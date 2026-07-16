# Trend Persistence Engine v0 — Final Research Report

**Status:** Completed research  
**Promotion decision:** Signal validated; portfolio implementation rejected  
**Runtime status:** Not promoted  
**Closed:** 2026-07-15

## Executive decision

Trend Persistence Engine v0 demonstrated repeatable out-of-sample ranking skill for continuation events in BTC and ETH. The strongest center candidates survived nearby horizon and label perturbations and were supported by hundreds to thousands of out-of-sample events.

However, none of the tested portfolio mappings improved the canonical Core v1 portfolio. Every tested sleeve-gating or sleeve-scaling overlay reduced CAGR, Sharpe, and Calmar while worsening maximum drawdown. Trend Persistence v0 is therefore closed without runtime promotion.

This is not a rejection of the predictive signal. It is a rejection of the tested economic implementation.

## Research question

Given an already-established trend direction, can current market state rank the probability of a meaningful continuation over a future horizon, and can that ranking improve the canonical Core v1 portfolio?

The research produced two distinct answers:

1. **Predictive question:** Yes. Several continuation-ranking candidates showed meaningful and robust out-of-sample discrimination.
2. **Portfolio question:** No, not through the tested continuous sleeve gates and scaling rules.

## Completed research program

The program included:

- BTC and ETH hourly discovery sweep
- Expanding annual walk-forward validation
- Logistic-regression and gradient-boosting baselines
- Feature-family ablation
- Targeted horizon refinement
- Nearby-parameter robustness testing
- Event-count and top-tail validity audit
- Canonical Core v1 sleeve-matrix reconstruction and reconciliation
- Strictly out-of-sample portfolio integration with one-bar lag
- Conservative incremental overlay-turnover cost

## Validated signal candidates

| Asset | Candidate | Horizon | Model | Features | ROC AUC | Average Precision | Top-5 Lift | Audit |
|---|---|---:|---|---|---:|---:|---:|---|
| BTC | Immediate | 3h | Logistic | Momentum + volatility | 0.7399 | 0.0485 | 5.29x | VALID |
| ETH | Immediate | 3h | Logistic | All features | 0.7137 | 0.0767 | 4.01x | VALID |
| BTC | Medium | 60h | Logistic | All features | 0.6770 | 0.1185 | 3.48x | VALID |
| BTC | Long | 120h | Logistic | All features | 0.6703 | 0.1378 | 3.49x | WARN |

The targeted robustness study reviewed 126 configurations:

- 93 VALID
- 33 WARN
- 0 INVALID/REJECT

Center-candidate event support:

- BTC immediate: 760 OOS events; 201 events in the top 5% probability bucket
- ETH immediate: 1,497 OOS events; 300 top-5% events
- BTC medium: 2,904 OOS events; 505 top-5% events
- BTC long: 3,178 OOS events; 554 top-5% events

## Canonical portfolio baseline

The reconciled Core v1 walk-forward portfolio used 52,374 hourly rows and reproduced the canonical NAV to floating-point precision.

| Metric | Core v1 |
|---|---:|
| CAGR | 19.93% |
| Sharpe | 1.318 |
| Calmar | 1.208 |
| Maximum drawdown | -16.50% |
| Final NAV from $100,000 | $297,331.76 |

## Portfolio integration results

The tested overlays altered only the existing BTC and ETH trend sleeves. Core remained the directional strategy.

| Portfolio variant | Decision | CAGR | Sharpe | Calmar | Maximum drawdown |
|---|---|---:|---:|---:|---:|
| Core unchanged | BASELINE | 19.93% | 1.318 | 1.208 | -16.50% |
| BTC immediate gate | REJECT | 18.14% | 1.194 | 0.979 | -18.52% |
| BTC medium scaling | REJECT | 17.58% | 1.107 | 0.887 | -19.82% |
| BTC + ETH immediate gates | REJECT | 11.43% | 0.730 | 0.430 | -26.56% |
| Combined persistence governor | REJECT | 11.68% | 0.721 | 0.406 | -28.73% |

No overlay passed the predeclared promotion rule:

- Sharpe delta greater than zero
- Calmar delta greater than zero
- Maximum-drawdown delta nonnegative
- CAGR degradation no worse than 0.50 percentage points

## Interpretation

The predictive models rank continuation events, but the tested controls acted too broadly on portfolio exposure.

The likely failure modes are:

- A continuation classifier is not necessarily an optimal continuous position-sizing signal.
- Reducing entire sleeves during low-confidence periods removed profitable exposure that Core was designed to retain.
- ETH gating was especially destructive, indicating that a statistically valid ETH signal did not map cleanly to Core's ETH sleeve economics.
- Medium-horizon boosting added exposure at times that did not compensate for turnover and adverse path effects.
- Portfolio drawdown is path-dependent; local event-ranking skill does not guarantee improved portfolio-level downside control.

## Final status

| Dimension | Decision |
|---|---|
| Predictive evidence | VALIDATED |
| Robustness | PASSED for three center candidates |
| Cross-asset evidence | SUPPORTED by independent BTC and ETH immediate signals |
| Portfolio implementation | REJECTED |
| Runtime promotion | NOT ALLOWED |
| Research lifecycle | COMPLETED |

## Preserved future work

Trend Persistence may be revisited only as a new, narrowly scoped research program. Plausible hypotheses include:

- Entry or re-entry confirmation rather than continuous scaling
- Delayed exits during high-confidence persistence
- BTC-only event-triggered use
- No-boost defensive gating
- Conditional use only when Core has just changed state

Those ideas are not continuations of v0 by default. They require a new charter, frozen hypotheses, and independent promotion criteria.

## Institutional lesson

Trend Persistence v0 establishes an important research principle for Itera Dynamics:

> Out-of-sample predictive skill is necessary but insufficient. A signal is promoted only when its economic mapping improves the canonical portfolio under realistic timing and cost assumptions.

Core v1 remains unchanged.
