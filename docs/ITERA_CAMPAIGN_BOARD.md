# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Future ChatGPT conversations should read this file before proposing or implementing the next step.

The board is descriptive project state. It does not authorize production, threshold, order, NAV, exposure, or runtime changes.

## Active campaign

**Campaign:** Core v1 Historical Regime Taxonomy

**Status:** Implementation complete; pre-merge portability hardening committed and awaiting final real-artifact verification

**Working branch:** `feature/core-v1-historical-regime-taxonomy`

**Pull request:** `#40 — Complete Core v1 historical regime taxonomy`

**Repository:** `IteraDynamics/ID_test`

**Production:** `dashboard.iteradynamics.com` / `/opt/itera/app`

## Governing constraints

All work in this campaign must remain:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- separate from production runtime;
- independent of model retraining;
- independent of threshold, order, NAV, and exposure mutation.

## Completed milestones

### Historical regime analysis

- 122 comparable collapse episodes identified.
- 74 recovered within the bounded horizon.
- 48 remained persistent within the bounded horizon.
- Descriptive recovered fraction: 0.607.
- Median recovery: 1224 rows, approximately 51 days.
- Persistent episodes were associated with elevated volatility-related features.
- Important caveat: overlapping rolling windows make these descriptive dependent observations, not calibrated probabilities or independent Bernoulli trials.

### Historical regime taxonomy specification

Created:

- `docs/research/CORE_V1_HISTORICAL_REGIME_TAXONOMY.md`

Specification commit:

- `bb561049d9ddde23a33c74583db679c2d4b2d7fc`

The specification defines deterministic labels for:

- collapse severity;
- feature displacement;
- volatility-state subtype;
- recovery outcome;
- similarity-to-current band;
- composite regime label.

The specification now also documents:

- source artifacts;
- reproduction commands;
- classifier and report output paths;
- report-model requirements;
- feature-ranking rules;
- digest and byte-replay verification;
- portability requirements;
- explicit deferred scope.

### Taxonomy implementation

Created:

- `research/ml/validation/historical_regime_taxonomy.py`
- `scripts/run_core_v1_historical_regime_taxonomy.py`
- `tests/test_historical_regime_taxonomy.py`

Implementation commits:

- `76b73e07b38be9462b52648ffb334c2b5fd804b2`
- `17b01f71d627d2ad618887c616fb9f72e254ddcf`
- `b39254ed41ab14241d63f13c9a813c37751d9ea8`
- pandas 3 / Python 3.14-compatible test fix: `fafe7808594225cbf43a4fb658475873fa023c90`
- direct-run import and strict JSON null normalization: `7ef4181fb1e1108033ff1bdce1e55b24e7bb2971`
- strict JSON regression coverage: `0f0c2847dce572d6cb126cc9fc244e1bef3646a9`

### Human-readable taxonomy reporting

Created:

- `research/ml/validation/historical_regime_taxonomy_report.py`
- `scripts/run_core_v1_historical_regime_taxonomy_report.py`
- `tests/test_historical_regime_taxonomy_report.py`

Implementation commits:

- report model: `c2e6ce5d7b7125128219f682f7e21699c820a23e`
- report runner: `13aeff95bb9a5a9873d60096eedc4b97486abd10`
- report tests: `8dad4e3fc06f5949e622a7577aed7835ad2ddda1`

The reporting layer:

- validates exact classified/signature episode identity;
- validates taxonomy summary counts against classified rows;
- validates subtype recovery summaries against the taxonomy summary;
- computes subtype activation, similarity, recovery, and feature metrics deterministically;
- ranks shifted features from the numeric episode-signature artifact;
- emits compact strict JSON and human-readable Markdown;
- writes JSON and Markdown through temporary files and replacement;
- preserves research-only, observation-only, and no-runtime-mutation flags;
- includes overlapping-window and bounded-censoring caveats.

## Pre-hardening real verification evidence

The following results were verified on 2026-07-22 from a data-bearing Windows checkout using Python 3.14.6 before the portability-hardening commits:

- Required historical JSON, episode CSV, and signature CSV were present.
- Episode CSV and signature artifact aligned exactly using deterministic positional episode IDs `0` through `121`.
- Focused classifier suite: 6 passed.
- Combined focused classifier/report suite: 10 passed.
- Real classified episode count: 122.
- Taxonomy digest: `7e18d3a9f963029588d01deaa27427279c172a1d948cf696a0df79d91142b547`.
- Report digest: `c0717f2227b7fe060cbe71e3010b3ce90800143c3f90c9d90af883c8c1d23198`.
- Classifier CSV, classifier JSON, and taxonomy summary were byte-identical across same-machine replay.
- Report JSON and Markdown were byte-identical across same-machine replay.
- Full repository suite: 398 passed, 75 warnings, exit code 0.
- Warning classes were existing deprecations involving `datetime.utcnow()` and pytest class-scoped fixture behavior.

These digests remain valid evidence for commit `2b2605acd0bd44337333c20f2c8261027262d0ea`, but they are superseded for the final branch head because provenance path formatting is now canonicalized.

## Observed historical taxonomy

Observed from the 122 real classified episodes:

