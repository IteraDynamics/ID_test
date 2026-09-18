# RRE Core v1 Entry Deferral — Daily-Source Lineage Amendment — 2026-09-18

## Status

**PRE-OUTCOME SOURCE-LINEAGE AMENDMENT — daily-market source family.**

Exact-hash recovery searches confirmed that neither the frozen Campaign #52 SPY source nor the
frozen Campaign #52 QQQ source remains available under the local C:\Dev tree. No RRE economic
result has been computed.

This amendment does not alter the historical Campaign #52 record. Its source hashes remain the
authoritative identities for that closed campaign. The current local daily-market files are
candidate replacement sources for this RRE experiment only.

## Frozen historical identities

- SPY: 85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86
- QQQ: 34867c2b2da4aece23892b8e035e528f547173f3bc137cbe33b1295af0c1ff7b
- BIL: 8c7522487662bc65711deb5a784806fcdb5006f631d2359d3bbaaca9e226ae7a
- GLD: f740b144a1ceea2ce85afdc503175a5e7c0f96a8cfbd6ddea3ed26cfed7d491b

Historical Campaign #52 structural facts retained:
- SPY/QQQ/GLD: 2,010 rows, 2018-01-02 through 2025-12-30.
- BIL: 1,714 rows, 2019-03-08 through 2025-12-30.
- schema: timestamp,open,high,low,close,volume.
- no substitution, repair, interpolation, fill, or acquisition occurred in Campaign #52.

## Replacement gate

Before any signal, RRE score, trade, return, NAV, or performance calculation, the current
SPY/QQQ/BIL/GLD files must pass one source-only inventory:

1. exact ordered OHLCV schema;
2. parseable, unique, strictly increasing timestamps;
3. finite positive OHLC, nonnegative volume, valid OHLC relationships;
4. current source SHA-256, byte count, row count, first session, and last session recorded;
5. exact historical date-window coverage required by Core v1:
   - SPY/QQQ/GLD must include 2018-01-02 through 2025-12-30;
   - BIL must include 2019-03-08 through 2025-12-30;
6. canonical RRE extracts are created by deterministic date filtering only;
7. no interpolation, repair, fill, nearest-session substitution, or synthetic rows;
8. SPY, QQQ, and GLD canonical extracts must have identical timestamp calendars and exactly
   2,010 sessions;
9. BIL canonical extract must have exactly 1,714 sessions and end on 2025-12-30;
10. BTC and ETH remain bound to the original governed Campaign #52 hashes and are not amended.

A PASS establishes only structural/calendar suitability of new daily-market sources for this
RRE experiment. It does not establish price or byte equivalence to the unavailable Campaign #52
files.

## Economic-run provenance

If this source-family gate passes, the RRE economic runner must be changed before execution so
that:
- BTC/ETH are still verified against their original governed hashes;
- SPY/QQQ/BIL/GLD are verified against the newly frozen RRE extract hashes produced by this gate;
- those exact extract hashes are recorded in the RRE manifest;
- Campaign #52 source hashes are never overwritten or relabeled.

## Authorization boundary

Observation/research only. No Core runtime, strategy, allocation, threshold, order, exposure,
execution, NAV handling, or production behavior is changed.
