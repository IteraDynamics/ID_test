# Trade Idea Radar / Core Allocator Research Findings and Failure Log

Branch: `research/trade-idea-radar`

This memo documents the research path, the results that survived validation, and the places where we kept striking out. The point is to preserve the lessons so future work does not repeat the same failure modes.

Research only. Nothing in this memo represents live-trading authorization.

---

## Executive Summary

The research split into two tracks:

1. **Tactical trade-idea sleeve research**
2. **Structural core allocator research**

The tactical sleeve produced useful, controlled results, but repeatedly compressed under stricter validation. It now looks like a possible satellite sleeve, not the flagship engine.

The structural allocator produced much stronger return profiles and appears to be the more promising path for the Itera Core engine. However, the current allocator variants still have underwhelming Sharpe/Calmar relative to the desired institutional-quality target. The next work should focus on regime-aware, risk-contribution-aware allocation using the existing Itera regime detector rather than brute-force tactical entries or HMM-style regime replacement.

Current high-level conclusion:

```text
Tactical entries can produce sleeves.
Structural exposure control is the likely core engine.
The missing piece is better risk selection, not more gross exposure reduction.
```

---

## Research Artifacts Added on This Branch

### Tactical Trade-Idea Research

Key scripts:

```text
scripts/run_trade_idea_cost_aware_universe_pruning.py
scripts/build_trade_idea_candidate_finalist_report.py
scripts/build_trade_idea_candidate_finalist_report_v2.py
scripts/run_trade_idea_finalist_walk_forward.py
scripts/run_trade_idea_stitched_oos_validation.py
```

Key artifact directories:

```text
artifacts/trade_idea_cost_aware_universe_pruning
artifacts/trade_idea_candidate_finalist_report_v2
artifacts/trade_idea_finalist_walk_forward
artifacts/trade_idea_stitched_oos_validation
```

### Core Allocator Research

Key scripts:

```text
research/core_allocator/README.md
scripts/run_core_allocator_policy_sweep.py
scripts/validate_core_allocator_policy_sweep.py
scripts/build_core_allocator_candidate_finalist_report.py
scripts/run_core_allocator_risk_constrained_sweep.py
scripts/run_core_allocator_risk_contribution_sweep.py
scripts/run_core_allocator_risk_contribution_sweep_fast.py
```

Key artifact directories:

```text
artifacts/core_allocator_policy_sweep
artifacts/core_allocator_validation
artifacts/core_allocator_validation_low_vol
artifacts/core_allocator_candidate_finalist_report
artifacts/core_allocator_risk_constrained_sweep_fast
artifacts/core_allocator_risk_contribution_sweep_compact
```

---

## Part I — Tactical Trade-Idea Sleeve Research

### Initial Candidate Finalists

The main tactical finalists were:

```text
primary_calmar
  looser_stop_12pct_max_new_3__crypto_plus_growth_plus_macro_liquid

secondary_return
  looser_stop_12pct_max_new_3__remove_splv

prior_current_core
  looser_stop_12pct_max_new_3__current_core

crypto_only_benchmark
  looser_stop_12pct_max_new_3__crypto_only
```

### Full-Period Cost-Adjusted Results

Under `asset_base`:

| Candidate | Trades | CAGR | Return | MaxDD | Sharpe | Calmar | Cost | Final Equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| primary_calmar | 404 | 19.10% | 185.17% | -11.90% | 1.211 | 1.604 | 16,780 | 285,169 |
| secondary_return | 486 | 19.58% | 192.19% | -12.73% | 1.189 | 1.538 | 17,460 | 292,191 |
| prior_current_core | 512 | 18.72% | 179.81% | -13.40% | 1.105 | 1.397 | 17,860 | 279,806 |
| crypto_only_benchmark | 91 | 14.38% | 123.80% | -11.30% | 1.136 | 1.273 | 13,650 | 223,805 |

Under `asset_conservative`:

