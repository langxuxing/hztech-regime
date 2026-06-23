# Trend / Regime Judgment — Demo → Production Work Plan

> Focus statement: **"Judge the current trend."** This is the single capability with the
> highest business value in this system. Everything else (LLM advice text, event engine,
> dashboard cosmetics, extra data sources) is secondary and must serve this one question:
>
> **"Right now, what regime is BTC in (up / down / range), how strong, how confident, and
> is it about to flip?"**
>
> In this codebase "region" == **regime** (市场状态). The "main data" is BTC OHLCV
> (local 1m → resampled) plus derivatives (funding / OI / CVD) and the macro‑hazard gate.
> The "main algorithm" is the regime engine + triad (BOCPD + HMM + fusion) + the model
> ensemble with the human‑feedback leaderboard.

This document is a phased, implementable plan. Each phase has: **Goal → Tasks (with file
references) → Acceptance criteria → Risks**. Phases are ordered so that each one leaves the
system in a shippable state. You can stop after any phase and still have value.

---

## 0. Scope decision (do this first)

To move fast, explicitly narrow the surface area. Concretely:

**In scope (the trend/regime core):**

- `ai_trade_advisor/regime/engine.py` — rule regime (Donchian/KAMA × vol × CVD × derivatives × macro).
- `ai_trade_advisor/regime/triad/` — BOCPD changepoint + HMM + fusion (the "is it flipping?" signal).
- `ai_trade_advisor/regime/models/ensemble.py` + `algorithm/` — multi‑model regime votes.
- `ai_trade_advisor/regime/feedback/` — leaderboard, calibration, recommender.
- `ai_trade_advisor/forecast/ensemble.py` — short‑horizon trend consensus.
- Data feeding the above: `datasource/ohlcv.py`, `datasource/derivatives_trend.py`,
  `datasource/spot_cvd.py`, `datasource/funding_snapshot.py`, `features/macro_calendar_engine.py`.
- Serving of the above: `snapshot/worker.py`, `api_server.py` (`/api/radar`, `/api/regime/*`, `/api/trend-consensus`).

**Out of scope for now (freeze, do not invest):**

- New data sources beyond what regime needs (on‑chain depth, X monitor, ETF flows can stay
  in "best effort / degraded" mode).
- LLM advice text quality, prompt tuning (`ai/advisor.py`, `context/builder.py`) — keep the
  rule fallback, do not block production on the LLM.
- Dashboard visual redesign — keep it functional.

Write this scope decision into the PR / README so the team stops adding breadth.

**Deliverable:** a one‑paragraph "Trend Core Charter" appended to `README.md` and a
`labels`/`milestone` in the issue tracker so every task maps back to the trend question.

---

## 1. Define "production" for the trend signal (acceptance contract)

You cannot go demo→production without a measurable target. The repo already has tiers in
`ai_trade_advisor/readiness.py` (`demo` / `degraded` / `production`) and an audit in
`scripts/run_business_review.py`. Extend these into an explicit **Trend SLA**.

**Tasks**

1. Write a `docs/TREND_SLA.md` defining the contract, e.g.:
   - **Freshness:** regime snapshot age ≤ `SNAPSHOT_STALE_SEC` (default 300s) at p99.
   - **Availability:** `/api/radar` returns a valid regime ≥ 99.5% of polls.
   - **Data integrity:** local 1m OHLCV gap rate < 0.1% over trailing 24h; 0 OHLC logic
     violations (already audited in `audit_ohlcv_local`).
   - **Stability:** regime flip rate ≤ N flips/day on a flat market (anti‑noise; see L3 dwell).
   - **Accuracy:** see Phase 5 metrics (hit‑rate, transition lead time, calibration error).
2. Add a `tier == "production"` gate that also requires `local_btc_1m == True` (today a
   demo env can pass with ccxt fallback). Tighten `check_readiness` so the **trend core**
   has its own readiness verdict, separate from event/LLM readiness.
3. Make `scripts/run_business_review.py` exit non‑zero if any **trend‑critical** finding is
   `high`/`critical` (it already does for high/critical overall; tag trend‑specific ones).

