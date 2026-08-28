# Campaign #42 — Core v1 Episode-Resolution Versus Event-Family-Resolution Taxonomy

## Authorization

Campaign #42 is authorized as a narrow BTC-only descriptive research campaign on branch `agent/campaign-42-event-robustness`.

## Exact research question

How do governed Core v1 intrinsic-subtype and recovery-outcome descriptions change when measured as overlapping episode observations versus label presence within deterministic historical event families?

## Governed inputs

- `artifacts/core_v1_historical_event_families/btc_extended_up_event_families.json`
- `artifacts/core_v1_historical_event_families/btc_extended_up_event_family_membership.csv`

The implementation must record and preserve the exact source hashes in the output manifest and must fail closed if either source changes during generation.

## Counting rules

### Episode resolution

Each governed episode contributes exactly one observation to its intrinsic-subtype label and exactly one observation to its recovery-outcome label.

### Event-family presence resolution

Each event family contributes at most one presence observation to each label contained in the corresponding Campaign #41 count map.

A mixed family may therefore contribute presence to more than one label. Presence shares are descriptive prevalence across families and are not a mutually exclusive probability distribution.

### Event-family homogeneous resolution

A family contributes to a label's homogeneous count only when that label is the sole label represented in the corresponding family count map.

### Mixed-label rule

Mixed families remain mixed. Campaign #42 must not infer, select, rank, or persist a dominant family label.

## Derived measurements

For every governed label:

- episode count and share;
- event-family presence count and share;
- event-family homogeneous count and share;
- family-presence share minus episode share;
- episode amplification ratio, defined as episode count divided by family-presence count.

All calculations are direct descriptive arithmetic. Campaign #42 defines no materiality threshold, confidence label, significance test, predictive claim, or alpha claim.

## Canonical outputs

Under `artifacts/core_v1_event_robustness/`:

- `btc_extended_up_event_robustness.json`;
- `btc_extended_up_event_robustness_labels.csv`;
- `btc_extended_up_event_robustness_report.md`;
- `btc_extended_up_event_robustness_manifest.json`.

## Determinism and serialization

- sorted label keys and records;
- stable family and membership ordering;
- strict JSON with sorted keys and no NaN;
- LF-only text outputs;
- no generated timestamp in canonical payloads;
- deterministic digest over the comparison payload;
- newly created or explicitly empty output directory only;
- staging-directory publication;
- no source overwrite;
- source hashes checked before and after generation.

## Authorized file surfaces

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/CORE_V1_EVENT_ROBUSTNESS.md`;
- `research/ml/validation/event_robustness.py`;
- `scripts/run_core_v1_event_robustness.py`;
- `tests/test_event_robustness.py`;
- `artifacts/core_v1_event_robustness/**`.

No other file surface is authorized without a later board transition.

## Acceptance gates

1. Focused Campaign #42 tests pass.
2. Full repository test suite passes with no new failures.
3. Two governed runs produce byte-identical outputs.
4. All canonical text outputs are LF-only.
5. Governed source identities and hashes remain unchanged.
6. Output schemas and cross-artifact counts reconcile.
7. Scope review finds no runtime, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard changes.

## Non-goals

Campaign #42 does not authorize:

- production runtime integration;
- model training or retraining;
- threshold changes;
- signal, intent, order, or execution changes;
- portfolio construction;
- NAV or exposure mutation;
- dashboard integration;
- cross-asset portability;
- predictive or statistical-independence claims;
- strategy or alpha recommendations.

## Go decision

**GO.** Implementation and governed artifact generation are explicitly authorized within this document and the campaign board, subject to the constraints and acceptance gates above.