| Candidate | CAGR | Return | MaxDD | Sharpe | Calmar | Final Equity |
|---|---:|---:|---:|---:|---:|---:|
| primary_calmar | 18.77% | 180.47% | -12.05% | 1.186 | 1.557 | 280,474 |
| secondary_return | 19.17% | 186.25% | -12.92% | 1.160 | 1.484 | 286,251 |
| prior_current_core | 18.27% | 173.49% | -13.79% | 1.074 | 1.325 | n/a |
| crypto_only_benchmark | 14.38% | 123.80% | -11.30% | 1.136 | 1.273 | 223,805 |

### Corrected Calendar-Year Returns

The first finalist report had a calendar-return calculation bug. The corrected report fixed period return math by using prior period-end equity as the next period's starting equity.

Corrected `primary_calmar` annual profile:

| Year | Return |
|---:|---:|
| 2020 | +68.93% |
| 2021 | +32.70% |
| 2022 | -8.47% |
| 2023 | +16.14% |
| 2024 | +15.86% |
| 2025 | +3.28% |

This made the profile more credible and less sensational. It showed that the candidate did not depend entirely on one year, but it also showed that the full-period headline was materially helped by the 2020–2021 cycle.

### Tactical Walk-Forward Result

Calmar-selected walk-forward:

```text
Window 1:
  Train: 2020–2021
  Test:  2022
  Selected: secondary_return
  OOS return: -9.73%

Window 2:
  Train: 2021–2022
  Test:  2023
  Selected: primary_calmar
  OOS return: +16.14%

Window 3:
  Train: 2022–2023
  Test:  2024
  Selected: primary_calmar
  OOS return: +15.86%
```

Aggregate:

```text
Avg OOS return:     +7.42%
Median OOS return: +15.86%
Worst OOS return:   -9.73%
Avg MaxDD:          -7.70%
Positive windows:   2/3
```

This was encouraging but not decisive. The strategy survived 2022 and recovered in 2023–2024, but the number of OOS windows was small.

### Stitched Tactical OOS Validation

The stitched OOS test answered:

```text
If we actually followed the walk-forward selector, what would the combined OOS equity curve look like?
```

Result under `asset_base`:

| Curve | CAGR | Return | MaxDD | Sharpe | Calmar | Final Equity |
|---|---:|---:|---:|---:|---:|---:|
| always_primary_calmar | 7.20% | 23.16% | -11.90% | 0.720 | 0.605 | 123,164 |
| stitched_walk_forward | 6.70% | 21.47% | -12.73% | 0.668 | 0.526 | 121,468 |

Conclusion:

```text
The finalist itself was stronger than the selector.
Dynamic switching did not help.
Always-primary beat the adaptive stitched version.
```

Under `asset_conservative`, the adaptive version slightly improved Calmar but gave up return. The difference was not strong enough to justify dynamic switching.

### Tactical Sleeve Conclusion

The tactical module moved from:

```text
interesting backtest candidate
```

to:

```text
credible tactical satellite candidate
```

But it did not become the flagship engine.

Best practical interpretation:

```text
primary_calmar is a possible Sleeve 2 satellite.
It should not be treated as the core fund engine.
```

### Where Tactical Research Struck Out

#### 1. Full-period results overstated the likely expectation

The full-period ~19% CAGR / ~1.6 Calmar result looked strong, but stricter stitched OOS reduced expectation to roughly:

```text
~7% OOS CAGR
~-12% OOS MaxDD
~0.6 Calmar
```

This is not bad, but it is not enough to be the core engine.

#### 2. Walk-forward selection did not add value

The adaptive selector did not beat the static primary candidate. It introduced complexity without improving the realized OOS equity curve.

#### 3. The tactical search space naturally produces sleeves

Most of the tactical research space was based on:

```text
entries/exits
breakouts
reclaims
compression
stop logic
universe pruning
cost filters
```

Those are alpha modules. They are not usually structural fund engines.

Lesson:

```text
Do not search for the flagship inside tactical entry modules.
Use tactical modules as satellites.
```

---

## Part II — Structural Core Allocator Research

### Why the Pivot Happened

After the tactical candidate compressed under validation, the research pivoted from:

```text
Find a better trade setup.
```

to:

```text
Build the flagship as a structural allocator.
```

Core allocator thesis:

```text
The fund engine should compound by deciding how much risk belongs in crypto, equities, defensive assets, and cash across regimes.
```

### Initial Core Allocator Policy Sweep

