# Core v1 Jump Risk Historical Regime Taxonomy

## Status

Implemented research-only taxonomy and reporting workflow on `feature/core-v1-historical-regime-taxonomy`.

This taxonomy extends the existing Core v1 Jump Risk drift diagnosis framework beneath the `REGIME_CHANGE` branch. It does not replace the top-level diagnosis classes and does not authorize runtime, threshold, order, NAV, or exposure changes.

## Purpose

Historical collapse episodes are identified by comparing observation-window activation with a preceding reference window. Recovery subtype analysis separates episodes that recovered without retraining from episodes that remained persistent. This taxonomy adds deterministic labels for the shape, severity, feature state, and bounded recovery behavior of those historical regime episodes.

The taxonomy is designed to answer three distinct questions:

1. What kind of activation collapse occurred?
2. What feature-state pattern accompanied it?
3. What happened afterward within the bounded recovery horizon?

The resulting labels are descriptive research evidence, not calibrated forecasts.

## Governing constraints

Every taxonomy artifact MUST remain:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- independent of model retraining;
- independent of runtime state mutation;
- independent of threshold, order, NAV, and exposure mutation.

A taxonomy result MUST NOT be interpreted as an instruction to alter production behavior.

## Taxonomy dimensions

Each historical episode receives one label from each dimension.

### 1. Collapse severity

Collapse severity is determined from the episode activation ratio:

`activation_ratio = observation_activation_rate / reference_activation_rate`

Labels:

- `SEVERE_COLLAPSE`: `activation_ratio <= 0.10`
- `MAJOR_COLLAPSE`: `0.10 < activation_ratio <= 0.20`
- `MODERATE_COLLAPSE`: `0.20 < activation_ratio <= collapse_ratio`

Episodes above the configured `collapse_ratio` are not taxonomy candidates because they are not selected by the historical collapse detector.

### 2. Feature displacement

Feature displacement uses the per-episode standardized feature signature produced from observation-window mean shifts relative to the episode reference distribution.

For each episode define:

- `signature_l2`: Euclidean norm of the full standardized signature;
- `max_abs_shift`: maximum absolute standardized feature shift;
- `shifted_feature_count`: count of features with absolute standardized shift at least `1.0`;
- `shifted_feature_fraction`: shifted feature count divided by total feature count.

Labels:

- `CONCENTRATED_SHIFT`: `max_abs_shift >= 2.0` and fewer than 25% of features have absolute shift at least `1.0`;
- `BROAD_SHIFT`: at least 25% of features have absolute shift at least `1.0`;
- `LOW_DISPLACEMENT_COLLAPSE`: neither condition is met.

`BROAD_SHIFT` takes precedence when both conditions are true.

### 3. Volatility-state subtype

The recovery subtype analysis showed that persistent episodes were associated with elevated volatility, range, width, return-magnitude, and downside-proximity features. The taxonomy therefore records a volatility-state subtype using feature-name matching rather than hard-coding a single feature schema.

A feature is considered volatility-related when its lowercase name contains any of:

- `atr`
- `volatility`
- `realized_vol`
- `bollinger`
- `bb_width`
- `abs_return`
- `downside`

For the matched subset, calculate the median standardized signature.

Labels:

- `VOLATILITY_EXPANSION`: median matched signature `>= 1.0`;
- `VOLATILITY_COMPRESSION`: median matched signature `<= -1.0`;
- `VOLATILITY_NEUTRAL`: otherwise;
- `VOLATILITY_UNAVAILABLE`: no matching features.

The name-matching rule and matched feature list MUST be emitted in the artifact so the classification remains auditable.

### 4. Recovery outcome

Recovery outcome preserves the historical analysis definition: the trailing observation-window activation rate reaches the configured recovery ratio of the episode reference activation rate within the bounded maximum recovery horizon.

Labels:

- `RAPID_RECOVERY`: recovered and `recovery_rows <= observation_rows`;
- `DELAYED_RECOVERY`: recovered and `recovery_rows > observation_rows`;
- `PERSISTENT_COLLAPSE`: no recovery within `max_recovery_rows`.

This is bounded censoring. `PERSISTENT_COLLAPSE` means persistent within the configured search horizon, not necessarily permanent.

### 5. Similarity-to-current band

Cosine similarity to the latest feature signature is retained as a descriptive analogue measure.

Labels:

- `HIGH_SIMILARITY`: similarity `>= 0.75`;
- `MEDIUM_SIMILARITY`: `0.40 <= similarity < 0.75`;
- `LOW_SIMILARITY`: similarity `< 0.40`.

Similarity MUST NOT be used alone as a recovery forecast. Historical evidence already shows that feature similarity is insufficient to determine recovery outcome.

## Composite regime label

A deterministic composite label is formed as:

`<collapse_severity>__<feature_displacement>__<volatility_state>__<recovery_outcome>`

Example:

`MAJOR_COLLAPSE__BROAD_SHIFT__VOLATILITY_EXPANSION__PERSISTENT_COLLAPSE`

