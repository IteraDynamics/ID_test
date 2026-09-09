# Historical exit-price recovery probe — 2026-09-09

The next required input is one local run of `scripts.run_ml_exit_price_probe`.
This bounded probe asks Yahoo through the repo's locked yfinance dependency and
Stooq's public CSV endpoint for 2018–2024 histories. No subscription, API key,
SEC email, fitting or portfolio changes are required.

## What we recovered remotely

Anadarko's August 8, 2019 acquisition paid $59 cash plus 0.2934 Occidental
shares per Anadarko share. APC stopped NYSE trading after that day's close.
[Issuer release filed with the SEC](https://www.sec.gov/Archives/edgar/data/797468/000095015719000864/ex99-1.htm).
These terms establish the form of consideration, not daily prices, an executable
liquidation price, or the treatment/timing of fractional-share cash.

Newfield's acquisition completed February 13, 2019.
[Encana completion announcement](https://www.globenewswire.com/news-release/2019/02/13/1725049/0/en/encana-completes-acquisition-of-newfield-exploration-to-create-north-america-s-premier-resource-company.html).
The approved terms were 2.6719 Encana common shares per Newfield share.
[Issuer shareholder-approval announcement](https://investor.ovintiv.com/news-releases?item=36).
Encana's subsequent identity/capital changes would need their own mapping if
shares were carried forward. Do not replace NFX history with a current ticker.

For Signature, the March 12, 2023 joint government announcement protected
depositors and explicitly excluded shareholder protection.
[Federal Reserve statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20230312b.htm).
This does not establish zero as an executable historical shareholder exit price.
OTC Markets identifies [FRCB as First Republic Bank](https://www.otcmarkets.com/stock/FRCB/overview)
and [SBNY as Signature Bank](https://www.otcmarkets.com/stock/SBNY/overview).
Those listings justify candidate price requests only. They do not establish
continuous historical coverage, historical execution access or an exact alias
effective date. No OTC prices or recovery values are assumed.

HRS/LHX, FB/META and LLL terms are recorded in the preceding membership repair.
The existing META raw pilot is retained; no repeat META acquisition is requested.

## Request budget and outputs

Each selected provider receives SPY first as a control, then at most eight
target symbols: APC, NFX, FRC, FRCB, SBNY, HRS, LHX and LLL. Both providers together
have at most 18 top-level history calls. yfinance may make internal setup calls.
No application-level retry loop is used. Requests use a 25-second timeout and
one-second spacing. A failed/invalid control stops that provider. An explicit
401/403/429 or yfinance rate-limit exception stops subsequent requests to that
provider. A successful control followed by an individual missing symbol records
that failure and proceeds. No proxy rotation, alternate credentials or challenge
bypass is implemented.

Requested dates end before 2025. Returned later data is retained as raw evidence
but rejected by the requested-window check. CSV schemas, numerical values,
duplicate dates and diagnostic event observations are checked. Gaps longer than
seven calendar days are reported without filling them. Missing check dates are
coverage exceptions, not assertions that a particular OTC day was executable.

Yahoo requests keep Adj Close, dividends and splits with auto_adjust=False and
back_adjust=False. This does not prove nominal unadjusted OHLC prices. Stooq's
adjustment basis is unverified. Every result remains identity/terminal-outcome
unverified even when its structural checks pass. Neither endpoint overlap nor
the presence of an event-day row is sufficient to approve a backtest.

The runner creates a fresh directory containing `raw/`, `source_manifest.json`
and `exit_price_report.json`, then a sibling `_review.zip` with all those files.
The manifest records failed and skipped attempts as well as saved file hashes.
Raw non-CSV responses may use a `.csv` filename and will be marked rejected.
It never overwrites an existing output directory or review ZIP.

The report is built twice for byte equality. Offline replay verifies raw hashes,
inventory, attempt coverage and exact report bytes. A completed probe may have
zero recovered histories and still exit successfully: that is a recorded source
result. Corrupt inputs, overwrite attempts and replay mismatches fail the command.

```powershell
uv run --locked --python 3.12 python -m scripts.run_ml_exit_price_probe --output-dir $output
if ($LASTEXITCODE -ne 0) { throw 'Exit-price probe failed' }
uv run --locked --python 3.12 python -m scripts.run_ml_exit_price_probe --replay-from $output
if ($LASTEXITCODE -ne 0) { throw 'Exit-price replay failed' }
```

Use a separate worktree as in earlier local pilots. The operator's original
checkout has an unfinished merge and must not be switched or reset.

## Validation and decision after the local result

35 focused tests passed: 11 new probe tests, 10 existing acquisition tests and
14 packaging tests. Canaries cover late/reused history, duplicate dates, holdout
rows, rate-limit/control stops, invalid response preservation, path/inventory
tampering, raw hash tampering, offline replay and overwrite rejection.

Remote direct requests returned Stooq APC HTTP 404 and Yahoo FRCB HTTP 429.
These are endpoint-access observations, not proof of missing historical data.
Yahoo was not retried after its rate limit. The actual runner's Stooq SPY control
also returned 404, skipped all eight targets, and passed offline replay. That
manifest and report are committed under `evidence/ml_exit_price_probe_host_20260909/`.
The local run is necessary to resolve
provider access and actual target coverage from the operator's environment.

Review the returned raw histories against the named events and adjustment basis.
If acquired/failed-stock history cannot be recovered, do not expand downloads or
run the broad-equity model. The next decision would be an explicit change of
research universe/design. If recovery works, expand the same source method
against the dated roster and reconcile all remaining exits before model fitting.