Universe:

```text
BTC-USD, ETH-USD, QQQ, SPY, TLT, GLD
```

Policies tested:

```text
static_balanced_core
static_crypto_growth
static_defensive_core
trend_gated_balanced_ma200
trend_gated_crypto_growth_ma200
trend_gated_balanced_ma120
vol_target_trend_12pct
vol_target_trend_18pct
vol_target_trend_25pct
relative_momentum_top2_6m
relative_momentum_top3_6m
relative_momentum_top2_12m
crypto_only_equal
risk_assets_equal
defensive_overlay_balanced
```

Top initial full-period results:

| Policy | CAGR | Return | MaxDD | Sharpe | Calmar | Vol | Final Equity |
|---|---:|---:|---:|---:|---:|---:|---:|
| trend_gated_balanced_ma200 | 37.14% | 810.84% | -40.00% | 1.007 | 0.928 | 24.72% | 910,839 |
| defensive_overlay_balanced | 36.93% | 801.35% | -40.00% | 1.002 | 0.923 | 24.74% | 901,354 |
| vol_target_trend_25pct | 32.03% | 598.41% | -37.35% | 0.980 | 0.858 | 22.10% | 698,413 |
| vol_target_trend_18pct | 26.35% | 413.42% | -34.31% | 0.957 | 0.768 | 18.74% | 513,416 |
| vol_target_trend_12pct | 19.35% | 244.70% | -25.98% | 0.971 | 0.745 | 13.52% | 344,696 |

Initial read:

```text
This was the first result that looked like a true core engine candidate rather than another tactical sleeve.
```

### Core Allocator Walk-Forward / Stitched OOS Validation

The first stitched OOS validation showed that dynamic policy selection failed badly.

Full policy universe selector:

```text
stitched_walk_forward:
  CAGR:   12.46%
  Return: 59.90%
  MaxDD: -73.85%
  Sharpe: 0.404
  Calmar: 0.169
```

Why it failed:

```text
Window 1: static_crypto_growth
Window 2: crypto_only_equal
Window 3: trend_gated_balanced_ma200
Window 4: vol_target_trend_25pct
```

The selector chose crypto-only into 2022, which wrecked the OOS curve.

Low-vol focused validation removed the most obviously dangerous choices but the selector still failed:

```text
stitched_walk_forward:
  CAGR:   23.11%
  Return: 129.57%
  MaxDD: -53.88%
  Sharpe: 0.660
  Calmar: 0.429
```

Why it still failed:

```text
Window 1: static_balanced_core
Window 2: static_balanced_core
Window 3: trend_gated_balanced_ma200
Window 4: vol_target_trend_25pct
```

The selector chose `static_balanced_core` into 2022 and absorbed a major drawdown.

Conclusion:

```text
Do not dynamically select allocator policies using trailing 2-year Calmar.
The selector is backward-looking and regime-late.
Static structural policy > unconstrained adaptive policy selector.
```

### Core Finalist Stack

The finalist report locked three fixed structural candidates:

```text
core_aggressive = trend_gated_balanced_ma200
core_balanced   = vol_target_trend_18pct
core_defensive  = vol_target_trend_12pct
```

Full-period finalists:

| Alias | Policy | CAGR | Return | MaxDD | Sharpe | Calmar | Vol | AvgExp | FinalEq |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| core_aggressive | trend_gated_balanced_ma200 | 37.14% | 810.84% | -40.00% | 1.007 | 0.928 | 24.72% | 0.91 | 910,839 |
| core_balanced | vol_target_trend_18pct | 26.35% | 413.42% | -34.31% | 0.957 | 0.768 | 18.74% | 0.74 | 513,416 |
| core_defensive | vol_target_trend_12pct | 19.35% | 244.70% | -25.98% | 0.971 | 0.745 | 13.52% | 0.55 | 344,696 |

Static OOS finalists:

| Alias | Policy | CAGR | Return | MaxDD | Sharpe | Calmar | Worst Day | FinalEq |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| core_aggressive | trend_gated_balanced_ma200 | 30.28% | 187.83% | -35.87% | 0.904 | 0.844 | -8.88% | 287,831 |
| core_balanced | vol_target_trend_18pct | 22.83% | 127.51% | -29.56% | 0.910 | 0.772 | -5.24% | 227,512 |
| core_defensive | vol_target_trend_12pct | 15.99% | 80.94% | -24.85% | 0.871 | 0.643 | -3.85% | 180,937 |

