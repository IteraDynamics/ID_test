# Campaign #52 Development-Only Execution Procedure

## Status

Procedure-only governance record. This document defines the exact development-stage execution sequence for Campaign #52 against the frozen statistical specification and the governed-source capture/replay equivalence PASS.

This record does **not** authorize implementation, control generation, replay, performance calculation, bootstrap inference, multiplicity adjustment, ranking, or any development or validation outcome inspection.

## Governing references

- frozen Core reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- frozen statistical specification: `14a96b4078eec516570fce0c289baa061398a995`
- source/calendar evidence: `bd2af6c11991a637510122bdb4a3300b9653be14`
- governed-source equivalence PASS evidence: `0db3875d2c181f65b41e06145825f7d5363226e4`
- governed equivalence runner performance correction: `0da89d7af340ca8bdb629ce29ee09cfbb683f971`
- scenario: `baseline_40_35_15_10`
- development stage only: `2020-01-01` through `2022-12-31`

The validation stage `2023-01-01` through `2025-12-31` remains inaccessible to the development runner and must not be read, transformed, replayed, measured, ranked, summarized, or disclosed.

## Purpose

The development run will test whether the authentic chronological target stream is separated from exactly 20 frozen controls under identical execution mechanics. The run is observation-only, deterministic, replay-safe, stage-isolated, and fail-closed.

The development runner must reuse the canonical target artifacts produced by the governed equivalence PASS. It must not rerun canonical strategy modules or regenerate canonical intents.

## Required input roots

The runner accepts one governed equivalence artifact root, defaulting to:

`artifacts/campaign52_governed_equivalence`

Required inputs:

- `equivalence_manifest.json`
- `pass_1/artifact_sha256.json`
- `pass_1/development/2020/.../targets.csv`
- `pass_1/development/2021/.../targets.csv`
- `pass_1/development/2022/.../targets.csv`
- corresponding development source, configuration, sleeve, fold, and replay inputs required by unchanged execution mechanics

`pass_2` is evidence of deterministic identity only. Development execution imports target streams from `pass_1` after proving that `pass_1` and `pass_2` artifact maps are identical.

No validation-path file may be opened. The implementation must enforce this structurally rather than by convention.

## Entry preflight

Before constructing any control, the development runner must verify all of the following:

1. the equivalence manifest exists and parses as canonical JSON;
2. `status == "PASS"`;
3. `campaign == 52`;
4. `canonical_capture_equal == true`;
5. `capture_replay_equal == true`;
6. `independent_passes == 2`;
7. `counterfactuals_generated == false`;
8. `performance_metrics_calculated == false`;
9. `bootstrap_run == false`;
10. `runtime_modified == false`;
11. `strategy_modified == false`;
12. `weights_modified == false`;
13. all six governed source SHA-256 values exactly match the frozen identities;
14. the `pass_1` and `pass_2` artifact SHA-256 maps are byte-identical;
15. every imported development target file matches the recorded SHA-256 identity;
16. no required target file is missing, duplicated, empty, or outside the development folds;
17. every target stream satisfies the frozen schema, sort order, sequence, sleeve, fold, timestamp, action, and signed-target validation contract;
18. no path containing `validation`, `2023`, `2024`, or `2025` is opened by the development process.

Any failure terminates before control generation and writes only a fail-closed diagnostic manifest. It must not write partial target, replay, NAV, metric, bootstrap, ranking, or decision artifacts.

## Canonical development reference

The canonical development reference consists of the imported authentic target streams for folds `2020`, `2021`, and `2022`, replayed through the already validated unchanged execution path.

The development runner must replay the canonical target stream once within the new run and verify that its sleeve equity, exposure, trades, costs, fold NAV, and stitched development NAV match the corresponding governed equivalence artifacts exactly.

This is an import-integrity check, not a new canonical strategy evaluation.

## Frozen controls

Exactly 20 controls are constructed. Control count and identifiers are invariant.

Canonical order:

