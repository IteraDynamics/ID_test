# Fresh crypto review and proposed ML starting point

## Decision

**Continue research.** The 20% and 40% capped trend ensembles merit further work, but
their incremental advantage is sensitive to cost, delayed execution and the two bear
years in this sample. A narrow ML experiment could learn when the existing trend
portfolio is preferable to its same-risk-rule allocation control. This is a proposed
experiment, not an implemented ML strategy or an OOS promotion.

The operator asked where ML could improve this result and supplied the complete ZIP.
This review evaluates only the previously committed 16 policies and four scenarios.
There are zero new model fits, strategy variants, or holdout evaluations. Existing
charter performance targets did not enter the research decision.

## Verified evidence

Source archive: `fresh_crypto_20260914_110447_621.zip`.
SHA-256: `4cad6e73c19b24eeda7e8e0ae7d9ca2c9666306633fd76c67144790499d3a684`.
Run commit: `62cc0f1e110aa4f83e9502198e43105368fbc89e`.

Archive CRC and all 12 manifest-listed file hashes verify. The 11 code/spec/lock hashes
match the pinned Git revision under uniform Windows CRLF encoding. The separately
archived specification also matches. Normalized BTC/ETH calendars contain 2,922 complete
daily observations from 2017-01-01 through 2024-12-31, with no gaps or future prices.
Evaluation runs from 2018-01-03 through final liquidation at the 2024-12-31 open.

All 64 ledgers / 163,520 rows replay from the archived normalized inputs. Maximum
absolute return difference is 6.66e-16 and NAV difference 2.13e-14; target-weight
differences are at most 2.22e-16. Cross-platform bit identity is not claimed. Independent
wealth, asset-P&L, full-equity weights, CAGR and drawdown identities pass; every saved
full/era metric reconstructs. Twelve direct BTC/ETH/mixed buy-and-hold entry/exit-price
and fee identities pass. A deliberately corrupted return triggers the audit rejection.

The normalized data are sufficient to reproduce this run. The original full source
files are not in the ZIP, so their recorded hashes and vendor/acquisition history cannot
be independently checked here. Their source label is `operator_local_unverified`.
This audit validates the recorded inputs and implemented economics, not a historical
vendor's point-in-time publication behavior, executable opening fills or capacity.

Reproducer: `scripts/review_fresh_crypto_discovery.py`. Evidence tables and audit JSON:
`docs/research/evidence/fresh_crypto_20260914/`. Original supplied summaries are preserved.

## Return, drawdown and friction

All returns below are development results on the common window; Sharpe is excess over
zero-yield USD cash, annualized with 365 daily observations. The baseline cost assumption
is 30 bps one way, stress 75 bps. These are assumed all-in costs, not a verified fee tier.

| Profile / scenario | Trend CAGR | Trend Sharpe | Trend max DD | Allocation CAGR | Allocation Sharpe | Allocation max DD |
|---|---:|---:|---:|---:|---:|---:|
| 20%, frictionless | 19.74% | 1.018 | -25.63% | 17.80% | 0.855 | -38.15% |
| 20%, base | 17.01% | 0.900 | -27.13% | 16.70% | 0.812 | -38.65% |
| 20%, cost stress | 13.05% | 0.724 | -29.32% | 15.06% | 0.748 | -39.38% |
| 20%, one extra day | 16.38% | 0.874 | -26.55% | 16.30% | 0.796 | -38.55% |
| 40%, frictionless | 32.43% | 0.979 | -38.75% | 31.22% | 0.844 | -63.37% |
| 40%, base | 28.19% | 0.886 | -40.16% | 29.34% | 0.810 | -63.85% |
| 40%, cost stress | 22.08% | 0.747 | -45.21% | 26.59% | 0.761 | -64.55% |
| 40%, one extra day | 24.46% | 0.802 | -44.30% | 28.60% | 0.797 | -63.72% |

