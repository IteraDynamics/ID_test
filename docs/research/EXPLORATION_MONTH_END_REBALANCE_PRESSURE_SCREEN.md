# Exploration Screen — Month-End Equity/Bond Rebalancing Pressure

**Status:** SCREEN CARD FROZEN / OUTCOME NOT YET RUN
**Date:** 2026-09-02
**Governance:** `docs/ITERA_EXPLORATION_SANDBOX.md`

## Screen card

- **Mechanism:** balanced portfolios, pensions, target-risk mandates, and other asset allocators mechanically rebalance equity/bond weights after relative asset-class moves. If equities materially outperform bonds during a month, month-end allocation maintenance should create net sell-equity / buy-bond pressure; if bonds outperform, the pressure should reverse. The hypothesized edge comes from mandate-driven flow, not a generic price anomaly.
- **Survival argument:** rebalancing trades are executed to restore policy weights or risk budgets, not because the allocator believes the short-horizon trade itself has positive alpha. The flow can therefore persist even when anticipated, although arbitrageurs may front-run or diffuse it.
- **Instrument / venue:** SPY as the equity leg and AGG as the broad US investment-grade bond proxy. Both are plain US ETFs. Research-only sandbox; no live/paper action authorized.
- **Horizon sanity:** the primary event window is the final **3 trading sessions of each calendar month**. The signal is computed only through the close immediately before that 3-session window, so the screen is causal at daily resolution. Secondary descriptive windows are 1 and 5 final sessions, frozen now and not used to rescue the primary gate.
- **Falsification:** monthly equity-minus-bond relative performance through the cutoff does not predict opposite-signed SPY-minus-AGG relative performance during the final 3 sessions; the effect is not stronger than shuffled month labels; or the result is concentrated in one small era/handful of crisis months.
- **Budget:** one sandbox session. No paid data and no campaign-level machinery unless the screen passes.

## Frozen design

### Data

- `data/SPY_1D.csv`
- `data/AGG_1D.csv`

Both sources must contain `timestamp` and `close`, cover the same monthly event windows, and be parsed causally. Missing/ambiguous months are skipped and counted; the script fails closed if too few valid months remain.

### Signal

For each calendar month `m`:

1. identify the final 3 shared SPY/AGG trading sessions of `m`;
2. define the cutoff close as the session immediately preceding those final 3 sessions;
3. define the month-start anchor as the final shared session of the prior calendar month;
4. compute pre-window relative performance:
   `signal_m = SPY_return(anchor -> cutoff) - AGG_return(anchor -> cutoff)`.

Positive `signal_m` means equities outperformed bonds before the rebalance window and therefore predicts negative relative equity performance during the month-end window.

### Primary endpoint

`outcome_3d = SPY_return(cutoff -> month_end) - AGG_return(cutoff -> month_end)`.

Expected sign: negative association between `signal_m` and `outcome_3d`.

Two frozen primary summaries:

1. Spearman correlation between signal and 3-day outcome, expected `< 0`.
2. Causal expanding-tercile spread: low-signal months minus high-signal months for `outcome_3d`, expected `> 0`; minimum 36 prior months before assigning a state.

### Negative control

1,000 fixed-seed permutations shuffle signal values **within 5-year calendar blocks** while leaving month-end outcomes fixed. This preserves broad era/regime structure better than a global shuffle.

Primary gate passes only if BOTH:

- Spearman rho is negative with one-sided permutation `p <= 0.05`; and
- low-minus-high 3-day relative-return spread is positive with one-sided permutation `p <= 0.05`.

### Robustness / anti-salvage checks

The same frozen signal is also reported for final 1-session and 5-session windows, but these are descriptive only and cannot rescue a failed 3-day primary gate.

The report must include:

- number of valid months and skipped months;
- yearly and decade-level primary differences;
- top 10 absolute-signal months with outcomes;
- leave-one-year-out primary statistics;
- quarter-end vs non-quarter-end descriptive splits.

A result that depends on one crisis year or a few extreme months is `SCREEN_NEGATIVE` or `SCREEN_INCONCLUSIVE`, not a promotion.

## Boundary

A `SCREEN_POSITIVE` only earns governed research. It authorizes no Core v1/Core v2/runtime/portfolio/order/NAV/exposure/paper/live change.
