# ML Lab Experiment 003 — Results

**Branch:** `agent/ml-lab-exploration-20260903`

**Status:** EXPLORATORY / NON-CONFIRMATORY

## Headline

Experiment 003 did not establish a broad nonlinear-model advantage. Logistic regression retained the higher pooled ROC AUC than shallow GBM across all tested severity thresholds on BTC, and GBM's AUC disadvantage generally widened as expansion severity increased.

The more important finding was structural: the target `future_24h_vol / trailing_24h_vol >= threshold` is dominated by a highly monotonic relationship with current short-term volatility relative to long-term volatility. That relationship transfers strongly from BTC to ETH.

## Model comparison

Across thresholds 1.25, 1.50, 1.75, and 2.00:

- BTC pooled ROC AUC favored logistic at every severity;
- ETH pooled ROC AUC also favored logistic at every severity;
- BTC average-precision deltas did not show a stable GBM advantage;
- ETH average precision increasingly favored GBM in the tail, culminating at threshold 2.00 with GBM AP above logistic and GBM winning AP in 6/6 yearly transfer folds;
- ETH top-1% and top-5% lift also favored GBM at the highest severities.

This ETH tail-ranking behavior is interesting but not sufficient to claim a general nonlinear advantage because the same pattern does not appear on BTC, the asset used for fitting.

## State geometry

The dominant state variable is `vol_ratio_24_168`.

For BTC at threshold 1.25:

- lowest decile median vol ratio ≈ 0.422; event rate ≈ 77.8%;
- highest decile median vol ratio ≈ 1.624; event rate ≈ 8.4%.

For BTC at threshold 2.00:

- lowest decile event rate ≈ 38.6%;
- highest decile event rate ≈ 1.2%.

ETH shows the same qualitative monotonic shape.

GBM feature importance confirms that most nonlinear attention is concentrated in:

1. short/long volatility ratio;
2. current 24h realized volatility;
3. range position / longer-run volatility state.

## Critical target-integrity issue

The Experiment 003 target itself contains trailing 24h realized volatility in its denominator:

`future_24h_vol / trailing_24h_vol >= threshold`

Current 24h realized volatility and the short/long volatility ratio are also among the strongest predictors.

Therefore a low current-volatility state mechanically lowers the hurdle for the future/current ratio to exceed a fixed threshold. The strong monotonic relationship is consistent with genuine volatility mean reversion / compression-expansion behavior, but it is not clean evidence that the models forecast the absolute future volatility level independently of the label construction.

This is not a code bug. It is a target-definition confound revealed by the experiment.

## Interpretation

Experiment 003 supports three conclusions:

1. volatility state is highly structured and transferable across BTC and ETH;
2. shallow GBM still does not broadly outperform competent logistic regression;
3. the current target makes it impossible to cleanly separate genuine forward-volatility predictability from denominator-driven relative expansion behavior.

The right next step is therefore not model tuning. It is a target-integrity experiment.

## Next experiment

Experiment 004 should remove trailing 24h volatility from the outcome denominator and ask whether current state predicts genuinely high future 24h realized volatility relative to a slower causal baseline known at time `t`.

No result here authorizes any Core, runtime, portfolio, paper/live, or capital action.