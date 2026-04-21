# IteraDynamics — Project Context

## What This Is

A crypto trend-following research and live-trading platform. The platform
backtests, validates, and deploys systematic strategies against hourly OHLCV
data. The primary asset is BTC/USD; ETH/USD has been added as a second sleeve.

---

## Current Production Strategy

**`trend_following_v8_ecap60_add80`** — this is the validated, deployment-ready strategy.

Key design: *asymmetric two-level exposure cap*
- Initial ENTER_LONG capped at 60% NAV
- Add-on entries (meta key `add_on: True`) capped at 80% NAV
- HOLDs and exits float freely — preserves the Exit/Entry convexity
- Exit/Entry ratio: 1.432x (BTC), 1.526x (ETH) — both well above the 1.2x fee survival threshold

Why this over hard caps: hard caps (e.g. `with_capped_exposure`) kill HOLDs too, collapsing
Exit/Entry to ~1.0x and destroying most of the CAGR.

---

## ML Calibration

Platt scaling (multivariate logistic) fitted via `scipy` only — no scikit-learn.

**BTC**: Calibrator trained, walk-forward validated as **LIKELY ROBUST** (5/5 folds improved DD,
4/5 improved Sharpe, 5/5 reduced slippage). Production model at:
`artifacts/ml_models/calibrator_trend_following_v8_ecap60_add80.json`
This file is gitignored — must be SCP'd to the server separately.

