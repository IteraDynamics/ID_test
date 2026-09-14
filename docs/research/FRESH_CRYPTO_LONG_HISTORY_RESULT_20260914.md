# Fixed crypto rules: longer-history result and research decision

## Decision

Advance `state_rule_vol20_band2` and `state_rule_vol40_band2` to a frozen historical
forward evaluation. Treat 20% as the primary risk-adjusted research profile and 40%
as the higher-return, higher-risk alternative. Report both; do not use the next
period to choose a risk budget retrospectively. Keep plain trend, risk-controlled
allocation, the fixed blend and spot buy-and-hold as comparators.

The state rule has a useful development return/drawdown trade-off. Its incremental
advantage over plain trend is modest and partly explained by lower trading costs.
The fixed blend remains a comparator rather than the lead candidate. The earlier
learned allocator remains unpromoted. These findings justify another fixed test;
they do not establish validated alpha or an expected forward return.

No rule, threshold, covariance setting or cost assumption changed during this audit.
No ML fit, post-2024 evaluation or Monte Carlo calculation occurred. The next-stage
runner and its full validation protocol are still to be implemented and committed
before the operator evaluates that period. No rerun of this experiment is needed.

## Evidence and reproduction

Source: `fresh_crypto_long_history_20260914_142341_250.zip`, 23,046,161 bytes.
SHA-256: `1e760e98447d1544cce5f8be4d93953ce6026e12cc2dc6002c5358f0a1a600fb`.
The run used source commit `535453e3a7499c00111f7f90a587c36dea9a1a7a`.

The review verified all 14 artifact hashes, all 14 code/specification hashes, ZIP
integrity, the archived specification and the exact pinned BTC/ETH input snapshots.
Windows source files match the pinned commit under uniform CRLF line endings. Both
input calendars contain 2,922 days, January 1, 2017 through December 31, 2024.

All 20 policies across four scenarios were replayed: 80 ledgers and 204,400 daily
rows. Archived features and mixture decisions reproduce exactly; floating-point
differences elsewhere are negligible (maximum ledger NAV difference 2.94e-14).
Independent wealth reconstruction, all 400 full-period/subperiod statistic rows,
and 12 closed-form buy-and-hold price/fee identities passed. A deliberately changed
return was rejected by the numerical comparison canary. Original vendor and
acquisition provenance remain unverified; byte identity is not vendor validation.

Reproducer: `scripts/review_fresh_crypto_long_history.py`. Aggregate evidence is in
[`evidence/fresh_crypto_long_history_20260914/market_review/`](evidence/fresh_crypto_long_history_20260914/market_review/).
Raw prices and full ledgers remain outside tracked evidence. To reproduce the audit
against a local copy of the ZIP, use a new output directory:

```powershell
uv run --locked --python 3.12 --extra dev python -m scripts.review_fresh_crypto_long_history --archive '.\artifacts\fresh_crypto_long_history_20260914_142341_250.zip' --output-dir '.\artifacts\fresh_crypto_long_history_review_local'
```

## Comparable full-period results

January 3, 2018 through December 31, 2024, including final liquidation. This is
already-inspected development history. Figures below are net of 30 bps one-way
costs; all active portfolios shown use the same 2% execution band. Spot is unlevered,
cash earns zero and Sharpe uses daily cash-excess returns with 365-day annualization.
The 20/40 labels are forecast volatility settings, not guaranteed realized risk.

| Policy | CAGR | Sharpe | Maximum drawdown | Realized annual volatility |
|---|---:|---:|---:|---:|
| State rule 20 | 18.11% | 0.956 | -26.02% | 19.37% |
| Plain trend 20 | 17.30% | 0.922 | -26.27% | 19.31% |
| Allocation 20 | 16.90% | 0.830 | -37.49% | 21.60% |
| Fixed blend 20 | 17.31% | 0.896 | -31.34% | 20.06% |
| State rule 40 | 30.29% | 0.921 | -39.34% | 35.65% |
| Plain trend 40 | 28.49% | 0.896 | -39.23% | 34.72% |
| Allocation 40 | 29.82% | 0.822 | -63.39% | 43.15% |
| Fixed blend 40 | 30.05% | 0.884 | -51.05% | 37.89% |
| BTC buy-and-hold | 29.90% | 0.729 | -81.38% | 68.77% |
| ETH buy-and-hold | 21.29% | 0.666 | -94.01% | 88.10% |
| Initial 50/50 buy-and-hold | 26.03% | 0.690 | -87.85% | 73.72% |

State-40 approximately matches BTC's base-case CAGR with substantially lower daily
drawdown, but takes more risk than state-20. It has a slightly deeper base drawdown
than plain trend-40. This is not dominance across all measures or scenarios.

The execution treatment is not the entire explanation: exact-execution state-20
and state-40 have CAGRs of 17.80% and 29.91%, with Sharpes of 0.932 and 0.910.
All exact, banded, frictionless and stressed results remain in `metrics.csv`.

## Bear markets, recoveries and concentration

| Calendar year | State 40 | Plain trend 40 | Allocation 40 | BTC buy-and-hold |
|---|---:|---:|---:|---:|
| 2018 | -28.15% | -28.60% | -53.21% | -75.10% |
| 2019 | 15.37% | 16.05% | 35.14% | 94.10% |
| 2020 | 146.47% | 142.69% | 197.83% | 304.57% |
| 2021 | 83.32% | 80.41% | 84.45% | 59.40% |
| 2022 | -24.69% | -24.70% | -47.17% | -64.23% |
| 2023 | 44.50% | 35.70% | 102.12% | 155.82% |
| 2024 | 56.06% | 55.68% | 67.25% | 118.37% |

