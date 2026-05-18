# Fund Side-by-Side Composite v1 — Findings

## Status

**Branch:** `research/fund-side-by-side-composite-v1`

**Research status:** static crypto/equity side-by-side composite tested with equity, crypto, and passive benchmark comparisons.

**Runtime status:** no dynamic allocator, paper-trading, live allocation, broker/execution, dashboard, runtime, or global allocator changes approved.

## Executive Summary

This research tests an investor-facing fund view:

```text
Independent crypto system + independent equity system
viewed side by side under static capital weights
```

This is not a return to a dynamic allocator. The systems remain independently evaluated and separately executable. The composite answers a fund-performance question:

```text
If Itera ran crypto and equities in parallel, what would the total fund return stream look like?
```

The answer is strong: a static 50/50 crypto/equity composite materially improved fund-level return quality versus standalone crypto, standalone equity, and passive equity benchmarks. It did not beat passive crypto HODL baskets on raw return, but it avoided the extreme crypto drawdowns and volatility.

## Preferred Composite

Preferred initial fund composite:

```text
50% crypto sleeve
50% equity sleeve
```

Secondary candidate:

```text
60% crypto sleeve
40% equity sleeve
```

Demote:

```text
70% crypto / 30% equity
```

Reason: the 70/30 version adds only a small amount of CAGR while degrading Sharpe, Calmar, drawdown, and time-underwater behavior.

## Input Sleeves

### Crypto Input A

```text
artifacts/crypto_risk_budget_v2_capture_audit/equity_curves.csv::Fund_v1
```

This run includes passive crypto benchmarks from the same artifact:

```text
BTC_HODL
ETH_HODL
BTC_ETH_50_50_DAILY_REBAL
BTC_ETH_60_40_DAILY_REBAL
```

### Crypto Input B

```text
artifacts/fund_tilted_cal_4s_2019-03-08_2025-12-31/equity_curves.csv::portfolio
```

This artifact does not include passive BTC/ETH benchmark columns, so crypto passive benchmarks are skipped for that pass.

### Equity Input

Computed from local market data:

```text
SPY/QQQ SMA175 with BIL risk-off
```

Common overlap for both runs:

```text
2019-03-08 → 2025-12-30
1714 bars
```

## Result A — Crypto Risk Budget v2 Capture Audit Fund_v1

### 50/50 Composite

```text
FUND_STATIC_CRYPTO50_EQUITY50
CAGR:   18.25%
MaxDD: -14.14%
Sharpe: 1.563
Sortino: 2.356
Calmar: 1.291
AnnVol: 11.15%
Worst 90d:  -9.95%
Worst 180d: -10.45%
```

### Standalone Sleeves

```text
Crypto sleeve:
  CAGR:   18.35%
  MaxDD: -17.72%
  Sharpe: 1.167
  Calmar: 1.036

Equity sleeve:
  CAGR:   17.03%
  MaxDD: -19.53%
  Sharpe: 1.181
  Calmar: 0.872
```

### Passive Crypto Benchmarks

```text
BTC/ETH 50/50 daily rebalance:
  CAGR:   62.49%
  MaxDD: -76.34%
  Sharpe: 1.054
  Calmar: 0.819

BTC/ETH 60/40 daily rebalance:
  CAGR:   62.36%
  MaxDD: -76.30%
  Sharpe: 1.063
  Calmar: 0.817

BTC HODL:
  CAGR:   58.28%
  MaxDD: -76.67%
  Sharpe: 1.046
  Calmar: 0.760

ETH HODL:
  CAGR:   57.79%
  MaxDD: -78.44%
  Sharpe: 0.971
  Calmar: 0.737
```

### Passive Equity Benchmarks

```text
Passive SPY/QQQ 50/50:
  CAGR:   18.97%
  MaxDD: -30.86%
  Sharpe: 0.909
  Calmar: 0.615

QQQ HODL:
  CAGR:   21.55%
  MaxDD: -35.12%
  Sharpe: 0.926
  Calmar: 0.614

SPY HODL:
  CAGR:   16.21%
  MaxDD: -33.72%
  Sharpe: 0.857
  Calmar: 0.481
```

