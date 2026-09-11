# Diversified trend foundation — fixed exploratory specification

Written before this baseline's performance calculation, 2026-09-11. Execution
specification only: this same-session discovery run is not a governed frozen
campaign or independent confirmation. No model fits or statistical null claim;
no formal power assertion. Core/runtime/portfolio settings remain untouched.

## Economic question

Can a fixed, medium-term trend policy provide useful downside management across
several market groups, at realistic costs, as a foundation for a subsequent ML
variance-forecast comparison? Slow adjustment to information and persistent
positioning are possible mechanisms, not identified causes. Alternatives are
static market exposure, reduced exposure alone, sample selection, and fund carry.

Universe is the available uploaded manifest-identified adjusted ETF snapshots:
equity SPY/QQQ/IWM/EFA/EEM; rates IEF/TLT; gold GLD; energy USO; agriculture
CORN/SOYB/WEAT. BIL is the cash proxy. Five groups, not twelve independent bets.
Commodity ETF returns include the fund's actual historical structure and roll
exposure; they are not spot commodity returns or synthetic rolled futures P&L.
US-listed fund feasibility is a research assumption; brokerage eligibility and
live order routing are unverified. No live integration or subscriptions.

The original nine files retain the incremental experiment's exact identities;
the energy/crop ZIP SHA256 and contained CSV/manifest SHA256 are recorded.
Use the common supplied session calendar, 2013-12-02 to 2024-12-31, with no
imputation. All source checks must pass before signals. Drop no bad row silently.

## Fixed signals and allocation

At each completed calendar-month's last supplied session, compute adjusted-close
63,126,252-session returns minus corresponding BIL returns. Invest a fraction
0,1/3,2/3,1 according to the fraction of these three excess trends strictly
positive. Three speeds are averaged with equal weights; no speed selection.

Each of the five market groups receives a15% capital budget. Within a group,
allocate its budget inversely to trailing63-session realized volatility, using
only signal-close information. A1% annual volatility floor prevents division by
zero. Multiply each base asset weight by its trend fraction. Unused budgets
move to BIL; never redistribute an inactive group's budget to active groups.
Thus initial target risky exposure is at most75%, each risky asset at most15%.

Use trailing252-session covariance, half diagonal shrinkage, to scale the entire
risky allocation down if necessary to a10% predicted annual volatility ceiling.
Do not scale up or borrow. All targets are long-only and sum to one including BIL.
Risk estimates are causal approximations, not guarantees about realized risk.

Execute targets at next session open. Recompute each month; no threshold search,
stop-loss overlay, tactical override, or ML. Charge fees on actual dollars bought
and sold, including BIL switches, initial investment, and final liquidation.
No extra fund-expense deduction: adjusted fund return histories already reflect
fund expenses. Taxes, impact curves and actual fills are not modeled.

## Fixed benchmarks and scenarios

Four policies: trend; static group allocation under the identical volatility and
covariance rules; no-change shares seeded from the first static allocation; BIL.
No-change positions can drift beyond limits. The static allocation is the matched
construction benchmark. Also calculate a diagnostic static/BIL blend with its
fixed mixing fraction chosen to match trend's *observed* average risky exposure;
this is explicitly an ex-post attribution diagnostic, not a tradable contender.

Primary cost10bps per dollar traded. Same signal targets at0/5/25bps and a one
additional-session execution delay at10bps. Five scenarios x4 policies=20
ledgers. Scenarios are sensitivities, not candidates from which to select a winner.
Primary period: first eligible January2018 month-end signal through liquidation
at the final supplied December2024 open. Last December month-end signal is not
executed. Delay scenario shares terminal date; its last holding is one session
shorter, disclosed. Prices after2024 are excluded before feature construction.

## Evaluation and next decision

Report daily NAV, holdings/targets, turnover, fees, asset P&L contributions, CAGR,
annual mean/volatility/CE(gamma3), drawdown, worst21-session return, yearly and
ex2020 summaries, gross/net economics and market contribution concentration.
Ex2020 moments are descriptive, not a continuous investable equity curve.

No requirement that defensive trend beat static CAGR in every bull market.
Proceed to the single ML risk-forecast comparison if the baseline demonstrates
an economically material trade-off: improved drawdown/tail behavior without
merely duplicating an exposure-reduced static portfolio, or stronger net CE.
Report both dimensions and judgment; do not invent significance from this sample.
If it is dominated on return, risk and costs, stop before training ML and identify
whether long-only implementation or market coverage is a binding limitation.

Any ML experiment must keep these signals, market groups, budgets and execution
fixed; compare next-month risk forecasts against simple price-based forecasting
benchmarks and isolate forecast improvement from portfolio benefit. No neural
architecture sweep. This baseline does not claim ML value or staying power by
itself. Fresh holdout eligibility requires a separate use-history check; no year
becomes untouched because this strategy is new.

## Provenance and literature

Published futures/forward evidence motivates the strategy family, not this
long-or-cash ETF adaptation:
https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum
https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing

Record specification and code hashes before running, exact data identities,
actual environment, synthetic mechanics tests and independently reconciled
metrics. Synthetic correctness fixtures are not market evidence.
