# ML Lab Experiment 008 — Tail Increment Audit

## Status

**EXPLORATORY / DIAGNOSTIC / NON-CONFIRMATORY.**

No model refit. No tuning. No feature, target, model-family, hyperparameter, memory-scheme, or training change. Campaign #50's reserved 2025 holdout remains untouched. No Core/runtime/portfolio/capital implication.

## Motivation

Experiment 007 showed:

- shorter training memory repaired the post-2021 deterioration for both GBM and Ridge;
- average rank IC did not restore a durable GBM-over-Ridge edge;
- shorter-memory GBMs nevertheless produced stronger top-minus-bottom tail spread than their corresponding Ridge models in 2022–2024.

The remaining ML-specific question is therefore not whether GBM ranks the entire cross-section better, but whether it adds useful information in the extreme selections where the two models disagree.

## Question

> When GBM and Ridge disagree about the cross-sectional tails, do GBM-only selections realize better outcomes than Ridge-only selections, and is any incremental effect stable across time and assets?

## Frozen source

Experiment 008 consumes only:

`artifacts/ml_lab_experiment_007/experiment_007_oos_predictions.csv`

Required columns:

- `timestamp`
- `ticker`
- `target_raw`
- `target_rank`
- `test_year`
- `memory_scheme`
- `model`
- `score`

Only `ridge` and `gbm` rows for:

- `expanding`
- `trailing_5y`
- `trailing_3y`

are analyzed.

## Tail definitions

For each timestamp × memory scheme × model, rank model score across the 14 assets.

Two frozen tail widths:

1. **top/bottom 3** assets — fixed-count extreme set;
2. **top/bottom quartile** — `ceil(N × 0.25)` assets, which is 4 for N=14.

No alternative tail width is searched.

## Comparisons

For each anchor and memory scheme:

### Overlap

Measure Jaccard overlap for GBM vs Ridge:

- top tail
- bottom tail

### Agreement sets

Measure realized `target_raw` and `target_rank` for:

- both models top
- both models bottom

### Disagreement sets

Measure realized outcomes for:

- GBM-only top
- Ridge-only top
- GBM-only bottom
- Ridge-only bottom

Primary incremental contrasts:

- **upside increment** = mean target of GBM-only top − mean target of Ridge-only top
- **downside increment** = mean target of Ridge-only bottom − mean target of GBM-only bottom

The downside sign is defined so positive means GBM selected worse-realized assets into the bottom tail more effectively.

### Combined tail increment

`combined_increment = upside_increment + downside_increment`

This is descriptive only and is not a trading-return measure.

## Periods

Frozen diagnostic periods:

- pre: 2012–2021
- post: 2022–2024

No 2025 data is permitted.

## Stability diagnostics

Report by memory scheme and tail definition:

- eligible anchors with non-empty disagreement sets;
- mean and median upside increment;
- mean and median downside increment;
- mean and median combined increment;
- positive fraction of each increment;
- pre vs post comparison;
- yearly comparison;
- overlap rates.

## Asset concentration

For GBM-only and Ridge-only disagreement selections, attribute contributions by ticker and report:

- selection count;
- mean target outcome;
- contribution to aggregate GBM-vs-Ridge incremental difference;
- share of positive incremental contribution concentrated in top 3 tickers.

## Interpretation rules

This experiment does not validate a model or authorize portfolio use.

A useful nonlinear-tail finding would require a qualitatively coherent pattern such as:

- positive GBM-only vs Ridge-only increment in both pre and post periods;
- support from both top-3 and quartile definitions;
- not dominated by one year or a very small set of assets.

If the effect is unstable, period-specific, or heavily asset-concentrated, the cross-sectional price-state ML thread should be treated as lacking robust incremental nonlinear value despite Experiment 005's historical pooled edge.

## Outputs

`artifacts/ml_lab_experiment_008/`

- `experiment_008_report.json`
- `experiment_008_anchor_tail_audit.csv`
- `experiment_008_period_tail_summary.csv`
- `experiment_008_yearly_tail_summary.csv`
- `experiment_008_asset_attribution.csv`
- `experiment_008_overlap_summary.csv`

## Boundary

Observation-only exploratory research. Nothing in this experiment changes or authorizes Core v1, Core v2, runtime, thresholds, orders, NAV, exposures, strategy, paper/live behavior, or capital allocation.