**Acceptance:** `python scripts/check_readiness.py` and `python scripts/run_business_review.py`
both produce a clear PASS/FAIL for the trend core, and the criteria are documented.

---

## 2. Phase A — Data foundation for trend (the input must be trustworthy)

A trend signal is only as good as the bars feeding it. Today OHLCV is local 1m → resample,
and is **gitignored / not present** in fresh environments — the #1 demo→prod gap.

**Goal:** Guaranteed, gap‑free, monitored BTC OHLCV + derivatives feed.

**Tasks**

1. **Reliable ingestion.** Harden `scripts/okx_btc_fetch.py` / `scripts/data_scheduler.py`:
   - Incremental fetch with overlap + dedupe (already partly in `_load_local_1m_csvs`).
   - Automatic gap backfill when `audit_ohlcv_local` detects missing bars.
   - Persist scheduler health to `scheduler_meta` and expose via `/api/scheduler/status`.
2. **Data validation layer.** Promote the checks in `audit_ohlcv_local` (gaps, OHLC logic,
   zero‑volume) into a reusable `datasource/quality.py` that runs *inside* `load_ohlcv` and
   stamps a `data_quality` field onto the regime output (so the UI can show "degraded data").
3. **Derivatives feed.** Ensure `derivatives_trend.py` + `funding_snapshot.py` degrade
   gracefully (they already swallow exceptions). Add per‑source freshness/error counters.
4. **Fixtures for tests/backtest.** Commit a small, sanitized BTC 1m sample under
   `tests/fixtures/` so CI and backtests never depend on a live download.

**Acceptance:**

- Fresh clone + `./scripts/start-data-scheduler.sh` reaches `local_btc_1m == True` within one
  scheduler cycle.
- `run_business_review.py` reports `gap_count == 0` (or auto‑backfilled) and 0 OHLC violations.
- `load_ohlcv` returns a `data_quality` tag consumed by the snapshot.

**Risks:** exchange rate limits / API changes (mitigate with retry + ccxt fallback flag),
clock/timezone drift in resample (`SCHED_SYNC_TIMEZONE`).

---

## 3. Phase B — Lock down the trend judgment algorithm

**Goal:** A single, well‑defined, deterministic regime verdict with calibrated confidence and
an explicit "about to flip" flag.

**Tasks**

1. **Single source of truth.** `analyze_btc_regime()` in `regime/engine.py` is the canonical
   entry. Confirm the production path (`layers/orchestrator.py → run_l3_pipeline →
   confirm_regime_state`) and the backtest path use the *same* function (the review script
   already flags divergence in `audit_config_conflicts`). Remove/align any drift, especially
   `regime_min_dwell_bars` vs `DEFAULT_MIN_DWELL_BARS`.
2. **Confidence calibration.** `_confidence()` is currently hand‑tuned constants. Replace with
   a calibration informed by the feedback store (`regime/feedback/calibrator.py`) so
   `confidence` reflects measured hit‑rate per regime, not magic numbers. Keep the hand‑tuned
   values as priors.
3. **Transition signal.** The triad already yields `changepoint_prob`, `next_regime_label`,
   `in_regime_transition` (`regime/triad/fusion.py`). Make these first‑class in the API
   contract and define thresholds (e.g. `changepoint_prob > X` ⇒ surface "TRANSITION" to the
   business UI). This is the highest‑value business signal: *early warning of a trend flip.*
4. **Ensemble fusion.** `run_all_regime_models` + `fuse_with_leaderboard` already blend models
   with feedback weights. Define behaviour when models disagree (`needs_human_judgment`):
   product decision = surface "low confidence / human check" rather than guessing.
5. **Macro gate.** `evaluate_macro_hazard` forces `macro_frozen_range`. Confirm this is the
   intended business behaviour (force flat / observe during macro windows) and document it.

**Acceptance:**

- One deterministic regime per snapshot with `confidence`, `dashboard_regime`,
  `in_regime_transition`, `changepoint_prob`, and `drivers` (explainability).
- Unit tests pin the decision boundaries (`tests/test_regime_core.py`,
  `test_regime_models.py`, `test_regime_confirmation.py`) — extend to cover transition flags.
