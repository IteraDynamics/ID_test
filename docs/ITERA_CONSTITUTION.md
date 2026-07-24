# Itera Constitution

## Purpose

This document defines the durable governance rules for Itera Dynamics research and engineering.

## Research integrity

- Observation, hypothesis, specification, implementation, validation, replay, and documentation remain distinct stages.
- Meaningful research or behavioral changes require explicit scope, acceptance criteria, and evidence.
- Intuition may propose a hypothesis; evidence determines whether it advances.

## Determinism and replay

- Identical governed inputs must produce identical governed outputs.
- Ordering, serialization, path handling, and identifiers must be explicit and stable.
- Research artifacts must fail closed on malformed, incomplete, mismatched, or non-finite input.
- Replay evidence is required whenever an output claims deterministic identity.

## Research and production separation

- Research code is observation-only unless a campaign explicitly authorizes otherwise.
- Runtime, thresholds, orders, NAV, and exposure must not change as a side effect of research.
- Production executes validated and explicitly authorized behavior; it does not perform open-ended research.

## Core stability

Core behavior changes only under an explicitly authorized campaign with understood compatibility, deterministic tests, replay evidence, and documented consequences.

## Campaign governance

Each active campaign must identify:

- one objective;
- one working branch;
- explicit included and excluded scope;
- acceptance and verification gates;
- a concrete next executable step;
- evidence required before merge.

Campaigns must not silently expand into runtime or portfolio behavior.

## Documentation and institutional memory

A campaign is incomplete until its methodology, evidence, caveats, and remaining uncertainty are documented. Negative or inconclusive results must be preserved rather than hidden.

## Amendment standard

Changes to this Constitution should be rare, explicit, reviewed independently from ordinary implementation, and must not weaken determinism, replay safety, fail-closed behavior, or research-production separation.