# ML Lab Experiment 007 — Training Memory Adaptivity — Results

## Status

**EXPLORATORY / NON-CONFIRMATORY.**

This result has no Core, runtime, portfolio, order, exposure, NAV, paper/live, or capital implication. Campaign #50's reserved 2025 holdout remained untouched.

## Question

After Experiment 006 diagnosed a post-2021 relationship shift and expanding-window model brittleness, does bounded training memory repair the deterioration without changing features, target, model families, or hyperparameters?

Compared memory schemes:

- expanding
- trailing 5 years
- trailing 3 years

Models remained exactly:

- Ridge: `StandardScaler + Ridge(alpha=10.0)`
- GBM: `GradientBoostingRegressor(n_estimators=200,max_depth=2,learning_rate=0.04,random_state=42)`

## Core result

Shorter memory materially repaired the post-2021 deterioration for both model families.

### Post-2022–2024 mean rank IC

| Memory | GBM | Ridge | GBM − Ridge |
|---|---:|---:|---:|
| Expanding | -0.0019 | 0.0300 | -0.0319 |
| Trailing 5y | 0.0157 | 0.0206 | -0.0049 |
| Trailing 3y | 0.0479 | 0.0531 | -0.0052 |

Relative to expanding memory, post-2021 GBM mean IC improved by:

- trailing 5y: **+0.0176**
- trailing 3y: **+0.0498**

Ridge also benefited:

- trailing 5y: **-0.0094** mean IC vs expanding, but with stronger tail spread
- trailing 3y: **+0.0231** mean IC vs expanding

The shorter-memory repair therefore supports the Experiment 006 diagnosis that stale historical relationships hurt expanding models, but it does not establish a durable nonlinear advantage because Ridge adapted too.

## Tail behavior

Post-2021 GBM minus Ridge top-minus-bottom raw-target spread:

- expanding: **-0.0164**
- trailing 5y: **+0.0383**
- trailing 3y: **+0.0235**

This is the strongest remaining ML-specific clue: shorter-memory GBMs separate the tails better than their Ridge counterparts even though average rank IC remains slightly lower.

## Cost of adaptivity

Shorter memory reduced the historical GBM advantage.

Pre-2012–2021 GBM mean IC:

- expanding: **0.1004**
- trailing 5y: **0.0860**
- trailing 3y: **0.0733**

Pre-period Ridge was much more stable:

- expanding: **0.0737**
- trailing 5y: **0.0764**
- trailing 3y: **0.0744**

Thus the 3-year window adapts most aggressively but discards substantial historical GBM signal.

## Feature-importance response

Shorter memory reduced GBM concentration in the old long-horizon volatility/trend geometry and distributed importance more broadly across recent-return, drawdown, SMA-distance, and volatility features.

For example, mean GBM `vol_60d_xrank` importance fell from about 28.6% expanding to 22.5% at 5y and 19.6% at 3y, while several medium/short-horizon state variables gained weight.

This is directionally consistent with faster adaptation rather than a simple performance coincidence.

## Interpretation

Experiment 007 is a **partial success**:

1. Experiment 006's stale-memory diagnosis is supported.
2. Bounded recency materially repairs GBM after the 2021 structural break.
3. The same adaptivity also helps Ridge, so average cross-sectional ranking does not show a persistent GBM-over-Ridge edge.
4. GBM's surviving incremental clue is concentrated in tail separation rather than average IC.
5. Further tuning of memory length would become post-hoc optimization and is not justified.

## Next diagnostic

The next justified step is a no-refit audit of the saved Experiment 007 predictions:

> Does GBM add information specifically when its top/bottom selections disagree with Ridge?

That audit should distinguish broad rank reshuffling from genuine nonlinear tail selection, with no model, target, feature, memory, or holdout changes.
