# Fund Paper Readiness v1 — Findings

## Status

**Branch:** `research/fund-paper-readiness-v1`

**Research status:** Phase 1 static sleeve ledger and diversification diagnostics completed.

**Decision:** promote Phase 1 fund paper-readiness as a successful accounting/ledger checkpoint.

**Runtime status:** no live trading, broker integration, paper-broker execution, dashboard integration, or dynamic allocator changes approved.

## Executive Summary

Fund Paper Readiness v1 successfully moves Itera from a static research composite toward a paper-accounted fund book.

This branch does not trade. It does not connect to brokers. It does not implement a dynamic allocator.

It does prove that the promoted two-sleeve architecture can be represented as a deterministic fund ledger with:

```text
fund NAV
sleeve NAVs
target weights
actual weights
drift
rebalance events
drawdowns
performance summaries
sleeve diversification diagnostics
```

The results support the current fund concept:

```text
Governed crypto sleeve
+ governed equity sleeve
+ static 50/50 fund book
```

## Phase 1 Ledger Result

Input:

```text
artifacts/fund_side_by_side_composite_v1_tilted_4s/equity_curves.csv
CRYPTO_SLEEVE
EQUITY_SLEEVE
```

Configuration:

```text
Target weights: 50% crypto / 50% equity
Initial capital: $100,000
Rebalance threshold: 5 percentage points absolute drift
```

Headline ledger result:

```text
FUND_PAPER_LEDGER
Window: 2019-03-08 → 2025-12-30
Final NAV: $311,629.82
Total return: 211.63%
CAGR: 18.15%
MaxDD: -14.25%
Sharpe: 1.589
Sortino: 2.463
Calmar: 1.273
Annualized volatility: 10.90%
Worst 90d: -10.13%
Worst 180d: -11.25%
Rebalance events: 5
```

This is close to the prior tear-sheet static composite:

```text
FUND_STATIC_CRYPTO50_EQUITY50
CAGR: 18.32%
MaxDD: -14.15%
Sharpe: 1.62
Calmar: 1.29
```

The difference is expected because the ledger uses drift-band rebalancing rather than continuous/daily static composite accounting.

## Final Ledger State

```text
Final fund NAV:       $311,629.82
Final crypto NAV:     $145,845.20
Final equity NAV:     $165,784.63
Final crypto weight:  46.80%
Final equity weight:  53.20%
Final drawdown:       -2.65%
```

Final drift was within the 5 percentage point threshold:

```text
Crypto drift: -3.20 percentage points
Equity drift: +3.20 percentage points
```

Therefore no final rebalance was triggered. This is correct behavior for a drift-band fund ledger.

## Stress Window Review

### 2022 Bear Market

```text
BEAR_2022
Return: -11.73%
MaxDD: -11.80%
Sharpe: -2.185
Calmar: -1.005
```

This is one of the most important validation points. The fund did not avoid losses in 2022, but it reduced damage materially versus passive crypto and passive growth equity exposure.

Approximate 2022 context:

```text
BTC HODL: roughly -64%
ETH HODL: roughly -68%
SPY HODL: roughly -18% to -19%
QQQ HODL: roughly -33%
SPY/QQQ 50/50: roughly -25% to -26%
Itera paper fund ledger: -11.73%
```

### Post-2022 Recovery

```text
POST_2022_RECOVERY
Return: 50.47%
CAGR: 22.75%
MaxDD: -7.43%
Sharpe: 2.032
Calmar: 3.062
```

This supports the fund-book profile: controlled bear-market damage followed by strong recovery participation.

### 2025+

```text
RECENT_2025_PLUS
Return: 5.96%
CAGR: 6.02%
MaxDD: -9.08%
Sharpe: 0.709
Calmar: 0.663
```

Recent results are positive but less exceptional. This should remain visible in future reporting.

## Diversification Diagnostics

The diversification diagnostics directly tested whether the promoted crypto and equity sleeves are genuinely complementary.

