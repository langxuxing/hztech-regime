#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKX 历史 K 线拉取：BTC-USDT-SWAP 标记价格（mark price）。

参考 CreativeIdeaLab/OHLCV/okx_pepe_fetch.py 的分日下载、重试与 failover 逻辑。
数据源：GET /api/v5/market/history-mark-price-candles
分日文件名：btc_usdt_swap_mark_{bar}_YYYY-MM-DD.csv（如 mark_15m、mark_1m）
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import certifi

    _CA_BUNDLE = certifi.where()
except ImportError:
    _CA_BUNDLE = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.datasource.paths import get_ohlcv_dir

logger = logging.getLogger(__name__)

OKX_BASE_HOSTS = ("https://www.okx.com", "https://aws.okx.com")
OKX_PATH_MARK = "/api/v5/market/history-mark-price-candles"
INST_ID = "BTC-USDT-SWAP"
DEFAULT_BAR = "15m"
_BAR_PRESETS: dict[str, tuple[int, str]] = {
    "1m": (60_000, "mark_1m"),
    "15m": (15 * 60_000, "mark_15m"),
}
LIMIT = 100
RATE_LIMIT_DELAY = 1.0
MAX_RETRIES = 5
BACKOFF_FACTOR = 2.0
RETRY_DELAY = 2.0
RATE_LIMIT_WAIT_BASE = 5.0
SSL_COOLDOWN_BASE = 10.0
COOLDOWN_AFTER_FAILURES = 2
MAX_COOLDOWN_SEC = 120.0
PAUSE_RETRY_CYCLES = 3
COOLDOWN_PAUSE_SEC = 30.0
COLUMNS_MARK = ["ts", "open", "high", "low", "close", "confirm"]

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = get_ohlcv_dir("Btc")

_runtime: dict = {
    "pause_retries": PAUSE_RETRY_CYCLES,
    "cooldown_pause_sec": COOLDOWN_PAUSE_SEC,
    "okx_bases": None,
    "proxy": None,
    "bar": DEFAULT_BAR,
    "ms_per_bar": _BAR_PRESETS[DEFAULT_BAR][0],
    "file_suffix": _BAR_PRESETS[DEFAULT_BAR][1],
}


def _configure_bar(bar: str) -> None:
    key = bar.strip().lower()
    if key not in _BAR_PRESETS:
        raise ValueError(f"不支持的 bar: {bar!r}，可选: {', '.join(sorted(_BAR_PRESETS))}")
    ms, suffix = _BAR_PRESETS[key]
    _runtime["bar"] = key
    _runtime["ms_per_bar"] = ms
    _runtime["file_suffix"] = suffix


def _bar() -> str:
    return str(_runtime["bar"])


def _ms_per_bar() -> int:
    return int(_runtime["ms_per_bar"])


def _file_suffix() -> str:
    return str(_runtime["file_suffix"])


def _configure_runtime(*, pause_retries: int | None = None, cooldown_pause_sec: float | None = None, okx_base: str | None = None, proxy: str | None = None) -> None:
    if pause_retries is not None:
        _runtime["pause_retries"] = max(0, int(pause_retries))
    if cooldown_pause_sec is not None:
        _runtime["cooldown_pause_sec"] = max(0.0, float(cooldown_pause_sec))
    if okx_base is not None:
        _runtime["okx_bases"] = (okx_base.rstrip("/"),)
    if proxy is not None:
        _runtime["proxy"] = proxy.strip() or None


def _active_okx_bases() -> tuple[str, ...]:
    bases = _runtime.get("okx_bases")
    return tuple(bases) if bases else OKX_BASE_HOSTS


def _normalize_okx_path(url_or_path: str) -> str:
    s = (url_or_path or "").strip()
    for base in OKX_BASE_HOSTS:
        if s.startswith(base):
            return s[len(base) :] or "/"
    if s.startswith("http://") or s.startswith("https://"):
        path = urlparse(s).path
        return path if path.startswith("/") else f"/{path}"
    return s if s.startswith("/") else f"/{s}"


def _is_transient_network_error(exc: BaseException) -> bool:
    if isinstance(exc, (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError)):
        return True
    msg = str(exc).lower()
    return any(k in msg for k in ("ssl", "connection", "unexpected_eof", "timed out", "reset by peer"))


