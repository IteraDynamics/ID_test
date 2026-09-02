# Exploration Screen — Month-End Equity/Bond Rebalancing Pressure

**Status:** SCREEN CARD FROZEN / OUTCOME NOT YET RUN
**Date:** 2026-09-02
**Governance:** `docs/ITERA_EXPLORATION_SANDBOX.md`

## Screen card

- **Mechanism:** balanced portfolios, pensions, target-risk mandates, and other asset allocators mechanically rebalance equity/bond weights after relative asset-class moves. If equities materially outperform bonds during a month, month-end allocation maintenance should create net sell-equity / buy-bond pressure; if bonds outperform, the pressure should reverse. The hypothesized edge comes from mandate-driven flow, not a generic price anomaly.
- **Survival argument:** rebalancing trades are executed to restore policy weights or risk budgets, not because the allocator believes the short-horizon trade itself has positive alpha. The flow can therefore persist even when anticipated, although arbitrageurs may front-run or diffuse it.
- **Instrument / venue:** SPY as the equity leg and AGG as the broad US investment-grade bond proxy. Both are plain US ETFs. Research-only sandbox; no live/paper action authorized.
- **Horizon sanity:** the primary event window is the final **3 trading sessions of each calendar month**. The signal is computed only through the close immediately before that 3-session window, so the screen is causal at daily resolution. Final 1-session and 5-session windows are frozen as descriptive robustness checks; each uses its own matching pre-window cutoff so no secondary outcome starts before its signal is observable.
- **Falsification:** monthly equity-minus-bond relative performance through the cutoff does not predict opposite-signed SPY-minus-AGG relative performance during the final 3 sessions; the effect is not stronger than shuffled month labels; or the result is concentrated in one small era/handful of crisis months.
- **Budget:** one sandbox session. No paid data and no campaign-level machinery unless the screen passes.

## Frozen design

### Data

Use isolated sandbox total-return-like daily series generated with the existing research downloader and `--auto-adjust`:

- `artifacts/month_end_rebalance_data/SPY_1D.csv`
- `artifacts/month_end_rebalance_data/AGG_1D.csv`

Adjusted data are required because AGG distributes income monthly; comparing unadjusted SPY close to unadjusted AGG close would mechanically distort the monthly equity-vs-bond relative-performance signal. These sandbox files do not replace or mutate canonical Core v1 sources.

Both sources must contain `timestamp` and `close`, cover the same monthly event windows, and be parsed causally. Missing/ambiguous months are skipped and counted; the script fails closed if fewer than 120 valid monthly observations remain.

### Signal

For each calendar month `m` and event window `w` in `{1, 3, 5}` trading sessions:

1. identify the final `w` shared SPY/AGG trading sessions of `m`;
2. define the cutoff close as the session immediately preceding those final `w` sessions;
3. define the month-start anchor as the final shared session of the prior calendar month;
4. compute pre-window relative performance:
   `signal_m,w = SPY_return(anchor -> cutoff_w) - AGG_return(anchor -> cutoff_w)`.

Positive signal means equities outperformed bonds before the rebalance window and therefore predicts negative relative equity performance during that month-end window.

### Primary endpoint

Primary window: final **3 trading sessions**.

`outcome_3d = SPY_return(cutoff_3d -> month_end) - AGG_return(cutoff_3d -> month_end)`.

Expected sign: negative association between `signal_3d` and `outcome_3d`.

Two frozen primary summaries:

1. Spearman correlation between signal and 3-day outcome, expected `< 0`.
2. Causal expanding-tercile spread: low-signal months minus high-signal months for `outcome_3d`, expected `> 0`; minimum 36 prior months before assigning a state.

### Negative control

1,000 fixed-seed permutations shuffle signal values **within 5-year calendar blocks** while leaving month-end outcomes fixed. This preserves broad era/regime structure better than a global shuffle. For the tercile control, causal expanding labels are recomputed from each permuted signal sequence rather than merely shuffling already-created labels.

### Frozen positive gate

`SCREEN_POSITIVE` requires all of the following on the primary 3-session window:

- Spearman rho `< 0` with one-sided permutation `p <= 0.05`;
- causal low-minus-high outcome spread `> 0` with one-sided permutation `p <= 0.05`;
- leave-one-calendar-year-out Spearman rho remains `< 0` for every eligible omitted year, preventing one crisis year from carrying the sign.

Otherwise the primary thesis is `SCREEN_NEGATIVE` unless a source/support defect makes the result genuinely inconclusive.

### Robustness / anti-salvage checks

Final 1-session and 5-session windows are descriptive only and cannot rescue a failed 3-session primary gate. Each uses its own causal signal cutoff as defined above.

The report must include:

- number of valid months and skipped months;
- yearly and decade-level primary differences;
- top 10 absolute-signal months with outcomes;
- leave-one-year-out primary statistics;
- quarter-end vs non-quarter-end descriptive splits.

No threshold/window tuning after outcome inspection. A later quarter-end-only or other variant would require a genuinely new screen card rather than reinterpreting this result.

## Boundary

A `SCREEN_POSITIVE` only earns governed research. It authorizes no Core v1/Core v2/runtime/portfolio/order/NAV/exposure/paper/live change.
