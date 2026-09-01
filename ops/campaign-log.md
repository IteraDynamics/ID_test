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