class _OkxCooldown:
    def __init__(self) -> None:
        self._consecutive_failures = 0

    def extra_wait_sec(self) -> float:
        if self._consecutive_failures < COOLDOWN_AFTER_FAILURES:
            return 0.0
        n = self._consecutive_failures - COOLDOWN_AFTER_FAILURES + 1
        return min(COOLDOWN_PAUSE_SEC * (BACKOFF_FACTOR ** (n - 1)), MAX_COOLDOWN_SEC)

    def wait_if_needed(self) -> None:
        extra = self.extra_wait_sec()
        if extra > 0:
            logger.info("连续失败 %d 次，额外冷却 %.1fs", self._consecutive_failures, extra)
            time.sleep(extra)

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        self._consecutive_failures += 1

    def retry_wait_sec(self, attempt: int, exc: BaseException, backoff_factor: float) -> float:
        base = SSL_COOLDOWN_BASE if _is_transient_network_error(exc) else RETRY_DELAY
        return base * (backoff_factor**attempt)


_OKX_COOLDOWN = _OkxCooldown()


class _OkxHttpPool:
    def __init__(self) -> None:
        self._sessions: dict[str, requests.Session | None] = {}
        self._host_idx = 0

    def _ordered_hosts(self) -> tuple[str, ...]:
        hosts = _active_okx_bases()
        if len(hosts) <= 1:
            return hosts
        i = self._host_idx % len(hosts)
        return hosts[i:] + hosts[:i]

    def _get_session(self, base: str) -> requests.Session:
        s = self._sessions.get(base)
        if s is None:
            s = requests.Session()
            s.headers.update({"User-Agent": "okx-btc-fetch/1.0", "Accept": "application/json", "Connection": "close"})
            adapter = HTTPAdapter(max_retries=Retry(total=0, connect=0, read=0, redirect=0), pool_connections=2, pool_maxsize=2)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            self._sessions[base] = s
        return s

    def _drop_session(self, base: str) -> None:
        s = self._sessions.pop(base, None)
        if s is not None:
            try:
                s.close()
            except Exception:
                pass

    def rotate_host(self) -> None:
        hosts = _active_okx_bases()
        if len(hosts) > 1:
            self._host_idx = (self._host_idx + 1) % len(hosts)

    def get(self, path: str, *, params: dict, no_proxy: bool = False, timeout: float = 30) -> requests.Response:
        api_path = _normalize_okx_path(path)
        hosts = self._ordered_hosts()
        last_error: BaseException | None = None
        for hi, base in enumerate(hosts):
            try:
                if hi > 0:
                    logger.info("切换 OKX host → %s", base)
                session = self._get_session(base)
                kw = _request_kw(no_proxy)
                kw["timeout"] = timeout
                return session.get(base.rstrip("/") + api_path, params=params, verify=_CA_BUNDLE, **kw)
            except requests.exceptions.RequestException as e:
                last_error = e
                self._drop_session(base)
                if _is_transient_network_error(e) and hi + 1 < len(hosts):
                    logger.warning("host %s 不可用，尝试下一 host: %s", base, e)
                    continue
                raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("无可用 OKX host")


_OKX_HTTP = _OkxHttpPool()


def _request_kw(no_proxy: bool) -> dict:
    kw: dict = {}
    proxy = _runtime.get("proxy")
    if no_proxy:
        kw["proxies"] = {"http": None, "https": None}
    elif proxy:
        kw["proxies"] = {"http": proxy, "https": proxy}
    kw["headers"] = {"Connection": "close"}
    return kw


