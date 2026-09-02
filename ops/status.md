# Itera Dynamics — Status

_Overwrite this file each session. This is a snapshot, not a log — history lives in campaign-log.md and decisions.md._

**Last updated:** 2026-09-02

## 🔴 Needs CEO decision
- None from Campaign #57 at this stage. Independent Red Team owns the next gate and cannot be bypassed by CIO/Quant judgment.

## 🟡 Blocked (no action available from CEO)
- **Campaign #57 — independent Red Team required:** the one-shot VFINX/VBMFX long-history historical confirmation passed its frozen primary test but returned `HISTORICAL_CONFIRMATION_CONDITIONAL` because the 1990s decade had a small wrong-sign rho. VTI/BND remains sealed until a genuinely independent Red Team review decides whether the conditional result is sufficient to proceed to modern cross-instrument replication.
- Campaign #53 confirmation — CDE live-forward funding holdout accumulating since 2026-08-24; do not open early. Basis ladder is also accumulating toward a full roll-cycle observation.
- Defined-risk equity VRP — research remains promising but execution quality is the binding unknown; spread-capable brokerage/options approval remains the external gate before real fill-quality work.
- Core v2 Tier 2 risk framework — Risk/PM owes the real `crash_short_v6` CDE margin schedule by 2026-09-13; 30% interim conservative margin assumption governs until then.

## 🟢 In motion (no action needed)
- **Campaign #57 — Month-End Equity/Bond Rebalancing Pressure:** sandbox `SCREEN_POSITIVE` remains intact. The original VTI/BND 50/25/25 validation architecture is permanently `HISTORICAL_ARCHITECTURE_UNDERPOWERED`. Validation Architecture Amendment 2 then passed timestamp-only long-history power at 85.2% for the frozen 50%-haircut effect across 476 valid VFINX/VBMFX months. The one-shot historical confirmation subsequently passed the primary test: Spearman rho `-0.1524487`, one-sided 10,000-permutation p `0.00039996`. Required robustness was strong except for decade consistency: 1980s `-0.344`, 1990s `+0.0287`, 2000s `-0.174`, 2010s `-0.299`, 2020s `-0.0990`. All leave-one-year-out aggregate rhos remained negative; removing the 10 largest absolute-signal months left rho `-0.1182`; the causal low-minus-high spread was `+0.5033%`; actual month-end rho remained stronger than all frozen -5/-10/-15-session placebos. Classification is therefore `HISTORICAL_CONFIRMATION_CONDITIONAL`, not clean confirmation. Result record: `docs/research/CAMPAIGN_57_LONG_HISTORY_CONFIRMATION_RESULT.md`. VTI/BND remains sealed pending independent Red Team.
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
2. Single return source — Campaign #53 funding/carry discovery is positive but unconfirmed; defined-risk VRP is promising but execution-gated; Campaign #57 has now produced a statistically strong but robustness-conditional historical confirmation and awaits independent Red Team.
3. No rates/fixed-income exposure — Campaign #56 is the active research thread; power gate not yet run.
4. Single-name crypto concentration — open. Campaign #53's current statistical execution scope is BTC/ETH only and does not solve broad cross-sectional crypto exposure.

## Research queue
1. Campaign #57: run genuinely independent Red Team against Amendment 2, the frozen confirmation runner, raw result, and source identities without CIO/Quant narrative framing. Do not open VTI/BND before that verdict.
2. Run Campaign #56's real-data regime census and Amendment 1 power simulation in a later session under its charter.
3. Let Campaign #53 and VRP external clocks accumulate without peeking/routing around their gates.
4. Continue exploration-sandbox alpha hunting only when it does not interfere with the governed queue above.
