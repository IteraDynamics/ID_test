# Campaign #54 — Macro-Confirmed Crash-Short Hedge Sleeve

## 1. Charter

### Status

**PLANNING CHARTER — drafted 2026-08-13, not frozen.** Per Amendment 3's pacing rule, no
section of this document may be frozen the same session it is first drafted. Section 3 in
particular is explicitly a draft pending a later-day review pass.

No predictor, outcome, ranking, economic result, or runtime change is authorized under this
charter. This is Core v2's second founding thread alongside Campaign #53
(`docs/research/CAMPAIGN_53_FUNDING_CARRY_PLANNING_CHARTER.md`), addressing a different named
deficiency: see `docs/CORE_V2_CHARTER.md`.

### Question

> Does including `crash_short_v6` — an existing, fully-specified, currently-unused strategy
> module — as a standalone sleeve in a Core-v1-style trend/equity/gold blend produce a
> persistent, generalizable improvement in risk-adjusted portfolio outcomes, or does its
> apparent 2022 payoff reflect one historical draw that should not be trusted to repeat?

### Economic mechanism

Core v1's six sleeves are all long-with-filter: each can step aside from a decline by reducing
exposure to zero, but none can profit from one. `crash_short_v6` is the only strategy module in
this codebase capable of expressing negative crypto exposure. Its entry gate requires seven
conditions simultaneously, including a cross-asset confirmation (SPY also below its own
175-day SMA) that distinguishes a macro bear from a crypto-specific correction — the exact
distinction its own docstring identifies as the failure mode of every earlier version (v1-v5).
A sleeve that only takes risk under this narrow, confirmed condition is a genuine diversifying
return source, not merely a defensive filter, if the mechanism is real rather than a fitted
artifact of one bear market.

### Why not already represented

Named directly in `docs/ITERA_DESTINATION_CHARTER.md`'s list of Core v1 deficiencies:
"Structurally long-only. All six sleeves are long-with-filter. The strategy can step aside from
a decline but cannot profit from one." `crash_short_v6` is built, registered in
`research.strategies.REGISTRY`, wired into `scripts/run_multi_strategy_fund.py`'s hedge slot
via the existing `--hedge-weight` CLI flag — and excluded from Core v1's canonical scenario
weights. No new code, venue, or data source is required to test it; the question is whether it
belongs in a standalone Core v2 composition, never whether Core v1 should change.

### Falsification statement

The family is falsified for this design if a properly powered analysis cannot distinguish the
sleeve's contribution from what a single historical crisis realization would produce by chance
— i.e., if the 2022 result cannot be shown to generalize beyond that one draw. Section 4 records
why this is a harder standard to meet here than for a cross-sectional design, and what partial
corroboration is available.

