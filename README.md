# IteraDynamics

> Research-backed systematic trading infrastructure for building, validating, and packaging multi-sleeve fund strategies.

IteraDynamics is a Python research/runtime monorepo for deterministic quantitative trading research. The current promoted research architecture centers on two independent systematic sleeves:

```text
1. Governed crypto sleeve
2. Governed equity sleeve: SPY/QQQ SMA175 + BIL risk-off
```

The current promoted fund-level view is a static side-by-side composite of those independent sleeves, currently centered on:

```text
50% crypto sleeve / 50% equity sleeve
```

This repository contains the research harnesses, strategy contracts, runtime/governance components, validation scripts, and reporting tools used to evaluate that architecture.

---

## Current Research State

### Promoted

```text
Crypto sleeve
  - Independent systematic crypto engine candidate.
  - Used as the digital-asset sleeve in fund-level composite reporting.

Equity Core
  - SPY/QQQ SMA175 trend-risk participation engine.
  - BIL used as the practical defensive/risk-off proxy.

Fund side-by-side composite
  - Static crypto/equity reporting view.
  - Preferred current view: 50/50 crypto/equity.
  - Secondary view: 60/40 crypto/equity.
```

### Not promoted

```text
Dynamic crypto/equity allocator
  - Not part of the current promoted architecture.

Vanilla sector rotation
  - Initial sector-rotation research did not beat Equity Core + BIL.

Equity alpha overlays
  - Breadth / leadership / correlation diagnostics remain interesting.
  - Hard and soft overlay replays did not beat Equity Core + BIL on the required drawdown-adjusted basis.
```

### Current fund setup, plainly

```text
Itera is currently modeled as a disciplined two-sleeve systematic architecture:

  governed crypto sleeve
  + governed equity sleeve
  + static 50/50 fund reporting composite
```

This is not a legal fund vehicle, live investor product, or live allocation system. It is the current research-backed architecture and reporting view.

---

## Current Fund View

The preferred fund-level reporting series is:

```text
FUND_STATIC_CRYPTO50_EQUITY50
```

Latest tear-sheet run from the tilted 4-sleeve crypto input plus Equity Core + BIL:

```text
Window: 2019-03-08 → 2025-12-30
CAGR:   18.32%
MaxDD: -14.15%
Sharpe: 1.62
Sortino: 2.51
Calmar: 1.29
AnnVol: 10.80%
```

Benchmark interpretation:

```text
Versus passive SPY/QQQ 50/50:
  - Slightly lower raw CAGR
  - Less than half the max drawdown
  - Higher Sharpe
  - Higher Calmar

Versus passive BTC/ETH:
  - Much lower raw CAGR during the 2019–2025 crypto bull-cycle window
  - Dramatically lower drawdown
  - Better drawdown-adjusted quality
```

Preferred language:

```text
The composite nearly matched passive SPY/QQQ 50/50 raw CAGR while cutting max drawdown by more than half and materially improving Sharpe and Calmar.
```

Avoid vague claims such as:

```text
Itera beat the market.
```

Always specify the benchmark and metric.

---

## Architecture

The codebase still follows a strict research-to-runtime separation.

```text
┌────────────────────────────────────────────────────────────────────┐
│ Research Layer                                                     │
│ Pure strategy/regime logic, deterministic backtests, diagnostics    │
│                                                                    │
│ research/regimes/                                                  │
│ research/strategies/                                               │
│ research/harness/                                                  │
├────────────────────────────────────────────────────────────────────┤
│ Runtime / Governance Layer                                         │
│ Execution orchestration, brokers, governors, runtime state          │
│                                                                    │
│ runtime/argus/                                                     │
├────────────────────────────────────────────────────────────────────┤
│ Reporting / Research Artifacts                                     │
│ Fund composite analysis, tear sheets, findings docs, decision logs  │
│                                                                    │
│ scripts/run_fund_side_by_side_composite_v1.py                      │
│ scripts/run_fund_tearsheet_v1.py                                   │
│ docs/research_decision_register_v1.md                              │
└────────────────────────────────────────────────────────────────────┘
```

### Research principles

```text
Closed-bar only
No lookahead
Deterministic calculations
Research code has no broker side effects
Runtime/execution code is isolated under runtime/argus
Every promoted result must have artifact-backed evidence
Negative results are documented, not buried
```

---

## Important Research Documents

```text
docs/research_decision_register_v1.md
  Canonical register of promoted, rejected, and active research decisions.

docs/fund_side_by_side_composite_v1_findings.md
  Findings for the static crypto/equity fund composite.

docs/equity_alpha_rule_replay_v1_findings.md
  Documents why tested equity alpha overlays were not promoted.

docs/fund_tearsheet_v1_research_plan.md
  Plan for packaging the current promoted architecture into a tear sheet.
```

---

## Key Reporting Scripts

### Fund side-by-side composite

Builds static fund-level composites from an explicit crypto curve plus Equity Core + BIL.

```powershell
python scripts\run_fund_side_by_side_composite_v1.py `
  --crypto-curve "artifacts\fund_tilted_cal_4s_2019-03-08_2025-12-31\equity_curves.csv" `
  --crypto-column "portfolio" `
  --spy-data "data\SPY_1D.csv" `
  --qqq-data "data\QQQ_1D.csv" `
  --bil-data "data\BIL_1D.csv" `
  --weights "50/50,60/40,70/30,40/60,30/70" `
  --out-dir "artifacts\fund_side_by_side_composite_v1_tilted_4s"
