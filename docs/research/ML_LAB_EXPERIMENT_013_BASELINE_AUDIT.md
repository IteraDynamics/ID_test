# Experiment 013 — Price Ridge versus fixed simple rankings

**Specification date:** 2026-09-08. **Status:** IMPLEMENTED; real run pending.
**Boundary:** exploratory, discovery-contaminated, non-confirmatory.

The operator authorized proceeding from the post-012 evidence review. This is a
new no-refit diagnostic, not a reopening or modification of Experiment 012.

## Frozen question and inputs

Does saved price-only Ridge add chronological ranking information beyond fixed
low-volatility and momentum rankings on exactly the same observations?

Reuse all 17 files and exact hashes in the Experiment 012 input manifest. No new
acquisition or reference generation for the real run. Rebuild the existing panel
with its cutoff before features/targets, then require all Experiment 012 row,
target, fold and saved-anchor parity checks against all four Experiment 009 models.
Select only saved price_ridge for the diagnostic after that verification.
No estimator is fitted. Training slices are reconstructed solely for support parity.

Real support is exactly 902 anchors per memory, 2007–2024, including 147 anchors
in 2022–2024. Keep the original 14 ETFs and embargo. Trailing-3y is primary;
expanding is context. The reserved 2025 holdout is untouched.

## Scores, outcomes and ties

Fixed scores (higher means preferred):

- saved price_ridge score;
- negative vol_60d_xrank;
- positive ret_60d_xrank;
- positive ret_120d_xrank.

No sign, window, tail-size or composite search. Two outcomes: existing target_raw,
and its unscaled 20-common-session close-return numerator. Reconstruct the numerator
from the same cutoff-filtered prices and assert that dividing it by the original
volatility denominator recovers target_raw within absolute 1e-10, zero relative
tolerance. This additional outcome does not change the saved model's training target.

IC is Pearson correlation of average ranks (Spearman). Undefined IC or nonfinite
values fail execution. Sort tails by score ascending, then ticker ascending; bottom
four and top four, matching ceil(14/4). The explicit ticker tie-break makes the new
diagnostic invariant to input order. Saved-reference parity still uses the original
metric routine before diagnostic metrics are computed.

Emit paired Ridge-minus-each-baseline differences on identical anchors for each
outcome. Summaries include mean/median IC, positive IC fraction, mean/median spread,
and counts for all, pre-2022, 2022–2024 and every evaluated year.
Score agreement is per-anchor Spearman with Ridge. Each ETF's spread contribution
is outcome/4 for top, -outcome/4 for bottom, zero otherwise. Emit every ETF without
selecting favorable names. Selection persistence is retained names/4 versus the
previous evaluated anchor, across year boundaries, separately for each tail/model/
memory. Omit the first anchor rather than inventing a prior selection.
Persistence is not executed portfolio turnover, and close returns are not net P&L.

## Frozen descriptive disposition

For each memory and each of the three baselines, recurrent original-target lift
requires strictly positive paired mean IC and mean spread in BOTH pre/post periods,
and positive annual mean IC in strictly more than half of evaluated years.
Equality fails. These are descriptive rules, not significance or promotion gates.

- Any primary baseline comparison fails: NO_STABLE_PRIMARY_BASELINE_INCREMENT.
- All primary comparisons pass but any expanding comparison fails:
  MEMORY_DEPENDENT_BASELINE_INCREMENT.
- All comparisons in both memories pass: EXPLORATORY_BASELINE_INCREMENT_RECURRENT.

Report every component. The return-numerator diagnostic, concentration and persistence
remain visible and cannot override a failed primary result. A positive label only
justifies considering a separately specified research portfolio test; it does not
show profitability, causality or independent validation. No post-result tuning.

## Artifacts and publication

Exactly 11 CSVs, prefixed experiment_013_: predictions, reference_parity, fold_support,
anchor_metrics, paired_differences, selections, asset_contributions, score_agreement,
selection_persistence, model_summary, comparison_summary. Also experiment_013_report.json
with input/source hashes, environment, zero fits, boundary flags, summaries and
classification components. Verify inputs again before atomic new-directory publication;
refuse existing output directories. Failures produce no successful output directory.

Implementation: scripts/run_ml_lab_experiment_013.py. Shared Experiment 012 functions
are reused without changing them or their globals. The packaging boundary adds only
this named runner; existing containment remains active. Synthetic verification uses
generated references clearly isolated from real evidence and compares two complete runs.

## Local execution

From the separate review worktree after checking out the published 013 branch:

