# ML development lab — first diagnostic

2026-09-10. Status: DEVELOPMENT_DIAGNOSTIC_ONLY. No economic or confirmation
verdict. The fixed ETF crash-probability screen remains closed negative.

## Implemented and run

Executable module: `research.ml_development.run`. Eight candidates: two ridge,
two histogram GBM, two summary-input MLP neural networks, two ordered-window
MLPs. Two inner validation years select settings for each of seven outer years.
Every outer candidate remains visible. 168 corrected comparison fits plus 18
selected-candidate training-size/seed diagnostics. Inputs are the already supplied
SPY/QQQ/GLD testbed, not an asserted broad institutional universe.

A separate initial 168-fit attempt is INVALID: inner validation outcomes could
cross the first outer signal at New Year. The correction purges those outcomes
and has a canary test demonstrating the old crossing. All initial artifacts and
executed source/spec are preserved in the review ZIP. Total real fits this session:
354 = 168 invalid + 168 corrected + 18 diagnostics. No invalid score is used below.

33 tests passed, including prior input/accounting/packaging tests. Cached forecast
metrics reproduce byte-for-byte without refitting. This does not claim that every
trained model was independently refit/replayed. Reserved 2025 was not used.

## Findings

364 weekly development dates; 1,092 ETF forecast rows. Target is five-session
open-to-open simple return. Previously inspected 2018–2024 data remain development
history; chronological separation does not erase design contamination.

| Model | Full MSE skill versus zero-return forecast |
|---|---:|
| Past ETF mean | +0.98% |
| Ridge alpha 100 | +0.57% |
| Ridge alpha 1 | +0.39% |
| Inner-selected procedure | -0.53% |
| GBM depth 2 | -2.22% |
| GBM depth 3 | -3.50% |
| Summary MLP 16 | -2.97% |
| Summary MLP 32/16 | -23.68% |
| Ordered-window MLP 16 | -17.39% |
| Ordered-window MLP 32/16 | -31.42% |

Positive values indicate lower prediction squared error, not positive investment
returns. The historical-mean baseline outperforms the selected procedure on pooled
MSE. No candidate selection is changed using this full-period table.

The inner procedure selects GBM2 for 2018, ridge100 for 2019–2022, MLP16 for
2023, ridge100 for 2024. The larger summary network has pooled prediction/target
correlation about 0.111 while worsening MSE. Ranking association and well-calibrated
return levels are different. Neither metric by itself establishes an allocation edge.

Training-error gaps expose a useful diagnostic: ordered-window MLP32's mean outer
training MSE is about .000203 versus .000869 validation MSE. Ridge100 is about
.000478 versus .000657. These gaps are consistent with poor generalization, but
period/distribution changes also affect the comparison; do not attribute causally
all of the gap to model capacity.

All 84 neural comparison fits reached the declared 150-iteration cap. Their
optimization warnings are retained. Consequently this run is NOT a settled
architecture comparison and does not close neural research. The next neural
revision needs recorded loss trajectories, optimization diagnostics and
chronological early stopping inside development, with a recorded bounded budget.
Do not use random early-stopping splits or optimize against outer scores.

The 18 supplemental fits do not change the selections. Recent-25% and recent-50%
training subsets change both sample size and recency: they are sensitivity checks,
not clean causal learning curves. Ridge seed repeats were skipped as inapplicable.
The selected 2023 MLP's two other seeds have MSE approximately .000467 and .000462;
convergence warnings persist. No best-seed cherry-picking or portfolio conclusion.

## Next concrete dependency

The inventory contains full local IWM, EFA, EEM, IEF and TLT daily files. Upload
those five files with any accompanying manifests before selecting a broader
research universe. They add candidate small-cap, international and Treasury
observations; they do not magically create independent samples. No new source
hunt or subscription is needed. Missing manifests for four files and TLT's
unadjusted declaration require source/adjustment inspection before modeling.
Do not silently mix their opens/closes with the adjusted testbed.

`PACK_ML_BREADTH_INPUTS.ps1` only compresses those existing named files, adding
manifests when present. It performs no Git checkout, download or model run and is
safe to use while the original repository has an unfinished merge.

Next development revision will record the neural optimization protocol and the
supported universe after that inspection. The prediction layer, risk layer and
portfolio decision remain separate; no simple probability-to-exposure shortcut.
An actual allocation comparison still needs return/risk forecasts, cash returns,
turnover and identical baseline portfolio construction. That module is not yet
implemented or represented as completed by this diagnostic.

## Reproduction

From the new branch checkout, pointing at the existing three adjusted CSVs and
manifests, use fresh output directories:

```powershell
uv run --locked --python 3.12 python -m research.ml_development.run --input-root data --output-dir artifacts/ml_development_reproduction
uv run --locked --python 3.12 python -m research.ml_development.diagnostics --input-root data --original artifacts/ml_development_reproduction --output-dir artifacts/ml_development_sensitivity_reproduction
```

These commands refit models. No operator rerun is needed now. Share the five
additional existing input files using the packaging block instead.