def _ts_fmt(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _now_utc_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _okx_request_get(path: str, params: dict, *, no_proxy: bool = False, context: str = "") -> requests.Response:
    pause_retries = int(_runtime["pause_retries"])
    cooldown_pause_sec = float(_runtime["cooldown_pause_sec"])
    ctx = f" ({context})" if context else ""
    last_error: BaseException | None = None

    for pause_cycle in range(pause_retries + 1):
        for attempt in range(MAX_RETRIES + 1):
            try:
                _OKX_COOLDOWN.wait_if_needed()
                r = _OKX_HTTP.get(path, params=params, no_proxy=no_proxy)
                if r.status_code == 429 or "Too Many Requests" in (r.text or ""):
                    wait = RATE_LIMIT_WAIT_BASE * (BACKOFF_FACTOR**attempt)
                    if attempt < MAX_RETRIES:
                        _OKX_COOLDOWN.record_failure()
                        logger.warning("OKX 限频(429)%s，%.1fs 后重试", ctx, wait)
                        time.sleep(wait)
                        continue
                    r.raise_for_status()
                r.raise_for_status()
                _OKX_COOLDOWN.record_success()
                return r
            except (requests.exceptions.RequestException, RuntimeError) as e:
                last_error = e
                _OKX_COOLDOWN.record_failure()
                if attempt < MAX_RETRIES:
                    wait = _OKX_COOLDOWN.retry_wait_sec(attempt, e, BACKOFF_FACTOR)
                    logger.warning("请求失败%s，%.1fs 后重试: %s", ctx, wait, e)
                    time.sleep(wait)
                else:
                    break
        if pause_cycle < pause_retries and last_error is not None:
            wait = cooldown_pause_sec * (BACKOFF_FACTOR**pause_cycle)
            _OKX_HTTP.rotate_host()
            for base in _active_okx_bases():
                _OKX_HTTP._drop_session(base)
            logger.warning("批次仍失败%s，暂停 %.1fs 后整轮重试", ctx, wait)
            time.sleep(wait)
        else:
            break
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"OKX 请求失败{ctx}")


def _fetch_chunk(after_ts: int, before_ts: int, *, no_proxy: bool = False) -> list[list[str]]:
    ms = _ms_per_bar()
    okx_before = str(after_ts - 1) if after_ts % ms == 0 else str(after_ts)
    params = {"instId": INST_ID, "bar": _bar(), "limit": str(LIMIT), "after": str(before_ts), "before": okx_before}
    r = _okx_request_get(OKX_PATH_MARK, params, no_proxy=no_proxy, context=_ts_fmt(after_ts))
    data = r.json()
    if data.get("code") != "0":
        raise RuntimeError(f"OKX API error: {data.get('msg', data)}")
    return data.get("data") or []


def _get_end_ts(no_proxy: bool = False) -> int:
    params = {"instId": INST_ID, "bar": _bar(), "limit": "1"}
    r = _okx_request_get(OKX_PATH_MARK, params, no_proxy=no_proxy, context="latest")
    data = r.json()
    if data.get("code") != "0" or not data.get("data"):
        raise RuntimeError(f"OKX API error or no data: {data}")
    ts = int(data["data"][0][0])
    now_ms = _now_utc_ms()
    if ts > now_ms + 2 * _ms_per_bar():
        logger.warning("OKX 最新 K 线时间 %s 晚于本机 UTC，按本机截断", _ts_fmt(ts))
        return now_ms
    return ts