```powershell
git fetch origin research/experiment-013-baseline-audit-20260908
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git switch --detach FETCH_HEAD
if ($LASTEXITCODE -ne 0) { throw "Checkout failed" }
uv run --locked --python 3.12 python -m scripts.run_ml_lab_experiment_013 --input-root ..\ID_test --preflight-only
if ($LASTEXITCODE -ne 0) { throw "Frozen input verification failed" }
uv run --locked --python 3.12 python -m scripts.run_ml_lab_experiment_013 --input-root ..\ID_test --output-dir ..\ID_test\artifacts\ml_lab_experiment_013
if ($LASTEXITCODE -ne 0) { throw "Experiment 013 failed" }
```

The real input files are in the operator's original checkout and unavailable in the
assistant workspace. No remote real result is claimed. No merge, deployment, Core,
portfolio, capital or holdout action follows from this diagnostic.

---

## Execution, evidence review and closure — 2026-09-09

**Current disposition: CLOSED — NO_STABLE_PRIMARY_BASELINE_INCREMENT.**
This dated entry supersedes the historical "real run pending" status above.
The original specification text remains intact. The operator authorized the
research redesign after reviewing this result; no post-result retuning of 013
is proposed.

The operator completed the real run in the separate Windows review worktree at
`d0971a3fbc6f7412d13afe0704b6cd231cddbf12`, using Python 3.12.13. The supplied report
records 17 verified frozen inputs, 144 reference checks, zero fits, 902 anchors
per memory across 2007–2024, and no use of the reserved 2025 holdout.
This is operator-run evidence, not a real run performed in the assistant workspace.

| Primary trailing-3y comparator | Frozen rule passed | Positive annual IC increments |
| --- | --- | --- |
| Low 60d volatility | No | 8/18 |
| High 60d momentum | Yes | 14/18 |
| High 120d momentum | Yes | 13/18 |

Ridge-minus-low-volatility original-target mean IC/spread increments are
-0.034167/-0.029203 before 2022 and +0.036600/+0.122707 in 2022–2024.
The full-sample mean IC is 0.057673 for Ridge versus 0.080307 for low volatility.
The recent advantage cannot override the failed primary rule. Expanding also
fails against low volatility (5/18 positive annual IC increments).

The operator subsequently supplied two original CSVs. Independently recomputed
SHA-256 values match the corresponding report entries:

- score_agreement: `a1b2df1d57491938223d3b5e59348b10738312b870d7ae4e25152056e541d801`
  (7,216 rows);
- asset_contributions: `f6d4e88b6e36e8fbf767b401d6619e4105ea0a2d09d535fbd8f73bdf4e4eea77`
  (202,048 rows).

Summing all asset contributions per anchor and averaging over each reported
memory/model/outcome/period reconstructs all 336 spread summaries, with maximum
absolute difference 8.33e-17. Actual bytes of the other nine CSVs were not supplied;
there is no claim of a full 013 artifact replay or byte equality across two runs.

The run's specification hash `887053920a4e0c4c5e6c828c7a6882558135ae50fe9289e8d0d740ac3e3647ae`
matches the parent specification encoded with CRLF. Its LF repository bytes at
`d0971a3` hash to `7ffb04c6cb4a2f0c9204b31c65b94f60ac9d343474f3a04156f35cba85bbc041`.
This newline difference is explained without modifying the original run report.
This appended closure naturally changes the current document hash.

### Interpretation of the supplied diagnostics

Mean score rank correlation with low volatility is 0.4909 for trailing-3y Ridge
and 0.7120 for expanding Ridge. In 2022–2024 it is 0.4288 and 0.8867 respectively.
Primary annual correlations are 0.6960 (2022), 0.5782 (2023), and -0.0297 (2024).
There is substantial shared ranking structure, but no constant equivalence or
causal variance-explanation claim follows from these correlations.

The primary 2022–2024 Ridge-minus-low-volatility unscaled forward-return spread
is +0.9253 percentage points per average 20-session window. Contributions are
XLU +0.3431pp, IWM +0.2308pp, XLE +0.2118pp and MDY +0.1717pp, with other assets
netting to -0.0321pp. These four names supply 75.8% of positive contributions.
For XLE both models' contributions are negative; the increment reflects a less
negative Ridge contribution. IWM is near zero for Ridge versus negative for the
baseline. This is relative attribution, not four independently profitable trades.
These overlapping-window spreads are neither annualized nor cost-adjusted P&L.

Low volatility's full-sample IC is 0.080307 on the original normalized target
but 0.000631 on unscaled forward returns. This supports reviewing objective
alignment; it does not prove leakage, a software error, or that all ML is useless.

Computed evidence: [compact verification and summaries](evidence/ml_lab_013_closeout_20260909.json).
Next decision: [ML research redesign](ML_DECISION_REDESIGN_20260909.md).
End variations on this target/universe combination. All results remain exploratory
and discovery-contaminated. No Core, runtime, portfolio, paper/live or capital
change follows, and the reserved holdout remains untouched.
