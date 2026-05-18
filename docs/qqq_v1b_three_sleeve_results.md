# QQQ Growth Sleeve v1b and Three-Sleeve Portfolio Results

## Status

Research experiment complete enough for candidate assessment. QQQ Growth Sleeve v1b is **not promoted as a standalone sleeve**, but it remains a **candidate small-allocation portfolio component** pending additional confirmation.

## Objective

The goal was to determine whether adding a dedicated QQQ growth sleeve improves Itera's portfolio construction more effectively than forcing SPY to behave as both a defensive stabilizer and a growth engine.

Current sleeve roles:

```text
Crypto Sleeve v1  → primary return engine
SPY Equity v1     → defensive equity stabilizer
QQQ Growth v1b    → candidate growth equity sleeve
```

## QQQ v1 Standalone Result

Initial QQQ v1 was too reactive.

| Metric | QQQ v1 |
|---|---:|
| Total Return | +348.15% |
| CAGR | +7.29% |
| MaxDD | -22.12% |
| Sharpe | 0.634 |
| Calmar | 0.330 |
| Annualized Volatility | 12.33% |
| Trades | 467 |
| Exposure Time | 63.0% |

Verdict: concept valid, implementation too twitchy.

## QQQ v1b Refinement

QQQ v1b added:

- 3-day entry confirmation;
- 2-day exit confirmation;
- softened 21-day early exit;
- 10-trading-day minimum hold intent.

## QQQ v1b Standalone Result

| Metric | QQQ v1 | QQQ v1b |
|---|---:|---:|
| Total Return | +348.15% | +306.79% |
| CAGR | +7.29% | +6.80% |
| MaxDD | -22.12% | -26.62% |
| Sharpe | 0.634 | 0.589 |
| Calmar | 0.330 | 0.256 |
| Annualized Volatility | 12.33% | Not materially improved |
| Trades | 467 | 157 |

QQQ v1b significantly reduced turnover, but worsened drawdown and risk-adjusted efficiency. It is cleaner mechanically but too lagged as a standalone strategy.

Standalone verdict:

```text
QQQ v1b is not promoted as a standalone sleeve.
```

## Three-Sleeve Portfolio Test

The portfolio-level test combined:

```text
Crypto Sleeve v1
SPY Equity Sleeve v1
QQQ Growth Sleeve v1b
```

Test window:

```text
2019-03-08 → 2025-12-31
1715 daily bars
Initial capital: $100,000
```

Primary tested allocation:

```text
60% Crypto / 25% SPY / 15% QQQ
```

## Primary Three-Sleeve Result

| Series | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| Crypto Sleeve | +215.14% | +18.34% | -17.72% | 1.166 | 1.035 | 15.49% |
| SPY Sleeve | +85.39% | +9.48% | -17.31% | 0.986 | 0.547 | 9.68% |
| QQQ Sleeve | +99.72% | +10.68% | -19.57% | 0.777 | 0.546 | 14.44% |
| Itera 3-Sleeve | +165.39% | +15.39% | -13.91% | 1.292 | 1.106 | 11.63% |

## Correlation

| Pair | Daily Return Correlation |
|---|---:|
| Crypto vs SPY | +0.103 |
| Crypto vs QQQ | +0.099 |
| SPY vs QQQ | +0.795 |

Interpretation:

QQQ is highly correlated with SPY, but it is not materially correlated with the crypto sleeve over this test window. Its portfolio value comes from adding a different equity expression while remaining diversifying relative to crypto.

## Allocation Sweep

| Crypto | SPY | QQQ | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 70% | 30% | 0% | +176.21% | +16.07% | -15.48% | 1.252 | 1.038 | 12.56% |
| 65% | 25% | 10% | +171.16% | +15.76% | -14.61% | 1.274 | 1.078 | 12.08% |
| 60% | 25% | 15% | +165.39% | +15.39% | -13.91% | 1.292 | 1.106 | 11.63% |
| 60% | 20% | 20% | +166.10% | +15.44% | -13.78% | 1.290 | 1.120 | 11.68% |
| 55% | 25% | 20% | +159.62% | +15.02% | -13.42% | 1.306 | 1.119 | 11.22% |
| 50% | 30% | 20% | +153.13% | +14.59% | -13.03% | 1.321 | 1.120 | 10.78% |
| 50% | 25% | 25% | +153.84% | +14.64% | -12.89% | 1.316 | 1.136 | 10.86% |
| 50% | 20% | 30% | +154.56% | +14.69% | -12.76% | 1.310 | 1.151 | 10.95% |
| 40% | 40% | 20% | +140.15% | +13.71% | -12.19% | 1.341 | 1.125 | 9.98% |

## Portfolio-Level Interpretation

Compared with the 70/30 Crypto/SPY baseline:

```text
70/30 baseline:
CAGR   +16.07%
MaxDD  -15.48%
Sharpe  1.252
Calmar  1.038

60/20/20 three-sleeve candidate:
CAGR   +15.44%
MaxDD  -13.78%
Sharpe  1.290
Calmar  1.120
```

The QQQ sleeve does not improve raw CAGR, but it improves drawdown, Sharpe, and Calmar in several portfolio configurations.

The strongest crypto-forward three-sleeve candidate is:

```text
60% Crypto / 20% SPY / 20% QQQ
```

It preserves the Itera crypto-forward thesis while improving risk-adjusted portfolio quality versus the 70/30 two-sleeve baseline.

## Decision

QQQ v1b is **not promoted as a standalone sleeve**.

However, QQQ v1b is preserved as a **candidate small-allocation growth equity sleeve** for further portfolio-level testing.

Recommended status:

```text
QQQ Growth Sleeve v1b — candidate / watchlist
```

Recommended candidate allocation:

```text
60% Crypto / 20% SPY / 20% QQQ
```

## Next Research Question

The next step is not more QQQ tweaking immediately.

The next strategic question is whether Itera needs a more orthogonal third sleeve than QQQ. SPY and QQQ are highly correlated with each other, so a future volatility sleeve or regime-aware sleeve may provide more diversification than another equity-beta expression.

Recommended next work:

1. Preserve QQQ v1b as candidate / watchlist.
2. Explore Volatility Sleeve v1 as a distinct sleeve class.
3. Revisit HMM regime modeling after the sleeve universe is more complete.
