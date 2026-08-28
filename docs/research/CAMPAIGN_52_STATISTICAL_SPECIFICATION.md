# Campaign #52 Frozen Statistical Specification

## Status

Frozen pre-outcome statistical and counterfactual specification. No Campaign #52 canonical targets, counterfactuals, trades, exposures, NAVs, performance metrics, rankings, or support decisions were generated or inspected while drafting this record.

Implementation remains on HOLD until a source-only identity preflight freezes the missing non-BTC source hashes and verifies the calendar contract.

## Research question

Does canonical Core v1 derive material value from the authentic chronological alignment of its sleeve-level pre-execution signed target exposures, beyond what can be explained by static composition or chronology-destroyed controls replayed through identical execution mechanics?

## Canonical repository reference

- repository: `IteraDynamics/ID_test`
- branch: `agent/campaign-50-holdout-first-alpha-research-planning`
- frozen repository reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- scenario: `baseline_40_35_15_10`
- sleeve weights:
  - BTC 1H trend: `0.10`
  - BTC 4H trend: `0.10`
  - ETH 1H trend: `0.10`
  - ETH 4H trend: `0.10`
  - BTC 1H hedge: `0.05`
  - ETH 1H hedge: `0.05`
  - SPY 1D equity: `0.175`
  - QQQ 1D equity: `0.175`
  - GLD 1D gold: `0.15`
- total portfolio weights: trend `0.40`, equity `0.35`, gold `0.15`, hedge `0.10`, mean reversion `0.00`

No allocation, sleeve, strategy, threshold, regime, order, execution, or runtime change is permitted.

## Source contract

Authorized source paths:

- `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/SPY_1D.csv`
- `data/QQQ_1D.csv`
- `data/BIL_1D.csv`
- `data/GLD_1D.csv`

Known BTC identity:

- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- bytes: `4,792,028`
- rows: `70,069`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`

The ETH, SPY, QQQ, BIL, and GLD SHA-256, byte-count, row-count, schema, timestamp coverage, and missing-timestamp identities must be produced by a source-only preflight before implementation authorization. Any mismatch closes the gate fail-closed; no substitution or repair is permitted.

## Cost and execution contract

Frozen settings:

- crypto taker fee: `0.0006`
- equity/gold fee: `0.0001`
- crypto base slippage: `3.0` bps
- crypto slippage volatility factor: `50.0`
- crypto cooldown: `2` native bars
- equity/gold cooldown: `1` native bar
- rebalance threshold: `0.02`
- equity/gold execution settings remain exactly those in the frozen repository reference
- BIL close-to-close return remains the idle-cash yield proxy for equity and gold sleeves
- initial portfolio NAV: `100000.0`
- yearly walk-forward folds and chronological stitching remain canonical

## Retrospective stages

Because Core v1 research already inspected 2025, Campaign #52 makes no untouched-2025 claim.

- development: `2020-01-01` through `2022-12-31`
- validation: `2023-01-01` through `2025-12-31`
- prospective confirmation: not part of the retrospective campaign; any future confirmation requires a separately opened stage using data unavailable when this specification was frozen

Controls are constructed separately within development and validation except the static target values, which are estimated from development only and reused unchanged in validation.

No target block, displacement value, or permutation may cross a stage boundary.

## Intervention object and serialization

For every active sleeve and native decision timestamp, capture the signed target exposure implied by canonical `StrategyIntent` before cooldown, rebalance threshold, fills, fees, slippage, spread, cash-yield application, and mark-to-market.

Canonical fields:

- stage
- fold
- timestamp in UTC, ISO `YYYY-MM-DDTHH:MM:SSZ`
- sleeve label
- asset
- native timeframe
- strategy id
- action
- desired exposure fraction
- signed target exposure
- canonical sequence number

Numeric serialization uses decimal text with 12 digits after the decimal point. Rows are sorted by stage, fold, sleeve canonical order, timestamp, and sequence number. UTF-8 CSV uses LF line endings and a fixed header.

## Capture and replay equivalence gate

Before any counterfactual execution:

1. capture-only execution must reproduce canonical trades, fees, slippage, spread, realized exposure, sleeve equity, fold fund NAV, and stitched NAV;
2. replay of the unmodified captured target stream must reproduce the capture-only execution;
3. canonical artifact bytes must be identical across two independent runs, except where the implementation specification later freezes exact numeric CSV equivalence instead of byte identity;
4. any mismatch is a HOLD; counterfactual results may not be generated or inspected.

## Frozen counterfactual family

Exactly 20 controls are selected.

### Static control — 1

For each sleeve, compute the arithmetic mean of its signed canonical development-stage target exposure across all native decision timestamps.

- one fixed signed target per sleeve
- estimated from development only
- rounded only at canonical serialization
- reused unchanged in validation
- continuously supplied at every native decision timestamp
- unchanged execution rules determine whether a trade occurs

Control id: `static_dev_mean_target`

### Positive displacement controls — 3

Wall-clock lags:

- `24h`
- `168h`
- `672h`

For each sleeve, target at time `t` equals its canonical target at `t - lag` only when that source timestamp exists within the same stage and fold. Otherwise the supplied target is `0.0`.

- no wraparound
- no cross-stage or cross-fold carry
- no nearest matching
- no resampling or forward fill beyond the canonical target timestamp mapping

Control ids:

- `lag_24h`
- `lag_168h`
- `lag_672h`

### Deterministic block permutations — 16

- block duration: `28` consecutive wall-clock days
- partition origin: each stage/fold start
- only complete blocks are permuted
- incomplete terminal block remains in its original terminal location
- within-block order and native timestamps relative to block start are preserved
- blocks remain within the same stage and fold
- all sleeves use the same block permutation within a stage/fold so cross-sleeve temporal coordination is preserved while market alignment is destroyed

Permutation seeds are derived as the first 16 unsigned 64-bit integers from:

`SHA256("campaign52|block28d|perm|NN")`

where `NN` is zero-padded `01` through `16`, taking the first 16 hexadecimal characters of each digest. The seeded Fisher-Yates permutation is applied to complete block indices. Canonical order is `perm_01` through `perm_16`.

No seed or permutation may be rejected or replaced after outcomes are generated.

## Primary endpoints

Calculated from daily end-of-day stitched portfolio NAV for each stage:

1. annualized geometric return;
2. maximum drawdown magnitude;
3. Calmar ratio.

Higher is better for return and Calmar. Lower absolute drawdown magnitude is better.

## Secondary endpoints

- annualized volatility
- Sharpe ratio using zero excess-return benchmark
- worst 21-calendar-day return
- worst 63-calendar-day return
- longest drawdown duration in calendar days
- median drawdown-recovery duration
- total fees plus slippage plus spread
- turnover notional divided by average NAV
- final equity

Secondary endpoints are descriptive and cannot rescue failure of the primary rule.

## Inferential unit and uncertainty

The inferential series is paired daily log return: canonical minus each counterfactual on common daily timestamps.

For each stage/control pair:

- use a deterministic moving-block bootstrap;
- block length: `21` consecutive daily observations;
- bootstrap replications: `10,000`;
- seed: first unsigned 64-bit integer from `SHA256("campaign52|bootstrap|stage|control_id")`;
- sample blocks with replacement until the original stage length is reached, then truncate;
- report the two-sided 95% percentile interval for mean daily log-return difference.

Drawdown and Calmar are evaluated directly on the observed stage NAV paths and through the same bootstrapped paired daily-return paths.

## Multiplicity

The confirmatory family contains all 20 controls separately within each stage.

For the mean daily log-return superiority test, apply Holm step-down adjustment across all 20 one-sided p-values within the stage. Family size remains 20 if a control is unrankable; unrankable controls receive adjusted p-value `1.0`.

No control may be removed from the family after outcomes are inspected.

## Development support

A control is development-separated when all are true:

- canonical annualized geometric return exceeds the control;
- canonical maximum drawdown magnitude is at least `1.00` percentage point smaller than the control, or canonical Calmar is at least `0.10` higher;
- one-sided Holm-adjusted p-value for positive mean daily log-return difference is `<= 0.10`.

The campaign advances to validation interpretation only if at least:

- `2` of `3` lag controls are development-separated; and
- canonical exceeds the median of the 16 block permutations on all three primary endpoints; and
- canonical exceeds the static control on at least `2` of `3` primary endpoints.

Failure closes Campaign #52 as a development negative without validation-based support claims.

## Validation support

Chronological state value is supported only if all are true:

1. at least `2` of `3` lag controls are validation-separated under the same separation rule, using Holm-adjusted `p <= 0.10`;
2. canonical validation annualized return, drawdown, and Calmar each beat the median of the 16 validation block permutations;
3. canonical ranks in the favorable top `3` of `17` among canonical plus 16 permutations for at least `2` of the `3` primary endpoints;
4. canonical beats the static control on at least `2` of `3` primary endpoints;
5. the direction of canonical-minus-control differences for the three lag controls is not materially reversed from development on more than one primary endpoint per lag.

## Interpretation categories

### Chronological state value

Validation support rule passes and canonical also beats the static control on annualized return plus at least one capital-protection endpoint.

### Capital-protection value

Validation support rule passes for drawdown/Calmar structure, but canonical annualized return does not exceed the static control by at least `1.00` percentage point. Canonical must still improve maximum drawdown by at least `2.00` percentage points or Calmar by at least `0.15` versus static.

### Static-allocation value

Static control is within:

- `1.00` percentage point annualized return;
- `2.00` percentage points maximum drawdown;
- `0.10` Calmar;

of canonical in validation, and the chronological support rule fails.

### Negative result

None of the above categories is established, or development gate fails.

These categories are mutually resolved in the order listed above.

## Deterministic artifacts

Required canonical artifacts include:

- source identity manifest
- reference configuration manifest
- canonical target stream per stage/fold/sleeve
- capture-equivalence manifest
- unmodified replay-equivalence manifest
- counterfactual transformation manifest
- target stream for every control
- trade/cost/exposure artifacts for every reference and control
- sleeve and fund NAV artifacts
- daily metrics table
- bootstrap and multiplicity table
- stage decision manifest
- SHA-256 manifest for every canonical file

All JSON is canonical sorted-key compact JSON with LF termination. All CSV uses fixed headers, canonical row order, UTF-8, and LF termination.

## Prohibitions

- no source substitution, repair, interpolation, or acquisition
- no strategy, regime, threshold, cooldown, cost, weight, fold, order, or execution change
- no negative displacement
- no cross-stage or cross-fold transformation
- no outcome-based seed, block, offset, metric, margin, or control selection
- no 2025 holdout claim
- no deployment, paper trading, or runtime action

## Current decision

Statistical specification is frozen, but implementation is not authorized.

Next authorized deliverable should be a source-only identity and calendar preflight that reads metadata and timestamps only, freezes the missing source hashes and calendar viability, and keeps all target, execution, NAV, and metric flags false.
