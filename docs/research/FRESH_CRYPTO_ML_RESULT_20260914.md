# Fresh crypto ML — first development result and research decision

**Decision: reject promotion of this ML allocation setup; continue research on the
fixed state rule and fixed blend.** Neither learned model establishes useful incremental
value beyond the simpler controls. This is a conclusion about the specified features,
14-day counterfactual target, estimators and decision rule, not a conclusion that all ML
applications to crypto are ineffective. No OOS or Monte Carlo result is claimed.

The full fixed experiment was reproduced from the operator's archive. No parameter,
feature, horizon, asset universe or strategy variant was added during the review.

## Source and audit

- Operator archive: `fresh_crypto_ml_20260914_134645_379.zip`.
- SHA-256: `7d27e12ec606d9168962204a4ad65ab9ea9a9fefbbaeae53b982dba00a803d5d`.
- Source commit: `682b6054c0024ddefef12898dbb190fc33727ed3`.
- Prices: the previously reviewed BTC/ETH snapshot, 2017-01-01 to 2024-12-31.
- Portfolio evaluation: 2020-01-01 to 2024-12-31; earlier observations supply training.
- 32 portfolios, four scenarios, 128 ledgers and 233,856 daily rows.

All 18 manifest file hashes, 17 code/specification hashes, ZIP CRC and complete daily
calendars verify. All recorded code hashes match the pinned Git files with uniform
Windows CRLF line endings. All 120 archived training sets reconstruct exactly from
the saved feature and label bytes, including strict label maturity and prediction
availability. These comprise 80 learned fits and 40 constant estimates.

The audit reran those same 80 learned fits; the existing replay requirement executes
each twice, so 160 learned-fit executions and 80 constant-estimate executions occurred.
Features reproduce exactly. Cross-platform label differences are at floating-point
precision: maximum target difference 8.78e-16 and forecast difference 7.90e-17. Binary
hashes of newly regenerated training sets therefore differ from the Windows hashes;
this does not affect the exact reconstruction of the archived training bytes. All
mixture selections and executed/skipped trade decisions are identical.

All 128 wealth paths replay to numerical precision: maximum daily-return difference
2.00e-15 and unit-capital NAV difference 2.23e-14. Full/era metrics, annual returns,
prediction diagnostics and matched-control comparisons reconstruct. Independent
wealth/P&L/weight checks and 12 buy-and-hold price/fee identities pass. Deliberately
corrupted training timing and a corrupted return each trigger a failure.

The source and reviewer use numpy 2.4.4, pandas 3.0.2, scikit-learn 1.9.0, scipy 1.17.1
and threadpoolctl 3.6.0; Python is 3.12.13 on Windows and 3.12.14 in the reviewer
environment. Original exchange/vendor acquisition provenance remains unverified.
Daily opening fills and proportional cost assumptions do not establish live capacity.

## Comparable portfolio economics

The following table uses the same 2020–2024 dates, 30 bps one-way costs and 2% execution
band throughout. The numbers 20/40 denote forecast-volatility settings, not returns.
Sharpe uses zero-yield USD cash and sqrt(365) annualization. CAGR uses elapsed calendar
time and full-equity wealth. All exposure is unlevered spot with cash.

| Policy | Risk setting | CAGR | Sharpe | Max drawdown | Realized annual volatility |
|---|---:|---:|---:|---:|---:|
| Risk-controlled allocation | 20% | 28.78% | 1.262 | -34.38% | 21.93% |
| Trend | 20% | 27.58% | 1.322 | -23.42% | 19.91% |
| Fixed 50/50 blend | 20% | 28.53% | 1.320 | -28.33% | 20.60% |
| Simple state rule | 20% | 28.78% | 1.365 | -23.41% | 19.99% |
| Ridge ML | 20% | 27.99% | 1.339 | -23.42% | 19.90% |
| Boosted ML | 20% | 26.54% | 1.243 | -32.01% | 20.64% |
| Risk-controlled allocation | 40% | 57.82% | 1.265 | -58.90% | 43.63% |
| Fixed 50/50 blend | 40% | 53.49% | 1.289 | -48.07% | 39.22% |
| Simple state rule | 40% | 50.32% | 1.267 | -38.20% | 37.84% |
| Ridge ML | 40% | 35.56% | 0.984 | -60.56% | 38.52% |
| Boosted ML | 40% | 48.02% | 1.194 | -52.80% | 39.35% |
| BTC buy-and-hold | Uncapped | 66.65% | 1.116 | -76.67% | 65.22% |
| ETH buy-and-hold | Uncapped | 91.80% | 1.201 | -79.35% | 84.42% |

