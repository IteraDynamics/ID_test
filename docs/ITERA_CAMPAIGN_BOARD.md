# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Future ChatGPT conversations should read this file before proposing or implementing the next step.

The board is descriptive project state. It does not authorize production, threshold, order, NAV, exposure, or runtime changes.

## Active campaign

**Campaign:** Core v1 Historical Regime Taxonomy

**Status:** Active — classification milestone complete; reporting milestone next

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

Verification:

- Focused suite: `tests/test_historical_regime_taxonomy.py`
- Result: 5 passed.

## Verified branch state

Verified on 2026-07-22 through the GitHub repository interface:

- `feature/core-v1-historical-regime-taxonomy` is 6 commits ahead of `main` and 0 commits behind.
- The campaign board is the only branch change after the recorded pandas 3 / Python 3.14 test-fix commit.
- The taxonomy implementation, runner, specification, and focused tests are present on the working branch.
- Repository rules intentionally ignore generated `artifacts/*` and `data/*.csv` content.

## Current milestone

### Human-readable taxonomy report

Build and run a deterministic reporting layer over the real historical taxonomy artifacts.

The report should let a human understand the historical regime distribution in approximately two minutes without inspecting raw CSV or JSON files.

### Required outputs

At minimum, report:

- total episodes analyzed;
- deterministic digest;
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
- top shifted features by subtype where supported by existing artifacts;
- explicit overlapping-window and bounded-censoring caveats.

### Acceptance criteria

- Run the classifier against the full historical episode and signature inputs.
- Confirm the expected episode count or explain any mismatch.
- Confirm deterministic output and capture the digest.
- Emit a concise human-readable report artifact in addition to machine-readable artifacts.
- Add focused tests for reporting calculations and deterministic ordering.
- Run focused tests and the full repository test suite.
- Preserve original source artifacts without mutation.
- Keep all work research-only and observation-only.
- Commit and push a clean, resumable branch state.

## Current blocker

The required real runner inputs are generated research artifacts and are not committed to the repository:

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`

A remote branch inspection cannot execute the taxonomy runner because these ignored files are unavailable there. No episode count, digest, generated path, schema mismatch, or validation result has been inferred or fabricated. The campaign remains fail-closed until the command is run from a data-bearing checkout containing the original generated artifacts.

## Next executable step

From a data-bearing checkout of `feature/core-v1-historical-regime-taxonomy`, first verify that all three required source artifacts listed above exist. If any are absent, stop and regenerate them only through the existing research-only historical-regime and recovery-subtype scripts against the locked prediction and feature evidence; do not substitute synthetic or assumed values.

Then run:

```powershell
python scripts/run_core_v1_historical_regime_taxonomy.py
```

Capture:

- command output;
- episode count;
- deterministic digest;
- generated paths;
- any schema mismatch or validation failure.

Do not design the reporting layer around assumed output values before this run is completed.

## Open questions

- Do the current historical episode and signature artifacts join cleanly by `episode_id`?
- Does the real episode count equal 122 after validation and deduplication?
- Are top shifted features available directly in the classified artifact, or should they be joined from a separate signature artifact during report generation?
- Should the first report artifact be Markdown only, or Markdown plus a compact JSON report model? Current recommendation: both.

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
