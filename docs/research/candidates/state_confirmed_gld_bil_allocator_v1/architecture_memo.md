# State-Confirmed GLD/BIL Allocator — Architecture / Deployability Memo

## Purpose

This memo translates the validated state-confirmed GLD/BIL research candidate into an architecture decision record before any runtime or broker integration work.

The candidate has passed the current research validation sequence:

```text
state-confirmed sweep
candidate diagnostic
BIL comparison
transition-cost review
GLD/BIL blend review
concentration review
blend robustness sweep
```

This memo does not promote the candidate to live trading.

It defines what the candidate is, where it belongs in Itera architecture, what must be true before implementation, and what should explicitly not happen.

---

## Candidate Summary

### Current Risk-Adjusted Leader

```text
State-confirmed 50% GLD / 50% BIL risk-off allocator
```

Rule:

```text
Risk-off when:
  Fund v1 prior-day drawdown <= -18%
  AND BTC prior-day close < BTC SMA200

Release when:
  Fund v1 drawdown recovers to >= -12%
  OR BTC recovers above SMA200

Destination during risk-off:
  50% GLD / 50% BIL

Crypto scale during risk-off:
  0%
```

Representative cost-adjusted result at 10 bps per changed notional:

```text
CAGR:    37.73%
MaxDD:  -22.80%
Sharpe:  1.233
Calmar:  1.655
Stress: +1.28%
Episode win rate: 71.43%
Episode sum delta: +18.37 percentage points
```

### Return-Preserving Alternative

```text
State-confirmed 75% GLD / 25% BIL risk-off allocator
```

Representative result:

```text
CAGR:    39.87%
MaxDD:  -24.36%
Sharpe:  1.274
Calmar:  1.637
Stress: +1.05%
Episode win rate: 71.43%
Episode sum delta: +29.36 percentage points
```

### Higher-Return Alternative

```text
State-confirmed GLD-only risk-off allocator
```

Representative cost-adjusted result:

```text
CAGR:    41.98%
MaxDD:  -26.56%
Sharpe:  1.309
Calmar:  1.581
```

---

## Architecture Classification

This candidate should be treated as a:

```text
Layer 3 portfolio-level defensive destination overlay
```

It should not be treated as:

```text
Layer 1 regime engine
Layer 2 alpha strategy
standalone discretionary macro trade
independent PM agent
live broker directive
```

### Why Layer 3

The candidate does not generate alpha from GLD/BIL in isolation.

It changes where capital goes when Fund v1 is already in a crypto-hostile state.

The candidate depends on:

```text
portfolio drawdown state
BTC trend confirmation
capital destination selection
risk-off release behavior
```

That makes it a capital allocation / governance overlay, not a primary alpha module.

---

## Proposed Runtime Concept

If promoted later, the candidate should be represented as a deterministic destination allocator with an explicit state machine.

### Inputs

Allowed runtime inputs:

```text
Fund v1 equity curve / NAV
Fund v1 current drawdown
BTC daily close or prior confirmed close
BTC SMA window value
configured trigger threshold
configured release threshold
configured destination weights
current allocator state
```

Disallowed runtime inputs:

```text
LLM commentary
news headlines
subjective macro interpretation
agent-generated trade ideas
intraday discretionary overrides
unvalidated current-market opinions
```

### State Machine

States:

```text
NORMAL
RISK_OFF_DESTINATION
```

Transition to `RISK_OFF_DESTINATION` when:

```text
prior confirmed Fund v1 drawdown <= trigger_dd
AND prior confirmed BTC close < BTC SMA window
```

Transition back to `NORMAL` when:

```text
prior confirmed Fund v1 drawdown >= release_dd
OR prior confirmed BTC close >= BTC SMA window
```

Default candidate settings:

```text
trigger_dd: -18%
release_dd: -12%
btc_sma_window: 200
release_mode: either
destination_weights:
  GLD: 50%
  BIL: 50%
crypto_scale: 0%
```

Alternative profile:

```text
destination_weights:
  GLD: 75%
  BIL: 25%
```

---

## Key Design Decision

The central unresolved design question is:

```text
Does crypto_scale = 0% mean liquidation of all crypto sleeves, or only rerouting the governed risk budget?
```

This must be answered before runtime implementation.

### Preferred Interpretation

For initial implementation, this should govern a defined portfolio allocation budget rather than imply uncontrolled liquidation of every crypto position.

Preferred design:

```text
The allocator controls a specific defensive-overlay allocation budget.
When RISK_OFF_DESTINATION is active, that governed allocation budget moves from Fund v1 crypto exposure into GLD/BIL destination exposure.
```

Avoid:

```text
Implicitly liquidating all runtime crypto positions without a portfolio-level allocation contract.
```

Reason:

The research overlay was tested at portfolio level. Runtime must define exactly which capital pool is being redirected.

---

## Broker / Account Deployability Concerns

The candidate crosses asset rails:

```text
crypto exposure
ETF exposure
```

This introduces practical issues that do not exist in a crypto-only runtime.

Required deployability questions:

