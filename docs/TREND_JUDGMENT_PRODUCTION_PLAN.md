# Trend Judgment → Production Work Plan

> Goal: take the existing sprawling system (data + algorithms + models + regime + AI
> prediction) and **focus it on the single most business-useful capability: judging the
> current BTC trend/regime**, using the *main* data and the *main* algorithms to compute the
> region (regime), and harden that one capability from a **demo system into a production
> system**.

This plan is intentionally opinionated about **scope**. The codebase today does many things
(LLM advice, event/X monitoring, ETF/on-chain flows, multi-model leaderboards, dashboards).
For a production trend-judgment product, most of those are *secondary inputs or side
features*. The plan below defines the **core spine**, what to keep, what to defer, and a
phased path with concrete acceptance criteria tied to actual files in this repo.

---

## 0. Guiding principle — one job, done reliably

**The product's one job:**

> Given live BTC market data, output *the current trend/regime*, *how confident we are*,
> *how likely it is to flip soon*, and *whether it is actionable* — fast, fresh, and with an
> honest data-quality label.

Everything is judged against that sentence. If a component does not improve the accuracy,
calibration, stability, freshness, or trustworthiness of that output, it is **not** in the
v1 critical path.

### In-scope core spine

```
L1 main data  →  features  →  L2 regime engine  →  L3 confirmation/debounce
            →  confidence + changepoint/transition  →  trend output contract  →  read-only API
```

Concretely, the spine is:

| Stage | Primary code | Role |
|------|--------------|------|
| Main data | `datasource/ohlcv.py`, `datasource/spot_cvd.py`, `datasource/derivatives_trend.py`, `datasource/funding_snapshot.py` | The minimal sufficient inputs |
| Features | `features/indicators.py` (Donchian/KAMA/ATR), `features/smc.py` | Structure + volatility |
| Regime engine | `regime/engine.py` (`analyze_btc_regime`) | **The trend decision** |
| Probabilistic confirm | `regime/triad/` (BOCPD + HMM + transition), `regime/models/ensemble.py` + `algorithm/` | Changepoint, transition, agreement |
| Confirmation | `layers/l3_confirmation/` (`run_l3_pipeline`, `regime_stabilizer.py`), `signal/debouncer.py` | Anti-whipsaw / dwell |
| Calibration & feedback | `regime/feedback/` (`calibrator.py`, `scoring.py`, `rollup.py`, `recommender.py`) | Make confidence honest |
| Serving | `snapshot/worker.py` + `api_server.py` | Compute/serve separation |

### Deferred to "secondary" (keep behind flags, NOT in the v1 critical path)

- LLM trade advice text (`ai/advisor.py`) — useful UX, but not the trend judgment itself.
- Event / calendar / X monitoring (`bigevent/`, `datasource/x_monitor.py`) — keep only the
  **macro-hazard circuit breaker** (`features/macro_calendar_engine.py`) as a safety input.
- ETF / on-chain capital flows (`datasource/etf_flow.py`, `onchain.py`, `capital_flows.py`)
  — context enrichers, not core.
- Orderbook microstructure / GEX (`features/gex_proxy.py`, `liquidity_map.py`, `signal/`
  OBI) — optional Tier-2 confirmation.
- Multi-asset (PEPE/ETH) — BTC-only for v1.

These stay in the repo and remain callable, but they must be **toggleable off** and must
never block or crash the core trend output.

---

## 1. Current-state assessment

**Strengths already in place (do not rebuild):**

- A real regime decision tree: `analyze_btc_regime` maps `raw_trend ∈ {uptrend, downtrend,
  range}` × `vol_bucket ∈ {low, mid, high}` + CVD/derivatives/macro into **11 regimes**
  with labels, confidence, and drivers.
- A 4-layer orchestration (`layers/orchestrator.py`) with confirmation/debounce and a
  black-swan circuit breaker.
- Probabilistic layer: BOCPD changepoint + HMM + transition matrix (`regime/triad/`), plus
  an 8-model ensemble in `algorithm/` and `regime/models/`.
- A feedback/calibration scaffold (`regime/feedback/`) and a human-judgment store.
- Compute/serve separation (snapshot worker + read-only Flask API) and a readiness tiering
  (`readiness.py`: `demo | degraded | production`).
- A backtest harness skeleton with **forward-return-by-regime** (`backtest/regime_backtest.py`).
- A self-audit "business review" script (`scripts/run_business_review.py`) and ~35 test files.

**Demo→production gaps observed (these drive the phases below):**

1. **Data reliability is the #1 risk.** `audit_ohlcv_local` already checks for 1m time
   gaps, OHLC logic violations, and zero-volume bars; the core requires
   `load_ohlcv` source == `local_btc_1m_resample`. Gaps/violations directly corrupt
   Donchian/KAMA/HMM and therefore the trend call. There is no hard data-quality gate that
   *stops* a low-quality trend from being published.
