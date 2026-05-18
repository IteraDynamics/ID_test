# Equity Enhancements v1 — Defensive Substitute Findings

## Status

**Branch:** `research/equity-enhancements-v1`

**Research status:** defensive carry / risk-off substitute sweep complete.

**Runtime status:** no paper-trading, broker, execution, governor, live allocation, crypto runtime, dashboard, or global allocator changes approved.

## Executive Summary

The Equity Core v1 signal was kept fixed:

```text
SPY/QQQ 50/50 SMA175 trend-to-cash signal
```

This sweep varied only the inactive-sleeve risk-off asset:

```text
cash
SGOV
BIL
SHV
IEF
TLT
GLD
```

The result is clear:

```text
Short-duration Treasury proxies are useful, clean, modest enhancements.
Intermediate/long-duration bonds and gold are not suitable as default risk-off substitutes.
```

## Primary Decision

Carry forward short-duration Treasury proxies as the defensive-carry enhancement family:

```text
Primary practical candidate: BIL
Best recent-history candidate: SGOV
Secondary practical candidate: SHV
Reference baseline: cash
```

Reject as default risk-off substitutes:

```text
IEF
TLT
GLD
```

## Why This Matters

The original Equity Core v1 used literal cash when either the SPY or QQQ sleeve was inactive. In actual equity portfolio construction, inactive capital can often earn short-duration Treasury yield or sit in Treasury collateral-like instruments.

This sweep asks whether the system should model risk-off as:

```text
zero-return cash
```

or as:

```text
short-duration Treasury carry
```

The answer is that Treasury-bill-like risk-off improves the book modestly and cleanly, but does not transform it into a new alpha engine.

## Full Sweep Results

### Performance Summary

```text
SPY_QQQ_SMA175_RISK_OFF_SGOV:
  Start: 2020-06-01
  End:   2025-12-30
  CAGR:   18.44%
  MaxDD: -14.67%
  Sharpe: 1.287
  Sortino: 1.823
  Calmar: 1.256

SPY_QQQ_SMA175_RISK_OFF_BIL:
  Start: 2019-03-08
  End:   2025-12-30
  CAGR:   17.03%
  MaxDD: -19.53%
  Sharpe: 1.181
  Sortino: 1.634
  Calmar: 0.872

SPY_QQQ_SMA175_RISK_OFF_SHV:
  Start: 2019-03-08
  End:   2025-12-30
  CAGR:   16.98%
  MaxDD: -19.53%
  Sharpe: 1.178
  Sortino: 1.630
  Calmar: 0.870

SPY_QQQ_SMA175_RISK_OFF_CASH:
  Start: 2005-01-03
  End:   2026-04-29
  CAGR:   10.29%
  MaxDD: -19.56%
  Sharpe: 0.849
  Sortino: 1.172
  Calmar: 0.526

SPY_QQQ_SMA175_RISK_OFF_IEF:
  Start: 2005-01-03
  End:   2026-05-06
  CAGR:   11.05%
  MaxDD: -25.64%
  Sharpe: 0.872
  Sortino: 1.212
  Calmar: 0.431

SPY_QQQ_SMA175_RISK_OFF_GLD:
  Start: 2005-01-03
  End:   2026-05-06
  CAGR:   12.25%
  MaxDD: -35.59%
  Sharpe: 0.785
  Sortino: 1.105
  Calmar: 0.344

SPY_QQQ_SMA175_RISK_OFF_TLT:
  Start: 2005-01-03
  End:   2026-05-06
  CAGR:   10.28%
  MaxDD: -40.18%
  Sharpe: 0.729
  Sortino: 1.018
  Calmar: 0.256

PASSIVE_SPY_QQQ_50_50:
  Start: 2005-01-03
  End:   2026-04-29
  CAGR:   12.93%
  MaxDD: -53.66%
  Sharpe: 0.712
  Sortino: 1.012
  Calmar: 0.241
```

## Pairwise Versus Cash

The pairwise table is the most important because it compares each defensive substitute against cash over the same overlapping dates.

