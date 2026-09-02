# Itera Dynamics — Status

_Overwrite this file each session. This is a snapshot, not a log — history lives in campaign-log.md and decisions.md._

**Last updated:** 2026-09-02

## 🔴 Needs CEO decision
- None from Campaign #57 at this stage. The mandatory independent Red Team gate has now run (see below); Risk/PM and CEO approval are the remaining gates before any `ALIVE`/Core v2/capital language, but neither is ripe yet — VTI/BND itself is still sealed pending the Red Team's own binding conditions.

## 🟡 Blocked (no action available from CEO)
- **Campaign #57 — independent Red Team has passed conditionally; VTI/BND stays sealed pending its binding conditions.** Verdict: `CONDITIONAL_PASS_TO_VTI_BND_REPLICATION` (`docs/research/CAMPAIGN_57_INDEPENDENT_RED_TEAM_REVIEW_20260902.md`). No defect fatal to the primary result was found, but VTI/BND may not be opened until: (1) raw artifacts/source manifests are committed and VFINX/VBMFX series continuity is verified — this session could not download any price data at all (Yahoo/Vanguard/SEC EDGAR all returned HTTP 403 through the proxy), so this is blocked on a future session with data access, not a decision; (2) a quantitative VTI/BND expectation band (rho in [-0.32, -0.10]) is pre-registered before any VTI/BND return is read; (3) unit tests are added to the Campaign #57 code. Two material corrections were also made to the existing record (57.8% calendar overlap between the long-history "confirmation" pair and the original sandbox discovery pair; Amendment 2's stated power rationale for weakening the statistical gate was wrong at the actual sample size) — neither reopens or re-runs the primary result, both are documented corrections. Campaign #57 remains `HISTORICAL_CONFIRMATION_CONDITIONAL`, not `ALIVE`.
- Campaign #53 confirmation — CDE live-forward funding holdout accumulating since 2026-08-24; do not open early. Basis ladder is also accumulating toward a full roll-cycle observation.
- Defined-risk equity VRP — research remains promising but execution quality is the binding unknown; spread-capable brokerage/options approval remains the external gate before real fill-quality work.
- Core v2 Tier 2 risk framework — Risk/PM owes the real `crash_short_v6` CDE margin schedule by 2026-09-13; 30% interim conservative margin assumption governs until then.

## 🟢 In motion (no action needed)
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
1. Campaign #57: independent Red Team has passed conditionally (`CONDITIONAL_PASS_TO_VTI_BND_REPLICATION`,
   `docs/research/CAMPAIGN_57_INDEPENDENT_RED_TEAM_REVIEW_20260902.md`). Next step, in a later session with real
   network/data access: acquire and commit raw VFINX/VBMFX artifacts and source manifests (this session's proxy
   blocked Yahoo/Vanguard/SEC EDGAR — HTTP 403 on all three), verify VFINX/VBMFX series continuity through
   2026-08, add unit tests to the Campaign #57 code (lookahead canary, causal-label canary, null/positive-control
   calibration, matching Campaigns #50-53 practice), then pre-register the VTI/BND expectation band (rho in
   [-0.32, -0.10]) before reading any VTI/BND return. Do not open VTI/BND before all of that is done.
2. Run Campaign #56's real-data regime census and Amendment 1 power simulation in a later session under its charter.
3. Let Campaign #53 and VRP external clocks accumulate without peeking/routing around their gates.
4. Continue exploration-sandbox alpha hunting only when it does not interfere with the governed queue above.
