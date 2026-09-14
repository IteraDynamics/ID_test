# Fresh strategy discovery — September 14, 2026

## Decision and authorization

The operator requested a fresh exploratory strategy exercise, explicitly setting aside
existing charter performance targets and research gates. This branch starts at
`8869dfcc85f9fdf0b82ee308e813a3b176dd3f0c` on
`research/economic-opportunity-review-20260911`. Its purpose is to identify worthwhile
net return / Sharpe / drawdown trade-offs before freezing anything for OOS and Monte Carlo.
No prior fitted model, result-dependent parameter, prior screening verdict, Core strategy
or execution engine is an input. The campaign board was read for the project handoff.

This is a new research implementation, not a claim that momentum or reversal is novel.
It changes no Core v1/v2 behavior, runtime, orders, paper accounts, or capital allocation.
The code does not place trades. The user will run market-data acquisition and the screen
on Windows, share the generated ZIP, and review actual findings before the next stage.

## Three hypotheses and discriminating controls

| Family | Economic hypothesis and exact rule | Main alternative / falsification |
|---|---|---|
| Cross-asset dual momentum | Slow adjustment and persistent capital flows may reward medium-term winners. At the first observed session of each month, rank 10 ETFs by 63/126/252-session total return minus BIL over the same horizon. Buy the best three with positive excess momentum, inverse-volatility weighted. Fewer than three qualifying assets reduces risky allocation in proportion to occupied slots. | Exposure to equities/rates explains performance; compare to the same universe's static inverse-volatility allocation and SPY. Failure across neighboring horizons or only one asset/era weakens the mechanism. |
| Sector residual reversal | Temporary sector selling/buying pressure may reverse after market moves are removed. Estimate each of nine sectors' SPY beta from the last 63 daily returns. Rank sums of 3/5/10-session residual returns divided by trailing volatility and square-root horizon. Long the lowest three, short the highest three, add a SPY beta hedge, normalize to gross one, refresh weekly. | Sector moves reflect persistent information or the effect decays before execution. Compare with raw sector reversal without residualization/hedging, charge both sides' turnover/borrow, and delay execution one additional session. This is an ETF adaptation of a stock-liquidity hypothesis, not a replication of published stock returns. |
| Trend-conditioned pullback | Short-lived selling inside an established uptrend may offer better entry timing. For five equity ETFs above their 200-session mean, allocate one fifth of capital times `clip(-z,0,2)/2`, where z is the 3/5/10-session total return divided by trailing annual volatility times `sqrt(window/252)`. Refresh daily. | Cash timing or plain equity beta explains the result; compare against the exact same five-asset trend-only rule. Failure after costs/delay or no advantage to the trend-only control weakens the timing hypothesis. |

No rule has a fitted directional model. No threshold/window was selected using results
from this screen. Portfolio weights from the three central variants (126/5/5) also form
a fixed equal-capital blend, refreshing all three signals weekly. That blend is an
explicit separate strategy; it does not splice the historically best sleeve.

Universe: macro `SPY QQQ IWM EFA EEM IEF TLT GLD DBC VNQ`; sectors
`XLB XLE XLF XLI XLK XLP XLU XLV XLY`; pullbacks `SPY QQQ IWM EFA EEM`;
cash instrument `BIL`. The nine longstanding sector funds deliberately omit newer
XLRE/XLC. Sector definitions and fund holdings have changed historically. The present-day
choice of these funds is a research selection, not a survivorship-free all-ETF universe.
No current stock-constituent list is applied to historical prices.

## Search budget and portfolio construction

Three families × three windows × two exposure ceilings = **18** individual candidates;
two fixed blends = **20** candidates. Three matched controls at both ceilings, plus
SPY and BIL buy-and-hold, make **28 policies**. Four execution scenarios produce
**112 ledgers**, all retained. The scenario count is not a count of independent trials.
All policy identities and parameters are saved before evaluation.

