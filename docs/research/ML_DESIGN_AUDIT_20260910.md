# Learning-design audit — recorded before results

2026-09-10. Operator approved cash-permitted portfolio research with explicit risk
limits and requested the stated learning-design investigation first. Core remains
frozen. All2018–2024 results remain discovery-contaminated development diagnostics.
No2025 use, no confirmation claim and no portfolio promotion from forecast metrics.

## Known-signal diagnostic

Synthetic800 business dates,8 assets, independent standard-normal numeric summary
features, fixed identities. Target .01*(ret5+.5*ret20)+Gaussian noise .001, with
next-six-session label availability. Train first600 signal dates with complete
labels before evaluation; remaining200 dates evaluated weekly. Fixed seed123.
Test ridge100,gbm2,mlp16 through the production breadth.fit and its chronological
neural stopping pipeline. Compare with the known conditional mean, zero and a
training-target permutation (seed321). Recovery criterion: each correctly paired
model reduces test MSE at least50% versus zero; each shuffled-label model below10%
reduction. This validates a strong simple planted relationship, not market alpha,
feature extraction or every nonlinear architecture. Six model evaluations/eight
optimizer fits. Record failures without modifying the criterion after results.

## Cached market audit and bounded controlled comparisons

Use the exact8-ETF source snapshot and breadth forecasts. First inspect saved
loss curves, error contributions by year/asset and signal-time volatility tercile
(cutoffs learned from each annual training fold). No real fits for these audits.

Fix representative ridge100,gbm2,mlp16 before seeing new results. Reuse their saved
raw-return forecasts, verifying source hashes and keys. No candidate reselection.
Compare two new objectives on identical summaries, identities, folds and estimators:
- Risk-scaled return: .01 * raw five-session return / max(.005,rv60*sqrt(5/252)).
  The scale uses information through the signal close. Convert predictions back
  to raw returns before raw-MSE evaluation; also evaluate risk-normalized error.
- Cross-sectional rank: average tied rank of raw future return among8 assets,
  mapped to [-.01,.01] by .02*((rank-1)/7-.5). Treat outputs as ranking scores,
  never as calibrated expected returns. This is pointwise rank regression, not a
  pairwise/listwise ranking loss. Require8 assets per date.

Both transformations define a new objective and target numerical scale; fixed
neural optimizer/regularization interactions cannot be separated from that choice.
Risk scale floor and rank range are not tuned. Raw and risk scores can be compared
on raw-return MSE and normalized MSE; all objectives compared on same-date rank IC.
Report pooled, annual, per-asset and excluding2020 diagnostics. Eight assets give
coarse correlated ranks; no significance claim. No pseudo-investment returns.

42 new model evaluations:2 objectives*3 models*7 outer years;56 optimizer fits.
No inner model selection in this controlled fixed-model comparison. Every variant
is retained, no outer-year winner becomes a trading procedure automatically.

Separate stopping-resolution comparison: raw-return mlp16 only, same data and
parameters, inspect stopping loss every epoch rather than every5. Maximum200,
patience25 and improvement1e-10 unchanged;7 evaluations/14 optimizer fits.
Its only change is checkpoint resolution, including epochs1–4. Record full curves.
Total budget:70 real optimizer fits +8 synthetic; zero additional search.

## Portfolio decision evaluation

After the audit, specify one common cash-permitted, long-only allocation procedure,
risk estimator and cost assumptions for learned and baseline forecasts. Ranking
scores need a training-only calibration or a separately specified rank allocation
rule before economic comparisons. Do not force incomparable scores through an
expected-return optimizer. If required risk/cash data are missing, prepare the
smallest local collection request; do not silently invent cash yields.
