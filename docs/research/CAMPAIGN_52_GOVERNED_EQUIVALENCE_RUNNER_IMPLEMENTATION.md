# Campaign #52 Governed-Source Equivalence Runner Implementation

## Status

Implementation committed. No governed-source run result is asserted by this record.

## Runner

- `scripts/run_campaign52_governed_equivalence.py`
- implementation commit: `92b274c57c2cca2a3ac094896894779a7bb0a42a`

## Scope

The runner:

1. verifies all six frozen source SHA-256 identities before execution;
2. runs canonical Core sleeve execution, capture-only execution, and replay of the unchanged captured target stream;
3. requires equality of sleeve equity, realized exposure, and trade economics;
4. requires equality of fold fund NAV;
5. writes deterministic target, trade-economics, exposure, equity, fold-NAV, and stitched-NAV artifacts;
6. repeats the complete process independently twice;
7. requires identical artifact SHA-256 maps across both passes;
8. writes a final equivalence manifest.

Replay-only audit reason text is excluded from trade equivalence because replay intentionally labels its source differently. All economic and execution fields remain included.

## Prohibited outputs

The runner does not generate:

- static controls;
- lag controls;
- block permutations;
- Campaign #52 performance metrics;
- bootstrap inference;
- multiplicity tables;
- support decisions.

## Fail-closed conditions

Any source mismatch, sleeve-series mismatch, trade-economic mismatch, fold-NAV mismatch, or independent-pass artifact mismatch raises an error and prevents a PASS manifest.

## Authorization boundary

This implementation record authorizes no result claim. Local execution evidence must be returned to the campaign board before any development or validation execution decision.
