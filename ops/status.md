# Itera Dynamics — Status

_Overwrite this file each session. This is a snapshot, not a log — history lives in campaign-log.md and decisions.md._

**Last updated:** 2026-09-03

## 🔴 Needs CEO decision
- **Campaign #58 Phase 1 — confirm closure of the time-series track as underpowered?** The duplication concern raised against the 45.8% grid-level power FAIL was independently reviewed by a genuinely separate reviewer, not told which outcome anyone preferred — verdict `ORIGINAL_POWER_FAIL_VALID`. Its own synthetic experiment, using this repo's real simulator functions, found zero measurable power difference between duplicate and independently-drawn fillers (0.0000 ± 0.0009 across 8 seeds), with a positive control confirming the test harness is genuinely sensitive to family size when size actually changes (~32% real drop, 8→16 hypotheses). The concern was also self-reportedly post-hoc. **45.8% is now recorded as binding, not provisional.** Staff's recommendation, consistent with how this fund has closed other underpowered designs: close Phase 1's time-series track as underpowered. Phase 0 (COT cross-sectional) is unaffected — still open, blocked on data access, not on this result. Full record: `docs/research/CAMPAIGN_58_GRID_POWER_CALIBRATION_IMPLEMENTATION_REVIEW.md`, `docs/ITERA_CAMPAIGN_BOARD.md` (2026-09-03 same-day correction).
- None from Campaign #57 at this stage. The mandatory independent Red Team gate has now run (see below); Risk/PM and CEO approval are the remaining gates before any `ALIVE`/Core v2/capital language, but neither is ripe yet — VTI/BND itself is still sealed pending the Red Team's own binding conditions.

## 🟡 Blocked (no action available from CEO)
- **Campaign #58 Phase 0 (cross-sectional COT census) — blocked on data/network access, not a decision.** This session's environment has no outbound network access to any market-data source (verified: proxy-level 403 on `cftc.gov`, `deribit.com`, and generic internet hosts alike) and no COT positioning history is committed to this repo. The Red Team's required effective-breadth measurement for Campaign #58's own proposed universe cannot be run until a future session has real data/network access — same class of gap as Campaign #57's VTI/BND block below. Full record: `docs/research/CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md` §2.
- **Campaign #57 — independent Red Team has passed conditionally; VTI/BND stays sealed pending its binding conditions.** Verdict: `CONDITIONAL_PASS_TO_VTI_BND_REPLICATION` (`docs/research/CAMPAIGN_57_INDEPENDENT_RED_TEAM_REVIEW_20260902.md`). No defect fatal to the primary result was found, but VTI/BND may not be opened until: (1) raw artifacts/source manifests are committed and VFINX/VBMFX series continuity is verified — this session could not download any price data at all (Yahoo/Vanguard/SEC EDGAR all returned HTTP 403 through the proxy), so this is blocked on a future session with data access, not a decision; (2) a quantitative VTI/BND expectation band (rho in [-0.32, -0.10]) is pre-registered before any VTI/BND return is read; (3) unit tests are added to the Campaign #57 code. Two material corrections were also made to the existing record (57.8% calendar overlap between the long-history "confirmation" pair and the original sandbox discovery pair; Amendment 2's stated power rationale for weakening the statistical gate was wrong at the actual sample size) — neither reopens or re-runs the primary result, both are documented corrections. Campaign #57 remains `HISTORICAL_CONFIRMATION_CONDITIONAL`, not `ALIVE`.
- Campaign #53 confirmation — CDE live-forward funding holdout accumulating since 2026-08-24; do not open early. Basis ladder is also accumulating toward a full roll-cycle observation.
- Defined-risk equity VRP — research remains promising but execution quality is the binding unknown; spread-capable brokerage/options approval remains the external gate before real fill-quality work.
- Core v2 Tier 2 risk framework — Risk/PM owes the real `crash_short_v6` CDE margin schedule by 2026-09-13; 30% interim conservative margin assumption governs until then.

