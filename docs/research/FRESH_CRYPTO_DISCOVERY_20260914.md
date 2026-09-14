# Fresh BTC/ETH discovery — 2026-09-14

The operator asked why the ETF screen struggled against buy-and-hold and explicitly
opened this fresh research exercise to crypto. This extension follows the same
code-on-GitHub, operator-local-run, returned-ZIP workflow. Existing charter performance
targets do not determine this exploratory screen. Core and runtime are outside its scope.
Parameters below were chosen before evaluating crypto market outcomes in this exercise.

## What we learned from the ETF comparison

The uploaded ETF screen earned SPY 11.87% CAGR, 0.610 BIL-excess Sharpe and -47.17%
maximum drawdown. The leading unlevered momentum candidate earned 6.75%, 0.513 and
-23.49%, with realized volatility 12.27% versus SPY's 19.97%. Comparing nominal CAGR
alone confounds exposure and signal quality. However, the weaker Sharpe and the static
macro control's 0.541 Sharpe also show that the current rule has not established a
strong standalone timing advantage. The detailed reviewed evidence remains in
`FRESH_STRATEGY_DISCOVERY_RESULT_20260914.md`.

Buy-and-hold has low turnover, continuous exposure to recoveries, and no exit/reentry
forecast to get right. Cash abstention has an opportunity cost when the asset appreciates.
Reducing drawdown can still be valuable, but it does not automatically improve return per
unit of risk. Our next comparison must separate asset selection, exposure sizing and timing.

