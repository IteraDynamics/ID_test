# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #50 — Holdout-First Alpha Research

**Status:** DEVELOPMENT/VALIDATION COMPLETE — EMPTY SHORTLIST; two governed 2018–2024 replays were byte-identical, zero candidates were discovery-supported, zero candidates were validation-supported, and no 2025 holdout execution is authorized or necessary.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

## Governed design

- Base statistical specification: commit `36dd499d00740062f10c1c070896f740f55f6808`
- Frozen source universe: commit `f32cac981bf55d0b1799949988df70e5546394e5`
- Execution procedure: commit `16b00d8e5f33a1636a65cb6a3885b19562726551`
- Support-gate amendment: commit `18ff04022fac611c4c2c6136132afa57ee8ad30e`
- Amended implementation constants: commit `29b38116eccb2802756c622ac260eb0908492ad2`
- Fresh execution GO: commit `07276cc5831de016ebb55259c3c8154ec10cde86`
- Amended execution entry point: commit `71a77cf4969fbc61a56db711c1e8ef781d5e1c5f`
- Read-only reviewer: commit `fb0efde552e5e16e75f2123871e9d9cdae5a2a99`
- Development/validation result record: `docs/research/CAMPAIGN_50_DEVELOPMENT_VALIDATION_RESULT.md`; commit `61deee7c94e22ad88aac498f50fb13748f78cd58`

Research family: equity breadth deterioration and recovery.

Targets: SPY and QQQ.

Breadth members: RSP, MDY, IWM, IWD, IWF, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, and XLY.

Candidate inventory: exactly 24 candidates from four predictors, two targets, and 5-, 20-, and 60-session forward-return horizons.

Intervals:

- development: `2018-01-02` through `2022-12-30`
- validation: `2023-01-03` through `2024-12-31`
- untouched holdout: `2025-01-02` through `2025-12-30`

Amended development total-support gates:

- 5 sessions: 180
- 20 sessions: 50
- 60 sessions: 16

All other frozen methods and gates remained unchanged.

## Execution evidence

- complete Campaign #50 tests: `15 passed in 0.12s`
- amended run 1: `PASS`
- amended run 2: `PASS`
- candidate count: `24`
- predictors generated: `true`
- outcomes generated: `true`
- holdout loaded: `false`
- confirmation enabled: `false`
- method mutation: `false`
- replay identity: all six canonical artifacts byte-identical
- read-only review: `PASS`

Development status counts:

- `DISCOVERY_NOT_SUPPORTED`: 16
- `INSUFFICIENT_EVENT_SUPPORT`: 8
- `DISCOVERY_SUPPORTED`: 0

Validation status counts:

- `VALIDATION_NOT_ELIGIBLE`: 20
- `INSUFFICIENT_EVENT_SUPPORT`: 4
- `VALIDATION_SUPPORTED`: 0

Frozen shortlist count: `0`.

## Canonical artifact hashes

- candidate inventory: `d99457662519151f0735964374e9e6d8ecfa155be9caa0c50f8a8491487d3d19`
- development results: `639387c0f68eba59e007d345eae592391738dc36f6c8b672ce9affd0e08f7b0e`
- preflight: `826a9332f34de76ee19305639125b11b41c0d64d48276a523a501d469cbd3e39`
- shortlist: `0fbf25b2bcb93f63ecd92e30d81f980d1d38412ebaa15b3a680a664da8810d2e`
- stage manifest: `7a44a19b3373465b99aa95989614b468d5572b092120374cb0299d2f603827b5`
- validation results: `3fac458eef010e34eeb8e66f911bd8f2bde77422b9f3363c67223a7676e033da`

The canonical run-1 bytes remain local under `artifacts/campaign50_development_validation_run1/`. The result record preserves their governed identities; repository publication of those bytes, if required, must preserve the exact hashes above.

## Current authorization

**Decision:** HOLD after a valid negative development/validation result.

Authorized now:

- preserve the result record and canonical artifact identities;
- publish the unchanged canonical run-1 artifact bytes if repository policy requires it;
- review Campaign #50 process lessons without altering the completed result;
- plan a new campaign or hypothesis family under a separate pre-outcome charter and gate;
- continue Campaign #49 passive prospective accumulation.

Not authorized:

- running the 2025 Campaign #50 holdout, because the frozen shortlist is empty;
- changing Campaign #50 predictors, thresholds, horizons, support gates, signs, covariance, multiplicity, or shortlist rules after observing results;
- economic testing or Core v1 comparison for Campaign #50;
- paper trading;
- runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training changes.

## Conclusion

Campaign #50 did not establish a supported predictive association under the frozen equity-breadth design. This is a valid governed negative result.

No historical-confirmation GO should be issued for Campaign #50. The untouched 2025 holdout remains unaccessed analytically.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.

## Campaign #48 completion

Campaign #48 is complete under closure `77c1ae8c70de7a16cca847aeb1a4cb2eea638007` and canonical publication `fd7ee01`. It authorized no runtime or strategy change.
