# ML Lab Experiment 012 results — recorded 2026-09-08

**Disposition: CLOSED — NO_STABLE_PRIMARY_SIMPLIFICATION.**
**Evidence boundary: EXPLORATORY_NONCONFIRMATORY; discovery-contaminated.**

The fixed 22-feature compact macro Ridge failed the frozen primary stability
rule. Park this six-interaction simplification without searching subsets, changing
alpha, swapping primary memory or changing the target within Experiment 012.
The result does not disprove every possible simple or macro representation.

## Execution and evidence source

These results come from the operator's pasted local reports and successful
standalone artifact comparison. The raw real-data artifacts are held in the
operator's original checkout, not copied into this repository or independently
read in the assistant's execution workspace. This document is a result summary,
not a reconstructed full report snapshot.

| Run | Code commit | Python | Output directory under original checkout |
| --- | --- | --- | --- |
| Original (files dated 2026-09-04) | `e7c27040543723417fb4466638c53890a54c6adb` | 3.14.6 | `artifacts/ml_lab_experiment_012/` |
| Refactor replay (2026-09-08) | `233b1f4466b0d0b3898e2c05b34329aaa0b192f7` | 3.12.13 | `artifacts/ml_lab_experiment_012_refactor_233b1f4/` |

Both report NumPy 2.4.4, pandas 3.0.2, scikit-learn 1.9.0 and SciPy 1.17.1.
Both record manifest SHA-256
`cf7cb675392c76b9806b0fa9acb574b56b7f4cedecfcdd6f811f19d6ecd57bbb`.
All 17 frozen inputs verified; 144 reference checks passed with maximum rank-IC,
spread, target-rank and raw-target deltas of zero (tolerance `1e-10`).
The run fitted 36 candidate folds across 18 years (2007–2024) and two memories.
Each memory has 902 test anchors: 755 pre-2022 and 147 in 2022–2024.
Saved Experiment 009 comparators were not refitted.

The operator's separate comparison asserted matching 11-file inventories, read
every CSV, verified each recorded SHA-256, and asserted byte equality across the
two runs. Parsed reports were equal after removing only `code` and `environment`.
This establishes exact Experiment 012 output parity for these inputs and revisions.
It is not a claim of universal refactor equivalence or identical raw JSON reports.

## Primary trailing-three-year results

IC measures within-anchor ranking association; higher is better. Spread is the
top-minus-bottom raw volatility-adjusted target, not a trading return. Values below
are rounded from the reports; comparisons use the same anchor sets.

| Period | Compact IC | Price Ridge IC | IC increment | Compact spread | Price Ridge spread | Spread increment |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pre-2022 | 0.040542 | 0.058566 | -0.018024 | 0.047127 | 0.067078 | -0.019950 |
| 2022–2024 | 0.020857 | 0.053091 | -0.032234 | 0.019536 | 0.056485 | -0.036949 |
| All | 0.037333 | 0.057673 | -0.020340 | 0.042631 | 0.065351 | -0.022721 |

The candidate's own mean IC and spread were positive in both periods, but both
increments were negative in both periods. Only 7/18 annual mean IC increments
were positive; the rule requires strictly more than half. Primary stable lift
therefore failed. Full-sample macro GBM IC was 0.058178 and spread 0.065788;
the compact model did not match either metric.

## Fixed expanding comparison and interpretation

Expanding also failed stable lift: 5/18 positive annual IC lift years. Its
compact-minus-price-Ridge IC/spread increments were -0.030105/-0.052484 pre-2022
and +0.008462/+0.024754 in 2022–2024. The favorable later period does not replace
the primary-memory result. Expanding full-sample compact IC/spread were
0.032185/0.017735 versus macro GBM 0.067148/0.076745.

Effective slopes also varied over time. For example, trailing-memory annual mean
momentum slope changed from +0.101596 in 2021 to -0.237354 in 2022; annual mean
volatility slope changed from +0.292175 in 2019 to -0.163101 in 2020. These are
conditional fitted-score slopes, not causal effects or standalone strategy returns.

The classification follows the frozen descriptive rule, not a significance test.
Overlapping forward targets and discovery-based feature selection preclude a fresh
confirmation claim. Experiment 011's transfer failure remains closed; no destination
training or 2025 holdout use occurred. No portfolio or production implication follows.

## Next research boundary

Close this candidate and finish engineering review. Before specifying another
experiment, inspect the earlier price-only evidence and any existing turnover,
cost and portfolio tests to identify an unanswered question. No new model fit,
portfolio experiment or holdout opening is specified by this closure.
