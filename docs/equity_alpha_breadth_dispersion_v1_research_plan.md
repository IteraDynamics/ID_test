# Equity Alpha v1 — Breadth / Dispersion / Leadership Fragility Research Plan

## Status

**Branch:** `research/equity-alpha-breadth-dispersion-v1`

**Purpose:** Begin a true equity alpha search by studying market-structure signals rather than adding more vanilla trend or rotation variants.

**Guardrail:** Research-only. This branch does not approve paper trading, live allocation, broker/execution changes, runtime changes, dashboard changes, crypto allocator changes, or global crypto/equity allocator changes.

## Why This Exists

Prior merged equity work established a credible base:

```text
Equity Core v1:
  SPY/QQQ SMA175 trend-risk book

Defensive Carry Enhancement:
  short-duration Treasury proxy risk-off family
  primary practical candidate: BIL
  best recent-history candidate: SGOV
  secondary practical candidate: SHV
```

A first simple sector rotation test was intentionally vanilla: top sector momentum, sector SMA filter, optional SPY filter, risk-off to cash/BIL. It did not beat Equity Core + BIL.

That result suggests the next alpha search should not simply add more sector-rotation parameters. Instead, the research should ask whether market structure contains predictive information that a core trend book misses.

## Research Thesis

Markets with broad, healthy participation may behave differently from markets led by narrow, fragile leadership.

Markets with high sector dispersion may offer more opportunity for selection/rotation than markets where all sectors move together.

Therefore, the first alpha question is:

```text
Can ETF-based breadth, leadership, and dispersion signals classify equity regimes that predict forward returns or drawdown risk better than price trend alone?
```

## Initial Signal Families

### 1. Breadth Proxy

Use sector ETFs as a lightweight breadth proxy:

```text
sector_count_above_sma200
sector_pct_above_sma200
sector_count_positive_126d_momentum
sector_pct_positive_126d_momentum
```

Interpretation:

```text
Higher breadth = healthier participation.
Lower breadth = fragile or deteriorating market.
```

### 2. Leadership Fragility

Use cap-weight versus equal-weight / broad-index relationships:

```text
SPY / RSP ratio
QQQ / SPY ratio
XLK / SPY ratio
```

Optional if data exists:

```text
QQQE / QQQ ratio
```

Interpretation:

```text
Strong cap-weight leadership with weak breadth may indicate narrow leadership.
QQQ leadership with weak sector breadth may indicate concentration risk.
```

### 3. Sector Dispersion

Measure cross-sectional sector opportunity:

```text
std of sector 63d returns
std of sector 126d returns
top-minus-bottom sector 126d momentum spread
average pairwise sector correlation over 63d returns
```

Interpretation:

```text
Higher dispersion may create more opportunity for rotation.
Lower dispersion may make sector selection less useful.
```

### 4. Forward Return Diagnostics

For each signal regime, evaluate forward returns for:

```text
SPY
QQQ
SPY/QQQ 50/50
Equity Core SMA175 cash-risk-off
Equity Core SMA175 BIL-risk-off, if BIL data exists
```

Forward horizons:

```text
21 trading days
63 trading days
126 trading days
```

## Initial Regime Buckets

Use simple quantile buckets first:

```text
low / mid / high sector breadth
low / mid / high sector dispersion
healthy breadth + high QQQ leadership
weak breadth + high QQQ leadership
high dispersion vs low dispersion
```

The goal is diagnostics, not immediate trading.

## Outputs

The first diagnostic script should produce:

```text
artifacts/equity_alpha_breadth_dispersion_v1/
  daily_signal_panel.csv
  forward_return_by_regime.csv
  forward_return_by_quantile.csv
  regime_counts.csv
  performance_context_summary.csv
  skipped_assets.csv
  summary.json
  summary.md
```

## Success Criteria

This research family becomes interesting if it finds one or more regimes where:

```text
1. Forward returns differ materially across breadth/dispersion states.
2. Weak breadth + strong leadership predicts worse future risk-adjusted outcomes.
3. High dispersion identifies periods where sector selection/rotation has a better chance of working.
4. Signals provide information beyond SPY > SMA175 alone.
```

## Failure Criteria

Demote this alpha family if:

```text
1. Signal buckets show little or no forward-return separation.
2. Effects vanish across horizons.
3. Results are driven only by short-history assets like XLC/XLRE.
4. Signals are too correlated with the existing Equity Core trend filter to add value.
```

## Non-Goals

```text
No trading strategy yet.
No parameter optimization.
No ML model.
No paper trading.
No live trading.
No broker integration.
No dashboard integration.
No global allocator.
No individual stock selection.
```

## Bottom Line

This is the first true equity alpha search layer. The goal is to discover whether equity market structure — breadth, leadership fragility, and dispersion — contains predictive information worth converting into a future sleeve or governor.