1. `static_dev_mean_target`
2. `lag_24h`
3. `lag_168h`
4. `lag_672h`
5. `perm_01`
6. `perm_02`
7. `perm_03`
8. `perm_04`
9. `perm_05`
10. `perm_06`
11. `perm_07`
12. `perm_08`
13. `perm_09`
14. `perm_10`
15. `perm_11`
16. `perm_12`
17. `perm_13`
18. `perm_14`
19. `perm_15`
20. `perm_16`

No control may be omitted, substituted, regenerated with another seed, or reordered after any outcome artifact exists.

## Static development mean

For each sleeve independently:

- pool all canonical signed target exposure observations across development folds `2020`, `2021`, and `2022` in canonical timestamp order;
- calculate the arithmetic mean using full in-memory precision;
- do not weight folds, timestamps, assets, or sleeves differently;
- do not round before target serialization;
- supply the same signed value at every native decision timestamp in every development fold;
- preserve each row's original stage, fold, timestamp, sleeve, asset, native timeframe, and sequence number;
- set transformation metadata to identify the source as `static_dev_mean_target`;
- unchanged execution rules decide whether a trade occurs.

The static values must be written once to a dedicated deterministic manifest before replay and then treated as immutable inputs.

## Positive displacement controls

For `lag_24h`, `lag_168h`, and `lag_672h`, transform each sleeve and fold independently.

For canonical row timestamp `t`:

- look up the canonical signed target at exact timestamp `t - lag` within the same sleeve and same fold;
- if the exact source timestamp exists, copy its signed target value;
- otherwise supply `0.0`;
- do not wrap;
- do not cross folds;
- do not cross stages;
- do not use nearest matching, resampling, interpolation, backward fill, or forward fill;
- retain the destination row's timestamp and sequence number.

The transformation manifest must report, for every fold/sleeve/control, exact matched-row and zero-filled-row counts.

## Deterministic 28-day block permutations

Permutations operate separately within each development fold while using the same fold-specific block order across all sleeves.

For each fold:

1. set the partition origin to the fold start;
2. partition wall-clock time into consecutive 28-day intervals;
3. identify complete blocks wholly contained in the fold transformation interval;
4. leave the incomplete terminal block in its original terminal location;
5. derive seeds for `perm_01` through `perm_16` as the first unsigned 64-bit integer represented by the first 16 hexadecimal characters of `SHA256("campaign52|block28d|perm|NN")`, with zero-padded `NN`;
6. apply seeded Fisher-Yates to the complete block indices;
7. use the same resulting block-index permutation for every sleeve in that fold;
8. move target values by preserving within-block wall-clock offset and canonical row order;
9. retain each destination row's stage, fold, timestamp, sleeve, asset, timeframe, and sequence number;
10. preserve the terminal incomplete block unchanged.

If a sleeve lacks a source row at an exact mapped within-block timestamp because of its native calendar, the implementation must use the frozen native row-order mapping within that sleeve's block, not nearest-time matching. Source and destination complete blocks must have identical row counts per sleeve. Any unequal block row count fails closed before replay.

The transformation manifest must include the seed, complete-block count, terminal-block boundaries, canonical block order, permuted block order, and per-sleeve row-count equality checks.

## Transformation invariants

Every control target stream must:

- contain exactly one row for every canonical destination row;
- preserve destination identifiers and sequence numbers;
- contain finite signed target values;
- preserve control-independent metadata fields;
- be deterministic across two independent transformation passes;
- remain within its development fold;
- never read or derive from validation data;
- serialize using the frozen target CSV contract.

The implementation must generate all transformation manifests and target SHA-256 maps before executing any control. If the two independent transformation passes differ, the runner stops and no replay occurs.

## Replay execution

After transformation identity passes:

