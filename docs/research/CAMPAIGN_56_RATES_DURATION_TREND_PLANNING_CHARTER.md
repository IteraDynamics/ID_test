# Campaign #56 — Rates/Duration Trend Sleeve

## 1. Charter

### Status

**PLANNING — gates 0-3 pass below. Gate 4 (power) scoped, not yet run. Nothing in this
document is frozen** — per Amendment 3's pacing rule, a specification may not be frozen the
same session it is first drafted. This is the draft; a later-day review pass comes before any
freeze.

### Question

> Does applying Core v1's own existing, unmodified SMA175 trend-filter mechanism
> (`research/strategies/equity_sma175.py`) to a US Treasury duration instrument produce a
> standalone sleeve worth including in Core v2, or does the mechanism's known single-instrument
> power limitation (the same one that bounded Campaign #54's crash-short evidence) mean this
> closes the "no rates exposure" deficiency in name only, without a statistically credible
> result behind it?

### Named deficiency

**"No rates or fixed income exposure"** — the fourth of Core v1's four named structural
deficiencies (`docs/ITERA_DESTINATION_CHARTER.md`), explicitly flagged in `docs/CORE_V2_CHARTER.md`
as *"not addressed by either founding campaign... the most novel and most expensive avenue
available."* Still fully open. This is Gate 0: a named deficiency, not a reparameterization —
nothing about Core v1's SMA175 constant, weights, or logic changes; a new instrument gets the
same already-validated mechanism, the same category of addition as GLD's original inclusion.

### Economic mechanism

Long-duration Treasuries exhibit sustained multi-month/multi-year directional regimes (rate-cut
cycles, rate-hike cycles, flight-to-quality episodes) — the same kind of persistent, trending
behavior the SMA175 mechanism was built to capture on equities. The mechanism itself is not new
or untested; only the instrument is. This is a deliberately conservative design choice: reusing
`equity_sma175.py` (v1 — the plain SMA175 crossover, not v3's BTC-parabolic-conditioned
de-risk overlay, which encodes an equity/crypto-macro relationship that has no articulated
reason to apply to bonds) means zero new signal-design risk. The open question is not "does
this mechanism work" — it already runs live on SPY/QQQ — it's "does trend-following on this
specific asset class clear this fund's own evidentiary bar," which Campaign #54 already showed
is a real and separate question from mechanism validity.

### Why not already represented

Confirmed directly in this repo, not assumed: `research/strategies/` contains six modules
(`contracts.py`, `crash_short_v6.py`, `equity_sma175.py`, `equity_sma175_v2.py`,
`equity_sma175_v3.py`, `__init__.py`) — no rates or duration instrument anywhere in the
strategy registry, and no rates data source referenced in the codebase's scripts. Core v1's
defensive state during any regime is cash; there is no instrument in the fund's current universe
that can gain when rates fall.

### Falsification statement

The hypothesis is falsified if either: (a) the backtested sleeve does not clear the frozen power
standard set in Section 4 (a design that cannot detect a plausible true effect is not run at
all, per Amendment 1); or (b), if it is run under a judgment-bound framing per Campaign #54's own
precedent for low-regime-count families, the sleeve's live-relevant risk-adjusted metrics do not
exceed a static buy-and-hold benchmark on the same instrument net of costs. A sleeve that merely
replicates buy-and-hold with extra transaction costs and whipsaw does not close the deficiency —
it adds instrument exposure without adding a trend-following edge, which is a different, weaker
claim than what this campaign is chartering.

## 2. Feasibility

### Gate 1 — Horizon feasibility (Amendment 4)

The SMA175 mechanism's signal persists for the life of the trend regime it detects — the same
signal already running live on SPY/QQQ, whose regimes run weeks to years. Measured runtime
cadence, corrected 2026-08-20 (`CLAUDE.md`, `tests/test_paper_runtime_cadence_audit.py`):
~0.5–0.6 effective bars, roughly constant across timeframes. On daily bars (this sleeve's only
valid cadence — `equity_sma175.py`'s own design notes: *"Daily bars only. Do NOT feed hourly
bars to this strategy"*), a multi-week-minimum regime against sub-1-bar decision lag is a
feasibility margin of hundreds-to-one. **Passes trivially**, stated for completeness per this
fund's own convention (Campaign #54 §2 handled an equally trivial margin the same way).

### Gate 2 — Tradeability (Amendment 5)

- **Instrument:** TLT (iShares 20+ Year Treasury Bond ETF) as the primary candidate — the most
  duration-sensitive, most liquid long-Treasury ETF, so the trend signal has the most amplitude
  to work with. IEF (7-10yr) is the natural robustness-check alternative (Section 4).
- **Venue:** the same equity brokerage already executing SPY/QQQ/GLD live. TLT is a plain,
  unlevered, NYSE Arca-listed ETF — no options approval, no futures/margin account, no
  derivatives eligibility tier required, unlike every crypto or options candidate this fund has
  examined. This is about as close to zero tradeability risk as this gate gets. **Not yet
  independently confirmed:** that the specific live brokerage account has TLT enabled for
  trading (vs. just SPY/QQQ/GLD) — a one-line operator confirmation, not a probe script, given
  the near-certainty here.
- **Data source:** same equity/ETF daily-bar pipeline already feeding SPY/QQQ/GLD. No new
  acquisition anticipated; to be confirmed when Section 4's data pull happens.
- **Research source vs. execution venue:** identical (same ETF, same exchange, same broker) —
  no cross-venue basis risk, unlike Campaign #53's Deribit-discovery/CDE-confirmation split.

### Gate 3 — Economic materiality

At $100k capital: single-asset time-series momentum studies span Sharpe ~0.4 (1880-2016,
futures/spot) to ~0.72 (200-year cross-sector trend) to ~0.95-1.2+ in diversified multi-asset
constructions that include Treasuries as one of several instruments (Quantpedia; CFM;
arXiv:2412.14361 — see prior staff discussion this session for full citations). A single
uncorrelated instrument, with none of that cross-asset diversification benefit, should be
priced toward the conservative end: **Sharpe ~0.4-0.6**. TLT's own annualized volatility runs
~12-15%. At a Core-v1-sleeve-sized allocation (~15% weight): 0.5 × 13% × 15% ≈ **$975/yr** —
squarely inside this fund's own repeatedly-observed $400-1,500/yr range for every edge examined
this session, not an exception. **Stated plainly, per this gate's own rule against softening:**
this campaign is not expected to move the fund's returns materially on its own. Its case rests
on closing a named structural gap and adding a genuinely low-correlation return source, the same
basis GLD and crash-short were included on — not on an exciting standalone number.

## 3. Frozen specification

**Not written. Blocked on Section 4.** Per this skill's own gate ordering, no specification is
drafted before the power gate is scoped and a real result exists to design around.

## 4. Power and confirmation standard — SCOPED, NOT RUN

**Honest framing before any number exists, because this fund has been burned by the alternative
once already (Campaign #54).** This is structurally a single-instrument time-series design.
Amendment 1 explicitly prefers cross-sectional designs because a time-series test on
autocorrelated data has far fewer effective observations than rows — and this campaign's own
economic mechanism (multi-year rate regimes) means the number of genuinely *independent* regime
cycles in reachable, liquidity-adequate history is small. TLT itself only launched in 2002; the
full modern Treasury cycle set (the 1980s disinflation, the 2000s range, 2013's taper tantrum,
2020's zero-rate regime, 2022's hiking cycle) offers on the order of **4-6 major regimes**, not
the dozens of effectively-independent observations a real power analysis needs. This is the same
shape of problem Campaign #54 hit with `crash_short_v6` (§4 of that charter: *"power is
fundamentally limited... by the count of genuine historical regimes"*) — flagged here **before**
building anything, not discovered after, which is the entire point of running this gate.

**Planned mitigation, following Amendment 1's own prescribed remedy ("broader cross-section, not
more calendar time on the same series"):** broaden from a single instrument (TLT alone) to the
US Treasury maturity curve as a small cross-section — SHY (1-3yr), IEI (3-7yr), IEF (7-10yr),
TLT (20+yr) — applying the identical, unmodified SMA175 mechanism to each independently. This
is **not** genuine cross-sectional independence the way Campaign #53's 10-name crypto universe
was (maturities along one curve move together, often sharply so) — stated honestly rather than
oversold — but it does let the campaign test whether the mechanism's behavior generalizes across
the curve rather than resting on one single instrument/parameter combination, and it modestly
improves effective breadth over n=1.

**Concrete next executable step, not done in this session:**

1. Acquire real daily-bar history for SHY/IEI/IEF/TLT (own governed acquisition, matching the
   existing ETF data pipeline — to be confirmed, not assumed, when this step runs).
2. Run `equity_sma175.py`'s exact, unmodified mechanism against each series — zero
   perturbation, matching Campaign #54's own "exactly as coded" discipline.
3. Count genuine independent regime cycles per instrument (the same census discipline as
   Campaign #54 §3c's entry-episode census — collapse raw signal crossings into distinct
   regimes, don't count fragments as independent observations).
4. Run Amendment 1's simulation-based power estimate: inject a hypothetical effect at a
   plausible grid, measure whether the frozen gates would detect it given the real regime count.
5. **If average power at the central plausible effect size is below 50%, per Amendment 1 this
   campaign does not proceed to a numeric decision rule** — it either redesigns further (a wider
   curve, a different mitigation) or closes as judgment-bound under Campaign #54's own precedent
   (a bounded, honestly-scoped claim, not a power-gated validated result). Which of those two
   paths applies is not decided here, before real data exists to decide it on.

**This section is not a result. It is the honest state of the problem before Gate 4 is actually
run**, written down before the data pull so the record shows the concern was anticipated, not
discovered conveniently after a favorable-looking backtest.

## 5. Execution evidence

Not started.

## 6. Result

Not applicable — no execution has occurred.

## 7. Closure

Not applicable. **Next executable step is Section 4, item 1** (data acquisition), on a later
session per Amendment 3's pacing rule — this planning charter should not be reviewed and
extended in the same sitting it was drafted.
