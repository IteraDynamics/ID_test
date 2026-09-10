# Incremental information and abstention — result

2026-09-10. Completed the fixed two-model,42-fit experiment and30 portfolio ledgers. Neither model meets the prespecified predictive and economic consistency rules. This closes this particular feature/target probe without promotion. These are inspected development years, not independent evidence against ML generally.

## What changing features add

Targets are five-session returns above BIL. Positive MSE skill means lower forecast error than the asset-specific training mean.

| Forecast | Full-period MSE skill | Excluding2020 MSE skill |
| --- | ---: | ---: |
| Raw residual Ridge | +1.031% | -1.035% |
| Calibrated residual Ridge | +0.529% | -1.267% |
| Raw residual GBM | +0.971% | -0.711% |
| Calibrated residual GBM | +0.024% | -0.421% |
| Same-fit static GBM | +0.222% | +0.354% |

Calibrated Ridge beats historical-mean MSE in2/7 years; calibrated GBM in4/7. GBM's static-feature counterfactual has lower MSE than its changing-feature forecast on both full and excluding2020 scopes. Ridge's full-period lift reverses outside2020. The static ablation freezes changing features to training asset means; it is not a separately retrained identity-only model, so it does not isolate every model-capacity effect.

Earlier-year OOS calibration sets Ridge's residual contribution to zero in2018,2019,2023,2024 and GBM's in2018,2019. Calibration is estimated only from the two inner years. Its failure to improve consistently is itself a result; we did not replace it after inspecting outer performance. These small and unstable aggregate improvements do not meet the declared consistency bar. They are not proof of zero conditional information or a causal attribution of performance to2020.

## Did abstention make the forecasts tradable?

Baseline execution:10bp per traded notional including BIL, next-session open. An asset must forecast more than40bp over BIL over five sessions to qualify, representing a conservative complete equity/BIL round trip. The same rule is applied to historical means. Maximum three25% risky slots, with risk scaling and BIL for unused slots.

| Policy | CAGR | Annualized CE | Maximum drawdown | Average risky exposure |
| --- | ---: | ---: | ---: | ---: |
| Calibrated GBM + gate | 2.16% | 1.72% | -16.59% | 11.35% |
| Calibrated Ridge + gate | 1.28% | 0.43% | -20.41% | 12.83% |
| Raw GBM + gate | 3.02% | 2.14% | -19.12% | 21.72% |
| Raw Ridge + gate | 3.24% | 2.10% | -20.41% | 20.25% |
| Historical mean + same gate | 1.05% | 0.95% | -8.33% | 3.57% |
| All BIL | 2.18% | 2.15% | -0.21% | 0% |
| Risk-managed equal weights | 5.48% | 4.44% | -19.71% | 73.60% |
| Historical mean without gate | 6.34% | 4.40% | -25.37% | 61.80% |

CE is annualized mean daily return minus1.5 times annualized daily variance. It is a descriptive risk-adjusted objective, not a realized annual payout. First/last calendar years are partial.

Calibrated GBM beats the gated mean on baseline CE, but trails BIL alone and equal weights. It beats gated mean annual CE in4/7 years, Ridge in3/7. GBM spends76.03% of rebalance signals entirely in BIL, Ridge71.90%, gated mean85.67%. Thus abstention genuinely executes; it is not forced investment under another name.

At25bp costs, the gate rises mechanically to100bp. Calibrated Ridge full-period CE improves to2.92%, despite higher transaction costs, because the policy avoids more trades. It still fails the full consistency rule. This is NOT a pure fee sensitivity with fixed trades: costs change both fees and eligibility. The extra-session delay likewise yields no passing calibrated model. All policy/scenario/year metrics remain in the evidence.

The fixed gate substantially suppresses the historical-mean control's exposure too. Its weak returns cannot be taken as proof that all forms of abstention are useful, or that this hurdle is optimal. The gate is conservative for retained positions; no incumbent-aware turnover optimization or forecast uncertainty estimate is implemented.

## Answer and next boundary

For these features, models and five-session target, changing market information has not shown sufficiently consistent incremental predictive value or economic value under the declared rules. A linear/nonlinear residual probe directly tested learning beyond historical means; this job did not refit neural networks or test a richer information source.

Do not launch another architecture or threshold sweep on these results. The next decision is whether to pursue a new information/economic hypothesis with existing free/local data, or pause this ETF return-forecasting line. A new hypothesis should specify why its information could forecast a tradable outcome before selecting a model. Prior negative experiments remain intact, and2025 remains reserved.

## Validation

11 tests passed, including planted incremental signal recovery, held-out outcome and overlap canaries, calibration clipping, no-trade and cutoff ties, plus existing fold/risk/ledger tests. Separate validation checks42 fit boundaries, source parity, hashes, reconstructed means/targets/calibration, byte-replayed forecast/economic summaries, reconciled daily contributions and cash, and exact representative ledger replay. Ungated controls reproduce the preceding study's NAV exactly.

Runner: `python -m research.ml_development.incremental --input-root <nine-ETF-input-directory> --output-dir <new-output-directory>`. Full forecasts, fits, calibration, weights, daily ledger and metrics are in the review package. No local rerun is needed. No raw inputs committed; Core/runtime/capital unchanged.