- replay the canonical reference and all 20 controls through the same validated target-replay adapter;
- use unchanged source files, fold windows, sleeve weights, capital allocation, execution costs, slippage, spread, cooldowns, rebalance threshold, BIL cash-yield handling, aggregation frequency, and stitching semantics;
- process controls in frozen canonical order;
- isolate each control's output directory;
- do not invoke any strategy module;
- do not alter targets during replay;
- fail closed on any malformed stream, execution exception, missing artifact, non-finite value, index mismatch, or aggregation mismatch.

The runner may parallelize controls only if each worker is isolated and deterministic, worker count is recorded, output ordering remains canonical, and a serial-versus-parallel synthetic equivalence test exists before governed execution.

## Development NAV construction

For canonical and each control:

- aggregate sleeve equity through canonical `align_equity_curves(..., base_freq="1h")` semantics;
- sum active sleeve equity to fold fund NAV;
- restrict fold reporting to the canonical out-of-sample portion;
- scale and stitch folds chronologically using the frozen running-NAV procedure;
- remove duplicated boundary timestamps using the same canonical keep rule;
- derive daily end-of-day NAV from the stitched hourly portfolio NAV using the last available observation for each UTC calendar day;
- use only common daily timestamps when forming paired canonical-minus-control series.

No normalization may change relative economics between canonical and controls.

## Primary metrics

For canonical and each control, calculate on daily end-of-day stitched development NAV:

1. annualized geometric return;
2. maximum drawdown magnitude as a non-negative magnitude;
3. Calmar ratio.

The exact annualization basis, zero-duration handling, zero-drawdown handling, and non-finite Calmar behavior must be frozen in implementation tests before governed execution. No post-outcome convention changes are allowed.

## Secondary descriptive metrics

Calculate exactly the frozen secondary set:

- annualized volatility;
- Sharpe ratio with zero excess-return benchmark;
- worst 21-calendar-day return;
- worst 63-calendar-day return;
- longest drawdown duration in calendar days;
- median drawdown-recovery duration;
- total fees plus slippage plus spread;
- turnover notional divided by average NAV;
- final equity.

Secondary metrics are descriptive only and cannot alter the development support decision.

## Paired daily inference

For each of the 20 controls:

- align canonical and control daily NAV to common timestamps;
- compute daily log returns separately;
- form paired difference `canonical_log_return - control_log_return`;
- require identical paired timestamp sets across repeated runs;
- use deterministic moving-block bootstrap with block length `21` daily observations;
- use `10,000` replications;
- derive seed from the first unsigned 64-bit integer represented by the first 16 hexadecimal characters of `SHA256("campaign52|bootstrap|development|control_id")`;
- sample starting blocks with replacement until stage length is reached, then truncate;
- report observed mean paired difference;
- report two-sided 95% percentile interval;
- calculate the one-sided superiority p-value from the deterministic bootstrap distribution using the implementation convention frozen before execution.

The same sampled paired-return paths must be used to derive bootstrapped drawdown and Calmar comparisons for that control.

Bootstrap index arrays must be serializable or reproducible from a manifest containing the exact seed, stage length, block length, replication count, and bootstrap algorithm version.

## Multiplicity

Apply Holm step-down adjustment across exactly 20 one-sided mean-difference p-values within development.

- family size remains 20;
- ties use deterministic control order as the secondary sort key;
- an unrankable control receives raw and adjusted p-value `1.0` and remains in the family;
- adjusted p-values must be monotone under the Holm step-down rule;
- no control may be excluded after outcomes exist.

## Frozen development decision

A control is `development-separated` only when all are true:

1. canonical annualized geometric return exceeds the control;
2. canonical maximum drawdown magnitude is at least `1.00` percentage point smaller than the control, **or** canonical Calmar is at least `0.10` higher;
3. one-sided Holm-adjusted p-value for positive mean daily log-return difference is `<= 0.10`.

Campaign #52 advances to a separate validation-interpretation decision only if all are true:

- at least `2` of the `3` lag controls are development-separated;
- canonical exceeds the median of the `16` block permutations on all three primary endpoints;
- canonical exceeds the static control on at least `2` of the `3` primary endpoints.

