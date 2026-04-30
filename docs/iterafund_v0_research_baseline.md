# Itera Fund v0 — Static Multi-Asset Research Baseline

## Status

Research baseline. Not production. Not live trading guidance. This document captures the first validated multi-asset portfolio architecture for Itera Dynamics.

## Naming Convention

To avoid confusion, Itera components are named as follows:

- **Crypto Sleeve v1** — the calibrated BTC + ETH systematic crypto engine currently used as the crypto-side research/paper-trading baseline.
- **Crypto Sleeve v2** — future defensive-overlay / allocator-evolved crypto sleeve work.
- **Equity Sleeve v1** — SPY daily defensive trend sleeve.
- **Itera Fund v0** — static multi-asset research blend of Crypto Sleeve v1 and Equity Sleeve v1.

The sleeves are not standalone funds. Itera Fund v0 is the first research-level expression of a unified capital pool across asset classes.

## Architecture

Itera Fund v0 combines independently validated sleeve equity curves:

```text
Crypto Sleeve v1
  BTC + ETH systematic crypto exposure engine

Equity Sleeve v1
  SPY daily defensive trend sleeve

Static Allocator
  Weighted capital blend across sleeves

Itera Fund v0
  Unified multi-asset research portfolio
```

The initial allocator is deliberately static. Its purpose is to establish a clean baseline before exploring dynamic allocation.

## Crypto Sleeve v1

Crypto Sleeve v1 is the current calibrated multi-sleeve crypto engine. It includes BTC and ETH exposure across the validated sleeve structure. In the multi-asset blend tests, the crypto sleeve is represented by the existing calibrated 4-sleeve equity curve artifact:

```text
artifacts/fund_equal_cal_4s_2019-03-08_2025-12-31/equity_curves.csv
```

Observed metrics over the multi-asset overlap window:

| Metric | Crypto Sleeve v1 |
|---|---:|
| Total Return | +215.14% |
| CAGR | +18.34% |
| Max Drawdown | -17.72% |
| Sharpe | 1.166 |
| Calmar | 1.035 |
| Annualized Volatility | 15.49% |

## Equity Sleeve v1

Equity Sleeve v1 is a research-only SPY daily trend sleeve. It is intentionally simple and designed to test whether the Itera architecture generalizes cleanly beyond crypto.

### Signal Logic

Equity Sleeve v1 enters long when:

```text
close > EMA200
EMA50 > EMA200
63-day momentum > 0
```

It exits when:

```text
close < EMA200
or
EMA50 < EMA200
```

The sleeve is long-only, uses daily bars, targets SPY, and does not use leverage or shorting.

### Long-Window Robustness: 2005-01-03 to 2026-04-29

| Metric | Equity Sleeve v1 | SPY Buy & Hold |
|---|---:|---:|
| Total Return | +227.88% | +774.35% |
| CAGR | +5.73% | +10.71% |
| Max Drawdown | -17.31% | -55.19% |
| Sharpe | 0.685 | 0.632 |
| Calmar | 0.331 | 0.194 |
| Annualized Volatility | 8.70% | 18.99% |
| Trades | 69 | N/A |
| Exposure Time | 70.3% | 100.0% |

### Stress Window Behavior

| Window | Strategy Return | SPY Return | Delta Return | Strategy MaxDD | SPY MaxDD | Delta MaxDD |
|---|---:|---:|---:|---:|---:|---:|
| GFC 2008 | -8.35% | -46.56% | +38.22% | -9.37% | -55.19% | +45.82% |
| COVID 2020 | -12.27% | -3.88% | -8.39% | -17.31% | -33.72% | +16.41% |
| Bear 2022 | -9.80% | -18.65% | +8.85% | -9.80% | -24.50% | +14.70% |
| Post-2022 Recovery | +27.91% | +58.24% | -30.33% | -7.05% | -9.97% | +2.93% |

### Interpretation

Equity Sleeve v1 is validated as a defensive equity trend sleeve. It is not a return-maximizing equity alpha sleeve.

The sleeve behaves coherently:

- It protects capital during prolonged drawdown regimes.
- It lags violent recoveries and strong bull markets.
- It improves risk-adjusted efficiency but materially reduces raw return versus buy-and-hold SPY.

## Multi-Asset Blend Results

The first multi-asset tests combine Crypto Sleeve v1 and Equity Sleeve v1 over the common period:

