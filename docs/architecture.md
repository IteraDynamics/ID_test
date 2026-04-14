# IteraDynamics Architecture

## Overview

IteraDynamics is structured around three strictly separated layers. The
separation is enforced by convention and import discipline, not a framework:

```
research/ ──────── Layer 1 (Regime) + Layer 2 (Strategy) + Harness
runtime/  ──────── Layer 3 (Execution) only
```

No file in `research/` imports from `runtime/`.  
No file in `runtime/` imports from `research/harness/` (only regimes and strategies).

---

## Layer 1 — Regime Engine

**Location:** `research/regimes/`

**Purpose:** Classify market state from price data into discrete labels.

**Contract:**
- Input: OHLCV `pd.DataFrame`
- Output: `RegimeSignal` (one per bar) or `pd.Series[RegimeLabel]`
- No I/O. No broker calls. No mutable external state.

**Baseline implementation (`BaselineRegimeEngine`):**

Uses three independent sub-signals:
1. **EMA spread** (`fast_ema=21`, `slow_ema=55`): direction of trend.
2. **ATR as % of close** (`period=14`): volatility level.
3. **Slow EMA rate-of-change** (`lookback=5`): trend momentum.

Classification priority:
```
HIGH_VOL        (atr_pct > 4%)
VOL_EXPANSION   (atr_pct > 2.5% AND accelerating > 10%)
VOL_COMPRESSION (atr_pct < 1.2%)
TREND_UP        (fast > slow AND positive momentum)
TREND_DOWN      (fast < slow AND negative momentum)
RANGE           (no dominant signal)
UNKNOWN         (warmup period)
```

**Extension:**  
Implement `classify_bar(df, i) -> RegimeSignal` and `classify_dataframe(df) -> list[RegimeSignal]`
on a custom class. Pass it to `compute_regime_series(df, engine=...)`.

---

## Layer 2 — Strategy Modules

**Location:** `research/strategies/`

**Purpose:** Translate regime + OHLCV data into a trade intent signal.

**Contract:**
```python
generate_intent(df: pd.DataFrame, ctx: StrategyContext, closed_only: bool = True) -> StrategyIntent
```

**StrategyContext** (inputs):
- `regime: RegimeLabel` — current market regime (from Layer 1)
- `current_exposure_frac: float` — current portfolio exposure [0, 1]
- `asset: str`
- `bar_index: int`
- `meta: dict` — optional extras

**StrategyIntent** (outputs):
- `action: Action` — ENTER_LONG / EXIT_LONG / HOLD / FLAT
- `confidence: float` — [0, 1] signal quality
- `desired_exposure_frac: float` — [0, 1] requested position size
- `horizon_hours: int` — advisory holding period
- `reason: str` — human-readable explanation
- `strategy_id: str` — audit identifier

**Rules:**
- Pure functions. No I/O. No hidden state.
- `desired_exposure_frac` must be 0.0 when action is EXIT/FLAT.
- Strategy IDs are stable strings (used in audit logs).

### Strategy Summary

| Module | Key Indicators | Entry Regime | Exit Trigger |
|--------|---------------|-------------|-------------|
| `trend_following` | Dual EMA, EMA spread momentum | TREND_UP | TREND_DOWN, HIGH_VOL, EMA cross |
| `volatility_breakout` | ATR-band breakout, vol surge | VOL_COMPRESSION, RANGE | HIGH_VOL, price < midpoint |
| `mean_reversion` | RSI-14, Bollinger position | RANGE, VOL_COMPRESSION | RSI > 55, price > BB mid |

---

## Layer 3 — Runtime (Argus)

**Location:** `runtime/argus/`

**Purpose:** Orchestrate signals → governance → execution → state persistence.

### Components

#### DrawdownGovernor
Tracks high-water mark. Halts new BUY when `(NAV - HWM) / HWM < -halt_threshold`.
Clears halt when drawdown recovers below `recovery_threshold`. SELL always passes.

#### ExposureGovernor
Enforces:
- `max_portfolio_exposure` cap.
- `max_strategy_exposure` cap per sleeve.
- `min_trade_notional` — suppresses micro orders.
- Low-confidence filter: blocks intents below `confidence < 0.35`.
- UNKNOWN-regime fail-closed: blocks new entries when regime is UNKNOWN and flat.

#### PortfolioAllocator
Receives `[(StrategyIntent, weight), ...]`. Normalises weights. Computes
weighted blend of `desired_exposure_frac`. Consults both governors. Returns
`AllocationDecision(target_exposure, action, reason, approved)`.

#### PaperBroker
In-memory simulation. Orders fill immediately at submitted price ± slippage.
Fee deducted from notional. Maintains cash and position balances. Full fill history.

#### Orchestrator
The main runtime loop:
```
1. update_nav() → DrawdownGovernor.update()
2. generate_signals() → SignalBundle (Layer 1 + Layer 2)
3. allocator.allocate() → AllocationDecision
4. If approved: broker.submit_and_fill()
5. RuntimeState.save()
```

---

## Data Flow

```
CSV / Exchange Feed
      │
      ▼
 data_loader.load_ohlcv()          (research/harness)
      │
      ▼
 BaselineRegimeEngine.classify_bar()    (Layer 1)
      │
      ▼  RegimeSignal
 strategy.generate_intent()              (Layer 2)
      │
      ▼  StrategyIntent
 PortfolioAllocator.allocate()           (Layer 3)
      │
      ▼  AllocationDecision
 PaperBroker.submit_and_fill()           (Layer 3)
      │
      ▼
 RuntimeState.save()
```

---

## Research Harness

The harness (`research/harness/`) runs backtests without any Layer 3 machinery:

```
load_ohlcv() → validate_ohlcv()
      │
      ▼
run_backtest(df, strategy_module)
      │
      ▼  BacktestResult
compute_metrics(equity_curve, trades)
      │
      ▼  BacktestMetrics
save_artifacts(result, metrics)
```

Guarantees:
- Deterministic: same seed / same data → identical output.
- No lookahead: `strategy.generate_intent(df.iloc[:i+1], ctx)` for each bar `i`.
- Fees and slippage applied on every simulated trade.

---

## Adding Multi-Asset Support

The architecture is asset-agnostic by design:
- `StrategyContext.asset: str` passes the asset label into strategies.
- `PaperBroker` tracks positions per asset in `self._positions: dict[str, float]`.
- `Orchestrator.__init__` takes `asset: str` — instantiate one per asset.
- The harness CLI accepts `--asset` flag.

For a multi-asset portfolio, instantiate N orchestrators and a cross-asset
portfolio governor (not yet implemented — planned extension).
