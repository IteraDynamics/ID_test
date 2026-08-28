# Campaign #52 Reference-Artifact and Intervention Feasibility Inventory

## Status

Planning-only inventory completed before any Campaign #52 counterfactual generation, NAV reconstruction, performance comparison, model fitting, ranking, or support decision.

This record does not freeze a hypothesis family or authorize execution.

## Campaign objective

Determine whether canonical Core v1 derives material value from the correct chronological alignment of its state-conditioned decisions, beyond what can be explained by average exposures, sleeve composition, and activity profile.

Campaign #52 is an architecture-falsification campaign. It does not reopen Campaign #51 and does not authorize changes to Core v1.

## Reference lineage reviewed

### Blessed Core v1 baseline manifest

Reference document:

- `research/trade_idea_radar/CORE_V1_BASELINE_MANIFEST.md`

Documented allocation:

- trend: `0.40`;
- equity: `0.35`;
- gold: `0.15`;
- hedge: `0.10`;
- mean reversion: `0.00`.

Documented defining architecture:

- explicit BTC macro-state ownership across all crypto trend sleeves;
- ETH trend sleeves consume BTC recovery and parabolic state rather than deriving those states from ETH-local prices.

Documented BTC state columns:

- `btc_above_sma175`;
- `btc_extension_sma365`;
- `btc_parabolic_soft`;
- `btc_parabolic_hard`;
- `btc_parabolic_tier`.

The baseline manifest records an older validation command using 2019-start BTC and ETH files. Later accepted Core research documents require the canonical 2018-start crypto files. Therefore, the old command is historical lineage, not yet an acceptable Campaign #52 execution reference.

### Current candidate walk-forward runner

Reference implementation:

- `scripts/run_core_v1_candidate_wfo.py`.

The runner defines explicit per-sleeve capital weights and calls the canonical sleeve audit/backtest path. Its default cost assumptions are:

- crypto taker fee: `0.0006`;
- equity fee: `0.0001`;
- base crypto slippage: `3.0` bps;
- slippage volatility factor: `50.0`;
- rebalance threshold: `0.02`;
- crypto cooldown: `2` bars;
- mean-reversion cooldown: `12` bars.

The runner creates yearly OOS folds, stitches fold NAVs chronologically, and writes:

- per-fold sleeve and fund artifacts through the audit path;
- `stitched_oos_nav.csv`;
- `summary.csv`.

Its scenario inventory includes the original baseline and later allocation candidates. Campaign #52 must separately freeze which scenario is the canonical reference; no scenario is selected by this inventory.

### Sleeve contribution and audit path

Reference implementation:

- `scripts/run_core_v1_sleeve_contribution_audit.py`.

This path:

- loads canonical source files supplied by path;
- constructs sleeve specifications;
- computes BTC macro state once;
- injects BTC macro state into trend sleeves;
- generates sleeve strategies independently;
- runs each sleeve through the shared deterministic backtest engine;
- writes sleeve curves and scaled sleeve curves;
- aligns full fold curves before slicing OOS;
- records BTC-state-source audit rows for trend sleeves;
- stitches the fund chronologically.

The path exposes enough structure to capture sleeve-level decisions without changing strategy logic.

### Shared backtest engine

Reference implementation:

- `research/harness/backtest_engine.py`.

The engine is deterministic and closed-bar only. At each bar it:

1. computes the causal regime label;
2. calls `strategy.generate_intent` using data only through the current closed bar;
3. converts the intent into a signed target exposure;
4. applies cooldown and rebalance-threshold rules;
5. simulates fills with fees, spread, and dynamic slippage;
6. marks positions to market;
7. records equity, realized exposure, intent, regime, and trades.

Relevant output objects:

- `intent_series` — pre-execution strategy decisions;
- `position_series` — realized post-execution exposure;
- `trades` — executed changes after cooldown, threshold, and cost treatment;
- `equity_curve` — post-execution NAV.

## Source-reference feasibility

Later accepted Core work identifies these as canonical data paths:

- `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`;
- `data/SPY_1D.csv`;
- `data/QQQ_1D.csv`;
- `data/BIL_1D.csv`;
- `data/GLD_1D.csv`.

Campaign #52 still requires a separate non-outcome preflight to freeze:

- SHA-256 identity;
- byte count;
- schema;
- row count;
- timestamp coverage;
- missing-timestamp inventory;
- accepted date interval;
- fold construction;
- cash-yield treatment;
- exact canonical Core commit and scenario.

No source values or performance outcomes were generated or inspected for this inventory.

