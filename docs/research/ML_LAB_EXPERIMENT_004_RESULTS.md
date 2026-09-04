# ML Lab Experiment 004 — Target Integrity Results

**Branch:** `agent/ml-lab-exploration-20260903`

**Status:** EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY

## Question tested

Does the volatility predictability seen in Experiments 002–003 survive when the outcome denominator is changed from trailing 24h realized volatility to trailing 168h realized volatility, so that current 24h volatility is no longer mechanically embedded in the label hurdle?

## Result summary

Yes, predictive structure survives, but at materially lower strength than under the original relative-expansion target.

The original Experiment 003 target produced pooled AUCs roughly in the 0.78–0.82 range. Under the corrected target `future 24h realized vol / trailing 168h realized vol >= threshold`, pooled AUCs fall into a more modest but still nontrivial range, approximately 0.66–0.74 across BTC and locked BTC→ETH transfer.

This demonstrates two things simultaneously:

1. the earlier target construction materially inflated apparent predictability because current 24h volatility was part of the outcome denominator;
2. a substantive volatility-persistence/clustering signal remains after that issue is removed.

## Pooled model results

### Threshold 1.00

- BTC logistic AUC: 0.6653
- BTC GBM AUC: 0.6633
- ETH transfer logistic AUC: 0.6698
- ETH transfer GBM AUC: 0.6728

### Threshold 1.25

- BTC logistic AUC: 0.6965
- BTC GBM AUC: 0.6893
- ETH transfer logistic AUC: 0.6960
- ETH transfer GBM AUC: 0.6948

### Threshold 1.50

- BTC logistic AUC: 0.7100
- BTC GBM AUC: 0.6996
- ETH transfer logistic AUC: 0.7155
- ETH transfer GBM AUC: 0.7033

### Threshold 1.75

- BTC logistic AUC: 0.7057
- BTC GBM AUC: 0.6970
- ETH transfer logistic AUC: 0.7431
- ETH transfer GBM AUC: 0.7290

## Model-complexity conclusion

Shallow GBM again does not establish durable incremental value over logistic regression.

Across thresholds and roles, GBM typically matches or underperforms logistic on AUC and average precision. The effect is especially clear at the more severe 1.50 and 1.75 thresholds.

The Experiment 003 ETH tail-ranking advantage for GBM does not survive this target-integrity correction in a broad, stable way.

Exploratory conclusion for this sub-thread:

> Predictive structure exists, but nonlinear boosting is not justified by these low-dimensional price-state features.

This is not a global conclusion about ML at Itera.

## State-geometry result

The decile relationship flips relative to Experiment 003 once the target denominator is corrected.

For BTC at threshold 1.25, the event rate rises from roughly 7.5% in the lowest `vol_ratio_24_168` decile to roughly 33.1% in the highest decile.

For BTC at threshold 1.50, it rises from roughly 3.4% to roughly 22.5%.

ETH shows the same broad monotonic structure.

Interpretation:

> When short-horizon realized volatility is already elevated relative to the slower 168h volatility regime, the next 24 hours are more likely to remain unusually volatile relative to that slower baseline.

This is consistent with volatility persistence/clustering rather than the denominator artifact exposed in Experiment 003.

## Feature-importance shift

After correcting the target, `realized_vol_168h` becomes the dominant feature for both models, while `realized_vol_24h` becomes much less important than it was under the original target.

This is consistent with the intended target-integrity correction: current 24h volatility is no longer mechanically determining the classification hurdle.

## ML Lab synthesis after Experiments 001–004

1. Continuation ranking is learnable, but logistic captures essentially all of the useful structure in the tested feature set.
2. Relative volatility expansion is highly learnable, but the original target definition materially inflated apparent predictability.
3. After correcting the target, real volatility predictability remains and transfers BTC→ETH.
4. Across these low-dimensional price-state classification tasks, shallow GBM has not earned its complexity over logistic regression.
5. The most useful role ML has played in this sequence is as a research microscope: it exposed structure that could then be simplified, interrogated, and corrected.

## Disposition

Close the BTC/ETH low-dimensional price-state classifier sub-thread as an exploratory methodological negative for nonlinear complexity, not as a rejection of ML generally.

Recommended next ML Lab direction: move to a domain where ML has a stronger structural reason to add value, such as cross-sectional ranking or non-price / heterogeneous information.

No Core v1/Core v2/runtime/threshold/order/NAV/exposure/paper/live/capital implication follows from this result.