```text
SGOV vs cash over SGOV overlap:
  Delta CAGR:   +0.54 percentage points
  Delta MaxDD:  +1.36 percentage points
  Delta Sharpe: +0.033
  Delta Sortino:+0.046
  Delta Calmar: +0.140

BIL vs cash over BIL overlap:
  Delta CAGR:   +0.42 percentage points
  Delta MaxDD:  +0.03 percentage points
  Delta Sharpe: +0.025
  Delta Sortino:+0.035
  Delta Calmar: +0.023

SHV vs cash over SHV overlap:
  Delta CAGR:   +0.37 percentage points
  Delta MaxDD:  +0.03 percentage points
  Delta Sharpe: +0.023
  Delta Sortino:+0.031
  Delta Calmar: +0.020

IEF vs cash over IEF overlap:
  Delta CAGR:   +0.75 percentage points
  Delta MaxDD:  -6.08 percentage points
  Delta Sharpe: +0.022
  Delta Sortino:+0.038
  Delta Calmar: -0.096

GLD vs cash over GLD overlap:
  Delta CAGR:   +1.87 percentage points
  Delta MaxDD: -16.03 percentage points
  Delta Sharpe: -0.068
  Delta Sortino:-0.073
  Delta Calmar: -0.184

TLT vs cash over TLT overlap:
  Delta CAGR:   -0.06 percentage points
  Delta MaxDD: -20.62 percentage points
  Delta Sharpe: -0.123
  Delta Sortino:-0.158
  Delta Calmar: -0.272
```

## Interpretation

### SGOV

SGOV produced the strongest recent-history result:

```text
CAGR:   18.44%
MaxDD: -14.67%
Sharpe: 1.287
Calmar: 1.256
```

Pairwise versus cash over the SGOV overlap, it improved CAGR, MaxDD, Sharpe, Sortino, and Calmar.

However, SGOV history starts in 2020. It misses GFC, the 2010s, and the COVID crash itself. It should be carried forward as the best recent-history candidate, not treated as a full-cycle answer.

### BIL

BIL is the strongest practical conservative candidate.

It improved CAGR and risk-adjusted metrics versus cash over its available overlap while barely changing MaxDD.

```text
Delta CAGR vs cash:  +0.42 percentage points
Delta MaxDD vs cash: +0.03 percentage points
Delta Calmar:        +0.023
```

This is not a dramatic improvement, but it is clean and explainable.

### SHV

SHV behaved similarly to BIL but slightly weaker.

```text
Delta CAGR vs cash:  +0.37 percentage points
Delta MaxDD vs cash: +0.03 percentage points
Delta Calmar:        +0.020
```

It remains a valid secondary candidate.

### IEF

IEF added full-period CAGR but worsened drawdown-adjusted quality.

```text
Delta CAGR vs cash:  +0.75 percentage points
Delta MaxDD vs cash: -6.08 percentage points
Delta Calmar:        -0.096
```

This means IEF is not a clean risk-off substitute. It adds duration risk.

### GLD

GLD added full-period CAGR, but at too much drawdown and volatility cost.

```text
Delta CAGR vs cash:  +1.87 percentage points
Delta MaxDD vs cash: -16.03 percentage points
Delta Calmar:        -0.184
```

GLD may be a separate diversifier candidate someday, but it should not be the default inactive-sleeve holding.

### TLT

TLT is a reject as a default risk-off substitute.

```text
Delta CAGR vs cash:  -0.06 percentage points
Delta MaxDD vs cash: -20.62 percentage points
Delta Calmar:        -0.272
```

It adds too much duration and rate-shock risk.

## Research Decision

Promote this finding:

```text
Equity Core v1 should carry forward short-duration Treasury proxy risk-off as an enhancement family.
```

Do not promote duration-heavy bonds or gold as default risk-off substitutes.

Current ranking:

```text
1. BIL — primary practical candidate
2. SGOV — best recent-history candidate
3. SHV — secondary practical candidate
4. cash — reference baseline
5. IEF — demote; duration risk
6. GLD — demote; separate diversifier only
7. TLT — reject as default risk-off
```

## Recommended Next Step

The next clean research step is not paper trading and not broker integration.

It is one of two things:

```text
Option A:
Short-duration defensive implementation-readiness

Goal:
Represent risk-off as a configurable short-duration Treasury proxy inside the Equity Book signal/replay layer.

Option B:
Sector rotation research

Goal:
Explore whether equity-sector leadership rotation can add a genuine equity alpha sleeve beyond the core SPY/QQQ book.
```

Recommended order:

```text
1. Finish this branch as a research checkpoint.
2. Then start sector rotation research as a separate branch.
```

## Guardrails

```text
No paper trading.
No live allocation.
No broker or execution changes.
No crypto runtime changes.
No crypto/equity global allocator.
No dashboard integration.
No SGOV/BIL/SHV implementation until this research checkpoint is merged.
```

## Bottom Line

Short-duration Treasury proxies are worth carrying forward.

They improve the Equity Core modestly, cleanly, and explainably. BIL is the most practical first candidate, SGOV is the best recent-history candidate, and SHV is a valid secondary candidate.

IEF, TLT, and GLD should not be default risk-off substitutes because they add hidden duration or commodity drawdown risk.