The similarity band remains a separate field because it describes relation to the latest window rather than the episode's intrinsic subtype.

## Required episode artifact schema

Each classified episode MUST contain at least:

- `episode_id`
- `window_start`
- `window_end`
- `reference_activation_rate`
- `observation_activation_rate`
- `activation_ratio`
- `collapse_severity`
- `feature_cosine_similarity_to_latest`
- `similarity_band`
- `signature_l2`
- `max_abs_shift`
- `shifted_feature_count`
- `shifted_feature_fraction`
- `feature_displacement`
- `volatility_feature_count`
- `volatility_features`
- `volatility_median_signature`
- `volatility_state`
- `recovered_without_retraining`
- `recovery_rows`
- `recovery_outcome`
- `composite_regime_label`

## Required taxonomy summary schema

The taxonomy summary MUST contain:

- experiment name and research-only safety flags;
- exact threshold configuration;
- total episode count;
- counts by each taxonomy dimension;
- counts by composite regime label;
- recovered fraction by intrinsic subtype;
- median recovery rows by intrinsic subtype where recovery occurred;
- latest-window metadata copied from the historical regime artifact;
- matched volatility-feature names;
- normalized source artifact identifiers;
- deterministic SHA-256 digest.

## Required report model

The compact report model and Markdown rendering MUST include:

- source taxonomy digest and report digest;
- total, recovered, and persistent episode counts;
- descriptive recovered fraction;
- counts by taxonomy dimension and composite label;
- dominant intrinsic subtypes;
- subtype episode count, recovered count and fraction;
- subtype median recovery rows where recovery occurred;
- subtype median activation ratio;
- subtype median and mean similarity to the latest signature;
- top shifted features by subtype;
- source artifact identifiers;
- overlapping-window, bounded-censoring, and research-only caveats.

Top shifted features are calculated from the numeric episode-signature artifact, not from the inherited string representation of `top_shifted_features` in the historical episode CSV. Features are ordered by median absolute standardized signature descending, with feature name ascending as the deterministic tie-breaker. Median signed signature preserves direction.

## Determinism and validation requirements

The implementation MUST:

- sort categorical summaries deterministically;
- reject duplicate episode identifiers;
- reject missing required fields;
- reject non-numeric activation ratios and signature values;
- reject recovered episodes without valid positive `recovery_rows`;
- reject persistent episodes with non-null `recovery_rows`;
- require exact identity between classified episode IDs and signature episode IDs;
- reconcile report counts and subtype recovery summaries to the taxonomy summary;
- serialize missing optional scalars as strict JSON `null`, never non-standard `NaN`;
- normalize repository artifact identifiers to slash-separated repo-relative form;
- emit generated text and CSV artifacts with explicit LF line endings;
- emit the same digest and byte-identical artifacts for identical inputs and configuration;
- preserve original source rows and signature artifacts without mutation.

## Source artifacts

The default workflow requires these generated, intentionally uncommitted inputs:

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`

If any required artifact is absent, stop and regenerate it only through the existing research-only historical-regime and recovery-subtype workflows. Do not substitute synthetic values for a real verification run.

## Reproduction commands

Run from the repository root:

```powershell
python scripts/run_core_v1_historical_regime_taxonomy.py
python scripts/run_core_v1_historical_regime_taxonomy_report.py
```

Focused verification:

```powershell
python -m pytest `
    tests/test_historical_regime_artifact_io.py `
    tests/test_historical_regime_taxonomy.py `
    tests/test_historical_regime_taxonomy_report.py `
    -q
```

Full repository verification:

```powershell
python -m pytest -q
```

## Generated outputs

Classifier outputs:

- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_classified_episodes.csv`
- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_classified_episodes.json`
- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_summary.json`

Report outputs:

- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_report.json`
- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_report.md`

Generated artifacts remain ignored and MUST NOT be committed unless explicitly authorized.

## Verification protocol

A release-quality verification requires:

1. successful focused tests;
2. successful classifier execution against the full real artifact set;
3. confirmation of the expected episode count;
4. capture of the taxonomy digest;
5. a second classifier run with byte-identical CSV, JSON, and summary outputs;
6. successful report execution;
7. capture of the report digest;
8. a second report run with byte-identical JSON and Markdown outputs;
9. successful full repository test suite;
10. human inspection that Markdown and compact JSON agree and retain all caveats.

The portability-hardening change that canonicalizes artifact identifiers and line endings requires a fresh real-data verification before merge. Earlier same-machine digests remain historical evidence but are superseded for the final branch head.

## Statistical interpretation

Historical episodes are sampled from overlapping rolling windows. Counts and recovered fractions are therefore descriptive and dependent, not independent Bernoulli trials. The taxonomy is intended for structured diagnosis, analogue retrieval, and hypothesis generation. It is not a calibrated probability model and must not be presented as one.

## Explicitly out of scope

- runtime integration;
- threshold changes;
- order generation or routing changes;
- NAV or exposure mutation;
- model retraining;
- learned clustering;
- predictive recovery modeling;
- calibrated recovery probabilities;
- automated production actions from taxonomy labels.
