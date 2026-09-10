# Incremental information and cost-aware abstention — 2026-09-10

Exploratory development revision, recorded before results. Eight existing ETFs plus adjusted BIL; all source hashes verified. No 2025, production or capital usage. Previously inspected 2018–2024 remain development years. No significance or independent-confirmation claim.

Question: do changing features improve forecasts beyond per-asset historical averages, and does that improvement justify trading after costs?

## Fixed design

Target: asset five-session next-open return minus the matching BIL five-session return. For each training fold, subtract that asset's training mean excess return. Predict the residual using existing eight summary features plus eight identity flags. Ridge alpha100 and depth2 GBM use the existing fixed settings. Two models are enough for a linear/nonlinear information probe; this does not retest or rule out neural networks. No architecture search.

Annual outer years2018–2024. Each outer year uses two prior inner years with training labels strictly before validation signal and inner validation labels strictly before outer signal. Use daily training and weekly validation. Fit42 models total:2 models ×7 years ×(2 inner+1 outer). No performance-driven additional fits. Check synthetic functionality without consuming real fits.

Calibrate each model's residual amplitude on concatenated inner OOS residuals only: slope=sum(predicted_residual*realized_residual)/sum(predicted_residual²), clipped[0,1], zero if denominator zero. No intercept. Outer forecast=outer training asset mean + slope*outer residual prediction. Also retain uncalibrated forecasts to reveal whether calibration suppresses useful or harmful information. No threshold search.

For a same-fit static-feature ablation, replace the eight changing features with the corresponding training asset means while retaining identity. Apply the same inner-derived slope. This is a counterfactual feature-freezing diagnostic, not a separately fitted capacity-matched model. A full forecast must improve on both the historical mean and this static forecast before attributing useful lift to changing features.

## Allocation

Compare mean, raw/calibrated/static forecasts for both models, plus risk-managed equal weights, all-BIL, and mean without abstention:10 policies. At each weekly signal, forecasts are expected excess return over BIL. For gated policies accept only assets with forecast >4×one-way cost, representing a conservative complete risky-asset/BIL round trip. Choose at most three qualifying assets,25% each; split cutoff ties fairly. Unused allocation goes to BIL; zero qualifying assets means all BIL. Gate applies also to existing holdings, deliberately conservative. It is not a full turnover optimizer or an uncertainty bound. No learned probability claims.

Keep prior252-session nine-asset covariance,50% diagonal shrinkage,10% forecast-volatility ceiling, next-session open,25% risky-asset cap at rebalance, and reconciled daily ledger. Forecast risk is not guaranteed realized risk. Baseline10bp and stress25bp per traded notional (including BIL), plus extra-session execution delay at10bp. Gate responds mechanically to each scenario's specified costs; no selecting costs from results. Final eligible signal liquidates rather than initiating an unobserved holding period. Settlement cash earns zero.

## Interpretation rules

Prediction: calibrated full MSE must be below mean and same-fit static on all and excluding2020 scopes, and below mean in at least4/7 years. Report raw results, residual correlations, inner calibration slopes, yearly and per-asset errors even if this fails.

Economics: calibrated policy CE (annualized mean minus1.5×annualized variance) must exceed identically gated mean and risk-managed equal weights on all and excluding2020 in every scenario, and beat gated mean CE in at least4/7 baseline years. These are descriptive consistency rules, not statistical tests. Report CAGR, drawdown, volatility, turnover, cash, asset contributions and decision coverage for all policies. No stitched excluding-year path statistics. No candidate promotion based on this job.

If neither model meets both rules, retain the negative result and stop this feature/target probe. A different information source or economic hypothesis would require a new bounded proposal; do not respond with an unrecorded parameter sweep.
