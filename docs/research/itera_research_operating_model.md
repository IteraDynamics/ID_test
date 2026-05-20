# Itera Research Radar Operating Model

## Purpose

This document defines how Itera Dynamics uses an agentic research process without allowing agents to control runtime trading behavior.

The goal is to solve a specific founder/operator problem:

```text
Itera has a growing deterministic validation engine, but the opportunity space is too large for one person and ad hoc chat sessions to continuously track across crypto, macro, equities, sectors, factors, volatility, commodities, and capital destinations.
```

The research radar exists to widen idea coverage, prioritize hypotheses, and convert promising concepts into deterministic ID_test validation tasks.

It does not place trades.
It does not modify runtime governors.
It does not override live systems.
It does not promote candidates without human review.

---

## Core Principle

```text
Agentic idea generation.
Deterministic validation.
Human promotion decision.
Deterministic runtime.
```

Agents may produce research memos, candidate hypotheses, priority rankings, and test proposals.

Only deterministic research scripts and validated artifacts may support promotion into Itera architecture.

---

## What Is Being Adapted

The AI-fund daily cycle is useful as a research operating rhythm:

```text
market scan
macro brief
PM / lane briefings
analyst research
risk report
capital report
synthesis memo
ops check
```

For Itera, this becomes a research-radar cycle.

The output is not trade recommendations.

The output is:

```text
ranked research ideas
candidate memos
validation tasks
risk / capital concerns
archive / iterate / proceed decisions
```

---

## Itera Research Radar Cycle

### Stage 1 — Market Monitor

Purpose:

- capture current market conditions relevant to research prioritization
- identify unusual moves, regime shifts, or stress conditions
- update the context used by research lanes

Coverage:

- BTC / ETH
- SPY / QQQ
- GLD / BIL / SHY / IEF / TLT
- sector ETFs
- volatility proxies
- factor ETFs
- dollar / rates proxies when available

Output:

```text
Current market overlay.
Market observations that may affect research priority.
No trade instructions.
```

---

### Stage 2 — Macro Brief

Purpose:

- interpret cross-asset conditions for research purposes
- identify macro-sensitive destination candidates
- decide whether current conditions raise or lower priority for certain tests

Research questions:

- Are rates supportive of cash-like destinations such as BIL / SGOV / SHY?
- Is GLD behaving as a useful diversifier or facing dollar/yield headwinds?
- Are duration assets such as IEF / TLT worth retesting under a filtered regime?
- Does dollar strength deserve testing as a crypto risk-off confirmation signal?

Output:

```text
Macro research implications.
Candidate destination ideas.
Priority changes for the research queue.
```

---

### Stage 3 — Research Lane Briefs

Each lane acts like a scoped analyst team. Lanes produce research candidates, not trades.

#### Crypto Lane

Coverage:

- BTC / ETH regimes
- BTC/ETH relative strength
- volatility and drawdown states
- sleeve interaction
- crypto exposure throttles

Candidate outputs:

- BTC/ETH dynamic allocator
- ETH sleeve diagnostic
- realized volatility governor
- crypto trend confirmation variants

#### Macro / Cross-Asset Lane

Coverage:

- GLD
- BIL / SGOV / SHY
- IEF / TLT
- UUP or dollar proxy
- commodities
- broad macro destinations

Candidate outputs:

- GLD risk-off allocator
- BIL defensive allocator
- dollar-confirmed crypto risk-off rule
- duration-only-under-falling-yields destination rule

#### Equity / Factor Lane

Coverage:

- SPY / QQQ
- RSP / QQQE
- MTUM / QUAL / USMV / SPLV
- VTV / VUG
- IWM / MDY

Candidate outputs:

- low-vol defensive destination basket
- factor momentum allocator
- equal-weight versus cap-weight equity destination comparison

#### Sector Lane

Coverage:

- XLU / XLP / XLV defensive sectors
- XLK / SMH / IGV growth and AI infrastructure
- XLE / XLF / XLI / XLB cyclicals and inflation sensitivity

Candidate outputs:

- defensive sector destination matrix
- risk-on sector basket during crypto-friendly states
- sector rotation as macro confirmation, not discretionary stock picking

#### Volatility / Risk Lane

Coverage:

