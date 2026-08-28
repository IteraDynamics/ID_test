# Campaign #51 Statistical Specification

## Status and purpose

This document freezes the statistical design for Campaign #51 before any Campaign #51 predictor values, forward outcomes, model fits, coefficients, p-values, rankings, shortlist decisions, confirmation results, or economic results are generated.

Campaign #51 asks:

> Does the association between recent signed BTC return and subsequent directional return differ as a function of recent realized volatility or drawdown state?

This is a research-only conditional-association study. It is not a trading-strategy backtest and authorizes no runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Governed lineage

- Campaign #48 closure: `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`
- Campaign #48 canonical publication: `fd7ee01`
- Campaign #51 planning charter: `59359493787dcac855063debbda8a76895a55378`
- Campaign #51 source-and-variable inventory: `5bdef3783975902516bac49ca23b00b023d108f9`
- Campaign #51 hypothesis-family selection: `11db395e117343e10ea836231b0903b982e9a674`

## Governed source

Only this source is permitted:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- rows: `70,069`
- schema, in exact order: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- first timestamp: `2018-01-01 00:00:00`
- last timestamp: `2025-12-31 00:00:00`
- exact governed missing timestamp inventory: the 36 timestamps frozen by Campaign #48 amendment `d9fc7e7103a5033a9dbbe06b7abf93aea27d863b`

Only `timestamp` and `close` may enter Campaign #51 calculations.

No interpolation, filling, resampling, nearest-row matching, as-of matching, shifting, synthetic bars, timestamp repair, source substitution, or source acquisition is permitted.

## Frozen stages

- development: `2018-01-01 00:00:00` through `2022-12-31 23:00:00`
- validation: `2023-01-01 00:00:00` through `2024-12-31 23:00:00`
- untouched confirmation: `2025-01-01 00:00:00` through `2025-12-31 00:00:00`

Every 2025 close value is forbidden from analytical loading until a separate confirmation GO is recorded after development and validation produce a non-empty frozen shortlist.

## Anchor grid and exact-window rules

The anchor grid is the existing Campaign #48 168-hour grid:

- origin: `2018-01-08 00:00:00`
- spacing: exactly 168 hours
- anchors are evaluated in chronological order

A predictor is available at anchor `t` only when every exact hourly timestamp required from `t - 168h` through `t`, inclusive, exists in the governed source.

A forward outcome at horizon `h` is available only when the exact timestamp `t + h` exists and lies inside the same frozen stage as anchor `t`.

No anchor may borrow a predictor timestamp from after the anchor. No outcome may cross a stage boundary. Missing exact timestamps make the affected predictor or outcome unavailable; they are never repaired.

## Directional variables

For close price `C_t`:

### Trailing 24-hour signed log return

`D24_t = ln(C_t / C_{t-24h})`

### Trailing 168-hour signed log return

`D168_t = ln(C_t / C_{t-168h})`

## Conditioning movement states

Let hourly log return be `r_j = ln(C_j / C_{j-1h})`.

### Trailing 24-hour realized volatility

`V24_t = sqrt(sum(r_j^2))` over the 24 exact hourly returns ending at `t`.

### Drawdown from trailing 168-hour close high

`DD168_t = C_t / max(C_{t-168h}, ..., C_t) - 1`

`DD168_t` is non-positive. More negative values represent deeper drawdown.

## Forward outcome

For horizon `h` in `{24, 72, 168}` hours:

`Y_{t,h} = ln(C_{t+h} / C_t)`

This is directional forward BTC log return. No absolute-return, volatility, hit-rate, binary-direction, economic-return, or strategy outcome belongs to Campaign #51.

## Candidate inventory

Exactly 12 candidates:

- directional variable in `{D24, D168}`
- movement state in `{V24, DD168}`
- horizon in `{24h, 72h, 168h}`

Canonical candidate key:

`<directional_variable>__x__<movement_state>__fwd_log_return_<horizon>h`

