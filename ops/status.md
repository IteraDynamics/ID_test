# Itera Dynamics — Status

_Overwrite this file each session. This is a snapshot, not a log — history
lives in campaign-log.md and decisions.md._

**Last updated:** [date]

## 🔴 Needs CEO decision
- [ ] none currently

## 🟡 Blocked (no action available from CEO)
- [dependency] — owner: [seat] — since: [date]

## 🟢 In motion (no action needed)
- Pod degradation bands for `crash_short_v6` (retroactive) and the equity-options sleeve
  (prospective) filed 2026-08-30, ahead of the 2026-09-29 deadline —
  `docs/research/CORE_V2_CRASH_SHORT_DEGRADATION_BAND.md`,
  `docs/research/CORE_V2_VRP_OPTIONS_DEGRADATION_BAND.md`.
- Tier 2 risk framework (`docs/CORE_V2_RISK_FRAMEWORK.md`) ADOPTED 2026-08-30, three rounds of
  independent review (Ops/Compliance, CIO, Red Team). Risk/PM owes `crash_short_v6`'s real CDE
  margin schedule by **2026-09-13** (14-day deadline); a 30% interim conservative margin
  assumption governs until then. Aggregate moonshot-bucket cap (a number, not the methodology,
  which is now frozen) still waits on a second live pod — see the framework's "Still open" section.
- Two CEO decisions named in the risk framework are open but not urgent: the VRP sleeve's
  risk-budget % (moot until its brokerage account clears) and whether the quarterly correlation
  recompute should be tightened.
- **Campaign #56 (rates/duration trend sleeve) chartered 2026-08-30** — gates 0-3 pass, gate 4
  scoped (not run). Next step: pull real SHY/IEI/IEF/TLT data and run the actual power
  simulation, on a later session per the pacing rule. See
  `docs/research/CAMPAIGN_56_RATES_DURATION_TREND_PLANNING_CHARTER.md`.

## Fund constraints (keep current)
- Jurisdiction: [e.g. US — Binance/Bybit unreachable]
- Execution venue(s): [e.g. Coinbase Derivatives — crypto perps]
- Capital scale: [e.g. ~$100k]
- Runtime cadence: [e.g. ~0.5-0.6 effective bars behind bar close]

## Open deficiencies (Core v2, per the One Rule)
1. Structurally long-only — [status: open / addressed by X / blocked]
2. Single return source — [status]
3. No rates/fixed-income exposure — [status]
4. Single-name crypto concentration — [status]
