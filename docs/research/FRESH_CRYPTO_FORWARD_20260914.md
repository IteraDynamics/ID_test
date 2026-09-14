# Frozen crypto rules: historical forward validation

## Question and evidence boundary

The operator approved the next step in `FRESH_CRYPTO_LONG_HISTORY_RESULT_20260914.md`:
test the frozen state rule on later history. Does its incremental net return/risk
trade-off versus plain trend, allocation and the fixed blend persist in 2025 onward?
The competing explanation is that the development gain reflects a small number of
bear/recovery episodes and cost savings, without stable additional predictive value.

This specification is committed before the operator's forward market run. Engineering
checks use synthetic prices only. No post-2024 market returns were evaluated during
implementation. This is **locked historical forward validation**, not globally pristine
final OOS: earlier repo BTC/ETH research included 2025. The 2026 access classification
defaults to `unknown`; a local operator can report `already_inspected` or
`not_known_inspected`. The latter is not proof of untouched history. Every output
retains this limitation. No new ML fit, parameter search or Monte Carlo is included.

## Unchanged strategies and comparisons

The candidate freeze in
`evidence/fresh_crypto_long_history_20260914/market_review/candidate_freeze.json`
is the authority for the strategy definition. Its normalized SHA-256 is
`b8676a153882587c55b8bbeb76d59022490e12c960920473d0f7d087f4585230`.
The runner verifies it and all 14 original code/specification dependency hashes,
allowing uniform LF/CRLF conversion, before a market run.

- Primary risk-adjusted research candidate: `state_rule_vol20_band2`.
- Higher-risk research alternative: `state_rule_vol40_band2`.
- Keep all 20 original policies: state, trend, allocation and fixed blend at 20/40
  volatility settings with exact/2% band execution, plus BTC, ETH, initial 50/50
  buy-and-hold and zero-yield cash. Exact state rules are diagnostics; the blend is
  a comparator. Preserve all outputs rather than selecting a forward winner.
- Preserve the two-thirds trend-agreement threshold, 1.25 fast/slow volatility
  threshold, weekly state decision schedule, daily expert sizing, 60-day covariance
  with 10% diagonal shrinkage, and 365-day risk annualization.
- Unlevered spot and existing band exceptions, self-financing inventory accounting
  and final-exit fee treatment remain unchanged. Base costs are 30 bps one way,
  stress costs 75 bps, with frictionless and separate extra-day-delay scenarios.

This gives 80 continuous ledgers. No absolute Sharpe/CAGR promotion threshold or
old charter performance target is imported into this exploratory exercise.

## Frozen calendar and initial inventory

The evaluation starts **January 1, 2025**. Each policy begins with one unit of USD
cash and zero coin inventory. This isolates the new period's deployable cash-start
behavior rather than inheriting positions selected in 2018. No pre-2025 portfolio
P&L contributes to forward metrics.

Deterministic features and weekly state decisions continue from the original 2018
schedule. The initial target uses the December 30, 2024 signal bar, available on
December 31, with the base fill on January 1. The state coefficient is inherited
from the most recent scheduled Monday-fill decision; there is no extra midweek
state update on January 1. Expert weights and covariance use the December 30 bar.
The first delayed fill is January 2, with January 1 held in cash. Subsequent state
choices retain Monday base fills; the delay scenario shifts fills, not decisions.

The common end is the earlier eligible last date of the two specified local files,
with a hard cap of **August 26, 2026**, chosen from their already-known coverage names.
Both files must have complete daily coverage through December 31, 2025. The end is
selected from date labels before forward OHLCV validation or performance calculation;
it cannot be supplied as a performance-dependent CLI option. If only 2025 is jointly
available, report that full year and omit 2026. No missing interior dates are dropped.

No inventory reset occurs at January 1, 2026. Every policy liquidates at the common
final day's open with applicable fees, including buy-and-hold. The final day's close
does not contribute P&L after liquidation. Year slices use returns from this continuous
ledger and do not impose fictional year-boundary exits/re-entries. The evaluated 2025
slice therefore has different terminal handling when a 2026 extension is present.

## Existing local data, provenance and preparation

The default raw files are the exact daily filenames identified by the operator:

| Asset | Filename under `DataRoot` |
|---|---|
| BTC | `btcusd_86400s_2015-07-15_to_2026-08-26.csv` |
| ETH | `ethusd_86400s_2016-05-13_to_2026-08-26.csv` |

