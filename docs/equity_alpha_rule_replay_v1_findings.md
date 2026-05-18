# Equity Alpha Rule Replay v1 — Findings

## Status

**Branch:** `research/equity-alpha-rule-replay-v1`

**Research status:** hard-overlay and soft-overlay rule replays completed.

**Decision:** do not promote any tested overlay yet.

**Runtime status:** no paper trading, live allocation, broker/execution, dashboard, runtime, crypto allocator, or global allocator changes approved.

## Executive Summary

The breadth / dispersion / leadership diagnostic signal remains informative, but the tested overlay implementations do not yet improve the promoted Equity Core + BIL baseline on the required drawdown-adjusted basis.

The key diagnostic lead was:

```text
weak_breadth__qqq_leading
```

The diagnostic study showed strong forward-return separation, but the replay tests showed that monetizing the signal is non-trivial.

The first hard-overlay pass was too aggressive. It added return in some cases, but materially worsened drawdown and Calmar.

The second soft-overlay pass was better behaved, but still did not beat the baseline on the primary promotion metric.

## Baseline Hurdle

The corrected baseline is:

```text
BASE_EQUITY_CORE_BIL
Window: 2019-03-08 → 2025-12-30
CAGR:   17.03%
MaxDD: -19.53%
Sharpe: 1.181
Sortino: 1.634
Calmar: 0.872
AnnVol: 14.21%
Worst 90d:  -11.38%
Worst 180d: -11.37%
```

This matches the previously validated Equity Core + BIL result and is the correct hurdle for overlay promotion.

## Hard Overlay Results

The hard overlay pass tested direct full-risk or reduction rules:

```text
RULE_WEAK_BREADTH_QQQ_LEADING_ALLOW
RULE_WEAK_BREADTH_QQQ_LAGGING_REDUCE
RULE_HIGH_CORR_ALLOW
RULE_COMBINED_NARROW_LEADERSHIP_AND_CORR
```

### Hard Pass Verdict

Do not promote.

The most return-positive hard rule was:

```text
RULE_HIGH_CORR_ALLOW
CAGR:   23.34%
MaxDD: -30.86%
Sharpe: 1.195
Calmar: 0.756
```

This improved CAGR and slightly improved Sharpe, but the drawdown expansion was too severe.

The `weak_breadth__qqq_leading` hard allow rule also failed promotion:

```text
RULE_WEAK_BREADTH_QQQ_LEADING_ALLOW
CAGR:   18.37%
MaxDD: -30.86%
Sharpe: 1.037
Calmar: 0.595
```

Interpretation:

```text
The signal contains return information, but forcing full SPY/QQQ exposure is too blunt.
```

## Soft Overlay Results

The soft pass tested smaller exposure tilts rather than full exposure overrides.

### Baseline

```text
BASE_EQUITY_CORE_BIL
CAGR:   17.03%
MaxDD: -19.53%
Sharpe: 1.181
Calmar: 0.872
```

### Best Soft CAGR / Sharpe Candidate

```text
SOFT_HIGH_CORR_TILT_10
CAGR:   17.77%
MaxDD: -20.72%
Sharpe: 1.212
Sortino: 1.677
Calmar: 0.858
Worst 90d:  -11.18%
Worst 180d: -10.30%
```

This is the most interesting soft result. It improved CAGR, Sharpe, Sortino, and worst-window behavior versus baseline, but its Calmar was slightly lower because MaxDD worsened from -19.53% to -20.72%.

Decision:

```text
Interesting, but not promoted yet.
```

### Best Soft Calmar Result After Baseline

```text
SOFT_WEAK_LAGGING_REDUCE_75
CAGR:   16.84%
MaxDD: -19.53%
Sharpe: 1.170
Calmar: 0.862
```

This preserved drawdown but reduced CAGR and Sharpe. Not promoted.

### Weak Leading Soft Tilts

```text
SOFT_WEAK_LEADING_ACTIVE_ONLY_15
CAGR:   17.29%
MaxDD: -20.21%
Sharpe: 1.183
Calmar: 0.856

SOFT_WEAK_LEADING_TILT_10
CAGR:   17.34%
MaxDD: -20.72%
Sharpe: 1.188
Calmar: 0.837

SOFT_WEAK_LEADING_TILT_15
CAGR:   17.49%
MaxDD: -21.34%
Sharpe: 1.189
Calmar: 0.820
```

