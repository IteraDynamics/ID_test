# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Future ChatGPT conversations should read this file before proposing or implementing the next step.

The board is descriptive project state. It does not authorize production, threshold, order, NAV, exposure, or runtime changes.

## Active campaign

**Campaign:** Core v1 Historical Regime Taxonomy

**Status:** Active — classifier verified on real artifacts; reporting implementation committed and awaiting data-bearing checkout verification

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
- Focused suite `tests/test_historical_regime_taxonomy.py`: 6 passed.
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
- Subtype feature reporting must therefore use the numeric episode-signature artifact.
- Deterministic feature ranking is median absolute standardized signature descending, then feature name ascending; median signed signature preserves direction.

## Current milestone

### Human-readable taxonomy report

Build and run a deterministic reporting layer over the verified real historical taxonomy artifacts.

The report should let a human understand the historical regime distribution in approximately two minutes without inspecting raw CSV or JSON files.

### Reporting implementation committed

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

Synthetic preflight completed before commit:

- Combined focused suite: 10 passed.
- Synthetic JSON and Markdown report artifacts were byte-identical across replay.

These synthetic checks do not replace verification against the real data-bearing artifacts or the full repository test suite.

### Required report outputs

At minimum, report:

- total episodes analyzed;
- taxonomy digest and report digest;
- counts by collapse severity;
- counts by feature displacement;
- counts by volatility state;
- counts by recovery outcome;
- counts by composite regime label;
- recovered fraction by intrinsic subtype;
- median recovery rows by intrinsic subtype where recovery occurred;
- median activation ratio by subtype;
- median or average similarity-to-current by subtype;
- dominant subtypes;
- top shifted features by subtype from the numeric signature artifact;
- explicit overlapping-window and bounded-censoring caveats.

## Verified branch state

Verified immediately before this board update on 2026-07-22:

- `feature/core-v1-historical-regime-taxonomy` was 13 commits ahead of `main` and 0 commits behind.
- This board update adds documentation only.
- Generated `artifacts/*` and `data/*.csv` remain intentionally ignored.
- No runtime, threshold, order, NAV, or exposure files were changed by the committed implementation.

## Next executable step

From the data-bearing checkout:

1. Discard or stash only the two tracked local edits that are now incorporated in the remote branch:
   - `scripts/run_core_v1_historical_regime_taxonomy.py`
   - `tests/test_historical_regime_taxonomy.py`
2. Pull `feature/core-v1-historical-regime-taxonomy` with fast-forward only.
3. Run the focused taxonomy and report tests.
4. Run the report runner against the verified real artifacts.
5. Capture the report digest and generated JSON/Markdown paths.
6. Run the report runner a second time and confirm byte-identical JSON and Markdown.
7. Run the full repository test suite.
8. Inspect the Markdown report for clarity and fidelity to the generated JSON.
9. Update this board with real report verification, full-suite status, and the next decision.

Do not commit generated report artifacts unless explicitly authorized; repository rules currently ignore `artifacts/*`.

## Acceptance criteria

- Real classifier execution remains 122 episodes with taxonomy digest `7e18d3a9f963029588d01deaa27427279c172a1d948cf696a0df79d91142b547`.
- Focused classifier and report tests pass on the data-bearing checkout.
- Report JSON and Markdown are generated from real artifacts.
- Report output is deterministic and byte-identical across replay.
- Report counts reconcile to the taxonomy summary.
- Subtype feature rankings use the numeric signature artifact, not the inherited string field.
- Full repository test suite passes, or any unrelated failure is documented without weakening fail-closed behavior.
- Original source artifacts remain unmodified.
- Work remains research-only and observation-only.
- Branch is committed, pushed, and resumable.

## Open questions

- What report digest is produced by the real 122-episode artifacts?
- Are the generated Markdown and JSON byte-identical across real replay?
- Does the full repository test suite pass with the reporting layer?
- Does the Markdown report communicate the main findings in approximately two minutes without overstating dependent historical observations?

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
- **Current milestone target:** Taxonomy Report Complete.

## New-chat handoff prompt

Use this prompt in a fresh ChatGPT conversation:

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test`, verify the current branch state, and continue the active campaign from the documented next executable step. Preserve deterministic, replay-safe, observation-only, and fail-closed constraints. Do not introduce runtime integration, threshold changes, orders, NAV, or exposure mutation.

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
