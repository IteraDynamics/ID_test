# Core v1 Historical Alpha Discovery

## Status

Governing research specification for Campaign #43.

This document must be committed before result inspection, candidate optimization, or canonical artifact generation.

## Purpose

Campaign #43 is the first Itera campaign explicitly intended to discover candidate historical predictive relationships.

Its purpose is to identify which existing governed Core v1 descriptors exhibit repeatable out-of-sample association with deterministic forward BTC outcomes after correcting for overlapping episode duplication through Campaign #41 event families.

The campaign produces candidate evidence, not a trading strategy and not authorization for production use.

## Safety boundary

The work is:

- BTC-only;
- deterministic;
- replay-safe;
- research-only;
- observation-only;
- fail-closed.

The work does not authorize:

- production runtime integration;
- live signal generation;
- model retraining or replacement;
- threshold changes;
- signal or intent changes;
- order generation or execution;
- portfolio construction;
- NAV changes;
- exposure mutation;
- dashboard integration;
- cross-asset work;
- deployable-alpha claims;
- strategy recommendations.

## Governed source classes

The implementation may consume only exact, hashed canonical artifacts already committed to the repository and explicitly listed in the Campaign #43 manifest.

Required source classes:

1. Governed Core v1 episode-level taxonomy and descriptors.
2. Campaign #41 deterministic historical event-family membership.
3. Campaign #42 episode-versus-event-family robustness outputs.
4. Governed BTC historical market data sufficient to calculate predeclared forward outcomes.

Before implementation begins, the exact file paths and SHA-256 hashes for every source must be added to this specification and the campaign board. Missing, changed, duplicated, malformed, or inconsistent governed inputs must fail closed.

## Unit of observation

Two evidence resolutions are required.

### Episode resolution

Each governed episode contributes one observation for its predeclared candidate descriptor values and forward outcomes.

Episode-resolution evidence is permitted only as a description of rolling-window observations. It must never be presented as independent-event support.

### Event-family resolution

Campaign #41 deterministic event families define the independent-event correction layer.

Each event family contributes at most one family-level observation per candidate and evaluation horizon under a predeclared aggregation rule.

The family-level aggregation rule must be fixed before results are inspected. No plurality, latest-value, best-performing, or otherwise result-conditioned representative value may be inferred.

Where a family cannot be represented without ambiguity under the predeclared rule, the family must be marked mixed or unavailable rather than coerced.

## Candidate descriptor eligibility

Eligible candidates must already exist in governed artifacts before Campaign #43 begins.

Initial candidate classes:

- intrinsic subtype;
- recovery outcome;
- pre-existing component labels used to construct intrinsic subtype, where separately governed;
- pre-existing deterministic episode descriptors explicitly documented in the governed source artifacts.

Ineligible candidates:

- newly invented transformations created after observing outcomes;
- arbitrary interactions selected because they look favorable;
- post-outcome information;
- timestamps or identifiers acting as memorization keys;
- descriptors sourced from runtime-only or ungoverned files;
- any candidate requiring a production behavior change.

The final candidate inventory must be committed before canonical result generation.

## Forward outcomes

Forward outcomes must be deterministic and calculated from governed BTC market data using fixed timestamps and fixed price-selection rules.

The initial allowed outcome families are:

1. Forward simple return.
2. Forward maximum favorable excursion.
3. Forward maximum adverse excursion.
4. Forward realized volatility.
5. Binary positive-return indicator derived directly from the fixed forward return.

No outcome may incorporate transaction costs, slippage, leverage, position sizing, execution assumptions, stop-loss logic, take-profit logic, or portfolio behavior.

## Evaluation horizons

The exact horizon set must be fixed before result inspection.

Proposed initial horizons:

- 2 hours;
- 6 hours;
- 24 hours;
- 72 hours;
- 168 hours.

A horizon may be removed before implementation if governed data coverage cannot support it consistently. Horizons may not be added or removed after observing candidate results without a new board transition and explicit rerun designation.

## Temporal anchoring

Each outcome must begin from a single predeclared episode anchor timestamp already present or deterministically derivable from governed episode artifacts.

The anchor definition must avoid look-ahead. If multiple plausible anchors exist, the implementation must fail closed until one is selected in the specification.

Event-family outcomes must use a predeclared family anchor rule that does not select the best-performing episode within the family.

## Chronological evaluation

Random train-test splits are prohibited.

The campaign must use deterministic chronological evaluation.

Initial evaluation design:

