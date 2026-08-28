# Campaign #52 Development Tooling Implementation

## Status

Observation-only implementation record. This commit set adds pure Campaign #52 development-stage transformation, metric, inference, multiplicity, decision, and atomic-output helpers plus fabricated-data tests.

No governed equivalence artifact was opened. No governed target stream, control, replay, NAV, metric, bootstrap, ranking, or development decision was generated or inspected.

## Commits

- board implementation authorization: `82b1e920c5b0e1bd4918e62d9b13eed511463d1b`
- pure helper implementation: `f9ef8eb41dbbdd9417b1ec0b85918da0e98d2898`
- synthetic tests: `54ce33a0f3c9edc881aad69b8f5efbd913516e95`

## Added module

`research/harness/campaign52_development.py`

The module contains only caller-supplied-data helpers. It performs no artifact discovery, source loading, strategy invocation, governed replay orchestration, or validation-stage access.

Implemented contracts:

- frozen 20-control identifier order;
- structural validation-path rejection;
- development-record validation;
- full-precision per-sleeve static development mean;
- exact same-fold lag controls with zero fill;
- SHA-256-derived 64-bit permutation and bootstrap seeds;
- deterministic Fisher-Yates permutation;
- 28-day complete-block transformation with unchanged terminal remainder and row-count fail closure;
- UTC daily end-of-day NAV derivation;
- frozen annualized geometric return, maximum drawdown magnitude, and Calmar conventions;
- deterministic 21-day moving-block bootstrap with exactly 10,000 replications;
- one-sided bootstrap p-value convention using add-one correction;
- Holm step-down adjustment over exactly 20 controls with deterministic tie order and unrankable value `1.0`;
- exact development support decision boundaries;
- atomic output promotion and stale-output rejection.

## Synthetic tests

`tests/test_campaign52_development.py`

The tests use fabricated target records and NAV paths only. Coverage includes:

- structural validation-path rejection;
- static mean construction and transformation;
- exact lag mapping and zero fill;
- deterministic seeds and Fisher-Yates;
- terminal incomplete-block preservation;
- common permutation across sleeves;
- unequal complete-block row-count rejection;
- two-pass target byte identity;
- daily end-of-day NAV;
- primary metric edge handling;
- deterministic frozen bootstrap;
- Holm ties and unrankable controls;
- development decision pass/fail boundaries;
- atomic promotion and stale-output rejection.

## Explicit omissions

Not implemented or authorized in this stage:

- a governed artifact-root reader;
- source or equivalence manifest import;
- governed control generation;
- canonical or control replay orchestration;
- governed metric or bootstrap execution;
- output of any development classification;
- validation-stage reading or execution;
- any Core, runtime, threshold, order, exposure, cost, weight, or strategy change.

## Local validation command

```text
python -m pytest tests/test_campaign52_development.py -q
```

Exact local output is required before any further implementation or governed execution decision.