The state rule was fixed before this run: use trend protection when the fraction of
positive BTC/ETH 90/180/365-day trend votes is below two thirds, or the average ratio
of 20-day to 60-day volatility exceeds 1.25; otherwise use risk-controlled allocation.
It makes weekly mixture decisions using completed bars. It has no fitted parameters.

At 20%, ridge adds only 0.41 percentage points of CAGR and 0.017 Sharpe over banded
trend, while the state rule adds 1.20 points and 0.043. The rule has higher CAGR and
Sharpe than ridge in both the 2020–2021 and 2022–2024 eras. Their average risky exposures
are very similar: state 29.28% and ridge 29.17%. This result does not support crediting
the ML architecture for the strongest observed improvement.

At 40%, the state rule and fixed blend express different return/drawdown trade-offs.
The blend has higher CAGR and Sharpe; the rule has a smaller drawdown and higher
Calmar, 1.317 versus 1.113. Ridge is worse on all three headline metrics than either.
Boosted ML also has lower CAGR, lower Sharpe and a deeper drawdown than both.

Even the better control paths require patience: the state rule remains below a prior
daily wealth peak for as long as 754 days at 20% and 825 days at 40%. Its CAGR is not
a stable annual payout or a forward return forecast.

## Costs, execution and concentration

| Policy, 2% band | Base CAGR / Sharpe / DD | 75 bps CAGR / Sharpe / DD | Extra-day delay CAGR / Sharpe / DD |
|---|---|---|---|
| State rule 20 | 28.78% / 1.365 / -23.41% | 25.70% / 1.243 / -25.29% | 27.77% / 1.322 / -21.94% |
| Ridge 20 | 27.99% / 1.339 / -23.42% | 24.54% / 1.201 / -25.64% | 27.93% / 1.334 / -21.97% |
| State rule 40 | 50.32% / 1.267 / -38.20% | 44.84% / 1.169 / -41.41% | 48.15% / 1.226 / -38.07% |
| Ridge 40 | 35.56% / 0.984 / -60.56% | 29.74% / 0.870 / -64.01% | 33.32% / 0.939 / -61.13% |

Ridge 20 does beat the state rule modestly on CAGR and Sharpe in the extra-day scenario:
0.16 CAGR points and 0.013 Sharpe with the band, and 0.33 points and 0.019 under exact
execution. Its drawdown is slightly deeper. This exception matters: the rule does not
win every scenario. But ridge trails the rule in frictionless, base and cost-stress
comparisons under both execution treatments.

At 20%, the band reduces the state's annual one-way turnover from 6.29x to 5.37x and
raises stressed Sharpe from 1.213 to 1.243. Banded ridge still turns over 6.07x. At base
cost, banded arithmetic execution drag is 1.61% annually for state, 1.82% for ridge,
and 2.17% for trend. The band is an execution control applied to all policies; its
effect cannot be attributed to ML. Its base CAGR is not uniformly higher than exact
execution, so this review does not optimize or further tune the band.

2022 is the main ridge-40 failure: annual return is -51.99% with the band, versus
-24.69% for the state rule and -35.50% for the fixed blend. Exact-execution losses are
-52.06%, -24.54% and -36.06%, respectively. Banded ridge's 2022–2024 CAGR is just 1.08%,
versus 19.32% for state and 20.12% for the blend.

Deleting one calendar year's saved returns at a time leaves the state-20 Sharpe above
ridge-20 in all five cases. This is a retrospective influence diagnostic, not a refitted
backtest or significance test. Protection's benefit still depends on bear-market
experience: excluding 2022 makes allocation-20 Sharpe 1.878 versus state-20 1.767.

