# Active equity: prospective SEC enrollment and filing inbox

This continues the active-equity pilot. Crypto/timeframe exploration is parked.
The hypothesis, 20-issuer cohort, accounting comparator and portfolio limits stay
as originally frozen. This is a feed adapter, not a new strategy or performance run.
No existing pilot/specification/prompt, Core, runtime or dependency file changes.

## Feed decision

Use SEC daily master indexes for 8-K, 10-Q, 10-K and their amendments. Freeze all
CIKs with a nonempty exchange in SEC company_tickers_exchange.json at enrollment.
Retain all associated listings, then resolve common-stock eligibility and issuer
identity during evidence review. Do not filter the snapshot by earnings, future
results or a handpicked stock list. This universe excludes later listings absent
from the snapshot; it is not exhaustive US-equity coverage. SEC itself does not
guarantee the exchange mapping's accuracy or scope.

Each relevant filing must be reviewed for earnings, statements or guidance, with
nonrelevant filings, amendments and duplicate disclosures logged rather than
silently discarded. A filing date is not announcement time. Earlier issuer
releases and SEC acceptance/dissemination need review before deciding if an event
is inside the registered window. Resolve event-time capitalization, prior-session
ADV20, instrument type, sector, comparable revenue and operating margins from
attributable evidence. No missing value becomes a reject or a screen failure.

Choose the first 20 distinct eligible issuers under the original selection rule
only after full coverage and unresolved items are reviewed. Then review all 20
with the frozen analyst prompt, before portfolio proposals. No price at the
original earnings announcement will be credited as an executable entry.

SEC reference checked 2026-09-15:
https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
This documents daily index fields, nightly generation, correction limitations,
exchange mappings, and required identifying User-Agent headers. Access is public;
no API key or paid feed is introduced. This adapter serializes requests with at
least 250ms spacing and stops on 403/429; it does not bypass access blocks.

## Local commands

Continue in the existing checkout and pilot. Enroll once:

```powershell
Set-Location 'C:\Dev\IteraDynamics\ID_active_equity_20260914'
git switch research/active-equity-pilot-20260914
if ($LASTEXITCODE -ne 0) { throw 'Branch switch failed' }
git pull --ff-only origin research/active-equity-pilot-20260914
if ($LASTEXITCODE -ne 0) { throw 'Pull failed' }
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_active_equity_sec_feed.ps1 -Mode Enroll -PilotDir '.\artifacts\active_equity_pilot_20260915_084801_765'
```

The script prompts for your actual contact email for the SEC User-Agent; it is
sent to SEC as a request header and is not saved in the research ZIP. It downloads
one issuer mapping, registers its snapshot and the locally authored feed protocol,
and freezes a UTC start 24-48 hours after enrollment. This is not retrospective
enrollment. The protocol includes the collector code hash. Duplicate enrollment
is refused; a failed attempt before enrollment may leave auditable source records
and can be rerun. Do not delete or recreate the existing pilot.

Upload the path printed as `UPLOAD SEC FEED ZIP`. The ZIP includes the existing
pilot journal/evidence export and the feed-run summary. An enrolled universe is
not yet an eligible 20-company cohort. No forecasts or investment results exist.

After `suggested_first_collect_at` in the enrollment summary, run:

```powershell
Set-Location 'C:\Dev\IteraDynamics\ID_active_equity_20260914'
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_active_equity_sec_feed.ps1 -Mode Collect -PilotDir '.\artifacts\active_equity_pilot_20260915_084801_765'
```

Collect is manually invoked, not scheduled. It captures daily index files through
two UTC dates before execution, retaining a boundary day for timezone review.
It revisits the full elapsed window (maximum 90 days) so later index corrections
remain visible as additional snapshots. Review duplicate accession paths across
index dates; do not count them as new events. Weekend requests are skipped under
SEC's stated business-day indexing convention. Missing weekday indexes, including
possible holidays, remain unresolved. HTTP 404 never proves a holiday or an empty
feed. No automated complete-coverage assertion is made, even after all downloads
succeed. An early empty collection is not evidence of no qualifying businesses.

Read `summary.json`, `coverage.json` and `filing_candidates.json` in the feed ZIP.
Candidates contain links to filings, not the downloaded filing documents. The next
analyst review obtains actual disclosures and eligibility evidence, resolves all
inbox items, and prepares cohort records. This implementation cannot autonomously
finish those research judgments. The nested unchanged pilot report's downloads=0
describes its offline exporter only; feed summary reports actual request attempts.
Snapshot timestamps explicitly describe local capture, not upstream publication.

## Verification and limits

Executed Linux / Python 3.12.14 / pytest 9.0.3 with locked repository dependencies:

```text
uv run --locked --python 3.12 --extra dev python -m pytest tests/test_active_equity_pilot.py tests/test_active_equity_sec_feed.py tests/test_core_v1_runtime_identity.py -q -W error
```

89 tests passed: 68 existing pilot tests, 19 feed tests, two Core identity tests.
Feed tests use synthetic mocked HTTP responses and real temporary SQLite journals;
they exercise enrollment, source hashing, future boundaries, frozen code, coverage
errors, selection nonclaims, malformed inputs and portable ZIP output. No live SEC
download was executed in this build environment. Official service documentation
was checked; actual SEC access from the user's machine remains to be exercised.
PowerShell was reviewed, not executed here. No strategy backtest was run.
