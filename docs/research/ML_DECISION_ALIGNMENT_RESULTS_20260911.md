# Corrected ETF decision experiment — results

**Decision: close this daily-summary, five-session ETF design as an alpha candidate.**
The decision-layer correction materially improves portfolio behavior, and calibrated
GBM shows a useful but fragile incremental economic result. It does not pass the
fixed consistency criteria. This rejects this particular design for advancement;
it does not establish that ETF prediction or ML generally cannot work.

## What the correction established

All inputs match the original nine source hashes. Signals occur every five
trading sessions; all 2,808 targets span the corresponding next-open to sixth-open
interval. The 351 decisions begin 2018-01-04 and terminate at the final label's
2024-12-27 open. The models and features are unchanged. Calibration is refitted
on the corrected inner grid, so this is an aligned rerun, not reuse of the old
calendar-week predictions. No 2025 data were used.

The optimizer compares forecast reward, five-session covariance risk, and costs
of changing current holdings. A retained feasible position can remain untouched.
Orders are selected at the signal close and executed at the next open. The old
four-leg gate is retained as an ablation on this same grid.

| Policy,10 bps per dollar bought/sold | Net CAGR | Annual CE | Annual realized volatility | Maximum drawdown |
|---|---:|---:|---:|---:|
| Corrected calibrated GBM | 7.10% | 5.41% | 12.05% | −21.01% |
| Corrected historical mean | 6.16% | 4.62% | 11.68% | −22.18% |
| Corrected static-feature GBM | 5.58% | 4.14% | 11.38% | −21.39% |
| Corrected raw GBM | 6.25% | 4.59% | 12.19% | −21.01% |
| Corrected calibrated Ridge | 4.74% | 3.20% | 11.95% | −23.04% |
| Periodic risk-limited equal allocation | 5.51% | 4.47% | 9.47% | −19.63% |
| No-change allocation | 6.57% | 5.36% | 10.04% | −21.59% |
| All-BIL | 2.19% | 2.16% | 0.25% | −0.21% |
| Old gate, calibrated GBM, aligned grid | 1.86% | 1.56% | 5.33% | −13.00% |

CE is 252 times mean daily return minus 1.5 times 252 times sample daily variance.
It is a descriptive risk-adjusted measure with gamma 3, not a return guarantee.

The GBM's corrected CE is 0.79 percentage points above optimized historical mean
and 1.27 points above the static-feature control. Excluding 2020, its mean-baseline
CE advantage is 0.93 points. Those are real observed improvements in this run.
However, its all-period CE advantage over no-change is only 0.047 percentage
points annually, approximately 4.7 bps. It beats optimized historical mean in only
2022 and 2023, ties 2018–2020, and trails in 2021 and 2024.

The large improvement over the old gate must not be attributed entirely to ML.
Average risky exposure rises from 10.9% to 73.2% for calibrated GBM; the same
construction correction raises historical mean exposure from 7.2% to 73.7% and its
CE from 1.72% to 4.62%. The old gate suppressed investing, including baseline
investing. Correcting it improves the experiment's validity, not automatically
its evidence for changing features.

## Forecast and cost checks

| Forecast | Pooled MSE skill versus historical mean | Skill excluding 2020 |
|---|---:|---:|
| Raw Ridge | +0.495% | −1.246% |
| Calibrated Ridge | −0.531% | −0.811% |
| Raw GBM | +0.450% | −1.098% |
| Calibrated GBM | −0.207% | −0.316% |
| Calibrated static-feature GBM | +0.206% | +0.314% |

Positive skill means lower squared error. Raw predictive gains remain dependent
on 2020. Calibration sets both residual signals to zero in 2018–2020; their
positive raw 2020 skill was not selected by the eligible prior calibration data.
The calibrated GBM's small pooled MSE loss does not logically preclude useful
portfolio decisions, because weights emphasize only some forecasts. Its economic
advantage is therefore worth recording separately, even though it fails the
prewritten combined criterion.

| Annual CE | Calibrated GBM optimizer | Historical-mean optimizer | No-change |
|---|---:|---:|---:|
|10 bps, adaptive decisions | 5.41% | 4.62% | 5.36% |
|25 bps, adaptive decisions | 2.86% | 3.32% | 5.32% |
| Same 10 bps order paths, zero fees | 5.88% | 4.70% | 5.39% |
| Same 10 bps order paths,25 bps fees | 4.69% | 4.49% | 5.32% |

The 25 bps adaptive scenario changes decisions as well as fees. The matched-order
replay separates these: calibrated GBM still beats optimized mean by 0.20 points
of CE on the frozen path, but trails no-change. The much larger adaptive decline
shows sensitivity to the one-period cost objective and resulting path, beyond
the direct deduction of fees. It is not a reason to tune the cost assumption
until the model passes.

## Verification and limitations

Seven synthetic mechanics tests passed: marginal no-trade behavior, known
allocation optimum, covariance/risk units, holiday/session timing, accounting,
next-open independence, future-label exclusion, and fee replay are covered
across those seven tests. Synthetic data demonstrate correctness, not returns.

Independent reconciliation verified eight result-file hashes, all 42 fitted
training boundaries and inner calibration maturity, all 2,808 realized targets,
all 68 ledgers, forecast MSE and CE. Maximum NAV reconstruction difference was
2.49e-14; maximum metric difference was below 1e-16. The highest optimized
signal-time predicted volatility was 10.00000005%, within solver tolerance.

The 10% forecast risk ceiling is not a realized-volatility guarantee: the GBM
realized 12.05%. Covariance estimation, overnight movements and subsequent drift
matter. The no-change control is initially risk-limited equal 75/BIL 25, then
holds shares; its risky exposure can drift above 75% (average 77.9%). Thus it is
a no-action reference, not an exactly constraint-matched optimized portfolio.
The historical-mean optimizer is the matched primary comparison.

This remains repeatedly inspected development data. There is no independent
confirmation, significance claim, estimated power or production authorization.
Historical adjusted prices and next-open cost approximations remain limitations.

Execution needed numerical recovery: an initial near-boundary SLSQP status
failure stopped the run. A complete 2018–2023 checkpoint was retained; the six
2024 fits were recovered unchanged. The final lineage contains 42 fits; total
executed fits were 48 including the unretained six. No extra candidate was
selected. Solver scaling/tolerance and the recovery are recorded in
`evidence/ml_decision_alignment_20260911/validation.json`.

## Disposition and reproduction

Retain the corrected accounting and holdings-aware decision layer for future
research. Archive this exact ETF alpha design; do not advance it to trading,
launch a neural-network search, or change its pass criteria after seeing these
results. The actionable finding is that the old construction understated
portfolio economics, while this corrected experiment still does not establish
sufficiently robust incremental ML value.

Specification: `ML_DECISION_ALIGNMENT_SPEC_20260911.md`.
Small evidence: `evidence/ml_decision_alignment_20260911/`.
Full local ledgers/forecasts: `artifacts/ml_decision_alignment_20260911_final/`.
Original experiment artifacts remain unchanged.

From repository root, using the original nine CSV/manifest pairs:

```powershell
uv run --locked --python 3.12 python -m unittest discover -s tests -p test_decision_alignment.py -v
uv run --locked --python 3.12 python -m research.ml_development.decision_alignment --input-root <nine-input-directory> --output-dir <new-output-directory>
uv run --locked --python 3.12 python scripts/research_probes/verify_decision_alignment_20260911.py --results <new-output-directory> --input-root <nine-input-directory>
```

The actual execution environment and every result hash are recorded in the
report. A different dependency environment need not reproduce bytes exactly.
No local run is required from the user to review this completed result.
