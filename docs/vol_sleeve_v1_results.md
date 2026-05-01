# Volatility Sleeve v1 — Research Results

## Status

Research experiment in progress. Initial standalone and portfolio results show that **Short-Vol v1 is a candidate carry sleeve**, while **Long-Vol v1 is rejected in its current form**.

This document captures the first volatility-sleeve research pass and defines the next required stress test before any promotion decision.

## Objective

The purpose of Volatility Sleeve v1 is to test whether volatility exposure adds a new risk dimension to Itera Dynamics beyond:

```text
Crypto Sleeve v1  → high-vol / asymmetric return engine
SPY Equity v1     → defensive equity stabilizer
QQQ Growth v1b    → candidate equity growth sleeve
```

The volatility sleeve is not intended to be another equity-beta expression. It is intended to test whether volatility carry or volatility hedging can improve portfolio-level behavior.

## Instruments Tested

| Sleeve | Instrument Proxy | Role |
|---|---|---|
| Short-Vol v1 | SVIX | Carry / volatility risk premium |
| Long-Vol v1 | VIXY | Crash hedge / volatility spike participation |

## Short-Vol v1 Standalone Result

Test window:

```text
2022-03-30 → 2026-05-01
```

| Series | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| Short-Vol v1 Strategy | +53.72% | +11.09% | -28.01% | 0.529 | 0.396 | 27.12% |
| SVIX Buy & Hold | +32.45% | +7.12% | -79.30% | 0.458 | 0.090 | 66.83% |

Activity:

| Metric | Value |
|---|---:|
| Trades | 48 |
| Exposure Time | 38.5% |
| Average Exposure | 38.5% |

### Interpretation

Short-Vol v1 materially improved on raw SVIX buy-and-hold by cutting drawdown and volatility substantially while improving CAGR, Sharpe, and Calmar.

However, the sleeve remains high risk:

```text
Strategy MaxDD: -28.01%
Strategy AnnVol: 27.12%
```

This is not a safe diversifier. It is a high-risk carry sleeve with embedded left-tail exposure.

## Long-Vol v1 Standalone Result

Test window:

```text
2011-01-04 → 2026-05-01
```

| Series | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| Long-Vol v1 Strategy | -67.43% | -7.06% | -83.66% | -0.025 | -0.084 | 36.94% |
| VIXY Buy & Hold | -100.00% | -48.16% | -100.00% | -0.602 | -0.482 | 70.02% |

Activity:

| Metric | Value |
|---|---:|
| Trades | 170 |
| Exposure Time | 9.8% |
| Average Exposure | 9.8% |

### Interpretation

Long-Vol v1 improved substantially over buy-and-hold VIXY, but the absolute result is still unacceptable. The strategy lost two-thirds of capital and experienced an -83.66% max drawdown.

Current long-vol conclusion:

```text
Long-Vol v1 is rejected in current form.
```

Long-vol hedging may still be useful in the future, but it likely requires a different event-triggered design rather than simple trend-following on a decaying VIX proxy.

## Four-Sleeve Portfolio Test

The initial portfolio-level test added Short-Vol v1 to the three-sleeve Itera candidate portfolio.

Test window was restricted by SVIX history:

```text
2022-03-30 → 2025-12-31
943 daily bars
```

Primary tested allocation:

```text
55% Crypto / 20% SPY / 15% QQQ / 10% Short-Vol
```

## Four-Sleeve Result

| Series | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| Crypto Sleeve | +27.79% | +6.75% | -13.32% | 0.557 | 0.506 | 13.37% |
| SPY Sleeve | +36.93% | +8.73% | -7.26% | 1.062 | 1.202 | 8.24% |
| QQQ Sleeve | +39.22% | +9.21% | -19.57% | 0.756 | 0.471 | 12.80% |
| Short-Vol Sleeve | +75.26% | +16.11% | -28.01% | 0.686 | 0.575 | 27.50% |
| Itera Four-Sleeve | +36.08% | +8.55% | -9.86% | 0.871 | 0.867 | 10.04% |

## Correlation

| Pair | Daily Return Correlation |
|---|---:|
| Crypto vs Short-Vol | +0.104 |
| SPY vs Short-Vol | +0.418 |
| QQQ vs Short-Vol | +0.406 |
| SPY vs QQQ | +0.805 |

Short-vol is not just duplicating crypto or equity returns, but it is still positively correlated with equity risk-on behavior.

## Allocation Sweep

| Crypto | SPY | QQQ | Vol | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 70% | 30% | 0% | 0% | +30.53% | +7.35% | -10.42% | 0.750 | 0.706 | 10.20% |
| 60% | 20% | 20% | 0% | +31.90% | +7.65% | -9.66% | 0.815 | 0.792 | 9.66% |
| 60% | 20% | 15% | 5% | +33.71% | +8.04% | -9.48% | 0.840 | 0.848 | 9.82% |
| 55% | 20% | 15% | 10% | +36.08% | +8.55% | -9.86% | 0.871 | 0.867 | 10.04% |
| 50% | 25% | 15% | 10% | +36.54% | +8.64% | -9.72% | 0.901 | 0.889 | 9.78% |
| 50% | 20% | 20% | 10% | +36.65% | +8.67% | -9.90% | 0.893 | 0.876 | 9.91% |
| 45% | 25% | 20% | 10% | +37.11% | +8.76% | -9.95% | 0.920 | 0.881 | 9.69% |
| 45% | 20% | 20% | 15% | +39.02% | +9.17% | -11.44% | 0.892 | 0.801 | 10.50% |
| 40% | 30% | 20% | 10% | +37.56% | +8.86% | -10.00% | 0.944 | 0.886 | 9.52% |

## Portfolio Interpretation

In the available SVIX window, adding a small short-vol allocation improved portfolio metrics.

Example comparison:

```text
70/30 Crypto/SPY baseline:
CAGR   +7.35%
MaxDD  -10.42%
Sharpe  0.750
Calmar  0.706

55/20/15/10 four-sleeve candidate:
CAGR   +8.55%
MaxDD  -9.86%
Sharpe  0.871
Calmar  0.867
```

This is a real improvement in the tested window.

However, the result is not sufficient for promotion because the test window is short and favorable. It excludes important volatility shock regimes such as 2018-style short-vol collapse and the 2020 COVID volatility spike.

## Decision

Current statuses:

```text
Short-Vol v1: candidate / high-risk carry sleeve
Long-Vol v1: rejected in current form
```

Short-Vol v1 should not be promoted until explicit shock testing is complete.

Recommended guardrail:

```text
Short-Vol portfolio allocation should remain capped at 5–10% during research.
Do not test or propose allocations above 10% without explicit tail-risk justification.
```

## Required Next Test: Shock Scenario Analysis

Backtest metrics are not enough for short-volatility sleeves.

The next required test is a deterministic shock scenario applied to the short-vol sleeve inside the four-sleeve portfolio.

The test must answer:

```text
What happens to portfolio MaxDD, Sharpe, and Calmar if the vol sleeve suffers a sudden -50%, -70%, or -90% shock?
```

Shock testing is required before any promotion decision.

## Promotion Criteria

Short-Vol v1 can only remain a candidate if:

- 5–10% allocations survive shock testing without unacceptable portfolio damage;
- portfolio MaxDD remains within acceptable bounds under simulated -50% and -70% vol-sleeve shocks;
- any improvement in Sharpe/Calmar is not purely an artifact of the limited SVIX history window;
- allocation remains capped and explicitly labeled high-risk carry.

If shock testing shows that a 10% allocation creates unacceptable fragility, Short-Vol v1 should be reduced to 5% max or rejected.