- expanding-window folds;
- fixed chronological ordering;
- no future observations in candidate estimation;
- fixed fold boundaries derived without reference to outcomes;
- both episode-resolution and event-family-resolution fold reporting.

The exact fold count, boundary rule, and minimum observations per fold must be committed before canonical result generation.

## Candidate evidence metrics

For every candidate value and horizon, the campaign should report, where support permits:

- total episode support;
- total event-family support;
- chronological fold support;
- mean forward return;
- median forward return;
- positive-return rate;
- mean maximum favorable excursion;
- mean maximum adverse excursion;
- mean forward realized volatility;
- out-of-sample directional consistency across folds;
- episode-versus-event-family sign agreement;
- episode-versus-event-family magnitude divergence;
- null, insufficient-support, contradictory, or eligible status.

No p-value, confidence label, Sharpe ratio, alpha estimate, annualization, or deployable-strategy score is authorized in the initial campaign unless separately added to the board before implementation.

## Ranking rules

The primary artifact may rank candidates only through a deterministic, predeclared evidence ordering.

Ranking must prioritize:

1. sufficient event-family support;
2. out-of-sample fold consistency;
3. episode-versus-event-family directional agreement;
4. deterministic effect magnitude;
5. stable support across horizons.

The implementation may not tune weights after observing results.

A candidate with favorable episode evidence but contradictory or insufficient event-family evidence must not be ranked as supported.

A candidate with mixed signs across chronological folds must be marked unstable or contradictory according to the predeclared rule.

## Minimum support and fail-closed states

Exact minimum-support values must be committed before result inspection.

Required fail-closed states include:

- missing governed source;
- source-hash disagreement;
- duplicate episode identity;
- unknown event-family membership;
- ambiguous anchor;
- unavailable forward coverage;
- insufficient episode support;
- insufficient event-family support;
- insufficient chronological fold support;
- contradictory episode and event-family direction;
- non-finite metric;
- malformed serialization;
- output-directory collision.

Insufficient or contradictory evidence must remain visible in canonical outputs rather than being silently dropped.

## Canonical outputs

Under `artifacts/core_v1_historical_alpha_discovery/`:

- `btc_core_v1_alpha_candidates.json`;
- `btc_core_v1_alpha_candidates.csv`;
- `btc_core_v1_alpha_discovery_report.md`;
- `btc_core_v1_alpha_discovery_manifest.json`.

A deterministic fold-level diagnostic CSV may be added before implementation if required to reconcile the ranked results. Any added output must be documented in the campaign board first.

## Serialization and replay requirements

- deterministic sorting;
- strict JSON with sorted keys and no NaN;
- LF-only text;
- no generated timestamps in canonical payloads;
- deterministic payload digest;
- newly created or explicitly empty output directory only;
- staging-directory publication;
- atomic publication;
- no governed-source overwrite;
- source hashes verified before and after generation;
- two governed runs must be byte-identical.

## Required tests

Focused tests must cover at least:

- source-hash verification;
- chronological ordering;
- no-look-ahead outcome construction;
- event-family reconciliation;
- mixed-family handling;
- insufficient-support handling;
- contradictory-evidence handling;
- deterministic ranking;
- strict finite serialization;
- replay byte identity;
- output-directory fail-closed behavior.

## Acceptance gates

1. Exact governed source paths and hashes are committed before result generation.
2. Candidate inventory is committed before result generation.
3. Outcome horizons, anchor rules, fold construction, minimum support, and ranking rules are committed before result generation.
4. Focused Campaign #43 tests pass.
5. Full repository suite passes with no new failures.
6. Two governed runs produce byte-identical outputs.
7. Canonical text outputs are LF-only.
8. Governed source identities and hashes remain unchanged.
9. Episode and event-family counts reconcile.
10. Chronological folds reconcile and contain no look-ahead.
11. Null, insufficient-support, and contradictory evidence remain visible and fail closed.
12. Scope review finds no runtime, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard changes.
13. The final report makes no deployable-alpha or production recommendation.

## Pending specification decisions

Before implementation, Campaign #43 must resolve and commit:

- exact governed source paths and hashes;
- exact eligible candidate inventory;
- exact episode anchor;
- exact event-family anchor and aggregation rules;
- exact price field and timestamp matching rule;
- final horizon set;
- chronological fold count and boundary construction;
- minimum episode, event-family, and fold support;
- deterministic ranking tuple;
- whether a fold-level canonical diagnostic artifact is required.

No result inspection or optimization is authorized until these decisions are resolved in the board and this document.
