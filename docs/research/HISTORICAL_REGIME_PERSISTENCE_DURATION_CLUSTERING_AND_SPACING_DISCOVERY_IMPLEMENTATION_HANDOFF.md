# Campaign #47 Implementation Handoff — Historical Regime Persistence, Duration, Clustering, and Spacing Discovery

## Status

Frozen implementation handoff. This document does not authorize implementation or predictive outcome generation. Implementation may begin only after `docs/ITERA_CAMPAIGN_BOARD.md` records a separate Campaign #47 implementation GO.

## Governing specification

`docs/research/HISTORICAL_REGIME_PERSISTENCE_DURATION_CLUSTERING_AND_SPACING_DISCOVERY.md`

Specification freeze commit:

`bc715119d93d44b8991e02e4afb5a71d5e150c70`

The specification is authoritative. Any disagreement between this handoff and the specification fails closed in favor of the specification.

## Objective

Implement a deterministic, observation-only Campaign #47 research pipeline that tests whether regime age, previous-state duration, time since transition, and transition density contain incremental information about BTC forward return, move magnitude, realized volatility, or current-regime survival.

The implementation must not modify runtime behavior, regime labels, thresholds, signals, orders, execution, portfolio construction, NAV, exposure, dashboards, or model training.

## Authorized implementation surfaces after separate GO

Only the following new or updated surfaces may be used:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- the Campaign #47 specification;
- this Campaign #47 implementation handoff;
- one new observation-only module under `research/ml/validation/`;
- one Campaign #47 runner under `scripts/`;
- focused Campaign #47 tests under `tests/`;
- canonical outputs under `artifacts/historical_regime_structure/`.

Any additional file surface requires an explicit board transition before modification.

## Proposed implementation names

- module: `research/ml/validation/historical_regime_structure_discovery.py`;
- runner: `scripts/run_historical_regime_structure_discovery.py`;
- tests: `tests/test_historical_regime_structure_discovery.py`;
- output directory: `artifacts/historical_regime_structure/`.

Names are frozen by this handoff unless the board explicitly supersedes them before implementation.

## Source paths

```text
artifacts/full_historical_regime_state_sequence/btc_hourly_regime_state_manifest.json
artifacts/full_historical_regime_state_sequence/btc_hourly_regime_state_sequence.csv
artifacts/full_historical_regime_state_sequence/btc_hourly_regime_state_runs.csv
artifacts/full_historical_regime_state_sequence/btc_hourly_regime_transitions.csv
data/btcusd_3600s_2018-01-01_to_2025-12-31.csv
```

Preflight must hash and reconcile all governed source files before loading predictive outcomes. It must confirm the underlying BTC identity, timestamp bounds, row count, canonical state ordering, run coverage, transition ordering, and all source-manifest digests.

## Required module interface

The module should expose immutable contracts and side-effect-free functions sufficient to support focused testing. Exact internal structure may vary, but the public research surface must include equivalents of:

- frozen source-path and contract dataclasses;
- raw-byte SHA-256 helpers;
- strict JSON loading;
- governed source preflight;
- exact canonical state/run/transition readers;
- deterministic common-grid anchor construction;
- structural predictor construction;
- exact outcome construction;
- development-only scaling and regime fixed-effect encoding;
- OLS-HC3 estimation;
- directional-consistency evaluation;
- family-specific Benjamini-Hochberg adjustment;
- canonical candidate evaluation;
- deterministic JSON, CSV, Markdown, and manifest serialization;
- staged canonical publication with before/after source-digest verification.

All functions used in preflight must remain separate from predictive outcome construction so `--preflight-only` cannot accidentally calculate or inspect forward outcomes.

## Frozen anchor algorithm

1. Reconcile the canonical Campaign #46 state sequence to the BTC hourly source by exact timestamp.
2. Find the earliest non-`UNKNOWN` state row with all six trailing controls available.
3. Set that timestamp as the common-grid origin.
4. Generate scheduled anchors at exact 168-hour increments through the final source timestamp.
5. Include a scheduled timestamp only when the exact BTC and canonical state rows exist and all anchor-local required fields are available.
6. Never shift, replace, interpolate, or nearest-match an omitted scheduled timestamp.
7. Serialize the complete anchor inventory before candidate evaluation.
8. Split anchors into three contiguous near-equal partitions, assigning remainder rows to earlier partitions.

