# Analyst rehearsal — 15 September 2026

Decision: continue the active-equity research. Two source-backed cases demonstrate
earnings-quality distinctions that the frozen accounting screen does not express.
Neither warrants a rehearsal buy. This is evidence of analytical usefulness, not
evidence of return predictability, an actionable bargain, or superiority to Core.

Research judgments below were authored now, using already-public Q2 2026 reports
and indicative September quotes. They are not backdated earnings-day decisions.
Cases were chosen purposively, not consecutively; secondary news snippets were
visible during discovery. No historical blindness, statistical significance or
OOS claim is made. Exact model checkpoint is not exposed; analyst: ChatGPT/Codex.
No rehearsal record was appended to the prospective pilot. These events predate
its enrollment window; these cases contribute no prospective observations.

## Crocs — WATCH; reject the claimed operating turnaround

**Observed:** Q2 revenue grew 2.62%; GAAP margin moved from -37.20% to 24.22%,
passing the frozen screen. However, the prior quarter contained $737m of
impairments. Adjusted operating profit fell 4.48%; adjusted net income fell 4.97%.
An 11.61% reduction in adjusted diluted shares explains rising EPS despite lower
total adjusted earnings. [C1: operations and reconciliation tables](https://www.sec.gov/Archives/edgar/data/1334036/000133403626000050/croxq22026-pressrelease.htm).

**Valuation/inference:** The indicative $112.20 quote divided by management's
$13.85 guidance midpoint gives 8.10x adjusted earnings. An illustrative 30% EPS
haircut gives 11.57x; neither establishes intrinsic value. This may deserve value
research, but apparent GAAP recovery is insufficient evidence of durable growth.

**Counterargument:** Low expectations and shareholder distributions can produce
good returns without an operating turnaround. **Risks:** demand deterioration,
adjustment quality, and capital allocation. **Forecast:** in at least one of the
next two quarters, adjusted EPS grows while adjusted net income does not.
**Reconsider:** sustained total operating-profit growth and a cash-based valuation.
**Confidence:** medium in the accounting diagnosis, low in the investment edge.

## Duolingo — WATCH; engagement is not yet an earnings inflection

**Observed:** Revenue grew 18.31%, but GAAP operating margin fell from 13.23% to
11.37%, failing the screen. Operating income rose $0.582m while founder-award
compensation swung favorably by $10.945m. Removing that line in both years gives
$26.963m versus $37.326m: a sensitivity, not a fully normalized earnings measure.
[D2: income statement and Note 8](https://investors.duolingo.com/node/11971/html).

DAUs rose 23%, versus 8% bookings growth. The letter describes a one-time streak
revival campaign as one growth contributor. Using indicative price $151.21,
June diluted shares and cash/short-term investments gives a $6.35bn enterprise
value proxy: 5.26x guided revenue or 19.85x guided adjusted EBITDA. Allowing for
guided stock compensation reduces that EBITDA denominator from $320m to $138.95m;
the corresponding 45.72x diagnostic is not a GAAP/FCF multiple. Do not charge the
same future compensation again as dilution. [D1: letter pp. 4–5, 8–11, 15](https://investors.duolingo.com/static-files/3c8277ee-bc94-4f5d-9b77-0db3e46f88b8).

**Inference:** durability requires profitable retention and conversion, not merely
reactivated accounts. **Counterargument:** deliberate investment may temporarily
hide improving customer economics. **Risks:** weak monetization, competition and
compensation dilution. **Forecast:** bookings growth remains below DAU growth in
each of the next two quarters. **Reconsider:** narrowing growth gap plus improving
compensation-inclusive margins. **Confidence:** medium in diagnosis; low in edge.

## What this rehearsal changes

Keep the frozen comparator exactly as defined. Crocs illustrates an analyst veto
of a screen pass; Duolingo illustrates agreement with a screen failure while
retaining a specific hypothesis for future review. We have not demonstrated a
valuable positive selection that the screen misses. Do not claim that two watch
judgments establish a working investment strategy.

The next evidence packet should include a reconciliation of total profit to
per-share profit and a bridge between reported operating profit and consequential
adjustments. This is a research requirement learned from development, not an
unlogged change to the frozen analyst prompt, feed, selection rule or comparator.

The decision horizon for both forecasts is 2027-03-15: evaluate the next two
reported quarters after Q2 2026; if disclosures are missing, mark unresolved.
The reconsideration conditions concern further research, not automatic orders.

Unresolved before any buy: independent security/market-cap/ADV20 eligibility;
actual announcement availability; full current disclosure sweep; reconciled
current shares, debt and cash; cash-flow normalization; execution/cost protocol.
The price observations are from the web finance tool at 15:25:34/35 UTC on
2026-09-15, with vendor lineage not exposed. They are illustrative reference
quotes, not fills. The DUOL proxy mixes June balance-sheet/share inputs with a
September quote and excludes leases and long-term investments. No live P/E,
market-cap, or consensus estimate from that feed was accepted as verified.

## Reproduction and evidence limits

Hand-transcribed values, dates and source locators are in
`research/active_equity/rehearsals/20260915_inputs.json`. Original web document
bytes are not archived; this packet is not equivalent to registered pilot evidence.
Recheck the linked issuer documents before prospective use. Source publication
dates are identified, but original intraday availability was not independently
established. Sources were read; market outcomes were not evaluated.

Run from the checkout:

```powershell
uv run --locked --python 3.12 python .\research\active_equity\rehearsal_20260915.py
```

The standard-library script prints the arithmetic and `performance: null`; it
does not download anything, select candidates, append to a ledger or call a model.
Its two watch labels are authored judgments, not outputs of a predictive model.
The script was executed successfully in the build environment; results reproduce
the displayed margins, screen classifications, earnings/share bridges and multiple
sensitivities. No new strategy test or Monte Carlo analysis was run.
