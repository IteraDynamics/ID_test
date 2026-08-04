# Campaign #52 Capture/Replay Adapter Implementation

## Status

Research-only implementation completed for synthetic validation. No governed Campaign #52 source was loaded or executed, and no governed Core target, trade, exposure, cost, return, NAV, or performance outcome was generated or inspected.

## Implementation

Adapter:

- `research/harness/campaign52_target_replay.py`

Synthetic tests:

- `tests/test_campaign52_target_replay.py`

The implementation is additive. It does not modify:

- `research/harness/backtest_engine.py`;
- any strategy module;
- regime logic;
- execution settings;
- thresholds;
- cooldowns;
- costs;
- sleeve weights;
- walk-forward folds;
- runtime behavior.

## Capture mode

Capture mode calls the supplied strategy at each closed native bar using the same causal context pattern as the canonical engine. It converts the resulting `StrategyIntent` into a signed pre-execution target:

- `ENTER_LONG` -> positive capped desired exposure;
- `ENTER_SHORT` -> negative capped desired exposure;
- `EXIT_LONG`, `EXIT_SHORT`, or `FLAT` -> `0.0`;
- `HOLD` -> current realized signed exposure.

The target is captured before cooldown, rebalance-threshold, fill, fee, spread, slippage, and mark-to-market decisions.

## Replay mode

Replay mode accepts one complete target record per native decision timestamp and does not call a strategy. It reuses the unchanged execution primitives and semantics for:

- cooldown;
- rebalance threshold;
- dynamic fill;
- fees;
- spread;
- slippage;
- cash yield;
- cash and position accounting;
- mark-to-market;
- trade recording.

## Fail-closed validation

Replay rejects:

- wrong target count;
- duplicate target timestamps;
- stage or fold mismatch;
- sleeve or asset mismatch;
- timeframe mismatch;
- non-contiguous sequence numbers;
- target values outside `[-1, 1]`;
- target timestamp sets that differ from the native DataFrame index;
- duplicate or non-monotonic DataFrame timestamps;
- capture without a strategy;
- replay that also supplies a strategy.

## Deterministic serialization

Target CSV serialization follows the frozen field contract:

- stage;
- fold;
- UTC timestamp;
- sleeve label;
- asset;
- native timeframe;
- strategy id;
- action;
- desired exposure fraction;
- signed target exposure;
- sequence number.

Numeric target fields use 12 decimal places. Rows use canonical sorting, UTF-8, LF line endings, and a fixed header.

## Synthetic test scope

The focused suite is designed to prove:

1. long, short, flat, exit, and hold conversion;
2. capture-only equality with canonical `run_backtest` on synthetic OHLCV;
3. unmodified target replay equality with capture execution;
4. preservation of cooldown, rebalance threshold, costs, and cash yield;
5. native timestamp preservation;
6. stage/fold and malformed-stream fail-closed behavior;
7. deterministic target serialization independent of input row order.

No claim of PASS is made until local focused-test output is supplied.

## Safety state

At implementation commit:

- governed source loaded: `false`;
- governed Core executed: `false`;
- governed targets generated: `false`;
- counterfactual generated: `false`;
- governed trades/exposures/costs generated: `false`;
- governed NAV or metrics generated: `false`;
- runtime modified: `false`;
- strategy modified: `false`;
- weights modified: `false`.

## Authorization boundary

This implementation authorizes nothing beyond local synthetic tests and review of their exact output. A governed-source capture/replay equivalence run requires a separate board decision after the focused tests pass.
