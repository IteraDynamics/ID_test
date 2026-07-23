# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Future ChatGPT conversations should read this file before proposing or implementing the next step.

The board is descriptive project state. It does not authorize production, threshold, order, NAV, exposure, or runtime changes.

## Active campaign

**Campaign:** Core v1 Historical Regime Taxonomy

**Status:** Complete, portability-verified, and ready for user-managed merge

**Working branch:** `feature/core-v1-historical-regime-taxonomy`

**Pull request:** `#40 — Complete Core v1 historical regime taxonomy`

**Repository:** `IteraDynamics/ID_test`

**Production:** `dashboard.iteradynamics.com` / `/opt/itera/app`

## Governing constraints

All work in this campaign remains:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- separate from production runtime;
- independent of model retraining;
- independent of threshold, order, NAV, and exposure mutation.

## Completed deliverables

### Historical regime taxonomy specification

Created and completed:

- `docs/research/CORE_V1_HISTORICAL_REGIME_TAXONOMY.md`

The specification defines deterministic labels for:

- collapse severity;
- feature displacement;
- volatility-state subtype;
- recovery outcome;
- similarity-to-current band;
- composite regime label.

It also documents source artifacts, reproduction commands, output paths, report-model requirements, feature-ranking rules, strict JSON behavior, digest and byte-replay verification, portability requirements, statistical caveats, and explicitly deferred scope.

### Taxonomy implementation

Created:

- `research/ml/validation/historical_regime_taxonomy.py`
- `scripts/run_core_v1_historical_regime_taxonomy.py`
- `tests/test_historical_regime_taxonomy.py`

The implementation is deterministic, preserves source rows, fails closed on invalid or mismatched inputs, emits strict JSON, and remains separate from runtime behavior.

### Human-readable taxonomy reporting

Created:

- `research/ml/validation/historical_regime_taxonomy_report.py`
- `scripts/run_core_v1_historical_regime_taxonomy_report.py`
- `tests/test_historical_regime_taxonomy_report.py`

The reporting layer:

- validates exact classified/signature episode identity;
- reconciles taxonomy summary counts against classified rows;
- validates subtype recovery summaries;
- computes activation, similarity, recovery, and feature metrics deterministically;
- ranks shifted features from the numeric episode-signature artifact;
- emits compact strict JSON and human-readable Markdown;
- preserves research-only, observation-only, and no-runtime-mutation flags;
- includes overlapping-window and bounded-censoring caveats.

### Portable artifact I/O hardening

Created:

- `research/ml/validation/historical_regime_artifact_io.py`
- `tests/test_historical_regime_artifact_io.py`

The hardening:

- normalizes repository source identifiers to forward-slash, repo-relative form;
- writes generated JSON, Markdown, and classifier CSV with explicit LF line endings;
- directly tests separator normalization, repo-relative identifiers, and LF bytes;
- does not change taxonomy thresholds, labels, episode ordering, subtype calculations, feature ranking, runtime state, NAV, orders, or exposure.

## Final portability-hardened verification

Verified on 2026-07-23 from the real data-bearing Windows checkout using Python 3.14.6.

### Focused tests

Command covered:

- `tests/test_historical_regime_artifact_io.py`
- `tests/test_historical_regime_taxonomy.py`
- `tests/test_historical_regime_taxonomy_report.py`

Result:

- **13 passed in 1.52 seconds**

### Real classifier result

- Episode count: **122**
- Final taxonomy digest: `2114b2353322b3404db4000b36e425716c1a6d01027934ac0b0f595c9f45484f`

Generated classifier outputs:

- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_classified_episodes.csv`
- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_classified_episodes.json`
- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_summary.json`

### Real report result

- Episode count: **122**
- Source taxonomy digest: `2114b2353322b3404db4000b36e425716c1a6d01027934ac0b0f595c9f45484f`
- Final report digest: `e1b29df5853e86c8da627730f2a4af374c0e64c58889f0f0dfdb601385581618`

Generated report outputs:

- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_report.json`
- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_report.md`

### Replay and source-integrity evidence

- Classifier CSV, classifier JSON, and taxonomy summary were byte-identical across replay.
- Report JSON and Markdown were byte-identical across replay.
- All five generated artifacts were explicitly confirmed LF-only with no CRLF bytes.
- All three real source artifacts retained identical SHA-256 hashes before and after replay.
- Generated `artifacts/*` remain intentionally ignored and uncommitted.
- No Core state, NAV, orders, thresholds, exposure, or runtime behavior changed.

### Full repository suite

- **401 passed, 75 warnings**
- Exit code: **0**
- Runtime: **247.88 seconds**
- Captured local log: `%TEMP%/itera_historical_regime_taxonomy_portable_full_suite.txt`

The warnings are existing deprecations involving `datetime.utcnow()` and pytest class-scoped fixture behavior. No warning was suppressed or converted into a weaker gate.

## Observed historical taxonomy

Observed from the 122 real classified episodes:

- Collapse severity: 94 severe, 10 major, 18 moderate.
- Feature displacement: 111 low displacement, 6 broad shift, 5 concentrated shift.
- Volatility state: 114 neutral, 8 expansion.
- Recovery outcome: 29 rapid recovery, 45 delayed recovery, 48 persistent collapse.
- Similarity band: 68 low, 52 medium, 2 high.
- Ten intrinsic subtypes were observed.
- Dominant subtype: `SEVERE_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL`, 87 episodes, descriptive recovered fraction 0.758621, median recovery 1392 rows, median activation ratio 0.0, median similarity-to-current 0.144540.
- Subtype feature reporting uses the numeric episode-signature artifact rather than the inherited string representation of `top_shifted_features`.
- Feature ordering is median absolute standardized signature descending, then feature name ascending; median signed signature preserves direction.

Historical interpretation remains descriptive. Overlapping rolling windows are dependent observations, and persistent collapse means no recovery within the bounded horizon rather than permanent non-recovery.

## Merge state

All documented acceptance gates for PR #40 are complete.

The branch is ready for the user to review and merge. The assistant must not merge PR #40 without explicit user instruction.

After merge:

1. update the local checkout from `main`;
2. confirm the merge commit and clean tracked state;
3. decide whether to authorize the recommended next campaign;
4. do not begin the next implementation solely because it is documented below.

## Recommended next campaign after merge

### Deterministic overlap-aware historical event families

The strongest next research task is an observation-only event-family rollup addressing the principal methodological limitation of the current analysis: many episode rows come from overlapping rolling windows and are dependent observations.

Start with a specification-only milestone. Define a deterministic, replay-safe method to group overlapping or immediately adjacent collapse windows into auditable event families and report both episode-level and event-family-level summaries.

Required design constraints:

- deterministic interval-based grouping only;
- no learned clustering;
- explicit source episode membership for every event family;
- stable ordering and digest;
- no deletion or mutation of existing episode artifacts;
- descriptive event-level counts, durations, recovery outcomes, subtype composition, and latest-window similarity;
- explicit handling of mixed subtype or recovery labels within a family;
- research-only and observation-only;
- no runtime integration, threshold change, model retraining, order, NAV, or exposure mutation.

This recommendation is not active implementation authorization. Begin only after PR #40 merges and the user explicitly selects the campaign.

## Explicitly deferred

- runtime integration;
- threshold changes;
- Core exposure changes;
- learned clustering;
- predictive recovery modeling;
- calibrated recovery probabilities;
- automated production actions from taxonomy labels.

## Calendar operating cadence

- **Daily Mission Check:** confirm PR #40 merge state and identify one concrete next executable step.
- **Weekly Campaign Review:** record shipped evidence, blockers, roadmap decisions, and update this board.
- **Current milestone status:** Final verification complete; awaiting user-managed PR #40 merge.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test`, verify PR #40 and the current branch state, and continue from the documented post-verification merge handoff. Preserve deterministic, replay-safe, observation-only, and fail-closed constraints. Do not introduce runtime integration, threshold changes, orders, NAV, or exposure mutation.

## Board maintenance rule

Update this file whenever one of the following changes:

- active campaign;
- working branch;
- pull request state;
- completed milestone;
- test status;
- material research finding;
- blocker or open decision;
- next executable step;
- acceptance criteria;
- deferred scope.

A campaign is not considered cleanly paused until this board identifies a verified state and one concrete next executable step.
