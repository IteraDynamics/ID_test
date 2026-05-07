# Fund Side-by-Side Composite v1 — Findings

## Status

**Branch:** `research/fund-side-by-side-composite-v1`

**Research status:** static side-by-side crypto/equity fund composite tested.

**Runtime status:** no paper-trading, broker, execution, governor, live allocation, crypto runtime, dashboard, or global allocator changes approved.

## Executive Summary

This research tests a fund-level investor view, not a dynamic allocator.

The current operating architecture remains:

```text
Crypto systems run independently.
Equity systems run independently.
No central dynamic allocator decides which sleeve gets capital each bar.
```

This test asks a separate reporting/product question:

```text
If Itera's crypto and equity systems ran side by side under static capital weights, what would the total fund return stream look like?
```

The answer is strong.

A static crypto/equity composite materially improved the fund-level return path versus either standalone sleeve and versus passive equity benchmarks on risk-adjusted metrics.

The cleanest candidate is:

```text
50% crypto / 50% equity
```

A secondary candidate is:

```text
60% crypto / 40% equity
```

The 70/30 crypto-heavy configuration adds only marginal CAGR while weakening drawdown-adjusted return quality.

## Inputs Tested

### Equity Sleeve

The equity sleeve was computed from local data as:

```text
SPY/QQQ SMA175 with BIL risk-off
```

This reflects the merged Equity Core + Defensive Carry findings.

### Crypto Sleeve Pass 1

```text
artifacts/crypto_risk_budget_v2_capture_audit/equity_curves.csv::Fund_v1
```

### Crypto Sleeve Pass 2

```text
artifacts/fund_tilted_cal_4s_2019-03-08_2025-12-31/equity_curves.csv::portfolio
```

The tilted 4-sleeve crypto pass is treated as the more current fund-composite read because it reflects the later calibrated multi-sleeve crypto structure.

## Common Test Window

Both runs used the same common overlap:

```text
2019-03-08 → 2025-12-30
1714 bars
```

## Primary Result — Tilted 4-Sleeve Crypto Composite

### 50/50 Composite

```text
FUND_STATIC_CRYPTO50_EQUITY50
CAGR:   18.3230%
MaxDD: -14.1536%
Sharpe: 1.6165
Sortino: 2.5123
Calmar: 1.2946
AnnVol: 10.7974%
Worst 90d:  -10.0847%
Worst 180d: -11.2221%
Max time underwater: 597 days
```

### 60/40 Composite

```text
FUND_STATIC_CRYPTO60_EQUITY40
CAGR:   18.4242%
MaxDD: -14.6921%
Sharpe: 1.5640
Sortino: 2.5157
Calmar: 1.2540
AnnVol: 11.2456%
Worst 90d:  -10.5350%
Worst 180d: -12.3697%
Max time underwater: 611 days
```

### 70/30 Composite

```text
FUND_STATIC_CRYPTO70_EQUITY30
CAGR:   18.4727%
MaxDD: -15.4353%
Sharpe: 1.4701
Sortino: 2.4224
Calmar: 1.1968
AnnVol: 12.0553%
Worst 90d:  -10.9935%
Worst 180d: -13.5157%
Max time underwater: 749 days
```

## Standalone Sleeve Context

### Crypto Sleeve

```text
CRYPTO_SLEEVE
CAGR:   18.3028%
MaxDD: -18.8887%
Sharpe: 1.1331
Sortino: 1.8960
Calmar: 0.9690
AnnVol: 15.9956%
Worst 90d:  -12.8759%
Worst 180d: -16.9407%
Max time underwater: 773 days
```

### Equity Sleeve

```text
EQUITY_SLEEVE
CAGR:   17.0301%
MaxDD: -19.5271%
Sharpe: 1.1809
Sortino: 1.6338
Calmar: 0.8721
AnnVol: 14.2134%
Worst 90d:  -11.3816%
Worst 180d: -11.3650%
Max time underwater: 534 days
```

## Passive Equity Benchmark Context

### Passive SPY/QQQ 50/50

```text
PASSIVE_SPY_QQQ_50_50
CAGR:   18.9709%
MaxDD: -30.8583%
Sharpe: 0.9091
Sortino: 1.2897
Calmar: 0.6148
AnnVol: 21.7762%
Worst 90d:  -22.6223%
Worst 180d: -26.9892%
Max time underwater: 714 days
```

### QQQ Hold

```text
QQQ_HODL
CAGR:   21.5528%
MaxDD: -35.1187%
Sharpe: 0.9260
Sortino: 1.3190
Calmar: 0.6137
AnnVol: 24.3431%
Worst 90d:  -27.4273%
Worst 180d: -30.6605%
Max time underwater: 715 days
```

### SPY Hold

```text
SPY_HODL
CAGR:   16.2085%
MaxDD: -33.7172%
Sharpe: 0.8565
Sortino: 1.2085
Calmar: 0.4807
AnnVol: 19.9078%
Worst 90d:  -26.9131%
Worst 180d: -24.1425%
Max time underwater: 708 days
```

## Interpretation

The 50/50 side-by-side composite produced approximately the same CAGR as the standalone crypto sleeve, but with much better drawdown and volatility characteristics.

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

This is the desired portfolio effect:

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

Preferred language:

```text
From March 2019 through December 2025, a static 50/50 side-by-side composite of Itera's crypto and equity systems produced an 18.3% CAGR with a -14.2% max drawdown, 1.62 Sharpe, and 1.29 Calmar. Over the same window, passive SPY/QQQ 50/50 produced a slightly higher 19.0% CAGR but with a -30.9% max drawdown, 0.91 Sharpe, and 0.61 Calmar.
```

A shorter version:

```text
The side-by-side composite nearly matched passive SPY/QQQ 50/50 CAGR while reducing max drawdown by more than half and materially improving Sharpe and Calmar.
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
Crypto passive benchmarks should be included in a follow-up patch so the composite can be compared against BTC_HODL, ETH_HODL, BTC/ETH 50/50, and BTC/ETH 60/40.
No fees, taxes, slippage, custody, borrow, financing, or operational constraints are modeled unless already embedded in the source curves.
```

## Recommended Follow-Up

Patch the composite runner to automatically include crypto benchmark columns from the crypto source file when present:

```text
BTC_HODL
ETH_HODL
BTC_ETH_50_50_DAILY_REBAL
BTC_ETH_60_40_DAILY_REBAL
```

That will allow the fund-composite analysis to compare against:

```text
SPY/QQQ passive equity
SPY hold
QQQ hold
BTC hold
ETH hold
BTC/ETH passive crypto baskets
```

This is necessary before making any final fund-level market-beating or benchmark-relative claims.

## Bottom Line

This is the first result where Itera clearly looks like a fund rather than a set of isolated strategy tests.

The static 50/50 side-by-side composite nearly matched passive equity benchmark CAGR while producing a much cleaner return path. It also improved meaningfully over standalone crypto and standalone equity systems.

This supports a strong investor-facing claim:

```text
Itera's independent crypto and equity systems appear complementary when viewed as a static side-by-side fund composite.
```

It does not support a sloppy claim that Itera simply “beat the market” on raw return.

It does support a precise claim that Itera delivered a superior drawdown-adjusted return stream versus passive equity benchmarks over the tested window.