Candidate order is lexicographic by the frozen directional-variable order above, then movement-state order above, then horizon order `24, 72, 168`.

No other directional variable, state variable, transformation, horizon, target, control, threshold, regime, or interaction is permitted.

## Development-only transformations

For each base variable separately, compute the arithmetic mean and population standard deviation (`ddof=0`) using candidate-complete development anchors for that candidate and horizon.

For directional variable `D` and movement state `S`:

`D_z = (D - mean_dev(D)) / sd_dev(D)`

`S_z = (S - mean_dev(S)) / sd_dev(S)`

The same frozen development means and population standard deviations must be reused unchanged in validation and, if later authorized, confirmation.

The interaction is formed only after standardization:

`I = D_z * S_z`

No winsorization, clipping, ranking, quantiling, thresholding, sign conversion, nonlinear transformation, residualization, or stage-specific restandardization is permitted.

## Model equation

For each candidate and stage, fit OLS with intercept:

`Y = beta0 + betaD * D_z + betaS * S_z + betaI * (D_z * S_z) + epsilon`

The primary estimand is `betaI`, the interaction coefficient.

Interpretation:

- `betaD` is the directional-return slope when the standardized state equals zero, meaning at the development-stage mean of the state.
- `betaS` is the state slope when the standardized directional variable equals zero.
- `betaI` is the change in the directional-return slope associated with a one-development-standard-deviation increase in the movement state.

For `DD168`, a positive standardized increase means movement toward a shallower drawdown because the raw variable becomes less negative. Interpretation must preserve that orientation.

The main effects must remain in every model. An interaction-only regression is prohibited.

## Estimation and inference

- estimator: ordinary least squares
- covariance: HC3 heteroskedasticity-consistent covariance
- test: two-sided normal test of `H0: betaI = 0`
- confidence interval: two-sided 95% normal interval for `betaI`
- numerical output: finite double-precision values

No Newey-West/HAC covariance, clustering, bootstrap, permutation test, fixed effects, regime controls, additional covariates, regularization, model selection, or alternative estimator is permitted.

The 168-hour anchor spacing is the sole ex ante mechanism for limiting outcome overlap. The same anchor grid is used for all horizons; no horizon-specific denser grid is permitted.

## Rankability and support gates

A candidate-stage fit is rankable only when all of the following hold:

- the exact source identity and schema pass;
- candidate-complete observations meet the stage/horizon minimum below;
- both base predictors have finite development means and finite strictly positive development population standard deviations;
- all transformed predictors and outcomes are finite;
- the design matrix has full column rank 4;
- the fitted interaction coefficient is finite;
- the HC3 interaction standard error is finite and strictly positive;
- the raw two-sided interaction p-value is finite and in `[0,1]`.

Minimum candidate-complete observations:

| Stage | 24h | 72h | 168h |
|---|---:|---:|---:|
| Development | 220 | 220 | 219 |
| Validation | 90 | 89 | 89 |
| Confirmation | 40 | 39 | 39 |

These gates were selected before outcome generation and are below the timestamp-only maxima:

- development: `248, 248, 247`
- validation: `104, 103, 103`
- confirmation: `51, 50, 50`

A failed gate remains visible with a deterministic failure status and is not silently dropped.

## Multiplicity correction

Within each stage, apply Holm's step-down family-wise error correction to the 12 raw two-sided interaction p-values.

The multiplicity family size remains exactly 12 even when one or more candidates are unrankable. Unrankable candidates cannot be supported and do not reduce the correction burden.

Ties are broken by canonical candidate order.

No separate multiplicity families by directional variable, movement state, or horizon are permitted.

## Development decision rule

A candidate is `DISCOVERY_SUPPORTED` only when:

- it is rankable in development; and
- its development Holm-adjusted interaction p-value is at most `0.05`.

The interaction sign is not prespecified. Campaign #51 is sign-agnostic because the economically plausible direction differs by directional variable, conditioning state, and horizon.

