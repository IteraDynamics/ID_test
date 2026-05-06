# Equity Book v1 — Baseline Findings and Research Finalist

## Status

**Branch:** `research/equity-book-v1`

**Research status:** baseline research complete; robustness audit complete.

**Runtime status:** no paper-trading, broker, execution, governor, live allocation, crypto runtime, or global allocator changes approved.

## Executive Summary

Equity Book v1 is being evaluated as a separate SPY/QQQ daily equity book, not as a sleeve inside the crypto fund and not as a forced diversifier for the crypto book.

The research sequence was:

```text
1. Establish passive SPY/QQQ benchmarks.
2. Recover and audit old SPY/QQQ/equity artifacts.
3. Run a fresh transparent SPY/QQQ baseline sweep.
4. Audit shortlisted candidates across major market regimes.
5. Select a research finalist without approving paper/live trading.
```

The result is that the recovered old equity artifacts were useful as historical context but were not strong enough to become Equity Book v1. The fresh baseline sweep found a stronger candidate:

```text
Equity Book v1 research finalist:
SPY_QQQ_50_50_SMA150_CASH
```

This candidate is a simple, transparent, cash-risk-off SPY/QQQ trend book:

```text
50% SPY sleeve and 50% QQQ sleeve.
Each sleeve is active only when its asset closes above its own 150-day simple moving average.
Inactive sleeve exposure goes to cash.
Signals are closed-bar daily signals.
```

The candidate is not approved for paper trading or live allocation. It is promoted only as the current Equity Book v1 research finalist for further validation.

## Passive Benchmark Hurdle

The passive benchmark audit covered the common SPY/QQQ daily overlap from 2005-01-03 through 2026-04-29.

The hurdle was not raw equity CAGR alone. Passive QQQ and passive SPY/QQQ 50/50 already produced strong long-run returns, but with deep equity drawdowns.

```text
QQQ_HODL:
  Total Return:  +1865.86%
  CAGR:            15.00%
  MaxDD:          -53.40%
  Sharpe:           0.756
  Sortino:          1.077
  Calmar:           0.281

SPY_QQQ_50_50_DAILY_REBAL:
  Total Return:  +1236.49%
  CAGR:            12.93%
  MaxDD:          -53.66%
  Sharpe:           0.712
  Sortino:          1.012
  Calmar:           0.241

SPY_HODL:
  Total Return:   +774.35%
  CAGR:            10.71%
  MaxDD:          -55.19%
  Sharpe:           0.632
  Sortino:          0.892
  Calmar:           0.194
```

The correct Equity Book v1 question therefore became:

```text
Can a simple SPY/QQQ equity book retain respectable equity CAGR while materially reducing drawdown versus passive SPY/QQQ exposure?
```

A desirable candidate profile was framed as:

```text
CAGR:   9%–13%+
MaxDD: -20% to -35%
Sharpe: >0.8
Sortino: >1.1
Calmar: >0.4–0.6
```

## Artifact Recovery Result

The initial artifact search surfaced many files named `equity_curves.csv`, but most were crypto-era fund outputs, crypto/equity blended portfolio experiments, or defensive/allocator overlays from prior fund research.

Those were excluded from Equity Book v1 because they were not clean standalone SPY/QQQ daily strategy curves.

The valid recovered standalone equity candidates were:

```text
artifacts/spy_trend_backtest/equity_curve.csv
artifacts/spy_trend_v2/equity_curve.csv
artifacts/qqq_trend_v1/equity_curve.csv
```

Recovered candidate audit results:

```text
spy_trend_backtest:
  CAGR:    5.73%
  MaxDD: -17.31%
  Sharpe:  0.685
  Calmar:  0.331

spy_trend_v2:
  CAGR:    5.97%
  MaxDD: -22.35%
  Sharpe:  0.684
  Calmar:  0.267

qqq_trend_v1:
  CAGR:    6.76%
  MaxDD: -26.62%
  Sharpe:  0.586
  Calmar:  0.254
```

Decision:

```text
Recovered old equity work is useful as baseline evidence, but not viable as Equity Book v1.
```

The recovered strategies reduced drawdown, but gave up too much equity risk premium. They did not meet the Equity Book v1 target profile.

## Fresh Baseline Sweep

A fresh research-only script was added:

```text
scripts/run_equity_book_v1_baselines.py
```

It tests transparent daily SPY/QQQ baselines only:

```text
SPY_HODL
QQQ_HODL
SPY_QQQ_50_50_DAILY_REBAL
SPY SMA trend-to-cash
QQQ SMA trend-to-cash
SPY/QQQ 50/50 SMA trend-to-cash
SPY/QQQ 50/50 SMA half-risk-off
SPY/QQQ dual momentum with cash risk-off
SPY/QQQ relative strength rotation, always invested
```