If the development gate fails, Campaign #52 closes as a development negative. Validation outcomes must not be generated or inspected.

## Two-pass determinism

The complete development process must run twice independently from the verified imported target artifacts.

The two passes must produce identical SHA-256 maps for:

- transformation manifests;
- every control target stream;
- canonical and control trades/costs/exposures;
- sleeve equity;
- fold NAV;
- stitched hourly NAV;
- daily NAV and return tables;
- metric tables;
- bootstrap/multiplicity tables;
- development decision manifest.

Any mismatch is a HOLD and the runner must not print or expose the development support classification as valid evidence.

## Required output layout

Default root:

`artifacts/campaign52_development_execution`

Required top-level artifacts:

- `input_identity_manifest.json`
- `reference_configuration_manifest.json`
- `control_definition_manifest.json`
- `transformation_manifest.json`
- `pass_1/...`
- `pass_2/...`
- `artifact_sha256.json`
- `development_decision_manifest.json`

Each pass must contain canonical and all 20 controls with deterministic target, trade, cost, exposure, sleeve equity, fold NAV, stitched NAV, daily NAV, metric, and inference artifacts.

The terminal console output must be a compact canonical JSON summary only after all checks pass. It must state whether the development gate passed or failed, but must not contain or trigger any validation result.

## Fail-closed conditions

The implementation must terminate without a valid decision on any of the following:

- source or imported artifact identity mismatch;
- equivalence manifest not PASS;
- development/validation boundary violation;
- control count or identifier mismatch;
- seed mismatch;
- block partition or row-count mismatch;
- target schema, sequence, timestamp, or finiteness failure;
- canonical import replay mismatch;
- replay exception or economic artifact mismatch;
- non-deterministic transformation or execution artifacts;
- daily alignment failure;
- bootstrap replication or seed failure;
- Holm family-size or monotonicity failure;
- non-finite required primary metric without a pre-frozen handling rule;
- partial or stale output contamination.

The runner must write into a fresh temporary directory and atomically promote it to the final output root only after a full PASS or valid development-negative decision. Existing output directories must not be silently reused or merged.

## Required pre-governed tests

Before any governed development execution, implementation must pass focused synthetic tests covering at minimum:

- equivalence-manifest and source-hash preflight;
- structural rejection of validation paths;
- exact static mean construction;
- exact lag zero-fill behavior;
- deterministic seed derivation;
- Fisher-Yates permutation identity;
- terminal incomplete-block preservation;
- same permutation across sleeves;
- unequal block row-count rejection;
- two-pass target byte identity;
- canonical import replay identity;
- daily EOD construction;
- primary metric edge cases;
- paired 21-day moving-block bootstrap reproducibility;
- Holm adjustment including ties and unrankable controls;
- development decision rule boundaries;
- atomic output promotion and stale-output rejection;
- serial-versus-parallel identity if parallelism is enabled.

Synthetic tests may use fabricated prices and targets only. They must not inspect governed development outcomes.

## Runtime strategy

The governed run must avoid rerunning canonical strategy evaluation. The expensive canonical target generation has already passed equivalence and is imported by identity.

Expected cost drivers are:

- replaying 21 target families across 9 sleeves and 3 development folds;
- writing deterministic artifacts;
- 20 paired bootstraps with 10,000 replications;
- repeating the complete process twice.

Implementation should vectorize bootstrap index generation and metric evaluation where exact equivalence is demonstrable. It must not reduce replication count, shorten the development period, alter block length, change control count, or approximate execution.

A dry-run mode may validate identities, transformations, row counts, and artifact plans without replay or metrics. Dry-run output must be clearly marked non-outcome and cannot satisfy the governed execution gate.

## Current decision

Procedure is defined for review only.

Next possible action requires an explicit board authorization to implement observation-only development tooling and synthetic tests. Control generation, governed replay, metrics, inference, and development outcome inspection remain prohibited until later gates separately authorize them.