- Collapse severity: 94 severe, 10 major, 18 moderate.
- Feature displacement: 111 low displacement, 6 broad shift, 5 concentrated shift.
- Volatility state: 114 neutral, 8 expansion.
- Recovery outcome: 29 rapid recovery, 45 delayed recovery, 48 persistent collapse.
- Similarity band: 68 low, 52 medium, 2 high.
- Ten intrinsic subtypes were observed.
- Dominant subtype: `SEVERE_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL`, 87 episodes, descriptive recovered fraction 0.758621, median recovery 1392 rows, median activation ratio 0.0, median similarity-to-current 0.144540.
- The inherited `top_shifted_features` field is a string representation, not a JSON list.
- Subtype feature reporting therefore uses the numeric episode-signature artifact.
- Feature ordering is median absolute standardized signature descending, then feature name ascending; median signed signature preserves direction.

## Pre-merge portability hardening

Audit after PR creation found that the verified Windows artifacts embedded OS-rendered source paths and used platform-default line endings. Same-machine replay remained deterministic, but otherwise identical Windows and Linux runs could differ byte-for-byte and could produce different embedded digests because of path separators.

Committed hardening:

- portable artifact I/O helper: `331292549ba5e637191937315f0fada80c4ce084`
- classifier runner portability: `caf069b29f5f68057bca91ecf273ac044b2cae08`
- report runner portability: `3ed927552545e5467c1894f71526f28a23787697`
- portability regression tests: `1117940310403535eff88980cc317be93cd44457`
- completed taxonomy reproduction runbook: `62c26fd8b5d806c4badb0ba8a3b9077acccfadfd`

The hardening:

- normalizes repository source identifiers to forward-slash, repo-relative form;
- writes generated JSON, Markdown, and classifier CSV with explicit LF line endings;
- adds direct tests for separator normalization, repo-relative identifiers, and LF bytes;
- does not change taxonomy thresholds, labels, episode ordering, subtype calculations, feature ranking, runtime state, NAV, orders, or exposure.

## Generated artifacts

Classifier outputs:

- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_classified_episodes.csv`
- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_classified_episodes.json`
- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_summary.json`

Report outputs:

- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_report.json`
- `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_report.md`

Generated `artifacts/*` remain intentionally ignored and must not be committed unless explicitly authorized.

## Current verification gate

Do not merge PR #40 until the portability-hardened branch head is verified against the real data-bearing artifact set.

Required acceptance evidence:

- focused portability, classifier, and report tests pass;
- classifier still produces exactly 122 episodes;
- new taxonomy digest is captured;
- classifier CSV, JSON, and summary are byte-identical across replay;
- report JSON and Markdown are generated from the real artifacts;
- new report digest is captured;
- report JSON and Markdown are byte-identical across replay;
- full repository suite passes;
- report counts and qualitative findings remain unchanged;
- original source artifacts remain unmodified;
- generated artifacts remain uncommitted;
- work remains research-only and observation-only.

## Next executable step

From the data-bearing checkout on `feature/core-v1-historical-regime-taxonomy`:

1. Pull the latest PR #40 head with fast-forward only.
2. Run the three focused suites:

```powershell
python -m pytest `
    tests/test_historical_regime_artifact_io.py `
    tests/test_historical_regime_taxonomy.py `
    tests/test_historical_regime_taxonomy_report.py `
    -q
```

3. Run the classifier, capture the new taxonomy digest, and verify byte-identical replay for all three classifier outputs.
4. Run the report, capture the new report digest, and verify byte-identical replay for JSON and Markdown.
5. Run `python -m pytest -q`.
6. Confirm report counts and findings still reconcile to the 122-episode taxonomy.
7. Update this board and PR #40 with the final digests and verification results.
8. Only then merge PR #40.

## Recommended next campaign after merge

### Deterministic overlap-aware historical event families

The strongest next research task is an observation-only event-family rollup that addresses the principal methodological limitation of the current analysis: many episode rows come from overlapping rolling windows and are dependent observations.

Start with a specification-only milestone. Define a deterministic, replay-safe method to group overlapping or immediately adjacent collapse windows into auditable event families and report both episode-level and event-family-level summaries.

Required design constraints:

- deterministic interval-based grouping only;
- no learned clustering;
- explicit source episode membership for every event family;
- stable ordering and digest;
- no deletion or mutation of existing episode artifacts;
- descriptive event-level counts, durations, recovery outcomes, subtype composition, and latest-window similarity;
- explicit handling of mixed subtype/recovery labels within a family;
- research-only and observation-only;
- no runtime integration, threshold change, model retraining, order, NAV, or exposure mutation.

This recommendation is not yet an active implementation authorization. Begin only after PR #40 merges and the user explicitly selects the next campaign.

## Explicitly deferred

- runtime integration;
- threshold changes;
- Core exposure changes;
- learned clustering;
- predictive recovery modeling;
- calibrated recovery probabilities;
- automated production actions from taxonomy labels.

## Calendar operating cadence

- **Daily Mission Check:** choose one concrete finish line, identify the next executable command or edit, and leave the branch resumable.
- **Weekly Campaign Review:** record shipped evidence, blockers, roadmap changes, next acceptance criteria, and update this board.
- **Current milestone status:** Taxonomy portability verification pending.

## New-chat handoff prompt

Use this prompt in a fresh ChatGPT conversation:

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test`, verify the current branch and PR #40 state, and continue from the documented portability-verification step. Preserve deterministic, replay-safe, observation-only, and fail-closed constraints. Do not introduce runtime integration, threshold changes, orders, NAV, or exposure mutation.

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