Risk-off is cash only. No SGOV, BIL, SHV, T-bill, volatility sleeve, crypto allocator, or global allocator logic is included.

The wide baseline sweep produced several viable candidates. The most important rows were:

```text
SPY_QQQ_50_50_SMA150_CASH:
  Total Return:  +708.26%
  CAGR:            10.30%
  MaxDD:          -20.69%
  Sharpe:           0.855
  Sortino:          1.179
  Calmar:           0.498
  AnnVol:          12.38%

QQQ_SMA150_CASH:
  Total Return: +1221.58%
  CAGR:            12.87%
  MaxDD:          -26.30%
  Sharpe:           0.894
  Sortino:          1.246
  Calmar:           0.490
  AnnVol:          14.80%

SPY_QQQ_50_50_SMA200_CASH:
  Total Return:  +675.40%
  CAGR:            10.09%
  MaxDD:          -21.86%
  Sharpe:           0.827
  Sortino:          1.139
  Calmar:           0.461
  AnnVol:          12.60%
```

Initial baseline decision:

```text
Primary book candidate:
  SPY_QQQ_50_50_SMA150_CASH

Aggressive/growth candidate:
  QQQ_SMA150_CASH

Confirmation candidate:
  SPY_QQQ_50_50_SMA200_CASH
```

## Why SPY_QQQ_50_50_SMA150_CASH Became the Primary Candidate

Against passive SPY/QQQ 50/50, the candidate gave up some CAGR but substantially improved drawdown-adjusted quality.

```text
SPY_QQQ_50_50_DAILY_REBAL:
  CAGR:   12.93%
  MaxDD: -53.66%
  Sharpe:  0.712
  Sortino: 1.012
  Calmar:  0.241

SPY_QQQ_50_50_SMA150_CASH:
  CAGR:   10.30%
  MaxDD: -20.69%
  Sharpe:  0.855
  Sortino: 1.179
  Calmar:  0.498
```

Trade-off versus passive 50/50:

```text
CAGR give-up:      -2.63 percentage points
MaxDD improvement: +32.98 percentage points
Sharpe improvement: +0.143
Calmar improvement: +0.257
```

This is a good match for the Equity Book mandate: retain respectable equity CAGR while materially reducing passive equity drawdown.

The exposure profile was also reasonable:

```text
Average SPY weight:       38.05%
Average QQQ weight:       38.75%
Average gross exposure:   76.80%
Time in market:           80.80%
Cash time:                19.20%
```

The rule is simple enough to audit, explain, and govern.

## Robustness Audit

A research-only robustness script was added:

```text
scripts/audit_equity_book_v1_robustness.py
```

It reads existing baseline equity curves and audits selected candidates across named windows. It does not rerun strategy logic or tune parameters.

Default windows:

```text
FULL
GFC_2007_2009
COVID_2020
BEAR_2022
POST_2022_RECOVERY
RECENT_2025_PLUS
```

Default audited shortlist:

```text
SPY_QQQ_50_50_SMA150_CASH
SPY_QQQ_50_50_SMA200_CASH
QQQ_SMA150_CASH
SPY_QQQ_50_50_DAILY_REBAL
QQQ_HODL
SPY_HODL
```

## Robustness Findings

### Full Period

```text
SPY_QQQ_50_50_SMA150_CASH:
  CAGR:   10.30%
  MaxDD: -20.69%
  Sharpe:  0.855
  Sortino: 1.179
  Calmar:  0.498
```

Full-period result passes the Equity Book v1 mandate.

### GFC 2007–2009

```text
SPY_QQQ_50_50_SMA150_CASH:
  Return: -16.26%
  MaxDD:  -18.70%

SPY_QQQ_50_50_DAILY_REBAL:
  Return: -43.77%
  MaxDD:  -53.66%

QQQ_HODL:
  Return: -41.32%
  MaxDD:  -53.40%

SPY_HODL:
  Return: -46.56%
  MaxDD:  -55.19%
```

Result: strong pass. SMA150 materially reduced catastrophic long bear-market drawdown.

### 2022 Bear Market

```text
SPY_QQQ_50_50_SMA150_CASH:
  Return: -13.98%
  MaxDD:  -13.98%

SPY_QQQ_50_50_DAILY_REBAL:
  Return: -26.19%
  MaxDD:  -29.63%

QQQ_HODL:
  Return: -33.22%
  MaxDD:  -34.83%
```

Result: strong pass on capital preservation.

