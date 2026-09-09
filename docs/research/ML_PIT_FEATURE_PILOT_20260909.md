# Point-in-time issuer feature pilot — 2026-09-09

Status: **PIT_FEATURE_PILOT_REVIEW_REQUIRED**. Offline data engineering, zero fits.
Parent: `ML_DATA_ACQUISITION_PILOT_20260909.md`; broader proposal:
`ML_DECISION_REDESIGN_20260909.md`. This is the bounded period/context follow-up
requested after the operator supplied the complete acquisition bundle.

## What was built and run

`scripts/run_ml_pit_feature_pilot.py` consumes the saved, hash-verified pilot.
It emits all selected filing versions, eight recent quarters at each filing
snapshot, and trailing-year financial values and ratios. Every populated result
carries source fact IDs, accession numbers and the latest required availability
instant. There is no network access, model, price return, allocation or trading.
Core v1 and experiments 005–013 are untouched.

Actual source: `ml_data_pilot_20260909_110717_review_20260909_113736.zip`.
The fourteen raw files matched their recorded byte lengths and SHA-256 hashes;
replaying acquisition reproduced its report byte for byte. Manifest SHA-256:
`80153824ae7e736271d98301628076cadeea3d166c7df6cea4c80deb711befa4`.

The feature runner computed its outputs twice and compared the complete byte
payloads before writing. Actual outputs:

| Issuer | Distinct fact versions | Filing snapshots | NI/assets populated | Total CFO/assets populated | Liabilities/assets populated |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tesla | 1,192 | 55 | 53 | 35 | 55 |
| Meta | 826 | 50 | 48 | 48 | 50 |
| Anadarko | 706 | 41 | 39 | 36 | 0 |

Counts are filing snapshots, not independent samples or a monthly investment
universe. Populated does not mean fully validated. The three CSVs contain 2,724
fact versions, 8,176 quarter rows (including explicit missing values), and 2,336
feature rows. Evidence and hashes are in
`evidence/ml_pit_feature_pilot_20260909.json`.

## Exact rules and limits

- Only the three named filing entities, USD, 10-K/10-Q and amendments, filed from
  2005 through 2024. Facts with later filing/end dates are excluded before use.
  Filing accession, form, date and entity must agree with submissions metadata.
- Calendar quarters only. Exact quarter end and Jan/Apr/Jul/Oct quarter starts
  or same-calendar-year January YTD starts. Other fiscal calendars, transition
  periods and non-USD units are outside this pilot.
- Availability is the **later of acceptance UTC + 24 hours and midnight UTC
  after the official filing date**. Some Tesla filings were accepted Friday
  with Monday filing dates; this rule prevents premature weekend availability.
  This is a conservative pilot convention, not measured dissemination latency
  or an exchange-session label. A future monthly consumer must select only
  snapshots available at its actual decision time, with a freshness policy.
- Each as-of query chooses the latest then-available version of the exact
  tag/start/end context. Same-filing duplicate values are collapsed. Conflicting
  values poison that version rather than allowing fallback to an older value.
- Quarters use directly reported three-month values, or YTD minus the previous
  YTD with the same tag and fiscal start. Q4 can be annual minus nine months.
  A newer cumulative revision supersedes an older direct quarter; absent
  compatible components produce missing values. Cross-filing subtraction is
  explicitly marked `YTD_DIFFERENCE_CROSS_FILING_REVIEW`.
- At December year-end, TTM uses the directly reported annual observation.
  Otherwise it requires four contiguous calendar quarters of the same tag.
  The four-quarter sum is marked for cross-filing accounting-basis review.
  There is no interpolation, zero filling, future backfill or tag splicing.
- Features: per-tag TTM net income, operating cash flow (total and continuing
  separately), revenue and operating income; assets, liabilities and total
  equity; TTM NI/assets, total CFO/assets, continuing CFO/assets,
  (TTM NI minus TTM total CFO)/assets, and liabilities/assets. Denominator is
  same-period **ending** assets, strictly positive. These are pilot formulas,
  not a frozen broad-universe feature contract.
- Revenue concepts remain separate; no automatic transition alias. Continuing
  operations cash flow is never a global replacement for total cash flow.
- Assets minus total equity is emitted only as a separate same-filing diagnostic.
  It is never used to fill liabilities or leverage. Redeemable/mezzanine equity
  and other presentation details have not been ruled out comprehensively.