The base 20% trend portfolio improves the control's CAGR, Sharpe and drawdown. The 40%
trend portfolio exchanges some CAGR for substantially lower drawdown. At 75 bps, both
trend profiles retain drawdown protection but lose their Sharpe advantage. Delay hurts
the 40% profile more: CAGR falls from 28.19% to 24.46%. The cost and delay cases are
separate stresses; simultaneous high cost plus extra delay has not been evaluated.

Base annual one-way turnover is 7.66 times equity for trend-vol20 versus 3.14 for its
control, and 10.84 versus 4.79 for vol40. Annual arithmetic execution drag is 2.30% and
3.25% respectively for the trend strategies, versus 0.94% and 1.44% for controls. These
are sums of daily equity-normalized fee contributions divided by elapsed years, not
CAGR deductions: compounding explains why the frictionless-to-net CAGR gaps differ.

The uncapped trend portfolio earns 31.15%, Sharpe 0.779 and -69.64% maximum drawdown,
versus BTC buy-and-hold 29.90%, 0.729 and -81.38%. This apparent headline improvement
does not make a roughly 70% drawdown attractive or establish prospective superiority.

## Where the protection helped, and what it cost

| Year | Trend 20% | Allocation 20% | Trend 40% | Allocation 40% |
|---|---:|---:|---:|---:|
| 2018 (partial) | -21.79% | -30.56% | -29.26% | -53.91% |
| 2019 | 13.11% | 18.29% | 15.12% | 34.71% |
| 2020 | 71.74% | 77.45% | 141.83% | 196.76% |
| 2021 | 37.71% | 39.03% | 81.47% | 84.96% |
| 2022 | -15.42% | -25.99% | -24.55% | -47.57% |
| 2023 | 29.25% | 48.31% | 35.15% | 101.79% |
| 2024 | 31.17% | 32.35% | 55.78% | 67.62% |

Both capped trend profiles improve annual returns in the two losing years and trail
their allocation controls in all five positive years. This is a retrospective pattern,
not an available-at-the-time regime label or evidence that a model can identify it.

Both trend profiles have higher base Sharpe than their controls in the early and late
eras. However, omitting 2022 reverses their full-sample Sharpe advantage: vol20 becomes
1.128 versus its control's 1.156; vol40 becomes 1.094 versus 1.156. Omitting 2018 also
reverses vol40's advantage (1.148 versus 1.206). These year-deletion summaries omit
observations without refitting; they are sensitivity diagnostics, not new backtests or
independent statistical tests. Protection being valuable in bear markets is expected;
only two such years leave little evidence about how reliably a learned gate could generalize.

The economic opportunity is therefore specific: retain some protection while reducing
missed participation and unnecessary trading. An abstention-only overlay may simply
lower exposure further. Improvements must be compared with static allocation changes
and inexpensive execution rules before being attributed to learning.

## Proposed minimum ML experiment — not yet implemented

### Decision and action space

Use two fixed experts already present in the research code: the trend ensemble and the
daily equal-weight allocation control with the same volatility treatment. Let a model
select their mixture once a week, from 0%, 50%, or 100% trend. Daily targets remain a
mixture of their causally computed targets, with the mixture coefficient held between
weekly decisions. Thus the model can favor protection or retain more allocation exposure
when the trend filter stands aside. It does not select a coin universe, rewrite the
90/180/365-day rules, add leverage, or choose its risk budget after seeing results.

Use the 20% profile as the primary learning experiment and the 40% profile as a declared
risk-sensitivity check. The two endpoints satisfy the same ex-ante covariance risk cap;
convex mixtures respect that cap at target formation. Actual realized volatility and
drawdown still need measurement. All candidate target changes enter the same full-equity
inventory ledger with cash and actual transition fees; do not splice saved sleeve returns
and ignore the cost of changing the mixture.

### Target and features

