# Itera Dynamics Research Status

**As of 2026-07-15**  
**Branch:** `research/trend-persistence-v0`

This document summarizes completed research, current evidence, and promotion status. It is intentionally conservative: historical and walk-forward results are not presented as live or production performance.

## Executive Summary

Itera Dynamics has progressed beyond a strategy framework into a reproducible quantitative research platform with two completed research programs under active validation:

1. **Jump Risk Engine v0** — ranks the probability of discontinuous market moves across multiple horizons.
2. **Trend Persistence Engine v0** — estimates whether an established trend is likely to continue over a specified horizon.

Both programs use expanding walk-forward validation, immutable artifacts, feature ablation, targeted horizon refinement, nearby-parameter robustness testing, and cross-asset checks. Neither is deployed in the live paper runtime. Promotion requires portfolio-level evidence.

The strongest current finding is a robust 3-hour trend-continuation signal that appears independently in BTC and ETH, alongside a separate immediate jump-risk signal that also transfers from BTC to ETH.

---

## Research Process

The current research workflow is:

```text
Hypothesis
  -> Discovery sweep
  -> Feature ablation
  -> Targeted horizon refinement
  -> Nearby-parameter robustness
  -> Cross-asset transfer
  -> Statistical validity audit
  -> Candidate registry
  -> Portfolio integration
  -> Runtime promotion decision
```

Reusable Research Engine components include:

- Deterministic dataset/configuration fingerprints
- Immutable Parquet feature caches
- Resumable long-running experiments
- Timestamped artifact directories
- Per-configuration JSON outputs
- Statistical validity audits
- Append-only candidate/champion registry
- Explicit research-only/runtime-separation flags

---

# 1. Jump Risk Engine v0

## Research Question

Can observable market state rank the probability of a future discontinuous move without claiming to predict the exact time, direction, or magnitude of that move?

## BTC Hourly Results

Targeted refinement produced the following leading out-of-sample configurations:

| Target | Horizon | Model | Feature family | ROC AUC | Average Precision | Top-5% Event Rate | Top-5 Lift |
|---|---:|---|---|---:|---:|---:|---:|
| Any jump | 2h | GBM | Energy | 0.8036 | 0.0159 | 1.75% | 7.30x |
| Down jump | 2h | Logistic | Structure | 0.7641 | 0.0146 | 1.07% | 7.57x |
| Up jump | 18h | GBM | Energy | 0.7054 | 0.0432 | 7.23% | 4.90x |
| Up jump | 120h | Logistic | Structure | 0.7692 | 0.1307 | 16.51% | 5.30x |

These are ranking results on rare-event labels. High lift does not imply calibrated certainty or production readiness.

## Threshold Robustness

The leading BTC candidates survived nearby label definitions rather than existing at one exact threshold. Examples:

- Immediate any-jump, 2h:
  - z=2.5: AUC 0.8018, lift 7.59x
  - z=3.0: AUC 0.8036, lift 7.30x
  - z=3.5: AUC 0.7610, lift 6.72x

- Extended upside, 120h:
  - z=2.5: AUC 0.6891, lift 3.43x
  - z=3.0: AUC 0.7692, lift 5.30x
  - z=3.5: AUC 0.8126, lift 5.85x

Interpretation: the signal survives nearby event definitions, but this does not by itself prove absence of overfitting.

## Locked BTC-to-ETH Transfer

The exact BTC-selected models were applied to ETH without retuning:

| Target | Horizon | ETH ROC AUC | ETH Average Precision | ETH Top-5 Lift |
|---|---:|---:|---:|---:|
| Any jump | 2h | 0.7628 | 0.0243 | 5.76x |
| Down jump | 2h | 0.7418 | 0.0194 | 4.83x |
| Up jump | 18h | 0.6828 | 0.0345 | 3.46x |
| Up jump | 120h | 0.7115 | 0.0544 | 2.57x |

This is the strongest evidence that the immediate jump-risk ranking is not purely BTC-specific.

## Daily ETF Generalization Audit

A broad daily-native study was run on SPY, QQQ, and GLD. Initial headline metrics contained sparse-event and undefined-fold artifacts, so a formal audit was introduced.

Audit outcome:

- 180 configurations reviewed
- 150 INVALID
- 30 WARN
- 0 VALID

Audited candidates retained for future work:

| Asset | Lane | Horizon | Grade | Events | Top-5 Events | ROC AUC | Lift |
|---|---|---:|---|---:|---:|---:|---:|
| GLD | Extended up | 60d | WARN/A | 143 | 26 | 0.7902 | 3.62x |
| GLD | Immediate any | 5d | WARN/A | 70 | 10 | 0.7405 | 2.88x |
| GLD | Medium up | 20d | WARN/A | 93 | 11 | 0.7483 | 2.35x |
| QQQ | Immediate any | 5d | WARN/B | 25 | 3 | 0.6992 | 2.42x |

These are registered as **research candidates**, not champions.

## Current Status

**Status:** Mature research program / candidate set  
**Not yet proven:** portfolio value, production calibration, forward live stability

---

# 2. Trend Persistence Engine v0

## Research Question

Given an already-established trend direction, can current market state rank the probability of a meaningful continuation over a future horizon?

This is not raw direction prediction. The model first defines the current trend direction and then predicts whether future return in that same direction exceeds a volatility-aware and absolute threshold.

## Discovery

The first hourly BTC/ETH discovery sweep completed 180 configurations using:

- Multiple horizons
- Multiple volatility thresholds
- Multiple absolute return floors
- Logistic regression and gradient boosting
- Expanding annual walk-forward validation

