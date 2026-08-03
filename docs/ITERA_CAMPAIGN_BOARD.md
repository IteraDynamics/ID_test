# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** None — Campaign #51 closed.

**Status:** HOLD AFTER VALID NEGATIVE RESULT — Campaign #51 completed with an empty shortlist. No 2025 confirmation is authorized or necessary.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Campaign #51 conclusion

Campaign #51 tested whether BTC volatility and drawdown states previously supported by Campaign #48 condition the directional association of recent signed return.

Frozen family:

- trailing 24-hour and 168-hour signed log return;
- trailing 24-hour realized volatility and drawdown from the trailing 168-hour close high;
- 24-hour, 72-hour, and 168-hour forward-return horizons;
- exactly 12 interaction candidates.

Frozen model:

`Y = beta0 + betaD * D_z + betaS * S_z + betaI * (D_z * S_z) + epsilon`

Primary estimand: interaction coefficient `betaI`.

Inference:

- OLS;
- HC3 covariance;
- two-sided normal test;
- Holm correction across all 12 candidates separately within each stage.

## Final result

Two governed development/validation executions completed successfully.

Both runs reported:

- candidate count: `12`;
- `DISCOVERY_NOT_SUPPORTED`: `12`;
- `VALIDATION_NOT_ELIGIBLE`: `12`;
- shortlist count: `0`;
- predictors generated: `true`;
- forward outcomes generated: `true`;
- models fitted: `true`;
- prices loaded through: `2024-12-31 23:00:00`;
- holdout loaded: `false`;
- confirmation enabled: `false`;
- runtime modified: `false`.

All five canonical artifacts were byte-identical across replay.

Canonical SHA-256 identities:

- candidate inventory: `06c29c8caddf56d9278c53971d7a014f8fb596d36435f74257af9ddee15d5386`;
- development results: `ddfa49087995850cabf6dadbaf74038c12c6fe7954dce04fd2ec2176de51c774`;
- validation results: `afc389e2b4283e94e396bce4ba4c0ffbce23d74f2e6b0d81301a28ed13c7e2d9`;
- shortlist: `5d6088e94d033382d421c9ddb34b940d5a645a26cd15beada4b69ba2aa04acad`;
- stage manifest: `0b332f2353202b88be841277c04f579bc988568deb869e6a5963ac48b0b48814`.

Final closure record:

- `docs/research/CAMPAIGN_51_FINAL_CLOSURE.md`;
- commit `f9858cf8ceacb669f69d569250410ae289c6126d`.

## Interpretation

Campaign #51 did not establish that recent BTC momentum becomes directionally informative as a function of recent volatility or drawdown under the frozen design.

This is a valid governed negative result, not an implementation or reproducibility failure.

Campaign #48 remains intact: volatility and drawdown showed supported association with future movement magnitude and volatility. Campaign #51 rejects only this specific interaction-based directional-conditioning family.

## Current authorization

**Decision:** HOLD.

Authorized now:

- preserve the Campaign #51 closure record and canonical artifact identities;
- publish unchanged canonical artifact bytes if repository policy requires it;
- review Campaign #51 process lessons without changing the result;
- plan a new campaign or hypothesis family under a separate pre-outcome charter and gate;
- continue Campaign #49 passive prospective accumulation.

Not authorized:

- any Campaign #51 2025 confirmation run;
- analytically loading 2025 close values for Campaign #51;
- changing Campaign #51 candidates, formulas, horizons, support gates, standardization, covariance, multiplicity, pass rules, or signs after observing the result;
- economic-value testing or Core v1 comparison for Campaign #51;
- paper trading;
- runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training changes.

## Mandatory stage separation

Campaign #51 is closed.

Any next campaign requires:

1. a separate pre-outcome planning charter;
2. a fresh source-and-variable feasibility review;
3. a separately frozen hypothesis family;
4. a separately frozen statistical specification;
5. a fresh implementation and execution gate.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
