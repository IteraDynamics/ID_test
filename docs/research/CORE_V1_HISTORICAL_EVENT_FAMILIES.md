# Core v1 Historical Event Families

## Campaign

**Campaign #41 — Deterministic overlap-aware historical event families**

**Classification:** Research primary; engineering secondary.

**Milestone:** Specification only.

## Research question

Can overlapping or immediately adjacent historical collapse episode windows be grouped into deterministic, replay-safe event families so Itera can report both episode-level and event-family-level descriptive results without mutating the existing episode artifacts?

## Why this campaign exists

Campaign #40 classified 122 historical episode rows, but many rows originate from overlapping rolling windows and therefore are dependent observations. Episode-row counts must not be interpreted as counts of independent historical events.

This campaign defines an auditable event-family layer above the existing rows. It does not replace, delete, relabel, or rewrite the source episode artifacts.

## Governing constraints

The specification and any later implementation must remain:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- interval-based;
- explicit about source membership;
- separate from runtime behavior;
- independent of model retraining;
- independent of thresholds, orders, NAV, and exposure mutation.

## Governed source artifacts

Campaign #41 consumes the same three immutable source artifacts governed by Campaign #40:

1. `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`;
2. `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`;
3. `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`.

The Campaign #40 classified episode artifacts may be consumed as derived inputs only when their source identity and episode membership reconcile exactly to the three governed source artifacts.

No source artifact may be rewritten, reordered in place, relabeled, or mutated.

## Artifact reconnaissance findings

### Historical episode source fields

The historical episode generator emits one source row per qualifying rolling observation window with these fields:

| Field | Type | Role | Stability requirement |
|---|---|---|---|
| `window_start` | timestamp string | Inclusive first timestamp of the observation window | Required; parsed and normalized deterministically |
| `window_end` | timestamp string | Inclusive last timestamp of the observation window | Required; parsed and normalized deterministically |
| `reference_activation_rate` | finite numeric | Descriptive source metric | Preserved |
| `observation_activation_rate` | finite numeric | Descriptive source metric | Preserved |
| `activation_ratio` | finite numeric | Collapse severity input | Preserved |
| `feature_cosine_similarity_to_latest` | finite numeric | Episode similarity-to-current input | Preserved |
| `recovered_without_retraining` | boolean | Recovery input | Preserved |
| `recovery_rows` | positive integer or null | Bounded recovery distance | Preserved and validated against recovery state |
| `recovery_rate` | finite numeric or null | Descriptive recovery metric | Preserved |
| `top_shifted_features` | ordered list representation | Descriptive feature summary | Not used for family identity |

The source CSV does not emit an `episode_id`. Campaign #40 deterministically inserts a zero-based integer `episode_id` after reading the CSV in its persisted row order. That inserted identifier is therefore the governed episode identity for Campaign #41, provided the source artifact identity and row count match exactly.

### Campaign #40 classified fields

Campaign #40 preserves the complete source row and adds deterministic descriptive fields:

- `collapse_severity`;
- `similarity_band`;
- `signature_l2`;
- `max_abs_shift`;
- `shifted_feature_count`;
- `shifted_feature_fraction`;
- `feature_displacement`;
- `volatility_feature_count`;
- `volatility_features`;
- `volatility_median_signature`;
- `volatility_state`;
- normalized `recovery_rows`;
- `recovery_outcome`;
- `composite_regime_label`.

For Campaign #41:

- episode identity is `episode_id`;
- interval boundaries are `window_start` and `window_end`;
- subtype is the intrinsic three-part label `collapse_severity + feature_displacement + volatility_state`;
- recovery is `recovery_outcome`;
- similarity is `feature_cosine_similarity_to_latest`;
- `composite_regime_label` is not used as the intrinsic subtype because it embeds recovery outcome.

### Boundary semantics

The historical generator constructs each episode from a positional observation slice and emits:

- `window_start = predictions.index[obs_start]`;
- `window_end = predictions.index[end - 1]`.

The emitted interval is therefore a **closed timestamp interval**: `[window_start, window_end]`.

The governed episode artifacts do not emit source row indices and do not encode bar cadence. `step_rows` controls rolling-window traversal; it is not the source bar cadence and must not be reused as an adjacency duration.

## Canonical parsing and normalization

Before grouping, each episode boundary must be parsed as a timezone-aware or timezone-naive timestamp under one uniform source convention.

The implementation must fail closed when:

