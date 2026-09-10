# Common cash-permitted portfolio diagnostic — 2026-09-10

## Finding

The fixed allocation diagnostic does not establish an ML advantage. All ten ML policies trail the historical-mean and risk-managed equal-weight controls on full-period CAGR and certainty equivalent (CE) under each of the three execution scenarios. No policy is promoted. This is descriptive evidence from inspected development data, not a significance test or a verdict on neural networks in general.

The adjusted BIL input passed manifest, schema, OHLC, calendar and finite-value checks: 2,789 common sessions, 2013-12-02 through 2024-12-31. There were zero model fits. Existing hashed forecasts feed 14 policies and 42 reconciled daily ledgers. Actual ledger dates are recorded in validation.json; the 2018–2024 calendar years have partial first/last years.

## Baseline economics

Costs are 10 basis points per unit of traded notional, including BIL, initial entry and final liquidation. Returns include adjusted ETF distributions. CE is annualized mean daily return minus 1.5 times annualized daily return variance (risk aversion 3). Turnover is cumulative one-way traded notional divided by contemporaneous NAV, not trades per year.

| Policy | CAGR | Annualized volatility | Maximum drawdown | Annualized CE | Cumulative turnover |
| --- | ---: | ---: | ---: | ---: | ---: |
| Historical mean | 6.34% | 13.22% | -25.37% | 4.40% | 8.01× |
| Risk-managed equal weights (`zero`) | 5.48% | 9.48% | -19.71% | 4.44% | 6.80× |
| Fixed 75% equal weights / 25% BIL | 5.88% | 9.64% | -19.71% | 4.79% | 6.50× |
| Rank Ridge | 5.39% | 12.93% | -25.86% | 3.58% | 49.63× |
| Raw GBM | 3.37% | 11.43% | -20.92% | 2.02% | 207.70× |
| Raw neural network | 1.40% | 11.96% | -22.01% | -0.03% | 170.45× |
| Rank neural network | 1.86% | 12.61% | -24.75% | 0.26% | 156.56× |
| Risk-scaled neural network | 2.95% | 11.37% | -22.12% | 1.62% | 190.39× |

Rank Ridge is described as the best ML result after observation, not selected for deployment. The complete evidence includes every policy, including fine-checkpoint MLP and momentum60.

At 25bp costs, rank Ridge CAGR falls to 4.27%, versus 6.16% for historical mean and 5.32% for risk-managed equal weights. Raw MLP becomes -2.26%. An extra session of execution delay does not reverse the control-versus-ML full-period conclusion.

Excluding 2020, rank Ridge CE is 5.00%, above risk-managed equal weights at 3.36%, but below historical mean at 5.94%. Rank Ridge beats historical mean annual CE in only 3/7 calendar years (4/7 versus equal weights). Excluding-year statistics omit 2020 daily observations; they do not invent a stitched equity curve, CAGR or drawdown.

## Design implications and limits

1. Cost-sensitive turnover is a concrete weakness. The learned policies trade substantially more than the controls. This does not prove that turnover alone explains their weakness.
2. A 10% forecast-volatility ceiling is not a realized-volatility guarantee. It uses a trailing 252-session covariance estimate with 50% diagonal shrinkage; several concentrated policies realize more than 10% volatility. Individual risky assets are capped at 25% at rebalances, with drift between them.
3. This is a fixed ranking-to-portfolio diagnostic. Every score policy starts with a 75% risky allocation, reduced only by the volatility rule. It does not test learned abstention, negative expected-return thresholds, probability calibration, turnover penalties or optimized cash allocation. Rank targets cannot be treated as expected returns without calibration.
4. The passive75 control deliberately omits volatility scaling. The zero-score policy provides the common-risk-rule equal-weight comparison; historical mean also uses that same rule.
5. BIL is a traded adjusted ETF proxy, not an assumption about interest credited on brokerage cash. Residual settlement cash earns zero. All nine assets enter the covariance calculation, including BIL.
6. The known-signal audit previously demonstrated that the fitting code can learn a strong planted signal. It did not prove that these market features, labels or allocation rules express the right economic task.

The next research question should isolate the incremental value of time-varying features over asset identity and historical means, and then test a prespecified cost-aware abstention rule using calibrated return forecasts. More architectures or a search for the best threshold on these results would not resolve that question. Any such experiment must retain these results and use chronological training-only selection; 2025 remains reserved. This job does not run or select those additional experiments.

## Validation and reproducibility

17 tests cover the existing accounting engine plus ties, full covariance risk limits, future-price isolation, round-trip costs and BIL/delayed execution. Validation separately checks output hashes, contributions, cash/exposure reconciliation, target risk ceilings, byte-identical weight/metric replay, an exact representative ledger replay and lower CAGR for every policy at higher costs. Full validation is in the evidence directory.

Run from this branch with the existing design-audit forecast cache and nine adjusted ETF input files plus manifests:

```powershell
uv run --locked --python 3.12 python -m research.ml_development.portfolio --input-root <input-directory> --cached artifacts/ml_design_audit_20260910 --output-dir artifacts/ml_portfolio_diagnostic_replay
if ($LASTEXITCODE -ne 0) { throw 'Portfolio diagnostic failed' }
```

The output directory must be new. No local rerun is needed to review the attached completed results. No Core, runtime, capital or reserved-2025 changes.