- Calibration test: confidence buckets match realized hit‑rate within tolerance on the sample set.

**Risks:** overfitting confidence to a small feedback set (use shrinkage toward priors).

---

## 4. Phase C — Anti‑noise & stability (business hates flicker)

**Goal:** The trend verdict must be stable enough to act on — no second‑by‑second flip‑flop.

**Tasks**

1. Verify L3 (`layers/l3_confirmation/regime_stabilizer.py`): dwell time, debounce, advice
   cooldown. Align `regime_min_dwell_bars` config with `DEFAULT_MIN_DWELL_BARS`.
2. Add a **hysteresis** test: feed a borderline series and assert flip count stays under SLA.
3. Black‑swan fast path (`black_swan/`) must be able to *override* dwell (instant suspend on a
   crash) — confirm precedence: black swan > dwell > normal transition.
4. Expose stability metrics (flips/day, mean dwell) in the snapshot for monitoring.

**Acceptance:** On a synthetic flat market, flip rate ≤ SLA; on a synthetic crash, suspension
fires within one bar. Covered by `tests/test_black_swan*.py` + new stability test.

---

## 5. Phase D — Evaluation & backtest framework (prove it works)

**Goal:** Quantify how good the trend judgment is, so "production" is evidence‑based and
regressions are caught automatically. This is what converts a demo into a trustworthy product.

**Tasks**

1. Build on `backtest/regime_backtest.py` (walk‑forward). Define and compute the core metrics:
   - **Directional hit‑rate** per regime (did `uptrend`/`downtrend` precede the right move?).
   - **Transition lead time** — bars between `in_regime_transition=True` and the actual flip.
   - **Stability / churn** — flips per day.
   - **Confidence calibration** — reliability curve / Brier score.
   - **Optional P&L proxy** — simple regime‑following strategy return vs buy‑and‑hold, as a
     business‑facing KPI (not investment advice; for evaluation only).
2. Produce a reproducible **backtest report** (extend `scripts/run_business_review.py` or add
   `scripts/run_trend_backtest.py`) writing JSON + Markdown to `data/exports/reviews/`.
3. Establish a **baseline + regression guardrail**: store last good metrics; CI fails if
   hit‑rate or calibration regresses beyond a threshold.
4. Compare the model ensemble members head‑to‑head (the feedback leaderboard already exists)
   and pick / weight the production default from backtest evidence.

**Acceptance:** A committed baseline report; CI runs the backtest on the fixture sample and
enforces no‑regression. Numbers are documented in `docs/TREND_SLA.md`.

**Risks:** lookahead bias (use `df_confirmed`, never `df_live`, for scoring), tiny sample
overfit (walk‑forward, out‑of‑sample windows).

---

## 6. Phase E — Serving, observability, and hardening

**Goal:** The compute/serve split (already designed: snapshot worker → JSON → read‑only Flask
API) runs reliably 24/7 with monitoring and auth.

**Tasks**

1. **Freshness guarantees.** Worker (`snapshot/worker.py`) writes `data/cache/snapshots/*.json`;
   API serves cache with `SNAPSHOT_STALE_SEC`. Make the API return an explicit `stale: true`
   flag + last‑computed age so consumers never act on stale trends silently.
2. **Health & metrics endpoints.** Add `/healthz` (liveness) and `/readyz` (calls
   `check_readiness`, fails if trend core not production). Emit metrics: snapshot age, compute
   latency, source error counts, regime flip counter, data_quality.
3. **Auth & limits.** `API_KEY` auth already exists (`tests/test_api_auth.py`). Confirm it is
   enforced on all trend endpoints; add basic rate limiting.
4. **Structured logging** with snapshot_id/version correlation (the snapshot already carries
   `version` + `snapshot_id`).
5. **Graceful degradation contract.** Define exactly what the API returns when: data stale,
   models error, macro hazard active, sources down. Each must yield a *safe* verdict
   (e.g. neutral/observe) not a crash.

**Acceptance:** `/healthz`, `/readyz` exist; load a stale snapshot and confirm `stale:true`;
kill a data source and confirm the API still serves a degraded‑but‑valid regime.

