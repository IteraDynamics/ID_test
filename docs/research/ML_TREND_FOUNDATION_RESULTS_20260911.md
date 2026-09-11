# Diversified trend foundation — completed baseline

**Decision: continue research with this fixed baseline.** It earns a single,
controlled ML risk-forecast comparison. It has not established independent OOS
success or deployment eligibility, and it is not an ML strategy yet.

## Experiment actually run

Twelve risky ETFs plus BIL, grouped into equities, rates, gold, oil and
agriculture. Each group has a 15% capital budget, inverse-volatility weights
within group, and equal-weighted 63/126/252-session trend votes against BIL.
Inactive allocations remain in BIL. A 10% estimated portfolio-volatility ceiling
can scale down exposure but cannot increase it or introduce leverage. Monthly
close signals fill next open, with paid initial and terminal transactions.

83 signal dates; primary ledger 2018-02-01 through 2024-12-31. Four policies and
five fixed cost/delay scenarios,20 ledgers. Zero model fits, parameter searches,
or 2025 observations. Data are exactly the earlier nine identified inputs plus
USO/CORN/SOYB/WEAT from the uploaded manifest-bearing archives. This is a
long-or-cash fund implementation, not a long/short futures replication.

## Net results at 10 bps per dollar bought or sold

| Policy | CAGR | Annual CE | Realized annual volatility | Maximum drawdown | Average risky exposure |
|---|---:|---:|---:|---:|---:|
| Fixed trend | 5.49% | 5.05% | 5.37% | −5.94% | 39.81% |
| Matched static group allocation | 3.76% | 2.95% | 8.62% | −19.66% | 72.81% |
| No-change initial allocation | 3.55% | 2.89% | 7.73% | −15.11% | 75.63% |
| BIL | 2.20% | 2.18% | 0.25% | −0.21% | 0.00% |

CE is annual mean minus gamma/2 times annual variance, with gamma 3. It is a
risk-adjusted descriptive statistic, not a guaranteed return. Relative to
matched static, trend gains 1.72 percentage points of CAGR and 2.10 points of CE;
maximum drawdown is 13.73 points shallower. Worst 21-session return is−5.80%,
versus−16.29% for static. Calendar periods and transaction assumptions match.

Trend's annualized return is modest in absolute terms. Its observed value is
its combination of return and substantially reduced loss severity. No leverage
increase was tested to make the return number more appealing.

## Costs, timing and exposure attribution

| Trend scenario | CAGR | Annual CE | Maximum drawdown |
|---|---:|---:|---:|
| Zero explicit trading costs | 5.74% | 5.30% | −5.93% |
|5 bps per dollar traded | 5.62% | 5.18% | −5.93% |
|10 bps primary | 5.49% | 5.05% | −5.94% |
|25 bps stress | 5.10% | 4.69% | −5.97% |
| One additional session delay,10 bps | 5.34% | 4.92% | −6.11% |

Signal targets are unchanged across scenarios; costs are not retuned gates.
Cumulative one-way turnover is 16.88, calculated by summing each day’s traded
notional divided by that day’s pretrade NAV, approximately 2.44 per year. This turnover
includes BIL and terminal trades; it is not a trade count. The delay scenario
holds settlement cash until its first fill and shares the primary terminal date.

An ex-post constant blend of static and BIL matches trend's average risky
exposure:54.68% static,45.32% BIL. It has 3.15% CAGR,2.88% CE and−10.99% drawdown.
Trend's advantage therefore cannot be explained simply by reducing average
static exposure. This blend uses the observed sample exposure and combines
component returns; it is explicitly a noninvestable attribution diagnostic,
not an independently selected or exactly executed benchmark.

## Dependence on periods and markets

Annual CE by policy:

| Year | Trend | Matched static |
|---|---:|---:|
|2018, beginning February | −1.82% | −8.08% |
|2019 | 5.61% | 12.30% |
|2020 | 7.30% | −5.35% |
|2021 | 10.04% | 11.76% |
|2022 | 5.28% | −0.04% |
|2023 | 2.29% | 3.61% |
|2024 | 6.04% | 5.53% |

Trend beats static in 4/7 annual CE comparisons. Excluding 2020, CE is 4.67% versus
4.37%: the advantage remains positive but shrinks to 0.31 points annually. The
large 2020 contribution matters. For a defensive trend hypothesis, dependence on
stress periods is not automatically disqualifying; this limited crisis sample
also does not establish reliable future crisis protection. Ex 2020 statistics
are pooled moments, not a continuous investment path.

Net terminal gain is 44.60 cents per initial dollar. Exact dollar P&L attribution
(including each asset's explicit trading fees) is:

| Group | Net gain per initial dollar |
|---|---:|
| Equities | 0.05934 |
| Rates | 0.00144 |
| Gold | 0.07403 |
| Energy | 0.13384 |
| Agriculture | 0.05873 |
| BIL | 0.11863 |

These sum to terminal wealth minus initial wealth; they are not standalone
asset CAGRs. Energy and cash account for a substantial share. Five market groups
and 83 monthly decisions are not 1,000 independent opportunities.

## Verification and evidence boundary

Four synthetic mechanics tests passed: relative trend signals and group budgets,
future-price independence, risk limits, and self-financing entry/delay/exit costs.
An independent verifier checked all four recorded output hashes,13-asset targets,
all 20 ledger calendars and NAV paths, per-asset P&L reconciliation, cost ordering,
CE/CAGR/drawdown calculations, and complete terminal liquidation. Maximum NAV
reconstruction discrepancy was 2.14e-14; metric discrepancies were zero at the
recorded precision. These tests verify mechanics, not market profitability.

This specification was fixed before these results but drafted and executed in
one session as exploratory research. It is not a formally preregistered frozen
campaign. The histories have been inspected in earlier research. Causal
signals and execution are present; a fresh research holdout is not. ETFs were
selected from available supplied data, so universe selection is another limit.
Vendor adjusted-price provenance is recorded, not certified by hash equality.
Commodity fund structure, especially energy exposure, differs from direct
futures. No new subscriptions, live routing, or Core changes were made.

## Next job

Keep this entire signal and execution specification unchanged. Test whether
one pooled ML next-month variance forecast improves on simple price-based risk
forecasts under the same portfolio rules. Evaluate forecast error and net
portfolio impact separately. The baseline survives if ML adds nothing; do not
retune its horizons, group budgets or exposure to rescue a model. Validate
actual month-to-month label boundaries and training maturity before fitting.

A genuine final OOS test requires checking data-use history and quarantining a
qualifying period before any results, or freezing for prospective paper
observation. Do not relabel previously inspected 2025 as untouched. Brokerage
eligibility, actual fills and live risk controls remain separate future gates.

Implementation: `research/ml_development/trend_foundation.py`.
Specification: `ML_TREND_FOUNDATION_SPEC_20260911.md`.
Small evidence: `evidence/ml_trend_foundation_20260911/`.
Complete local outputs: `artifacts/ml_trend_foundation_20260911/`.

Reproduction from repository root, replacing the path placeholders:

```powershell
uv run --locked --python 3.12 python -m unittest discover -s tests -p test_trend_foundation.py -v
uv run --locked --python 3.12 python -m research.ml_development.trend_foundation --etf-root <original-nine-input-folder> --energy-zip <energy-package.zip> --crop-zip <crop-package.zip> --output-dir <new-output-folder>
uv run --locked --python 3.12 python scripts/research_probes/verify_trend_foundation_20260911.py --results <new-output-folder>
```

No user-side run is needed to review this completed baseline. Actual environment,
code, source, specification and artifact hashes are recorded in the report.
