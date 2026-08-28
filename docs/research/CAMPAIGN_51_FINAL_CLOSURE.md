# Campaign #51 Final Closure

## Final status

Campaign #51 is complete as a valid governed negative result.

The frozen question was whether previously supported BTC volatility and drawdown states condition the directional association of recent signed return.

The campaign tested exactly 12 preselected interaction candidates across development and validation. No candidate passed the frozen development gate, so none was eligible for validation support and the frozen shortlist is empty.

The untouched 2025 confirmation period was not analytically loaded and must remain untouched.

## Frozen design

Directional variables:

- trailing 24-hour signed log return;
- trailing 168-hour signed log return.

Conditioning states:

- trailing 24-hour realized volatility;
- drawdown from the trailing 168-hour close high.

Horizons:

- 24 hours;
- 72 hours;
- 168 hours.

Candidate count:

- `2 × 2 × 3 = 12`.

Frozen model:

`Y = beta0 + betaD * D_z + betaS * S_z + betaI * (D_z * S_z) + epsilon`

The interaction coefficient `betaI` was the primary estimand. Estimation used OLS with HC3 covariance, two-sided normal inference, and Holm correction across all 12 candidates separately within each stage.

## Governed lineage

- hypothesis-family selection: `11db395e117343e10ea836231b0903b982e9a674`
- frozen statistical specification: `c2f4770ac84e460a387ad2c341d7a4129034b720`
- implementation handoff: `ecc69384a4951928a88857809b8af54a9c7c1a6d`
- research core: `a0e4857c8582682d0f025085456f56e76e2c2d63`
- development/validation execution GO: `e9eba6f7141851934fbe6a31b4f5c999493d7ab8`
- governed runner correction: `4fb144de0ddd49dff68ac6b450e35384e49a31c5`
- runner-boundary tests: `5e87611edc352c29ec3bf9cd14c46674df37be96`

## Governed source

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- rows: `70,069`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- governed missing timestamps: `36`

Development/validation execution parsed close values only through `2024-12-31 23:00:00`.

Safety evidence from both governed runs:

- `holdout_loaded`: `false`
- `confirmation_enabled`: `false`
- `runtime_modified`: `false`

## Execution result

Two independent governed executions completed with `status: PASS`.

Both runs reported:

- candidate count: `12`
- development status counts: `DISCOVERY_NOT_SUPPORTED: 12`
- validation status counts: `VALIDATION_NOT_ELIGIBLE: 12`
- shortlist count: `0`
- predictors generated: `true`
- forward outcomes generated: `true`
- models fitted: `true`
- prices loaded through: `2024-12-31 23:00:00`
- holdout loaded: `false`
- confirmation enabled: `false`
- runtime modified: `false`

## Replay identity

The five canonical artifacts were byte-identical across both governed runs.

- candidate inventory: `06c29c8caddf56d9278c53971d7a014f8fb596d36435f74257af9ddee15d5386`
- development results: `ddfa49087995850cabf6dadbaf74038c12c6fe7954dce04fd2ec2176de51c774`
- validation results: `afc389e2b4283e94e396bce4ba4c0ffbce23d74f2e6b0d81301a28ed13c7e2d9`
- shortlist: `5d6088e94d033382d421c9ddb34b940d5a645a26cd15beada4b69ba2aa04acad`
- stage manifest: `0b332f2353202b88be841277c04f579bc988568deb869e6a5963ac48b0b48814`

## Interpretation

Campaign #51 did not establish that trailing 24-hour or 168-hour BTC return becomes directionally informative as a function of trailing 24-hour volatility or trailing 168-hour drawdown under the frozen design.

This is a valid negative research result, not an implementation failure.

The result does not negate Campaign #48's supported evidence that volatility and drawdown contain information about future movement magnitude and volatility. It only rejects this specific interaction-based directional-conditioning hypothesis family under the frozen Campaign #51 design.

## Permanent boundaries

Campaign #51 may not be reopened by changing candidates, formulas, horizons, support gates, standardization, covariance, multiplicity, pass rules, or signs after observing the result.

Because the shortlist is empty:

- no 2025 confirmation run is authorized or necessary;
- 2025 close values must remain analytically untouched for Campaign #51;
- no economic-value testing is authorized;
- no Core v1 comparison is authorized;
- no paper trading is authorized;
- no runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change is authorized.
