# RRE Core v1 Entry Deferral — Daily-Source Gate Evidence — 2026-09-18

## Status

**PASS — source-only replacement-family gate.**

No RRE economic result was computed.

The locally available daily-market family passed the pre-outcome structural/calendar gate frozen
in RRE_CORE_V1_DAILY_SOURCE_LINEAGE_AMENDMENT_20260918.md.

## Candidate source identities

- SPY source SHA-256: 83df8fb4ae2123fb7b25da6e72149678c86469e1dd3de4c2e1e1efa1c0078714
- QQQ source SHA-256: 984edd17a462d9d13d2d08b6b811af9ecd2a46dbbe31f58c66c6b4bdb7a70cb9
- BIL source SHA-256: 8c7522487662bc65711deb5a784806fcdb5006f631d2359d3bbaaca9e226ae7a
- GLD source SHA-256: 5fae32a2c4bd7070502a0ae9401bf57571502a7fc5d306e3303b14d5d70a203f

BIL remains byte-identical to the historical Campaign #52 source. SPY, QQQ, and GLD do not.

## Frozen RRE extract identities

The source-only run reported deterministic historical extracts:

- SPY: 2,010 rows, 2018-01-02 through 2025-12-30,
  SHA-256 5c7461eb6fc265e1f53b7e68e51e4386e28720cb6095da14556feae0f6abc911
- QQQ: 2,010 rows, 2018-01-02 through 2025-12-30,
  SHA-256 7f3c42c05390a86bf8d9f1e3f4990eddc9163ab46ad8855a87120ecf08504cde
- BIL: 1,714 rows, 2019-03-08 through 2025-12-30,
  SHA-256 174f541610e8f34246837ada83c9346c20d5df5805af5349cf6ec043d8265022
- GLD: 2,010 rows, 2018-01-02 through 2025-12-30,
  SHA-256 1942a0e13c92487a72bb5c1e6f13b0317ab7f99cb3f798d9d0d279df91630477

SPY/QQQ/GLD extracts shared the required identical 2,010-session calendar. No interpolation,
repair, fill, nearest-session substitution, or synthetic rows were authorized.

## Provenance boundary

These hashes are frozen only for this RRE experiment. They do not replace or revise Campaign #52
source identities and do not prove row-level price equivalence to the unavailable historical
Campaign #52 SPY/QQQ/GLD files.

## Safety state

The reported gate had signals_generated=false, rre_scores_generated=false, trades_generated=false,
returns_generated=false, nav_generated=false, performance_metrics_calculated=false,
runtime_modified=false, strategy_modified=false, allocation_modified=false.