## Candidate intervention layers

### 1. Raw BTC macro-state columns

Mechanically feasible for crypto trend sleeves only.

Advantages:

- directly targets the promoted explicit-BTC-state architecture;
- preserves downstream strategy and execution behavior;
- easy to displace or block-permute deterministically.

Limitations:

- does not cover equity, gold, hedge, or other sleeve-local decision streams;
- does not isolate the chronology of the complete Core portfolio;
- static exposure matching is not naturally defined at this layer;
- changing state columns can alter strategy activity and average exposure substantially, weakening matched-control interpretation.

Conclusion:

- feasible as a narrow secondary architecture test;
- insufficient as the sole Campaign #52 intervention object.

### 2. Strategy intent / pre-execution target-exposure stream

Mechanically feasible with an additive research harness.

The existing engine converts each `StrategyIntent` into a signed target exposure before applying execution rules. A research-only adapter can capture the canonical intent-derived target exposure at every bar and replay an externally supplied target stream through the unchanged cooldown, threshold, fill, cost, and mark-to-market machinery.

Advantages:

- common layer across all sleeves;
- preserves canonical strategy outputs before intervention;
- permits static, displaced, and block-permuted controls;
- retains unchanged execution costs, cooldowns, rebalance thresholds, cash yield, and mark-to-market semantics;
- separates timing intervention from strategy-logic modification;
- allows exact comparison of target prevalence, duration, turnover demand, and realized execution.

Limitations:

- requires a new side-effect-free research adapter because the current engine generates intents internally;
- static matching must be defined carefully to avoid using later-stage or protected information;
- displacement and permutation can alter realized turnover after cooldown and threshold application, which must be measured rather than assumed away;
- short and long target conventions must remain sleeve-specific and signed.

Conclusion:

- strongest primary intervention candidate;
- suitable for a later frozen hypothesis family, subject to synthetic replay tests and exact invariants.

### 3. Realized position series

Mechanically easy to shift or permute after a canonical run, but analytically unsuitable as the primary intervention layer.

Advantages:

- directly observable;
- already incorporates cooldown and rebalance-threshold behavior;
- convenient for exposure-distribution matching.

Limitations:

- realized positions embed prior execution decisions and costs;
- shifting positions without replaying execution can assign exposure changes without valid fills;
- transaction costs, slippage, spreads, and cash balances would no longer correspond to the counterfactual chronology;
- replaying realized positions as targets changes their meaning and can generate new execution paths.

Conclusion:

- useful as a matching/audit diagnostic;
- rejected as the primary chronology intervention object.

### 4. Executed order or trade stream

Mechanically possible but too downstream.

Advantages:

- preserves exact canonical trade sizes and counts if merely reassigned in time.

Limitations:

- prices, liquidity proxies, NAV, and affordability differ at displaced timestamps;
- exact notional preservation can violate exposure and capital constraints;
- order reassignment bypasses the strategy-to-target and execution decision process;
- static matching is unnatural;
- high risk of constructing impossible or economically incoherent trades.

Conclusion:

- rejected.

### 5. NAV or return series

Mechanically trivial to rearrange but invalid for causal architecture testing.

Conclusion:

- rejected outright.

## Counterfactual-class feasibility

### Static exposure-matched control

Feasible at the target-exposure layer.

Possible deterministic construction:

- calculate a fixed signed target exposure separately for each sleeve from a frozen development interval only;
- apply that fixed target through the unchanged execution engine for the applicable stage;
- preserve original sleeve capital weights, source data, costs, cash yield, and execution settings.

Required later decisions:

- whether the match uses arithmetic mean target exposure, mean absolute exposure with sign prevalence, or another predeclared statistic;
- whether matching is sleeve-specific and stage-frozen;
- how short-capable hedge sleeves are handled;
- whether the target is continuously maintained or only reset at predetermined intervals;
- how development-derived values are reused in validation and confirmation.

Risk:

- a continuously maintained fixed target may create little turnover and therefore fail to match Core activity.

Conclusion:

- feasible as an exposure-composition control;
- cannot by itself match both exposure and activity without an additional frozen mechanism.

### Deterministically displaced target sequence

Feasible at the target-exposure layer.

Construction principle:

- preserve each sleeve’s exact canonical target sequence order and values;
- apply a fixed predeclared temporal displacement within a stage;
- forbid wraparound across stage boundaries;
- mark leading or trailing uncovered bars according to a frozen fail-closed rule, likely flat or unavailable;
- replay through unchanged execution.

Advantages:

