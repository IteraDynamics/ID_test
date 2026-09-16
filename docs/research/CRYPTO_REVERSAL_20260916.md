# Crypto selloff stabilization experiment — design frozen before results

Date: 2026-09-16. Exploratory research; Core and analyst pilot unchanged.
The earnings-event/vendor project is parked. No acquisition or network request is
part of this experiment. Existing research has examined these assets and years;
none of 2018–2025 is called an untouched OOS sample. This is a specific execution
and stabilization hypothesis, not a claim of a novel price-information family.

## Fixed hypothesis and competing explanation

Temporary selling pressure can overshoot; a subsequent bar holding the selloff
low and recovering may distinguish a rebound from continuing deterioration. OHLCV
cannot establish liquidations or forced selling as the cause. The competing
explanations are generic crypto beta, ordinary dip buying, or the benefit of merely
waiting. Test all of those before claiming value from stabilization.

Primary candidate: 4h shock, one 4h stabilization bar, 24h holding period.
Secondary timeframe: 1h. Holding sensitivities: 6h and 48h. Six candidates total;
all are reported, with no best-parameter selection. For each, two ablations buy
immediately after a shock or wait one signal bar without requiring stabilization.
Do not expand this grid in response to performance.

## Exact signal and time semantics

Source timestamps are UTC candle STARTS. Use complete UTC-aligned 1h or 4h bars.
Four-hour bars require all four observed hourly constituents. No fabricated bars.
Let r[t] = log(close[t]/close[t-1]). Define sigma[t] as sample standard deviation
of returns r[t-N] through r[t-1], N=168/timeframe_hours (one week). Require every
bar/return in this history to be present and sigma>0. A shock is r[t] <= -2.5*sigma[t]
and close[t] < open[t]. Neither current nor future return enters its own threshold.

Stabilization requires the immediately following complete signal bar t+1:
low[t+1] >= low[t], close[t+1] > close[t], and close[t+1] > open[t+1]. No search
for a later recovery bar. A qualifying entry uses the hourly open ONE FULL HOUR
after the determining bar has completed. Example: a 00:00–04:00 shock followed by
04:00–08:00 stabilization enters at 09:00 UTC. Delay stress enters at 10:00 UTC.
The immediate and unfiltered-wait controls have the same one-hour processing lag.
Exit at the hourly open H hours after actual entry. No stops, target, leverage,
shorts, funding exposure or ML. Signals during an open position are discarded;
no pyramiding. Do not re-enter at the same open at which a position exits.

## Capital, execution and missingness

Start each BTC and ETH standalone sleeve with 1 unit of cash. Each trade invests
that sleeve fully including entry costs. The combined portfolio allocates half
of initial capital to each sleeve, with no subsequent inter-sleeve rebalancing.
This reports the capital denominator honestly even while one sleeve sits in cash.
Cash earns zero; Sharpe is relative to this cash assumption, not Treasury excess.

Costs are deterministic all-in one-way notional charges: frictionless 0bp,
base 30bp, stress 75bp. Delay stress uses base costs and 2h processing lag.
These are assumptions, not a claim about a user's fee tier or order size. Entry
quantity = cash / [open*(1+cost)]; exit proceeds = quantity*open*(1-cost).
The first historical trade in an hourly candle is a fill proxy, not evidence of
available depth or capacity. No capacity claim is made.

Known gaps: BTC 36 missing hourly timestamps in 14 gaps; ETH 19 in 10 gaps.
Signals requiring missing bars are unavailable. Missing entry opens cancel the
entry; missing planned exit opens defer liquidation to the first observed hourly
open. Positions are never removed because future data are missing. For valuation
only, carry the last observed close across a gap and count stale held marks. This
can understate drawdown during gaps and does not establish executable prices there.
Forbid new entries whose planned exit lies beyond the predetermined sample end;
force terminal liquidation at that end if a position remains. Both end opens must
exist. Include deferred exits and stale marks in output. Do not retune from these.

## Sample, controls and outputs

