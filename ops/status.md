# Itera Dynamics — Status

_Overwrite this file each session. This is a snapshot, not a log — history lives in campaign-log.md and decisions.md._

**Last updated:** 2026-09-04

## 🔴 Needs CEO decision
- [ ] none currently

## 🟡 Blocked (no action available from CEO)
- **Campaign #58 Phase 0 (cross-sectional COT census) — blocked on data/network access, not a decision.** This session's environment has no outbound network access to any market-data source (verified: proxy-level 403 on `cftc.gov`, `deribit.com`, and generic internet hosts alike) and no COT positioning history is committed to this repo. The Red Team's required effective-breadth measurement for Campaign #58's own proposed universe cannot be run until a future session has real data/network access — same class of gap as Campaign #57's VTI/BND block below. Full record: `docs/research/CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md` §2.
- **Campaign #57 — independent Red Team has passed conditionally; VTI/BND stays sealed pending its binding conditions.** Verdict: `CONDITIONAL_PASS_TO_VTI_BND_REPLICATION` (`docs/research/CAMPAIGN_57_INDEPENDENT_RED_TEAM_REVIEW_20260902.md`). No defect fatal to the primary result was found, but VTI/BND may not be opened until: (1) raw artifacts/source manifests are committed and VFINX/VBMFX series continuity is verified — this session could not download any price data at all (Yahoo/Vanguard/SEC EDGAR all returned HTTP 403 through the proxy), so this is blocked on a future session with data access, not a decision; (2) a quantitative VTI/BND expectation band (rho in [-0.32, -0.10]) is pre-registered before any VTI/BND return is read; (3) unit tests are added to the Campaign #57 code. Two material corrections were also made to the existing record (57.8% calendar overlap between the long-history "confirmation" pair and the original sandbox discovery pair; Amendment 2's stated power rationale for weakening the statistical gate was wrong at the actual sample size) — neither reopens or re-runs the primary result, both are documented corrections. Campaign #57 remains `HISTORICAL_CONFIRMATION_CONDITIONAL`, not `ALIVE`.
- Campaign #53 confirmation — CDE live-forward funding holdout accumulating since 2026-08-24; do not open early. Basis ladder is also accumulating toward a full roll-cycle observation.
- Defined-risk equity VRP — research remains promising but execution quality is the binding unknown; spread-capable brokerage/options approval remains the external gate before real fill-quality work.
- Core v2 Tier 2 risk framework — Risk/PM owes the real `crash_short_v6` CDE margin schedule by 2026-09-13; 30% interim conservative margin assumption governs until then.

## 🟢 In motion (no action needed)
- **Campaign #58 Phase 1 — CLOSED_UNDERPOWERED (CEO 2026-09-04).** Grid-level power FAIL at 45.8% vs 50% floor on the frozen 144-candidate grid (central IC 0.065; Family R 54.9%, M 41.8%, V 40.6%) remains binding after independent review `ORIGINAL_POWER_FAIL_VALID`. Time-series track closed; no model fit authorized. Phase 0 remains open (see blocked). Full record: `ops/decisions.md` (2026-09-04), `docs/research/CAMPAIGN_58_GRID_POWER_CALIBRATION_IMPLEMENTATION_REVIEW.md`.
- **ML Lab (branch `agent/ml-lab-exploration-20260903`):** Experiment 011 closed `EXPLORATORY_TRANSFER_FAILURE`; Experiment 012 specification frozen, not implemented/not run. Separate from Campaign #58. See `docs/ITERA_CAMPAIGN_BOARD.md` (2026-09-04 ML Lab note).
- **Recovery Trust Gate retroactively closed** 2026-09-03 — documentation-only: `docs/research/RECOVERY_TRUST_GATE_RETROACTIVE_CLOSURE.md`.
- **Campaign #57 — Month-End Equity/Bond Rebalancing Pressure:** `HISTORICAL_CONFIRMATION_CONDITIONAL`; independent Red Team `CONDITIONAL_PASS_TO_VTI_BND_REPLICATION`; VTI/BND sealed pending binding conditions (see blocked).
- Exploration sandbox adopted 2026-09-01. Month-end screen promoted to #57. Dealer-gamma SCREEN_NEGATIVE. Distance-method pairs and low-vol factor CLOSED_NEGATIVE.
- Campaign #56 — rates/duration trend sleeve chartered 2026-08-30; gates 0-3 pass; gate 4 power simulation remains next. No specification frozen.
- Pod degradation bands and Tier 2 Core v2 risk framework adopted 2026-08-30.

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
1. Campaign #58 Phase 0 (cross-sectional COT census): still open; blocked on data/network access for effective-breadth measurement. Phase 1 time-series track is **closed underpowered** (CEO 2026-09-04). Real model-fitting remains not authorized.
2. Campaign #57: independent Red Team conditional pass; next step requires real network/data access (VFINX/VBMFX artifacts, unit tests, pre-register VTI/BND band) before any VTI/BND returns are read.
3. Run Campaign #56's real-data regime census and Amendment 1 power simulation in a later session under its charter.
4. Let Campaign #53 and VRP external clocks accumulate without peeking/routing around their gates.
5. ML Lab Experiment 012 (implement frozen compact-macro-interactions spec) only when it does not interfere with the governed queue above; remains exploratory / non-confirmatory.