### Interpretation of Expanded Benchmarks

The 50/50 composite does not compete with passive BTC/ETH HODL baskets on raw CAGR. That is expected: passive crypto had enormous upside from 2019 through 2025.

The composite's value proposition is different:

```text
It captures an equity-like / fund-like CAGR profile with far lower drawdown and volatility than passive crypto.
```

Versus passive BTC/ETH 50/50 daily rebalance:

```text
50/50 Composite CAGR:       18.25%
BTC/ETH 50/50 CAGR:         62.49%

50/50 Composite MaxDD:     -14.14%
BTC/ETH 50/50 MaxDD:       -76.34%

50/50 Composite Sharpe:      1.563
BTC/ETH 50/50 Sharpe:        1.054

50/50 Composite Calmar:      1.291
BTC/ETH 50/50 Calmar:        0.819
```

This is not a raw-return victory versus crypto beta. It is a risk-adjusted and drawdown-control victory.

## Result B — Tilted 4-Sleeve Calibrated Portfolio

### 50/50 Composite

```text
FUND_STATIC_CRYPTO50_EQUITY50
CAGR:   18.32%
MaxDD: -14.15%
Sharpe: 1.617
Sortino: 2.512
Calmar: 1.295
AnnVol: 10.80%
Worst 90d:  -10.08%
Worst 180d: -11.22%
```

### Standalone Sleeves

```text
Crypto sleeve:
  CAGR:   18.30%
  MaxDD: -18.89%
  Sharpe: 1.133
  Calmar: 0.969

Equity sleeve:
  CAGR:   17.03%
  MaxDD: -19.53%
  Sharpe: 1.181
  Calmar: 0.872
```

### Passive Equity Benchmarks

```text
Passive SPY/QQQ 50/50:
  CAGR:   18.97%
  MaxDD: -30.86%
  Sharpe: 0.909
  Calmar: 0.615

QQQ HODL:
  CAGR:   21.55%
  MaxDD: -35.12%
  Sharpe: 0.926
  Calmar: 0.614

SPY HODL:
  CAGR:   16.21%
  MaxDD: -33.72%
  Sharpe: 0.857
  Calmar: 0.481
```

## Portfolio Effect

The 50/50 tilted 4-sleeve side-by-side composite produced approximately the same CAGR as the standalone crypto sleeve, but with much better drawdown and volatility characteristics.

```text
50/50 Composite vs Crypto Sleeve:
  CAGR:   18.32% vs 18.30%
  MaxDD: -14.15% vs -18.89%
  Sharpe: 1.62 vs 1.13
  Calmar: 1.29 vs 0.97
  AnnVol: 10.80% vs 16.00%
```

The 50/50 composite also materially improved on the standalone equity sleeve:

```text
50/50 Composite vs Equity Sleeve:
  CAGR:   18.32% vs 17.03%
  MaxDD: -14.15% vs -19.53%
  Sharpe: 1.62 vs 1.18
  Calmar: 1.29 vs 0.87
```

This is the desired fund-level portfolio effect:

```text
The combined fund stream is better than either standalone sleeve on risk-adjusted performance.
```

## Market-Beating Framing

This result should not be marketed as a vague claim that Itera “beat the market.”

Against passive SPY/QQQ 50/50 over the same window, the Itera 50/50 side-by-side composite did not win on raw CAGR:

```text
Itera 50/50 Composite CAGR:      18.32%
Passive SPY/QQQ 50/50 CAGR:     18.97%
```

But it decisively improved return quality:

