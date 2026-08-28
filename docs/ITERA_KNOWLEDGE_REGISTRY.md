# Itera Knowledge Registry

## Purpose

This registry tracks durable research domains, their maturity, supporting evidence, and the next unanswered question. It records knowledge, not software inventory.

## Maturity scale

- **L0 — Question:** important problem identified; no governed evidence yet.
- **L1 — Exploration:** initial observations or hypotheses exist.
- **L2 — Specified:** deterministic methodology is defined but not fully implemented and verified.
- **L3 — Validated:** implementation, tests, replay, and documentation support the result.
- **L4 — Institutionalized:** reused by subsequent governed research.
- **L5 — Foundational:** underpins multiple capabilities and changes only with extraordinary evidence.

## Current registry

| Domain | Maturity | Confidence | Evidence | Next question |
|---|---:|---|---|---|
| Deterministic research and replay discipline | L5 | Very high | Repository-wide tests, artifact digests, replay practices, campaign governance | How should the discipline scale without slowing useful research? |
| Historical collapse episode extraction | L3 | High within documented scope | Existing episode and signature artifacts used by Campaign #40 | How much dependence is introduced by overlapping windows? |
| Historical regime taxonomy | L3 | High within BTC extended-up sample | PR #40; 122 classified episodes; byte-identical replay; documented caveats | How do results change when summarized by event family rather than episode row? |
| Portable research artifact I/O | L4 | Very high | LF-only outputs, repo-relative identifiers, strict JSON, cross-platform hardening | Maintain and reuse. |
| Overlap-aware historical event families | L0 | None | Recommended by Campaign #40; no specification yet | What deterministic grouping and mixed-label rules are auditable and replay-safe? |
| Cross-asset taxonomy portability | L0 | None | Not yet tested | Which definitions generalize without asset-specific reinterpretation? |
| Event-family transition structure | L0 | None | Blocked on event-family representation | What descriptive transitions recur across independent events? |
| Recovery modeling | L0 | None | Existing recovery labels are descriptive and horizon-bounded | What additional evidence is required before any predictive or probabilistic claim? |
| Portfolio sleeve research | L0 | None | Long-term architectural direction only | Which validated research domains justify independent strategy hypotheses? |
| Execution latency as a research constraint | L3 | High | Jump Risk v0 retirement: cadence audit (808 cycles, ~1.5-1.7 effective bars) plus lag sensitivity showing 98% edge decay by bar 2 | Which candidate signal horizons are compatible with a ~1.5-bar decision lag, and how should horizon feasibility be tested before a campaign is chartered? |
| Audit falsifiability | L4 | Very high | Jump Risk timing audit found structurally incapable of failing; corrected with provenance checks plus a lookahead canary that must fire each run | Which other governed checks in this repository cannot fail, and how are they identified systematically? |

## Registry update rule

A campaign closeout must update relevant rows with new maturity, evidence, caveats, and next questions. Maturity must never increase solely because code was written.