1. Can the intended broker/account structure hold both crypto and ETFs?
2. If not, does capital movement require separate accounts or manual transfer?
3. Can the runtime represent ETF destination exposure even if live execution remains crypto-only for now?
4. Should GLD/BIL initially exist only in paper trading / research simulation?
5. Are ETF orders market-on-close, next-open, or daily-close simulated?
6. What happens when crypto trades 24/7 but ETF markets are closed?
7. How are weekends and market holidays handled?
8. What is the source of truth for daily ETF prices?

Until these are resolved, the candidate should remain:

```text
VALIDATED RESEARCH CANDIDATE — NOT LIVE RUNTIME FEATURE
```

---

## Timing / Market Hours Issue

Crypto trades continuously.

GLD and BIL trade during US equity market hours.

Therefore, runtime implementation cannot naïvely assume that crypto capital can instantly move into ETF exposure at all timestamps.

Recommended initial execution model:

```text
Evaluate allocator state on confirmed daily bars.
Use prior-day confirmed BTC and Fund v1 values.
Generate destination intent for the next available ETF execution window.
Do not allow intraday or weekend ETF fills in research unless explicitly modeled.
```

This means the first deployable version should likely be daily-resolution, not intraday.

---

## Paper Trading Requirement

Before live integration, a paper-trading layer must support:

```text
multi-asset positions
crypto sleeve exposure
ETF destination exposure
cash balance
state transition logs
destination order intents
simulated ETF fills
weekend / holiday handling
cost assumptions
```

Minimum paper-trading event log:

```text
timestamp
previous_state
new_state
fund_drawdown
btc_close
btc_sma
destination_weights
crypto_scale
orders_generated
simulated_fill_prices
estimated_friction
post_transition_allocations
reason
```

No live integration should proceed until the paper ledger can replay the allocator state transitions deterministically.

---

## Logging / Audit Requirements

Every state evaluation should produce an append-only record.

Suggested log:

```text
runtime/argus/state/defensive_destination_state.json
runtime/argus/state/defensive_destination_events.jsonl
```

Or research-only equivalents until runtime design is accepted:

```text
artifacts/state_confirmed_gld_bil_allocator/state_events.jsonl
artifacts/state_confirmed_gld_bil_allocator/allocation_intents.jsonl
```

Each event should include:

```text
timestamp
mode
prior_state
new_state
fund_nav
fund_drawdown
btc_close
btc_sma
trigger_dd
release_dd
release_mode
crypto_scale
gld_weight
bil_weight
reason
cost_model
source_data_cutoff
```

---

## Runtime Boundary

Agents may help generate future research ideas, but agents must not operate this allocator.

Allowed:

```text
agentic research radar proposes tests
agentic research radar writes candidate memos
agentic research radar updates research queue
```

Not allowed:

```text
agent changes destination weights in runtime
agent overrides state machine
agent reacts to headlines with allocation changes
agent sends broker orders
agent edits production governor state
```

---

## Promotion Gates

Before implementation, require:

### Research Gates

```text
concentration review: passed
robustness sweep: passed
transition-cost first pass: passed
```

Still open:

```text
chronological subperiod / walk-forward style validation
optional UUP false-positive filter test
optional higher-friction sensitivity
```

### Architecture Gates

```text
define governed capital budget
resolve crypto/ETF rail issue
define daily execution timing
define paper-trading representation
define logs and audit trail
define rollback / disable switch
```

### Runtime Gates

```text
paper-trading only first
no live broker integration initially
unit tests for state machine
integration tests for allocation intent generation
replay test against historical events
manual review before any live mode
```

---

## Recommended Implementation Sequence

### Step 1 — Research Candidate Memo Completion

Create and maintain:

```text
docs/research/candidates/state_confirmed_gld_bil_allocator_v1/candidate_memo.md
docs/research/candidates/state_confirmed_gld_bil_allocator_v1/concentration_review.md
docs/research/candidates/state_confirmed_gld_bil_allocator_v1/architecture_memo.md
docs/research/candidates/state_confirmed_gld_bil_allocator_v1/decision.md
```

### Step 2 — Paper-Only Design

Add a design document for:

```text
DefensiveDestinationAllocator
```

without implementing runtime code yet.

### Step 3 — State-Machine Unit Tests

Only after design acceptance, implement isolated tests for:

```text
NORMAL -> RISK_OFF_DESTINATION
RISK_OFF_DESTINATION -> NORMAL
no transition when data unavailable
no lookahead behavior
prior-day confirmed input usage
```

### Step 4 — Research Replay Harness

Build a replay script that uses historical data and emits allocation intents without broker integration.

### Step 5 — Paper Trading Integration

Only after replay is deterministic, connect to paper trading.

### Step 6 — Runtime Integration Review

No live integration without explicit human review and separate branch.

---

## Architecture Recommendation

Recommended classification:

```text
Layer 3 Defensive Destination Overlay
```

Recommended default candidate:

```text
50% GLD / 50% BIL
```

Recommended alternative profile:

```text
75% GLD / 25% BIL
```

Recommended implementation stance:

```text
Do not implement live runtime yet.
Proceed to design-only paper allocation model.
```

---

## Current Decision

```text
PROCEED TO PAPER-DESIGN PHASE
DO NOT PROMOTE TO LIVE RUNTIME
DO NOT MODIFY BROKER EXECUTION
DO NOT ALLOW AGENTIC OVERRIDES
```

The candidate is now strong enough to justify architecture work, but not yet ready for implementation inside live trading infrastructure.