def _parse_date_utc(s: str) -> int:
    dt = datetime.strptime(s.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _utc_day_end_ms(day_start_ms: int) -> int:
    return day_start_ms + 24 * 60 * 60 * 1000 - 1


def _iter_utc_days(start_day: str, end_day: str) -> list[str]:
    a = datetime.strptime(start_day.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc).date()
    b = datetime.strptime(end_day.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc).date()
    if a > b:
        raise ValueError("start_day 不能晚于 end_day")
    out: list[str] = []
    d = a
    while d <= b:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _per_day_filepath(out_dir: Path, day: str) -> Path:
    return out_dir / f"btc_usdt_swap_{_file_suffix()}_{day}.csv"


def _fetch_rows_in_range(since_ts: int, until_ts: int, *, no_proxy: bool = False, rate_limit_delay: float = RATE_LIMIT_DELAY) -> list[list[str]]:
    if since_ts > until_ts:
        return []
    if since_ts == until_ts:
        batch = _fetch_chunk(since_ts - 1, until_ts + _ms_per_bar(), no_proxy=no_proxy)
        time.sleep(rate_limit_delay)
        out = [row for row in batch if since_ts <= int(row[0]) <= until_ts]
        out.sort(key=lambda x: int(x[0]))
        return out
    chunk_size = LIMIT * _ms_per_bar()
    all_rows: list[list[str]] = []
    t = until_ts
    n_chunks = 0
    while t > since_ts:
        before_ts = t
        t = max(since_ts, t - chunk_size)
        after_ts = t
        all_rows.extend(_fetch_chunk(after_ts, before_ts, no_proxy=no_proxy))
        n_chunks += 1
        if n_chunks % 10 == 0:
            logger.info("进度: 已下载 %d 条", len(all_rows))
        time.sleep(rate_limit_delay)
    seen: set[str] = set()
    unique = [row for row in all_rows if row[0] not in seen and not seen.add(row[0])]
    unique.sort(key=lambda x: int(x[0]))
    return [row for row in unique if since_ts <= int(row[0]) <= until_ts]


def _save_csv(rows: list[list[str]], out_path: Path) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(",".join(COLUMNS_MARK) + "\n")
        for row in rows:
            f.write(",".join(row) + "\n")


def _read_csv_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header != COLUMNS_MARK:
            raise ValueError(f"CSV 表头不符: {path}")
        for row in reader:
            if row:
                rows.append(row)
    rows.sort(key=lambda x: int(x[0]))
    return rows


def _merge_rows(*groups: list[list[str]]) -> list[list[str]]:
    seen: set[str] = set()
    merged: list[list[str]] = []
    for group in groups:
        for row in group:
            ts = row[0]
            if ts in seen:
                continue
            seen.add(ts)
            merged.append(row)
    merged.sort(key=lambda x: int(x[0]))
    return merged


def download_btc_mark_one_utc_day(
    day: str,
    out_dir: str | Path,
    *,
    no_proxy: bool = False,
    skip_existing: bool = True,
    rate_limit_delay: float = RATE_LIMIT_DELAY,
) -> Path | None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _per_day_filepath(out_dir, day.strip())
    if skip_existing and path.is_file() and path.stat().st_size > 0:
        logger.info("已存在，跳过: %s", path)
        return None
    day_start = _parse_date_utc(day)
    until_ts = min(_utc_day_end_ms(day_start), _get_end_ts(no_proxy=no_proxy))
    since_ts = day_start
    if since_ts > until_ts:
        logger.warning("UTC %s 无可用区间，跳过", day)
        return None
    logger.info("拉取 UTC 日 %s (mark %s): %s ~ %s", day, _bar(), _ts_fmt(since_ts), _ts_fmt(until_ts))
    rows = _fetch_rows_in_range(since_ts, until_ts, no_proxy=no_proxy, rate_limit_delay=rate_limit_delay)
    if not rows:
        logger.warning("UTC %s 无数据", day)
        return None
    _save_csv(rows, path)
    logger.info("已写入 %s (%d 条)", path, len(rows))
    return path


def download_btc_mark_incremental_today(
    out_dir: str | Path,
    *,
    no_proxy: bool = False,
    rate_limit_delay: float = RATE_LIMIT_DELAY,
) -> Path | None:
    """增量更新当日 UTC CSV：从文件最后一条 ts 拉取到最新。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).date().isoformat()
    path = _per_day_filepath(out_dir, day)
    day_start = _parse_date_utc(day)
    until_ts = min(_utc_day_end_ms(day_start), _get_end_ts(no_proxy=no_proxy))

    existing: list[list[str]] = []
    since_ts = day_start
    if path.is_file() and path.stat().st_size > 0:
        existing = _read_csv_rows(path)
        if existing:
            since_ts = int(existing[-1][0])

    if since_ts > until_ts:
        logger.info("已是最新: %s", path)
        return None

    logger.info("增量拉取 UTC %s (mark %s): %s ~ %s", day, _bar(), _ts_fmt(since_ts), _ts_fmt(until_ts))
    new_rows = _fetch_rows_in_range(since_ts, until_ts, no_proxy=no_proxy, rate_limit_delay=rate_limit_delay)
    if not new_rows and not existing:
        logger.warning("UTC %s 无数据", day)
        return None
    rows = _merge_rows(existing, new_rows)
    _save_csv(rows, path)
    added = len(rows) - len(existing)
    logger.info("已更新 %s (+%d 条, 共 %d 条)", path, added, len(rows))
    return path


def download_btc_mark_15m_one_utc_day(
    day: str,
    out_dir: str | Path,
    *,
    no_proxy: bool = False,
    skip_existing: bool = True,
    rate_limit_delay: float = RATE_LIMIT_DELAY,
) -> Path | None:
    _configure_bar("15m")
    return download_btc_mark_one_utc_day(
        day,
        out_dir,
        no_proxy=no_proxy,
        skip_existing=skip_existing,
        rate_limit_delay=rate_limit_delay,
    )


def download_btc_mark_utc_days(
    start_day: str,
    end_day: str,
    out_dir: str | Path | None = None,
    *,
    no_proxy: bool = False,
    skip_existing: bool = True,
    rate_limit_delay: float = RATE_LIMIT_DELAY,
) -> list[Path]:
    base = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    written: list[Path] = []
    for d in _iter_utc_days(start_day, end_day):
        p = download_btc_mark_one_utc_day(
            d,
            base,
            no_proxy=no_proxy,
            skip_existing=skip_existing,
            rate_limit_delay=rate_limit_delay,
        )
        if p is not None:
            written.append(p)
    return written


def download_btc_mark_15m_utc_days(
    start_day: str,
    end_day: str,
    out_dir: str | Path | None = None,
    *,
    no_proxy: bool = False,
    skip_existing: bool = True,
    rate_limit_delay: float = RATE_LIMIT_DELAY,
) -> list[Path]:
    _configure_bar("15m")
    return download_btc_mark_utc_days(
        start_day,
        end_day,
        out_dir,
        no_proxy=no_proxy,
        skip_existing=skip_existing,
        rate_limit_delay=rate_limit_delay,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    p = argparse.ArgumentParser(description="下载 BTC-USDT-SWAP 标记价格 K 线（OKX，按 UTC 分日 CSV）")
    p.add_argument("--start-date", type=str, metavar="YYYY-MM-DD", help="开始日期（UTC）")
    p.add_argument("--end-date", type=str, metavar="YYYY-MM-DD", help="结束日期（UTC）")
    p.add_argument("--days", type=int, metavar="N", help="回溯 N 天（含今天 UTC），无需 start/end")
    p.add_argument("--bar", type=str, default=DEFAULT_BAR, choices=sorted(_BAR_PRESETS), help=f"K 线周期，默认 {DEFAULT_BAR}")
    p.add_argument("--incremental", action="store_true", help="仅增量更新当日 UTC CSV")
    p.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT_DIR), help=f"输出目录，默认 {DEFAULT_OUT_DIR}")
    p.add_argument("--force", action="store_true", help="已存在非空文件仍重新下载")
    p.add_argument("--no-proxy", action="store_true", help="不使用代理")
    p.add_argument("--proxy", type=str, default=None, metavar="URL", help="HTTP 代理，如 http://127.0.0.1:7890")
    p.add_argument("--rate-limit-delay", type=float, default=RATE_LIMIT_DELAY, help="每次请求后等待秒数")
    args = p.parse_args()

    if args.no_proxy and args.proxy:
        raise SystemExit("--no-proxy 与 --proxy 不能同时使用")
    _configure_runtime(proxy=args.proxy)
    _configure_bar(args.bar)

    if args.incremental:
        path = download_btc_mark_incremental_today(
            args.out_dir,
            no_proxy=args.no_proxy,
            rate_limit_delay=args.rate_limit_delay,
        )
        if path is None:
            print("Done, no update")
        else:
            print(f"Done: {path}")
        return

    if args.days is not None:
        if args.days < 1:
            raise SystemExit("--days 须 >= 1")
        end_d = datetime.now(timezone.utc).date()
        start_d = end_d - timedelta(days=args.days - 1)
        start_s, end_s = start_d.isoformat(), end_d.isoformat()
    elif args.start_date and args.end_date:
        start_s, end_s = args.start_date, args.end_date
    else:
        raise SystemExit("请提供 --start-date 与 --end-date，或 --days N，或使用 --incremental")

    paths = download_btc_mark_utc_days(
        start_s,
        end_s,
        args.out_dir,
        no_proxy=args.no_proxy,
        skip_existing=not args.force,
        rate_limit_delay=args.rate_limit_delay,
    )
    print(f"Done, files: {len(paths)}")
    for x in paths:
        print(x)


if __name__ == "__main__":
    main()
