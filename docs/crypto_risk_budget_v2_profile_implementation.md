# Crypto Risk Budget v2 Profile Implementation

## Profile Identity

**Profile name:** `fund_v2_crypto_hybrid_eth4h_cap75`
**Status:** Research / paper candidate. Not the default. Not live. Not Fund v1.

## Sleeve Strategy Mapping

| Sleeve | Strategy |
|--------|----------|
| BTC_1H | `trend_following_v8_ecap75` |
| BTC_4H | `trend_following_v8_ecap75` |
| ETH_1H | `trend_following_v8_ecap75` |
| ETH_4H | `trend_following_v8_cap75`  |

**Differentiator from Fund v1:** ETH_4H uses the hard-cap variant (`cap75`) instead of the entry-cap variant (`ecap75`).
Fund v1 uses `trend_following_v8_ecap60_add80` for all four sleeves.

## Files Changed

| File | Change type | Description |
|------|-------------|-------------|
| `scripts/run_fund_portfolio.py` | Modified | Added `--profile` argument; per-sleeve strategy support; `PROFILES` registry |
| `scripts/run_fund_v2_live.py` | Created | New isolated Fund v2 paper-trading runner |
| `dashboard_fund_v1.py` | Modified | Added fund selector (Fund v1 / Fund v2 radio); switches data sources; v2 banner |
| `docs/crypto_risk_budget_v2_profile_implementation.md` | Created | This file |

**Files NOT changed:** `run_fund_v1_live.py`, `run_paper_live.py`, all broker/governor/execution/harness files, `dashboard.py`, all strategy modules, all data files.

## Fund v1 Default Behavior — Unchanged Confirmation

- `scripts/run_fund_portfolio.py` without `--profile`: defaults to `fund_v1_current`.
  All four sleeves use `trend_following_v8_ecap60_add80`. Behavior is bit-for-bit identical to before.
- `scripts/run_fund_v1_live.py`: **not modified**. Fund v1 paper runner is untouched.
- `runtime/argus/state/fund_v1_state.json`: **not touched** by Fund v2 runner.
- `runtime/argus/state/fund_v1_fills.jsonl`: **not touched** by Fund v2 runner.
- `dashboard_fund_v1.py`: defaults to Fund v1 on load; Fund v1 view is unchanged.

## Fund v2 Separate State / Fill / Log Files

Fund v2 uses exclusively separate files — never reads or writes Fund v1 files:

| Artifact | Fund v1 | Fund v2 |
|----------|---------|---------|
| State JSON | `runtime/argus/state/fund_v1_state.json` | `runtime/argus/state/fund_v2_state.json` |
| Fills log | `runtime/argus/state/fund_v1_fills.jsonl` | `runtime/argus/state/fund_v2_fills.jsonl` |
| Signals log | _(none)_ | `runtime/argus/state/fund_v2_signals.jsonl` |
| Live log | `logs/fund_v1_live.out` | `logs/fund_v2_live.out` |
| Runner script | `scripts/run_fund_v1_live.py` | `scripts/run_fund_v2_live.py` |

## Exact Commands

### Backtest Runner

**Fund v1 (default — existing behavior):**
```bash
cd /root/ID_test
python scripts/run_fund_portfolio.py \
    --btc-data data/BTC_USD_1H.csv \
    --eth-data data/ETH_USD_1H.csv
```

**Fund v2 profile:**
```bash
cd /root/ID_test
python scripts/run_fund_portfolio.py \
    --profile fund_v2_crypto_hybrid_eth4h_cap75 \
    --btc-data data/BTC_USD_1H.csv \
    --eth-data data/ETH_USD_1H.csv
```

> Note: The on-server CSVs cover only ~39 days (2026-03-21 to 2026-04-29) — use for smoke
> tests only. Do not draw performance conclusions from this short window.

### Paper Trading Runners

**Fund v1 paper runner (existing — do not stop):**
```bash
cd /root/ID_test
python scripts/run_fund_v1_live.py
# With options:
python scripts/run_fund_v1_live.py --capital 100000 --poll 3600
```