2. **The trend output is not yet a frozen, versioned contract.** `BtcRegimeAnalysis.to_dict`
   is rich but evolving; consumers (API/dashboard) need a stable schema with `as_of`,
   `data_quality`, `confidence` semantics, and SLA guarantees.
3. **Confidence is heuristic, not calibrated.** `_confidence()` is hand-tuned constants.
   `feedback/calibrator.py` exists but needs to be wired so published confidence reflects
   *measured* forward outcomes (Brier/log-loss).
4. **Usefulness is asserted, not proven.** The backtest computes forward returns per regime
   but there is no published acceptance report ("directional regimes have correct forward
   sign X% of the time; range regimes have low drift; churn rate is Y").
5. **Ops/security not production-grade.** API auth exists (`api_auth.py` / `API_KEY`) but
   rate limiting, structured logging, metrics, alerting, and deployment/runbook are thin.
6. **Environment fragility.** Core Python deps are not installed in a fresh checkout; tiering
   silently degrades to `demo`. Production needs deterministic, reproducible setup.

---

## 2. Define the trend-output contract (do this first — it anchors everything)

Freeze a stable JSON contract returned by the core and served by the API. Proposed fields
(superset of today's `BtcRegimeAnalysis.to_dict`, with production additions in **bold**):

```jsonc
{
  "as_of": "2026-06-23T17:40:00Z",      // bar close timestamp (UTC)   ** add
  "snapshot_id": "btc-30m-...",         // for reproducibility          ** add
  "symbol": "BTC/USDT:USDT",
  "regime_id": "high_vol_uptrend",
  "regime_label": "高波上涨 · 现货 CVD 确认",
  "raw_trend": "uptrend",               // uptrend | downtrend | range
  "vol_bucket": "high_vol",
  "dashboard_regime": "trend_up",       // trend_up | trend_down | range | transition | high_vol
  "confidence": 0.82,                   // ** must be CALIBRATED, not heuristic
  "changepoint_prob": 0.11,             // BOCPD
  "next_regime_label": "...",
  "in_regime_transition": false,
  "regime_age_bars": 7,                 // ** dwell/age since last switch
  "actionable": true,                   // ** = confidence>=thr & !transition & !hazard
  "drivers": ["KAMA 轨道 ...", "..."],
  "data_quality": "ok",                 // ** ok | degraded | stale | insufficient
  "tier": "production",                 // from readiness.py
  "model_agreement": 0.75,              // ** ensemble consensus
  "schema_version": "1.0"               // ** contract version
}
```

Also publish an **SLA**:

- **Freshness:** trend reflects the latest closed 30m bar within `SNAPSHOT_STALE_SEC`.
- **Latency:** API p95 < 200 ms (reads cache only).
- **Availability:** 99.5% for `GET /api/trend` (new focused endpoint, see Phase 3).
- **Honesty:** if `data_quality != ok`, `actionable=false` and `confidence` is capped.

**Deliverable:** a documented `schema_version: 1.0` + a contract test that fails if fields
are removed/renamed.

---

## 3. Pin the "main data" and "main algorithms"

This is the user's explicit requirement: *use the main data and algorithms to compute the
region.* Define three tiers so production degrades gracefully.

### Main data (Tier-0, REQUIRED to publish a trend)

| Data | Source (existing) | Used for |
|------|-------------------|----------|
| 30m OHLCV (from local 1m resample) | `datasource/ohlcv.py` | Donchian/KAMA/ATR → `raw_trend`, `vol_bucket` |
| Spot CVD | `datasource/spot_cvd.py` | confirm real buying vs fake breakout |
| Funding / OI (derivatives) | `funding_snapshot.py`, `derivatives_trend.py` | trend confirmation votes |

If Tier-0 is incomplete → `data_quality=insufficient`, `actionable=false` (never crash).

### Main algorithms (the regime computation)

1. **Rule engine spine** — `regime/engine.py::analyze_btc_regime` (`_raw_trend`,
   `_vol_bucket`, `_compose_regime`, `_confidence`). This is the authoritative regime label.
2. **Probabilistic confirmation** — `regime/triad/` BOCPD changepoint + HMM regime +
   transition matrix → `changepoint_prob`, `in_regime_transition`, `next_regime_label`.
3. **Ensemble agreement** — `regime/models/ensemble.py` + `algorithm/` (HMM, clustering,
   MSAR, hybrid, heuristic) → `model_agreement`, divergence flag.
4. **Stabilization** — `layers/l3_confirmation/regime_stabilizer.py` + `signal/debouncer.py`
   (dwell/transition penalty) → anti-whipsaw.
5. **Calibration** — `regime/feedback/calibrator.py` → turns agreement + history into honest
   `confidence`.

### Tier-1 / Tier-2 enhancers (optional, off by default in v1 critical path)

- Tier-1: macro-hazard circuit breaker, black-swan fast alert (safety only).
- Tier-2: orderbook OBI, GEX proxy, ETF/on-chain flows, LLM narrative, events.

**Deliverable:** a single config profile (e.g. `TREND_CORE_ONLY=true`) that runs the spine
with Tier-0 data + the 5 algorithms and disables Tier-2, proving the focused path works
end-to-end without external API keys.

---

## Phased roadmap (demo → production)

Each phase has **objectives → tasks → acceptance criteria**. Phases are ordered by
dependency; you can implement them sequentially.

### Phase 0 — Lock scope & establish a green baseline (demo hardening)

**Objective:** reproducible environment, frozen contract, all core tests green.

Tasks:
- Pin and document deterministic setup (`pip install -e ".[dev]"`); fix the fresh-checkout
  missing-deps issue; add a `make setup` / `scripts/setup.sh` smoke check.
- Freeze the trend-output contract from §2 (`schema_version: 1.0`) and add a contract test.
- Add the `TREND_CORE_ONLY` profile from §3.
- Run `scripts/run_business_review.py` and record the baseline report.
- Get the core test subset green: `test_regime_core`, `test_regime_confirmation`,
  `test_regime_models`, `test_regime_triad`, `test_layers`, `test_ohlcv_local`,
  `test_readiness`, `test_derivatives_trend`, `test_taker_cvd`.

Acceptance:
- Fresh clone → setup → `pytest` core subset passes.
- `business_review` produces a report with **0 critical** findings on the data path.
- Contract test passes; `GET` of the trend dict matches `schema_version 1.0`.

### Phase 1 — Data reliability (the main-data backbone)

**Objective:** the trend is never computed on silently-bad data.

Tasks:
- Harden BTC 1m ingestion: dedupe, enforce monotonic timestamps, OHLC-logic validation,
  gap detection + (where possible) backfill; surface counts. Extend the checks already in
  `audit_ohlcv_local` into the runtime `load_ohlcv` path.
- Implement a **data-quality gate** in L1 (`layers/l1_ingestion/`): classify `ok / degraded
  / stale / insufficient` and propagate into the trend contract; cap `confidence` and set
  `actionable=false` when not `ok`.
- Harden the scheduler (`scripts/data_scheduler.py`, `btc_1m_scheduler.py`): retries with
  backoff, last-success heartbeat, alert on staleness > threshold.
- Make Tier-0 secondary sources (CVD, funding) degrade independently without breaking the
  core trend.

Acceptance:
- Inject a gap / OHLC violation → pipeline marks `data_quality=degraded|insufficient` and
  does **not** publish an actionable trend (test-covered).
- Scheduler recovers from a simulated fetch outage; staleness alert fires.
- 7-day continuous run with `ohlcv_source == local_btc_1m_resample` and zero unhandled
  ingestion exceptions.

### Phase 2 — Validate usefulness & calibrate confidence (the business proof)

**Objective:** prove the trend call is *useful for business* and make confidence honest.
This is the phase that converts "a demo that looks smart" into "a tool a desk would trust."

Tasks:
- Extend `backtest/regime_backtest.py` into a repeatable evaluation that reports, per regime:
  forward-return distribution, **directional hit-rate** (sign of forward return vs trend),
  expectancy, max adverse excursion, and **regime churn / whipsaw rate** (switches per day).
- Define and document **business acceptance metrics** (targets to be tuned on data), e.g.:
  - Directional regimes (`*_uptrend` / `*_downtrend`): forward-return sign accuracy materially > 50% over the chosen horizon (`regime_forward_bars`).
  - Range regimes: low absolute forward drift (mean-reverting), high time-in-regime.
  - `fake_breakout_wash`: negative/again forward edge vs naive breakout (validates the CVD filter's value).
  - Calibration: low Brier score / reliability-curve error between published `confidence`
    and realized correctness.
  - Stability: regime churn below a target (tune `regime_min_dwell_bars`,
    `regime_transition_penalty`).
- Wire `feedback/calibrator.py` so published `confidence` is the **calibrated** value, not
  the hand-tuned constants in `_confidence()`.
- Tune dwell / transition penalty using the churn metric; add a parameter snapshot
  (`feedback/params_store.py`) so config is reproducible.

Acceptance:
- A committed evaluation report (e.g. `data/exports/reviews/trend_eval_*.md`) with the
  metrics above on a defined history window.
- Reliability curve shows calibrated confidence (documented Brier improvement vs the old
  heuristic).
- Churn rate within target on the validation window.

### Phase 3 — Productionize serving, ops & security

**Objective:** a stable, observable, secured service.

Tasks:
- Add a focused **`GET /api/trend`** endpoint returning exactly the §2 contract (reuse the
  snapshot worker compute path; read-only). Keep existing `/api/radar` etc. as secondary.
- Compute/serve hardening: snapshot worker is the only writer; API only reads cache; cold
  start warmup (`SNAPSHOT_WARMUP_ON_START`).
- Security: enforce `API_KEY` (`api_auth.py`), per-key rate limiting, strict CORS, input
  validation, no stack traces leaked.
- Observability: structured JSON logs; metrics for **freshness lag, p95 latency, error
  rate, regime distribution, model-failure count, data_quality breakdown**; `/health` +
  `/api/scheduler/status` as liveness/readiness; alerting on staleness / error spikes /
  worker death.
- Resilience: retries+backoff on all network fetches; keep the black-swan circuit breaker
  (`black_swan/`) as the safety governor; graceful tier degradation.
- Deployment: production `docker-compose` (worker + API) → container image; env-only config;
  secrets via env/secret store; pinned dependency versions.

Acceptance:
- `GET /api/trend` p95 < 200 ms; rejects missing/invalid key; CORS enforced.
- Dashboards show the metrics above; killing the worker triggers a staleness alert.
- One-command deploy brings up worker + API; survives a dependency restart.

### Phase 4 — Continuous learning & business feedback loop

**Objective:** the trend judgment keeps improving and is monitored for drift.

Tasks:
- Run the feedback loop in production: human-judgment capture
  (`/api/regime/human-judgment`), scoring (`feedback/scoring.py`), leaderboard, recommender
  (`recommender.py`), scheduled calibration (`feedback/worker.py`,
  `REGIME_CALIBRATION_INTERVAL_HOURS`).
- Add **drift detection**: alert when live regime distribution or model agreement diverges
  from the validation baseline; alert when realized hit-rate decays.
- Model lifecycle: version + register model params; scheduled refit; rollback path.
- Business reporting: automated daily "trend report" (current regime, confidence, recent
  accuracy) and a periodic re-run of the Phase-2 evaluation on rolling windows.

Acceptance:
- Calibration job runs on schedule and updates confidence mapping.
- Drift alert fires on an injected distribution shift.
- Daily report artifact is generated automatically.

### Phase 5 — Launch readiness

**Objective:** safe go-live.

Tasks:
- Staging soak (run Phases 1–4 against live data for an extended window); canary; rollback.
- Runbook: how to restart worker/API, interpret `data_quality`/`tier`, respond to staleness
  and black-swan alerts, backfill data.
- Data retention & DR: snapshot/db backups (`data/db/`), retention policy, restore drill.
- Final sign-off checklist mapped to each phase's acceptance criteria.

Acceptance:
- Staging meets SLA over the soak window; runbook validated by a dry-run incident; restore
  drill succeeds.

---

## 4. Explicit cut list for v1 (focus discipline)

Keep in repo, behind flags, **out of the critical trend path**:

- LLM trade-advice text generation.
- Event engine, exchange-announcement scraping, X/Twitter monitor.
- ETF & on-chain capital-flow enrichers.
- Orderbook OBI / GEX microstructure.
- Multi-asset (ETH/PEPE) support.

Re-introduce any of these **only** after it demonstrably improves a Phase-2 metric.

---

## 5. Risk register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Bad/stale OHLCV silently corrupts trend | High | Phase 1 data-quality gate + alerts |
| Overfitting in backtest | High | Out-of-sample window, churn + calibration checks, rolling re-eval |
| Regime whipsaw erodes trust | Med | Dwell/transition tuning, stabilizer, churn metric in acceptance |
| Confidence misleading | Med | Calibrator wired into published confidence |
| Worker death / cache staleness | High | Heartbeat, staleness alert, warmup, restart runbook |
| External API outage (Tier-1/2) | Low | Tier-0-only core keeps publishing; graceful degrade |
| Black-swan / macro shock | Med | Keep circuit breaker as safety governor |

---

## 6. Phase summary & dependencies

```
Phase 0 (scope+baseline)
        │
        ▼
Phase 1 (data reliability) ──► Phase 2 (validation + calibration)
                                        │
                                        ▼
                               Phase 3 (serving/ops/security)
                                        │
                                        ▼
                               Phase 4 (continuous learning)
                                        │
                                        ▼
                               Phase 5 (launch)
```

**North-star definition of done:** a secured, observable `GET /api/trend` that, for the
latest closed BTC 30m bar, returns a calibrated, stabilized regime judgment with an honest
data-quality label — backed by a committed evaluation report proving the directional regimes
have real forward edge and acceptable churn.
