# ML Lab Experiment 011 — Results and closure

**Recorded:** 2026-09-04

**Disposition:** CLOSED — EXPLORATORY_TRANSFER_FAILURE

**Evidence status:** EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY

## Question and outcome

Annual models trained only on the original 14 U.S. ETFs were applied unchanged to
the frozen 14-country ETF universe. The macro-GBM increment did not transfer:
adding macro inputs reduced destination mean rank IC and top-minus-bottom target
spread under both memory schemes in both calendar periods.

This closes the frozen transfer experiment negatively. Experiments 009–010 retain
their original U.S. results, but their general-mechanism interpretation is weakened.
The results do not establish why transfer failed or that all international
predictability is absent.

## Evidence and execution integrity

- Design: [frozen Experiment 011 specification](ML_LAB_EXPERIMENT_011_CROSS_UNIVERSE_TRANSFER.md).
- Exact report snapshot: [Experiment 011 report](evidence/ML_LAB_EXPERIMENT_011_REPORT.json).
- Report SHA-256: `2a02d5bd6cd6af4ec10667960e3871647bf4ba23539500f1f381164396b85d1b`.
- Local output directory: `artifacts/ml_lab_experiment_011/`.
- Runner commit: `e512ee7ef1ec2535f59f6dec38a3069fc6b9eaf3`.
- Executed from the repository root on Windows using
  `uv run python scripts/run_ml_lab_experiment_011.py`; exit code 0.
- All 144 source-model parity checks passed; maximum absolute prediction
  difference from saved Experiment 009 predictions was `5.440092820663267e-15`,
  below the unchanged `1e-10` tolerance.
- All eight CSV outputs and the JSON report were produced.
- No destination fitting, tuning, target change, or 2025 holdout use occurred.

The preceding integration repairs restored direct-script imports, the macro
timestamp index expected by Experiment 009, and explicit destination-universe
selection in the shared panel builder. Its default U.S. output was checked against
the pre-patch implementation and matched exactly. Five regression tests passed
in both the isolated environment and the operator's Python environment, including
two complete synthetic transfer runs with identical replay outputs in each.
These checks support execution integrity; they are not statistical validation.

The report snapshot preserves destination input hashes and the result tables.
The companion [Experiment 012 input manifest](evidence/ML_LAB_EXPERIMENT_012_INPUT_MANIFEST.json)
identifies the unchanged U.S. source files and Experiment 009 reference artifacts
available after this run. Full CSV outputs remain local; they are not embedded in
this documentation commit.

## Coverage and metric meaning

Transfer test years were 2007–2024. Each model/memory combination was evaluated on
746 anchors in 2007–2021 and 144 anchors in 2022–2024: 890 evaluated anchors total.
The broader destination panel contained 977 eligible feature/target anchors before
training-support and annual-transfer eligibility requirements.

Rank IC is the cross-sectional Spearman correlation between scores and the frozen
20-session, volatility-adjusted forward-outcome ranks. Positive is the intended
direction. The top-minus-bottom spread is in volatility-adjusted target units,
not portfolio return, percentage return, Sharpe, or cost-adjusted P&L. Anchors are
five sessions apart with 20-session outcomes, so they are not independent samples.

## Primary transfer comparison

Macro GBM minus price GBM, on matched model/memory/period observations:

| Period | Memory | U.S. IC increment | Destination IC increment | Destination spread increment |
|---|---|---:|---:|---:|
| 2007–2021 | Expanding | +0.011043 | -0.011837 | -0.010348 |
| 2007–2021 | Trailing 3y | +0.020701 | -0.008822 | -0.018087 |
| 2022–2024 | Expanding | +0.020647 | -0.033028 | -0.061130 |
| 2022–2024 | Trailing 3y | -0.008457 | -0.036101 | -0.066328 |

Three positive U.S. increments reversed sign in the destination. In the fourth
cell, macro augmentation already hurt the U.S. model and hurt the destination
model more in IC terms. No memory/period cell preserved a positive macro-GBM
increment in the destination.

The reported trailing-3y 2022–2024 IC retention ratio of about +4.27 must not be
read as successful retention: it divides a negative destination increment by a
negative source increment. Absolute signs and paired differences govern the
interpretation, not the ratio's positive sign.

## Absolute destination ranking performance

| Model | Expanding, 2007–2021 | Trailing 3y, 2007–2021 | Expanding, 2022–2024 | Trailing 3y, 2022–2024 |
|---|---:|---:|---:|---:|
| Price Ridge | -0.004405 | -0.006950 | -0.040566 | -0.042504 |
| Price GBM | -0.008070 | -0.010571 | -0.022420 | -0.052152 |
| Macro Ridge | +0.001885 | -0.000231 | -0.074006 | -0.031655 |
| Macro GBM | -0.019907 | -0.019392 | -0.055447 | -0.088253 |

Values are mean rank IC. Fifteen of sixteen cells were negative; the remaining
macro-Ridge cell was close to zero. All sixteen mean top-minus-bottom target
spreads were negative. In particular, none of the eight model/memory combinations
had positive average IC or spread during 2022–2024.

Macro Ridge sometimes improved on price Ridge, including trailing-3y 2022–2024,
but its absolute IC and spread in that period remained negative. This is a
relative improvement, not evidence of successful positive transfer.

## Year and asset context

The annual results include positive years; this was not failure in every year.
For example, expanding macro GBM achieved +0.176947 IC in 2024, versus +0.179585
for price GBM. The positive 2024 level therefore did not supply a macro IC
advantage. It did not outweigh the negative aggregate 2022–2024 result.

Positive centered-rank-product contributions were also concentrated. Depending on
memory and period, only 4–7 of 14 countries had positive contributions; the top
three accounted for approximately 75.8%–91.6% of the positive contributions.
This is a descriptive attribution of the positive portion, not a decomposition
that turns the negative total transfer result into a positive one.

## Interpretation and closure

The defensible statement is: the frozen U.S.-trained model and representation
failed to demonstrate useful unchanged transfer to this country-ETF cross-section.
The experiment supplies no formal dependence-adjusted confidence interval or
significance test, so closure is an exploratory research disposition, not a
confirmed universal null or proof that the score should be traded in reverse.

Per the frozen design, this failure will not be rescued by changing destination
members, fitting on destination rows, changing features, choosing a winning year,
or tuning the GBM. No Core/runtime/threshold/order/NAV/exposure/portfolio/paper/live/
capital change is authorized.

The remaining bounded question is whether the original U.S. pattern can be
represented more simply. [Experiment 012](ML_LAB_EXPERIMENT_012_COMPACT_MACRO_INTERACTIONS.md)
specifies that separate exploratory test. It does not reopen 011, validate the
U.S. finding, or supersede Campaign #58's governed conclusions.
