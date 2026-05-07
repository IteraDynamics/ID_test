# Equity Alpha Rule Replay v1 — Research Plan

## Status

**Branch:** `research/equity-alpha-rule-replay-v1`

**Purpose:** Convert the strongest breadth / dispersion / leadership diagnostic regimes into controlled replay overlays and test whether the information is monetizable.

**Guardrail:** Research-only. This branch does not approve paper trading, live allocation, broker/execution changes, dashboard integration, runtime changes, or a global dynamic allocator.

## Context

The research decision register promoted the breadth / dispersion / leadership framework as the first active equity alpha lead.

Primary diagnostic lead:

```text
weak_breadth__qqq_leading
```

Secondary diagnostic lead:

```text
high sector correlation as possible core risk-on confirmation
```

The diagnostic result was promising but not yet a tradable rule.

This branch tests whether those states improve the actual Equity Core return stream when used as simple overlays.

## Baseline

Baseline strategy:

```text
Equity Core SMA175 + BIL risk-off
```

This is the promoted equity base plus promoted defensive carry.

## Inputs

Required market data:

```text
data/SPY_1D.csv
data/QQQ_1D.csv
data/BIL_1D.csv
```

Required sector data:

```text
XLK
XLV
XLF
XLE
XLY
XLP
XLI
XLU
XLB
XLRE
XLC
```

Optional breadth / equal-weight data:

```text
RSP
QQQE
```

The replay script may recompute the daily signal panel directly rather than requiring a pre-generated `daily_signal_panel.csv`, to keep the artifact reproducible.

## Candidate Rules

### Baseline

```text
BASE_EQUITY_CORE_BIL
```

Original Equity Core SMA175 + BIL risk-off.

### Rule A — Bullish Narrow Leadership Allow

```text
RULE_WEAK_BREADTH_QQQ_LEADING_ALLOW
```

Hypothesis:

```text
When breadth is weak but QQQ is leading, the market may be in a narrow growth acceleration / recovery regime, not necessarily a fragile regime.
```

Implementation idea:

```text
If weak_breadth__qqq_leading is true, force both SPY and QQQ sleeves to remain active.
Otherwise use baseline Equity Core weights.
```

### Rule B — Weak Breadth / QQQ Lagging Reduce

```text
RULE_WEAK_BREADTH_QQQ_LAGGING_REDUCE
```

Hypothesis:

```text
Weak breadth plus QQQ lagging is a caution regime.
```

Implementation idea:

```text
If weak_breadth__qqq_lagging is true, scale equity exposure down by 50% and move the remainder to BIL.
Otherwise use baseline Equity Core weights.
```

### Rule C — High Correlation Allow

```text
RULE_HIGH_CORR_ALLOW
```

Hypothesis:

```text
High sector correlation may identify broad index-level risk-on regimes where Equity Core should remain active.
```

Implementation idea:

```text
If high sector correlation bucket is true, force both SPY and QQQ sleeves active.
Otherwise use baseline Equity Core weights.
```

### Rule D — Combined Overlay

```text
RULE_COMBINED_NARROW_LEADERSHIP_AND_CORR
```

Hypothesis:

```text
Bullish states should allow/boost core exposure.
Caution states should reduce exposure.
```

Implementation idea:

```text
bullish = weak_breadth__qqq_leading OR high_corr
caution = weak_breadth__qqq_lagging OR low_corr

If caution:
  scale baseline equity exposure down by 50%.
Else if bullish:
  force both SPY and QQQ sleeves active.
Else:
  use baseline Equity Core weights.
```

Caution takes precedence over bullish to avoid overexposure in conflicted regimes.

## Evaluation

Compare every rule against:

```text
BASE_EQUITY_CORE_BIL
PASSIVE_SPY_QQQ_50_50
SPY_HODL
QQQ_HODL
```

Metrics:

```text
Total return
CAGR
Max drawdown
Sharpe
Sortino
Calmar
Annualized volatility
Worst 90d return
Worst 180d return
Max time underwater
Average exposure
Time full risk-off
Turnover proxy
```

Named windows:

```text
FULL
GFC_2007_2009
COVID_2020
BEAR_2022
POST_2022_RECOVERY
RECENT_2025_PLUS
```

## Outputs

```text
artifacts/equity_alpha_rule_replay_v1/
  equity_curves.csv
  performance_summary.csv
  window_performance_summary.csv
  exposure_summary.csv
  rule_exposure_history.csv
  rule_event_counts.csv
  skipped_assets.csv
  summary.json
  summary.md
```

## Promotion Criteria

A rule becomes a candidate overlay only if it:

```text
1. Improves Calmar and Sharpe versus BASE_EQUITY_CORE_BIL.
2. Does not materially increase MaxDD.
3. Improves at least one adverse window, especially 2022 or COVID.
4. Does not rely on an extremely small number of events.
5. Remains explainable and deterministic.
```

## Rejection Criteria

Reject or demote a rule if it:

```text
1. Adds CAGR only by increasing drawdown disproportionately.
2. Reduces CAGR materially without a major drawdown improvement.
3. Whipsaws into/out of exposure too often.
4. Depends on short-history optional assets only.
5. Fails to improve the baseline on risk-adjusted metrics.
```

## Non-Goals

```text
No optimizer.
No giant parameter grid.
No ML.
No paper trading.
No live trading.
No broker integration.
No dynamic crypto/equity allocator.
No dashboard integration.
```

## Bottom Line

This branch determines whether the first real equity alpha lead is monetizable as a simple, auditable overlay on top of Equity Core + BIL.