Crypto supplies a different hypothesis domain, not evidence that our trading rule will
beat holding crypto. Liu and Tsyvinski's historical work reports crypto momentum:
[Risks and Returns of Cryptocurrency](https://www.nber.org/papers/w24877). This motivates
a falsifiable test; it is neither a current profitability claim nor independent confirmation
of these particular rules. BTC/ETH are chosen as a small, understandable spot universe.
Selecting present-day survivors limits all historical inferences to this conditional universe.

## Frozen exploratory trial list

All lookbacks are calendar days; BTC is the fixed tie breaker. No fitted parameters,
optimizer, learned classifier, or outcome-selected mixture enters this run.

| Family | Rule after each completed daily bar | Mechanism and failure condition |
|---|---|---|
| Trend ensemble | Each coin gets half of the fraction of positive 90/180/365-day price changes | Persistent speculative trends; fails if missed recoveries and whipsaws erase protection after costs |
| Breakout | Half-capital slot per coin; enter above the prior 180-day high, exit below the prior 60-day low | Persistence following a range expansion; fails if delayed entries and false breaks trail the allocation controls |
| Rotation | Hold the higher positive 180-day return of BTC/ETH; otherwise USD | Relative trend persistence; fails if switching adds cost without durable improvement over holding either coin or the mix |

Each family has three exposure profiles: annual forecast-volatility caps of 20%, 40%,
and **no volatility cap**. All profiles remain long-only, at most 100% spot exposure.
This is nine candidates. Volatility uses 60 trailing daily returns, 365 annualization,
and fixed covariance shrinkage of 90% sample covariance plus 10% diagonal. Sizing can
only reduce the raw signal; it cannot fill an abstention slot or add leverage.

Three daily 50/50 BTC/ETH allocation controls use exactly those sizing profiles. Four
benchmarks buy BTC once, buy ETH once, buy a 50/50 mix once (allowing it to drift), or
hold USD. Thus there are **16 policies × four scenarios = 64 ledgers**. Compare each
candidate with its same-profile allocation control and all buy-and-hold benchmarks.
Identical sizing rules do not imply identical realized volatility: both are reported.
This is a crypto-only test; it does not yet measure a mixed SPY/crypto portfolio.

## Local inputs and boundaries

No download occurs by default. The wrapper searches `data` recursively for BTC/ETH
CSV names, excluding USDT pairs and artifacts. Explicit `-BtcCsv` / `-EthCsv` paths
override discovery. Inputs must be USD spot bars with one `timestamp`, `date`, `datetime`
or `time` column and `open,high,low,close,volume` (case insensitive). ISO timestamps,
epoch seconds and epoch milliseconds are supported. **Labels must represent bar starts
in UTC**; naive labels are assumed UTC, never the Windows local time zone. USD quotation
and source identity require operator verification; filenames cannot prove them.

Hourly, four-hour and daily bars are accepted. Intraday OHLCV aggregates only complete
UTC days. Missing interior bars, duplicates, invalid prices, mixed spacing and off-grid
labels fail. A partial first day may be removed; the complete 2024-12-31 day is required.
Different eligible files are not automatically ranked by length or returns: supply explicit
paths when there is ambiguity. Equivalent normalized daily files can be deduplicated.

The loader restricts history to 2017-01-01 through 2024-12-31. For a file extending later,
it inspects timestamps to exclude future rows before inspecting price/volume values.
It requires 365 warmup days plus at least three years of evaluation. The later of the two
available initial dates sets the common start, determined by coverage rather than results.
All policies then share the same evaluation dates; trimming is recorded. A full 2017
start gives initial execution on 2018-01-03. A later local history gives a later test.
2025+ prices are neither requested nor evaluated, and are absent from normalized ZIP
inputs. This reserves them within this exercise, without asserting they are unseen elsewhere.

If requested with `-DownloadMissing`, only a missing eligible BTC-USD or ETH-USD input
is downloaded from Coinbase Exchange. It requests pre-2025 daily candles in batches of
at most 290, checks conflicting overlap and complete coverage, and refuses to overwrite
an existing cache. The [official candle schema](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
defines bucket-start timestamps and the 300-candle request limit. This source is spot;
it is not CDE or a perpetual/funding series. No ETF data is downloaded by this extension.

## Accounting and executable timing assumptions

Bar t spans midnight t through midnight t+1. Its close is available at t+1; a decision
using it executes at the open of t+2, allowing a full day's latency. Delay stress executes
at t+3. Breakout state warms before evaluation and excludes the current bar from the
entry/exit extrema. All orders that would collide with final liquidation are suppressed.
The common final exit is the 2024-12-31 open, before any 2025 valuation.

Full initial equity includes zero-yield USD cash. Inventory carries forward between
orders. Fees are paid on absolute traded notional, with post-fee weights solved by the
existing independent rebalance primitive; all daily P&L and NAV changes reconcile.
Daily close marks include overnight/open gaps; final liquidation has no subsequent
intraday exposure. No leverage, shorting, lending, staking or perpetual funding is modeled.

| Scenario | One-way total execution assumption | Delay after signal availability |
|---|---:|---:|
| Frictionless diagnostic | 0 bps | 24 hours |
| Base | 30 bps | 24 hours |
| Cost stress | 75 bps | 24 hours |
| Delay stress | 30 bps | 48 hours |

Fees include entry and terminal liquidation for benchmarks too. These are explicit
research assumptions, not verified Coinbase fee tiers or capacity estimates. Confirm an
actual all-in execution cost before interpretation. Daily candle opens are fill proxies;
the experiment does not establish executable size, venue access, custody, tax treatment
or intraday drawdown. USD yield is zero for everyone, so the Sharpe is excess over zero
cash. Do not compare it directly with a different-period ETF Sharpe excess over BIL.

## Outputs and interpretation

The ZIP contains normalized pre-2025 BTC/ETH inputs, their source hashes and manifests,
committed-code hashes and versions, the complete trial registry, target weights with
availability/fill timestamps, all daily ledgers, annual returns, early/late summaries,
matched-control differences and correlations. The base README displays every policy.
CAGR uses elapsed calendar time; volatility and arithmetic cash-excess Sharpe use 365.
Drawdown includes initial capital and uses daily marks; the terminal fee is included.
Era rows rebase their own return sequence; annual returns may have a partial first year.
The CAGR/Sharpe/drawdown Pareto flags are descriptive, not a selection or significance test.

Every portfolio is computed twice and must replay byte-for-byte before results finish.
An invalid-leverage canary must fail on every run. Source files remain untouched; normalized
copies and hashes are enough to replay without sharing future prices. The code/spec must
be committed before a market run. A data failure produces a diagnostic ZIP rather than
quietly shrinking a sample, filling prices or returning a misleading performance table.

The useful finding would be a coherent family-level improvement over controls that
survives costs, delayed fills and early/late periods. An isolated top Sharpe is insufficient.
Three to seven years contain few independent crypto cycles despite thousands of bars;
the study is unlikely to resolve small Sharpe differences reliably. No significance,
power claim, Monte Carlo conclusion or promotion follows from this descriptive screen.
Review the ZIP, then freeze any shortlisted configuration and its confirmation design.
Block resampling and OOS can assess fragility later; neither manufactures new edge.

## Run on Windows

From the repository root, after fetching this branch:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_fresh_crypto_discovery.ps1
```

To search another existing local data directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_fresh_crypto_discovery.ps1 -DataRoot 'D:\MarketData'
```

For explicit file selection (replace the example paths and source label):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_fresh_crypto_discovery.ps1 -BtcCsv 'D:\MarketData\BTC-USD.csv' -EthCsv 'D:\MarketData\ETH-USD.csv' -SourceLabel 'Coinbase UTC spot bar starts'
```

Only if downloads are wanted, append `-DownloadMissing`. Share the printed results ZIP
or the data-check ZIP if local coverage/schema needs attention. No API credentials needed.

## Engineering verification

Synthetic tests cover independent buy-and-hold fee identities, fixed mixed-asset units,
weekends, UTC availability/fill separation, planted trend and breakout response, future
perturbations, missing/invalid data rejection, complete intraday aggregation, local reuse,
ambiguous inputs, 365-day metrics, exposure caps, and all 64-ledger deterministic replay.
Synthetic performance is mechanics evidence only. The PowerShell wrapper is reviewed
statically here; the operator's machine supplies the actual Windows execution.
