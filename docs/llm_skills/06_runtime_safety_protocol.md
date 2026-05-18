# Itera Runtime Safety Protocol (Skill)

## Purpose

Ensure that all runtime and paper-trading behavior remains safe, controlled, and attributable.

---

## Core principle

Itera is now an operated system, not just a research environment.

Runtime behavior must be stable and explainable at all times.

---

## Fund v1 protection rule

```text
Do not modify Fund v1 paper-trading behavior during validation.
```

This includes:

- strategy changes
- allocator changes
- governor insertion
- parameter changes

Until at least one full trade cycle is observed.

---

## Feature gating

All new runtime features must be:

- disabled by default, OR
- completely isolated from execution path

Example:

```text
DEFENSIVE_OVERLAY_ENABLED = 0
```

---

## Separation of concerns

Maintain clear boundaries:

- research scripts ≠ runtime system
- analysis outputs ≠ execution inputs
- experimental overlays ≠ live governors

---

## Observability requirements

The system must always expose:

- current exposure
- position
- cash
- NAV
- fees and slippage
- governor state (if active)

No hidden state.

---

## Invariants

The following must always hold:

```text
NAV = cash + position * price
```

Violations must be logged and treated as errors.

---

## Change discipline

Before merging any runtime change:

- confirm no change to Fund v1 behavior OR
- explicitly gate new behavior behind a flag

---

## Paper trading expectations

Flat behavior is acceptable.

Do not interpret inactivity as failure if:

- signals are not triggered
- governors are inactive

---

## Deployment readiness

A feature is ready for runtime integration only if:

- backtest validated
- cost-adjusted validated
- unit-tested
- behavior understood
- impact isolated

---

## Itera-specific current state

- Fund v1: active paper trading baseline
- Defensive governor: validated but NOT deployed

This separation must be preserved until explicit promotion to Fund v2.