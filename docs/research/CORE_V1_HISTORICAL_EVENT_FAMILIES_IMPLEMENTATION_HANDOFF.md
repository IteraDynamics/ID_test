# Core v1 Historical Event Families — Final Implementation Handoff

## Campaign

**Campaign #41 — Deterministic overlap-aware historical event families**

**Milestone:** Implementation, validation, canonical artifact publication, and draft-PR preparation complete.

This document is the final implementation handoff for Campaign #41. It records completed work and acceptance evidence. It does not authorize production runtime integration, model retraining, threshold changes, order behavior, NAV behavior, exposure behavior, or dashboard integration.

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

## Governing documents

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_CADENCE_EVIDENCE.md`;
- `docs/ITERA_CAMPAIGN_BOARD.md`.

## Implemented surfaces

- `research/ml/validation/historical_event_families.py`;
- `scripts/run_core_v1_historical_event_families.py`;
- `tests/test_historical_event_families.py`;
- `artifacts/core_v1_historical_event_families/`;
- Campaign #41 research documentation;
- the Campaign Board.

No production runtime, live-state, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard surface was changed.

## Governed inputs

Immutable Campaign #40 sources:

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`;
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`;
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`.

Cadence-validation source:

- `artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`.

Governed cadence evidence:

- SHA-256: `36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7`;
- rows: `52453`;
- first timestamp: `2020-01-01 01:00:00`;
- last timestamp: `2025-12-26 00:00:00`;
- timezone-naive;
- strictly increasing;
- no duplicates;
- canonical cadence: `PT1H`;
- larger timestamp deltas remain preserved missing-bar gaps.

## Canonical adjacency rule

For closed intervals, a later episode joins the current family only when:

`next_start <= current_family_end + PT1H`

No inferred cadence, interpolation, tolerance expansion, or learned gap rule is permitted.

## Implementation properties

The research module is side-effect free and performs deterministic loading, validation, reconciliation, grouping, family identity construction, composition summaries, similarity summaries, and canonical record construction.

The command-line runner:

- requires explicit governed paths;
- verifies prediction identity and source hashes;
- recomputes and reconciles Campaign #40 classification;
- refuses unauthorized or non-empty output directories;
- stages a complete output set before publication;
- emits strict, stable, LF-only text artifacts;
- exits nonzero on validation, integrity, reconciliation, or publication failure.

## Canonical generated artifacts

The following files are accepted and published directly under `artifacts/core_v1_historical_event_families/`:

1. `btc_extended_up_event_family_membership.csv`;
2. `btc_extended_up_event_families.json`;
3. `btc_extended_up_event_family_summary.json`;
4. `btc_extended_up_event_family_report.md`;
5. `btc_extended_up_event_family_manifest.json`.

Canonical publication commit:

- `d850307d53236b369af87ef5d10908d7ce0108f1` — `Publish Campaign 41 historical event-family artifacts`.

Exact canonical SHA-256 values:

- `btc_extended_up_event_families.json` — `be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584`;
- `btc_extended_up_event_family_manifest.json` — `e59c27fd40b4a5994cbe2b46e9585a75f8470bdcb5a9bf9998cfb32a3873da9a`;
- `btc_extended_up_event_family_membership.csv` — `6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744`;
- `btc_extended_up_event_family_report.md` — `f63dbb3fa66c0fb66dbcd244f0e83a890ecc011d8ac8e5c55a043e9b2638bab5`;
- `btc_extended_up_event_family_summary.json` — `cd8235ec0572060bc36872e2d6771b298d41102f91d383d5cfc4df0e0e85b922`.

The canonical files were copied from `replay_a` only after exact hash verification. `replay_a` and `replay_b` remain local validation outputs and are not committed.

## Validation evidence

### Focused tests

- original pure-core suite: `9 passed`;
- expanded Campaign #41 suite: `12 passed in 1.07s`;
- environment: Windows / Python `3.14.6`.

### Governed two-run execution

Two governed runs completed into separate empty directories. Each produced:

- source episodes: `122`;
- event families: `14`;
- exactly five output files;
- observation-only completion;
- no runtime, threshold, order, NAV, or exposure changes.

### Replay verification

The two output sets were verified using resolved absolute paths, strict PowerShell mode, terminating errors, exact filename-set comparison, byte-length comparison, SHA-256 comparison, and carriage-return-byte checks.

Verified:

- five files in each replay directory;
- identical filename sets;
- byte-identical content for every file;
- identical SHA-256 values for every file;
- LF-only content for every generated text artifact.

### Full repository suite

Command:

`python -m pytest -q`

Result:

- collected: `413`;
- passed: `413`;
- failed: `0`;
- warnings: `75`;
- elapsed: `241.42s` (`0:04:01`).

Warnings were existing deprecation warnings involving `datetime.utcnow()` and pytest class-scoped instance-method fixtures.

### Publication scope

The canonical publication commit added exactly the five accepted artifact files. The local worktree continued to show only pre-existing untracked export, data, server-data, and runtime-state files; none was staged or committed.

Remote branch comparison against `main` showed no production runtime, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard file changes.

The branch also contains foundational Itera governance documents created earlier on the same branch. Those documents are disclosed in the draft PR scope and are not runtime behavior changes.

## Acceptance gates

- approved Campaign #41 implementation surfaces respected — complete;
- focused tests pass — complete;
- full repository suite passes — complete;
- governed real-artifact execution succeeds twice — complete;
- source identities and hashes reconcile — complete;
- every governed episode appears exactly once — complete;
- membership, family, summary, report, and manifest counts reconcile — complete;
- replay outputs are byte-identical — complete;
- all generated text artifacts are LF-only — complete;
- canonical artifacts accepted and committed — complete;
- no prohibited behavior change — complete;
- exact final evidence recorded — complete.

## Explicit non-goals and continuing prohibitions

Campaign #41 does not authorize:

- learned clustering;
- semantic or model-generated event labels;
- predictive recovery modeling;
- calibrated probabilities;
- dominant-label inference;
- Campaign #40 artifact mutation;
- strategy logic changes;
- runtime integration;
- threshold changes;
- model retraining;
- order, NAV, or exposure mutation;
- dashboard integration.

No existing governed artifact may be rewritten in place.

## Final handoff state

Campaign #41 implementation and validation are complete. Canonical artifacts are published on the working branch. The remaining repository action is review and eventual merge of the draft pull request. Merge remains a separate explicit decision and must not be interpreted as authorization for runtime integration or any prohibited behavior change.
