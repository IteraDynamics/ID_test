# Fresh strategy lab — 14 September 2026

Status: implemented for local execution; no market results yet.

The operator explicitly authorized a new exploratory strategy branch, code commits
to GitHub, and local PowerShell execution followed by result review. For this
exercise the previous charter's performance goals and research approval sequence
do not determine the search. Research integrity and correct accounting still do.
This is separate from Core v1, its paper record, and existing campaign decisions.

Base: research/economic-opportunity-review-20260911 at
8869dfcc85f9fdf0b82ee308e813a3b176dd3f0c. That base preserves the recent refactor and
research history, including the rejected quote-based condor configuration.
Branch: research/fresh-strategy-lab-20260914.

## Decision and scope

Find a useful net return / Sharpe / drawdown frontier worth deeper investigation.
There is no inherited 10% volatility ceiling, allocation cap, minimum CAGR, or
mandatory significance hurdle. This first batch compares explicit 1x and 2x gross
budgets; they are experimental settings, not approved live exposure. Subsequent
research can revise the search openly based on what we learn.

"Adjusted annual return" has no unique definition. Report CAGR and annual mean
separately, plus annual certainty-equivalent return with gamma 3:
252 * mean(daily net returns) - 1.5 * 252 * sample_variance(daily net returns).
Gamma 3 is a disclosed descriptive convention, not the operator's utility function.
Also report ordinary and HAC Sharpe, volatility, Calmar, Sortino, worst day,
expected shortfall, time under water, turnover, costs, and actual gross exposure.
All returns are on total account equity including unused cash. No margin-only,
premium-on-collateral, or return-per-active-day annualization.

## Fixed first search

| Family | Economic hypothesis | Implementation | Variants |
|---|---|---|---:|
| Index shock bounce | Temporary selling pressure can overshoot; subsequent liquidity provision may earn a premium | SPY/QQQ/IWM; a daily loss beyond 1.5 or 2 times prior 20-session volatility; next-open entry; hold 1/3/5 sessions; with/without a 200-session total-return trend filter | 12 |
| Sector residual reversal | Short-lived sector-specific pressure may reverse after removing common market movement | Nine original sector ETFs; prior-estimated 60-session beta removes each day's SPY return; rank cumulative residuals over 3/5/10 sessions; long bottom three, short top three; rebalance every 1/3 sessions | 6 |
| Session balance | Daytime and overnight price formation may contain different forecasting information | SPY/QQQ/IWM; positive trailing mean log(day return) minus log(overnight total return) selects long/cash; 21/63/126 sessions; full-session or overnight execution | 6 |
| Fixed equal blend | Different trading patterns may improve portfolio outcomes together | One third each shock z1.5/hold3/unfiltered, sector residual lookback5/rebalance3, and session balance63/full | 1 |

The sector family has equal long/short dollars, NOT guaranteed beta neutrality.
Removing market returns from the ranking signal does not neutralize portfolio beta.
The full registry, signal hashes and every result are exported. No fitted ML models.
This batch has 25 research candidates including the fixed blend, plus six controls:
cash, SPY buy/hold, equal-weight indices, index SMA200/cash, unconditional index
overnight, and unconditional index daytime. With two gross budgets and five
scenarios this is 310 ledgers, not 310 independent hypotheses. The cash control
appears twice for a rectangular comparison. There are no fitted blend weights.

Signals have a unit gross budget. A shock allocates one third per triggered index;
unused slots remain cash, rather than concentrating all equity in one event.
Repeated shock triggers do not extend an existing holding; a new trigger can open
a new tranche after expiry. The three-session sector schedule is anchored to the
first source session, independent of future performance. Ties use fixed ticker order.
The ensemble nets opposing positions before trading; standalone and ensemble
costs can therefore differ.

These are fresh implementations for this exercise, not claims of academic novelty.
Daily ETF patterns may fail after realistic fills, remain mostly equity beta,
or have insufficient magnitude for the operator's objective. The benchmark and
stress comparisons are designed to show that promptly.

