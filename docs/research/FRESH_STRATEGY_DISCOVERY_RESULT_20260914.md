# Fresh strategy discovery — first market screen reviewed

## Decision

**No current configuration is recommended for OOS/Monte Carlo promotion.** This is a
research judgment from the observed trade-offs, not an imported charter threshold or a
formal universal null. The best momentum configuration earns positive net returns but
does not establish a compelling standalone advantage over simple controls. The tested
sector-reversal mappings lose money; pullbacks spend little capital productively while
paying substantial turnover costs; the fixed blend combines those weaknesses.

Retain 63-session momentum as a comparison strategy and a possible diversification
hypothesis. Its base daily-return correlation with SPY is 0.334. This screen did not test
a SPY/momentum allocation, so that possible portfolio use is unresolved, not a positive
portfolio finding. If pursued, specify that separate allocation experiment before
evaluating it. Do not treat another lookback adjustment as unseen confirmation.

## Source and audit

The operator supplied `fresh_discovery_20260914_090006_675.zip` after running commit
`b23a0ea76c4ab8a69ed8416dd624180817d43738`. Its SHA-256 is
`9cb9bd23f9921de9f9cae5d1758c8f15cef7dc9a9559c53fb5d9ab564654a2e3`.
The ZIP contains the completed market backtest as well as the downloaded data.

Verified archive CRC, all recorded output/source hashes, all 20 source manifests and
their common calendar, and the archived specification. The ten code/spec/lock/runner/test
hashes match the pinned commit under Windows CRLF checkout encoding; no source-text
change was found. Input history contains 4,427 common sessions from June 1, 2007 through
December 31, 2024. Evaluation contains 4,154 sessions from July 1, 2008 through December
31, 2024: 28 policies × four scenarios = 112 ledgers / 465,248 rows. The 2008 year is partial.

The entire fixed screen was replayed locally from those exact cached files. No download,
new strategy variant, model fitting or OOS evaluation was performed. All 43,428 target
weight rows, asset-attribution output and robustness summary are byte-identical.
Windows/Linux floating-point/serialization differences prevent claiming global byte
identity: maximum daily return delta is approximately 1.00e-13; NAV delta approximately
1.00e-11; full/era CAGR, Sharpe and drawdown metric deltas approximately 1.00e-13.
All nonnumeric output identities and missing-value patterns match.

An independent reconstruction of all 112 wealth paths and CAGR/drawdown metrics from
the saved returns reconciles within CSV precision. Eight SPY/BIL buy-and-hold results
also match the direct adjusted-open price ratio times entry/exit cost factors. These
checks validate the implemented accounting; they do not establish point-in-time Yahoo
data provenance, broker fills, margin feasibility, capacity or statistical significance.

Full audit and original summary tables are preserved under
`docs/research/evidence/fresh_discovery_20260914/`. Original uploaded tables remain
unchanged; the positive-day reporting correction below has its own separate table.

## Full-period base economics

Full-equity denominator; net of 5 bps one-way execution, 1% annual borrow on shorts,
and lagged BIL yield + 1.5% long-debit financing. Sharpe uses excess daily returns over
frictionless BIL, annualized by 252 sessions. Drawdowns include initial equity and costs.

| Policy | Net CAGR | Excess Sharpe | Maximum drawdown | Calmar |
|---|---:|---:|---:|---:|
| SPY buy-and-hold | 11.87% | 0.610 | -47.17% | 0.252 |
| Static macro, gross target ceiling 1.0 | 5.96% | 0.541 | -21.74% | 0.274 |
| 63-session momentum, ceiling 1.0 | 6.75% | 0.513 | -23.49% | 0.288 |
| 63-session momentum, ceiling 1.5 | 7.37% | 0.469 | -30.10% | 0.245 |
| Trend-only control, ceiling 1.0 | 5.57% | 0.468 | -18.94% | 0.294 |
| 5-session pullback, ceiling 1.0 | 1.68% | 0.193 | -7.02% | 0.240 |
| 10-session sector reversal, ceiling 1.0 | -3.25% | -0.763 | -47.50% | -0.068 |
| Fixed blend, ceiling 1.0 | 1.42% | 0.106 | -11.83% | 0.120 |

The static macro control uses the same ten-ETF universe with inverse-volatility weights
and the same risk treatment. Momentum's roughly 0.80 percentage-point CAGR increment
comes with 12.27% realized annual volatility versus 9.67%, a larger drawdown, and lower
Sharpe. Its gamma-3 certainty equivalent is slightly higher (5.04% versus 4.86%) and its
Calmar is slightly higher: it is not strictly dominated on every criterion. Those modest
trade-offs do not support describing the result as a strong new standalone strategy.

