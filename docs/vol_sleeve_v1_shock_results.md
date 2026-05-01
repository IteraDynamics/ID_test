# Volatility Sleeve v1 — Short-Vol Shock Test Results

## Status

Shock testing complete for the initial Short-Vol v1 candidate at a 10% portfolio allocation.

Result:

```text
Short-Vol v1 remains interesting as a high-risk research sleeve, but it is not promoted as a core sleeve.
10% allocation is rejected as a default allocation.
5% maximum allocation may be revisited only with additional controls.
```

## Objective

The purpose of this test was to determine whether the attractive clean backtest results for the short-volatility sleeve survive realistic left-tail stress.

Short-volatility products can appear attractive in normal backtests but carry embedded crash risk. A sleeve that improves clean-period Sharpe and Calmar is not automatically acceptable if it creates hidden fragility under volatility shocks.

The shock test asked:

```text
What happens to the four-sleeve Itera portfolio if the short-vol sleeve suffers a sudden -50%, -70%, or -90% level shock?
```

## Portfolio Tested

Allocation:

```text
50% Crypto / 25% SPY / 15% QQQ / 10% Short-Vol
```

Test window:

```text
2022-03-30 → 2025-12-31
943 daily bars
```

The window is constrained by available SVIX history.

## No-Shock Baseline

| Series | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| Crypto Sleeve | +27.79% | +6.75% | -13.32% | 0.557 | 0.506 | 13.37% |
| SPY Sleeve | +36.93% | +8.73% | -7.26% | 1.062 | 1.202 | 8.24% |
| QQQ Sleeve | +39.22% | +9.21% | -19.57% | 0.756 | 0.471 | 12.80% |
| Vol Sleeve | +75.26% | +16.11% | -28.01% | 0.686 | 0.575 | 27.50% |
| Itera 4-Sleeve | +36.54% | +8.64% | -9.72% | 0.901 | 0.889 | 9.78% |

The clean four-sleeve result was attractive. Compared with no-vol alternatives in the same window, the 10% short-vol allocation improved CAGR, Sharpe, and Calmar while keeping drawdown controlled.

## Shock Method

The shock runner applied a one-time permanent level shock to the short-vol sleeve at the midpoint of the common test window.

Shock date selected by the runner:

```text
2024-02-14
```

Shock scenarios:

```text
-50% short-vol sleeve shock
-70% short-vol sleeve shock
-90% short-vol sleeve shock
```

The shock is applied only to the vol sleeve. Crypto, SPY, and QQQ sleeve curves are unchanged.

## Shock Results Summary

| Scenario | Portfolio Total Return | Portfolio CAGR | Portfolio MaxDD | Sharpe | Calmar | AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| No shock | +36.54% | +8.64% | -9.72% | 0.901 | 0.889 | 9.78% |
| Vol -50% | +27.77% | +6.74% | -9.72% | 0.692 | 0.694 | 10.24% |
| Vol -70% | +24.27% | +5.95% | -11.51% | 0.592 | 0.517 | 10.81% |
| Vol -90% | +20.76% | +5.15% | -14.05% | 0.496 | 0.367 | 11.57% |

## Vol Sleeve Shock Behavior

| Scenario | Vol Sleeve Total Return | Vol Sleeve CAGR | Vol Sleeve MaxDD | Vol Sharpe | Vol Calmar | Vol AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| No shock | +75.26% | +16.11% | -28.01% | 0.686 | 0.575 | 27.50% |
| Vol -50% | -12.37% | -3.45% | -63.03% | 0.146 | -0.055 | 37.76% |
| Vol -70% | -47.42% | -15.73% | -77.82% | 0.003 | -0.202 | 45.48% |
| Vol -90% | -82.47% | -37.10% | -92.61% | -0.096 | -0.401 | 54.08% |

## Interpretation

The portfolio survives the shocks mechanically. Even a -90% vol-sleeve shock does not destroy the overall portfolio:

```text
-90% shock portfolio MaxDD: -14.05%
```

That means a 10% short-vol sleeve is not catastrophic at the portfolio level in this particular test.

However, the shock-adjusted results are not attractive enough to justify making short-vol a core sleeve.

The clean 10% short-vol allocation looks strong:

```text
No shock:
CAGR   +8.64%
MaxDD  -9.72%
Sharpe  0.901
Calmar  0.889
```

But after only a -50% vol shock:

```text
Vol -50% shock:
CAGR   +6.74%
MaxDD  -9.72%
Sharpe  0.692
Calmar  0.694
```

This becomes worse than simpler no-vol portfolios from the prior sweep, such as:

```text
60% Crypto / 20% SPY / 20% QQQ / 0% Vol:
CAGR   +7.65%
MaxDD  -9.66%
Sharpe  0.815
Calmar  0.792
```

Under -70% and -90% shocks, the short-vol sleeve clearly fails the compensation test. The portfolio still survives, but the expected benefit is no longer compelling.

## Decision

Short-Vol v1 is **not promoted** as a core Itera sleeve.

The clean backtest improvement is not sufficient to justify the embedded tail risk at a 10% allocation.

Recommended status:

```text
Short-Vol v1: high-risk watchlist / not promoted
10% allocation: rejected as default
5% allocation: may be revisited only with stricter controls
```

Long-Vol v1 was already rejected in the prior standalone test and remains rejected in current form.

## Research Lesson

Short-volatility carry can improve clean-period metrics, but its value is fragile once realistic shock scenarios are introduced.

The key lesson is not that short-vol can never belong in Itera. The lesson is that short-vol must be treated as a capped, explicitly risk-labeled carry sleeve, not a normal diversifier.

## Current Sleeve Universe After Shock Testing

| Sleeve | Status | Notes |
|---|---|---|
| Crypto Sleeve v1 | Validated / active research baseline | Primary return engine |
| SPY Equity v1 | Validated / active research baseline | Defensive equity stabilizer |
| QQQ Growth v1b | Candidate / watchlist | Adds some portfolio value, not strong standalone |
| Short-Vol v1 | High-risk watchlist / not promoted | 10% allocation rejected after shock testing |
| Long-Vol v1 | Rejected | Current implementation loses too much capital |
| Allocator v1 | Rejected | Dynamic allocation failed vs static baseline |
| Allocator v2 | Rejected | Defensive overlay failed vs static baseline |

## Next Research Direction

With the current sleeve universe assessed, the next logical research path is Layer 1 regime modeling.

Recommended next branch:

```text
research/hmm-regime-v1
```

Purpose:

```text
Explore Hidden Markov Model regime detection as a research-only Layer 1 enhancement.
```

The HMM work should not replace the deterministic regime engine initially. It should run in shadow mode and compare probabilistic regime states against the existing deterministic Layer 1 outputs.
