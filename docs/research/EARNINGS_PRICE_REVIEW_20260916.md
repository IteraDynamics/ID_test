# Earnings price review — 2026-09-16

Decision: continue targeted source repair; do not backtest this calendar as a
verified earnings-event panel. This is not a rejection of the economic hypothesis.
The supplied 415-file ZIP provides 207 price files, 207 manifests and earnings CSV.
All 206 stock hashes match the preceding local audit. Reproduction gives 4,304
candidate five-session windows across 201 tickers. No return, gap-signal screen,
performance statistic or model fit was computed.

## Price findings

Stock manifests: all 206 have auto_adjust=false. SPY has auto_adjust=true.
Adjustment flags describe downloader requests, not proof of full corporate-action
semantics. Files contain OHLCV only, without dividend/split reconciliation fields.
Do not mix these directly into a claimed total-return excess-P&L series. Either
recover consistent actions/adjustments, or explicitly limit a price-only diagnostic
and exclude affected dates after documented source checks.

Main-root SPY passes structural checks and spans the required period. Each valid
stock's observed dates matches SPY's dates within that stock's own start/end bounds.
This removes an obvious missing-session problem; SPY is still a proxy, not an
independently certified exchange calendar. The live2026 SPY copy is not used.

Four rows have open outside reported low/high:

| Ticker | Date | Open | Low | High |
|---|---|---:|---:|---:|
| HUBB | 2021-05-05 | 195.98 | 196.21 | 198.64 |
| LEG | 2021-05-05 | 54.32 | 55.09 | 56.42 |
| LEG | 2023-06-05 | 31.58 | 30.9099998 | 31.3955002 |
| UA | 2021-05-05 | 20.8700008 | 21.00 | 21.8250008 |

Three issues cluster on one date; cause remains unknown. Do not clamp opens into
ranges or fabricate corrected quotes. Whole-file rejection remains in the original
sample; a later documented window-local exclusion can salvage unaffected periods
without changing this sample. Every affected lookback/reaction/entry/exit window
would need exclusion, not just events on the bad date. Original inputs untouched.

## Fixed source sample and material discrepancies

The predeclared hash rule selected 30 events before returns or gap thresholds were
examined. All 30 are preserved in the accompanying JSON. Initial searches were
performed for each; most are not fully verified. Source leads are not a completed
point-in-time panel, and no success percentage is reported.

- ECHO / 2019-05-08: Echo Global Logistics' issuer release is April 24, 2019;
  EchoStar has a May 8 release. Echo Global Logistics was acquired for cash in
  November 2021, whereas the local ECHO price series extends into 2026. This is
  an identity/date conflict requiring reconstruction, not evidence permitting us
  to substitute SATS or a successor automatically.
- IEX / 2024-02-07: the issuer's results PDF is dated February 6 and contains the
  same adjusted EPS 1.83 as the calendar row. The calendar is not uniformly the
  original release date. Conference-call versus announcement dating is a possible
  explanation, not yet a proven cause for every row.
- BBT / 2023-07-20: the historical BB&T security changed to TFC in 2019. The
  existence of a same-date Truist release does not validate this BBT series or its
  EPS observation; identity stays unresolved.
- DD / 2019-05-02 requires DowDuPont/spin-off security-basis review.
- SMCI / 2023-05-02 has an April 24 preliminary-results release. The final release
  cannot automatically be treated as the first arrival of earnings information.

Primary links and explicitly qualified source notes are stored per event in
[evidence](evidence/earnings_price_review_20260916.json). For examples:
[Echo Global release](https://www.globenewswire.com/news-release/2019/04/24/1809098/10361/en/echo-global-logistics-reports-first-quarter-2019-results.html),
[Echo take-private](https://www.sec.gov/Archives/edgar/data/1426945/000110465921142821/tm2133713d1_ex99-1.htm),
[IDEX release](https://s21.q4cdn.com/862080382/files/doc_news/2024/02/21761.pdf).
These are present-day historical-source checks. Original source bytes and verified
first-publication timestamps are not archived; no historical execution is credited.

## Next research decision

Source-backed publication dating and historical identity are now the priority,
not acquiring more daily bars. Finish the unchanged 30-case source feasibility
sample with saved original releases, schedule notices and security identifiers,
including failures. Resolve dividend/action basis for those same securities. Then
decide whether a broad event study can be assembled at reasonable cost. Do not
repair only known bad cases and certify the rest by omission, or switch silently
to date-only delayed entries: a one-day delay does not fix a wrong issuer/date.
The already specified event hypothesis and analyst pilot remain unchanged.

## Reproduction and verification

`python -m research.earnings_event.review --data-root <extracted-flat-price-zip> --output <new-json-path>`

The pure local review computes diagnostics and fixed sample, not web-source notes.
It requires the main SPY file explicitly at the data root. Source notes are separately
reviewed annotations and do not change the candidate list. Nine tests passed with
Python 3.12.14 / pytest 9.0.3, including independence of selection from price levels
and missing-calendar-row detection. No new local run is necessary from the user.
