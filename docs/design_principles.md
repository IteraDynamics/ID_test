# IteraDynamics Design Principles

These principles govern every architectural decision in the platform.

---

## 1. Determinism above all

Every compute path must be deterministic given the same inputs.
- No `datetime.now()` inside strategy logic.
- No random seeding inside production code paths.
- No hash-based non-determinism.
- Same data → same regime series → same intents → same equity curve.

This is the foundation of trustable backtesting.

---

## 2. Closed-bar logic only

Signals are generated after a bar closes. Never intra-bar.

The `closed_only=True` parameter on `generate_intent()` is a contract-level
signal to callers and auditors that no current-bar data is consumed.

---

## 3. No lookahead

At bar index `i`, only `df.iloc[:i+1]` is visible to any Layer 1 or Layer 2
function. This is enforced by the backtest engine's slicing:

```python
df_slice = df.iloc[:i + 1]
intent = strategy.generate_intent(df_slice, ctx)
```

Vectorised indicator pre-computation uses rolling windows, not future data.

---

## 4. Layer separation is mandatory

Research code (`research/`) **never** imports from `runtime/`.  
Runtime code (`runtime/`) **never** imports from `research/harness/`.

The regime engine and strategy modules are the only research components
visible to the runtime.

---

## 5. Fail-closed governance

When in doubt, do nothing and stay safe.

- UNKNOWN regime + no position = block entry.
- Low confidence = block entry.
- Drawdown halt = block entry.
- Sell / de-risk paths are **never** blocked by buy-side governors.

The system will miss opportunities before it will take uncontrolled risk.

---

## 6. Strategies have no state

A strategy module is stateless between calls. It may not:
- Mutate any object passed in.
- Write to files.
- Hold module-level mutable state.
- Call brokers or external APIs.

All state visible to a strategy is passed explicitly in `df` and `ctx`.

---

## 7. Runtime is the only execution point

Only `runtime/argus/` executes trades or persists live state. This is a hard
boundary. Research code can **simulate** trades (harness) but never execute them.

---

## 8. Every decision is auditable

- `RegimeSignal.sub_signals` contains all indicator values used for classification.
- `StrategyIntent.reason` contains a human-readable explanation.
- `AllocationDecision.reason` contains the governor/allocator rationale.
- `TradeRecord` contains full context for every simulated trade.
- `RuntimeState` is persisted to JSON on every live cycle.

---

## 9. Simplicity over cleverness

Three similar lines of code is better than a premature abstraction.
Build for the problem at hand. The right abstraction emerges from concrete implementations.

---

## 10. Practical extensibility

The platform is designed to grow from BTC-only to multi-asset:
- Asset label flows through `StrategyContext.asset` and `Orchestrator.asset`.
- Strategy modules don't hardcode BTC-specific prices or thresholds.
- The broker interface is exchange-agnostic.
- Regime labels are shared vocabulary across all assets.