```text
2019-03-08 to 2025-12-31
```

The daily return correlation between the crypto and equity sleeves is:

```text
+0.1033
```

This low positive correlation is the core reason the blend improves portfolio quality.

### 70/30 Candidate Baseline

| Series | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| Crypto Sleeve v1 | +215.14% | +18.34% | -17.72% | 1.166 | 1.035 | 15.49% |
| Equity Sleeve v1 | +86.57% | +9.58% | -16.82% | 0.996 | 0.569 | 9.68% |
| Itera Fund v0 70/30 | +176.57% | +16.09% | -15.47% | 1.255 | 1.040 | 12.55% |

Delta versus Crypto Sleeve v1:

| Metric | Delta |
|---|---:|
| CAGR | -2.24% |
| MaxDD | +2.25% |
| Sharpe | +0.088 |
| Calmar | +0.005 |

## Allocation Sweep

| Crypto Weight | Equity Weight | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol | Delta Sharpe vs Crypto | Delta MaxDD vs Crypto |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100% | 0% | +215.14% | +18.34% | -17.72% | 1.166 | 1.035 | 15.49% | +0.000 | +0.00% |
| 90% | 10% | +202.28% | +17.62% | -17.05% | 1.191 | 1.033 | 14.54% | +0.025 | +0.67% |
| 80% | 20% | +189.42% | +16.87% | -16.30% | 1.221 | 1.035 | 13.55% | +0.054 | +1.42% |
| 70% | 30% | +176.57% | +16.09% | -15.47% | 1.255 | 1.040 | 12.55% | +0.088 | +2.25% |
| 60% | 40% | +163.71% | +15.29% | -14.54% | 1.293 | 1.051 | 11.54% | +0.127 | +3.18% |
| 50% | 50% | +150.85% | +14.44% | -13.58% | 1.332 | 1.064 | 10.57% | +0.166 | +4.14% |
| 40% | 60% | +138.00% | +13.56% | -12.76% | 1.365 | 1.063 | 9.69% | +0.199 | +4.96% |
| 30% | 70% | +125.14% | +12.64% | -12.50% | 1.373 | 1.012 | 8.99% | +0.207 | +5.22% |
| 20% | 80% | +112.28% | +11.67% | -13.76% | 1.327 | 0.848 | 8.62% | +0.161 | +3.96% |
| 10% | 90% | +99.42% | +10.66% | -15.10% | 1.198 | 0.706 | 8.80% | +0.032 | +2.62% |
| 0% | 100% | +86.57% | +9.58% | -16.82% | 0.996 | 0.569 | 9.68% | -0.171 | +0.90% |

## Candidate Allocations

- **70/30** — flagship research baseline. Preserves Itera's crypto-forward identity while improving drawdown and Sharpe.
- **60/40** — defensive growth variant. Better Sharpe and Calmar with more return drag.
- **50/50** — balanced risk-adjusted variant. Strong Calmar, smoother profile, but less crypto-forward.
- **30/70** — low-volatility variant. Highest Sharpe in the tested sweep, but too equity-heavy to be the flagship Itera baseline at this stage.

## Baseline Conclusion

Itera Fund v0 is validated as a static multi-asset research baseline.

The primary evidence is:

1. Crypto Sleeve v1 remains the dominant return engine.
2. Equity Sleeve v1 contributes genuine diversification, with low correlation to crypto.
3. The blended portfolio improves Sharpe and drawdown versus the crypto-only baseline.
4. The allocation sweep behaves coherently and shows a clear tradeoff between return and stability.

## Known Limitations

- Equity Sleeve v1 is simple and defensive; it is not optimized as an equity alpha engine.
- The allocator is static and does not yet respond dynamically to cross-asset regimes.
- The blend uses independently generated equity curves and does not model all live portfolio-level execution frictions.
- Yahoo Finance data is acceptable for free research but is not institutional-grade market data.
- The current baseline is research-only and should not be treated as production fund logic.

## Next Research Direction

The next major research step is **Itera Allocator v1**.

Allocator v1 should investigate dynamic capital weights across sleeves based on regime, drawdown, volatility, and sleeve-level trend quality.

The core question:

```text
Can Itera improve on the static 70/30 baseline by dynamically shifting capital between Crypto Sleeve v1 and Equity Sleeve v1 without introducing overfit behavior?
```

Until that work is complete, Itera Fund v0 should remain the static research baseline and control group.