Ceilings are gross risky target exposure of 1.0 and 1.5 times equity. These are research
scenarios, not authorized broker leverage or live limits. A fixed 15% annualized risky
volatility ceiling reduces exposure using 63 daily returns, with 90% sample covariance
plus 10% of its diagonal. The raw signal is multiplied by at most the gross ceiling;
abstention is not normalized back to full investment. The volatility ceiling is a
forecast, not a guarantee; weights and risk can drift between rebalances. The output
reports actual average and maximum gross exposure. Buy-and-hold controls are unscaled.

Cash allocated to BIL is `max(0, 1 - sum(positive risky weights))`. Restricted short
proceeds remain non-interest-bearing settlement cash, not extra investment capital.
An equal blend nets common positions before execution costs; no benefit from knowing
future sleeve correlations is assumed. Blends use the same covariance ceiling.

## Data and temporal boundary

- Download request: daily history from **2007-06-01**, with exclusive end **2025-01-01**.
- Score from the first session on/after **2008-07-01** through the final open on
  **2024-12-31**. The 2008 result is partial; at least 252 sessions warm every feature.
- Default acquisition never requests 2025+. Loaded inputs containing 2025+ are rejected.
  This does not assert that 2025 is globally untouched across every prior investigation;
  its eligibility must be checked when a later OOS design is actually proposed.
- Raw Yahoo/yfinance OHLC, adjusted close, volume and actions are saved per asset.
  `auto_adjust=False`, `back_adjust=False`, `repair=False`, `keepna=True` are explicit.
  OHLC is then multiplied by `Adj Close / Close`. This is an adjusted-unit total-return
  approximation; distributions are not credited a second time. It is not a literal
  share/settlement ledger or point-in-time vendor archive. Historical revisions remain
  possible; raw file hashes pin the downloaded version for replay.
- No silent forward filling, price repair, dropping incomplete dates, proxy substitution,
  missing-ticker substitution or calendar intersection is permitted. All assets must
  match SPY's session calendar and source range. Invalid OHLC, dates, volume or hashes fail.
  SPY is the calendar reference, not an independently verified exchange calendar.
- Features through close t can first execute at open t+1; the delay case uses open t+2.
  No entry gap before the fill is earned. First-of-month/week decision dates use only
  the current and previous session label. All scenarios share valuation start and exit;
  a delayed policy waits in zero-yield settlement cash before its first fill.
- Signal construction is deterministic and causal. No training/validation labels, hidden
  target normalization, full-sample volatility scaling or ex-post sleeve choice enter weights.

All of 2008–2024 is **development history**. The early/late-era split is descriptive
robustness, not independent OOS. Prior exposure to this history cannot be undone by a
new branch. This stage does not run OOS, bootstrap significance tests, or Monte Carlo.

## Executable accounting and cost assumptions

The return denominator is full starting equity, normalized to one, including cash and
collateral. Daily equity is cash plus marked adjusted-unit inventory. Each rebalance
solves post-fee equity so desired weights, inventory, cash and charged turnover reconcile.
The final session liquidates at its open, charges exit costs, and earns no later price move.

| Scenario | One-way spread/fee/slippage budget | Annual short borrow | Annual long-debit financing | Fill |
|---|---:|---:|---|---|
| frictionless | 0 bps | 0% | 0% | next open |
| base | 5 bps | 1% | lagged BIL yield proxy + 1.5% | next open |
| cost_stress | 15 bps | 3% | lagged BIL yield proxy + 3% | next open |
| delay_one_session | 5 bps | 1% | lagged BIL yield proxy + 1.5% | one extra session |

Costs apply to absolute traded notional, including BIL and the hedge. A round trip pays
both directions. The budget aggregates execution costs rather than double-counting fees
and spreads. These values are explicit scenario assumptions, not verified broker quotes.
There is no capacity claim, price impact fit, borrow-availability history, locate/recall
model, broker maintenance-margin model, auction-access proof, or tax model.

