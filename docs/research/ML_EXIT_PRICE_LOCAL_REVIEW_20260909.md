# Local exit-price probe review — 2026-09-09

The uploaded `ml_exit_price_probe_20260909_142128_review.zip` contains four raw
Yahoo CSVs, the manifest and the report. All four lengths and SHA-256 values
verified. Offline report replay was byte-identical using the committed runner.
No download was repeated. Evidence is in `evidence/ml_exit_price_local_review_20260909/`.

| Source / ticker | Observed result |
| --- | --- |
| Yahoo SPY control | 1,761 rows, 2018-01-02 through 2024-12-31 |
| Yahoo FRCB | 1,761 rows covering older First Republic and post-failure dates; candidate continuity |
| Yahoo LHX | 1,761 rows including June 28 and July 1, 2019; candidate Harris continuity |
| Yahoo SBNY | 96 rows starting 2024-08-15; required 2021/2023 dates missing |
| Yahoo APC / NFX | YFPricesMissingError |
| Yahoo FRC / HRS / LLL | YFTzMissingError |
| Stooq SPY control | HTTP 404; all eight targets correctly skipped |

FRCB's May 1 and May 2, 2023 rows repeat April 28's $3.51 close in all four
OHLC fields with zero volume. May 3 opens around $0.396 and closes $0.3336.
These are observations in the supplied file, not evidence that the repeated
prices were executable. A month-end next-open ledger must not turn the zero-volume
rows into successful liquidations. Two additional FRCB rows have an open below
the reported low: May 5, 2021 and December 11, 2023. Retain and investigate them;
do not silently repair the source. SBNY has two zero-volume rows in its short
2024 history. LHX has neither zero-volume nor inconsistent-OHLC rows in this
specific check. None of this certifies adjustment basis or security identity.

The original probe intentionally labels structurally passing files STRUCTURE_ONLY.
Its finite-number checks do not include OHLC ordering or execution-volume checks.
The additional raw review therefore does not change the successful replay claim
or approve FRCB for a portfolio. No model fits have been performed.

## Remaining source-access question

On this review, both the [Stooq SPY historical page](https://stooq.com/q/d/?s=spy.us)
and [bulk history page](https://stooq.com/db/h/) returned a requirement to enable
JavaScript for browser verification. Our automated 404 result cannot establish
that Stooq lacks historical target data. The earlier no-key acquisition description
applies to what the script attempts; it must not be read as verified current
Stooq access requirements. Browser verification or an official download key may
be needed. No bypass or key sharing is requested.

The next required action is a manual local-browser source check: complete Stooq's
ordinary verification, try downloading SPY history as a control, then APC.US and
NFX.US for 2018–2019 if the control works. Share the downloaded CSVs. If the site
instead requires a key/account or reports unavailable symbols, share the message
with credentials excluded. Do not rerun the existing Python probe unchanged.

This is the remaining access check for the already selected second source, not
an expansion to another model or a survivor-only universe. If it fails to recover
the needed histories, the broad-equity historical design needs a scope decision.