- BTC realized volatility
- equity volatility proxies
- drawdown acceleration
- crash-window diagnostics
- volatility expansion / compression states

Candidate outputs:

- volatility-confirmed risk-off governor
- crash-risk throttle
- volatility smoothing sleeve research

#### Portfolio Construction Lane

Coverage:

- sleeve correlations
- allocation weights
- risk budgets
- state transitions
- candidate interactions

Candidate outputs:

- static versus dynamic allocation comparison
- GLD/BIL blend during risk-off
- crypto scale sensitivity
- portfolio-level rebalance diagnostics

#### Execution / Cost Lane

Coverage:

- turnover
- rebalance events
- instrument availability
- cost drag
- cash/yield implications
- deployability constraints

Candidate outputs:

- CFO-style cost review
- transition count and estimated friction report
- instrument eligibility report

---

### Stage 4 — Candidate Generation

Each lane may propose ideas in the following required format:

```text
Title:
Research lane:
Portfolio role:
Hypothesis:
Candidate instruments:
Deterministic rule candidate:
Required data:
Baseline:
Guardrails:
Expected failure mode:
Priority:
Next ID_test task:
```

An idea that cannot be expressed as a deterministic test remains a memo and is not promoted.

---

### Stage 5 — Risk Review

The CRO-style review asks:

- Does the idea reduce drawdown or only improve headline CAGR?
- Is it overfit to one event?
- Does it introduce concentration risk?
- Is the risk-off state too active?
- Does the rule miss recoveries or create false positives?
- Are stress windows improved?
- Does it survive robustness checks around nearby parameters?

Default guardrail examples:

```text
Calmar > 1.20
MaxDD materially better than baseline
Risk-off active under 30% unless explicitly justified
No single-episode dependency
False positives documented
```

---

### Stage 6 — Capital / Cost Review

The CFO-style review asks:

- Is the instrument tradeable in the intended brokerage/runtime?
- How many transitions occur?
- What is the estimated rebalance friction?
- What capital moves during each state change?
- Does the idea require full liquidation or partial scaling?
- What happens to idle cash?
- Does the candidate still work after costs?

This stage is required before promotion beyond research candidate status.

---

### Stage 7 — Research Radar Memo

The synthesis memo should update:

```text
docs/research/itera_research_radar.md
```

It should include:

- current market overlay
- active validated candidates
- validation queue
- idea backlog by lane
- archived / rejected ideas
- top recommended next tests
- known risks / blockers

The memo should recommend research priorities, not trades.

---

### Stage 8 — Repo Output

Permitted outputs:

```text
docs/research/itera_research_radar.md
docs/research/candidates/<candidate_id>/candidate_memo.md
docs/research/candidates/<candidate_id>/diagnostic_summary.md
docs/research/candidates/<candidate_id>/risk_review.md
docs/research/candidates/<candidate_id>/capital_review.md
docs/research/candidates/<candidate_id>/decision.md
artifacts/research_radar/context_pack.md
```

Not permitted without explicit human approval:

```text
runtime changes
broker changes
live execution changes
production governor changes
strategy promotion
capital allocation changes
```

---

## Promotion Statuses

Every candidate should have one status:

```text
IDEA
BACKLOG
ACTIVE TEST
VALIDATED CANDIDATE
NEEDS RISK REVIEW
NEEDS CAPITAL REVIEW
PROCEED
ITERATE
ARCHIVE
```

---

## Current Worked Example

The first worked example is:

```text
State-confirmed GLD risk-off allocator
```

Current evidence:

- GLD destination
- Fund v1 drawdown trigger around -18% to -20%
- BTC below SMA200 / SMA220 trend confirmation
- release mode: either drawdown recovery or BTC trend recovery
- crypto scale during risk-off: 0%
- risk-off active around 27% to 30%
- Calmar improved materially versus Fund v1 baseline
- episode attribution showed 10 wins / 4 losses across included episodes

Current status:

```text
VALIDATED CANDIDATE — needs BIL comparison, capital/cost review, and further robustness checks.
```

---

## Summary

The agentic research radar is an idea coverage system.

It exists to help Itera discover and prioritize research opportunities across many tradable lanes without allowing LLMs to become the execution engine.

The radar expands the search space.
ID_test remains the truth machine.
The human founder makes promotion decisions.
Runtime remains deterministic.