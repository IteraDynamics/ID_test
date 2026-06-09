# Core v1 Sleeve Contribution Audit Plan

Research-only planning note.

Branch: `gpt/core-v1-sleeve-contribution-audit`  
Base: merged Core v1 policy selector rejection  
Status: hypothesis before implementation

## Purpose

Core v1 allocation research has produced a stable conclusion:

```text
Core v1 official baseline:   40 trend / 35 equity / 15 gold / 10 hedge / 0 MR
Core v1 smoother candidate:  35 trend / 35 equity / 20 gold / 10 hedge / 0 MR
```

The first-pass policy selector did not justify dynamic switching.

The next useful question is not allocation-level complexity. The next useful question is sleeve-level attribution:

```text
Which sleeves are carrying the system?
Which sleeves are redundant?
Which sleeves protect drawdown?
Which sleeves hurt specific regimes?
```

## Scientific framing

The goal is not to find a sleeve to delete or optimize immediately.

The goal is to expose where Core v1's returns, drawdowns, and robustness actually come from.

A useful audit should be able to falsify assumptions such as:

```text
1. Both BTC trend timeframes are necessary.
2. Both ETH trend timeframes are necessary.
3. The hedge sleeve helps enough to justify its drag.
4. Equity exposure is diversified between SPY and QQQ rather than dominated by QQQ.
5. Gold is true ballast, not just a 2025 artifact.
```

## Baseline sleeves to inspect

Expected sleeve families:

```text
BTC_1H_trend
BTC_4H_trend
ETH_1H_trend
ETH_4H_trend
BTC_1H_hedge
ETH_1H_hedge
SPY_1D_equity
QQQ_1D_equity
GLD_1D_gold
```

MR remains disabled in Core v1:

```text
mr_weight = 0.00
```

## Required outputs

The audit should report at minimum:

```text
1. sleeve final equity by fold/year
2. sleeve return contribution by fold/year
3. sleeve MaxDD by fold/year
4. sleeve Sharpe/Calmar by fold/year where meaningful
5. sleeve trade count by fold/year
6. best and worst sleeve-years
7. sleeve correlation matrix using daily returns
8. contribution concentration by year
9. drawdown-period contribution if artifact structure supports it
```

## First-pass implementation target

Prefer extracting from existing walk-forward outputs if available.

If existing artifacts do not contain sleeve equity curves, add a minimal runner mode or companion script that reruns the same fold/sleeve logic and writes sleeve-level outputs without changing strategy logic.

Do not change strategy behavior in this branch.

Do not change allocation weights in this branch.

Do not introduce confidence sizing in this branch.

## Primary windows

Use the same validated windows:

```text
2021-01-01 to 2025-12-31
2020-01-01 to 2025-12-31
```

Start with the extended baseline:

```text
artifacts/extended_history_2020_2025/baseline_40_35_15_10
```

Then compare gold20 only if the baseline audit reveals useful structure.

## Questions to answer

### Trend sleeves

```text
Is BTC_1H doing something distinct from BTC_4H?
Is ETH_1H doing something distinct from ETH_4H?
Are 1H sleeves primarily return engines or churn/fee sources?
Are 4H sleeves smoother but slower?
```

### Hedge sleeves

```text
When do BTC_1H_hedge and ETH_1H_hedge help?
How much annual drag do they impose?
Did they help in 2020 crash, 2022 bear, or 2025 chop?
Are both hedge sleeves necessary?
```

### Equity sleeves

```text
Is QQQ dominating the equity sleeve?
Does SPY provide useful diversification or mostly dilute QQQ?
How did equity sleeves behave in 2022 versus crypto trend sleeves?
```

### Gold sleeve

```text
Does GLD reduce drawdown during stress?
Is its benefit persistent or mostly concentrated in 2025?
Does gold20 improvement come from true ballast or simply lower trend exposure?
```

## Acceptance criteria for future action

This audit alone should not promote changes.

A sleeve change becomes research-worthy only if the audit reveals a persistent pattern such as:

```text
1. a sleeve consistently adds drawdown without return contribution;
2. two sleeves are highly redundant and one is materially worse;
3. a hedge sleeve creates persistent drag and fails in stress windows;
4. a sleeve contributes mainly to one anomalous year and fails elsewhere;
5. a sleeve produces strong diversification during drawdown windows.
```

Any proposed change must then be tested in a separate ablation branch.

## Guardrails

```text
No live policy change.
No allocation promotion.
No confidence sizing.
No parameter tuning.
No deletion based on one table.
```

## Expected outcome

A good result is a clear attribution map, not necessarily a new strategy.

If all sleeves appear defensible, that is useful.

If one or more sleeves look suspicious, that becomes the next falsification target.