All 180 configurations completed with valid outputs.

## Feature Ablation

A targeted 96-configuration ablation compared baseline, momentum, volatility, structure, volume, and full feature sets.

Key findings:

- BTC short horizon favored momentum+volatility or structure.
- BTC 72h and 120h favored logistic regression with all features.
- ETH 72h favored volatility features.
- ETH 120h favored the full feature set.
- No universal feature family dominated all assets and horizons.

This suggests immediate and multi-day persistence may reflect different mechanisms.

## Targeted Horizon Refinement

| Asset | Candidate | Horizon | Model | Features | ROC AUC | Average Precision | Top-5 Lift |
|---|---|---:|---|---|---:|---:|---:|
| BTC | Immediate | 3h | Logistic | Momentum + volatility | 0.7399 | 0.0485 | 5.29x |
| ETH | Immediate | 3h | Logistic | All features | 0.7137 | 0.0767 | 4.01x |
| BTC | Medium | 60h | Logistic | All features | 0.6770 | 0.1185 | 3.48x |
| BTC | Long | 120h | Logistic | All features | 0.6703 | 0.1378 | 3.49x |
| ETH | Medium | 72h | Logistic | Baseline + volatility | 0.6415 | 0.1065 | 2.37x |
| ETH | Long | 132h | GBM | All features | 0.6208 | 0.1013 | 2.82x |

The central finding is the independent 3-hour continuation signal in BTC and ETH.

## Targeted Robustness

The four center candidates were tested across nearby horizons, volatility thresholds, and absolute floors.

Audit counts:

- 93 VALID
- 33 WARN
- 0 INVALID/REJECT

Center scorecard:

| Candidate | Grade | OOS Events | Top-5 Events | ROC AUC | Top-5 Lift |
|---|---|---:|---:|---:|---:|
| BTC immediate | VALID | 760 | 201 | 0.7399 | 5.29x |
| ETH immediate | VALID | 1,497 | 300 | 0.7137 | 4.01x |
| BTC medium | VALID | 2,904 | 505 | 0.6770 | 3.48x |
| BTC long | WARN | 3,178 | 554 | 0.6703 | 3.49x |

Interpretation:

- The immediate BTC/ETH signals are supported by hundreds of out-of-sample events.
- The signal survives nearby parameter perturbations.
- BTC immediate, ETH immediate, and BTC medium have advanced to engine-candidate status for portfolio testing.
- BTC long remains a secondary WARN candidate.

## Current Portfolio Integration Study

The current branch contains a research-only portfolio integration runner that conditions the canonical Core v1 crypto sleeves using the three VALID persistence candidates.

Planned comparisons:

1. Core unchanged
2. BTC immediate gate
3. BTC + ETH immediate gates
4. BTC medium scaling
5. Combined persistence governor

Primary metrics:

- CAGR
- Total return
- Sharpe
- Calmar
- Maximum drawdown
- Worst year
- Exposure
- Overlay turnover
- Incremental cost

Core remains the directional strategy. Trend Persistence only scales or gates existing crypto sleeves.

**Current status:** portfolio integration infrastructure is being reconciled against the canonical Core sleeve matrix. No portfolio-improvement claim has yet been made.

---

# 3. Canonical Core v1 Context

The selected Core v1 allocation is:

| Sleeve | Weight |
|---|---:|
| BTC 4H trend | 15.0% |
| ETH 1H trend | 10.0% |
| ETH 4H trend | 10.0% |
| SPY | 17.5% |
| QQQ | 27.5% |
| GLD | 20.0% |

Canonical research results over the primary study period were approximately:

- Total return: 201.43%
- CAGR: 20.19%
- Maximum drawdown: -17.50%
- Sharpe: 1.341
- Calmar: 1.154

A recent canonical WFO reconstruction for the portfolio-integration study produced:

- Total return: 197.33%
- CAGR: 19.93%
- Maximum drawdown: -16.50%
- Sharpe: 1.318
- Calmar: 1.208

These are historical research results, not live performance.

---

# 4. Promotion Status

| Program | Discovery | Ablation | Horizon Refinement | Robustness | Cross-Asset | Audit | Portfolio Value | Status |
|---|---|---|---|---|---|---|---|---|
| Jump Risk | PASS | PASS | PASS | PASS | PASS on ETH | Mixed: crypto strong, daily ETF WARN | PENDING | Research candidate set |
| Trend Persistence | PASS | PASS | PASS | PASS | PASS on ETH | PASS for 3 center candidates | IN PROGRESS | Engine candidates |

No research model has been added to the live or paper-trading runtime.

---

# 5. Current Limitations

The current evidence does not establish:

- Live profitability
- Stable real-time calibration
- Independent external validation
- Execution robustness under partial fills or venue outages
- Capacity or market-impact limits
- Portfolio improvement from either research engine
- Generalization beyond the tested assets and periods

The next decisive milestone is not another discovery experiment. It is proving that one of the validated research candidates improves the canonical Core portfolio after conservative cost and turnover assumptions.

---

# 6. Reproducibility

The branch contains scripts for:

- Jump Risk feature research, ablation, horizon search, robustness, transfer, daily generalization, and audit
- Trend Persistence discovery, ablation, horizon refinement, robustness, and portfolio integration
- Research Engine caching and candidate registry
- Canonical Core WFO and sleeve-level attribution

Generated artifacts are intentionally not committed because they can be large and environment-specific. Each runner writes timestamped manifests, summaries, detailed configuration outputs, and resumable state under `artifacts/`.

The numbers in this document are transcribed from completed experiment outputs and should be re-generated before any production decision.
