# Itera Dynamics — Campaign Log

_Append-only. Never rewrite past entries — if a conclusion changes, add a
new entry that references the old one._

## Campaign #[N] — [name]
- **Chartered:** [date] — by [seat], addressing deficiency [1-4 or "n/a"]
- **Status:** OPEN / CLOSED_POSITIVE / CLOSED_NEGATIVE / CLOSED_UNDERPOWERED / BLOCKED
- **Summary:** [what was tested]
- **Result:** [headline stat + backtest ceiling caveat]
- **Red Team verdict:** [pass/fail/conditional + key finding]
- **What killed it / what kept it alive:** [the specific check that decided it]
- **Risk/PM note (if applicable):** [correlation/materiality finding]

## Campaign — Distance-method pairs trading (equity relative-value)
- **Chartered:** 2026-09-01 — off-charter. Built directly on the CEO's request for an
  immediately-testable, previously-untouched mechanism during a live session; never went
  through `charter-campaign`'s standard five-gate sequence (horizon feasibility, tradeability,
  materiality, power, document format) before code was written. Recording that plainly rather
  than backfilling a charter after the fact.
- **Status:** CLOSED_NEGATIVE
- **Summary:** Gatev/Goetzmann/Rouwenhorst distance-method pairs trading — normalized-price-path
  distance selects pairs on a 12-month formation window, trades divergence-from-relationship on
  the following 6-month window, walk-forward across 2003-2026. Built with an automatic
  negative control (identical simulation with randomly-selected pairs) and a bootstrap of the
  real strategy's own window returns baked into the same run, specifically so the verdict
  couldn't be eyeballed off a single flattering point estimate.
- **Result:** Real annualized Sharpe -0.98 (window-level) on the corrected, single-market
  universe (265 US equities/ETFs, 2003-08 through 2026-08, 45 walk-forward windows, 9,762
  trades, 27.2% win rate). Real underperformed **all 100 of 100** random-pair null repeats
  (permutation p=1.0000). Bootstrap: 90% CI [-2.65, -0.45], P(Sharpe<=0)=100%. Not an
  underpowered null — a well-powered, unambiguous negative.
- **Red Team verdict:** FAIL, mechanical (verdict computed by the script itself against
  pre-registered thresholds, not an editorial call). Consistent with the literature's own
  account of why distance-method pairs trading decayed after the 1990s-2000s: the method
  selects pairs with the tightest historical spread variance by construction, which plausibly
  produces trades too small relative to fixed transaction costs, with occasional larger losses
  when a tight historical relationship doesn't hold going forward. Read as informed reasoning,
  not confirmed causally.
- **What killed it / what kept it alive:** Two real infrastructure bugs were found and fixed
  along the way before the result could be trusted — worth recording separately from the
  strategy verdict since they'll recur if not fixed at the source: (1) mixed tz-aware/tz-naive
  and DST-spanning timestamps across locally-downloaded `{TICKER}_1D.csv` files didn't reliably
  parse into a `DatetimeIndex`; (2) the loader was silently mixing plain US equities with
  Japanese listings, index tickers, and futures contracts from the same `data/` directory,
  which — on incompatible trading calendars — collapsed the eligible pairing universe to
  0-then-exactly-2 tickers for 13+ years and produced a first-pass "result" that was actually
  an artifact, not a strategy finding. Once both were fixed and the universe restricted to a
  single coherent market, the negative held cleanly. The per-window eligibility diagnostic
  added specifically to catch this class of bug (`scripts/backtest_pairs_distance_method.py`)
  is worth reusing on any future walk-forward script over this same local data.
- **Risk/PM note (if applicable):** n/a — closed before reaching a risk/sizing/materiality
  review; the mechanism itself did not clear its own negative control.

## Campaign — Low-volatility factor (cross-sectional equity, vol-sorted long/short)
- **Chartered:** 2026-09-01 — off-charter, same session, CEO's second pick after the pairs
  closure ("if it's the best you got, I guess let's build it," with an explicit crowding
  reservation stated upfront, not discovered after the result).