### Post-2022 Recovery

```text
SPY_QQQ_50_50_SMA150_CASH:
  CAGR:  25.96%
  MaxDD: -10.67%

SPY_QQQ_50_50_DAILY_REBAL:
  CAGR:  32.90%
  MaxDD: -10.67%

QQQ_HODL:
  CAGR:  40.09%
  MaxDD: -13.56%
```

Result: acceptable lag. The candidate underperformed passive exposure during a strong recovery, but still delivered high absolute return.

### Recent 2025+ Window

```text
SPY_QQQ_50_50_SMA150_CASH:
  CAGR:   12.59%
  MaxDD:  -9.16%
  Sharpe:  1.045
  Calmar:  1.374

SPY_QQQ_50_50_DAILY_REBAL:
  CAGR:   19.87%
  MaxDD: -20.78%
```

Result: pass. The candidate lagged raw passive returns but had much cleaner drawdown behavior.

### COVID 2020

```text
SPY_QQQ_50_50_SMA150_CASH:
  Return: -5.15%
  CAGR:  -12.22%
  MaxDD: -19.56%

SPY_QQQ_50_50_DAILY_REBAL:
  Return: +3.74%
  CAGR:   +9.50%
  MaxDD: -30.86%

QQQ_HODL:
  Return: +11.77%
  CAGR:  +31.61%
  MaxDD: -28.56%
```

Result: known weakness. SMA150 handled the crash drawdown better, but lagged the fast V-shaped rebound.

This does not invalidate the finalist, but it must be explicitly documented:

```text
SMA150 improves long bear-market survivability, but can underperform fast V-shaped recoveries because re-entry is delayed.
```

## QQQ_SMA150_CASH

QQQ_SMA150_CASH remains the strongest aggressive/growth candidate:

```text
Full period:
  CAGR:   12.87%
  MaxDD: -26.30%
  Sharpe:  0.894
  Sortino: 1.246
  Calmar:  0.490
```

It offers higher return than the 50/50 SMA150 book, but is more concentrated and more dependent on QQQ leadership.

Decision:

```text
Carry QQQ_SMA150_CASH forward as an aggressive equity candidate, not the default Equity Book v1 finalist.
```

## SPY_QQQ_50_50_SMA200_CASH

SMA200 is a useful confirmation candidate:

```text
Full period:
  CAGR:   10.09%
  MaxDD: -21.86%
  Sharpe:  0.827
  Sortino: 1.139
  Calmar:  0.461
```

It confirms that the 50/50 trend-to-cash effect is not isolated to exactly 150 days, but SMA150 remains slightly stronger on the tested period.

Decision:

```text
Carry SMA200 as a fallback/confirmation candidate, not the primary finalist.
```

## Research Finalist Decision

Promote the following candidate to Equity Book v1 research finalist:

```text
SPY_QQQ_50_50_SMA150_CASH
```

Rationale:

```text
1. Meets target CAGR, MaxDD, Sharpe, Sortino, and Calmar bands.
2. Materially improves drawdown versus passive SPY/QQQ exposure.
3. Survives GFC and 2022 bear-market robustness checks.
4. Maintains strong absolute performance in recovery and recent windows.
5. Has a simple, auditable rule.
6. Does not rely on crypto allocator logic, broker logic, or defensive-carry overlays.
```

Known weakness:

```text
Delayed re-entry can underperform fast V-shaped recoveries, as seen in COVID 2020.
```

## Current Guardrails

```text
No paper-trading approval.
No live allocation approval.
No broker or execution changes.
No crypto runtime changes.
No crypto/equity global allocator.
No forcing equities into the crypto book.
No SGOV/BIL/SHV/T-bill overlay yet.
No volatility sleeve search yet.
No dashboard or deployment changes.
```

## Next Valid Research Steps

Recommended next steps, in order:

```text
1. Finalize the research record with this memo.
2. Review yearly returns and failure modes for SPY_QQQ_50_50_SMA150_CASH.
3. Consider walk-forward / parameter stability testing for SMA windows around 100–250 days.
4. Only after stability review, consider whether cash should remain cash or whether a T-bill proxy overlay is worth testing.
5. Do not approve paper trading until the finalist has passed stability and implementation-readiness review.
```

## Bottom Line

Equity Book v1 is worth continuing.

The recovered old artifacts were not strong enough, but the fresh baseline sweep found a credible research finalist:

```text
SPY_QQQ_50_50_SMA150_CASH
```

It delivers the core desired trade-off: lower CAGR than passive QQQ or passive SPY/QQQ 50/50, but dramatically improved drawdown-adjusted performance and a clean, explainable rule set.
