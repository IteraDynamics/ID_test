# RRE Core v1 Entry Deferral — Runtime/Cost-Stress Execution Note — 2026-09-18

Pre-outcome implementation note. No economic result has been computed.

To minimize unnecessary compute without changing the frozen decision rule:

1. The base-cost paired experiment runs first.
2. If any already-evaluable frozen gate makes advancement impossible (for example non-positive mean paired Sharpe, insufficient cross-fold wins, a non-positive eligible-sleeve mean, drawdown failure, or insufficient intervention count), the run is classified FAIL and the higher-cost replay is skipped because it cannot rescue the frozen all-gates-required decision.
3. Only if the base case remains eligible to advance is the higher-cost stress executed.

The higher-cost stress is frozen here as a symmetric 2x execution-cost stress relative to canonical base assumptions: crypto taker fee 0.0012 instead of 0.0006, equity fee 0.0002 instead of 0.0001, base slippage 6 bps instead of 3 bps, and volatility slippage factor 100 instead of 50. Both control and experimental arms receive the identical stress.

Runtime optimization is restricted to parallel fold execution, reuse/caching of immutable derived daily RRE panels/scores, and avoiding redundant canonical/counterfactual passes. It may not alter chronology, bar frequency, numerical model settings, strategy logic, execution ordering, source data, or results.
