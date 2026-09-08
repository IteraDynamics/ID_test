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
