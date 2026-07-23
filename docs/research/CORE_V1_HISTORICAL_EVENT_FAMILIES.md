# Core v1 Historical Event Families

## Campaign

**Campaign #41 — Deterministic overlap-aware historical event families**

**Classification:** Research primary; engineering secondary.

**Milestone:** Specification only.

## Research question

Can overlapping or immediately adjacent historical collapse episode windows be grouped into deterministic, replay-safe event families so Itera can report both episode-level and event-family-level descriptive results without mutating the existing episode artifacts?

## Why this campaign exists

Campaign #40 classified 122 historical episode rows, but many rows originate from overlapping rolling windows and therefore are dependent observations. Episode-row counts must not be interpreted as counts of independent historical events.

This campaign defines an auditable event-family layer above the existing rows. It does not replace, delete, relabel, or rewrite the source episode artifacts.

## Governing constraints

The specification and any later implementation must remain:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- interval-based;
- explicit about source membership;
- separate from runtime behavior;
- independent of model retraining;
- independent of thresholds, orders, NAV, and exposure mutation.

## Source model

Each source episode must provide a stable episode identity and a closed or half-open interval representation derived from existing artifact fields. The final field mapping must be documented from the real source schema before implementation begins.

The implementation must fail closed when:

- required identity or boundary fields are missing;
- timestamps or row indices are malformed;
- an interval ends before it begins;
- duplicate episode identities disagree;
- source artifact identities do not reconcile;
- non-finite numeric values enter governed output.

## Proposed grouping rule

Event families are connected components under deterministic interval adjacency.

After sorting source episodes by:

1. start boundary ascending;
2. end boundary ascending;
3. stable episode identity ascending;

an episode belongs to the current family when its start boundary overlaps the current family interval or is immediately adjacent under the explicitly selected boundary unit. Otherwise, it starts a new family.

The family interval expands to the minimum member start and maximum member end.

### Open specification decision

The exact meaning of "immediately adjacent" must be resolved from the source artifact's native boundary representation:

- row-index adjacency: `next_start <= current_end + 1`; or
- timestamp adjacency based on the expected bar cadence.

No tolerance, learned distance, or heuristic gap may be introduced implicitly.

## Stable identity

Each family must have a stable identifier derived only from canonical governed content. The canonical identity payload should include:

- specification version;
- normalized source artifact identifier;
- ordered source episode identities;
- family start boundary;
- family end boundary.

The identifier must not depend on absolute paths, operating system separators, dictionary iteration order, runtime time, or random values.

## Required family record

Each event-family record must include at least:

- family identifier;
- stable ordinal in the full output;
- start and end boundary;
- duration in the source boundary unit;
- ordered source episode identities;
- source episode count;
- subtype composition counts;
- recovery-outcome composition counts;
- similarity-to-current summary;
- explicit mixed-label flags;
- research-only and observation-only markers.

## Mixed-label handling

Source labels must be preserved, never collapsed through an undocumented winner rule.

For subtype and recovery outcome, each family must report:

- deterministic count by label;
- whether the family is homogeneous or mixed;
- a dominant label only when a deterministic rule is specified;
- ties explicitly, rather than resolved through incidental ordering.

The specification must decide whether a dominant label is necessary. Composition counts are mandatory; a dominant label is optional.

## Similarity-to-current handling

The family-level similarity summary must remain descriptive. Candidate measures include maximum, median, and latest-window similarity, but the final specification must state which values are emitted and why.

The Campaign #40 recommendation specifically requires latest-window similarity. "Latest" must be determined by the governed episode boundary and then stable episode identity as a tie-breaker.

## Recovery handling

Recovery outcomes remain bounded-horizon descriptions. Persistent collapse means no recovery observed within the governed horizon, not permanent non-recovery.

Family reporting must preserve the complete member outcome composition. It must not infer a family recovery probability or calibrated forecast.

## Required outputs for a later implementation milestone

Provisional outputs:

- event-family membership CSV;
- event-family records JSON;
- event-family summary JSON;
- human-readable event-family report Markdown.

All generated text artifacts must use strict serialization, stable ordering, normalized repository-relative source identifiers, and explicit LF line endings.

## Verification requirements

Before any implementation milestone can merge:

- focused unit tests pass;
- real source schema and identity reconciliation pass;
- source episode membership is complete and exactly once;
- family ordering and identifiers are stable;
- generated artifacts are byte-identical across replay;
- source artifacts retain identical hashes;
- full repository regression suite passes;
- no runtime, threshold, order, NAV, or exposure behavior changes.

## Explicit non-goals

- learned clustering;
- semantic or model-generated event labels;
- predictive recovery modeling;
- calibrated probabilities;
- deletion or mutation of Campaign #40 artifacts;
- strategy logic;
- runtime integration;
- threshold changes;
- model retraining;
- order, NAV, or exposure mutation.

## Specification acceptance gates

The specification-only milestone is complete when:

1. the real source boundary fields and units are documented;
2. immediate adjacency is defined exactly;
3. canonical family identity is finalized;
4. mixed subtype and recovery rules are finalized;
5. similarity summary fields are finalized;
6. output schemas and ordering are explicit;
7. fail-closed validation rules are complete;
8. verification commands and expected evidence are documented;
9. no implementation code has been introduced.

## First executable step

Inspect the three Campaign #40 source artifacts and existing taxonomy code to document the exact episode identity, start boundary, end boundary, recovery, subtype, and similarity fields. Resolve the adjacency unit from those governed inputs before finalizing the grouping rule.