Full-period result:

```text
Crypto/equity return correlation: 0.0186
```

This is extremely low and strongly supports the side-by-side fund construction.

Window correlations:

```text
FULL:               0.0186
COVID_2020:         0.0743
BEAR_2022:          0.0561
POST_2022_RECOVERY: 0.0260
RECENT_2025_PLUS:   0.0417
```

The key finding is that correlations remained low even in the important stress windows.

## Rolling Correlation Diagnostics

Rolling correlation summary:

```text
63d rolling correlation:
  mean: 0.0313
  median: 0.0266
  min: -0.3593
  max: 0.3645
  below 0: 41.91%
  below 0.25: 98.49%
  above 0.75: 0.00%

126d rolling correlation:
  mean: 0.0334
  median: 0.0271
  min: -0.1624
  max: 0.2317
  below 0: 42.32%
  below 0.25: 100.00%
  above 0.75: 0.00%

252d rolling correlation:
  mean: 0.0296
  median: 0.0294
  min: -0.0833
  max: 0.1904
  below 0: 39.26%
  below 0.25: 100.00%
  above 0.75: 0.00%
```

This is a major fund-quality finding.

The promoted sleeves were not persistently correlated. They also did not become highly correlated during the tested rolling windows.

## Reference Performance From Correlation Diagnostic

```text
CRYPTO_SLEEVE
CAGR: 18.28%
MaxDD: -18.89%
Sharpe: 1.131
Calmar: 0.968

EQUITY_SLEEVE
CAGR: 16.93%
MaxDD: -19.53%
Sharpe: 1.174
Calmar: 0.867

FUND_STATIC_CRYPTO50_EQUITY50
CAGR: 18.26%
MaxDD: -14.15%
Sharpe: 1.610
Calmar: 1.290
```

The fund composite improves drawdown-adjusted quality versus both standalone sleeves.

## Interpretation

This branch validates the main portfolio theory behind the current Itera fund concept:

```text
The crypto sleeve and equity sleeve are not just separately profitable. They are meaningfully diversifying return streams.
```

The full-period correlation of 0.0186, combined with rolling correlations that never exceeded 0.75, supports the idea that the fund-level profile is not merely the result of adding two correlated risk assets together.

The fund book works because the sleeves are complementary.

## What This Does Not Prove

This does not prove:

```text
live execution readiness
broker integration readiness
capacity
slippage / fee realism
legal fund readiness
investor onboarding readiness
dynamic allocation superiority
future correlation stability
```

Correlation can change. The diagnostic is descriptive, not predictive.

## Research Decision

Promote Phase 1 paper-readiness as successful:

```text
Fund Paper Readiness v1 successfully builds a deterministic static-sleeve fund ledger and validates that the promoted sleeves are meaningfully diversifying over the tested window.
```

Do not promote live trading or broker paper execution yet.

## Recommended Next Step

Next branch should be:

```text
research/fund-paper-readiness-v2
```

Purpose:

```text
Move from precomputed sleeve curves to signal-driven sleeve targets.
```

Phase 2 should answer:

```text
Can the equity sleeve generate daily target exposure directly from SPY/QQQ/BIL data?
Can the crypto sleeve provide a daily target exposure stream from its promoted strategy artifacts or signal outputs?
Can the fund ledger consume target exposures rather than static sleeve equity curves?
Can the ledger produce paper orders/fills only after the accounting model is stable?
```

## Guardrails

```text
No live trading.
No broker integration.
No paper-broker execution yet.
No dynamic allocator.
No dashboard integration.
No legal fund claim.
```

## Bottom Line

Fund Paper Readiness v1 is a strong checkpoint.

Itera now has:

```text
research-validated sleeves
fund-level tear sheet
static fund accounting ledger
drift-band rebalance tracking
stress-window review
sleeve diversification proof
```

That is materially closer to paper-trading like a fund, but the next step is to make sleeve targets signal-driven rather than curve-driven.
