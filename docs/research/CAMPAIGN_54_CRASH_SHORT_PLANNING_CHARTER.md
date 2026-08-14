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
Shorting requires derivatives or margin access — **this shares Campaign #53's exact same
blocker, CDE derivatives eligibility.** That decision, still outstanding and still entirely the
operator's account-status item, unblocks both threads at once, not just one.

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

**The strongest result from this census is not the episode count — it's the SPY-gate
validation.** The "without SPY confirmation" comparison shows the gate correctly rejecting dozens
of windows across all of 2021, a raging equity bull market during which BTC still pulled back
sharply several times. This is the exact failure mode the strategy's own docstring names —
crypto-specific correction, not macro bear — caught mechanistically rather than inferred from an
aggregate Sharpe number. This is real, direct evidence the gate does what it claims, independent
of the profitability question above.

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
Q4 2018 equity correction) and 2022. 2018's ETH return (+22.30%) is larger than 2022's. This is
not a marginal addition to the case — it is a second clean profitable payoff, four years removed
from the first, on top of the SPY-gate's demonstrated mechanistic correctness across 2021.

**Updated honest count: two profitable corroborating crisis payoffs (2018, 2022), one
correctly-fired-but-unprofitable case (2020), across a reachable window containing three
distinct genuine macro-bear regimes total.** That is a materially stronger position than this
section's prior draft stated, though still not the breadth Campaign #53's cross-sectional design
achieves — three regime observations remain a small sample by conventional statistical standards,
and Section 4's judgment-bound framing still applies. The correction is recorded here rather than
silently overwritten: this section previously said the profitable count was "closer to one than
to four." It was closer to one at the time, on the evidence then available; it no longer is.

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

This must be stated plainly rather than forced into a false 50%-threshold pass. Three regime
observations, two of them favorable, is real evidence — meaningfully better than the single-draw
case this section originally described — but still a small sample by conventional statistical
standards, and still not the cross-sectional breadth Campaign #53 has. The honest paths forward,
to be resolved at review, not here:

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

## 5. Execution evidence

*Pending.*

## 6. Result

*Pending.*

## 7. Closure

*Pending.*
