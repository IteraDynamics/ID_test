# ML data acquisition pilot — 2026-09-09

Status: implementation tested with synthetic sources and local sample validation;
**live acquisition has not been run**. No fitting or performance screen.
Parent: [monthly allocation redesign](ML_DECISION_REDESIGN_20260909.md).

## Why this step exists

The operator supplied an inventory of 959 local files and a sample ZIP containing
279 daily-price manifests, eight price CSVs, an earnings CSV and an event calendar.
The 217-name stock batch requested history only from 2019. APC, FB and NFX samples
have no observations through 2024. SBNY begins in August 2024, after its calendar's
March 2023 removal. These are coverage/identity failures, not proof of a specific
replacement issuer. The earnings file has 13,950 pre-2025 rows, 206 tickers, and
37 duplicate ticker/date groups, 36 with conflicting values. Stock manifests use
`auto_adjust=false`; six other manifests, including SPY, use `true`.

[Local audit evidence](evidence/ml_data_local_audit_20260909.json) records source
hashes and bounded checks. Original files are untouched. These findings require
review of affected stock/event work; they do not by themselves invalidate the
separate frozen ETF experiments.

## Pilot scope

Four Yahoo queries: TSLA (ordinary continuing issuer and split example), META and
FB (rename/alias comparison), APC (discontinued historical issuer). Three SEC
entities: Tesla CIK 1318605, Meta CIK 1326801, Anadarko CIK 773910. CIKs identify
filing entities, not securities, classes or historical Yahoo ticker mappings.

Yahoo requests daily history from 2005-01-01 through 2024-12-31, with adjustment,
back-adjustment and repair disabled, corporate actions enabled, and missing rows
retained. It saves the full **provider-returned** table, including adjusted close,
dividends and splits if supplied. This is not a claim of raw unadjusted exchange
prices: provider OHLC can already reflect splits. Current metadata is saved only
as an identity hint. A matching ticker is never treated as verified identity.

SEC requests use fixed CIKs, saving original companyfacts, submissions and relevant
historical submission pages (maximum 20 pages per entity). Requests are sequential,
spaced at least 0.35 seconds apart, with up to three attempts for transient failures.
403 is recorded, not worked around. Raw SEC responses may contain later filings;
they remain quarantined source evidence. Diagnostics include only facts filed by
2024-12-31 whose period end is also no later than that cutoff. Later restatements
of older periods are excluded. No holdout returns or performance are computed.

Concept diagnostics cover USD assets, liabilities, net income, operating cash flow,
three revenue tags and operating income. They count fact versions and exact
accession/form/filing-date matches with timezone-aware acceptance timestamps.
They do not yet construct quarterly features or choose between competing contexts.
An acceptance timestamp is not a guarantee of market dissemination or tradability.
Dates without valid timestamps remain unmatched; no invented timestamp is supplied.

## Reading the outputs

- `source_manifest.json`: request sources, acquired byte hashes, package version,
  runner hash, timestamp and source failure types/HTTP status. Contact email is not
  written to these artifacts.
- `raw/`: original SEC JSON and provider-returned Yahoo tables/identity hints.
- `pilot_report.json`: coverage by year, event-date checks, missing fields,
  nonfinite values, duplicate dates, SEC entity and concept diagnostics.

`ACQUISITION_INCOMPLETE` means a request or validation failed, or a price sample
failed a structural/event-date check. `SOURCE_REVIEW_REQUIRED` means those checks
completed, not that the dataset is usable. `ready_for_model` remains false: this
pilot cannot establish a complete historical universe, security identity mapping,
terminal delisting outcomes or correct financial feature semantics. A discontinued
symbol failure is useful evidence; the script does not drop that case to pass.

A completed diagnostic exits zero even if its report records source failures.
Infrastructure errors, corrupt replay inputs, missing contact configuration and
existing output directories exit nonzero. Inspect the report status as well as the
process exit code. Unexpected interruption may leave a partial directory; use a
new output directory for another acquisition. No automatic overwrite is supported.

## Windows execution

Use an isolated worktree because the original checkout previously had an unfinished
merge. The script uses an absolute output path and needs no existing data files.
The email supplied below is transmitted to the SEC as its required identification
header; it is not an API key and is not included in the report.

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Dev\IteraDynamics\ID_test"
$work = "C:\Dev\IteraDynamics\ID_test_ml_data_pilot"
$branch = "research/ml-data-acquisition-pilot-20260909"

Set-Location $repo
git fetch origin "refs/heads/${branch}:refs/remotes/origin/${branch}"
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git worktree add --detach $work "origin/$branch"
if ($LASTEXITCODE -ne 0) { throw "Worktree creation failed" }
Set-Location $work

$email = Read-Host "Your real contact email for SEC data requests"
$env:SEC_USER_AGENT = "IteraDynamics research $email"
$output = Join-Path $repo ("artifacts\ml_data_pilot_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
uv run --locked --python 3.12 python -m scripts.run_ml_data_acquisition_pilot --output-dir $output
if ($LASTEXITCODE -ne 0) { throw "Pilot execution failed; share the error" }
Get-Content (Join-Path $output "pilot_report.json") -Raw
Write-Output "Share pilot_report.json and source_manifest.json from: $output"
```

If the worktree already exists, use it after checking its commit rather than
repeating `git worktree add`. Do not abort the original checkout's merge.

Optional exact saved-source replay (no requests, no email required):

```powershell
$replay = $output + "_replay"
uv run --locked --python 3.12 python -m scripts.run_ml_data_acquisition_pilot --replay-from $output --output-dir $replay
if ($LASTEXITCODE -ne 0) { throw "Replay failed" }
if ((Get-FileHash (Join-Path $output "pilot_report.json")).Hash -ne
    (Get-FileHash (Join-Path $replay "pilot_report.json")).Hash) {
    throw "Report replay differs"
}
```

## Decision after live results

Inspect access errors, price coverage and issuer identity before widening the pilot.
If free sources cannot recover discontinued securities and historical membership,
the original broad-universe design remains infeasible. Do not silently replace it
with today's survivors. If SEC fact versions and timestamps are available, the next
bounded task is period/context and availability validation, followed by a documented
source/universe decision. No economic screen or model configuration changes occur
in this acquisition step. Core v1 and existing 005–013 runners remain unchanged.

## Validation

Ten pilot tests cover missing historical event coverage, duplicate dates, missing
columns, nonfinite values, invalid dates, post-cutoff price exclusion, late-filed
restatement exclusion, accession timestamp matching, CIK and malformed-array
rejection, exact saved-source replay, source corruption/path/inventory rejection,
no-overwrite behavior, contact preflight, and mocked action/archive acquisition.
All ten passed; all fourteen scripts-packaging tests passed. Network access and
real SEC/Yahoo response compatibility still require the operator's live run.

## Primary references checked 2026-09-09

- [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces):
  submissions archives, companyfacts, CIK conventions and XBRL scope.
- [SEC access guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
- [yfinance history API](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html).
  The locked local yfinance 1.5.2 method signature was also checked.
- Filing-entity anchors: [Tesla](https://www.sec.gov/Archives/edgar/data/1318605/000095017022000796/tsla-20211231.htm),
  [Facebook/Meta](https://www.sec.gov/Archives/edgar/data/1326801/000132680119000009/fb-12312018x10k.htm),
  [Anadarko](https://www.sec.gov/Archives/edgar/data/773910/000077391019000009/apc201810k-10k.htm).
