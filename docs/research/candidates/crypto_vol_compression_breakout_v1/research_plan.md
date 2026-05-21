# Crypto Volatility Compression Breakout v1 — Research Plan

## Purpose

This candidate is a true-alpha research lane.

It is not a defensive parking rule and not a long-only asset allocation rule.

The research question:

```text
After volatility compresses, can Itera capture directional expansion with defined risk better than passive BTC/ETH exposure?
```

## Candidate Classification

```text
Research lane: Alpha-seeking crypto strategy
Candidate type: Volatility compression / breakout
Architecture role: Potential Layer 2 StrategyIntent module
Status: NEW RESEARCH CANDIDATE
```

## Why This Is Different

Recent candidates were mostly allocation or defense:

```text
GLD/BIL: defensive destination overlay
BTC/ETH relative strength: active crypto beta / selection
Risk-budgeted relative strength: governed participation sleeve
```

This candidate is different. It looks for a repeatable behavior:

```text
quiet volatility regime -> directional range expansion -> tradable breakout
```

That makes it more plausibly alpha-seeking.

## Hypothesis

Periods of compressed realized volatility sometimes precede directional expansion. A breakout rule that only activates after compression may have better expectancy than always-on trend exposure.

Hypothesis:

```text
Volatility-compression breakouts can improve risk-adjusted returns versus buy-and-hold and static crypto exposure.
```

Null hypothesis:

```text
The breakout rule mostly repackages crypto beta, whipsaws after false breakouts, or only works in hindsight.
```

## First-Pass Strategy Physics

For each asset independently:

```text
1. Compute rolling realized volatility.
2. Define compression when volatility is in a low percentile of its recent history.
3. Compute rolling high / low channel.
4. Enter long when price breaks above the recent channel while compression is active or recently active.
5. Exit on trailing stop, channel failure, time stop, or volatility regime failure.
```

Initial assets:

```text
BTC
ETH
```

Initial side:

```text
long only
```

Shorting is intentionally excluded from first pass.

## Initial Variant Grid

Compression lookbacks:

```text
60d
90d
120d
```

Compression percentile thresholds:

```text
20th percentile
30th percentile
```

Breakout channel lengths:

```text
20d
30d
40d
```

Exit styles:

```text
channel_low_exit
trailing_stop
time_stop
```

First-pass implementation may start with a smaller grid and expand only if warranted.

## Required Metrics

Each variant should report:

```text
CAGR
Max drawdown
Sharpe
Calmar
final NAV
trade count
win rate
average trade return
median trade return
average holding days
exposure percentage
crash-window return
bull-window return
```

## Correct Benchmarks

Compare against:

```text
BTC buy-and-hold
ETH buy-and-hold
50/50 BTC/ETH static blend
cash
```

If later combined with Fund v1, compare against Fund v1 separately.

## Alpha-Specific Promotion Criteria

A candidate should only advance if it shows evidence of at least some of the following:

```text
positive expectancy per trade
reasonable trade count
improved Sharpe or Calmar versus buy-and-hold
meaningfully lower drawdown than buy-and-hold
not dependent on one isolated period
not simply always-long crypto beta
```

High CAGR alone is not enough.

## Required Follow-Up If Promising

```text
subperiod validation
train/test split
rolling walk-forward
transaction cost sensitivity
parameter stability review
trade attribution by regime
```

## Initial Script Target

```text
scripts/run_crypto_vol_compression_breakout.py
```

Expected outputs:

```text
artifacts/crypto_vol_compression_breakout/results.csv
artifacts/crypto_vol_compression_breakout/trades.csv
artifacts/crypto_vol_compression_breakout/equity_curves.csv
artifacts/crypto_vol_compression_breakout/summary.md
artifacts/crypto_vol_compression_breakout/summary.json
```

## Boundary

```text
RESEARCH ONLY
NO RUNTIME WORK
NO BROKER WORK
NO LIVE PORTFOLIO INTEGRATION
```