## 🟢 In motion (no action needed)
- **Campaign #58 Phase 1 — statistical specification frozen (144-candidate grid: 16 feature-variants × 3 horizons × 3 outcome families R/M/V) and independently Red-Teamed (`CONDITIONAL_PASS`, 10 conditions, all applied same day).** Corrections applied: the material-margin threshold for "ML beats simple" recalibrated from an untested flat 0.02 to the census's own central-IC-implied effect size (≈0.0042); the negative-control and lift-FDR tests now explicitly replicate the full model-selection procedure at each resample rather than fixing the model choice; the underpowered-feature interpretation list is explicitly closed to its 3 named features; the charter's own Risk/PM correlation-to-Core-NAV check is reinstated into the decision rules. Grid-level power test run for real (FAIL, 45.8%) and the resulting duplication concern independently reviewed and rejected — see 🔴 above for the binding result and pending closure sign-off.
- **Recovery Trust Gate retroactively closed** 2026-09-03 — an ungoverned ~3,000-line ML program (Logistic/RF/GBM gating Core's own re-risk decisions) that ran to a diagnostic negative and was then abandoned outside governance. Closure is documentation-only (no new data touched, no code re-run): `docs/research/RECOVERY_TRUST_GATE_RETROACTIVE_CLOSURE.md`. Done within staff's routine authority (closing on an already-existing negative result), independent of the Campaign #58 CEO decision above.
- **Campaign #57 — Month-End Equity/Bond Rebalancing Pressure:** sandbox `SCREEN_POSITIVE` remains intact. The original VTI/BND 50/25/25 validation architecture is permanently `HISTORICAL_ARCHITECTURE_UNDERPOWERED`. Validation Architecture Amendment 2 then passed timestamp-only long-history power at 85.2% for the frozen 50%-haircut effect across 476 valid VFINX/VBMFX months. The one-shot historical confirmation subsequently passed the primary test: Spearman rho `-0.1524487`, one-sided 10,000-permutation p `0.00039996`. Required robustness was strong except for decade consistency: 1980s `-0.344`, 1990s `+0.0287`, 2000s `-0.174`, 2010s `-0.299`, 2020s `-0.0990`. All leave-one-year-out aggregate rhos remained negative; removing the 10 largest absolute-signal months left rho `-0.1182`; the causal low-minus-high spread was `+0.5033%`; actual month-end rho remained stronger than all frozen -5/-10/-15-session placebos. Classification is therefore `HISTORICAL_CONFIRMATION_CONDITIONAL`, not clean confirmation. Result record: `docs/research/CAMPAIGN_57_LONG_HISTORY_CONFIRMATION_RESULT.md`. **Independent Red Team has now reviewed this result** (`CONDITIONAL_PASS_TO_VTI_BND_REPLICATION`, see blocked item above and `docs/research/CAMPAIGN_57_INDEPENDENT_RED_TEAM_REVIEW_20260902.md`) — VTI/BND remains sealed pending that review's own binding conditions, not pending Red Team itself anymore.
- Exploration sandbox adopted 2026-09-01: `docs/ITERA_EXPLORATION_SANDBOX.md`; Amendment 6 added to `docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md`.
- Month-end equity/bond rebalancing exploration — `SCREEN_POSITIVE`, promoted to Campaign #57 by explicit CEO authorization.
- Index-options dealer gamma pressure exploration — `SCREEN_NEGATIVE`.
- Distance-method pairs trading exploration — CLOSED_NEGATIVE.
- Low-volatility factor exploration — CLOSED_NEGATIVE.
- Campaign #56 — rates/duration trend sleeve chartered 2026-08-30; gates 0-3 pass, gate 4 power simulation remains the next campaign step. No specification is frozen.
- Pod degradation bands for `crash_short_v6` and the prospective equity-options sleeve filed 2026-08-30.
- Tier 2 Core v2 risk framework adopted 2026-08-30.

## Fund constraints
- Jurisdiction: United States; venue/product access must be verified rather than assumed.
- Current crypto execution venue: Coinbase Derivatives Exchange where applicable; research/execution venue mismatches require explicit treatment.
- Capital scale: approximately $100,000.
- Measured fresh-bar reaction cadence: approximately 0.5-0.6 hours after bar close on the corrected 2026-08-20 audit; re-measure when a new campaign depends on it.
- Core v1: frozen. No exploration, campaign, staff consensus, or Core v2 work may mutate its live parameters, weights, or logic.

## Open deficiencies (Core v2)
1. Structurally long-only — provisionally addressed by `crash_short_v6`; evidence/sizing remain judgment-bound and governed as a separate pod.
2. Single return source — Campaign #53 funding/carry discovery is positive but unconfirmed; defined-risk VRP is promising but execution-gated; Campaign #57 has now produced a statistically strong but robustness-conditional historical confirmation, cleared independent Red Team conditionally, and awaits closing the Red Team's binding conditions before VTI/BND modern replication.
3. No rates/fixed-income exposure — Campaign #56 is the active research thread; power gate not yet run.
4. Single-name crypto concentration — open. Campaign #53's current statistical execution scope is BTC/ETH only and does not solve broad cross-sectional crypto exposure.

## Research queue
1. Campaign #58 (Itera Residual Predictability Census): Phase 1's statistical specification is
   frozen and independently Red-Teamed (`CONDITIONAL_PASS`, 10 conditions, applied). The
   grid-level power check ran for real: **FAIL, 45.8%, now recorded as binding** after an
   independent review rejected the post-hoc duplication concern raised against it (see 🔴 above
   for the closure sign-off awaiting your confirmation). Real model-fitting remains not
   authorized under the standing 2026-09-03 authorization regardless. Phase 0 remains blocked on
   data/network access (see 🟡 above).
2. Campaign #57: independent Red Team has passed conditionally (`CONDITIONAL_PASS_TO_VTI_BND_REPLICATION`,
   `docs/research/CAMPAIGN_57_INDEPENDENT_RED_TEAM_REVIEW_20260902.md`). Next step, in a later session with real
   network/data access: acquire and commit raw VFINX/VBMFX artifacts and source manifests (this session's proxy
   blocked Yahoo/Vanguard/SEC EDGAR — HTTP 403 on all three), verify VFINX/VBMFX series continuity through
   2026-08, add unit tests to the Campaign #57 code (lookahead canary, causal-label canary, null/positive-control
   calibration, matching Campaigns #50-53 practice), then pre-register the VTI/BND expectation band (rho in
   [-0.32, -0.10]) before reading any VTI/BND return. Do not open VTI/BND before all of that is done.
3. Run Campaign #56's real-data regime census and Amendment 1 power simulation in a later session under its charter.
4. Let Campaign #53 and VRP external clocks accumulate without peeking/routing around their gates.
5. Continue exploration-sandbox alpha hunting only when it does not interfere with the governed queue above.
