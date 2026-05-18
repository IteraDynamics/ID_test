# Itera Code Change Protocol (Skill)

## Purpose

Ensure all code changes are safe, explicit, and reproducible.

---

## Core rules

1. Prefer full-file replacements over partial snippets
2. Never introduce hidden behavior changes
3. Keep research code separate from runtime code

---

## Branch discipline

- Research stays in research branches
- Production stability lives in main
- Do not merge experimental logic into runtime without gating

---

## Runtime safety

Any new runtime feature must:

- be behind a flag OR
- not be imported into live flow

Example:

```text
DEFENSIVE_OVERLAY_ENABLED = 0
```

---

## Testing expectations

All new components must include:

- deterministic unit tests
- edge-case handling

---

## Output format

Every code task must include:

```text
Goal:
What was built:
Files changed:
How to run:
```

---

## Critical constraint

> Do not modify Fund v1 paper-trading behavior unless explicitly instructed.