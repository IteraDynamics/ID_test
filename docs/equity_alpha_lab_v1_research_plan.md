# Equity Alpha Lab v1 — Research Plan

## Status

**Branch:** `research/equity-alpha-lab-v1`

**Purpose:** Start an isolated equity alpha research lab for breadth, concentration, equal-weight confirmation, and sector participation diagnostics.

**Scope:** Research-only lab. This branch does not modify the current fund target book, crypto target stream, promoted Equity Core baseline, live trading, broker integration, paper-broker execution, order generation, fills, runtime deployment, dashboard integration, or dynamic fund allocation.

## Background

The current promoted equity sleeve remains:

```text
SPY / QQQ SMA175 risk-on/risk-off with BIL defensive substitute
```

That baseline is governed equity beta / trend-filtered equity participation. Equity Alpha Lab v1 tests whether breadth and concentration information has incremental diagnostic value against that baseline.

The current fund book remains the baseline fund target architecture and must not be contaminated by this lab.

## Research Question

```text
Can breadth, concentration, equal-weight confirmation, or sector participation diagnostics improve Equity Core quality without materially increasing drawdown, fragility, turnover, or implementation complexity?
```

## Candidate Set

```text
BASE_EQUITY_CORE
BREADTH_CONFIRMATION
NARROW_LEADERSHIP_REDUCE
BROAD_MARKET_CONFIRM_ALLOW
SECTOR_PARTICIPATION_FILTER
```

### BASE_EQUITY_CORE

The benchmark candidate. Uses SPY and QQQ SMA175 trend participation with BIL as defensive/risk-off substitute.

### BREADTH_CONFIRMATION

Uses equal-weight confirmation proxies where available:

```text
RSP/SPY
QQQE/QQQ
```

If breadth confirmation is weak, reduce active equity exposure conservatively and move the difference to BIL.

### NARROW_LEADERSHIP_REDUCE

Detects conditions where QQQ is trend-strong but equal-weight Nasdaq participation is weak. This is treated as a narrow leadership caution flag and reduces QQQ exposure conservatively.

### BROAD_MARKET_CONFIRM_ALLOW

Allows normal Equity Core exposure only when cap-weight trend and equal-weight confirmation agree. This candidate intentionally tests a stricter confirmation requirement and may sacrifice return for robustness.

### SECTOR_PARTICIPATION_FILTER

Uses available sector ETFs to compute the share of sectors above trend. If sector participation is weak, reduce active equity exposure conservatively and move the difference to BIL.

## Inputs

Required:

```text
data/SPY_1D.csv
data/QQQ_1D.csv
data/BIL_1D.csv
```

Optional breadth/equal-weight inputs:

```text
data/RSP_1D.csv
data/QQQE_1D.csv
```

Optional sector inputs:

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

Missing optional files should degrade gracefully and be reported in the readiness summary.

## Outputs

All outputs must be written under:

```text
artifacts/equity_alpha_lab_v1/
```

Required artifacts:

```text
equity_alpha_lab_summary.csv
equity_alpha_candidate_curves.csv
equity_alpha_diagnostics.csv
equity_alpha_readiness_summary.csv
summary.md
summary.json
```

## Required Metrics

Each candidate should be compared against `BASE_EQUITY_CORE` on:

```text
total_return_pct
cagr_pct
max_drawdown_pct
sharpe
sortino
calmar
ann_vol_pct
worst_90d_return_pct
worst_180d_return_pct
max_time_underwater_days
turnover / complexity
fund-level compatibility
```

## Required Diagnostics

The lab should emit daily traceability columns sufficient to explain candidate behavior:

```text
candidate_name
timestamp
spy_signal
qqq_signal
rsp_spy_ratio
qqqe_qqq_ratio
breadth_confirmed
narrow_leadership_flag
sector_participation_pct
sector_count_available
target_spy_weight
target_qqq_weight
target_bil_weight
total_accounted_weight
accounting_ok
```

## Readiness Classification

Expected v1 readiness state:

```text
research_ready = true
broker_ready = false
promotion_eligible = false
readiness_state = equity_alpha_lab_diagnostic_only
```

The lab may identify promising candidates, but no v1 result is automatically promoted.

## Non-Goals

```text
No promotion into Fund Target Book v3.
No replacement of Equity Core.
No crypto target stream changes.
No live trading.
No broker integration.
No paper-broker execution.
No order generation.
No fill simulation.
No runtime deployment.
No dashboard integration.
No dynamic fund allocator.
No aggressive parameter optimization.
No claim that equity alpha is approved.
```

## Success Criteria

Equity Alpha Lab v1 is successful if it:

```text
1. Produces isolated, deterministic artifacts under artifacts/equity_alpha_lab_v1/.
2. Preserves the current promoted fund book and Equity Core baseline.
3. Compares conservative breadth/concentration candidates against BASE_EQUITY_CORE.
4. Reports performance, drawdown, risk, turnover, accounting, and readiness diagnostics.
5. Explicitly marks all candidates as lab-only and not broker-ready.
```

## Future Step

After v1, review the artifacts and decide whether a v2 branch should deepen only the most promising diagnostic. A v2 branch should still require explicit approval before any candidate is considered for fund-level promotion.

## Bottom Line

This branch creates a controlled equity alpha research lab. It is designed to test signal value, not to approve a new equity sleeve.
