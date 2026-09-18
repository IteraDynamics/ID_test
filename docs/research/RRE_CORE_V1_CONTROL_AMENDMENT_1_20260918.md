# RRE Core v1 Control Amendment 1 — 2026-09-18

## Status
FROZEN AMENDMENT — observation-only control qualification.

The original historical-source gate remains unchanged. It stopped before strategy execution because local SPY, QQQ, and GLD no longer matched the frozen Campaign 52 source identities. BTC, ETH, and BIL still matched exactly.

Classification: HISTORICAL_SOURCE_BLOCKED.

This is not a strategy failure and not an RRE result.

## Amended question
Can the currently available six source files be frozen as a new common dataset and can authentic canonical Core v1 plus the existing deterministic capture/replay seam reproduce exactly across two independent passes, with no RRE information computed?

This does not claim reproduction of the old Campaign 52 NAV.

## Source freeze
Before Core execution the runner must record for each supplied source:
- SHA-256;
- byte size;
- row count;
- first and last timestamp;
- ordered OHLCV schema.

The supplied files may not be modified, repaired, truncated, reacquired, or substituted during the run. Extra history outside the frozen 2020-01-01 through 2025-12-31 evaluation window does not extend that window.

## Unchanged control
The control continues to use the canonical sleeve builder, strategy selection, BaselineRegimeEngine, execution configs, costs, weights, rebalance threshold, cross-asset state injections, BIL cash-yield treatment, and fold builder used by the existing Campaign 52 equivalence machinery.

Required:
- canonical/capture exact equality;
- capture/replay exact equality;
- fund NAV reconciliation;
- stitched NAV reconciliation;
- two independent deterministic passes;
- exact positive-capital sleeve inventory;
- no RRE, PCA, stability, or trajectory feature computed.

Any execution or determinism mismatch fails closed.

## Required output distinctions
The manifest must report:
- historical_reproduction_status = HISTORICAL_SOURCE_BLOCKED;
- fresh_paired_control_status = PASS or FAIL;
- historical_nav_reproduction_claimed = false;
- paired_control_dataset_frozen = true only after successful inventory;
- rre_features_computed = false;
- rre_intervention_applied = false.

## PASS meaning
PASS means authentic canonical Core v1 and its deterministic target-stream seam execute reproducibly on a newly frozen common dataset suitable for a separately frozen paired RRE experiment.

PASS does not mean the old historical artifact was reproduced, RRE improves Core, RRE is integrated, or production behavior may change.

## Next step
Only after PASS may a separate charter freeze an RRE treatment. Control and treatment must use identical frozen source identities and identical machinery except for the explicitly authorized RRE information-consumption seam.