- CSV blanks mean unavailable; method columns give derivation/review status.
  Normalized fact exclusions are counted by reason. 284 post-cutoff rows and
  20 out-of-contract forms were excluded; no malformed-context exclusions or
  conflicting versions occurred in this actual source bundle.

## Checks against a filed statement

Six independently read values from Tesla's
[2015 10-K cash-flow statement](https://www.sec.gov/Archives/edgar/data/1318605/000156459016013195/tsla-10k_20151231.htm)
match the exact accession `0001564590-16-013195` in the saved facts:

| Year | Operating cash flow, USD | Net loss, USD |
| --- | ---: | ---: |
| 2013 | 264,804,000 | -74,014,000 |
| 2014 | -57,337,000 | -294,040,000 |
| 2015 | -524,499,000 | -888,663,000 |

The cash-flow rows use the continuing-operations tag in Companyfacts. This
supports those six observations, not a blanket alias across Tesla's history or
other issuers. The full XBRL contexts and statements of all three issuers have
not been independently reconciled. Attempts to retrieve Anadarko's primary
filing in this session failed; its balance-sheet diagnostic remains unapproved.

## Validation

40 focused tests passed: 16 feature-pilot cases, 10 acquisition cases and 14
packaging cases. Tests exercise future-revision injection, cumulative versus
quarterly values, missing quarters, tag separation, latest conflicts, revised
cumulative values, duplicate rows, cutoff exclusion, timezone/matching failures,
Friday/Monday timing, liabilities non-substitution, exact CLI replay, no overwrite,
source corruption before output, and a deliberately wrong statement value.

The live run also injected extreme 2025 revisions into each issuer's input and
confirmed no change to its pre-2025 snapshot. Both full output builds matched.
All six filing spot checks passed. These checks prove bounded implementation
properties; accounting comparability and universe feasibility remain separate.

## Replay locally (optional; already executed on the uploaded sources)

Run in the new branch checkout with Python 3.12 and the existing lockfile:

```powershell
$source = 'C:\Dev\IteraDynamics\ID_test\artifacts\ml_data_pilot_20260909_110717'
$output = Join-Path (Split-Path $source) ('ml_pit_feature_pilot_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
uv run --locked --python 3.12 python -m scripts.run_ml_pit_feature_pilot --input-root $source --output-dir $output
if ($LASTEXITCODE -ne 0) { throw 'Feature pilot failed' }
Get-Content (Join-Path $output 'feature_pilot_report.json') -Raw
```

Do not run from an older checkout lacking the module. The operator's original
checkout has an unfinished merge; use a separate worktree without disturbing it:

```powershell
& {
    $repo = 'C:\Dev\IteraDynamics\ID_test'
    $work = 'C:\Dev\IteraDynamics\ID_test_ml_pit_feature_pilot'
    $branch = 'research/ml-pit-feature-pilot-20260909'
    git -C $repo fetch origin "${branch}:refs/remotes/origin/${branch}"
    if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
    git -C $repo worktree add --detach $work "origin/$branch"
    if ($LASTEXITCODE -ne 0) { throw 'Worktree creation failed' }
    Set-Location $work
}
```

Use the existing worktree if already created; never abort the original merge to
run this pilot. Outputs are a new directory containing `fact_versions.csv`,
`quarterly_snapshots.csv`, `feature_snapshots.csv`, and `feature_pilot_report.json`.
The implementation hashes normalize CRLF to LF so the same checkout's Windows
line endings do not change the report. Acquisition raw-file hashes are exact.

## Decision and next item

The free SEC source is sufficient to prototype historical issuer features with
explicit provenance. The original broad-stock ML experiment is **not yet ready**:
Anadarko lacks usable prices in this bundle, historical universe and security
identity remain unresolved, and cross-filing accounting bases require care.
Do not substitute present-day survivors or treat the three pilot issuers as an
investment test universe. No model performance or promotion claim follows.

The next distinct item is a bounded **historical universe and price coverage
reconciliation using the existing local inventory/calendar**, with explicit
identity changes and missing/delisted names. Its deliverable should be a concrete
supported universe/date range or an explicit rejection of the broad-stock design,
not another round of model tuning or open-ended acquisition. A reduced universe
would require an explicit amended research scope, with its selection bias stated.