- **Status:** CLOSED_NEGATIVE
- **Summary:** Ang/Hodrick/Xing/Zhang-style low-volatility anomaly (a close cousin of
  Frazzini/Pedersen's beta-neutral "Betting Against Beta") — rank the universe by trailing
  12-month realized volatility each formation window, long the lowest-vol quintile / short the
  highest-vol quintile, hold 3 months, walk forward 2003-2026. Reused the pairs campaign's
  already-fixed loading/eligibility infrastructure directly (import, not re-derivation), with
  the same automatic negative control (random long/short split of the same universe) and
  bootstrap baked into the same run. Window diagnostic included from the start this time rather
  than added reactively.
- **Result:** Real annualized Sharpe -0.30 across 82/90 valid windows (only the earliest 8
  windows, 2004-2005, skipped for a thin universe — the same organic early-history pattern as
  the pairs campaign, not a data artifact; confirmed clean on the first run, no debugging round
  needed). Real underperformed the random-split null's mean and 86% of its 100 repeats
  (permutation p=0.8614). Bootstrap: 90% CI [-0.62, +0.05], P(Sharpe<=0)=92.3%.
- **Red Team verdict:** FAIL, mechanical. Consistent with the CEO's own stated reservation
  before the build: this factor is not undiscovered — it's one of the most widely traded in
  finance (billion-dollar ETFs built on it) — and a clean negative here is exactly what
  substantial crowding since its academic documentation would look like, though the specific
  simplified construction used (realized-volatility sort, not full beta-neutral leverage
  adjustment; quarterly full-turnover rebalance) could independently account for some of the
  gap. Not disentangled here — read as informed reasoning, not a confirmed cause.
- **What killed it / what kept it alive:** The negative control and bootstrap, run automatically
  in the same pass — no separate debugging phase was needed this time because the reused
  infrastructure (ticker-pattern market filter, tz/DST-safe parsing) had already been proven
  clean on the same universe by the pairs campaign.
- **Risk/PM note (if applicable):** n/a — closed before reaching a risk/sizing/materiality
  review; the mechanism itself did not clear its own negative control.

## Exploration screen — Index-options dealer gamma pressure
- **Screened:** 2026-09-02 under `docs/ITERA_EXPLORATION_SANDBOX.md`; no campaign number.
- **Status:** SCREEN_NEGATIVE
- **Mechanism:** aggregate SPY option gamma/open-interest geometry was tested as a proxy for compelled dealer hedging pressure. The frozen directional story expected low signed GEX to produce more trend continuation than high signed GEX after a conservative one-trading-day source lag.
- **Result:** frozen signed-GEX continuation gate failed at all three horizons: 1d difference -0.000739, p=0.8982; 2d -0.001868, p=0.9621; 5d -0.004451, p=1.0000. The supplemental reversed call/put sign convention produced the opposite relationship and was nominally significant at 2d (p=0.0339) and 5d (p=0.0020), therefore contradicting rather than rescuing the primary dealer-sign story. The tested panel contains 3,024 usable state rows from 2013-12-02 through 2025-12-12; earlier option history was source-validation evidence only because the local SPY outcome file begins later.
- **Control / artifact findings:** raw total-gamma level separated future absolute movement at 1d/2d/5d (one-sided permutation p≈0.0020/0.0040/0.0279), but this does not earn promotion. Its causal expanding-tercile states were severely imbalanced (2,173 low vs 372 high), later-year high/low comparisons largely disappeared, raw total gamma grows with the secular size of the options market, and gamma itself is mechanically related to volatility and time-to-expiry. Treating that side result as alpha would be outcome-informed salvage and likely scale/volatility confounding. Gamma-concentration movement also failed its frozen expected direction at all horizons (p=1.0).
- **What killed it:** the pre-outcome directional gate failed cleanly, and the reversed sign convention performed better. Open interest does not identify dealer inventory direction, so the observed reverse-sign relationship cannot be interpreted as validating the same mechanism under a preferred convention.
- **Boundary:** closed as a sandbox negative. No Core v1/Core v2/runtime/portfolio/paper/live implication. Any future gamma-related screen must be a genuinely new pre-specified hypothesis rather than a retune of this result.