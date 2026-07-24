# Core v1 Historical Event Families — Final Implementation Handoff

## Campaign

**Campaign #41 — Deterministic overlap-aware historical event families**

**Final state:** Implemented, validated, canonically published, documented, scope-reviewed, and authorized for squash merge through PR #41.

## Governing constraints

All Campaign #41 work remains:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- separate from production runtime;
- independent of model retraining;
- independent of threshold, order, NAV, and exposure mutation;
- additive to Campaign #40 artifacts;
- incapable of mutating governed source artifacts.

Campaign closure and merge do not authorize runtime integration or any prohibited behavior change.

## Governing specification

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_CADENCE_EVIDENCE.md`

## Implemented surfaces

- `research/ml/validation/historical_event_families.py`
- `scripts/run_core_v1_historical_event_families.py`
- `tests/test_historical_event_families.py`
- `artifacts/core_v1_historical_event_families/`
- Campaign #41 documentation and campaign board

No production runtime, live-state, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard surface was modified.

## Governed inputs

Immutable Campaign #40 artifacts:

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`

Cadence-validation source:

- `artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`

Prediction-source evidence:

- SHA-256: `36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7`
- row count: `52453`
- first timestamp: `2020-01-01 01:00:00`
- last timestamp: `2025-12-26 00:00:00`
- timezone convention: timezone-naive
- canonical cadence: `PT1H`
- duplicate timestamps: zero
- timestamp order: strictly increasing
- larger timestamp gaps remain preserved missing-bar gaps

## Canonical adjacency rule

For closed intervals, a later episode joins the current family only when:

`next_start <= current_family_end + PT1H`

No inferred cadence, interpolation, tolerance expansion, or learned gap rule is permitted.

## Implemented behavior

The research module provides deterministic, side-effect-free logic for:

- loading and validating governed episode rows;
- reconciling zero-based `episode_id` values to persisted CSV row order;
- validating source and classified identities;
- parsing and normalizing timestamps;
- validating the governed `PT1H` cadence;
- confirming episode boundaries exist in the governed prediction index;
- grouping closed intervals by overlap or exact one-bar adjacency;
- computing stable family identifiers;
- computing family composition and similarity summaries;
- producing canonical records suitable for strict serialization;
- failing closed on validation violations.

The command-line runner:

- requires explicit governed input and output paths;
- verifies source identities and hashes;
- recomputes and reconciles Campaign #40 classification;
- writes only to a new or explicitly empty output directory;
- stages a complete deterministic output set;
- refuses source overwrite and partial publication;
- emits strict UTF-8, LF-only text artifacts;
- emits a machine-readable integrity manifest;
- exits nonzero on any validation, reconciliation, serialization, or integrity failure.

## Canonical artifacts

Published under `artifacts/core_v1_historical_event_families/`:

1. `btc_extended_up_event_family_membership.csv`
2. `btc_extended_up_event_families.json`
3. `btc_extended_up_event_family_summary.json`
4. `btc_extended_up_event_family_report.md`
5. `btc_extended_up_event_family_manifest.json`

Exact SHA-256 values:

- `btc_extended_up_event_families.json` — `be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584`
- `btc_extended_up_event_family_manifest.json` — `e59c27fd40b4a5994cbe2b46e9585a75f8470bdcb5a9bf9998cfb32a3873da9a`
- `btc_extended_up_event_family_membership.csv` — `6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744`
- `btc_extended_up_event_family_report.md` — `f63dbb3fa66c0fb66dbcd244f0e83a890ecc011d8ac8e5c55a043e9b2638bab5`
- `btc_extended_up_event_family_summary.json` — `cd8235ec0572060bc36872e2d6771b298d41102f91d383d5cfc4df0e0e85b922`

The accepted canonical set was copied from `replay_a` only after exact hash and LF-only verification. `replay_a` and `replay_b` remain local validation outputs and are not committed.

## Accepted results

- governed source episodes: `122`
- deterministic event families: `14`
- canonical outputs: `5`
- observation-only: true
- research-only: true
- runtime integration allowed: false
- exposure mutation allowed: false

## Validation evidence

### Focused tests

- original pure-core suite: `9 passed`
- expanded suite: `12 passed in 1.07s`

Environment: Windows / Python `3.14.6`.

### Full repository suite

Command:

`python -m pytest -q`

Result:

- collected: `413`
- passed: `413`
- failed: `0`
- warnings: `75`
- elapsed: `241.42s` (`0:04:01`)

Warnings were existing Python `datetime.utcnow()` deprecations and pytest class-scoped instance-method fixture warnings. No test failed.

### Governed replay

Two governed runs completed into separate empty output directories. Verification confirmed:

- five files in each replay directory;
- identical filename sets;
- equal byte lengths for every corresponding file;
- identical SHA-256 values for every corresponding file;
- LF-only content;
- unchanged governed source hashes;
- exact reconciliation of membership, family records, summary, report, and manifest.

### Publication scope

Canonical publication commit:

- `d850307d53236b369af87ef5d10908d7ce0108f1`

It added exactly the five authorized canonical artifact files.

The local working tree retained only pre-existing untracked export, data, server-data, and runtime-state files. None was staged or committed.

Remote comparison against `main` found no production runtime, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard file changes.

## Acceptance gates

All Campaign #41 technical and publication gates are complete:

- authorized implementation scope respected;
- focused tests pass;
- full repository suite passes;
- two real-artifact runs succeed;
- governed source hashes remain unchanged;
- every governed episode appears exactly once in membership output;
- family, summary, report, and manifest counts reconcile;
- replay outputs are byte-identical;
- generated text artifacts are LF-only;
- canonical artifacts are accepted and committed;
- exact hashes and evidence are recorded;
- branch scope is reviewed;
- PR #41 is opened, reviewed, and authorized for squash merge.

## Explicit non-goals retained

- learned clustering;
- semantic or model-generated event labels;
- predictive recovery modeling;
- calibrated probabilities;
- dominant-label inference;
- mutation or deletion of Campaign #40 artifacts;
- strategy logic;
- runtime integration;
- threshold changes;
- model retraining;
- order, NAV, or exposure mutation;
- dashboard integration.

## Campaign conclusion

Campaign #41 establishes the independent-event layer needed to distinguish `122` overlapping episode observations from `14` deterministic historical event families.

The campaign is complete once PR #41 is squash-merged and the final merge SHA is recorded on `docs/ITERA_CAMPAIGN_BOARD.md`.

The provisional next research frontier is Campaign #42: compare the governed Core v1 taxonomy at episode resolution versus independent event-family resolution. That work remains planning-only until separately specified and authorized.
