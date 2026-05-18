# Itera Allocator v1 — Research Results

## Status

Research experiment complete. Allocator v1 is **not promoted** as the active Itera Fund allocator.

Allocator v1 was tested as a dynamic capital-weighting layer between:

- Crypto Sleeve v1
- Equity Sleeve v1

The purpose was to test whether a simple dynamic relative-strength allocator could improve on the Itera Fund v0 static allocation baseline.

## Accounting Correction

The first allocator runner used an invalid portfolio accounting model. It effectively revalued the full portfolio each day using the newly selected weights against the full sleeve index history.

That was incorrect.

The corrected runner now uses proper no-lookahead daily portfolio accounting:

```text
nav[t] = nav[t-1] * (1 + w_crypto[t-1] * r_crypto[t] + w_equity[t-1] * r_equity[t])
```

New weights are decided after the close using data through `t` and apply to the next day's returns.

This corrected model is the valid basis for evaluating Allocator v1.

## Test Window

```text
2019-03-08 → 2025-12-31
1715 daily bars
Initial capital: $100,000
```

## Corrected Results

| Series | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| Allocator v1 | +171.75% | +15.79% | -14.42% | 1.310 | 1.095 | 11.75% |
| Static 70/30 | +174.56% | +15.97% | -14.02% | 1.347 | 1.139 | 11.51% |
| Static 60/40 | +161.18% | +15.12% | -13.10% | 1.405 | 1.154 | 10.43% |
| Static 50/50 | +147.94% | +14.25% | -12.25% | 1.446 | 1.163 | 9.55% |

## Delta vs Static 70/30

| Metric | Allocator v1 Delta |
|---|---:|
| CAGR | -0.17% |
| MaxDD | -0.41% |
| Sharpe | -0.037 |
| Calmar | -0.044 |

## Allocator Activity

| Metric | Value |
|---|---:|
| Average Crypto Weight | 68.1% |
| Weight Switches | 35 |
| Crypto 50% Weight Days | 310 |
| Crypto 70% Weight Days | 1103 |
| Crypto 80% Weight Days | 302 |

## Verdict

Allocator v1 does **not** improve on the static Itera Fund v0 baseline.

The corrected test shows Allocator v1 is close to the 70/30 static baseline, but worse across the primary metrics:

- lower CAGR
- deeper drawdown
- lower Sharpe
- lower Calmar
- higher annualized volatility

The conclusion is not that dynamic allocation is useless. The conclusion is that this particular relative-strength allocator adds complexity without improving the portfolio.

## Interpretation

The static blends are already strong. In this test, the simple static allocations were hard to beat:

- 70/30 remains the flagship crypto-forward baseline.
- 60/40 and 50/50 show stronger risk-adjusted metrics.
- Allocator v1 failed to justify replacing any of them.

Allocator v1 behaved as a modest relative-strength allocator, but the shifts were not valuable enough to overcome the stability of static allocation.

## Decision

Allocator v1 should be archived as a failed/neutral prototype.

It should not be promoted to:

- Itera Fund v1
- production allocator logic
- paper trading allocator logic
- live trading allocator logic

## Next Allocator Direction

The next allocator experiment should not be another relative-strength allocator.

The better next design is **Allocator v2: Defensive Overlay Allocator**.

Allocator v2 should start from a strong static baseline and only intervene during adverse conditions.

Suggested design principle:

```text
Default: static 70/30 or 60/40
Only shift defensively when crypto sleeve quality deteriorates materially
Otherwise do nothing
```

Potential triggers:

- crypto sleeve drawdown threshold
- crypto trend deterioration
- crypto volatility expansion
- both sleeves risk-off
- portfolio-level drawdown governor

Allocator v2 should have a stricter mandate:

```text
Do not try to be smart every day.
Only act when risk conditions justify intervention.
```

## Baseline Preservation

Itera Fund v0 remains the control group.

Allocator v1's failure reinforces the importance of preserving static baselines before introducing dynamic intelligence.