The anchor ordinal, timestamp, partition, current regime, current run identifier, current-state age, previous-run identifier and duration, previous transition identifier and timestamp, transition counts, controls, and all outcome availability fields must remain visible in canonical inventory outputs.

## Predictor formulas

### Current state age

```text
hours = exact integer hours(anchor_timestamp - current_run_start_timestamp)
value = log1p(hours)
```

The run start itself has age `0` and transformed value `0`.

### Previous completed state duration

Use the exact canonical duration of the immediately preceding run. Do not infer a previous run from labels alone. If no previous run exists, mark unavailable.

```text
value = log1p(previous_run_duration_hours)
```

### Hours since previous transition

Use the most recent canonical transition anchor at or before the current anchor.

```text
hours = exact integer hours(anchor_timestamp - previous_transition_timestamp)
value = log1p(hours)
```

At an anchor that is itself a transition timestamp, the value is `0`.

### Transition counts

Count canonical transition anchors in right-closed intervals:

```text
(anchor - window, anchor]
```

for windows of 24, 72, and 168 hours. Do not filter transition labels beyond the canonical source representation.

## Outcome formulas

For each horizon `h` in `24, 72, 168`:

### Directional return

```text
log(close[t+h] / close[t])
```

### Move magnitude

```text
abs(log(close[t+h] / close[t]))
```

### Realized volatility

Use every exact hourly BTC close from `t` through `t+h` and calculate:

```text
sqrt(sum(log(close[i] / close[i-1]) ** 2 for i in (t, t+h]))
```

Any missing exact hourly timestamp makes the volatility outcome unavailable.

### Current-regime survival

Set to `1` only when every canonical hourly regime label over `(t, t+h]` equals the anchor label. Set to `0` when any different canonical label occurs. Any missing exact hourly state timestamp makes the outcome unavailable.

Do not treat a return to the original label before `t+h` as survival.

## Controls and encoding

Use exactly the six BTC controls frozen in the specification.

For each chronological fit:

- calculate continuous means and population standard deviations on development rows only;
- require finite, strictly positive development standard deviation;
- transform development and evaluation rows with the frozen development statistics;
- derive current-regime fixed-effect levels from development rows only;
- sort levels lexicographically;
- omit the lexicographically first level as reference;
- fail the applicable fit if an evaluation row contains a non-`UNKNOWN` regime level absent from development.

For the pooled descriptive fit, derive scaling and fixed-effect levels from the complete pooled eligible sample and label the fit explicitly as pooled descriptive confirmatory.

No imputation, winsorization, clipping, thresholding, binning, interaction, or data-dependent transformation is allowed.

## Candidate inventory

Create candidates in deterministic order:

1. predictor order exactly as listed in the specification;
2. outcome-family order `R`, `M`, `V`, `S`;
3. horizon order `24`, `72`, `168`.

Candidate identifiers must be deterministic and should encode predictor, outcome family, and horizon without depending on result values.

Expected candidate count: `72`.

The candidate inventory must be serialized before estimator execution or result ranking.

## Estimation

For each candidate, construct:

- pooled complete sample;
- partition-2 evaluation fit using partition 1 as development;
- partition-3 evaluation fit using partitions 1 and 2 as development.

The design matrix is:

```text
intercept + standardized candidate predictor + six standardized controls + development-defined regime fixed effects
```

Use ordinary least squares and HC3 covariance. Record:

- sample count;
- design rank;
- predictor coefficient;
- HC3 standard error;
- two-sided normal p-value;
- 95% normal confidence interval;
- predictor and control scaling statistics;
- regime levels and reference level;
- explicit failure reason when unavailable or unrankable.

Family S remains a linear probability model. Do not clip fitted values or interpret them as calibrated probabilities.

## Support gates

Apply every frozen support gate before BH adjustment. At minimum, record explicit status values for:

- insufficient pooled support;
- insufficient partition support;
- missing outcome;
- predictor unavailable;
- predictor nonfinite;
- predictor zero variance;
- control zero variance;
- development-absent regime level;
- rank-deficient design;
- nonfinite coefficient;
- nonfinite or nonpositive HC3 standard error;
- estimator failure;
- direction inconsistent;
- multiplicity not met;
- supported research association.