### Core Finalist Interpretation

Current hierarchy:

```text
1. core_balanced
   Best current base for Core v1, but not finished.

2. core_aggressive
   Strongest compounding engine, too painful for default flagship use.

3. core_defensive
   Better drawdown profile, but still underwhelming Calmar/Sharpe.
```

Important distinction from tactical research:

```text
The tactical sleeve compressed from ~19% full-period CAGR to ~7% stitched OOS CAGR.
The structural core compressed from ~26% full-period CAGR to ~23% static OOS CAGR for core_balanced.
```

That is a much healthier validation shape.

However, the Sharpe and Calmar are still not good enough for the desired institutional-quality target.

---

## Part III — Risk-Constrained Core Research

### Target

The next target was to improve risk-adjusted quality, not maximize return.

Desired range:

```text
CAGR:   15–22%
MaxDD: <20–25%
Sharpe: >1.0
Calmar: >0.9–1.1
```

### Blunt Risk-Constrained Sweep

The risk-constrained v1 sweep tested:

```text
vol targets
max gross exposure caps
max crypto caps
drawdown throttles
monthly loss throttles
BTC crash-state throttles
asset concentration caps
```

Fast grid result:

```text
Constraint pass count: 0 / 96
```

Best full-period candidate:

```text
rc_def_vol18_mc35_mg75_dd10_ml06_cc50

CAGR:     13.36%
Return:   140.39%
MaxDD:    -17.08%
Sharpe:     0.991
Calmar:     0.782
Vol:        9.16%
AvgExp:     0.45
AvgCrypto:  0.11
```

Best OOS candidate:

```text
rc_bal_vol18_mc25_mg100_dd15_ml06_cc50

OOS CAGR:   16.33%
OOS Return: 83.08%
OOS MaxDD: -25.04%
OOS Sharpe: 0.892
OOS Calmar: 0.652
```

### Risk-Constrained Sweep Conclusion

This sweep lowered drawdown but did not improve the quality of the return stream enough.

The earlier `vol_target_trend_18pct` OOS profile:

```text
OOS CAGR:   22.83%
OOS MaxDD: -29.56%
Sharpe:     0.910
Calmar:     0.772
```

Best risk-constrained OOS profile:

```text
OOS CAGR:   16.33%
OOS MaxDD: -25.04%
Sharpe:     0.892
Calmar:     0.652
```

What happened:

```text
We reduced drawdown by about 4.5 points,
but gave up too much return and did not improve Sharpe/Calmar.
```

Diagnosis:

```text
The throttles were too blunt.
They reduced total exposure rather than selecting better risk.
```

Failure mode:

```text
less exposure
less volatility
less return
similar or worse risk-adjusted quality
```

Lesson:

```text
The next allocator must avoid bad risk before the loss, not merely reduce gross exposure after the portfolio is already damaged.
```

---

## Part IV — Risk-Contribution-Aware Allocator Research

### Motivation

The next design goal was to move from:

```text
portfolio-level throttle
```

to:

```text
risk-contribution-aware allocator
```

The proposed logic:

```text
1. Estimate each asset's realized volatility.
2. Convert target weights into inverse-vol / risk-aware weights.
3. Cap BTC/ETH by realized risk contribution, not just nominal allocation.
4. Dynamically reduce crypto risk cap when BTC is below MA200.
5. Dynamically reduce crypto risk cap when BTC volatility is rising.
6. Redistribute freed budget to QQQ/SPY/GLD/TLT/cash.
7. Rank by OOS Sharpe/Calmar first, full-period second.
```

### Operational Issue

The first `run_core_allocator_risk_contribution_sweep.py --fast` was still too large/noisy.

It attempted hundreds of policies and produced repeated pandas `FutureWarning` spam, making the run slow and painful in PowerShell.

A compact runner was added:

```text
scripts/run_core_allocator_risk_contribution_sweep_fast.py
```

