# SPY quote audit — 11 September 2026

Decision: **continue to full contract-lifecycle reconstruction**. These quotes
support an economically meaningful pricing test. They do not yet establish
profitable option selling. The earlier modeled condor P&L remains unverified.

## Observed evidence

Input: `options_quote_review_20260911_150922.zip`, SHA-256
`981d7485757710ed3bb6688db228fbe508b75090744fdd3003529a5663a725dc`.
All five CSV byte hashes match the supplied manifest. The annual source hashes
are supplied provenance; annual Parquets were not available for independent
rehashing here.

248,448 rows cover 55 sessions in five deliberately selected inspection windows.
Every encoded SPY contract ID matches its expiration, call/put type and strike.
No duplicate contract-day keys or crossed quotes were found. Every row has
`in_the_money=0`, including deep ITM contracts: this field is unusable and excluded.
`mark` differs from bid/ask midpoint by more than one cent on 848 rows; neither
mark nor last is used for trade pricing. Zero bids occur on 21,142 rows and must
not be confused with executable short-sale premiums.

The fixed pricing diagnostic uses the expiry nearest 35 days within 30–45 days,
short strikes nearest absolute delta .16 (maximum distance .05), and long wings
nearest 2% beyond each short strike. Earlier expiration/lower strike break ties.
These are operational diagnostic choices, not an optimized trading strategy.
Contracts are selected before checking prices; bad quotes do not trigger a search
for a more favorable structure. Nine sessions lack eligible geometry under this
rule; they are retained as unavailable, not repaired.

| Window | Candidate sessions | Structures available | Median bid/ask credit per standard condor | Median immediate round-trip spread cost |
|---|---:|---:|---:|---:|
| November 2017 | 11 | 7 | $61.00 | $8.00 |
| February 2018 | 11 | 9 | $86.00 | $22.00 |
| March 2020 | 11 | 10 | $128.50 | $58.50 |
| June 2022 | 11 | 9 | $217.00 | $19.00 |
| August 2024 | 11 | 11 | $204.00 | $21.00 |

Dollar figures assume standard 100-share deliverables. Entry sells at bid and
buys at ask; immediate liquidation reverses those sides at the same snapshot.
Commissions are excluded from this diagnostic. Spread cost is not an observed
holding-period loss. The windows contain overlapping candidates and different
wing widths; these credits are neither returns nor comparable capital efficiency.

All 46 selected structures have positive same-snapshot credits and positive
bid/ask sizes on every leg. The median entry concession relative to midpoint,
computed separately for each candidate, is 8.67%. All 42 structures with an
available next session retain all four contract IDs. However, the structure
selected on 2018-02-02 has a **negative $368 quoted entry credit on 2018-02-05**.
That would be rejected as an entry; it is not a realized loss or a missing-data
problem. This demonstrates why same-session selection/price assumptions matter.

## Source timing and remaining limits

The [preservation mirror's README](https://github.com/anahatsingh-ui/options-dataset-hist/blob/main/README.md)
describes 4 PM Eastern end-of-day snapshots. This is source documentation, not
independent verification of the historical arrival time. Actual records carry
dates only. The technical PDF could not be retrieved during this review.

[OIC's iron-condor documentation](https://www.optionseducation.org/strategies/all-strategies/short-condor)
explains that early assignment and expiration can leave stock exposure. Therefore
bounded terminal payoff is not an operational guarantee. Deliverables, dividends,
exercise/assignment and simultaneous fills remain unverified. Closing before
expiration reduces some exposure but does not eliminate early-assignment risk.

## Next local extraction and subsequent calculation

`scripts/local/run_options_condor_panel.ps1` reads only local 2008–2024 files.
It exports one candidate per calendar month, selected on the first observed
session, plus each selected contract's complete available daily quote history.
The next observed session is recorded as the earliest potential execution date.
No next-session delta is used to choose the contracts. This adds 2008–2012 stress
history to the legacy 2013-onward idea; these additional years are retrospective
research, not a newly untouched holdout. Missing eligibility is reported.

This is one extraction for both daily risk accounting and eventual exit pricing,
not another five-window sampler. It performs no model search or P&L calculation.
Source hashes, actual dependency versions and export hashes are included. Year
mismatches, duplicate contract-day records, schema changes and changing files
fail explicitly. No 2025 source is opened.

Draft next accounting specification: one contract per eligible monthly candidate;
prior-session contract choice; reject nonpositive credit, malformed quotes or
zero relevant displayed size; separately record rejections. Price entries and
exits at adverse quote sides, with an explicit commission sensitivity. Schedule
exit at the first observed session at or below seven calendar days to expiry;
track daily liquidation value and missing quotes, with no zero-return imputation.
An incomplete final cycle is censored and reported. Exact calendar/assignment
assumptions must be resolved before a strong trading claim. This is a draft
research accounting design, not a same-session frozen campaign.

First assess credit received versus subsequent liabilities and costs, crisis
loss concentration and daily portfolio overlap. Positive credits alone do not
pass that test. Only then map capital/risk budgets and annualized returns, with
cash, financing and committed capital explicit. No ML filter or risk scaling is
being introduced to rescue this baseline.

## Reproduction

```
python -m scripts.analyze_options_quote_review --bundle <uploaded.zip> --output-dir <new-directory>
```

Machine-readable results and 55 candidate rows are stored alongside this memo.
The audit was executed on the uploaded CSVs. Two synthetic tests exercise quote
cash-flow identities, rejection of crossed quotes, prior-session selection,
contract history retention, 2025 exclusion and overwrite refusal. They passed
under Python 3.12.14 with PyArrow 21.0.0. PowerShell itself was not executed here.
The full-history extractor was exercised on synthetic Parquets, not the user's
full annual files. There is no CAGR, Sharpe or performance claim from this audit.