```

Outputs:

```text
artifacts/fund_side_by_side_composite_v1_tilted_4s/
  equity_curves.csv
  performance_summary.csv
  capture_summary.csv
  window_performance_summary.csv
  input_summary.json
  summary.json
  summary.md
```

### Fund tear sheet

Packages existing composite artifacts into a concise investor-style markdown report.

```powershell
python scripts\run_fund_tearsheet_v1.py `
  --primary-dir "artifacts\fund_side_by_side_composite_v1_tilted_4s" `
  --secondary-dir "artifacts\fund_side_by_side_composite_v1" `
  --out-dir "artifacts\fund_tearsheet_v1"
```

Outputs:

```text
artifacts/fund_tearsheet_v1/
  fund_tearsheet.md
  fund_tearsheet_summary.json
  selected_performance_table.csv
  benchmark_comparison_table.csv
  window_summary_table.csv
```

### Equity alpha rule replay

Research-only replay of hard and soft overlays based on breadth / leadership / correlation diagnostics. No tested overlay is currently promoted.

```powershell
python scripts\run_equity_alpha_rule_replay_v1.py `
  --spy-data "data\SPY_1D.csv" `
  --qqq-data "data\QQQ_1D.csv" `
  --bil-data "data\BIL_1D.csv" `
  --data-dir "data" `
  --sectors "XLK,XLV,XLF,XLE,XLY,XLP,XLI,XLU,XLB,XLRE,XLC" `
  --optional-assets "RSP,QQQE" `
  --out-dir "artifacts\equity_alpha_rule_replay_v1"
```

Soft-overlay pass:

```powershell
python scripts\run_equity_alpha_rule_replay_v1_soft.py `
  --spy-data "data\SPY_1D.csv" `
  --qqq-data "data\QQQ_1D.csv" `
  --bil-data "data\BIL_1D.csv" `
  --data-dir "data" `
  --sectors "XLK,XLV,XLF,XLE,XLY,XLP,XLI,XLU,XLB,XLRE,XLC" `
  --optional-assets "RSP,QQQE" `
  --tilt-size 0.10 `
  --larger-tilt-size 0.15 `
  --reduce-scale 0.75 `
  --out-dir "artifacts\equity_alpha_rule_replay_v1_soft"
```

---

## Legacy / Runtime Scripts

The repository also contains the original Argus research-to-runtime stack:

```text
scripts/run_backtest.py
scripts/run_portfolio.py
scripts/run_paper.py
runtime/argus/
```

These remain useful for strategy/runtime validation, paper-broker testing, and CI coverage, but the current promoted fund architecture should be understood through the newer research artifacts and decision register.

---

## Installation

Requirements:

```text
Python 3.11+
```

Setup:

```powershell
git clone https://github.com/IteraDynamics/ID_test.git
cd ID_test

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

If using bash/macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Data Expectations

Most research scripts expect CSV files under `data/`.

Common equity files:

```text
data/SPY_1D.csv
data/QQQ_1D.csv
data/BIL_1D.csv
```

Sector ETF files used in breadth/dispersion research:

```text
data/XLK_1D.csv
data/XLV_1D.csv
data/XLF_1D.csv
data/XLE_1D.csv
data/XLY_1D.csv
data/XLP_1D.csv
data/XLI_1D.csv
data/XLU_1D.csv
data/XLB_1D.csv
data/XLRE_1D.csv
data/XLC_1D.csv
```

Optional breadth/equal-weight files:

```text
data/RSP_1D.csv
data/QQQE_1D.csv
```

Expected price columns are generally:

```text
timestamp/date, open, high, low, close, volume
```

The loaders are tolerant of common timestamp column names such as `timestamp`, `date`, `datetime`, `time`, and `Unnamed: 0`.

---

## Tests

Primary validation command:

```powershell
python -m pytest tests/ --maxfail=1 --disable-warnings -q
```

Recent full-suite baseline:

```text
321 passed, 73 warnings
```

Compile-check selected scripts:

```powershell
python -m py_compile `
  scripts\run_fund_side_by_side_composite_v1.py `
  scripts\run_fund_tearsheet_v1.py `
  scripts\run_equity_alpha_rule_replay_v1.py `
  scripts\run_equity_alpha_rule_replay_v1_soft.py
```

---

## Repo Structure

```text
IteraDynamics/
├── data/                         # Local market data; generally gitignored
├── artifacts/                    # Research outputs; generally gitignored
├── docs/                         # Research plans, findings, decision registers
├── research/                     # Pure research layer
│   ├── regimes/                  # Regime labels and engines
│   ├── strategies/               # Strategy modules and contracts
│   ├── harness/                  # Backtest/data/metrics utilities
│   └── diagnostics/              # Diagnostics and chart helpers
├── runtime/                      # Argus runtime/governance layer
│   └── argus/
├── scripts/                      # Research, reporting, and runtime CLIs
├── tests/                        # Unit and integration tests
├── pyproject.toml
└── README.md
```

---

## Current Non-Approvals

The current research state does not approve:

```text
paper trading client/investor capital
live allocation
broker integration
runtime deployment for the fund composite
dynamic crypto/equity allocation
equity alpha overlays
sector rotation sleeve
legal fund offering
```

---

## Bottom Line

IteraDynamics is currently best understood as a systematic fund research platform with a promoted two-sleeve architecture:

```text
governed crypto + governed equities + static 50/50 fund reporting composite
```

The current strongest result is not raw-return dominance. It is a materially cleaner drawdown-adjusted return stream than passive equity benchmarks and passive crypto beta, supported by reproducible artifacts and a documented decision trail.