The higher headline returns versus the earlier crypto screen must not be interpreted
as an ML improvement. The original screen included 2018–2019; the ML comparison starts
in 2020. Even unchanged non-ML controls therefore show different returns. The state-40
control has 112.68% CAGR in 2020–2021 but 19.32% in 2022–2024. Comparing all policies on
matched dates is essential; the full 50.32% development CAGR is not a projection.

## Did the models predict their target better?

No, under the fixed target and squared-error criterion. All four model/profile pairs
have higher RMSE and MAE than the quarterly expanding training-mean predictor. Each
comparison uses the same 260 weekly predictions with fully observed 14-day outcomes.
The last two decisions remain in the portfolio but are not scored without full labels.

| Model | Risk setting | RMSE above constant | MSE skill versus constant |
|---|---:|---:|---:|
| Ridge | 20% | 4.92% | -10.07% |
| Boosted | 20% | 5.92% | -12.19% |
| Ridge | 40% | 6.53% | -13.49% |
| Boosted | 40% | 9.61% | -20.14% |

Skill here is `1 - MSE_model / MSE_constant`; it is not an R-squared score against the
evaluation-period mean and is not a p-value. The mean predictor is a standard no-feature
regression comparator; scikit-learn documents this role for
[DummyRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.dummy.DummyRegressor.html).
This runner implements the same training-mean baseline directly.

Raw sign accuracy is misleading here: 81 of 260 target values at 20% and 69 at 40% are
within 1e-12 of zero. Exact zero comparisons are sensitive to numerical noise, and
getting the sign of a near-zero difference right has little economic meaning. The
constant predictor has lower reported sign accuracy yet lower error; its allocation
decisions stay at trend for all 262 weekly decisions, reproducing the trend portfolio.
These checks favor continuous forecast error and actual net portfolio economics over
an isolated classification-accuracy number.

No observed error was repaired by refitting transformations to the whole dataset.
Training-only preprocessing follows the information boundary described in
[scikit-learn's leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage).
The audit verifies the actual training sets rather than relying on a named split alone.

## Decision and next experiment

Stop tuning this ridge/boosted allocation version. Preserve its negative result and
all simple controls. A small delay-specific ridge-20 advantage is insufficient to
justify an ML branch when prediction errors are worse and its primary comparisons
favor a simpler rule.

The next inexpensive, discriminating test is to evaluate the *unchanged* state rule
and fixed blend across the available 2018–2024 development period, explicitly including
2018's bear market and 2019's recovery. Keep trend, risk-controlled allocation and spot
buy-and-hold comparators; retain the fixed 20%/40% profiles, exact/2% band treatments,
30/75-bps costs and extra-day stress. The current normalized snapshot already supplies
the needed prices and 2017 warm-up, so no new market-data download is required.

Record the longer-window design before running it locally. Treat the exercise as
development, since both the rule design and this next-step decision are informed by
inspected history. If the broader trade-off survives, freeze a small candidate set and
review prior access to 2025+ before any final chronological OOS evaluation. Only then
design joint BTC/ETH block resampling that retains dependence and distinguishes a
fixed deployed model from a retrained pipeline. No OOS/Monte Carlo claim follows from
this archive alone. No Core, runtime, paper/live configuration or capital change.

The longer-window experiment is recommended but has not been implemented or run in
this review. The operator does not need to rerun the completed ML experiment.

## Reproduction and evidence

The aggregate evidence is in `evidence/fresh_crypto_ml_20260914/market_review/`:
`review_audit.json`, all full/era `metrics.csv`, `annual_returns.csv`,
`matched_control_comparisons.csv`, `forecast_value.csv`, `leave_one_year_out.csv` and
`buy_hold_identities.csv`. Raw prices and full ledgers remain in the supplied archive.

Optional audit reproduction from the repository root, with a new output directory:

```powershell
uv run --locked --python 3.12 --extra dev python -m scripts.review_fresh_crypto_ml --archive '.\artifacts\fresh_crypto_ml_20260914_134645_379.zip' --output-dir '.\artifacts\fresh_crypto_ml_review_local'
```

This command reproduces the existing fixed fits and checks; it does not introduce
new model trials or open the reserved period. The audit refuses to run if consumed
research code/specification differs from the source commit.
