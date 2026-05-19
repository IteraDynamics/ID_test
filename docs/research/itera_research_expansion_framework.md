# Itera Research Expansion Framework

## Purpose

This document defines the next stage of Itera Dynamics research.

Itera began as a deterministic crypto trading architecture centered on BTC/ETH trend participation, regime awareness, execution modeling, and portfolio-level governance. That foundation remains the core of the platform.

The next phase is not to replace that foundation. The next phase is to expand the research map so Itera can evaluate additional return drivers, defensive destinations, and capital allocation roles without compromising the deterministic Fund v1 architecture.

The goal is to evolve Itera from a single-domain crypto system into a broader systematic fund research platform.

---

## Current foundation

The current Itera architecture is built around:

- deterministic closed-bar strategies
- explicit regime and strategy contracts
- no-lookahead backtesting
- execution cost modeling
- paper-trading discipline
- artifact-driven validation
- risk governors and capital allocation research

Fund v1 remains the current crypto baseline:

- BTC_1H
- BTC_4H
- ETH_1H
- ETH_4H
- equal-weight capital allocation
- `trend_following_v8_ecap60_add80`

This baseline should remain protected while new research is isolated in dedicated research scripts, docs, and branches.

---

## Why the research map needs to expand

Recent equity research clarified an important point:

- Broad equity ETFs can be useful capital destinations.
- They do not automatically become useful alpha sleeves.
- Static equity allocation can reduce risk modestly, but may not materially improve Fund v1.
- SPY SMA did not justify promotion as a standalone alpha strategy.
- QQQ SMA showed useful timing behavior, but static allocation mostly diluted crypto exposure rather than creating a distinct return stream.
- Cash proved to be a strong defensive benchmark during crypto risk-off states.

The implication is that the next stage of Itera research should be organized by **portfolio role**, not by ticker.

Instead of asking:

```text
Can we make SPY or QQQ into a strategy?
```

Itera should ask:

```text
What role does this asset, signal, or sleeve play in the fund?
```

---

## Research role taxonomy

Every new candidate should declare one primary role before testing.

### 1. Alpha sleeve

Purpose:

- generate independent positive expectancy
- stand on its own after costs
- improve the total portfolio when blended

Examples:

- crypto trend module
- cross-sectional factor signal
- relative value strategy
- event/catalyst strategy

Required evidence:

- standalone performance
- cost-adjusted performance
- drawdown behavior
- correlation to existing sleeves
- portfolio impact versus Fund v1

---

### 2. Defensive governor

Purpose:

- reduce exposure when portfolio or market state becomes hostile
- improve drawdown, Calmar, or stress-period behavior
- preserve the existing alpha engine rather than replace it

Examples:

- drawdown-triggered exposure scaling
- volatility-based exposure cap
- regime-based capital throttle

Required evidence:

- lower MaxDD
- improved or stable Calmar
- stable Sharpe
- acceptable CAGR trade-off
- low churn
- interpretable trigger/release behavior

---

### 3. Capital destination

Purpose:

- receive capital when the primary alpha sleeve is reduced
- compete against cash during risk-off windows
- provide either defense, carry, diversification, or upside preservation

Examples:

- cash / T-bill proxy
- SPY
- GLD
- IEF / TLT / SHY
- UUP
- commodities basket
- low-volatility equity ETF

Required evidence:

- return during risk-off windows
- impact on Fund v1 drawdown
- impact on Calmar and Sharpe
- correlation to Fund v1
- behavior during stress years such as 2022

---

### 4. Allocator modifier

Purpose:

- change capital weights across existing sleeves or destinations
- improve the use of available capital without creating a new alpha source

Examples:

- dynamic crypto/equity/cash weights
- risk-budgeted sleeve allocation
- volatility-targeted allocation
- drawdown-aware capital routing

Required evidence:

- better portfolio-level metrics than equal-weight or static allocation
- stable behavior across regimes
- no excessive turnover
- no hidden lookahead

---

### 5. Research intelligence layer

Purpose:

- generate hypotheses, classify regimes, or propose candidate universes
- support research direction
- never directly execute trades

Examples:

- macro research memos
- instrument universe selection
- factor taxonomy
- analyst-style research checklists
- live-vs-backtest degradation monitoring

Required evidence:

- improves research quality or coverage
- does not alter runtime behavior
- remains advisory unless translated into deterministic code

---

## Emerging pod structure

Itera should gradually organize research into pods. A pod is a research domain with a distinct mandate, not necessarily a production allocation.

### Core Crypto Pod

Current status:

- active baseline
- Fund v1 core

Mandate:

- systematic BTC/ETH participation
- trend/regime-aware crypto exposure
- execution-cost-aware portfolio construction

Current components:

- BTC_1H
- BTC_4H
- ETH_1H
- ETH_4H

---

### Defensive Governance Pod

Current status:

- active research direction