Short borrow accrues on prior-close short market value for actual calendar days / 365,
including weekends. Financing accrues on `max(total long market value - prior NAV, 0)`;
short proceeds cannot offset it and earn no rebate. The base financing rate is the
nonnegative trailing 21-session BIL return annualized by its actual calendar span, known
at the previous close. It is an approximation, not the historical broker debit schedule.
BIL is a traded ETF, so residual invested capital bears its observed price changes/costs.

The ledger independently reconciles overnight P&L, post-trade intraday P&L, fees, borrow,
financing and change in equity. Insolvency aborts the run with an error; it is never
silently removed from a leaderboard. Reaching a simulated target is not proof of broker
margin feasibility. No order API, live feed, credentials or execution account is used.

## What to review

Net **CAGR**, annualized arithmetic return, **excess Sharpe relative to frictionless BIL**,
**Calmar**, maximum drawdown, longest time below the previous high, worst day, 5% expected
shortfall, turnover, actual exposure, SPY beta, and descriptive annual alpha are reported.
CAGR uses elapsed calendar days / 365.25; means, variances and Sharpe use 252 sessions/year.
Sharpe's square-root convention is descriptive; no iid significance claim is made.
Calmar is CAGR / absolute maximum drawdown, including initial trading costs in the high-water
mark. Undefined ratios remain missing. Buy-and-hold BIL is a comparator, not an exact
institutional risk-free rate. Reported CE uses gamma=3: `252*(mean(r)-1.5*var(r))`;
it is one explicit risk-preference diagnostic, not the operator's assumed utility.

"Adjusted annual return" has no unique definition. Here it is made reviewable through
net CAGR, separately disclosed annual cost drags, excess Sharpe and CE; no custom opaque
score substitutes for these. Pareto flags identify policies not dominated simultaneously
on CAGR, excess Sharpe and drawdown. They do not declare a winner or a significance result.

Inspect full and early/late-era metrics, every year's return, year-deletion diagnostics,
cost/delay sensitivity, gross/net exposure, asset contribution/concentration, and return
correlations. Year deletion concatenates remaining daily observations only for descriptive
geometric return and Sharpe; it is not an executable path. Asset contribution is a sum
of daily arithmetic contributions, not compounded wealth attribution. The chart displays
the top five candidate Sharpe results using the full base sample, explicitly a selected view.

No historical Sharpe/CAGR threshold from previous campaigns is imported. A worthwhile
shortlist should present an economically useful trade-off against matched controls,
survive plausible costs/delay, and not depend on one isolated window, year or asset.
The final continuation judgment is made after seeing actual economics, not an arbitrary
power gate or a retrospective change to the primary metric.

## Reproduce and share

From a clean checkout of this branch on Windows:

```powershell
Set-Location C:\Dev\IteraDynamics\ID_test
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local\run_fresh_strategy_discovery.ps1
```

The wrapper uses the existing locked Python 3.12 environment, runs focused synthetic
correctness tests, downloads/resumes the 20-source snapshot, and writes a timestamped
results directory and ZIP under `artifacts`. It prints `SHARE THIS FILE` with the ZIP path.
The ZIP includes the exact inputs, manifests, all metrics, daily ledgers, target weights,
plot and specification; it excludes unrelated local files and account credentials.
Do not manually edit cached data. A provider correction needs a new data-root snapshot.

