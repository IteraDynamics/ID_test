# Itera Research Roadmap

## Purpose

This roadmap identifies the sequence of research questions that should compound Itera's knowledge. It is not a feature backlog and does not authorize implementation by itself.

## Completed foundation

- Deterministic research and replay discipline.
- Historical collapse episode extraction and signature artifacts.
- Core v1 historical regime taxonomy.
- Portable, strict artifact serialization and digest verification.
- Deterministic overlap-aware historical event families.

## Completed frontier

### Campaign #41 — Overlap-aware historical event families

Campaign #41 implemented and verified a deterministic interval-based method that groups overlapping or exactly one-canonical-bar-adjacent historical collapse windows into auditable event families.

Accepted knowledge gain:

- `122` governed episode rows reconcile to `14` independent historical event families;
- episode membership remains explicit and exhaustive;
- mixed intrinsic-subtype and recovery-outcome composition is preserved rather than collapsed to a dominant label;
- episode-level and family-level summaries coexist without mutating Campaign #40 artifacts;
- two governed runs produced five byte-identical, LF-only artifacts;
- the descriptive layer remains observation-only and separate from runtime behavior.

## Proposed next frontier

### Campaign #42 candidate — Episode-resolution versus event-family-resolution taxonomy

Evaluate how the governed Core v1 descriptive taxonomy changes when evidence is counted at episode resolution versus independent event-family resolution.

The campaign should remain specification-first, deterministic, replay-safe, observation-only, and fail-closed. It should answer descriptive questions such as:

- which subtype and recovery distributions materially change after overlap de-duplication;
- whether repeated episode windows overstate the apparent prevalence of particular historical structures;
- which findings remain stable across both resolutions;
- how mixed-label families should be represented in comparative summaries;
- what conclusions are unsupported because the effective independent-event count is only `14`.

This candidate does not authorize implementation. Campaign #42 scope, inputs, output schemas, acceptance gates, and branch must be separately approved on the Campaign Board.

## Candidate sequence after Campaign #42

The sequence remains provisional and must be re-evaluated using Campaign #42 evidence.

1. Evaluate cross-asset portability of the descriptive taxonomy.
2. Study event-family transitions and bounded recovery structure.
3. Explore strategy or sleeve hypotheses only after the descriptive foundation is sufficient.

## Deferred until explicitly authorized

- learned clustering;
- predictive recovery models;
- calibrated probabilities;
- strategy promotion;
- runtime integration;
- threshold, order, NAV, or exposure changes.

## Roadmap review rule

Update this document when a completed campaign materially changes dependencies, invalidates an assumption, or reveals a higher-value next research question.
