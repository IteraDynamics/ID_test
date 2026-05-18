# Itera Research Protocol (Skill)

## Purpose

Define how LLMs should conduct strategy, overlay, allocator, and governor research.

---

## Step 1 — Diagnose before building

Always start by answering:

- What problem are we solving?
- Which layer is this (L2 strategy, L3 governor, allocator, etc.)?
- What is the expected impact on the portfolio?

Do not write code before answering these.

---

## Step 2 — Define role explicitly

Every proposal must declare:

```text
Role: strategy / overlay / allocator / governor
```

Ambiguous role = invalid research.

---

## Step 3 — Define success criteria

Use portfolio-relevant metrics:

- Sharpe
- Calmar
- Max Drawdown
- Turnover / cost impact

Avoid optimizing only:

- raw CAGR

---

## Step 4 — Respect cost reality

All research must assume:

- fees
- slippage
- turnover impact

High-turnover strategies must justify their existence under cost.

---

## Step 5 — Avoid common failure modes

Do NOT:

- blindly build mean reversion variants
- treat zero correlation as sufficient
- ignore dominant crypto beta
- optimize thresholds without structural reasoning

---

## Step 6 — Produce structured output

Every research result must include:

```text
VERDICT: proceed / iterate / abandon
REASON:
PORTFOLIO IMPACT:
NEXT STEP:
```

---

## Step 7 — Preserve Fund v1 validation

Critical rule:

> Do not modify the live Fund v1 system during ongoing paper trading.

All new research must remain isolated.