Mandate:

- protect Fund v1 during hostile states
- reduce drawdowns without destroying the return engine
- provide interpretable Layer 3 controls

Candidate mechanisms:

- drawdown trigger and release bands
- trend confirmation
- volatility confirmation
- exposure scaling
- trading halt / observation states

---

### Capital Destination Pod

Current status:

- next priority

Mandate:

- determine where reduced crypto capital should go
- benchmark every destination against cash
- evaluate destinations during the exact windows when crypto exposure is reduced

Candidate destinations:

- cash
- SPY
- QQQ, if tradeable
- GLD
- IEF
- TLT
- SHY / BIL / SGOV
- UUP
- PDBC / broad commodities
- low-volatility equities

Key question:

```text
When crypto risk is unfavorable, what destination earns the right to receive capital?
```

---

### Cross-Asset Macro Pod

Current status:

- future research direction

Mandate:

- evaluate broad macro return drivers
- test rates, dollar, gold, commodities, and equity-beta destinations
- determine whether macro state improves capital routing

Candidate signals:

- inflation / rates regime
- dollar strength
- equity volatility
- gold trend
- bond trend
- commodity momentum

---

### Equity / Factor Pod

Current status:

- exploratory

Mandate:

- test whether equity factor exposures add anything beyond broad beta
- avoid assuming broad ETFs are alpha sleeves

Candidate instruments:

- momentum ETF
- quality ETF
- low-volatility ETF
- value ETF
- sector ETFs
- equal-weight equities

Key standard:

A factor sleeve must improve the portfolio after costs. It is not enough to make money in isolation.

---

## Research standards

All new research should follow these rules.

### Declare the role first

Before coding, every experiment must state:

```text
Role: alpha sleeve / defensive governor / capital destination / allocator modifier / research intelligence
```

Ambiguous role means the research is not ready.

---

### Use the correct baseline

Examples:

- standalone strategy: compare to same-asset buy-and-hold or cash
- destination test: compare to cash during the same risk-off windows
- portfolio blend: compare to Fund v1 baseline
- governor: compare to ungoverned Fund v1

Do not mix baselines without saying so explicitly.

---

### Treat cash as a benchmark, not a failure

Cash is not the final objective. Cash is the control group.

If a destination cannot beat cash during risk-off windows, it has not earned a role.

---

### Separate signal quality from deployability

A signal can be useful research but not deployable.

Examples:

- a QQQ signal may be informative even if QQQ cannot currently be traded
- an asset may be a good destination but not available through the target broker
- a strategy may look good as a composite book but fail real-world execution mapping

Deployability must be checked separately from research merit.

---

### Avoid ticker-first research

Do not start with:

```text
Find a SPY strategy.
```

Start with:

```text
What portfolio problem are we solving?
```

Then identify which instruments are eligible candidates for that role.

---

## Near-term roadmap

### Step 1 — Preserve current branch as research checkpoint

Current branch:

```text
cleanup/restart-from-qqq-v1
```

Status:

- full test suite passed
- LLM skill docs added
- SPY/QQQ composite decomposed into tradeable single-asset research sleeves
- standalone equity sleeve runner added
- Fund v1 + QQQ static blend runner added
- SPY risk-off destination runner added

---

### Step 2 — Document current findings

Create research notes for:

- equity SMA decomposition findings
- static QQQ blend findings
- SPY risk-off destination findings

These should clearly classify:

- proceed
- iterate
- archive

---

### Step 3 — Build destination matrix runner

Next major research script:

```text
scripts/run_risk_off_destination_matrix.py
```

Purpose:

- test multiple destinations during Fund v1 risk-off states
- compare every destination to cash
- rank by MaxDD, Calmar, Sharpe, 2022 behavior, and correlation

Initial destinations:

- cash
- SPY
- GLD
- IEF
- TLT
- SHY / BIL / SGOV, depending on available data
- UUP
- PDBC, if available

---

### Step 4 — Decide whether a destination deserves allocator research

Only after the matrix test should Itera consider dynamic routing logic.

A destination must first prove that it beats cash or improves a specific portfolio objective.

---

## Explicit non-goals

The next phase should not:

- introduce LLM-generated live trade decisions
- merge discretionary agent architecture into runtime
- weaken deterministic backtest standards
- bypass execution costs
- promote unavailable instruments
- treat broad equity beta as alpha without proof
- change Fund v1 paper-trading behavior

---

## Summary

Itera is evolving from a crypto strategy stack into a broader systematic fund architecture.

The immediate growth path is not to add random equity strategies. The immediate growth path is to formalize the research map:

```text
Core crypto alpha
+ defensive governance
+ capital destination research
+ cross-asset macro context
+ factor research where justified
```

The next practical milestone is a cross-asset risk-off destination matrix.

That is the clean bridge from the current Fund v1 system toward a more complete systematic fund architecture.