- any timestamp cannot be parsed;
- timezone awareness is mixed;
- normalized timestamps are non-finite or out of supported range;
- `window_end < window_start`;
- duplicate `episode_id` values exist;
- source and classified episode identities do not match exactly;
- two rows with the same identity disagree on any governed field.

Canonical timestamp serialization must use one documented ISO-8601 form and must not depend on host locale.

## Deterministic adjacency unit

The native boundary unit is timestamp, not row index.

Immediate adjacency is defined only through an explicit positive `bar_cadence` duration supplied as governed configuration for the event-family run:

`next_start <= current_family_end + bar_cadence`

This combines strict overlap and exactly one-bar adjacency for closed timestamp intervals.

The following are prohibited:

- inferring cadence from episode gaps;
- treating `step_rows` as cadence;
- using a tolerance larger than one configured bar;
- silently defaulting cadence from the stream name;
- accepting irregular source timestamps without validation.

Before grouping, the later implementation must validate `bar_cadence` against the governed prediction timestamp index or another explicitly governed cadence manifest. If that validating source is unavailable, inconsistent, or irregular under the documented policy, the implementation must fail closed rather than degrade to overlap-only behavior or infer a cadence.

For this campaign's `btc_extended_up` implementation milestone, the exact cadence value must be obtained from and reconciled against the governed prediction source before code is authorized. The specification intentionally does not guess the value.

## Grouping rule

Event families are connected components under deterministic interval adjacency.

Sort source episodes by:

1. normalized `window_start` ascending;
2. normalized `window_end` ascending;
3. integer `episode_id` ascending.

Initialize the current family from the first episode. Each subsequent episode belongs to the current family when:

`episode.window_start <= current_family.window_end + bar_cadence`

Otherwise it starts a new family.

When an episode joins a family:

- family start remains the minimum member start;
- family end becomes the maximum member end;
- the ordered membership list appends the episode according to canonical sort order.

This sweep is equivalent to deterministic connected components for closed intervals under one-bar adjacency.

## Stable family identity

Each family identifier must be the lowercase hexadecimal SHA-256 digest of canonical strict JSON containing exactly:

```json
{
  "specification_version": "1",
  "source_artifact": "<normalized repository-relative historical episode artifact identifier>",
  "bar_cadence": "<canonical duration>",
  "family_start": "<canonical ISO-8601 timestamp>",
  "family_end": "<canonical ISO-8601 timestamp>",
  "episode_ids": [0, 1]
}
```

Canonical JSON requirements:

- keys sorted lexicographically;
- separators `(',', ':')`;
- UTF-8 encoding;
- no NaN or Infinity;
- ordered integer episode identities;
- no absolute paths;
- no operating-system-specific separators;
- no runtime timestamps or random values.

The complete digest is authoritative. A shortened display form may be shown in reports but must never replace the complete identifier in governed artifacts.

## Required family record

Each event-family record must contain:

- `family_id`;
- `family_ordinal`, zero-based after canonical family ordering;
- `window_start`;
- `window_end`;
- `duration_bars`;
- `bar_cadence`;
- ordered `episode_ids`;
- `episode_count`;
- `intrinsic_subtype_counts`;
- `intrinsic_subtype_mixed`;
- `recovery_outcome_counts`;
- `recovery_outcome_mixed`;
- `latest_episode_id`;
- `latest_episode_similarity_to_current`;
- `maximum_similarity_to_current`;
- `median_similarity_to_current`;
- `research_only: true`;
- `observation_only: true`;
- `runtime_integration_allowed: false`;
- `exposure_mutation_allowed: false`.

`duration_bars` is inclusive for a closed regular-cadence interval:

`((window_end - window_start) / bar_cadence) + 1`

The value must be an exact positive integer. Non-integral duration is a fail-closed error.

## Mixed-label handling

Composition is authoritative. No dominant subtype or dominant recovery label is emitted in Campaign #41.

For intrinsic subtype and recovery outcome:

- counts are emitted as dictionaries with labels sorted lexicographically;
- homogeneous means exactly one distinct label;
- mixed means more than one distinct label;
- ties require no special winner handling because no winner is selected.

This avoids hiding within-family heterogeneity and prevents incidental ordering from becoming semantics.

## Similarity-to-current handling

Each family emits three descriptive similarity values:

1. `latest_episode_similarity_to_current` — similarity of the member with greatest `window_end`, then greatest `window_start`, then greatest `episode_id` as deterministic tie-breakers;
2. `maximum_similarity_to_current` — maximum finite member similarity;
3. `median_similarity_to_current` — deterministic numeric median across all finite member similarities.