**ETH**: Walk-forward returned **MIXED / REGIME-DEPENDENT**. DD reduction was 6/6 (consistent),
but Sharpe/Calmar improvement was inconsistent because the calibrator is too conservative during
ETH bull runs (Platt can't capture win-magnitude asymmetry). Decision: run ETH uncalibrated.

Calibration flow: raw confidence → `PlattCalibrator.predict_from_features()` → calibrated confidence
→ `ExposureGovernor` threshold (0.35). Threshold is now statistically meaningful post-calibration.

---

## Portfolio Allocation

**60% BTC (calibrated) / 40% ETH (uncalibrated)**

| Sleeve | CAGR | Max DD | Sharpe | Calmar | Exit/Entry |
|--------|-----:|-------:|-------:|-------:|-----------:|
| BTC (cal) | +15.6% | -24.9% | 0.921 | 0.626 | 1.752x |
| ETH (uncal) | +26.0% | -51.1% | 0.770 | 0.510 | 1.526x |
| **Combined** | **+20.4%** | **-39.9%** | **0.809** | **0.512** | — |

Period: 2019-03-08 → 2025-12-31. Pairwise daily-return correlation: 0.557.

Rationale: BTC calibrated sleeve has superior Calmar (0.626) and is the risk-management
engine. ETH lifts CAGR (+4.8pp over BTC-only) while 60/40 weighting keeps combined DD
under -40%. Going higher on ETH weight worsens Calmar; going lower sacrifices return.

---

## Repository Layout

```
research/
  harness/
    backtest_engine.py      # run_backtest() — add calibrators= kwarg for calibrated runs
    data_loader.py          # load_ohlcv(), validate_ohlcv()
    execution_model.py      # ExecutionConfig — fee/slippage parameters
    metrics.py              # compute_metrics(), BacktestMetrics dataclass
    artifacts.py            # save_artifacts()
  strategies/
    contracts.py            # StrategyIntent, RegimeSignal, Action, StrategyContext
    __init__.py             # REGISTRY — all strategy modules registered here
    trend_following_v8_ecap60_add80.py   # THE production strategy
    trend_following_v8_ecap75_add90.py   # also validated (slightly worse than ecap60_add80)
    trend_following_v8_ecap50_add70.py   # built but walk-forward not run
  ml/
    calibration/
      platt_calibrator.py   # PlattCalibrator — scipy only, no sklearn
      training_data.py      # extract_calibration_samples()
      model_store.py        # load_calibrator(), save_calibrator() — JSON format
      __init__.py           # make_calibrated_strategy(), _apply_calibration()
    validation/
      fold_spec.py          # FoldSpec, build_annual_folds(), from_custom_json()
      walk_forward.py       # run_fold(), run_walk_forward() — no-leakage guaranteed
      report.py             # aggregate(), to_markdown(), save_report()
  regimes/
    baseline_engine.py      # BaselineRegimeEngine — TREND_UP/DOWN/RANGE classification
    contracts.py            # RegimeLabel, RegimeSignal
  portfolio/
    blend.py                # run_portfolio_backtest(), SleeveConfig — single-asset multi-strategy

scripts/
  run_backtest.py           # single asset, single strategy
  run_multiasset_portfolio.py  # N assets × N strategies, combined NAV — THE portfolio runner
  run_walk_forward.py       # walk-forward validation CLI
  train_calibrator.py       # fit and save PlattCalibrator to artifacts/ml_models/
  run_paper.py              # paper trading runner (to be wired to live feed)
  run_portfolio.py          # single-asset multi-strategy (older, less relevant now)
  analyze_trades.py         # trade analysis across multiple backtest runs

runtime/
  argus/
    apex_core/
      orchestrator.py       # live trading orchestrator — loads calibrators on init

tests/
  unit/
    test_calibration.py
  integration/
    test_walk_forward_validation.py
    test_calibrated_pipeline.py
```

---

## Git / Branch State

- **`main`** — production branch, deploy from this
- **`feature/entry-classifier`** — development branch where all this work was done; now merged to main
- All code is pushed and current

---

## Files That Must Be SCP'd to the Server (not in git)

```bash
# Data files
scp data/btcusd_3600s_2019-01-01_to_2025-12-30.csv  user@droplet:/path/to/ID_test/data/
scp data/ethusd_3600s_2019-01-01_to_2025-12-30.csv  user@droplet:/path/to/ID_test/data/

# Trained BTC calibrator (gitignored — in artifacts/)
scp artifacts/ml_models/calibrator_trend_following_v8_ecap60_add80.json \
    user@droplet:/path/to/ID_test/artifacts/ml_models/

# Environment variables
scp .env  user@droplet:/path/to/ID_test/.env
```

---

## Immediate Next Task: Paper Trading Setup

The server previously ran a volatility breakout strategy (which does not survive Coinbase
Advanced fees — Exit/Entry 0.871x). That code should be wiped after preserving any useful
operational infrastructure:
- Live data feed mechanism (how real-time prices arrive)
- Systemd/supervisor service config (keep-alive after crashes)
- API credentials setup

The new paper trading stack runs `run_multiasset_portfolio.py` logic but needs:
1. A live price feed (WebSocket or polling from Coinbase/Binance)
2. `run_paper.py` wired to that feed for BTC and ETH
3. The calibrator loaded for BTC sleeve, ETH runs uncalibrated
4. Systemd service to keep it alive

---

## Key Decisions Already Made (do not re-litigate)

- **No scikit-learn** — calibration uses scipy only (L-BFGS-B minimisation)
- **Asymmetric cap** — only cap initial ENTER_LONG, not HOLDs/add-ons
- **ETH uncalibrated** — walk-forward was MIXED; calibration suppresses ETH bull runs
- **60/40 BTC/ETH** — optimal risk-adjusted allocation given the two sleeves
- **No mean_reversion, no volatility_breakout** — both fail the Exit/Entry > 1.2x fee test
- **Calmar plateau at ~0.53 (uncalibrated)** — fundamental signal property, not a sizing issue
- **Platt calibration** — sigmoid(A × raw_conf + B), fitted on trade cycle outcomes

---

## Execution Parameters (production)

```
taker_fee_rate:      0.0006   (6 bps — Coinbase Advanced)
base_slippage_bps:   3.0
slippage_vol_factor: 50.0
cooldown_bars:       0
rebalance_threshold: 0.05
```

---

## How to Run Things

```bash
# Baseline backtest
python scripts/run_backtest.py \
    --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \
    --strategy trend_following_v8_ecap60_add80 --asset BTC

# Calibrated backtest
python scripts/run_backtest.py \
    --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \
    --strategy trend_following_v8_ecap60_add80 --asset BTC --calibrate

# Walk-forward validation
python scripts/run_walk_forward.py \
    --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \
    --strategy trend_following_v8_ecap60_add80 --asset BTC

# Train calibrator
python scripts/train_calibrator.py \
    --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \
    --strategies trend_following_v8_ecap60_add80 --asset BTC

# Multi-asset portfolio (THE production backtest)
python scripts/run_multiasset_portfolio.py \
    --sleeve BTC,data/btcusd_3600s_2019-01-01_to_2025-12-30.csv,trend_following_v8_ecap60_add80,calibrated \
    --sleeve ETH,data/ethusd_3600s_2019-01-01_to_2025-12-30.csv,trend_following_v8_ecap60_add80,uncalibrated \
    --weights 0.6,0.4 --capital 100000
```
