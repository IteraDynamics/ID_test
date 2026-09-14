# Fixed crypto rules — longer development history

## Question and evidence status

The operator approved the next step in `FRESH_CRYPTO_ML_RESULT_20260914.md`: evaluate
the unchanged state rule and fixed 50/50 blend across 2018–2024. The purpose is to
learn whether their return/drawdown trade-offs also hold during 2018's bear market and
2019's recovery. The rule and blend were already inspected on 2020–2024 outcomes.
This is development research, not independent confirmation or a final OOS test.

This specification and implementation are committed before the operator's market run.
Engineering verification uses synthetic prices only. No new parameter search, ML fit,
reserved-period evaluation or Monte Carlo calculation is part of this experiment.

## Fixed comparison

| Family | Role | Volatility settings | Execution treatments |
|---|---|---|---|
| State rule | Candidate | 20%, 40% | Exact, 2% band |
| Fixed 50/50 trend/allocation blend | Candidate | 20%, 40% | Exact, 2% band |
| Trend ensemble | Control | 20%, 40% | Exact, 2% band |
| Risk-controlled equal-weight allocation | Control | 20%, 40% | Exact, 2% band |
| BTC, ETH, 50/50 buy-and-hold; USD cash | Benchmarks | Uncapped, unlevered | Initial entry and final exit |

Eight candidates, eight matched controls and four benchmarks give 20 policies.
All are evaluated with frictionless fills, 30 bps one-way base costs, 75 bps one-way
cost stress, and base costs with one extra day of execution delay. This gives 80
portfolio ledgers. Stress scenarios reuse the same signal targets and mixture choices.

All numerical rules are unchanged from the earlier ML comparison:

- Trend uses the average of positive 90/180/365-day close-return votes for each coin,
  multiplied by 0.5 before applying the existing volatility-sizing function.
- Allocation starts from equal BTC/ETH risky weights and uses identical sizing.
- The covariance estimate uses 60 daily returns, 10% diagonal shrinkage, and 365-day
  annualization. The existing sizing function and full-cash option remain unchanged.
- The fixed blend uses half of each expert's target weights.
- The state rule chooses trend if mean trend agreement is **below** two thirds or
  the mean 20-day/60-day volatility ratio is **above** 1.25; otherwise allocation.
- State choices update on the first eligible signal and thereafter for Monday base
  fills. Expert targets and covariance continue to update daily. No fitted classifier,
  forecast score, confidence hurdle or new threshold is introduced.
- Exact execution follows every target. The 2% band skips trades when total absolute
  risky-weight deviation is below 0.02, except for initial entry, final liquidation,
  full requested exits or a current-weight breach of the lagged covariance risk cap.
- Unlevered spot only; residual USD cash earns zero. Holdings drift between fills.

The previous research modules remain unchanged. A dedicated fixed-rule schedule
builder is checked against the earlier builder on identical synthetic inputs and
start dates. It uses the existing feature/expert calculations and portfolio simulator.

## Data and timing

The exact existing normalized snapshot covers 2017-01-01 through 2024-12-31:

| File | SHA-256 |
|---|---|
| BTC-USD.csv | `9864fb4539fd8199f2c4eab855e7dd8db4aa4e368a5eb670c0f870082a1f58d6` |
| ETH-USD.csv | `993cb7d7b63161181dfa245add3a146fef85a473173038103a8f94de44d4ece5` |

The runner accepts an earlier results directory or flat ZIP containing `report.json`
and these files. It validates the source flags, source manifest hashes, exact input
bytes and full daily calendar. It copies the input bytes and source report into the
new result bundle. Source commit and archive/report hashes are recorded. Original
vendor/acquisition provenance remains unverified. No download path is implemented.

Default lookup checks these known runs in the checkout's `artifacts` directory,
in the listed order, preferring each directory over its matching ZIP:

1. `fresh_crypto_ml_20260914_134645_379`
2. `fresh_crypto_20260914_110447_621`

`-SourceRun` can specify either result anywhere on disk. A missing directory argument
also checks its sibling `.zip`. An explicit missing path fails with the checked paths;
it does not silently switch to a different run. The raw `ID_test/data` directory is not
a results directory. All accepted paths must contain the same pinned input bytes.

Daily timestamps denote UTC bar starts. With the original 365-day feature warm-up,
the first signal bar is 2018-01-01, available at 2018-01-02 00:00 UTC, and the first
base fill is 2018-01-03 00:00 UTC. Extra-day delay enters on January 4 while holding
cash on January 3. Every portfolio is evaluated from January 3, 2018 through final
liquidation at the December 31, 2024 open: 2,555 daily rows per ledger, 204,400 total.

One continuous inventory ledger runs across all years. No yearly reset, model fit or
cash replenishment occurs. Final liquidation includes costs. Daily close marks and
opening-price fill proxies do not establish intraday drawdown or executable capacity.

## Reporting and research decision

Save full-period metrics, annual returns and these fixed subperiods:
2018–2019, 2020–2021, 2022–2024 and 2020–2024 with carried inventory. The last is a
slice of the longer continuous run, not a fresh January 2020 cash restart. Its early
2020 positions, costs and first weekly decision can differ from the previous ML
experiment. Subperiod risk/wealth metrics are calculated from that slice's returns;
they do not imply actual liquidation and re-entry at its boundaries.

Report CAGR, cash-excess Sharpe, maximum drawdown, realized annual volatility, Calmar,
gamma-3 certainty equivalent, average risky exposure, turnover, arithmetic execution
drag, worst day and longest underwater duration using the existing formulas. Sharpe
and volatility annualize with 365; CAGR and turnover use elapsed days/365.25. Each
candidate is compared with both endpoint controls and the other candidate on matched
dates, risk setting and execution treatment. Preserve all scenarios and variants.

The next review should focus on protection in both bear markets, participation in
recoveries, annual concentration, costs, delay sensitivity, and whether a simple blend
already captures the useful trade-off. A more attractive 2020–2024 headline alone
does not answer the longer-history question. There is no automatic winner or promotion
gate. Any final OOS design must separately establish prior access to reserved history.

## Verification and local procedure

Every run reproduces schedules, mixture choices and all 80 ledgers exactly within
the same environment. Independent checks reconstruct wealth, asset P&L and total
weights; all 12 non-cash buy-and-hold/scenario pairs satisfy closed-form price/fee
identities. Tests cover parity with prior fixed rules, future-data perturbation,
weekly timing, state-rule threshold boundaries, source folder/ZIP recovery, corrupted
inputs and a full synthetic workflow in which any attempted ML fit fails.

The wrapper validates the data source before running focused tests. It prints the
resolved source and produces a new immutable `fresh_crypto_long_history_*` directory
and ZIP. Source/specification code must be committed and clean. Existing result files
are never overwritten. PowerShell is inspected statically here; actual Windows
execution is performed by the operator.

From the research checkout, after pulling the research branch:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_fresh_crypto_long_history.ps1
```

Optional explicit source (a directory or ZIP):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_fresh_crypto_long_history.ps1 -SourceRun '.\artifacts\fresh_crypto_ml_20260914_134645_379.zip'
```

Share the printed long-history results ZIP for review. No Core, runtime, paper/live
parameters or capital changes are part of this experiment.
