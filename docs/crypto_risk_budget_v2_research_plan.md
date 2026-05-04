# Crypto Risk Budget v2 — Research Plan

## Status

**Branch:** `research/crypto-risk-budget-vtwo`

**Research status:** open.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

This branch opens after closing three major research loops:

```text
1. HMM Regime v1 — archived as shadow diagnostic, not governor.
2. Sleeve 4 defensive carry — useful benchmark/reserve sleeve, not flagship allocation.
3. Static multi-asset blending — useful reporting/composite layer, but not the core crypto mandate.
```

The conclusion from those tracks is that Itera's core issue is no longer drawdown control. The current crypto engine appears highly defensive versus passive BTC/ETH, but may be giving up too much upside participation.

## Core Question

```text
Can Itera intentionally spend some drawdown budget to buy back upside capture?
```

The goal is not to recklessly chase HODL returns. The goal is to explore whether Fund v1 is too conservative for a crypto-focused mandate.

## Current Baseline

Fund v1 / Crypto Sleeve v1 currently behaves like a conservative systematic crypto allocation engine.

Representative baseline range:

```text
Total Return: ~+215% to +223%
CAGR:         ~18% to 19%
MaxDD:        ~-17% to -18%
Sharpe:       ~1.2 to 1.4
Calmar:       ~1.0 to 1.1
```

Passive BTC/ETH over the same broad research period had vastly higher drawdowns but also vastly higher returns:

```text
BTC HODL: ~+2,200% total return, ~-76% max drawdown
ETH HODL: ~+2,010% total return, ~-79% max drawdown
```

This implies that Fund v1 has solved defense aggressively, but may have underspent its risk budget.

## Strategic Reframe

This branch separates the crypto program from the multi-asset allocator problem.

The crypto program should be evaluated as crypto:

```text
Primary benchmark: BTC, ETH, 50/50 BTC/ETH
Mandate: systematic crypto participation with controlled but not overly suppressed drawdown
Target: better upside capture while retaining major drawdown advantage over passive crypto
```

SPY, QQQ, T-bills, and blended composites are separate reporting/portfolio-construction tracks. They should not dictate the crypto engine's internal risk budget.

## Working Hypothesis

Fund v1 may be too safe for the desired flagship crypto mandate.

A more compelling crypto-risk profile may be closer to:

```text
Moderate-aggression target:
CAGR:   25% to 30%
MaxDD: -22% to -28%
Sharpe: >= 1.1
Calmar: near or above 1.0

Aggressive target:
CAGR:   30% to 35%
MaxDD: -25% to -35%
Sharpe: >= 1.0
Calmar: near or above 0.9
```

This would still be far safer than HODL, while offering a more fund-like crypto return profile.

## Research Objective

Map the efficient frontier between current Fund v1 and passive BTC/ETH.

Do not optimize for one headline metric. The output should show whether controlled aggression improves the mandate tradeoff.

## Candidate Levers

### 1. Exposure Cap Sweep

Test whether current exposure caps are too restrictive.

Potential variants:

```text
Current baseline
Higher exposure cap
Reduced bear cap strictness
Trend-confirmed higher exposure
Regime-specific exposure expansion
```

No leverage in the first pass unless explicitly approved.

### 2. Calibration Threshold Sweep

Test whether calibration is suppressing too many valid trend signals.

Potential variants:

```text
Current calibrated baseline
Less conservative confidence threshold
Higher participation threshold during trend regimes
Separate BTC/ETH thresholds
Separate 1H/4H thresholds
```

### 3. Sleeve Weight Sweep

Test whether equal-weight BTC/ETH x 1H/4H is leaving return on the table.

Initial variants:

```text
Equal weight baseline
BTC-heavy
ETH-heavy
4H-heavy
1H-heavy
BTC 4H / ETH 4H dominant
Best-risk-adjusted sleeve tilt
Best-upside-capture sleeve tilt
```

### 4. Re-entry / Recovery Participation Audit

Identify whether the strategy misses too much upside after defensive exits.

Required diagnostics:

```text
missed upside after exits
bars to re-enter after market recovery
return lost during first 30/60/90 days after major bottoms
exposure during recovery regimes
```

### 5. Bull / Bear Capture Audit

Measure whether Fund v1 is too defensive in bull regimes.

Required diagnostics:

```text
upside capture vs BTC
upside capture vs ETH
upside capture vs 50/50 BTC/ETH
downside capture vs BTC
downside capture vs ETH
yearly capture ratios
worst-year protection
best-year participation
```

## Benchmarks

Every candidate must be compared against:

```text
Fund v1 baseline
BTC HODL
ETH HODL
50/50 BTC/ETH HODL, periodically rebalanced if implemented
```

Optional benchmarks:

```text
60/40 BTC/ETH HODL
BTC-only systematic sleeve if generated
ETH-only systematic sleeve if generated
```

## Required Metrics

Every candidate must report:

```text
Total Return
CAGR
MaxDD
Sharpe
Calmar
Annualized Volatility
Worst year
Best year
Worst rolling 90-day return
Worst rolling 180-day return
Time underwater
Average exposure
Exposure by year
Upside capture
Downside capture
Return capture versus passive
Drawdown reduction versus passive
```

## Promotion Criteria

A more aggressive candidate may remain active if it improves the crypto mandate tradeoff.

Preferred evidence:

```text
CAGR improves materially versus Fund v1 baseline
MaxDD remains far below passive BTC/ETH drawdowns
Sharpe remains near or above Fund v1 baseline
Calmar remains near or above 1.0, or tradeoff is explicitly justified
Upside capture improves in bull years
Downside capture remains controlled in 2022-style stress
No single year explains the entire improvement
```

## Rejection Criteria

Reject a candidate if:

```text
CAGR improves only by accepting HODL-like drawdown
Sharpe collapses materially
Calmar falls below acceptable crypto-risk budget
Improvement comes from one lucky window
Candidate depends on lookahead, fragile calibration, or unrealistic execution
Candidate turns the strategy into disguised buy-and-hold without enough risk benefit
```

## First Recommended Experiment

Do not change runtime logic first.

First build an upside/downside capture audit around the existing Fund v1 artifact.

Script target:

```text
scripts/analyze_crypto_upside_capture.py
```

Inputs:

```text
Fund v1 equity curve
BTC 1H OHLCV
ETH 1H OHLCV
```

Outputs:

```text
artifacts/crypto_risk_budget_v2_capture_audit/
  capture_summary.csv
  yearly_capture_summary.csv
  rolling_window_summary.csv
  exposure_diagnostics.csv
  summary.json
  summary.md
```

This audit should answer where upside is being lost before any new aggressive strategy variant is tested.

## Guardrails

No paper-trading changes are approved from this branch until research explicitly passes.

Not approved:

```text
Fund v1 paper-trading changes
Production/runtimes changes
Higher live exposure
Leverage
Exchange/order-routing changes
```

Approved:

```text
Research scripts
Artifact generation
Benchmark comparisons
Static what-if analysis
Parameter sweeps in research harness only
```

## Bottom Line

The next frontier is not more diversification or more defense.

The next frontier is controlled offense:

```text
Spend some of the drawdown budget Fund v1 has preserved,
and see whether Itera can buy back enough upside capture to become a more compelling crypto-focused strategy.
```