Propose one 14-calendar-day decision horizon. The regression target is the difference
in net log terminal wealth of trend versus allocation over the following 14 days,
beginning at the earliest executable open, not at the close used to form features.
This targets relative compounded growth and keeps payoff magnitude in the label.
It is not a direct predictor or guarantee of maximum drawdown; protection must also
be evaluated against the original portfolios, rather than assumed from this loss.

Generate counterfactual labels from common starting capital/holdings and a documented
common terminal convention, including transition, interim rebalance and exit costs.
The model predicts a relative payoff, not just whether BTC goes up. Absolute prediction
accuracy alone is not the success criterion. The score-to-mixture thresholds and the
rule for retaining the previous mixture when uncertain must be fixed using eligible
training/inner-validation data before each outer evaluation window.

Start with roughly 12–15 predetermined price/volume/state features, all available from
the existing normalized inputs. Useful groups: continuous volatility-normalized trend
strength and acceleration; agreement/disagreement across the three trend horizons;
recent drawdown and downside volatility; short/long volatility ratio; BTC/ETH relative
strength and correlation; volume relative to its own history; current holdings and the
turnover required to change the mixture. Final formulas and the exact feature count
must be fixed in the implementation record before fitting. Feature relevance here is
a hypothesis, not a finding from a fitted model.

### Models, nulls and execution ablations

Compare one regularized linear regression with one shallow gradient-boosted regression.
Use a small fixed configuration budget and training-only scaling. The linear model asks
whether the proposed information has a stable simple relationship to relative value;
the shallow tree model tests interactions such as weak momentum with rising downside
volatility. There is no reason yet to pay for a large neural model or reinforcement
learning search given two correlated assets and seven years of overlapping outcomes.

Required controls are both existing endpoints, a fixed 50/50 mixture, a training-only
constant predictor passed through the same allocation mapping, and one simple
volatility/trend-state rule fixed before evaluation. Include a predetermined small
no-trade-band rule (skip economically minor target changes) as an execution ablation,
applied equally to learned and fixed mixtures. A simpler blend or execution rule may
capture much of the benefit; that is a valuable result and would not be ML alpha.
Do not optimize the band, horizon, feature list and model architecture together.

### Evaluation and what would change the decision

Use chronological development walk-forward evaluation: initially train on matured
2018–2019 labels and score 2020, then refit on a fixed quarterly schedule using only
labels fully observed before that fit. Compare all baselines over exactly the same
2020–2024 evaluation dates, not their longer 2018–2024 headline histories. All fitted
scaling, clipping, feature selection, calibration and threshold selection must stay
inside the eligible fit boundary. Scikit-learn documents why preprocessing fitted to
the full dataset leaks information: [official guidance](https://scikit-learn.org/stable/common_pitfalls.html).

The 14-day outcomes overlap. Use their actual execution-to-label-availability intervals
to exclude immature/overlapping training labels at boundaries. A generic chronological
split or an arbitrary gap alone is insufficient. Preserve shared BTC/ETH dates in every
split and any later resampling. Weekly actions reduce turnover but do not turn seven
years into hundreds of independent market cycles.

This design is informed by already inspected 2018–2024 outcomes, so even correctly
walk-forward model predictions in that period remain development evidence. Reserve
2025+ within this exercise until the research design is frozen and prior access has been
checked. No 2025+ price or ML result was inspected in this review.

Judge whether learned mixtures improve net return/risk trade-offs beyond fixed mixtures,
constant predictions and execution controls, including 30/75-bps costs, extra-day latency,
year/era concentration, exposure, drawdown and time underwater. A higher gross Sharpe,
an accuracy number, or a win caused solely by holding less risk is insufficient.
Counterfactual labels and simulator fills remain research assumptions to audit.

**Recommended first action:** implement this bounded comparison, beginning with fixed
mixture and no-trade-band controls, then the two small supervised models. Do not fit a
large model to optimize the full-period Sharpe, and do not consume the reserved period
to choose among versions. No numerical improvement from ML is claimed or forecast.
