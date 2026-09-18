# RRE Core v1 Entry Deferral — SPY Source-Lineage Amendment — 2026-09-18

## Status

**PRE-OUTCOME SOURCE AMENDMENT — replacement source not yet accepted.**

No RRE economic result has been computed. The frozen Campaign #52 SPY file with SHA-256
\`85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86\`
could not be recovered by exact-hash searches under \`C:\Dev\IteraDynamics\` or the broader
\`C:\Dev\` tree. The historical Campaign #52 identity remains immutable and is not restated.

The currently available \`data/SPY_1D.csv\` is therefore a **candidate replacement source for
this RRE experiment only**. Its different byte identity must be recorded, and it must pass the
source-only gate below before any signal, RRE score, position, trade, NAV, return, or performance
calculation is allowed.

## Historical evidence retained

The missing frozen source is documented as:

- rows: 2,010
- first session: 2018-01-02
- last session: 2025-12-30
- ordered schema: \`timestamp,open,high,low,close,volume\`
- duplicate timestamps: 0
- strictly increasing: true
- SHA-256: \`85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86\`

No retained row-level copy of the missing source is known, so price equality to that missing file
cannot be asserted or manufactured.

## Replacement acceptance gate

The candidate replacement MUST satisfy all of the following mechanically:

1. exact ordered OHLCV schema;
2. parseable, unique, strictly increasing timestamps;
3. finite positive OHLC values, nonnegative volume, and valid OHLC relationships;
4. it contains every one of the 2,010 sessions on the frozen QQQ calendar from 2018-01-02
   through 2025-12-30, with no missing frozen-calendar sessions;
5. its first and last matched frozen-calendar sessions are exactly 2018-01-02 and 2025-12-30;
6. no interpolation, repair, synthetic row, nearest-session substitution, or fill is used;
7. the RRE economic runner uses only the candidate's rows whose timestamps belong to the frozen
   2,010-session QQQ calendar and only through 2025-12-30;
8. the candidate's actual SHA-256, byte count, full row count, matched row count, and any extra
   sessions are recorded;
9. QQQ, BIL, GLD, BTC, and ETH remain subject to their previously frozen hashes; this amendment
   authorizes no substitution for those sources.

The QQQ calendar is used only as retained governed evidence of the exact equity-session calendar.
QQQ prices are not used to validate SPY prices.

## Interpretation boundary

A PASS establishes calendar/schema/structural suitability of a new SPY source for the RRE
experiment. It does **not** establish byte identity or row-level price identity to the missing
Campaign #52 SPY file. Results from the amended experiment must carry that provenance caveat.

A FAIL blocks the RRE economic run. No threshold, calendar, source, or acceptance criterion may
be loosened after seeing the result.

## Authorization boundary

This amendment is observation/research only. It changes no Core v1 runtime, allocation, threshold,
order, exposure, strategy, paper record, or production behavior.
