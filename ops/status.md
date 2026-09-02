# Itera Dynamics — Status

_Overwrite this file each session. This is a snapshot, not a log — history lives in campaign-log.md and decisions.md._

**Last updated:** 2026-09-02

## 🔴 Needs CEO decision
- **Month-end equity/bond rebalancing pressure:** sandbox screen passed its frozen gate and a separately frozen month-end-specificity placebo. CIO recommendation is to promote it into the normal governed research pipeline as a new campaign; CEO approval is required to charter the direction. Promotion handoff: `docs/research/MONTH_END_REBALANCE_PROMOTION_HANDOFF.md`. No Core v1/Core v2/runtime/portfolio/paper/live action is authorized by the sandbox result.

## 🟡 Blocked (no action available from CEO)
- Campaign #53 confirmation — CDE live-forward funding holdout accumulating since 2026-08-24; do not open early. Basis ladder is also accumulating toward a full roll-cycle observation.
- Defined-risk equity VRP — research remains promising but execution quality is the binding unknown; spread-capable brokerage/options approval remains the external gate before real fill-quality work.
- Core v2 Tier 2 risk framework — Risk/PM owes the real `crash_short_v6` CDE margin schedule by 2026-09-13; 30% interim conservative margin assumption governs until then.

## 🟢 In motion (no action needed)
- Exploration sandbox adopted 2026-09-01: `docs/ITERA_EXPLORATION_SANDBOX.md`; Amendment 6 added to `docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md`.
- Month-end equity/bond rebalancing exploration — `SCREEN_POSITIVE`: 275 valid months, primary 3-session rho -0.2486 (permutation p=0.000999), causal low-minus-high relative-return spread +0.8478% (p=0.001998), all leave-one-year-out aggregate rhos negative. Frozen -5/-10/-15-session placebo windows were all weaker than actual month-end. Awaiting CEO promotion decision; independent Red Team still required before `ALIVE`.
- Index-options dealer gamma pressure exploration — `SCREEN_NEGATIVE`: frozen dealer-directional sign story failed all horizons; reversed sign performed better at 2d/5d, so no promotion.
- Distance-method pairs trading exploration — CLOSED_NEGATIVE: Sharpe -0.98, worse than 100/100 random-pair controls after correcting universe/timestamp infrastructure defects.
- Low-volatility factor exploration — CLOSED_NEGATIVE: Sharpe -0.30, underperformed random-split control; no reason to continue this implementation.
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
2. Single return source — Campaign #53 funding/carry discovery is positive but unconfirmed; defined-risk VRP is promising but execution-gated; month-end rebalancing is now a sandbox-positive candidate awaiting governed-campaign authorization.
3. No rates/fixed-income exposure — Campaign #56 is the active research thread; power gate not yet run.
4. Single-name crypto concentration — open. Campaign #53's current statistical execution scope is BTC/ETH only and does not solve broad cross-sectional crypto exposure.

## Research queue
1. CEO decision: promote or decline month-end equity/bond rebalancing into a governed campaign.
2. Run Campaign #56's real-data regime census and Amendment 1 power simulation in a later session under its charter.
3. Let Campaign #53 and VRP external clocks accumulate without peeking/routing around their gates.
4. Continue exploration-sandbox alpha hunting only after the promotion decision is resolved or explicitly deferred.