The added 2018 bear market supports the downside-control interpretation, but the
2019 recovery exposes its opportunity cost. Across 2018-2019, state-20 still lost
9.56% cumulatively and state-40 lost 17.11%. The full run's longest underwater spells
were 754 and 825 calendar days respectively. A smaller drawdown can still require
years of patience. Daily close marks and opening-price fill proxies do not measure
intraday losses or executable market capacity.

State outperformed matched plain trend in six of seven annual returns for both
profiles, with some differences very small. This is descriptive, not a significance
test. Omitting any one calendar year from saved base daily returns leaves a positive
state-versus-trend Sharpe difference. Omitting 2023 reduces those differences to
about 0.010 and 0.008. Omitting 2020 reduces state Sharpes to 0.654 and 0.639.

Omitting both bear years, 2018 and 2022, reverses the Sharpe ordering versus
allocation: state-20/state-40 are 1.582/1.446 versus allocation's 1.710/1.712.
The useful trade-off depends on avoiding large losses, not universally capturing
more upside. These omissions are influence diagnostics only: no strategy was refit,
no confidence interval was estimated and omitted dates do not form a tradable path.

## Costs and delayed execution

| State profile and scenario | CAGR | Sharpe | Maximum drawdown |
|---|---:|---:|---:|
| 20, base 30 bps | 18.11% | 0.956 | -26.02% |
| 20, 75 bps stress | 15.24% | 0.828 | -27.87% |
| 20, extra-day delay | 16.74% | 0.895 | -25.52% |
| 40, base 30 bps | 30.29% | 0.921 | -39.34% |
| 40, 75 bps stress | 25.78% | 0.822 | -41.41% |
| 40, extra-day delay | 26.68% | 0.842 | -43.97% |

State retains a useful risk-adjusted profile under both perturbations. It does not
retain the highest raw CAGR: BTC exceeds state-40 in both stress and delay, and
allocation/blend can also have higher CAGR with larger drawdowns. Extra-day delay
reduces state-40 CAGR by 3.61 percentage points and deepens its drawdown to 43.97%.

Compared with matched plain trend, state-20/state-40 improve base CAGR by
0.81/1.80 percentage points. Frictionless improvements are only 0.32/0.99 points.
Base Sharpe gains are 0.034/0.025, falling to 0.012/0.005 without fees. State saves
1.41/2.14 times NAV of annual one-way turnover and 0.42/0.64 percentage points of
annual arithmetic execution drag. These arithmetic fee savings are not an exact
additive decomposition of compounded CAGR. State-40 also has higher mean risky
exposure (47.05% versus 45.45%) and realized volatility than plain trend-40.

The evidence supports a small execution/risk-allocation improvement over trend.
It does not identify a large independent prediction edge or a reason to resume ML
architecture search now.

## Candidate freeze and next evidence

`market_review/candidate_freeze.json` records both candidate names, the original
experiment registry, source hashes and the current evidence boundary. Preserve the
weekly state decision, two-thirds/1.25 thresholds, 60-day covariance with 10%
diagonal shrinkage, both risk settings, 2% band and all four execution scenarios.
Keep exact-execution policies as diagnostics and retain all matched comparators.
This records a development selection; it does not make that selection independent.

The next evaluation should use fixed rules on 2025 onward, with the common BTC/ETH
end date and prior-access classification fixed before calculating results. Check
local file coverage and provenance first; no data download is required by this
proposal. Specify start inventory, warm-up, calendar alignment and terminal handling
before execution so a period boundary cannot silently change the strategy.

**2025 is reserved within this fresh exercise, but is not globally untouched.**
Only prior period-usage metadata was inspected for this determination:

- [`ML_LAB_EXPERIMENT_002_RESULTS.md`](ML_LAB_EXPERIMENT_002_RESULTS.md) identifies
  BTC and ETH research data spanning 2018-2025.
- [`CAMPAIGN_50_HYPOTHESIS_FAMILY_SELECTION.md`](CAMPAIGN_50_HYPOTHESIS_FAMILY_SELECTION.md)
  records earlier BTC/ETH allocation research spanning 2019-2025.
- [`CORE_V1_PARAMETER_SENSITIVITY_RESULT.md`](CORE_V1_PARAMETER_SENSITIVITY_RESULT.md)
  identifies a 2020-2025 walk-forward evaluation.
- [`CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md`](CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md)
  mentions a partial 2026 BTC file. Its presence does not establish whether 2026
  strategy outcomes were inspected; that access status remains unresolved.

Consequently call the proposed step **locked historical forward validation**, not
a pristine final OOS test. This does not invalidate its usefulness. Preserve year
separation and disclose prior access; genuinely new observations after the freeze
would provide cleaner prospective evidence. Earlier strategy performance and old
charter thresholds were not used to select this experiment's rules or decision.

After fixing that evaluation protocol, specify uncertainty analysis separately.
A paired block-resampling design should use the same sampled calendar blocks for
all compared strategies; any price-path simulation must also preserve joint BTC/ETH
dependence and regenerate causal trading decisions. Saved-return resampling answers
a narrower conditional question than a new price-path backtest. Stationary bootstrap
theory addresses weakly dependent stationary observations, not arbitrary regime
change ([Politis and Romano, 1994](https://www3.stat.sinica.edu.tw/statistica/j4n2/j4n25/j4n25.htm)).
Block lengths, endpoints, cost handling and comparisons must be set before viewing
simulation outcomes. Resampled paths do not create new independent market cycles.

No historical forward or simulation result is claimed in this record. Core, runtime,
paper/live parameters and capital remain unchanged.