**Fund v2 paper runner (new):**
```bash
cd /root/ID_test
python scripts/run_fund_v2_live.py
# With options:
python scripts/run_fund_v2_live.py --capital 100000 --poll 3600
# With max cycles (for testing):
python scripts/run_fund_v2_live.py --max-cycles 1
# Redirect logs to file:
python scripts/run_fund_v2_live.py 2>&1 | tee logs/fund_v2_live.out
```

### Dashboard

```bash
cd /root/ID_test
# Fund v1 dashboard (port 8504):
streamlit run dashboard_fund_v1.py --server.port 8504
# Legacy paper-trader dashboard (port 8501):
streamlit run dashboard.py --server.port 8501
```

### How to Select Fund v1 vs Fund v2 in the Dashboard

1. Open the dashboard at `http://<server>:8504`
2. In the left sidebar, under **Fund**, there is a radio selector:
   - **Fund v1 — current** (default): shows Fund v1 state, fills, and logs
   - **Fund v2 — paper candidate**: shows Fund v2 state, fills, and logs
3. Selecting Fund v2 adds a yellow warning banner confirming it is a paper-only candidate.
4. The selector is read-only: it cannot trigger trades or modify any state files.

## Smoke-Test Commands

Run these from `/root/ID_test` to verify the implementation.

**1. Fund v1 backtest (default profile — verifies nothing broke):**
```bash
python scripts/run_fund_portfolio.py \
    --btc-data data/BTC_USD_1H.csv \
    --eth-data data/ETH_USD_1H.csv
```
Expected: output shows `Profile: fund_v1_current` and `Strategy: trend_following_v8_ecap60_add80`.

**2. Fund v2 backtest (new profile):**
```bash
python scripts/run_fund_portfolio.py \
    --profile fund_v2_crypto_hybrid_eth4h_cap75 \
    --btc-data data/BTC_USD_1H.csv \
    --eth-data data/ETH_USD_1H.csv
```
Expected: output shows `Profile: fund_v2_crypto_hybrid_eth4h_cap75` and `Strategy: mixed — ...ecap75, ...cap75`.

**3. Fund v2 paper runner — one-cycle dry run:**
```bash
# NOTE: --max-cycles 1 causes a live Coinbase API fetch. Safe for smoke testing.
# The runner will fetch 900 bars, generate signals, and stop after one cycle.
# No fills will occur unless a signal fires and clears governor threshold.
python scripts/run_fund_v2_live.py --max-cycles 1 --poll 0
```
Expected: `[fund_v2]` log lines; state written to `runtime/argus/state/fund_v2_state.json`;
signals written to `runtime/argus/state/fund_v2_signals.jsonl`.
Fund v1 state file is NOT modified.

**4. Dashboard import smoke test:**
```bash
python -c "
import sys; sys.path.insert(0, '.')
# Verify dashboard can import without error
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location('dash', 'dashboard_fund_v1.py')
# Just check for syntax errors by compiling:
import py_compile; py_compile.compile('dashboard_fund_v1.py', doraise=True)
print('dashboard_fund_v1.py: syntax OK')
"
```

**5. Unit tests:**
```bash
cd /root/ID_test
python -m pytest tests/unit/ -q 2>&1 | tail -20
```

## Explicit Non-Changes

The following were NOT modified:

- `runtime/argus/brokers/` — broker logic unchanged
- `runtime/argus/governors/` — governor logic unchanged
- `runtime/argus/apex_core/` — orchestrator unchanged
- `research/harness/execution_model.py` — execution logic unchanged
- `research/harness/backtest_engine.py` — backtest engine unchanged
- `research/strategies/trend_following_v8_ecap75.py` — strategy unchanged (pre-existing)
- `research/strategies/trend_following_v8_cap75.py` — strategy unchanged (pre-existing)
- `scripts/run_fund_v1_live.py` — Fund v1 runner untouched
- `scripts/run_paper_live.py` — legacy runner untouched
- `dashboard.py` — legacy dashboard untouched
- Any systemd/deployment service files
- Any fee, slippage, or leverage parameters

## Fund v2 is Paper Only — Confirmation

`run_fund_v2_live.py` uses `PaperBroker` exclusively (same class as Fund v1's paper runner).
There is no live broker, no Coinbase order submission, no real capital at risk.
The runner is equivalent in isolation to `run_fund_v1_live.py` — a paper simulation using
live Coinbase price data for signal generation and paper-fill simulation.