This trims the grid to a focused ~72-policy sweep and suppresses warning spam.

Expected command:

```powershell
python scripts\run_core_allocator_risk_contribution_sweep_fast.py `
  --data-dir data `
  --assets BTC-USD ETH-USD QQQ SPY TLT GLD `
  --start 2019-01-01 `
  --end 2025-12-30 `
  --oos-start 2021-01-01 `
  --oos-end 2024-12-31 `
  --rebalance W-FRI `
  --fee-bps 2 `
  --out-dir artifacts\core_allocator_risk_contribution_sweep_compact
```

As of this memo, the compact runner still needs to be executed and evaluated.

---

## Part V — Regime Detection / HMM Note

A YouTube transcript discussed a Markov/HMM-style market regime model.

Initial takeaway:

```text
Markov/HMM regimes are useful as conceptual framing but should not directly drive allocation without validation.
```

User clarified that a previous branch already tested HMM and existing Itera regime detection methods outperformed HMM marginally.

This changes the conclusion:

```text
Do not replace Itera's regime layer with HMM.
Use HMM only as a benchmark or secondary diagnostic.
Recover and reuse the existing regime detector that already beat HMM.
```

Strategic implication:

```text
The next serious allocator design should integrate the existing Itera regime detector, not invent a new HMM regime layer.
```

Desired architecture:

```text
Layer 1:
  existing Itera regime detector

Layer 3 Core Allocator:
  base structural weights
  volatility target
  crypto risk-contribution cap
  regime-conditioned crypto cap
  regime-conditioned gross exposure cap
  regime-conditioned defensive allocation
  drawdown governor as backup only
```

---

## Where We Keep Striking Out

### 1. Tactical modules keep becoming sleeves, not the fund

Repeated tactical sweeps find controlled, useful modules. But once costs, corrected math, walk-forward, and stitched OOS are applied, the results become modest.

Root cause:

```text
The tactical search space is built around entry/exit logic.
Entry/exit logic naturally produces alpha sleeves, not structural compounding engines.
```

Implication:

```text
Stop asking tactical modules to be the flagship.
```

### 2. Dynamic policy selection is regime-late

Both allocator walk-forward selectors failed.

The selector picked whatever looked best in the trailing train window, then carried it into a different future regime.

Most damaging examples:

```text
crypto_only_equal selected into 2022
static_balanced_core selected into 2022
```

Root cause:

```text
Trailing Calmar/return selection is backward-looking and chases the last regime.
```

Implication:

```text
Do not dynamically select policies using naive trailing performance.
Prefer fixed structural policy plus regime-aware exposure modifiers.
```

### 3. Drawdown throttles are too blunt

Risk-constrained sweep reduced drawdown but also reduced return too much.

Root cause:

```text
Blunt throttles reduce exposure after damage or during broad stress, but they do not distinguish good risk from bad risk.
```

Implication:

```text
Risk control must become risk selection.
Use risk contribution, regime state, volatility state, and asset-specific caps.
```

### 4. Sharpe and Calmar are still underwhelming

The structural core has strong returns but only moderate risk-adjusted quality.

Current OOS examples:

```text
core_aggressive:
  Sharpe 0.904, Calmar 0.844

core_balanced:
  Sharpe 0.910, Calmar 0.772

core_defensive:
  Sharpe 0.871, Calmar 0.643
