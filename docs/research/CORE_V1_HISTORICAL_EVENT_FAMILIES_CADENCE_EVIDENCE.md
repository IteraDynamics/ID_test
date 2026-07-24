# Core v1 Historical Event Families — Cadence Evidence

## Purpose

This evidence record closes the Campaign #41 cadence-reconnaissance gate without modifying any source artifact or authorizing implementation.

## Governed prediction source inspected

- repository-local path: `artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`
- SHA-256: `36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7`
- row count: `52453`
- first timestamp: `2020-01-01 01:00:00`
- last timestamp: `2025-12-26 00:00:00`
- timezone convention: timezone-naive
- monotonic increasing: `true`
- duplicate timestamp count: `0`

## Consecutive timestamp deltas

| Delta | Count |
|---|---:|
| `0 days 01:00:00` | 52447 |
| `0 days 02:00:00` | 3 |
| `0 days 04:00:00` | 1 |
| `0 days 06:00:00` | 1 |

Additional facts:

- minimum delta: `0 days 01:00:00`
- maximum delta: `0 days 06:00:00`
- unique delta count: `4`

## Determination

The governed stream has a nominal bar cadence of exactly one hour.

The five larger consecutive deltas are missing-bar gaps in an otherwise hourly timestamp series. They do not redefine the bar cadence and must not be silently bridged.

Canonical Campaign #41 cadence:

```text
PT1H
```

Immediate adjacency for closed episode intervals is therefore:

```text
next_start <= current_family_end + PT1H
```

This rule means:

- overlapping intervals join;
- intervals separated by exactly one hourly bar boundary join;
- intervals separated by more than one hour do not join;
- a larger source-data gap is never converted into adjacency through tolerance, interpolation, inferred rows, or stream naming.

## Validation policy for a later implementation

A later implementation must fail closed unless all of the following hold:

1. the validating timestamp source matches the governed source identifier and expected SHA-256 or an explicitly approved successor manifest;
2. timestamps parse under one uniform timezone-naive convention;
3. timestamps are strictly increasing;
4. duplicate timestamps are absent;
5. every consecutive delta is a positive integer multiple of `PT1H`;
6. episode boundaries align exactly to timestamps present in the governed source index;
7. adjacency is evaluated with `PT1H`, never with the observed larger gap size;
8. no missing timestamp is synthesized.

The presence of a positive integer-multiple gap does not itself invalidate the source. It is recorded as missing-bar evidence. Any non-integral multiple, non-positive delta, duplicate, mixed timezone convention, or boundary absent from the governed timestamp index is a fail-closed error.

## Scope control

This evidence is descriptive and observation-only. It introduces no runtime, model, threshold, order, NAV, exposure, portfolio, or source-artifact changes.