```text
Itera 50/50 Composite MaxDD:    -14.15%
Passive SPY/QQQ 50/50 MaxDD:   -30.86%

Itera 50/50 Composite Sharpe:    1.62
Passive SPY/QQQ 50/50 Sharpe:   0.91

Itera 50/50 Composite Calmar:    1.29
Passive SPY/QQQ 50/50 Calmar:   0.61

Itera 50/50 Composite AnnVol:   10.80%
Passive SPY/QQQ 50/50 AnnVol:  21.78%
```

Preferred wording:

```text
From March 2019 through December 2025, a static 50/50 side-by-side composite of Itera's crypto and equity systems produced an 18.3% CAGR with a -14.2% max drawdown, 1.62 Sharpe, and 1.29 Calmar. Over the same window, passive SPY/QQQ 50/50 produced a slightly higher 19.0% CAGR but with a -30.9% max drawdown, 0.91 Sharpe, and 0.61 Calmar.
```

For crypto benchmarks, use precise language:

```text
The composite did not match passive BTC/ETH raw returns during the 2019–2025 crypto bull-cycle window, but it delivered a much smoother return stream with dramatically lower drawdown, lower volatility, and better Sharpe/Calmar than passive BTC/ETH baskets.
```

## Weight Selection

### Preferred Initial Composite: 50/50

The 50/50 composite is the cleanest headline profile:

```text
CAGR:   18.32%
MaxDD: -14.15%
Sharpe: 1.62
Calmar: 1.29
```

It has the best balance of return, drawdown, volatility, and simplicity.

### Secondary Candidate: 60/40

The 60/40 composite offers slightly higher CAGR:

```text
CAGR:   18.42%
MaxDD: -14.69%
Sharpe: 1.56
Calmar: 1.25
```

This may be appropriate if the mandate prioritizes incremental return while accepting slightly weaker risk-adjusted metrics.

### Demote: 70/30

The 70/30 crypto-heavy composite is not compelling enough versus 50/50 or 60/40:

```text
CAGR:   18.47%
MaxDD: -15.44%
Sharpe: 1.47
Calmar: 1.20
```

The incremental CAGR is small, while Sharpe, Calmar, worst-window behavior, and time underwater deteriorate.

### Demote: 30/70

The 30/70 equity-heavy composite remains strong but is weaker than 50/50:

```text
CAGR:   17.96%
MaxDD: -15.83%
Sharpe: 1.54
Calmar: 1.13
```

## Research Decision

Promote this finding:

```text
A static side-by-side crypto/equity composite materially improves Itera's fund-level risk-adjusted return profile without requiring a dynamic allocator.
```

Preferred initial fund-composite view:

```text
50% crypto / 50% equity
```

Secondary candidate:

```text
60% crypto / 40% equity
```

Do not promote 70/30 as the primary profile because it does not provide enough incremental return for the deterioration in return quality.

## Important Caveats

```text
This is research-only.
The composite is a reporting/product view, not a live allocation system.
The result depends on the validity of the underlying crypto and equity sleeve curves.
The window starts in March 2019, not 2005, because the crypto sleeve begins in 2019.
No fees, taxes, slippage, custody, borrow, financing, or operational constraints are modeled unless already embedded in the source curves.
```

## Guardrails

```text
No dynamic allocator.
No paper trading.
No live trading.
No broker integration.
No runtime integration.
No dashboard integration.
No capital-routing engine.
No optimizer.
```

## Bottom Line

The fund side-by-side composite is highly promising.

The cleanest result is a 50/50 static composite of the crypto sleeve and Equity Core + BIL. It nearly matches passive SPY/QQQ 50/50 raw CAGR while producing a dramatically better drawdown-adjusted return stream.

This supports a strong investor-facing claim:

```text
Itera's independent crypto and equity systems appear complementary when viewed as a static side-by-side fund composite.
```

It does not support a sloppy claim that Itera simply “beat the market” on raw return.

It does support a precise claim that Itera delivered a superior drawdown-adjusted return stream versus passive equity benchmarks over the tested window, and a much smoother risk-adjusted return profile than passive BTC/ETH crypto beta.