Default `DataRoot` is the sibling `ID_test/data` directory. Explicit `-DataRoot`,
`-BtcCsv` and `-EthCsv` paths are supported. No arbitrary file search, automatic
choice among conflicting histories, or download is implemented. Inputs require one
timestamp/date/datetime/time column and OHLCV, with UTC daily bar-start timestamps.
Seconds/milliseconds epochs and ISO dates are supported. This runner deliberately
uses the identified daily files, not intraday aggregation.

The reviewed development snapshot comes from the known long-history, ML or crypto
results directory/ZIP, in that order. A missing explicit directory also checks its
sibling `.zip`; no explicit missing path silently falls back to another result.
Git does not restore local data or result artifacts.

Preparation proceeds before tests and evaluation:

1. Verify committed code/specification and the original candidate freeze.
2. Validate the prior result's exact pinned 2017-2024 BTC/ETH inputs.
3. Inspect raw headers/date labels, record raw-file hashes and the common end in
   `run_plan.json` before reading forward price columns. Reject missing, duplicate,
   non-daily or non-midnight dates in the eligible calendar.
4. Validate OHLCV inside the selected window. Do not convert or evaluate prices
   outside it. Require finite positive prices, nonnegative volume and valid ranges.
5. Compare all 2,922 development OHLCV rows per asset against the reviewed snapshot.
   Allow only numerical serialization noise (`rtol=1e-12`, `atol=1e-10`), record the
   maximum per-field differences and preserve reviewed development values exactly.
   Refuse a conflicting source or revised history instead of silently splicing it.
6. Save normalized complete 2017-through-end inputs and their hashes, the original
   source report, specification, candidate freeze and `prepared.json`. Recheck raw
   hashes to detect files changing during preparation.

The evaluation process consumes only these prepared snapshots and checks their
identity, hashes, calendar and code/environment before constructing strategies.
Directory or ZIP outputs are immutable; a failed/finished evaluation requires a new
run directory. Preparation failures produce a data-check ZIP and an explicit error.
Vendor acquisition history and execution-venue equivalence remain unverified.

## Reporting, checks and interpretation

Report full-forward and separate 2025/2026 slices: total return, CAGR, cash-excess
Sharpe, maximum drawdown, realized volatility, Calmar, certainty equivalent, turnover,
execution drag, exposure, worst day and underwater duration using existing formulas.
Partial-year totals are explicit; annualized short-window figures are not forecasts.
Sharpe/volatility use 365; CAGR/turnover use elapsed calendar days divided by 365.25.

Compare both candidates with trend, allocation and blend at matching risk/band settings,
plus all four spot/cash benchmarks on matched dates. Spot benchmarks have different
risk, which is flagged in comparisons. Save features, targets, carried pre-entry state
decisions, all ledgers, annual returns and artifact hashes. Do not refit thresholds,
change risk settings or suppress a scenario in response to these results.

Every run regenerates schedules and all 80 ledgers and compares them exactly within
the same environment. Independently check compounded NAV, asset P&L, equity weights,
entry/delay boundaries and 12 closed-form buy-and-hold price/fee identities. A runtime
canary must reject a deliberately changed return. Tests cover the January state/entry
boundary, future perturbations, preserved original targets, calendar/data corruption,
frozen dependencies and prepared-input tampering. Synthetic fixtures test mechanics;
they say nothing about expected market performance.

Evidence against continuation would include disappearance of the incremental
cost-adjusted state-versus-trend benefit across both year slices, weaker downside
control than the simpler matched alternatives, or dependence on optimistic execution.
Assess the size and consistency of those differences jointly, without inventing a
single pass/fail metric. Strong forward results would justify dependence-aware
uncertainty analysis and further prospective research; this runner cannot authorize
paper/live changes or capital deployment.

## Operator procedure

From a fresh PowerShell session in the research checkout:

```powershell
Set-Location 'C:\Dev\IteraDynamics\ID_fresh_discovery_20260914'
git switch research/fresh-strategy-discovery-20260914
if ($LASTEXITCODE -ne 0) { throw 'Branch switch failed' }
git pull --ff-only origin research/fresh-strategy-discovery-20260914
if ($LASTEXITCODE -ne 0) { throw 'Pull failed' }
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_fresh_crypto_forward.ps1 -DataRoot 'C:\Dev\IteraDynamics\ID_test\data'
```

The wrapper finds the existing result directory or ZIP, prepares local inputs, runs
focused tests, evaluates the frozen strategies and prints `SHARE FORWARD RESULTS ZIP`.
Supply `-SourceRun` if the previous result was moved. Optional `-PriorAccess2026`
records known prior access; the default accurately retains uncertainty. Share the
printed result ZIP for audit before any redesign or simulation. Core/runtime and
paper/live parameters remain unchanged.
