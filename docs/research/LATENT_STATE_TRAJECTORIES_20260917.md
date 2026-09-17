# Latent State Trajectories — 2026-09-17

## Status
Observation-only research. No production, strategy, portfolio, runtime, threshold, order, NAV, exposure, or execution change is authorized.

## Motivation
The predecessor state-compression study found that four training-only PCA dimensions preserve essentially the continuous-state information ceiling for forward log variance/downside, while small categorical K-means state sets do not. Core remains an interpretable discrete projection, but some Core labels contain heterogeneous latent conditions.

## Question
Can continuous latent-state trajectories materially improve risk characterization, regime-transition detection, and conditional behavior relative to Core alone?

## Frozen trajectory features
For the causal four-dimensional PCA state z(t), fit using training data only within each walk-forward fold:
- velocity: z(t)-z(t-1)
- acceleration: velocity(t)-velocity(t-1)
- speed: Euclidean norm of velocity
- acceleration magnitude
- distance from the training-state center
- radial velocity: change in distance from the training-state center
- direction: cosine alignment of velocity with the radial vector
- distance to training Core-label centroids, including current-label centroid and nearest alternate-label centroid
- margin: current-label-centroid distance minus nearest-alternate-centroid distance
- margin velocity

No future observation may enter PCA, scaling, centroids, clipping, thresholds, or feature construction.

## Forward questions
Evaluate, separately and descriptively:
1. risk characterization: forward log variance and downside;
2. volatility expansion: whether forward realized variance materially exceeds the trailing/current variance baseline;
3. Core transition detection: whether Core changes label within fixed forward horizons;
4. lead/lag: conditional distributions of trajectory features in windows before Core transitions versus matched non-transition observations;
5. transition direction: whether movement toward an alternate Core centroid is associated with subsequent transition into that label;
6. conditional behavior: whether trajectory features add information within dominant Core labels, especially VOL_COMPRESSION.

## Comparators
- constant baseline
- Core label only
- latent state point only (PCA4)
- trajectory only
- Core + trajectory
- PCA4 + trajectory
- Core + PCA4 + trajectory

Incremental skill must be reported against both constant and Core where meaningful. A richer model is not considered useful merely because it contains more predictors.

## Evaluation discipline
- BTC and ETH
- 1H and 4H source inputs
- UTC-midnight evaluation sampling consistent with predecessor study
- yearly 2020–2025 walk-forward folds
- training-only transforms
- deterministic seed/fits and replay-safe outputs
- adequate event counts reported for every transition/expansion statistic
- no threshold tuning against evaluation folds

## Interpretation guardrails
This study may establish descriptive/predictive state information. It may not authorize a trading rule, portfolio change, exposure change, runtime integration, or production promotion. Return alpha is not the target of this campaign.

## Decision
Advance only if trajectory information adds stable out-of-sample information beyond Core and/or the PCA4 state point itself, with cross-asset/timeframe support and sufficient transition-event counts. Otherwise close the trajectory hypothesis as non-incremental.