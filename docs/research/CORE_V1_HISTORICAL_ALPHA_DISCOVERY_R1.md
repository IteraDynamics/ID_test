# Core v1 Historical Alpha Discovery — R1 Source Governance Amendment

## Status

Frozen source-governance amendment for Campaign #43-R1.

This amendment is committed after the original governed hourly artifact failed closed for lacking an exact `close` field and before any predictive result generation or inspection.

## Scope

This amendment changes only the governed BTC hourly price source for Campaign #43-R1.

All other decisions in `docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY.md` remain unchanged, including:

- candidate inventory and leakage exclusions;
- episode and event-family anchors;
- homogeneous-only family aggregation;
- exact forward outcomes;
- horizons `2`, `6`, `24`, `72`, and `168` hours;
- chronological folds;
- support gates;
- evidence states;
- deterministic ranking;
- canonical outputs;
- replay and fail-closed requirements;
- prohibition on runtime, strategy, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, transaction-cost, deployable-alpha, or strategy-recommendation changes.

## Superseded source selection

The original specification selected:

`artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`

with SHA-256:

`36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7`

Observation-only inspection established that this artifact contains model prediction fields rather than an exact BTC `close` field. The governed preflight therefore failed closed as required. No predictive outcomes, candidate metrics, rankings, canonical result artifacts, or alpha claims were generated or inspected.

The source remains part of the audit record but is not a valid price source for Campaign #43-R1.

## Newly governed BTC hourly price source

### Provisioning class

Externally provisioned local research input. The file bytes are intentionally not stored in Git.

The file must exist at the following repository-relative local path:

`data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`

### Immutable identity and required evidence

- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- row count: `70,069`
- exact ordered schema: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- first timestamp: `2018-01-01 00:00:00`
- last timestamp: `2025-12-31 00:00:00`
- timestamp convention: timezone-naive exact hourly labels
- required price field: exact column `close`

### Numeric and structural requirements

The governed source must satisfy all of the following:

- every timestamp parses successfully;
- timestamps are strictly increasing;
- duplicate timestamps are absent;
- timestamps are aligned to exact hours;
- `open`, `high`, `low`, `close`, and `volume` are finite;
- `open`, `high`, `low`, and `close` are strictly positive;
- `volume` is nonnegative;
- OHLC relationships are internally consistent;
- the file identity, byte count, row count, schema, timestamps, and numeric evidence remain unchanged before and after generation.

Any disagreement fails closed.

## Gap evidence and exact reconciliation rule

Observation-only source inspection found `14` timestamp discontinuities containing `30` missing hourly timestamps. The largest discontinuity is a `16`-hour elapsed interval containing `15` missing timestamps.

These source-level gaps do not authorize interpolation, filling, resampling, nearest-row matching, as-of matching, cadence compression, inferred timestamps, or alternate price substitution.

Price matching remains exact timestamp matching only, as frozen in the original specification.

An observation is unavailable for a horizon unless its anchor and every exact hourly timestamp through that horizon exist.

Pre-result coverage reconciliation established:

- `122` governed episode observations;
- `122/122` episode anchors present;
- `14` governed event-family observations;
- `14/14` family anchors present;
- zero unavailable episode observations at horizons `2`, `6`, `24`, `72`, and `168` hours;
- zero unavailable family observations at horizons `2`, `6`, `24`, `72`, and `168` hours.

The unrelated source gaps therefore do not affect any currently governed Campaign #43-R1 observation.

## Fail-closed preflight requirements

Predictive result generation remains prohibited until implementation validates all of the following:

1. the local file exists at the governed repository-relative path;
2. SHA-256 matches exactly;
3. byte count matches exactly;
4. row count matches exactly;
5. ordered schema matches exactly;
6. first and last timestamps match exactly;
7. timestamp parsing, ordering, uniqueness, and hour alignment pass;
8. numeric finiteness and sign constraints pass;
9. OHLC consistency passes;
10. all governed episode and family anchors reconcile;
11. exact hourly coverage through each frozen horizon reconciles;
12. the source identity remains unchanged before and after generation.

No automatic search for alternate files is authorized. No fallback source is authorized. No field substitution is authorized.

## Required focused-test additions

Focused tests must additionally cover at least:

- correct externally provisioned local source succeeds;
- missing local source fails closed;
- hash mismatch fails closed;
- byte-count mismatch fails closed;
- row-count mismatch fails closed;
- schema or column-order mismatch fails closed;
- missing exact `close` fails closed;
- duplicate or non-increasing timestamp fails closed;
- malformed OHLC evidence fails closed;
- a source gap outside all governed outcome windows does not invalidate unaffected observations;
- a missing timestamp inside a required outcome window marks that observation unavailable;
- no interpolation, filling, resampling, nearest-row, as-of, or alternate-field behavior occurs.

Synthetic temporary fixtures should be used for focused tests where possible. The external market-data file must not be added to Git merely for test execution.

## R1 authorization boundary

Campaign #43-R1 is authorized only for governance-document changes, preflight implementation changes, focused tests, preflight execution, and later deterministic historical result generation after all acceptance gates pass.

No predictive result generation is authorized by this amendment alone.