- preserves sequence shape and duration;
- breaks authentic market alignment;
- yields a compact, interpretable placebo family.

Required later decisions:

- displacement magnitudes and directions;
- treatment of uncovered boundaries;
- sleeve-timeframe normalization;
- whether offsets are expressed in wall-clock time or native bars;
- multiplicity family.

Leakage warning:

- negative displacement applies future decisions earlier and is inherently look-ahead contaminated unless used only as a clearly labeled noncausal diagnostic. It should not enter support claims.

Conclusion:

- positive, lagging displacement is feasible and causal;
- negative, leading displacement should be excluded from confirmatory support testing.

### Deterministic block permutation

Mechanically feasible at the target-exposure layer, but requires careful stage-contained design.

Construction principle:

- partition each sleeve’s canonical target stream into fixed, non-overlapping chronological blocks;
- permute blocks using a fully specified deterministic mapping or seed;
- keep blocks within the same stage;
- preserve within-block order;
- replay the permuted target stream through unchanged execution.

Advantages:

- preserves local state persistence and within-block activity;
- destroys authentic long-run chronology;
- can generate a reference distribution rather than one arbitrary placebo.

Required later decisions:

- block duration;
- common wall-clock blocks versus native-bar blocks;
- number of deterministic permutations;
- seed derivation and canonical permutation order;
- handling incomplete terminal blocks;
- family-wise inference and equivalence rules.

Risks:

- too-short blocks destroy persistence and inflate turnover demand;
- too-long blocks leave much of the authentic chronology intact;
- unconstrained permutation can move decisions between materially different structural periods while still being valid as a placebo, but interpretation must be frozen;
- permutation must not use outcome metrics to choose seeds or block length.

Conclusion:

- feasible after a separately frozen design and non-outcome calendar preflight.

## Recommended intervention hierarchy for family selection

This inventory recommends, but does not yet freeze:

1. primary intervention object: sleeve-level signed target exposure derived from canonical strategy intents before execution;
2. primary placebo class: positive fixed displacement;
3. distributional placebo class: deterministic stage-contained block permutation;
4. composition control: development-frozen static sleeve target exposure;
5. secondary narrow attribution: explicit BTC macro-state intervention for crypto trend sleeves only.

The recommendation is based on mechanical validity and separation of strategy logic from execution, not on Campaign #52 outcomes.

## Required adapter invariants

Any later implementation should fail closed unless it demonstrates:

- canonical strategy run and capture-only adapter produce identical target, realized exposure, trade, fee, slippage, spread, and NAV artifacts;
- supplying the unmodified captured target stream reproduces canonical execution byte-for-byte or within a separately frozen exact numeric serialization contract;
- target interventions cannot alter source data, strategy code, regime code, sleeve weights, cost settings, cooldowns, rebalance thresholds, cash-yield treatment, or fold ordering;
- all transformations are stage-contained and deterministic;
- no target value from a later stage enters an earlier stage;
- no protected confirmation outcome or future target is used to parameterize development or validation controls;
- every control carries complete lineage: source hashes, reference commit, scenario, transformation id, parameters, seed, stage, and artifact hashes.

## Duplication exclusions

Campaign #52 should not repeat:

- allocation-weight optimization;
- risk-sleeve ablation;
- sleeve removal or capital redistribution;
- cost sensitivity;
- regime attribution of already-generated NAV;
- historical event summaries;
- policy-selector optimization;
- a fresh directional predictor search.

A control that merely changes sleeve weights is out of scope.

## Feasibility conclusion

Campaign #52 is mechanically feasible without modifying Core v1 strategy logic.

The strongest common chronology intervention layer is the sleeve-level pre-execution signed target-exposure stream derived from canonical intents. This layer permits static, causal lag-displacement, and stage-contained block-permutation controls while retaining the unchanged execution engine.

The current repository does not yet expose a governed capture-and-replay adapter, exact source identities for Campaign #52, a frozen canonical scenario, or a frozen counterfactual family. Those remain mandatory before implementation or execution.

## Safety state

At completion of this inventory:

- canonical Core run executed: `false`;
- counterfactual generated: `false`;
- target stream generated: `false`;
- realized exposure generated: `false`;
- orders generated: `false`;
- NAV generated: `false`;
- performance metrics calculated: `false`;
- outcomes inspected: `false`;
- runtime modified: `false`;
- strategy modified: `false`;
- weights modified: `false`.

## Authorization boundary

This document authorizes nothing beyond returning to the campaign board for a separate hypothesis-family-selection decision.