All other rankable candidates are `DISCOVERY_NOT_SUPPORTED`.

Only `DISCOVERY_SUPPORTED` candidates may be eligible for validation support.

## Validation decision rule

All 12 candidates are still fitted and multiplicity-adjusted in validation for a complete, deterministic record.

A candidate is `VALIDATION_SUPPORTED` only when:

- it was `DISCOVERY_SUPPORTED`;
- it is rankable in validation;
- the validation interaction coefficient has the same non-zero sign as the development interaction coefficient;
- its validation Holm-adjusted interaction p-value is at most `0.10`; and
- the absolute validation interaction coefficient is between `0.25` and `4.00` times the absolute development interaction coefficient, inclusive.

The coefficient-ratio rule is a prespecified compatibility guard against sign-consistent but economically incomparable collapse or explosion. Both coefficients use the same development-frozen standardization.

A rankable validation candidate without development support is `VALIDATION_NOT_ELIGIBLE`. A development-supported candidate failing any validation replication condition is `VALIDATION_NOT_SUPPORTED`.

The frozen confirmation shortlist consists exactly of `VALIDATION_SUPPORTED` candidates.

## Empty-shortlist rule

If the development/validation shortlist is empty:

- Campaign #51 closes as a valid negative result;
- no 2025 analytical values may be loaded;
- no confirmation run is authorized;
- no economic test or Core v1 comparison follows.

## Confirmation rule

Confirmation is not authorized by this specification. It requires a later board-recorded GO after a non-empty frozen shortlist is published.

If separately authorized, all 12 candidates must be represented in the confirmation record and Holm adjustment must retain family size 12. Only frozen-shortlist candidates may be labeled confirmation-eligible.

A shortlisted candidate is `CONFIRMATION_SUPPORTED` only when:

- it is rankable in confirmation;
- the confirmation interaction coefficient has the same non-zero sign as both development and validation;
- its confirmation Holm-adjusted interaction p-value is at most `0.05`; and
- the absolute confirmation interaction coefficient is between `0.25` and `4.00` times the absolute development interaction coefficient, inclusive.

Failure of confirmation cannot trigger method revision inside Campaign #51.

## Determinism, replay, and fail-closed behavior

Any later implementation must:

- validate the exact governed source before analytical loading;
- reject tracked-worktree modifications and unexpected branch or governance identity;
- reject any analytical loading of 2025 during development/validation;
- produce canonical UTF-8/LF JSON, CSV, and Markdown outputs with stable ordering and strict finite-number serialization;
- emit exact source, specification, implementation, execution-GO, and repository commit identities;
- execute development/validation twice into previously nonexistent directories;
- require identical canonical file sets, byte counts, and SHA-256 hashes across both runs;
- fail closed before partial canonical publication if any source, schema, timestamp, window, rankability, serialization, or replay check fails.

At minimum, later canonical development/validation artifacts must include:

1. source/preflight manifest;
2. candidate inventory;
3. development-standardization parameters;
4. development results;
5. validation results;
6. frozen shortlist;
7. stage manifest;
8. human-readable report.

Exact filenames and serialization contracts belong to a later implementation handoff and must be frozen before execution.

## Prohibited post-outcome changes

After any Campaign #51 outcome is generated, the following may not change inside Campaign #51:

- source or source treatment;
- stage boundaries;
- anchor origin or spacing;
- predictors, states, outcomes, or horizons;
- transformations or standardization;
- model equation or controls;
- covariance estimator or test;
- support gates;
- multiplicity family or correction;
- coefficient-sign or compatibility rules;
- shortlist or confirmation rules.

Any materially different design must become a new campaign.

## Interpretation boundary

Statistical support would establish only a reproducible conditional association under this frozen historical design.

It would not establish deployable alpha, economic value, transaction-cost robustness, timing value, sizing value, portfolio improvement, superiority to Core v1, production readiness, or permission to alter runtime behavior.
