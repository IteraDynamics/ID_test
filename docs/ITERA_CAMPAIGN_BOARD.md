# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Future ChatGPT conversations should read this file before proposing or implementing the next step.

The board is descriptive project state. It does not authorize production, threshold, order, NAV, exposure, or runtime changes.

## Active campaign

**Campaign:** Core v1 Historical Regime Taxonomy

**Status:** Complete — classifier and reporting milestones verified on real artifacts; branch ready for review

**Working branch:** `feature/core-v1-historical-regime-taxonomy`

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

### Real taxonomy execution

Verified on 2026-07-22 from a data-bearing Windows checkout using Python 3.14.6:

- Required historical JSON, episode CSV, and signature CSV were present.
- Episode CSV and signature artifact aligned exactly using deterministic positional episode IDs `0` through `121`.
- Focused classifier suite: 6 passed.
- Real classified episode count: 122.
- Deterministic taxonomy digest: `7e18d3a9f963029588d01deaa27427279c172a1d948cf696a0df79d91142b547`.
- Runner exit code: 0.
- Generated artifacts:
  - `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_classified_episodes.csv`
  - `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_classified_episodes.json`
  - `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_summary.json`
- A second run reproduced the same taxonomy digest.
- Summary JSON, classified episode JSON, and classified episode CSV were byte-identical across replay.

### Real output inspection

Observed from the generated taxonomy artifacts:

- Collapse severity: 94 severe, 10 major, 18 moderate.
- Feature displacement: 111 low displacement, 6 broad shift, 5 concentrated shift.
- Volatility state: 114 neutral, 8 expansion.
- Recovery outcome: 29 rapid recovery, 45 delayed recovery, 48 persistent collapse.
- Similarity band: 68 low, 52 medium, 2 high.
- Ten intrinsic subtypes were observed.
- Dominant subtype: `SEVERE_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL`, 87 episodes, descriptive recovered fraction 0.758621, median recovery 1392 rows, median activation ratio 0.0, median similarity-to-current 0.144540.
- The classified artifact's inherited `top_shifted_features` field is a string representation, not a JSON list.
- Subtype feature reporting therefore uses the numeric episode-signature artifact.
- Deterministic feature ranking is median absolute standardized signature descending, then feature name ascending; median signed signature preserves direction.

### Human-readable taxonomy reporting implementation

Created:

- `research/ml/validation/historical_regime_taxonomy_report.py`
- `scripts/run_core_v1_historical_regime_taxonomy_report.py`
- `tests/test_historical_regime_taxonomy_report.py`

Commits:

- report model: `c2e6ce5d7b7125128219f682f7e21699c820a23e`
- report runner: `13aeff95bb9a5a9873d60096eedc4b97486abd10`
- report tests: `8dad4e3fc06f5949e622a7577aed7835ad2ddda1`

The implementation:

- validates exact classified/signature episode identity;
- validates taxonomy summary counts against classified rows;
- validates subtype recovery summaries against the taxonomy summary;
- computes subtype activation, similarity, recovery, and feature metrics deterministically;
- emits compact strict JSON and human-readable Markdown;
- writes JSON and Markdown through temporary files and replacement;
- preserves research-only, observation-only, and no-runtime-mutation flags;
- includes overlapping-window and bounded-censoring caveats.

### Real report execution and replay

Verified on 2026-07-22 from the same data-bearing checkout:

- Combined focused classifier/report suite: 10 passed.
- Real report episode count: 122.
- Source taxonomy digest: `7e18d3a9f963029588d01deaa27427279c172a1d948cf696a0df79d91142b547`.
- Deterministic report digest: `c0717f2227b7fe060cbe71e3010b3ce90800143c3f90c9d90af883c8c1d23198`.
- Report runner exit code: 0.
- Generated report artifacts:
  - `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_report.json`
  - `artifacts/core_v1_jump_risk_historical_regime_taxonomy/btc_extended_up_taxonomy_report.md`
- A second report run reproduced the same embedded report digest.
- Report JSON and Markdown were byte-identical across replay.
- The uploaded report JSON reconciled to 122 episodes, 74 recovered, and 48 persistent.
- The Markdown report was consistent with the compact JSON and included all required distributions, subtype metrics, feature rankings, and caveats.
- Generated report artifacts remain ignored and were not committed.

### Full repository verification

Executed on Windows with Python 3.14.6, pytest 9.1.1:

- Collected: 398 tests.
- Result: 398 passed.
- Exit code: 0.
- Runtime: 233.71 seconds.
- Warnings: 75.
- Warning classes were deprecations involving `datetime.utcnow()` and pytest class-scoped fixture behavior; no test failed and no warning was suppressed as part of this campaign.

## Acceptance result

All campaign acceptance criteria are satisfied:

- Real classifier execution remained at 122 episodes with the verified taxonomy digest.
- Focused classifier and report tests passed on the data-bearing checkout.
- Report JSON and Markdown were generated from real artifacts.
- Taxonomy and report outputs were deterministic and byte-identical across replay.
- Report counts reconciled to the taxonomy summary.
- Subtype feature rankings used the numeric signature artifact rather than the inherited string field.
- The full repository suite passed 398/398.
- Original generated source artifacts were not modified.
- Generated report artifacts were not committed.
- Work remained research-only and observation-only.
- No Core state, model threshold, order, NAV, exposure, or production-runtime behavior changed.

## Verified branch state

Verified on 2026-07-22:

- The working branch was fast-forwarded cleanly into the data-bearing checkout.
- The checkout had no modified tracked files after the pull and verification runs.
- Existing local exports, data manifests, server data, and runtime-state files remained untracked and untouched.
- Generated `artifacts/*` and `data/*.csv` remain intentionally ignored.
- The committed campaign scope is limited to the taxonomy specification, deterministic classifier, report model/runner, focused tests, and campaign-board documentation.

## Next executable step

Review the complete branch diff against `main`, then open a pull request for the completed research-only taxonomy campaign.

The pull request should record:

- 122 real classified episodes;
- taxonomy digest `7e18d3a9f963029588d01deaa27427279c172a1d948cf696a0df79d91142b547`;
- report digest `c0717f2227b7fe060cbe71e3010b3ce90800143c3f90c9d90af883c8c1d23198`;
- focused result: 10 passed;
- full-suite result: 398 passed, 75 warnings;
- deterministic byte-identical taxonomy and report replay;
- research-only and observation-only scope;
- no runtime, threshold, order, NAV, or exposure changes.

Before merge, confirm the PR diff contains no generated artifacts, data files, local exports, or runtime-state files.

## Resolved questions

- Real report digest: `c0717f2227b7fe060cbe71e3010b3ce90800143c3f90c9d90af883c8c1d23198`.
- Real report JSON and Markdown are byte-identical across replay.
- Full repository suite passes with the reporting layer: 398 passed.
- The Markdown report communicates the primary distribution and dominant subtype in its executive sections while preserving explicit dependent-observation and bounded-censoring caveats.

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
- **Current milestone status:** Taxonomy Report Complete.

## New-chat handoff prompt

Use this prompt in a fresh ChatGPT conversation:

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test`, verify the current branch state, and continue from the documented next executable step. Preserve deterministic, replay-safe, observation-only, and fail-closed constraints. Do not introduce runtime integration, threshold changes, orders, NAV, or exposure mutation.

## Board maintenance rule

Update this file whenever one of the following changes:

- active campaign;
- working branch;
- completed milestone;
- test status;
- material research finding;
- blocker or open decision;
- next executable step;
- acceptance criteria;
- deferred scope.

A campaign is not considered cleanly paused until this board identifies a verified state and one concrete next executable step.
