# RRE / Canonical Core v1 Control Charter — 2026-09-18

## Status

**FROZEN CONTROL QUALIFICATION — observation-only.**

This charter follows the regime-usage audit. It does not authorize an RRE intervention or any economic Core-vs-RRE comparison.

No production, paper-trading, runtime, strategy, portfolio, threshold, order, NAV, exposure, execution, allocation, weight, cost, or Core-label behavior may change.

## Question

Can the repository reproduce the authentic canonical Core v1 historical control, on its governed sources and frozen economic configuration, with deterministic capture/replay identity and a research-only intervention seam, **before** any RRE information is introduced?

A PASS answers only that the control is qualified for a later separately frozen paired RRE experiment.

## Important discovery before implementation

A new control implementation is not required to establish the seam from scratch.

Campaign #52 already built and passed the exact infrastructure needed:

- `scripts/run_campaign52_governed_equivalence.py`;
- `research/harness/campaign52_target_replay.py`;
- exact canonical strategy execution through `run_backtest`;
- capture of sleeve-level pre-execution signed targets;
- unchanged-target replay through the same execution semantics;
- two independent deterministic passes;
- exact governed source SHA-256 verification.

The accepted evidence record `docs/research/CAMPAIGN_52_GOVERNED_EQUIVALENCE_PASS_EVIDENCE.md` reports:

- `canonical_capture_equal = true`;
- `capture_replay_equal = true`;
- `canonical_intents_reused_for_capture = true`;
- `independent_passes = 2`;
- `runtime_modified = false`;
- `strategy_modified = false`;
- `weights_modified = false`.

Therefore this phase must **reuse and qualify** that seam rather than create a second replay implementation.

## Frozen governed sources

The control uses the Campaign #52 governed identities:

- BTC: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`, SHA-256 `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- ETH: `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`, SHA-256 `73721a1ef1dffbff64bf6ef2d92fb508a59b20d5c847684d96fdc7015912845f`;
- SPY: `data/SPY_1D.csv`, SHA-256 `85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86`;
- QQQ: `data/QQQ_1D.csv`, SHA-256 `34867c2b2da4aece23892b8e035e528f547173f3bc137cbe33b1295af0c1ff7b`;
- BIL: `data/BIL_1D.csv`, SHA-256 `8c7522487662bc65711deb5a784806fcdb5006f631d2359d3bbaaca9e226ae7a`;
- GLD: `data/GLD_1D.csv`, SHA-256 `f740b144a1ceea2ce85afdc503175a5e7c0f96a8cfbd6ddea3ed26cfed7d491b`.

Any source mismatch is a hard FAIL. No substitute data are allowed.

## Frozen control configuration

Inherited from the governed Campaign #52 equivalence runner:

- capital: 100,000;
- data start: 2018-01-01;
- OOS folds: 2020-01-01 through 2025-12-31, annual;
- trend weight: 0.40;
- equity weight: 0.35;
- gold weight: 0.15;
- hedge weight: 0.10;
- mean-reversion weight: 0.00;
- crypto fee: 0.0006;
- equity fee: 0.0001;
- base slippage: 3.0 bps;
- slippage volatility factor: 50.0;
- crypto cooldown: 2 bars;
- mean-reversion cooldown: 12 bars;
- rebalance threshold: 0.02.

The control must use `_build_sleeves`, `strategy_for`, `run_backtest`, authentic `BaselineRegimeEngine`, BTC macro-state injection, SPY/BTC cross-asset fields, BIL cash yield treatment, and the existing fold builder exactly as the governed runner does.

## Canonical universe / BTC 1H clarification

The historical Core lineage includes a promoted baseline that originally contained BTC 1H. Later allocation research selected `candidate_btc1h_hedges_to_btc4h_gld_qqq`, moving the BTC 1H allocation away while retaining BTC 4H, ETH 1H, ETH 4H, equities, gold, and cash behavior.

For the RRE/Core-v1 comparison, the control must use the **currently accepted canonical Core scenario**, not infer the universe from an older baseline manifest and not equally weight research panels.

This qualification phase must report the exact positive-capital sleeve inventory produced by the governed control. It may not alter that inventory.

## Known historical backtest caveat

The parameter-sensitivity review later documented a narrow parity gap: historical backtests through `backtest_engine.py` did not simulate identical live logic at the equity de-risk margin for a handful of sessions. The live paper runtime reads the strategy correctly.

This charter does **not** authorize fixing that historical engine behavior. Doing so would change the control after the fact.

The qualification report must:

1. preserve the accepted historical canonical path;
2. disclose the parity caveat;
3. distinguish "canonical accepted historical Core control" from "live runtime exact behavior";
4. forbid any RRE claim from being attributed to that known branch unless separately investigated.

## Qualification invariants

The control qualifies only if all are true:

1. all six source SHA-256 identities match;
2. canonical execution and capture execution are exactly equal for sleeve equity, realized exposure, and trade economics;
3. unchanged-target replay equals capture execution;
4. fold fund NAVs reconcile;
5. stitched NAV reconciles;
6. two independent passes produce identical artifact SHA-256 maps;
7. the exact positive-capital sleeve inventory is recorded;
8. no RRE/PCA/stability/trajectory feature is imported or calculated;
9. no performance-dependent parameter or configuration is selected;
10. runtime, strategy, weights, costs, thresholds, execution, and Core labels remain unchanged.

Any failure is fail-closed. Do not widen tolerances or substitute sources after observing a failure.

## Intervention seam

The qualified seam is the existing sleeve-level pre-execution signed target stream.

A later RRE experiment may be allowed to alter information **before or at a separately frozen decision seam**, but this charter authorizes no such alteration.

The unchanged-target replay is the only intervention-seam test authorized now.

## Outputs

The qualification runner must produce a compact manifest containing:

- source hashes;
- inherited configuration;
- sleeve inventory and counts;
- canonical/capture/replay equality flags;
- independent-pass equality;
- artifact hashes;
- stitched NAV identity;
- explicit `rre_features_computed=false`;
- explicit guardrails;
- reference to the known equity de-risk historical parity caveat.

No new strategy P&L comparison is part of this phase.

## PASS meaning

PASS means:

> The accepted canonical historical Core v1 control and deterministic target-stream intervention seam are reproducible and suitable for a separately chartered RRE paired experiment.

PASS does **not** mean:

- RRE improves Core;
- RRE has been integrated;
- a production change is justified;
- historical Core v1 is identical to every live-runtime branch;
- any previously failed strategy is reopened.

## Next step after PASS

Only after PASS may a new frozen charter specify the first authentic Core-v1/RRE intervention.

That future charter must define, before economic output is observed:

- exact sleeve(s) eligible for RRE information;
- exact RRE information available at each timestamp;
- whether RRE is additive conditioning, gating, or risk scaling;
- exact training chronology and maturity;
- unchanged control arm;
- costs and execution;
- primary economic metric and paired gate;
- development/validation separation;
- failure rule.

No such intervention is frozen here.
