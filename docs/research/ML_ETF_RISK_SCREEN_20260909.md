# ETF risk-allocation exploration screen

2026-09-09. Operator authorized the pivot after manual Stooq download returned
an `access denied` body. Pause the broad-stock historical allocation design and
close its current data-recovery effort. Preserve the issuer-feature and source
work for reuse. No claim that every free stock source is exhausted is made.
This explicitly supersedes the prior design's restriction of ETFs to fixtures.
Experiments 012 and 013 retain their original conclusions.

Status: SCREEN CARD RECORDED; waiting for existing QQQ/GLD daily CSVs. No fits,
screen classification or economic results yet. This is the Amendment 6 exploration
sandbox, not a frozen campaign, production change or Core allocation proposal.

## Screen card

**Decision:** each week, how much of each fixed SPY, QQQ and GLD research budget
should remain exposed versus idle cash? No ETF ranking or optimizer is involved.

**Mechanism to test:** margin constraints, volatility-based mandates and gradual
position liquidation can prolong turbulent market states. Simple trend and
volatility rules may already capture all useful information. The specific ML
hypothesis is that their conditional combination predicts downside risk better
than either rule and improves a fixed exposure policy after costs. This is a
weak, falsifiable hypothesis; price proxies do not identify forced flows or
establish their cause. Risk forecastability alone does not imply an allocation edge.

**Persistence:** institutional constraints recur and do not require participants
to maximize short-term alpha. Arbitrage can nevertheless remove any incremental
allocation benefit. Controls below directly test that possibility.

**Instruments/venue:** fixed named U.S.-listed ETFs, long-only, unlevered. These
are existing research instruments; SPY/QQQ/GLD appear in Core paper research.
Actual broker access and execution quality are not established by those files.
No live/paper execution is proposed. Fixed fund selection is retrospective and
does not establish broad ETF-universe performance or eliminate selection bias.

**Horizon:** next 21 sessions for risk forecasting, weekly target updates, next
session open for execution. This screen uses an offline schedule and must pass
a one-additional-session execution-delay sensitivity. It does not assume the
existing runtime can execute a new sleeve on that schedule.

**Falsification:** learned forecasts must improve on a past-only event-frequency
forecast; learned allocation must improve on simple risk controls after costs.
Failure at either stage closes this screen. Do not add predictors or thresholds
to rescue its result.

**Budget:** one implementation and one fixed two-model comparison, seven annual
fits per model (2018–2024), 14 fits total. One bug-fix replay is allowed only for
an invalid run. No performance-driven search. Target one working session once
the two missing files are supplied; unresolved implementation/data work beyond
one day requires a scope decision.

## Data and time contract

Use SPY, QQQ, GLD daily OHLCV with their supplied auto_adjust=True manifests.
Features and execution prices use the same adjusted-price basis. This represents
synthetic total-return units, with provider distribution/reinvestment assumptions,
not nominal shares. Do not add dividends again. Do not mix in the unadjusted
TLT file. Absolute adjusted price and adjusted dollar volume are not predictors.

Common source period begins 2013-12-02. Only dates through 2024-12-31 enter any
features, fits, outcomes or summaries. Later rows may remain in source files and
hashes but are quarantined. Features require 200 prior closes; first evaluation
year is 2018. Common eligible decision dates come from SPY's session calendar;
any missing QQQ/GLD session or required price fails support rather than dropping
the date. Validate dates, numeric finiteness, positive OHLC, OHLC ordering,
nonnegative volume, duplicates and adjustment consistency before modeling.

The week-end signal is the final observed SPY session in an ISO week. Use data
through that close, enter at the following session open, and retain targets until
the next weekly entry. A holding interval is evaluated only if its next entry
and all required outcomes are before 2025. Include initial trading and final
liquidation. No fabricated future sessions or same-close execution.

For each daily training signal t, label an adverse event when the minimum
adjusted close across the next 21 sessions is at least 5% below the following
session's adjusted open: min(C[t+1:t+21])/O[t+1] - 1 <= -0.05.
This is loss relative to entry, not peak-to-trough drawdown. The 5% threshold and
21-session horizon are design defaults, not tuned winners.

Annual expanding fits pool eligible past rows from all three ETFs. For the first
weekly signal of each evaluation year, fit only rows whose entire label window
ended strictly before that signal date. Every ETF uses the same chronological
boundary. No random row split. Fit scaler and estimator on training data only.
Daily labels overlap and ETFs are correlated; report dates, event episodes and
weekly decisions, never count pooled rows as independent evidence. A one-class
training fold makes the screen inconclusive, not permission to move its boundary.

