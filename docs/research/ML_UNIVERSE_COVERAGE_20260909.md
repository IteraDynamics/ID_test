# Historical universe and price reconciliation — 2026-09-09

**BROAD_UNIVERSE_UNSUPPORTED_BY_SUPPLIED_DATA.** The supplied files establish
neither the proposed 2010–2024 top-100 operating-company universe nor complete
2019–2024 S&P membership. No model universe or evaluation period is approved.
Zero fits, no economic test, no Core changes.

This completes the bounded follow-up identified in
`ML_PIT_FEATURE_PILOT_20260909.md`. Sources:
`itera_local_data_inventory.csv` (959 entries) and
`itera_data_samples_20260909_103154.zip` (279 price manifests, eight price samples,
and a change calendar). Input member hashes are recorded in the JSON report.
No new subscription, price download or external security mapping was used.

## Results

The calendar has 262 eligible events, 2019-01-18 through 2024-12-23, covering
246 distinct ticker strings. Post-2024 events are excluded from coverage.

| Mutually exclusive ticker category | Count |
| --- | ---: |
| Manifest endpoints overlap all listed events | 166 |
| No matching manifest or root daily price file | 72 |
| History starts entirely after 2024 | 3 |
| Other history starts after at least one event | 5 |
| Total | 246 |

All 72 missing-manifest tickers also lack an exact same-name daily CSV anywhere
in the supplied inventory, including nested folders. This is a filename finding,
not proof that an alias or other provider cannot recover the history.
174 tickers have manifests. Of 262 event rows, 77 lack a manifest, 9 precede the
recorded history, and 176 fall within a manifest range.

Range overlap is **not usable-price verification**. Most daily files were not
uploaded. Their endpoints cannot establish continuity, actions, identity or
liquidation outcomes. Seven event tickers plus SPY have price samples in the ZIP;
this reconciliation inspects sample date counts, endpoints and duplicates only.

## Late-start exceptions

| Ticker | Relevant event date(s) | History begins |
| --- | --- | --- |
| NFX | Removal 2019-02-15 | 2026-07-07 |
| APC | Removal 2019-08-09 | 2026-02-12 |
| STI | Removal 2019-12-09 | 2022-05-02 |
| LB | Removal 2021-08-03 | 2024-06-28 |
| SBNY | Addition 2021-12-20; removal 2023-03-15 | 2024-08-15 |
| INFO | Removal 2022-03-02 | 2024-10-10 |
| FB | Removal 2022-06-09 | 2025-06-26 |
| VLTO | Addition 2023-10-02 | 2023-10-04 |

VLTO is a short boundary gap. Histories beginning years after removal need
security-identity checks. The subsequent acquisition pilot retrieved META back
to 2012, making FB/META a mapping-repair candidate. No relabeling is performed.
Same-day add/remove pairs alone are not proof of ticker continuity.

## Why this is not a complete universe

The repo's `fetch_sp500_reconstitution_events.py` explicitly collects a change
log starting in 2019. The supplied inventory/ZIP contains no dated complete
membership baseline. Names that never change membership are absent from a change
log. First removal implies prior membership for that name, not the full roster.

Using the union of names that changed in 2019–2024 would use future changes to
define the earlier population. It cannot substitute for point-in-time membership.
The original top-100 nonfinancial operating-company design also requires a
broader candidate roster, historical classifications, issuer/share-class IDs,
liquidity and nominal prices. S&P membership alone does not meet that contract.

HRS removal and LHX addition are dated Saturday 2019-06-01 in the supplied
calendar. Both require source verification; no guessed session shift is applied.

## Saved evidence and reproduction

The following CSVs are committed to GitHub under
`evidence/ml_universe_coverage_20260909/`:

- `ticker_coverage.csv`: all 246 tickers, file presence, range bounds, event counts.
- `event_coverage.csv`: all 262 events, weekday and range mismatch classification.
- `same_day_pairs.csv`: one-add/one-remove dates, all explicitly unverified.
- `universe_coverage_report.json`: exact counts, limitations, input/output hashes,
  and all 72 missing names.

`scripts/reconcile_ml_universe_coverage.py` reads the local inventory and flat
ZIP members without extracting paths. It rejects duplicate ZIP names, duplicate
events, invalid actions and manifest/name conflicts. It computes the entire
output twice and checks byte equality before creating a fresh output directory.

```powershell
uv run --locked --python 3.12 python -m scripts.reconcile_ml_universe_coverage `
    --inventory 'PATH_TO\itera_local_data_inventory.csv' `
    --samples-zip 'PATH_TO\itera_data_samples_20260909_103154.zip' `
    --output-dir 'PATH_TO\new_universe_coverage_output'
if ($LASTEXITCODE -ne 0) { throw 'Universe reconciliation failed' }
```

Seven reconciliation cases plus fourteen packaging cases passed (21 total).
Tests cover future-calendar injection leaving coverage CSVs unchanged, missing
and late histories, no automatic aliasing, range-only evidence, invalid inputs,
nested paths and deterministic ordering. Actual uploaded-source output matched
on both complete builds.

## Decision and next repair

Close the original design's **current local-data feasibility attempt** as
unsupported. This is not a negative ML or return-signal result and does not
invalidate unrelated ETF experiments.

Before expanding acquisition, the next repair must provide a dated complete
roster and historical identity mapping. For a proposed reduced 2019–2024
S&P-based scope, obtain an initial 2019 membership baseline and reconcile every
change, including aliases, mergers, share classes and the weekend pair. Then
use the 72-name list and nine event gaps to target histories and terminal outcomes.
That reduced scope is an explicit amendment, not an automatic replacement for
the original proposal.

Success means a named universe, defensible period and terminal outcomes for exits.
If free sources cannot establish those, stop this broad-equity historical test.
Today's survivors, the event-union and 166 overlapping manifest ranges are not
approved fallback investment universes. No more feature/model expansion is
justified before resolving this source question.