**Appended 2026-08-14, adversarial review — the null model above is too weak.** "By chance" is
not the only alternative explanation for this sleeve's apparent performance. `crash_short_v6` is
the sixth of six iterations, each explicitly built to fix the previous version's failure on a
named historical episode (its own docstring: *"What v5 taught us: 2021 Q2... this is a
crypto-specific correction. Do NOT short. 2022... this is a macro bear market. DO short."*). The
harder, more honest null this campaign actually needs to rule out is not "chance" but
**hindsight fitting** — that the SPY confirmation gate was hand-built by looking at exactly the
episodes now being cited as its validation. Section 4 addresses this directly and downgrades the
strength of the 2021/2022 evidence accordingly. This does not retract the falsification
statement; it corrects the standard it should have been held to from the start.

### Candidate-family sketch

This is not a parameter search. `crash_short_v6` is evaluated exactly as coded — all seven entry
gates, all five exit conditions, `ENTRY_EXPOSURE = 0.50` — with zero perturbation. There is no
grid, because a grid here would repeat exactly the retuning trap
`docs/research/CORE_V1_PARAMETER_SENSITIVITY_RESULT.md` exists to guard against. The question
this campaign answers is inclusion, not calibration; sizing (what weight it receives in a Core
v2 composition) is a separate decision deferred to Closure, after inclusion is answered.

## 2. Feasibility

### Horizon feasibility (Amendment 4)

Amendment 4's framing (decay horizon vs. measured cadence) is built for signals that expire.
`crash_short_v6` is the opposite: it holds a position through a confirmed, sustained regime
(`horizon_hours=120` at entry — five days) rather than acting on a single decaying observation.
Measured runtime cadence is ~1.5-1.7 bar periods (~1.6h on 1H data, `CLAUDE.md`). The margin —
120h against a 1.6h decision lag, roughly 75x — is not the relevant test the way it was for
Jump Risk, but it is stated here for completeness and because it passes trivially either way.

### Tradeability (Amendment 5)

Instrument: BTC/ETH, held short. Venue: the same execution venue as Core v1's crypto sleeves.
Shorting requires derivatives or margin access — **this shared Campaign #53's exact same
blocker, CDE derivatives eligibility. Resolved 2026-08-14: the operator's account was approved
for derivatives trading.** Both threads are unblocked on this specific dependency at once, as
anticipated. This clears account status only — it does not itself authorize execution, which
still requires this section's own frozen specification and its board transition.

### Economic materiality — measured, not assumed

From the blended test already run (`artifacts/core_v2_blend_no_hedge/`,
`artifacts/core_v2_blend_with_hedge/`, 2026-08-13, trend/hedge/equity/gold weights 0.40/0.10/
0.35/0.15 vs. 0.50/0/0.35/0.15, $100k, 2020-2025):

| | No hedge | With hedge (10%) | Δ |
|---|---:|---:|---:|
| CAGR | 20.25% | 18.27% | -1.98pp |
| MaxDD | -18.85% | -16.88% | +1.97pp shallower |
| Sharpe | 1.174 | 1.194 | +0.020 |
| Calmar | 1.074 | 1.082 | +0.008 |

Stated plainly, per this repo's own convention of assessing materiality in dollars before
proceeding: this is a risk-shape trade, not a return-generation one. At $100k and this one
tested weight, roughly -$2,000/yr in expected return for roughly $2,000 less peak-to-trough
drawdown. Small in absolute terms, consistent with this firm's repeated finding that edges here
land in the hundreds-to-low-thousands per year — not a reason to stop, but not to be oversold
either.

**Appended 2026-08-14:** these figures should be read as directionally right, not precisely
reliable. §3c's adversarial finding — that the strategy's own parameters were plausibly shaped by
exposure to the same historical episodes producing this number — applies to the dollar estimate
as much as to the entry-signal validation. An out-of-sample re-estimate would likely differ from
this one; "roughly -$2,000/yr" should not be quoted as a stable expectation.

### Data availability

Already resolved before this document existed: the same governed BTC/ETH/SPY sources used for
Core v1 and for `docs/research/CORE_V1_PARAMETER_SENSITIVITY_RESULT.md`. No new acquisition.

### Support inventory — exploratory results already in hand

Four runs, all via `scripts/run_core_v1_sleeve_contribution_audit.py`, all 2020-2025, all
2026-08-13, report-only:

1. **Standalone, isolated** (`artifacts/core_v2_hedge_only_probe/`): CAGR 0.32%, MaxDD -24.71%,
   Sharpe 0.084, Calmar 0.013. Annual pattern: small losses in 5 of 6 years (-0.12% to -4.80%),
   large gains in 2022 specifically (+5.87% BTC, +13.44% ETH) — the one year this sleeve exists
   for.
2. **Blended, 10% weight** (above table): real, modest, directionally correct improvement in
   Sharpe/Calmar/MaxDD.
3. **Comparative — `trend_following_short_v2`** (`artifacts/core_v2_alt_hedge_probe/`): the
   other existing short-side candidate, standalone CAGR -23.26%, MaxDD -84.39%, Sharpe -0.976.
   Decisively ruled out — and instructive: it lacks `crash_short_v6`'s cross-asset SPY
   confirmation gate, and gets destroyed by crypto's characteristic V-shaped recoveries as a
   result. This is evidence the specific gating mechanism matters, not incidental design.
   **Caveat added on adversarial review:** the comparison's cleanliness is itself worth
   qualifying — if `crash_short_v6` received more iterative refinement against this same
   2018-2022 history than its rival did (plausible; it is the sixth version, the other is the
   second), part of the margin between them may reflect unequal design attention rather than a
   pure lesson about selectivity as a principle. The magnitude of the gap (catastrophic vs.
   modest) makes this a secondary concern, not one that overturns the conclusion — but it
   belongs in the record alongside the primary circularity finding in §3c.
4. **Comparative — `mean_reversion`** (`artifacts/core_v2_mr_only_probe/`): unrelated
   deficiency, ruled out separately (six-for-six losing years, Sharpe -2.001).

## 3. Frozen specification — DRAFT, drafted 2026-08-13

**Not frozen.** Section 4 explains why this section cannot yet commit to a final confirmation
design.

### 3a. Mechanism

`crash_short_v6` exactly as coded, `research/strategies/crash_short_v6.py`. No modification.

### 3b. Primary universe

BTC and ETH, 1H, matching the sleeve as already wired into `scripts/run_multi_strategy_fund.py`.

### 3c. Resolved 2026-08-13 — entry-episode census, and what it does and doesn't establish

`scripts/diagnose_crash_short_entry_episodes.py`, run against the full 2018-2025 reachable
window (not just 2020, and not an approximation — the real `BaselineRegimeEngine` and the exact
formulas from `crash_short_v6.py`), found 126 raw entry-eligible windows. **That raw count is
not 126 independent observations and must not be read as one.** The large majority are 1-20 hour
fragments clustered tightly within a small number of actual regimes — gates 5/6 (EMA spread
persistence, momentum) flicker across their thresholds repeatedly inside one ongoing bear market,
fragmenting a single regime into dozens of raw "episodes." Collapsed to distinct regimes, the
count is roughly four: 2018 (April-January, the "crypto winter" grind), 2020 (COVID), 2022 (the
confirmed case), and two brief, uncertain windows in 2023-03 and 2025.

**2020 is confirmed as a genuine, sustained episode** — all seven gates aligned continuously
from 2020-03-08 to 2020-04-13, over a month, not a blip. That resolves the literal question this
section previously left open.

**But entry-eligibility is not the same claim as profitability, and conflating them would be
exactly the kind of check-that-cannot-fail this repo's culture exists to catch.** The standalone
hedge probe already run for this campaign (`artifacts/core_v2_hedge_only_probe/
scaled_sleeve_annual_returns.csv`) shows 2020 as a **losing** year for this sleeve (-1.27% BTC,
-3.06% ETH) despite the gate firing correctly for over a month — plausibly because COVID's crash
was V-shaped and fast, and a short position entered into it was likely caught by the reversal
before exit logic responded, unlike 2022's slow multi-month grind. **2020 corroborates the
regime-detection mechanism; it is a contrary data point for the profitability claim.**

**The SPY-gate result needs a significant downgrade — found on adversarial review, and this
section originally overstated it.** The "without SPY confirmation" comparison shows the gate
correctly rejecting dozens of windows across all of 2021. That was described above as "real,
direct evidence the gate does what it claims, independent of the profitability question." It
is not independent. `crash_short_v6`'s own docstring states its v5-to-v6 revision was motivated
by looking at exactly this: *"2021 Q2: BTC -54%, SPY +15% → crypto-specific correction. Do NOT
short."* The gate was very plausibly hand-built by examining 2021's false positives and
patching them. A rule that correctly excludes the case it was explicitly designed to exclude is
not confirmation of the rule; it is confirmation that the designer succeeded at the narrow task
of hindsight pattern-matching. The same applies to 2022 to a lesser degree, cited in the same
docstring passage as the positive case the gate should admit.

**This means 2018 is the most credible of the three regime observations below, not merely a
useful third data point.** It appears nowhere in any version's docstring as a episode any
revision was tuned against — the only one of the three not implicated by the design history.
Where this section previously treated 2021/2022 and 2018 as comparable-strength evidence, they
are not: 2018 is comparatively clean, 2021/2022 are comparatively contaminated, and the
"Updated honest count" below is restated to reflect that distinction rather than average across
it.

**Resolved 2026-08-14 — 2018 is a second genuine profitable payoff, not another mixed case.**
`scripts/run_core_v1_sleeve_contribution_audit.py` re-run with `--oos-start 2018-01-01`
(`artifacts/core_v2_hedge_only_probe_2018/scaled_sleeve_annual_returns.csv`) gives the full
eight-year standalone annual pattern:

| Year | BTC | ETH |
|---|---:|---:|
| 2018 | **+8.78%** | **+22.30%** |
| 2019 | -0.89% | -2.06% |
| 2020 | -1.29% | -3.10% |
| 2021 | -0.36% | -2.29% |
| 2022 | **+5.87%** | **+13.44%** |
| 2023 | -1.98% | -0.13% |
| 2024 | -0.36% | -0.12% |
| 2025 | -4.80% | -0.12% |

Six of eight years show small, narrow losses (-0.12% to -4.80%) — the cost-of-insurance pattern.
Exactly two years show large gains, and both land precisely on the two periods in this window
where BTC and SPY were genuinely in confirmed macro bears together: 2018 (crypto winter into the
Q4 2018 equity correction) and 2022. 2018's ETH return (+22.30%) is larger than 2022's.

**Updated honest count, corrected again for the contamination distinction above:** one
genuinely clean, out-of-sample-relative-to-design-history profitable payoff (2018); one
plausibly-contaminated profitable payoff that the gate was arguably built to produce (2022); one
correctly-fired-but-unprofitable case (2020, not implicated in the design narrative either way).
This is a real improvement on "rests on one draw" — 2018 alone is a genuine second data point —
but it is a smaller improvement than this section claimed two revisions ago. Not "two clean
payoffs plus mechanistic proof," which is what an earlier version of this section said. One
clean payoff, one likely-circular one, and a documented failure case. Still not the breadth
Campaign #53's cross-sectional design achieves; Section 4's judgment-bound framing still applies,
now on a more accurate reading of what the evidence actually supports.

### 3d. Output schema

Sleeve-level and blended fund-level NAV, matching the existing audit harness's own conventions
— no new schema needed.

## 4. Power — PLAN ONLY, and honestly constrained

Amendment 1 requires a simulation-based power estimate before execution. This family's power is
fundamentally limited in a way Campaign #53's is not: power there comes from breadth across 10
simultaneous instruments; here it comes from the count of genuine historical regimes, now
resolved at three (§3c), of which two produced a profitable payoff (2018, 2022) and one fired
correctly without paying off (2020). No simulation manufactures a fourth regime; the count is
whatever the reachable 2018-2025 history actually contains, and that has now been fully
enumerated rather than assumed.

**Revised again, adversarial review 2026-08-14:** the three-regime count is real, but it is not
three equally-weighted independent observations. `crash_short_v6`'s design history (§3c) means
2022's payoff and the SPY gate's 2021 rejections are plausibly the exact pattern its rules were
built to reproduce — evidence the designer succeeded at hindsight fitting, not clean confirmation
the mechanism generalizes. 2020's fired-but-unprofitable case and 2018's payoff are the two
observations not directly implicated by the docstring's own design narrative, and between them
they say something more mixed than "two favorable, one not": the mechanism identifies real macro
stress correctly in both, but only paid off in one. That is thinner support than this section
stated two revisions ago, even though it is still a real improvement on n=1.

This must be stated plainly rather than forced into a false 50%-threshold pass. The honest paths
forward, previously left as "to be resolved at review, not here":

1. Treat this as a **judgment-bound decision** rather than a power-gated one — the economic
   mechanism (why cross-asset confirmation should generalize) is sound independent of sample
   size, and Amendment 1's remedy for low power ("broader cross-section, fewer gates") partially
   applies via §3c's cross-sectional corroboration, even though it cannot fully substitute for
   more independent crisis events.
2. Explicitly bound the claim: this campaign can support "worth including as one small,
   asymmetric component, sized conservatively, monitored for whether the next real bear
   confirms or contradicts it" — a materially weaker and more honest claim than "validated," and
   a more defensible one than this section could support before 2018 was checked, but still not
   "validated" outright.

**Resolved at this review, 2026-08-19: both, not either.** They were never actually competing
options — (1) answers *how this campaign is decided* (a judgment call, not a numeric gate; no
simulation manufactures a fourth crisis) and (2) answers *what claim that judgment can support*
(the narrow one, not "validated"). Adopting (1) without (2) would leave an open-ended judgment
call with no stated boundary — exactly the kind of discretion this repo's governance exists to
close down. Adopting (2) without (1) would restate a scope limit while still implying some future
power threshold might be cleared, which §4 has already shown cannot happen here. The governed
position going forward: `crash_short_v6` may be sized into a Core v2 composition as a small,
asymmetric component under continuous monitoring, on the strength of a judgment call grounded in
one genuinely clean regime (2018), one plausibly-circular regime (2022), and one correctly-fired
but unprofitable regime (2020) — not on the strength of a power analysis, which this family
cannot produce. Sizing itself remains deferred to Closure per §1's candidate-family sketch.

## 5. Execution evidence

*Pending.*

## 6. Result

*Pending.*

## 7. Closure

*Pending.*