## Fixed models and inputs

Predictors: simple adjusted-close returns over 5/20/60 sessions; C/SMA200 - 1;
20/60-session sample standard deviation of daily simple returns times sqrt(252);
C/max(last 60 closes) - 1; fraction of negative returns in the last 20 sessions;
plus fixed one-hot ETF identity. No macro releases, earnings, hand-picked crisis
flags, future classification or historical stock constituents.

1. Primary: standardized logistic regression, C=1, L2, max_iter=1000,
   class_weight=None, solver=lbfgs.
2. Secondary: histogram gradient boosting classifier, learning_rate=0.05,
   max_iter=100, max_depth=2, max_leaf_nodes=4, min_samples_leaf=100,
   l2_regularization=10, early_stopping=False, random_state=0. No scaling needed.

No hyperparameter sweep, post-fit calibration or model blend. Historical event
frequency is fitted separately per ETF using the identical eligible training rows.
Score weekly out-of-sample probabilities with Brier score, log loss and calibration
bins (five fixed equal-width bins). Report full period, 2018–2020, 2021–2024,
individual years and ETFs. Use the same dates for paired comparisons.

## Exposure policy and controls

Each ETF has one third of total research NAV as its target budget. Learned
exposure e=clip(1-p, 0.25, 1). Its total-NAV target weight is e/3; cash gets the
remainder. No leverage, short positions or redistribution to another ETF.
No threshold optimization. Idle cash earns zero in all portfolios, explicitly a
research cash proxy; this cannot establish performance against an interest-paying
cash product, especially when exposure differs. Any positive result requires
actual cash-return sensitivity before promotion.

Apply the same budget convention to five controls:

- Constant exposure e=1.
- Constant exposure e=0.75.
- Constant exposure e=0.5.
- Trend e=1 when C>SMA200, otherwise 0.25.
- Volatility target e=clip(0.10/RV60, 0.25, 1); zero RV implies e=1.

Each portfolio has its own continuous ledger. Trade against drifted holdings,
solve post-cost sizing within available NAV, charge buys and sells, and mark
daily NAV. Primary cost is 10 basis points times absolute traded notional;
25 basis points is the adverse scenario. These are assumptions, not broker quotes.
No shared flat cost deduction or use of the existing HOLD/exposure harness.

Report net CAGR, annualized mean/volatility, maximum drawdown, worst 21-session
return, turnover, average exposure and cash fraction. Primary economic comparison
is annualized certainty equivalent CE=252*mean(daily net return)
- (3/2)*252*sample_variance(daily net return). Gamma=3 and an incremental
0.005 annual CE hurdle are declared defaults. This is a screening utility proxy,
not an assertion of the operator's optimal risk aversion.

## Outcome rule

SCREEN_INVALID: causality, accounting or integrity defect. Correct the defect.
SCREEN_INCONCLUSIVE: inadequate coverage/fold support, or apparent positive
conclusions reverse when 2020 is excluded. Report that dependence, not a rescue.
SCREEN_NEGATIVE: otherwise, primary logistic fails either positive Brier skill
versus its past-frequency control in both subperiods, or net CE lift over the best
of all five controls is <=0.005 over the full period, or it fails to exceed
every control's CE in either subperiod. Equality fails each positive hurdle.
SCREEN_POSITIVE requires all those conditions plus positive full-period CE lift
against every control at 25bp and under the extra-session delay. If main hurdles
pass but a robustness condition fails, classify SCREEN_INCONCLUSIVE.

GBM is a secondary diagnosis and cannot rescue a primary failure in this screen.
Report annual and per-ETF contributions and the result excluding each calendar
year; 2020 exclusion is the explicit crisis-dependence check. Do not silently
omit bad years. This exploratory sample is short and previously inspected.
A positive screen only earns governed research, including cash-return treatment,
tradeability, dependency-aware uncertainty/power and independent review.

## Inputs already checked and next local action

The supplied sample ZIP contains the full SPY file, 3,199 rows including later
quarantined dates, rather than just a short sample. Its adjusted-close daily
gross-return ratios on 1,761 overlapping 2018–2024 dates differ from the recent
Yahoo Adj Close download by at most 9.50e-7. This is a limited consistency check,
not independent validation of the provider. SPY does not need uploading again.
QQQ and GLD manifests are already available, but their full daily CSVs are not.
Upload the existing QQQ_1D.csv and GLD_1D.csv together. No subscription, new data
download, Stooq retry or original-checkout switch is necessary. Verify the
current matching manifests with the files if they changed since August 25.
