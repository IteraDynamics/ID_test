# Itera Governor Design Protocol (Skill)

## Purpose

Define how to design, classify, and evaluate Layer 3 governors.

Governors are not alpha. They shape risk.

---

## Definition

A governor is a Layer 3 component that:

- takes portfolio or market state
- outputs a constraint or scaling factor
- never generates independent alpha intent

Examples:

- exposure scaling
- risk caps
- capital throttling

---

## Classification

Every governor must declare its type:

```text
Type: defensive / risk cap / execution / allocator modifier
```

The current promoted candidate:

```text
Type: defensive exposure governor
```

---

## Design constraints

Governors must be:

- closed-bar only
- deterministic
- monotonic in risk (never increase exposure beyond base)
- low-frequency (avoid churn)
- interpretable (clear reason for state)

---

## Core design pattern

Typical defensive governor structure:

1. Risk signal (e.g., drawdown, volatility, trend)
2. Trigger condition
3. Confirmation window
4. Active state (risk-off)
5. Release condition
6. Release confirmation
7. Exposure scale output

---

## Evaluation criteria

A governor is successful if it improves portfolio behavior, not standalone returns.

Evaluate:

- MaxDD improvement
- Calmar improvement
- Sharpe stability
- recovery time (peak → trough → recovery)
- cost impact of transitions

---

## Acceptable trade-off

Governors may:

- slightly reduce CAGR

They must not:

- significantly degrade Sharpe or Calmar
- introduce excessive switching costs

---

## Failure modes

Reject governors that:

- trigger too frequently (high churn)
- react to noise instead of regime
- improve only a single historical event
- delay recovery too much
- rely on fragile thresholds without structural reasoning

---

## Integration rules

Governors must:

- operate after allocation, before execution
- scale exposure, not rewrite strategy intent
- be optional (feature flag or isolated integration)

---

## Promotion criteria

A governor may be promoted to Fund v2 if:

- cost-adjusted improvement persists
- improvements are not single-event artifacts
- behavior is stable and interpretable
- unit tests pass

---

## Itera-specific promoted design

```text
A_light_dd20_trend
```

Properties:

- ~20% drawdown trigger
- EMA trend filter
- confirmation / release windows
- exposure scale ≈ 0.75

Outcome:

- improved drawdown profile
- preserved Sharpe
- acceptable CAGR drag

Status:

- Fund v2 candidate
