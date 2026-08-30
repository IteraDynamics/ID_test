# Core v2 — Crash-Short Sleeve (`crash_short_v6`) Live Expectation and Degradation Band

## Status

**RETROACTIVE — filed 2026-08-30**, under the 30-day backfill clause of
`docs/ITERA_DESTINATION_CHARTER.md`'s "Refinement to the One Rule — pre-registered pod
degradation bands (2026-08-30)". Deadline for this filing: 2026-09-29. Filed within the window.

**Honest compliance note.** `crash_short_v6` has been live in Core v2's founding composition at
15% hedge weight since Campaign #54's closure (`docs/research/CAMPAIGN_54_CRASH_SHORT_PLANNING_CHARTER.md`,
2026-08-20). This document did not exist before that funding decision — the rule's item 5
(document git-committed before the funding action, hash cited in the funding record) cannot be
satisfied retroactively, and this is stated plainly rather than glossed over. The rule's own item
6 exists precisely for this case: a backfill within a stated deadline, not an equivalent
substitute for having had the document from day one.

## Honest statement of the evidentiary base

This is not a power-gated result and is not described as one here. Per Campaign #54's own closure
(§4, §7): the governed position is that `crash_short_v6` is included as "a small, asymmetric
component, sized conservatively, monitored for whether the next real bear confirms or contradicts
it" — a judgment call grounded in three historical regimes, not a statistically validated finding.

- **2018** — one genuinely clean, out-of-sample-relative-to-design-history profitable payoff
  (standalone +8.78% BTC / +22.30% ETH for the year).
- **2022** — a profitable payoff (+5.87% BTC / +13.44% ETH) that the sleeve's own design history
  plausibly built its confirmation gate to reproduce — real, but discounted relative to 2018.
- **2020** — the gate fired correctly (all seven conditions, sustained over a month) but the
  standalone sleeve lost money that year (-1.29% BTC / -3.10% ETH) — a correctly-identified regime
  that did not pay off, the sleeve's one documented failure case.
- **Six of eight backtested years (2019, 2020, 2021, 2023, 2024, 2025)** show small, narrow
  standalone losses (-0.12% to -4.80%) — the expected cost-of-insurance pattern for a sleeve that
  only takes risk under a rare, narrow gate.

No live Core v2 record exists yet at the time of this filing — everything above is backtest
evidence, subject to this repo's standing selection-bias convention: **a backtest figure is a
ceiling, never an expectation.**

## Live expectation band

- **Standalone sleeve, most years:** small negative drag, roughly -0.1% to -5% annually — the
  cost-of-insurance pattern observed in 6 of 8 backtested years. This is expected, not a sign of
  failure.
- **Standalone sleeve, a year with a genuine cross-asset-confirmed bear:** a materially positive
  contribution is plausible (backtested precedent: 2018, 2022) but not guaranteed — 2020 shows a
  correctly-fired regime can still lose money.
- **Blended Core v2 composition at 15% hedge weight** (backtested 2019-2025, 2020-2025 OOS,
  `scripts/run_campaign_54_sizing_sweep.py`): CAGR 17.24%, MaxDD -15.75%, Sharpe 1.206, Calmar
  1.094 — versus the no-hedge baseline (CAGR 20.25%, MaxDD -18.85%, Sharpe 1.174, Calmar 1.074).
  These are backtest figures, declared a ceiling per the standing convention above; no haircut
  factor is stated here because no live Core v2 record yet exists to calibrate one. **The first
  full live quarter's reading should be used to propose a live-expectation haircut in a dated
  append to this document — not before, and not by assumption.**

## Re-evaluation triggers

Each trigger is stated as a checkable number and window per the adopted rule's item 2. Each
non-operational trigger forces the same default action per item 3, unless overridden once with a
dated written reason; **a second consecutive firing of the same trigger executes the default
action with no override available.**

**Default action (T1-T4):** halve the hedge weight (15% → 7.5%) within 5 trading days.

- **T1 — Cost-of-insurance breach.** Standalone sleeve trailing 24-month return worse than -8%
  (BTC or ETH) while no cross-asset-confirmed entry (all seven gates, including the SPY 175-day
  SMA confirmation) has fired during that window. A 24-month window is used because the sleeve is
  designed to be dormant most of the time; a shorter window cannot distinguish ordinary cost drag
  from a real problem.
- **T2 — Confirmed-regime underperformance.** An entry fires with all seven gates (including
  cross-asset SPY confirmation) sustained continuously for 20+ trading days — matching or
  exceeding the duration of both 2020 and 2022 — and the sleeve's standalone return over that
  specific episode is worse than -6% BTC / -8% ETH (roughly 2x the worst historically observed
  correctly-fired case, 2020's -1.29% / -3.10%). This directly operationalizes the open question
  Campaign #54's closure left running: whether the next real bear confirms or contradicts 2018's
  clean payoff.
- **T3 — Portfolio-fit failure.** Trailing 12-month realized Calmar of the blended Core v2
  composition (with the 15% hedge live) is worse than the no-hedge configuration's own trailing
  12-month Calmar, for 2 consecutive quarterly readings. This checks whether the hedge is doing
  the one thing it is sized for.
- **T4 — Diversification failure during a fired regime.** Restricted to days with an active
  confirmed entry (all seven gates fired), the trailing Pearson correlation between
  `crash_short_v6`'s daily P&L and the combined SPY+QQQ trend-sleeve daily P&L (Core v1) is ≥ 0.
  Instrument: SPY+QQQ trend sleeves. Statistic: Pearson correlation of daily P&L. Window:
  restricted to active-entry days, evaluated per episode. A positive reading during exactly the
  regime this sleeve exists to diversify against would be direct evidence against the mechanism,
  distinct from ordinary cost drag.

**T5 — Operational integrity (immediate, no override, takes precedence over all other
considerations).** Any unexplained replay mismatch, any divergence of live entry/exit behavior
from `crash_short_v6.py` as coded (Campaign #54 evaluated it with zero modification and zero
perturbation — any live drift from that is itself a finding), or any unexplained divergence
between the sleeve's live state and reconstructed NAV.

## What a re-evaluation authorizes

A triggered re-evaluation authorizes exactly:

1. a documented review comparing live behavior against this document;
2. a written finding: within-plan / degraded / operationally compromised;
3. if degraded or compromised — a decision among: continue with explicit acknowledgment, reduce
   or remove the hedge weight, or charter a new governed campaign.

A re-evaluation never authorizes in-place modification of `crash_short_v6`'s coded gates or exit
logic (Campaign #54's own frozen specification: "exactly as coded... zero perturbation"), nor
retroactive restatement of the record.

## Within-plan outcomes (recorded to prevent future panic)

Small negative annual drag in most years; a confirmed entry (all seven gates fired) that still
loses money, as 2020 did, is within plan by itself and does not alone trigger re-evaluation —
only T2's specific magnitude threshold does. A single quarter of the blended composition trailing
the no-hedge configuration on Calmar is within plan; two consecutive quarters is T3.

## Authorization boundary

This document authorizes monitoring, reporting, and the re-evaluation procedure above. It does
not authorize any change to `crash_short_v6`'s code, Core v2's composition weights, or any
capital, runtime, or production change beyond what Campaign #54's own closure already authorized.
