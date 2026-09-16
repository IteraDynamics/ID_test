# Earnings source decision — 2026-09-16

**Replace the event calendar. Stop manual repair of the broad supplied calendar.**
Keep the earnings-reaction hypothesis; the feasibility review has not tested its
returns. This closes the bounded 30-case review, including unresolved cases. It
supersedes the prior price-review recommendation to continue source repair.

## What the completed review establishes

All 30 original hash-selected cases remain, in the original order. No event was
replaced after source inspection, and no gap, return, P&L or model was calculated.
The [case ledger](evidence/earnings_source_closure_20260916.json) contains URLs,
paraphrased evidence, uncertainty and final review dispositions for every case.

| Review disposition | Cases |
|---|---:|
| Release date corroborated, including one displayed publication timestamp | 16 |
| Results release located, timing unresolved | 3 |
| Planned session only | 2 |
| No sufficiently retained primary-source evidence | 4 |
| Specific identity, date, corporate-transition or preannouncement issue | 5 |
| Total | 30 |

These categories are not a calendar accuracy estimate. Unresolved does not mean
incorrect. The 16 date matches are not 16 certified tradeable events: historical
security-to-price mapping, corporate actions, actual release session and earlier
information must still be reconciled. CAG's issuer page displays January 4, 2024
at 07:30 EST; conference-call times elsewhere were not substituted for release times.
META's 2021 release explicitly identifies historical ticker FB, illustrating why
current ticker strings alone cannot establish historical identity.

Five previously identified issues remain material: ECHO has an issuer/date and
post-acquisition price-history conflict; IEX's February 2024 row is dated one day
after the issuer release; BBT needs historical security identification; DD needs
spin-off/security-basis reconciliation; SMCI has a preliminary announcement before
the calendar's final-results date. JBL's release also refers to a previously
amended outlook; finding a final release does not prove first information arrival.

The existing price audit also found inconsistent adjustment requests (206 stock
manifests versus SPY) and four invalid OHLC rows in three files. Neither changing
the earnings date nor delaying entry resolves security or price-basis problems.
No prices or event records have been silently corrected.

## Research judgment

The missing information is structural: a stable historical security identifier,
actual announcement session, preliminary/final linkage and defensible price/action
semantics. Repairing only the conspicuously bad rows leaves the other 4,304 candidate
windows uncertified. Manual issuer-by-issuer repair would become a separate data
engineering project. We have enough evidence to reject that use of research time;
we do not have a measured cost estimate or proof every record is unusable.

Stop expanding this manual review. Retain these 30 cases as a fixed acceptance
set for a replacement source. Do not use the survivors as a small alpha backtest
or relabel these inspected years as untouched out-of-sample data.

## Replacement assessment

1. **First candidate: Wall Street Horizon historical event data.** Its
   [historical-data documentation](https://www.wallstreethorizon.com/historical-data)
   describes history from 2006, varying by dataset. Its
   [earnings products](https://www.wallstreethorizon.com/earnings-calendar) include
   preliminary announcements, timestamped date-revision alerts and source links
   for EPS results. These capabilities fit the missing information. Public
   documentation does not establish that a purchasable historical package includes
   all of them, actual publication timestamps, or the required security mappings.
   Obtain a sample and field definitions before choosing or buying the package.
2. **Alternative: Benzinga earnings through Massive.** The
   [endpoint documentation](https://massive.com/docs/rest/partners/benzinga/earnings)
   advertises history from April 30, 2010 and exposes date status, event ID,
   company name, time and last-updated metadata. Critically, its time can describe
   scheduled or reported earnings; last-updated is not first-publication time or
   proof of an as-of historical version. The documented EST convention also needs
   a daylight-saving interpretation. It is a candidate, not a drop-in repair.
3. **Separate price candidate: Norgate.** Its
   [data-content documentation](https://norgatedata.com/data-content-tables.php)
   describes delisted securities, historical index constituents and capital-event
   information. Its daily open is the first price from any venue/ECN, so it cannot
   automatically represent an executable opening-auction fill. This would address
   price/universe work, not replace earnings announcement evidence.

No vendor data was purchased, sampled or certified, and no vendor was contacted.
Public-document review cannot establish coverage, price, licensing or API access.

## Concrete next task and stopping rule

Obtain a replacement-source extract for these same 30 cases, with the following
fields and definitions; do not buy broad history first:

- Stable issuer/security IDs and historical ticker validity, with explicit
  explanation for ECHO, BBT, DD and META. A company identifier alone does not
  distinguish all share classes or corporate-action price histories.
- Actual release date/session, timezone and precision; planned dates and call
  times in separate fields. Identify publication timestamp versus vendor receipt,
  record update, and any reconstructed historical timestamp.
- Preliminary/final relationships, fiscal period, source reference, and original
  versus corrected record history. For this reaction hypothesis, historical EPS
  estimates are not required; do not add surprise features from revised consensus.
- Price identifier, split/dividend/spin-off treatment, delisting treatment and
  executable-open definition, with sample reconciliation to existing bars.

Keep all 30 in the report, including vendor omissions. If the replacement still
requires bespoke date/identity repairs to establish these semantics, reject it
for this study rather than start another open-ended patch cycle. A credible sample
then justifies broad acquisition and a separate coverage audit; it is not proof of
vendor-wide accuracy. Costs/access remain the external dependency, not another
user-side backtest run. An adequate sample must be available before building an
adapter that assumes its schema or timestamp meaning.

After data acceptance, implement the already specified reaction test: large
positive earnings gap, first-session hold versus reversal, next-session-open
entry, primary three-session holding period with one/five-session sensitivities,
generic non-event and market/sector controls, and 10/30/60bp round-trip costs.
No new signal family, timeframe expansion or ML search is implied by this decision.
Core paper trading and the prospective active-equity analyst pilot remain separate.

## Reproducibility and limits

The source ledger preserves every ticker/date/rank hash from the prior evidence
file. Input hashes and local diagnostics remain in that file. Source inspection
used present-day web extraction; original page/PDF bytes were not archived.
Direct raw download returned HTTP 403 and some article retrievals failed. The
ledger records these as limitations, not successful source certification.
Thus the bounded feasibility review is closed, but the requested original-source
archive and a fully verified event panel are incomplete. The decision to replace
rather than certify does not depend on pretending those gates passed.

No executable strategy logic changed. Existing audit tests and a check of all
30 immutable sample keys are sufficient verification for this evidence-only update.
