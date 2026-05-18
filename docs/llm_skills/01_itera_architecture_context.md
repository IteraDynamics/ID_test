# Itera Architecture Context (Skill)

## Purpose

Provide the current ground truth of Itera Dynamics so LLMs operate with correct assumptions.

---

## System overview

Itera Dynamics is a deterministic, multi-layer systematic trading architecture:

- **Layer 1 — Regime Engine**: classifies market state (trend, compression, expansion, etc.)
- **Layer 2 — Strategy Modules**: generate exposure intent (no side effects)
- **Layer 3 — Allocation & Governors**: scale, constrain, and route capital

All logic must be:

- closed-bar only
- no lookahead
- deterministic
- auditable

---

## Fund v1 (current live paper-trading baseline)

Structure:

- BTC_1H
- BTC_4H
- ETH_1H
- ETH_4H

Allocation:

- equal-weight (25% each)

Strategy:

- trend_following_v8_ecap60_add80

Properties:

- calibrated
- deterministic backtest harness validated
- realistic fees and slippage applied

Status:

- currently paper trading
- currently flat (acceptable behavior)
- awaiting first trade cycle (entry → hold → exit)

**Critical rule:**

Do not modify Fund v1 runtime behavior until at least one full paper-trade cycle is observed.

---

## Fund v2 (emerging research direction)

Candidate improvement:

- DefensiveExposureGovernor (Layer 3)

Promoted design:

- A_light_dd20_trend

Behavior:

- reduces exposure during drawdowns + bearish trend
- scale = 0.75
- preserves Sharpe while improving drawdown profile

Status:

- backtest validated
- cost-adjusted validated
- unit-tested
- NOT integrated into live runtime

---

## Research conclusions (important constraints)

Rejected or limited:

- ETH/BTC rotation as external sleeve (too correlated)
- ETH/BTC allocator overlay (degrades performance)
- high-frequency orthogonal crypto strategies (cost dominated)

Valid but limited:

- post-capitulation long (event overlay, not capital sleeve)

Key insight:

> Crypto-only long strategies share dominant beta. True portfolio improvement requires either risk reduction (governors) or different return drivers.

---

## Operating principles

- Preserve attribution between Fund v1 and research
- Do not mix experimental logic into live system prematurely
- Always consider execution costs and turnover
- Prefer simple, robust mechanisms over complex optimizers
- Treat governance (Layer 3) as first-class, not secondary

---

## LLM expectations

When working on Itera tasks:

- Correctly identify whether the task is:
  - strategy (Layer 2)
  - overlay (Layer 3)
  - allocator
  - research-only

- Explicitly state role before coding
- Do not introduce hidden state or side effects
- Do not assume backtest results generalize without cost validation