Increasing momentum's target ceiling adds about 0.62 percentage points of CAGR but
deepens drawdown by about 6.61 percentage points, reduces Sharpe from 0.513 to 0.469,
and reduces CE from 5.04% to 4.66%. Gross exposure can drift above the target ceiling
between rebalances; the original report documents this rather than enforcing a live cap.

## Mechanism-specific findings

**Momentum:** the 63-session unlevered configuration is the strongest candidate by base
excess Sharpe. Early-era CAGR/Sharpe is 6.45%/0.568; 2017–2024 is 7.08%/0.456. It is
positive in 11 of 16 complete calendar years and beats the static control in nine of 16.
Returns are not confined to one positive asset or one isolated year. However, 2015,
2016, 2018 and 2022 lose money, 2024 earns only 0.86%, and the longest period below a
previous high is 746 sessions. The worst year-deletion Sharpe is 0.446 (excluding 2011).
These observations support a modest, uneven strategy, not a numerical artifact or a
high-performance discovery. Neighboring 126/252-session candidates have lower base
Sharpe (roughly 0.41–0.44).

**Sector reversal:** all six candidates lose after costs, with CAGR ranging from -3.25%
to -7.54%. Even frictionless excess Sharpe is negative for all six. The best frictionless
CAGR is only 0.51%, below the roughly 1% BIL comparator over the period. Zero modeled
costs at the specified next-open execution time do not rescue the residual-reversal prediction. Removing market moves and
adding the hedge does not establish an economical reversal premium in this ETF design.

**Pullbacks:** the 5-session unlevered mapping earns 1.68% CAGR with 0.193 excess Sharpe.
Its average risky gross exposure is only 9.11%, compared with 67.61% for the trend-only
control. Its small drawdown therefore reflects extensive cash holding as well as entry
timing; it is not equivalent to achieving high returns with unusually low risk. Turnover
is 33.05 times equity per year and the execution drag is about 1.65% of equity annually.
The simple trend-only control has higher CAGR, Sharpe and CE. Every pullback candidate
has negative CAGR under the cost stress. Reject these particular monetization mappings.

**Fixed blend:** 1.42% CAGR / 0.106 Sharpe at ceiling 1.0; 1.07% / 0.044 at ceiling 1.5.
The higher ceiling worsens the result. It does not combine three independently valuable
edges; the losing/expensive components impair its economics. No blend promotion.

## Execution stress

| Policy | Base CAGR / Sharpe | Cost-stress CAGR / Sharpe | Extra-session delay CAGR / Sharpe |
|---|---:|---:|---:|
| Momentum 63, ceiling 1.0 | 6.75% / 0.513 | 5.66% / 0.429 | 6.76% / 0.511 |
| Momentum 63, ceiling 1.5 | 7.37% / 0.469 | 5.54% / 0.359 | 7.25% / 0.459 |
| Pullback 5, ceiling 1.0 | 1.68% / 0.193 | -1.62% / -0.658 | 1.37% / 0.114 |
| Fixed blend, ceiling 1.0 | 1.42% / 0.106 | -2.17% / -0.587 | 1.31% / 0.085 |

Momentum survives the specified execution stresses but is not made compelling by that
fact. Under higher costs, its higher exposure ceiling earns less than the lower ceiling.
The pullback/blend weaknesses worsen under cost stress. Cost assumptions remain scenarios,
not claims about verified realized opening-auction fills.

## Reporting corrections discovered during review

1. The original `positive_day_fraction` used `return > 0`. Across platform replays,
   360 daily sign comparisons differed for returns no larger than 4.441e-16 in magnitude.
   The maximum period positive-day-fraction discrepancy was 0.004473 (0.4473 percentage
   points). The report now uses `return > 1e-12`, an explicit numerical-zero tolerance.
   This changes no daily returns, CAGR, Sharpe, drawdowns, positions or trade decisions.
   The separate correction table changes 94 of the 336 original summary rows; the corrected
   counts agree exactly across the two platform ledgers. This metric is a fraction of
   positive calendar-session returns, not a trade win rate.
2. Searching serialized metadata for the text `SYNTHETIC` matched the key
   `synthetic_data_used` even when its value was false. This affected the local replay's
   presentation label; the original submitted run was correctly labelled real data.
   Explicit boolean/status-value parsing fixes the label. No price or economic computation
   depends on the label, and no second market backtest is needed for this correction.

After these reporting-only fixes, **26 focused tests passed with warnings treated as
errors**, including the full synthetic screen replay and new label/rounding regression
checks. Accounting, strategy parameters, risk settings and the input dataset are unchanged.

## Next decision

Do not spend an OOS assessment or Monte Carlo promotion exercise on the current shortlist.
Keep the downloaded dataset and the momentum comparator. The unresolved portfolio question
is whether momentum's relatively low correlation with SPY provides enough diversification
to improve net return/drawdown trade-offs in a separately specified allocation experiment.
That is a possible next research test, not evidence already established by this screen.
No holdout was consumed and no paper/live/capital action follows.