Unrankable candidates must remain in JSON and CSV outputs with null statistical fields where appropriate.

## Multiplicity

Apply Benjamini-Hochberg independently to the rankable candidates inside each frozen outcome family. Use deterministic tie handling by raw p-value followed by candidate identifier.

The implementation must serialize:

- each family's complete candidate membership;
- rankable membership;
- raw rank order;
- adjusted q-values;
- family size and rankable size.

No candidate may move between families after results are inspected.

## Deterministic serialization

Canonical JSON must use:

- UTF-8;
- LF-only output;
- sorted object keys;
- compact deterministic separators where frozen by implementation;
- strict finite JSON values only;
- explicit `null` for unavailable values.

Canonical CSV must use:

- frozen column order;
- LF-only output;
- deterministic row order;
- deterministic serialization of lists and nested objects.

The canonical manifest must hash the first nine outputs and include an aggregate payload digest calculated before writing the manifest itself.

Generation must stage outputs in a temporary sibling directory and publish atomically only after all files and source immutability checks pass. The final output directory must not already exist or must be empty.

## Runner contract

The runner must support:

```text
python scripts/run_historical_regime_structure_discovery.py --preflight-only
```

Preflight output must state that predictive outcomes were not generated.

A later separately authorized canonical run may use:

```text
python scripts/run_historical_regime_structure_discovery.py
```

The runner must never mutate runtime state or production configuration.

## Focused test requirements

Focused tests must cover at least:

1. source identity and manifest reconciliation;
2. fail-closed missing and digest-mismatched sources;
3. exact common-grid anchor construction;
4. no nearest-row substitution;
5. chronological partition determinism;
6. current-state age conventions;
7. previous-run duration linkage;
8. previous-transition spacing conventions;
9. right-closed transition counts;
10. exact forward-return construction;
11. move-magnitude construction;
12. realized-volatility gap failure;
13. uninterrupted-regime-survival semantics;
14. development-only scaling;
15. development-defined fixed effects;
16. unseen evaluation regime failure;
17. OLS coefficient reconciliation;
18. HC3 covariance reconciliation with cross-platform numerical tolerance;
19. support-gate behavior;
20. directional-consistency behavior;
21. four independent BH families;
22. deterministic candidate identifiers and ordering;
23. null/failed candidate visibility;
24. strict JSON and LF-only serialization;
25. staged output publication;
26. source immutability before and after generation;
27. two-run byte-identical replay on synthetic fixtures;
28. runner preflight isolation from outcome construction.

Tests must not weaken source or support gates merely to pass synthetic fixtures.

## Required execution sequence after separate GO

1. implement module, runner, and focused tests only;
2. run focused tests;
3. run governed `--preflight-only` and stop on any discrepancy;
4. inspect preflight evidence without generating outcomes;
5. run canonical generation once;
6. preserve the first output set;
7. remove the output directory and run canonical generation again;
8. verify all ten files byte-identical;
9. rerun governed preflight;
10. inspect candidate support, family membership, coefficients, p-values, q-values, and direction rules;
11. run the full repository suite;
12. perform tracked scope review;
13. publish canonical artifacts only if every gate passes;
14. update the campaign board in a separate closure transition.

## Stop conditions

Stop immediately and do not generate or publish results when:

- any governed source digest or identity fails;
- state, run, transition, or BTC timestamps do not reconcile;
- exact anchors or outcomes cannot be constructed under the frozen rules;
- candidate count differs from 72;
- partition assignment is nondeterministic;
- any hidden imputation or nearest-row behavior is detected;
- family membership changes after result inspection;
- outputs differ across replay;
- governed source bytes change;
- focused or full-suite tests fail;
- tracked changes extend beyond authorized surfaces.

## Interpretation boundary

Campaign #47 may identify supported statistical associations. It cannot establish deployable alpha, economic usefulness, portfolio value, or a Core v1 improvement.

Any supported candidate must enter a separately frozen confirmation campaign. A later Core v1 incremental-value campaign may calculate Sharpe, CAGR, drawdown, turnover, and related economic metrics only for candidates that survive confirmation.