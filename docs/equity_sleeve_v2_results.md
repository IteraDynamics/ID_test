# Equity Sleeve v2 — Partial Exposure Research Results

## Status

Research experiment complete. Equity Sleeve v2 is **not promoted** in its current form.

Equity Sleeve v2 tested whether partial exposure states could improve Equity Sleeve v1's upside participation while preserving its defensive profile.

## Hypothesis

Equity Sleeve v1 is a simple defensive trend sleeve. It protects capital well but under-participates in strong equity recoveries and bull markets.

Equity Sleeve v2 tested a partial exposure model:

```text
0% / 40% / 80% / 100% exposure
```

The goal was to improve CAGR and total return without materially weakening drawdown protection, Sharpe, or Calmar.

## Design Summary

Equity Sleeve v2 scores the daily SPY trend using four components:

```text
price > EMA200
EMA50 > EMA200
63-day momentum > 0
21-day momentum > 0
```

Exposure mapping:

```text
Score 4 → 100% exposure
Score 3 → 80% exposure
Score 2 with price above EMA200 → 40% exposure
Score 0–1 → 0% exposure
```

The strategy is long-only, daily, no leverage, and no shorting.

## Test Window

```text
2005-01-03 → 2026-04-29
5364 daily bars
Initial capital: $100,000
```

## Results

| Metric | Equity Sleeve v1 | Equity Sleeve v2 | Interpretation |
|---|---:|---:|---|
| Total Return | +227.88% | +289.89% | v2 improves raw return |
| CAGR | +5.73% | +6.59% | v2 improves CAGR |
| MaxDD | -17.31% | -22.99% | v2 materially worsens drawdown |
| Sharpe | 0.685 | 0.692 | essentially flat |
| Calmar | 0.331 | 0.287 | v2 worsens Calmar |
| Annualized Volatility | 8.70% | 9.96% | v2 increases volatility |

## Activity

| Metric | Value |
|---|---:|
| Trades / Rebalances | 1,634 |
| Exposure Time | 78.1% |
| Average Exposure | 70.2% |
| 0% Exposure Days | 1,173 |
| 40% Exposure Days | 378 |
| 80% Exposure Days | 990 |
| 100% Exposure Days | 2,823 |

## Verdict

Equity Sleeve v2 is **not promoted**.

It validates the partial exposure concept directionally: total return and CAGR improved versus Equity Sleeve v1. However, the improvement came at an unacceptable cost:

- max drawdown worsened by more than 5 percentage points;
- Calmar declined;
- volatility increased;
- Sharpe barely improved;
- rebalance count exploded to 1,634.

The v2 strategy is too sensitive and behaves more like a daily rebalancing machine than a clean institutional equity sleeve.

## Interpretation

The idea is not dead. The implementation is too loose.

The partial exposure framework can help solve Equity Sleeve v1's under-participation problem, but the current version lacks sufficient state discipline and rebalance guardrails.

The primary flaw is daily target-maintenance behavior. The strategy should not rebalance constantly just to maintain exact target exposure.

## Decision

Equity Sleeve v1 remains the active equity baseline.

Equity Sleeve v2 should be archived as a near-miss / rejected prototype.

It should not replace Equity Sleeve v1 in:

- Itera Fund v0 baseline testing;
- multi-asset allocation sweeps;
- paper trading;
- live trading;
- production fund logic.

## Next Direction: Equity Sleeve v2b

The next equity experiment should preserve the partial exposure idea but add stronger state discipline.

Recommended design principles:

```text
Partial exposure is allowed.
Daily target maintenance is not.
Exposure changes must be state transitions.
```

Suggested v2b rules:

- same broad trend scoring concept;
- rebalance only when target exposure changes by at least 20 percentage points;
- treat 0% / 40% / 80% / 100% as discrete states, not continuously maintained targets;
- hard defensive rule: if price < EMA200 and EMA50 < EMA200, exposure must be 0%;
- optional drawdown guardrail before allowing 40% partial exposure;
- reduce churn before optimizing returns.

## Success Criteria for v2b

Equity Sleeve v2b should be judged against Equity Sleeve v1, not SPY buy-and-hold.

Minimum promotion criteria:

```text
CAGR > Equity v1
MaxDD no worse than roughly -18% to -19%
Sharpe >= Equity v1
Calmar >= Equity v1
Rebalances materially below v2
```

If v2b cannot improve upside participation without materially damaging the defensive profile, Equity Sleeve v1 should remain the baseline.