---

## 7. Phase F — CI/CD, packaging, deployment

**Goal:** Repeatable build, test, and deploy. Today there is **no CI** and only a Docker
Compose dev setup.

**Tasks**

1. **CI pipeline** (e.g. `.github/workflows/ci.yml`): lint → `pytest` (uses the committed
   fixture, no network) → trend backtest no‑regression gate → build Docker image.
2. **Containerization.** `Dockerfile` + `docker-compose.yml` already define `api` +
   `snapshot-worker`. Pin dependency versions, add healthchecks to compose, externalize
   `./data` to a volume.
3. **Config/secrets.** All keys via env (`.env.example` is the reference). Document required
   vs optional. For production, secrets via the orchestrator's secret store, not committed.
4. **Deployment target.** Choose one: single VM + Docker Compose + reverse proxy (simplest), or
   container service / k8s if scale is needed. Provide a one‑command deploy script.
5. **Backups.** SQLite stores (`data/db/events.db`, `regime_history.db`) — scheduled backup +
   restore runbook, since the feedback/calibration history is now product‑critical.

**Acceptance:** Green CI on PRs; `docker compose up` brings up a healthy stack that passes
`/readyz`; documented deploy + rollback steps.

---

## 8. Phase G — Rollout, feedback loop, and operations

**Goal:** Ship safely and keep improving the trend judgment with the human‑feedback loop.

**Tasks**

1. **Shadow / canary.** Run the production worker in parallel with the current demo for a
   period, comparing regime verdicts and metrics before cut‑over.
2. **Human feedback loop.** `regime/feedback/` + `/api/regime/human-judgment` let humans label
   the true regime; the leaderboard re‑weights models. Make labeling a routine ops task and
   schedule `calibrator.py` recalibration (already a scheduler task hook).
3. **Alerting.** Page on: snapshot stale > threshold, worker down, data gap spike, model
   ensemble all‑error, sustained low confidence.
4. **Runbooks.** Document: "trend stuck/stale", "all sources down", "models disagree",
   "post‑macro re‑enable".
5. **Iterate.** Use Phase D metrics + feedback leaderboard to periodically promote the
   best‑performing model/weights as the production default.

**Acceptance:** Canery comparison shows parity or improvement; alerts fire in a drill;
recalibration runs on schedule and is reflected in the leaderboard.

---

## Milestone summary

| Phase | Outcome | Ship‑ready? |
|-------|---------|-------------|
| 0 | Scope locked to the trend core | n/a |
| 1 | Measurable production contract (Trend SLA + readiness gate) | n/a |
| A | Trustworthy, gap‑free, monitored data feed | ✅ data demo→prod |
| B | Single deterministic, calibrated regime verdict + transition flag | ✅ algorithm prod |
| C | Stable, anti‑noise output with black‑swan override | ✅ |
| D | Backtest + metrics + no‑regression guardrail (evidence) | ✅ trustworthy |
| E | Reliable serving, health, observability, graceful degradation | ✅ ops prod |
| F | CI/CD + containerized deploy + backups | ✅ deployable |
| G | Canary rollout + feedback loop + alerting + runbooks | ✅ in production |

**Recommended critical path (minimum viable production):** 0 → 1 → A → B → C → E → F.
Phase D should run in parallel from the start (you need metrics to trust B/C). Phase G is the
final cut‑over.

---

## Definition of Done (the whole effort)

The trend core is "in production" when **all** are true:

1. `check_readiness` reports `tier == production` for the trend core in the deploy env.
2. `/api/radar` serves a fresh, calibrated regime with `confidence`, `in_regime_transition`,
   `changepoint_prob`, `drivers`, and a `stale`/`data_quality` flag.
3. A committed backtest baseline exists and CI blocks regressions.
4. Health/readiness endpoints + alerting + backups are live.
5. The human‑feedback recalibration loop runs on schedule.
6. Runbooks exist for the top failure modes.

> Anything that does not move one of these six items forward is, by definition, out of scope
> for the demo→production effort. Keep the focus on **the trend judgment.**
