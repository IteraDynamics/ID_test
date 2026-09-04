# ML Lab Experiment 008 — Tail Increment Audit Results

## Status

**EXPLORATORY / DIAGNOSTIC / NON-CONFIRMATORY**

Sub-thread classification: **EXPLORATORY_NONLINEAR_INCREMENT_NOT_ROBUST**.

This result does not reject machine learning globally and does not authorize any Core, runtime, threshold, order, NAV, exposure, strategy, portfolio, paper, live, or capital change.

## Question

When Ridge and GBM disagree on cross-sectional ETF tails, does GBM systematically select better winners and/or worse losers?

Experiment 008 used only saved Experiment 007 out-of-sample predictions. No model refit, tuning, feature change, target change, memory change, or 2025 Campaign #50 holdout use occurred.

## Main result

The historical expanding-window GBM tail advantage did not survive the post-2021 regime break.

Pre-2022 expanding GBM versus Ridge:

- quartile combined raw increment: approximately **+0.106**
- top-3 combined raw increment: approximately **+0.122**

Post-2021 expanding GBM versus Ridge:

- quartile combined raw increment: approximately **-0.141**
- top-3 combined raw increment: approximately **-0.095**

The old nonlinear tail advantage therefore reversed rather than merely weakened.

## Adaptive-memory result

Shorter-memory GBMs partially repaired the post-2021 tail outcome, but the increment was not robust across tail definitions or summary statistics.

### Trailing 3-year memory, 2022-2024

- quartile combined raw increment: approximately **+0.089**
- top-3 combined raw increment: approximately **+0.072**
- positive combined raw fraction: about **47%** for quartiles and **54%** for top-3
- medians were mixed, including a negative quartile median

This indicates that a minority of larger positive cases can pull the mean upward; it is not evidence of a consistently superior tail-selection process.

### Trailing 5-year memory, 2022-2024

- quartile combined raw increment: approximately **+0.038**
- top-3 combined raw increment: approximately **-0.064**

The sign instability across reasonable tail definitions argues against treating the apparent nonlinear increment as durable.

## Asset concentration

Positive incremental outcomes were materially concentrated in a small number of ETFs.

For trailing 3-year memory in 2022-2024, the top three positive contributors accounted for roughly:

- **61%** of positive quartile increment
- **74%** of positive top-3 increment

Key names included XLK, XLI, and XLF. Other memory/tail definitions were often more concentrated, in some cases above 80% in the top three contributors.

## Interpretation

Experiments 005-008 support the following narrower conclusion:

> Nonlinear ML can discover economically interesting cross-sectional relationships and historically did outperform a linear ranker, but the nonlinear increment was regime-sensitive. Shorter memory improved adaptation, yet the remaining tail advantage was inconsistent across definitions and concentrated in a few assets. Complexity did not earn a durable role in this price-only ETF-ranking family.

This is not a global rejection of ML.

## Closure

Close the **price/volume-only cross-sectional nonlinear ranking sub-thread** as:

**EXPLORATORY_NONLINEAR_INCREMENT_NOT_ROBUST**

The broader ML Lab remains open. The next scientifically justified direction is a genuinely different information set, with priority on explicit macro/rates state rather than additional transformations of the same ETF price data.