## Sources and interpretation

- Stefan Nagel, [Evaporating Liquidity](https://www.nber.org/papers/w17653):
  the publicly indexed abstract motivates reversal as possible liquidity-provider
  compensation. It does not establish profitable ETF execution here.
- Lou, Polk and Skouras,
  [The Day Destroys the Night, Night Extends the Day](https://personal.lse.ac.uk/loud/LouPolkSkouras.pdf):
  the inspected PDF identifies itself as July 2024; abstract and introduction
  motivate separating daytime and overnight market information. Our zero-threshold,
  daily ETF rule is a deliberately small adaptation, not a paper replication.
  The author's research page lists a later revision; this implementation makes no
  claim about reproducing that later specification.
- [yfinance source](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py):
  inspected the history signature and inclusive-start/exclusive-end semantics.
  The actual installed versions are recorded per local run.

## Data and information boundary

Twelve fixed ETFs: SPY, QQQ, IWM, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY.
The original nine sector funds give a long common history. This is a deliberately
selected surviving ETF universe, not an unbiased security-selection universe.
Sector definitions and holdings changed historically; ETF returns reflect those
changes, but generalization to today's sector structure needs review.

The downloader requests 2004-01-01 through exclusive 2024-01-01 only. Scoring starts
in 2006; 2004-2005 supply warmup. Current vendor snapshots are saved with hashes,
versions, flags, full OHLC, adjusted close, volume, distributions and split events.
Replays require matching hashes. No files belonging to earlier campaigns are read.
No forward-fill, zero-return substitution, or silent calendar intersection.

Yahoo OHLC are treated as split-adjusted, dividend-unadjusted prices. Holdings use
the corresponding split-adjusted share units, so split events are not applied
again. Dividends are credited to overnight holders on ex-date; shorts pay them.
The loader checks daily close-plus-dividend returns against adjusted-close returns,
refusing discrepancies above 20 bps. This is a source-convention canary, not proof
of data correctness. Daily distributions are assumed available by that day's close
for signal construction; the simulator credits holders mechanically. Payment-date
lag, tax and withholding are not modeled. Adj Close is used only for the audit,
not as a fill price.

Current vendor history can contain revisions. Calendar equality to SPY and long-gap
checks are enforced, but an independently sourced exchange calendar is not present.
The raw snapshots require source review before an economic conclusion is promoted.
Daily opens/closes are trade-price proxies, not historical bid/ask or guaranteed
auction fills. No price repair or alternate source is silently substituted.

At close of day t-1, compute signals and precommit share quantities using that
close's equity and prices. Full/day strategies fill at day t open; night strategies
fill at day t close. Neither uses completed day t information to decide that fill.
The one-session delay scenario uses day t-2's signal, sized from day t-1 equity.
Night orders deliberately retain the whole prior-session information gap.
Terminal liquidation is preplanned at the final 2023 close and charged.

Because quantity is fixed before the fill, an opening/closing gap can move actual
gross exposure beyond the planned 1x/2x budget. Actual maximum and average gross
at both marks are reported. The engine does not retroactively resize using the
realized fill price. Day orders exit at the close; night orders exit at the next
open; full-session positions carry until their next open rebalance. SPY buy/hold
keeps its initial shares until terminal liquidation.

Drawdowns are checked at both open and close, including initial losses and
transaction costs. Daily high/low path ordering is unknown, so intraday extremal
drawdown, gap-dependent margin calls, rejects, and borrow recalls are not modeled.
An insolvent ledger is explicitly failed; partial performance is not reported as
a valid candidate.

## Costs and performance search

| Scenario | Trading cost per dollar bought or sold | Annual financing | Annual short borrow | Extra signal delay |
|---|---:|---:|---:|---:|
| Zero trading costs | 0 bps | 6% | 3% | 0 |
| Base | 2 bps | 6% | 3% | 0 |
| Stress | 10 bps | 8% | 6% | 0 |
| Severe stress | 25 bps | 10% | 10% | 0 |
| Delay | 2 bps | 6% | 3% | 1 session |

These are assumptions, not broker quotes. Trading cost combines commission,
spread and slippage in one rate; there is no second spread charge. Financing uses
free-cash deficit after segregating short proceeds, so short proceeds do not
silently finance extra longs. Borrow uses marked short notional. Charges accrue
over calendar time including weekends, partitioned into overnight and 6.5-hour
daytime intervals. Intraday borrowing is charged conservatively as well.

Cash earns 0% in this first controlled comparison; excess Sharpe therefore uses
zero as its risk-free reference. This deliberately omits possible cash income,
and comparisons with external Sharpe figures using Treasury returns need adjustment.
No tax, fixed minimum commission, impact/capacity model, or broker margin schedule.
Normalized initial NAV is 1; share fractions are used. No capital amount is inferred.

Annualization uses 252 scored sessions per year. Maximum drawdown is reported as a
positive loss magnitude; Calmar is CAGR divided by that magnitude. HAC Sharpe uses
20 Bartlett lags to expose serial-dependence sensitivity. It is not a p-value,
deflated Sharpe, or correction for this search. Top-five-day removal is a clearly
labeled diagnostic with the affected returns set to zero, not a tradable path.

The Pareto flag compares CAGR, HAC Sharpe and maximum drawdown within the same
gross budget and cost scenario, including benchmarks. Family medians and ranges
show whether an apparent winner is a lonely parameter cell. All candidates are
scored; no best-per-year splice or parameter fitting is disguised as OOS.

## Run and review

From the new branch's repository root:

~~~powershell
.\scripts\local\run_fresh_strategy_lab.ps1
~~~

The wrapper runs the focused synthetic tests first, uses the existing locked
Python 3.12 environment, then acquires the twelve public ETF histories and runs
the batch. It creates a timestamped artifacts folder and adjacent ZIP.

For an exact re-run after a successful download, retaining the existing source:

~~~powershell
.\scripts\local\run_fresh_strategy_lab.ps1 -ReuseData
~~~

The default data folder is data/fresh_strategy_lab_20260914. Existing inputs and
outputs are never overwritten. An interrupted download has no completed manifest;
use a different -DataRoot for a new acquisition, or inspect the error first.
A vendor/network/schema failure stops the run and must be reviewed.

The review ZIP contains the report, source audit, prior search identity, all summary
and yearly metrics, complete daily return matrix, correlation table, and ledgers.zip.
Each ledger includes cash, inventory value, dividends, per-asset dollar P&L, trading
costs, financing/borrow, exposure, signal dates and reconciliation error. Data CSVs
stay in the snapshot folder and can be shared separately if source inspection is needed.
Base-scenario ledgers are recomputed twice and compared byte-for-byte.

Current verification status: Python and PowerShell were not executed in the offline
authoring workspace. Synthetic tests are included for local/CI execution. There are
no observed market returns in this document. Refer to GitHub CI and the operator's
local test output for actual execution status.

## Next research decision

Review the actual frontier, benchmarks, neighboring configurations, costs, delay,
year concentration, factor exposure and per-asset contributions. Prefer a family
with economically useful results across nearby definitions over an isolated maximum.
No universal Sharpe/CAGR threshold is invented here; judge the measured tradeoff
against the operator's stated objective.

Then select and freeze a small shortlist before opening additional evaluation data.
2024 onward is excluded from this batch but is NOT automatically pristine OOS:
some years were used in previous Itera research. Audit the prior-use record first.
A previously inspected period may still be a useful retrospective robustness
check, but genuine fresh confirmation may require prospective observations.

Monte Carlo follows candidate review: resample contiguous calendar blocks jointly
across selected strategies, stress costs/gaps and compare parameter neighborhoods.
It estimates path sensitivity conditional on the supplied history; it does not
manufacture new regimes or erase search bias. No OOS or Monte Carlo is run in
phase one, and no production behavior is changed.