```

Root cause:

```text
The allocator still earns largely through volatile risk premia.
Vol targeting helps, but it does not fully transform the return distribution.
```

Implication:

```text
The next edge must come from better regime/risk-state selection, not more exposure.
```

### 5. Brute-force grids are becoming less useful

As the allocator becomes more complex, parameter sweeps can become slow, noisy, and prone to overfitting.

Root cause:

```text
Too many combinations without a sufficiently strong structural hypothesis.
```

Implication:

```text
Future sweeps should be smaller, hypothesis-driven, OOS-first, and tied to known regime detector outputs.
```

---

## What Has Survived So Far

### Tactical Sleeve Survivor

```text
primary_calmar
looser_stop_12pct_max_new_3__crypto_plus_growth_plus_macro_liquid
```

Status:

```text
Possible tactical satellite sleeve.
Not flagship.
```

### Core Allocator Survivor

```text
core_balanced = vol_target_trend_18pct
```

Status:

```text
Best current base for Core v1 research.
Needs improved risk engine.
```

### Aggressive Structural Survivor

```text
core_aggressive = trend_gated_balanced_ma200
```

Status:

```text
Strongest compounding engine.
Drawdown too high for default flagship use.
```

### Defensive Structural Survivor

```text
core_defensive = vol_target_trend_12pct
```

Status:

```text
Lower-risk variant.
Still not enough Sharpe/Calmar improvement.
```

---

## Current Best Hypothesis

The current best research hypothesis is:

```text
A fixed structural core allocator using volatility targeting and trend gating can produce the return engine.
The missing improvement must come from regime-aware risk contribution controls.
```

Not:

```text
Find another tactical setup.
```

Not:

```text
Let trailing performance choose among policies.
```

Not:

```text
Replace the regime engine with HMM.
```

Instead:

```text
Use the existing Itera regime detector to condition crypto risk caps, gross exposure, and defensive allocation.
```

---

## Recommended Next Steps

### 1. Run compact risk-contribution sweep

Run:

```powershell
python scripts\run_core_allocator_risk_contribution_sweep_fast.py `
  --data-dir data `
  --assets BTC-USD ETH-USD QQQ SPY TLT GLD `
  --start 2019-01-01 `
  --end 2025-12-30 `
  --oos-start 2021-01-01 `
  --oos-end 2024-12-31 `
  --rebalance W-FRI `
  --fee-bps 2 `
  --out-dir artifacts\core_allocator_risk_contribution_sweep_compact
```

Evaluate whether it improves beyond:

```text
Prior best risk-constrained OOS:
  CAGR:   16.33%
  MaxDD: -25.04%
  Sharpe: 0.892
  Calmar: 0.652

Core balanced OOS:
  CAGR:   22.83%
  MaxDD: -29.56%
  Sharpe: 0.910
  Calmar: 0.772
```

### 2. Recover prior HMM/regime branch

Search locally:

```powershell
git branch -a | Select-String -Pattern "hmm|regime|markov|hidden"

git log --all --oneline --decorate --grep="hmm"

git log --all --oneline --decorate --grep="regime"

git log --all --name-only --pretty=format:"%h %d %s" | Select-String -Pattern "hmm|regime|classify|market_state|state"
```

Goal:

```text
Find the existing regime detector that already beat HMM.
Use it in allocator research.
```

### 3. Build regime-aware core allocator

Next real implementation should be:

```text
scripts/run_core_allocator_regime_aware_sweep.py
```

Design:

```text
Inputs:
  existing Itera regime detector outputs
  BTC/ETH/QQQ/SPY/TLT/GLD prices

Controls:
  regime-conditioned crypto risk cap
  regime-conditioned gross exposure cap
  regime-conditioned defensive allocation
  volatility target
  risk-contribution cap

Scoring:
  OOS Sharpe first
  OOS Calmar second
  OOS MaxDD hard constraint
  full-period CAGR secondary
```

### 4. Stop repeating these paths unless the hypothesis changes

Avoid spending more cycles on:

```text
naive tactical-entry sweeps as flagship candidates
unconstrained policy selector by trailing Calmar
blunt portfolio-level drawdown throttle only
HMM as a replacement for existing regime detection
large brute-force grids without structural hypothesis
```

---

## Working Research Standard Going Forward

A candidate should not be discussed as a Core candidate unless it clears at least:

```text
Static OOS CAGR:      >= 12–15%
Static OOS MaxDD:     <= 25–30%
Static OOS Sharpe:    >= 1.0 preferred
Static OOS Calmar:    >= 0.75 minimum, >0.9 preferred
Walk-forward behavior: no catastrophic selector mistakes
Explainability: asset/risk/regime attribution available
```

A candidate should not be discussed as a flagship-quality candidate unless it trends toward:

```text
CAGR:   15–22%
MaxDD: <20–25%
Sharpe: >1.0
Calmar: >0.9–1.1
```

Anything below that may still be useful, but should be classified honestly as:

```text
satellite sleeve
research diagnostic
risk overlay
benchmark
```

not as the Itera Core engine.