Evaluate 2020-01-01T00:00Z through liquidation at 2025-12-31T00:00Z. This boundary
uses the common supplied endpoint and excludes the final candle's later close.
Earlier history is used only for warmup. Report full period, 2020–2022, 2023–end,
and every calendar year as retrospective breakdowns of ONE continuous portfolio.
Positions carry across year/subperiod boundaries; these are not separate OOS runs.

Benchmarks: standalone BTC/ETH buy-and-hold, initial equal-weight buy-and-hold,
zero-return cash, and a descriptive exposure-matched buy-and-hold curve for each
candidate. The latter uses that candidate's realized full-sample mean exposure:
it is explicitly hindsight-normalized, not a deployable strategy or alpha test.
Report immediate-dip and unfiltered-wait ablations alongside every candidate.

Report CAGR, daily zero-cash Sharpe (365 periods/year), daily annualized volatility,
hourly-close max drawdown including initial capital, Calmar, average exposure,
turnover, trade count, fees, holding extensions and capital growth. Export daily
curves, all trade ledgers, yearly/subperiod summaries, gross geometric break-even
one-way cost per completed-trade sequence, fixed design/config, input/code hashes,
missing-data inventory and accounting/replay checks. Break-even cost ignores
cash yield and order-size-dependent impact; it is diagnostic, not a fee quote.

Results qualify for further research only if net economic value is meaningful,
not concentrated in a few trades or one asset/period, and stabilization adds value
against the ablations rather than merely reducing exposure. Show top-five-trade
profit concentration and return with those trades' multipliers removed as a
hindsight fragility diagnostic. No universal invented promotion threshold: inspect
all evidence, do not declare paper readiness from a leaderboard. This run does not
measure correlation or marginal contribution to Core without its aligned ledger.

## Data identity and provenance

Exact supplied snapshots (other files are rejected, never silently substituted):
- BTC SHA256 d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079
- ETH SHA256 73721a1ef1dffbff64bf6ef2d92fb508a59b20d5c847684d96fdc7015912845f

Repository source: scripts/fetch_coinbase_hourly_history.py and
CAMPAIGN_52_SOURCE_CALENDAR_PREFLIGHT_EVIDENCE.md. Coinbase's
[candle specification](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
defines bucket-start timestamps, first/last trade open/close and possible missing
intervals. The input hashes must match before relying on this established lineage.
No claim that all possible data errors are excluded by structural tests.

## Run locally

From the research checkout:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_crypto_reversal.ps1 -DataRoot 'C:\Dev\IteraDynamics\ID_test\data'
```

The script tests the experiment and then runs all frozen scenarios. It does not
fetch market data. By default it selects the two exact hourly filenames above
from DataRoot, rather than scanning the directory for alternative files. Optional
`-BtcCsv` / `-EthCsv` accept explicit paths to the same frozen snapshots; the hashes
must still match. `-CheckOnly` verifies inputs without signals or performance.
Relative arguments are resolved before changing the shell's working directory.

Upload the printed `artifacts\crypto_reversal_<UTC timestamp>.zip`. The ZIP includes
RESULTS.txt, summary.csv (all assets/periods), diagnostics.csv (full-run trade and
accounting diagnostics), trades.csv, fills.csv, signal_counts.csv, daily curves,
configuration/code hashes, source-gap inventory, status and artifact hashes.
Raw input price files are not copied into the ZIP. Failures also produce a ZIP
with the traceback, rather than silently falling back to a different dataset.

Interpretation notes: turnover is traded notional divided by prior hourly marked
NAV, summed and annualized; fees are in units of initial capital. Combined turnover
uses the same portfolio denominator. Maximum drawdown is calculated on hourly
marks, not the exported daily-only curves. Top-five positive dollar-P&L share and
terminal wealth with the five largest positive percentage-return trades removed
are distinct hindsight fragility measures. A negative gross trade sequence has no
nonnegative geometric break-even cost, reported blank rather than as a positive
cost allowance. That formula is reported only for single-asset sleeves, not for
a combination of independently compounding sleeves.