An exact offline replay with the same cache:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local\run_fresh_strategy_discovery.ps1 -Offline
```

The report records code/spec/data hashes, git commit and actual package versions. Modified
research code/spec must be committed before a real run. Synthetic integration tests replay
all 112 ledgers and compare CSV bytes/reports. Acquisition is resumable per verified symbol;
provider failures stop and leave completed downloads intact. No paid source is required.

## Next stage, conditional on a worthwhile screen

1. Review the returned ZIP and independently reconcile a proposed candidate against controls.
   Record all 20 candidates, negative outcomes and consequential exploratory redesigns.
2. Freeze one candidate or a small justified shortlist, execution assumptions, OOS dates,
   comparison and decision criteria. Check whether the proposed holdout is actually unused;
   use prospective evidence if it is not. Reusing an inspected holdout makes it development.
3. Run chronological OOS once under that frozen design. Monte Carlo then uses joint blocks
   of the selected portfolio/control returns, preserving cross-asset dependence and examining
   several defensible block lengths, plus explicit cost and tail scenarios. Resampling the
   winner alone cannot correct the research search or create previously unseen crises.
4. Make a research decision. Any paper/live integration remains a separate authorized task.

## Source basis and evidence status

- Moskowitz, Ooi and Pedersen (2012), [Time Series Momentum](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum):
  the authors' research summary supports the broad medium-term persistence hypothesis.
  The ETF top-three/cash rule here is an original implementation choice, not their tested portfolio.
- Nagel (2012), [Evaporating Liquidity](https://www.nber.org/papers/w17653): original working-paper
  bibliographic record identified through search; full text was not retrieved in this session.
  Liquidity provision motivates a reversal hypothesis; no published ETF performance is asserted.
- [yfinance source](https://github.com/ranaroussi/yfinance): the installed locked version's
  `PriceHistory.history` signature was directly inspected for all supplied arguments.

At implementation time no market backtest in this new suite has been run. Synthetic
mechanics results are engineering evidence only. Actual local test results are recorded
in the final implementation entry below, after execution.

## Implementation verification — September 14, 2026

- `uv run --locked --python 3.12 --extra dev python -m pytest tests/test_fresh_strategy_discovery.py -q -W error`:
  **25 tests passed**. Tests include independent algebraic buy/sell cost calculations,
  next-open/delayed execution, terminal gap and liquidation, financing and short collateral,
  distribution adjustment without double counting, future-price perturbation invariance,
  planted momentum/pullback recovery, beta hedge identity, abstention/target limits,
  source corruption and missing-session rejection, metrics and byte-identical screen replay.
- Full-length **synthetic-only** integration: 20 source files → validated snapshot → all
  112 ledgers → 336 period summaries → chart → integrity-tested ZIP. **482,272** daily rows;
  maximum accounting residual **7.525e-16** in prior-NAV units. About 91 seconds in the
  execution environment; this is not a Windows runtime guarantee. Synthetic economics
  are not market evidence and are not committed as findings.
- ZIP contents were checked to exclude an unrelated CSV deliberately placed in the input
  directory. Only the 20 named source pairs and snapshot manifest are included.
- Actual environment: Python **3.12.14**, NumPy **2.4.4**, pandas **3.0.2**, pytest **9.0.3**,
  yfinance **1.5.2**. Compilation, CLI help and git whitespace checks passed.
- PowerShell is not installed in this Linux environment; the wrapper is statically
  checked and awaits execution on the operator's Windows machine. Yahoo market-data
  acquisition and all market backtests in this new suite remain unrun here.

## Market-results transition — September 14, 2026

The operator subsequently completed the market run at `b23a0ea` and supplied its full
review ZIP. Its data, code, outputs and accounting were checked and the fixed screen was
replayed. None of the current configurations is recommended for OOS/Monte Carlo promotion.
The 63-session momentum comparator is modestly profitable; the tested reversal/pullback
and fixed-blend mappings do not justify continuation as standalone candidates.
Full results, retained evidence and the nuanced control comparison are in
`docs/research/FRESH_STRATEGY_DISCOVERY_RESULT_20260914.md`.

Two reporting defects found during replay are corrected: economically flat returns need
a `1e-12` tolerance when counting positive days, and false-valued synthetic metadata must
not set the synthetic presentation label. Neither fix changes strategy/accounting logic,
daily returns or headline economic metrics. The original summary tables are preserved;
the corrected positive-day diagnostic is a separate evidence file. 26 focused tests pass.