These improve CAGR modestly, but all reduce Calmar due to increased drawdown.

Decision:

```text
Do not promote weak-leading tilts in this form.
```

### Combined Soft Rule

```text
SOFT_COMBINED_TILT10_REDUCE75
CAGR:   16.01%
MaxDD: -19.54%
Sharpe: 1.250
Sortino: 1.737
Calmar: 0.820
AnnVol: 12.55%
Worst 90d:  -10.99%
Worst 180d:  -8.95%
```

This rule improves Sharpe, Sortino, volatility, and worst-window behavior, but it gives up too much CAGR and does not improve Calmar.

Reason:

```text
low_corr fired on 57.70% of bars, making the combined caution rule too broad and suppressive.
```

Decision:

```text
Not promoted as an alpha overlay.
Potentially useful as a conservative risk-profile variant, but not as the default equity alpha overlay.
```

## Exposure Observations

Baseline average exposure:

```text
Average equity weight: 81.04%
Average BIL weight:    18.96%
```

Most soft tilt rules changed exposure only modestly:

```text
SOFT_HIGH_CORR_TILT_10 average equity weight: 82.15%
SOFT_WEAK_LEADING_TILT_10 average equity weight: 81.47%
SOFT_WEAK_LEADING_TILT_15 average equity weight: 81.69%
```

The combined rule materially reduced exposure:

```text
SOFT_COMBINED_TILT10_REDUCE75 average equity weight: 68.43%
```

That explains its lower CAGR and lower volatility.

## Rule Event Counts

```text
weak_breadth__qqq_leading: 119 bars / 6.94%
weak_breadth__qqq_lagging: 158 bars / 9.22%
high_corr:                 309 bars / 18.03%
low_corr:                  989 bars / 57.70%
```

Interpretation:

```text
weak_breadth__qqq_leading is selective enough to remain interesting.
high_corr is broad enough to be useful as a confirmation state.
low_corr is too broad to use as a blunt caution trigger.
```

## Research Decision

Do not promote any tested rule as an equity alpha overlay.

Promote the following research conclusion:

```text
The breadth / leadership / correlation signals contain useful regime information, but the first hard and soft deterministic overlays do not yet improve Equity Core + BIL on the required Calmar/drawdown-adjusted basis.
```

## What Survives

The alpha lead is not dead.

The most promising surviving idea is:

```text
high_corr as a modest risk-on confirmation or reporting diagnostic
```

because `SOFT_HIGH_CORR_TILT_10` improved CAGR, Sharpe, Sortino, and worst 90/180-day behavior, despite a slightly lower Calmar.

The second surviving idea is:

```text
weak_breadth__qqq_leading as a regime label, not a direct exposure override
```

It may be useful in reporting, signal confidence, or future conditional rules, but not as a direct full-risk or simple tilt overlay yet.

## Recommended Next Step

Do not keep brute-forcing overlays in this branch.

Next research should move from rule overlays to attribution and regime anatomy:

```text
Equity Alpha Regime Anatomy v1
```

Questions:

```text
1. Which dates make weak_breadth__qqq_leading look so good in forward-return diagnostics?
2. Are returns concentrated in a few post-crash recovery windows?
3. Does the edge survive excluding 2020 and 2023?
4. Is high_corr just identifying periods where the baseline was already risk-on?
5. Are the signals useful for reporting/diagnostics rather than exposure rules?
```

## Guardrails

```text
No paper trading.
No live allocation.
No broker integration.
No runtime integration.
No dashboard integration.
No global allocator.
No promotion of tested overlays.
```

## Bottom Line

Equity Alpha Rule Replay v1 is a useful negative/near-miss result.

It prevents us from overfitting a good-looking diagnostic into a bad trading rule.

The promoted Equity Core + BIL baseline remains the best equity sleeve.

The breadth / leadership / correlation signals remain useful research leads, but not yet monetizable overlays.