All member similarity values are required to be finite. No probability, calibration, forecast, or family-level predictive score is inferred.

## Recovery handling

Recovery outcomes remain bounded-horizon descriptions. `PERSISTENT_COLLAPSE` means no recovery observed within the governed horizon, not permanent non-recovery.

Family reporting preserves complete recovery composition and does not infer a family recovery probability, family recovery date, or calibrated forecast.

## Output schemas for a later implementation milestone

### Membership CSV

One row per source episode, ordered by `family_ordinal`, canonical member order:

- `family_id`;
- `family_ordinal`;
- `episode_id`;
- `member_ordinal`;
- `window_start`;
- `window_end`;
- `intrinsic_subtype`;
- `recovery_outcome`;
- `feature_cosine_similarity_to_latest`.

Every governed episode identity must appear exactly once.

### Family records JSON

A strict JSON array of required family records ordered by:

1. family `window_start` ascending;
2. family `window_end` ascending;
3. `family_id` ascending.

### Family summary JSON

A strict JSON object containing at least:

- experiment identity;
- specification version;
- research and mutation-control flags;
- governed configuration, including canonical `bar_cadence`;
- source artifact identifiers;
- source episode count;
- event-family count;
- family-size distribution;
- homogeneous and mixed family counts by dimension;
- family-level recovery composition totals;
- family-level intrinsic subtype composition totals;
- deterministic digest.

### Human-readable report Markdown

The report must reconcile exactly to the JSON artifacts and explicitly state:

- episode rows are dependent rolling-window observations;
- event-family counts are deterministic interval rollups, not proof of statistical independence;
- one-bar adjacency is configuration-governed;
- recovery remains bounded-horizon and descriptive;
- no runtime or portfolio behavior changed.

All generated text artifacts must use strict serialization, stable ordering, normalized repository-relative source identifiers, and explicit LF line endings.

## Fail-closed validation rules

A later implementation must reject:

- missing governed artifacts;
- source identity mismatch;
- missing required columns;
- duplicate or non-integer episode identities;
- episode/signature identity mismatch;
- malformed or mixed-timezone boundaries;
- reversed intervals;
- missing, zero, negative, inferred, or unvalidated `bar_cadence`;
- intervals not aligned to validated cadence;
- non-finite governed numeric values;
- invalid recovery state/row combinations;
- unknown nulls in required labels;
- incomplete or duplicate family membership;
- family bounds inconsistent with member extrema;
- non-canonical ordering;
- digest mismatch;
- source mutation detected by hash comparison.

## Verification requirements

Before any implementation milestone can merge:

- focused unit tests pass;
- the exact real source schema is captured and reconciled;
- the explicit cadence source is documented and validated;
- source episode membership is complete and exactly once;
- family ordering and identifiers are stable;
- all summary counts reconcile to records and membership;
- generated artifacts are byte-identical across replay;
- all generated text artifacts are LF-only;
- source artifacts retain identical SHA-256 hashes;
- the full repository regression suite passes;
- no runtime, threshold, order, NAV, or exposure behavior changes.

The implementation campaign must document exact commands after its scripts and test paths exist. This specification milestone cannot truthfully prescribe commands for files that are not yet authorized or created.

## Explicit non-goals

- learned clustering;
- semantic or model-generated event labels;
- predictive recovery modeling;
- calibrated probabilities;
- dominant-label inference;
- deletion or mutation of Campaign #40 artifacts;
- strategy logic;
- runtime integration;
- threshold changes;
- model retraining;
- order, NAV, or exposure mutation.

## Specification acceptance status

Resolved:

1. real source identity, boundary, subtype, recovery, and similarity fields are documented;
2. the native boundary unit is timestamp;
3. immediate adjacency is exactly one explicitly configured and validated bar cadence;
4. canonical family identity is finalized;
5. subtype and recovery composition rules are finalized with no dominant label;
6. latest, maximum, and median similarity fields are finalized;
7. output schemas and ordering are explicit;
8. fail-closed validation rules are explicit;
9. no implementation code has been introduced.

Remaining evidence gate:

- inspect the real governed prediction timestamp source to establish and validate the exact `btc_extended_up` bar cadence before implementation authorization.

## Next executable step

Identify the governed Campaign #40 prediction source used to generate `btc_extended_up_historical_regimes.json`, inspect its timestamp index, record the exact fixed cadence and validation evidence, and update this specification and the campaign board. Do not implement event-family code yet.
