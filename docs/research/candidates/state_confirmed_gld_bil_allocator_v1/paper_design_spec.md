# DefensiveDestinationAllocator — Paper Design Specification

## Purpose

This specification defines a paper-only design for the validated state-confirmed GLD/BIL defensive destination allocator.

It is intentionally a design contract, not an implementation.

The goal is to describe how Itera could represent the allocator safely in a paper/replay environment before any runtime, broker, or live execution integration.

---

## Scope

This design covers:

```text
state machine behavior
required inputs
allowed outputs
allocation intent format
paper fill model
logging / audit trail
test requirements
runtime boundaries
```

This design does not authorize:

```text
live broker changes
runtime execution changes
production governor changes
automatic capital movement
agentic overrides
```

---

## Candidate Being Designed

Default candidate:

```text
State-confirmed 50% GLD / 50% BIL defensive destination allocator
```

Default rule:

```text
Risk-off when:
  Fund v1 prior-day drawdown <= -18%
  AND BTC prior-day close < BTC SMA200

Release when:
  Fund v1 drawdown recovers to >= -12%
  OR BTC prior-day close >= BTC SMA200

Destination during risk-off:
  50% GLD / 50% BIL

Crypto scale during risk-off:
  0%
```

Alternative profile:

```text
75% GLD / 25% BIL
```

---

## Architecture Classification

The allocator is a:

```text
Layer 3 portfolio-level defensive destination overlay
```

It is not a:

```text
Layer 1 regime engine
Layer 2 alpha strategy
single-asset trading strategy
discretionary macro trade
agent-controlled PM
```

Reason:

The allocator does not predict GLD/BIL independently. It redirects a governed capital budget when Fund v1 is in a crypto-hostile state.

---

## Governed Capital Budget

The allocator must operate on an explicit governed capital budget.

Required field:

```text
governed_budget_id
```

Examples:

```text
fund_v1_defensive_overlay_budget
paper_cross_asset_overlay_budget
research_replay_budget
```

The allocator must not imply uncontrolled liquidation of all crypto positions.

Preferred interpretation of `crypto_scale = 0%`:

```text
Within the governed budget only, crypto exposure is reduced to 0% while the risk-off destination state is active.
```

Not allowed:

```text
Implicitly liquidating all runtime BTC/ETH sleeves without an explicit portfolio-level budget contract.
```

---

## State Machine

### States

```text
NORMAL
RISK_OFF_DESTINATION
```

### NORMAL

In `NORMAL`, the governed budget remains allocated to the baseline Fund v1 exposure model.

Target weights:

```text
fund_v1_exposure: 100%
GLD: 0%
BIL: 0%
cash: 0% unless separately modeled
```

### RISK_OFF_DESTINATION

In `RISK_OFF_DESTINATION`, the governed budget is redirected to the defensive destination basket.

Default target weights:

```text
fund_v1_exposure: 0%
GLD: 50%
BIL: 50%
```

Alternative profile:

```text
fund_v1_exposure: 0%
GLD: 75%
BIL: 25%
```

---

## Transition Rules

All transition rules must use confirmed prior-day inputs.

### Enter Risk-Off Destination

Transition:

```text
NORMAL -> RISK_OFF_DESTINATION
```

Condition:

```text
prior_confirmed_fund_drawdown <= trigger_dd
AND prior_confirmed_btc_close < prior_confirmed_btc_sma
```

Default parameters:

```text
trigger_dd: -0.18
btc_sma_window: 200
```

### Exit Risk-Off Destination

Transition:

```text
RISK_OFF_DESTINATION -> NORMAL
```

Condition:

```text
prior_confirmed_fund_drawdown >= release_dd
OR prior_confirmed_btc_close >= prior_confirmed_btc_sma
```

Default parameters:

```text
release_dd: -0.12
release_mode: either
```

### No Transition

No transition occurs when:

```text
inputs are missing
input timestamps are stale
BTC SMA is unavailable
Fund drawdown is unavailable
current state already matches target state
```

Missing data must produce a `NO_ACTION_DATA_UNAVAILABLE` evaluation result, not a guessed state change.

---

## Required Inputs

Each evaluation requires:

```text
evaluation_timestamp
source_data_cutoff
current_state
fund_nav
fund_peak_nav
fund_drawdown
btc_close
btc_sma
trigger_dd
release_dd
release_mode
crypto_scale
destination_weights
governed_budget_nav
```

Optional inputs:

```text
market_calendar
next_etf_execution_timestamp
estimated_friction_bps
prior_allocations
cash_balance
```

---

## Input Timing Rules

The allocator must use prior confirmed daily data.

Required rule:

```text
Evaluation for date D may only use data confirmed through date D-1 unless explicitly running a historical replay where the cutoff is documented.
```

This prevents lookahead behavior.

Crypto trades continuously, but ETF destinations do not. Therefore the paper design should evaluate daily and produce intents for the next available ETF execution window.

---

## Market Hours / Calendar Handling

GLD and BIL are ETF instruments.

They cannot be filled on weekends, holidays, or outside modeled ETF execution windows.

Paper model requirements:

```text
If a state transition occurs on a non-ETF trading day, queue the destination intent for the next ETF trading day.
If crypto exits are modeled immediately but ETF entries are delayed, hold interim cash explicitly.
If both legs are modeled at ETF calendar timing, document the assumption.
```

Recommended first paper assumption:

```text
All cross-asset allocation changes execute at the next available ETF daily close or next-open proxy.
No intraday fills.
No weekend ETF fills.
```

The selected fill convention must be recorded in every replay artifact.

---

## Allocation Intent Output

The allocator should output intents, not broker orders.

Intent schema:

```json
{
  "timestamp": "YYYY-MM-DDTHH:MM:SSZ",
  "mode": "paper",
  "allocator_id": "defensive_destination_allocator_v1",
  "governed_budget_id": "fund_v1_defensive_overlay_budget",
  "prior_state": "NORMAL",
  "new_state": "RISK_OFF_DESTINATION",
  "reason": "drawdown_trigger_and_btc_trend_break",
  "source_data_cutoff": "YYYY-MM-DD",
  "inputs": {
    "fund_nav": 100000.0,
    "fund_peak_nav": 120000.0,
    "fund_drawdown": -0.18,
    "btc_close": 65000.0,
    "btc_sma": 70000.0
  },
  "parameters": {
    "trigger_dd": -0.18,
    "release_dd": -0.12,
    "release_mode": "either",
    "crypto_scale": 0.0,
    "btc_sma_window": 200
  },
  "target_weights": {
    "fund_v1_exposure": 0.0,
    "GLD": 0.5,
    "BIL": 0.5
  },
  "execution_policy": {
    "venue_mode": "paper",
    "fill_timing": "next_etf_daily_close_proxy",
    "allow_weekend_etf_fills": false
  }
}
```

---

## Evaluation Result Types

Every evaluation should return one result type:

```text
NO_ACTION_ALREADY_NORMAL
NO_ACTION_ALREADY_RISK_OFF
NO_ACTION_DATA_UNAVAILABLE
ENTER_RISK_OFF_DESTINATION
EXIT_RISK_OFF_DESTINATION
NO_ACTION_WAITING_FOR_EXECUTION_WINDOW
```

These result types should be logged even when no allocation change occurs.

---

## Paper Fill Model

The first paper version should use a simple deterministic fill model.

Recommended assumptions:

```text
ETF fills use next available daily close or next-open proxy.
Crypto exit/entry timing must match the chosen cross-asset convention.
Friction is applied to changed notional.
Default friction: 10 bps per changed notional.
No partial fill modeling in first version.
No intraday slippage model in first version.
```

Required fill record:

```json
{
  "timestamp": "YYYY-MM-DDTHH:MM:SSZ",
  "intent_id": "uuid-or-deterministic-id",
  "fill_id": "uuid-or-deterministic-id",
  "symbol": "GLD",
  "side": "BUY",
  "target_weight": 0.5,
  "notional": 50000.0,
  "fill_price": 190.25,
  "friction_bps": 10.0,
  "estimated_friction": 50.0,
  "mode": "paper"
}
```

---

## Logs And Artifacts

Research / paper artifacts:

```text
artifacts/defensive_destination_allocator/state_evaluations.jsonl
artifacts/defensive_destination_allocator/allocation_intents.jsonl
artifacts/defensive_destination_allocator/paper_fills.jsonl
artifacts/defensive_destination_allocator/replay_summary.md
artifacts/defensive_destination_allocator/equity_curves.csv
```

Potential runtime-equivalent paths only after future approval:

```text
runtime/argus/state/defensive_destination_state.json
runtime/argus/state/defensive_destination_events.jsonl
```

Do not create runtime paths during paper-design phase unless explicitly approved on a future implementation branch.

---

## Replay Harness Requirements

A replay harness should be able to:

```text
load historical Fund v1 baseline NAV
load BTC daily close
compute BTC SMA without lookahead
load GLD and BIL daily prices
simulate state transitions
emit allocation intents
simulate paper fills
apply friction
produce equity curve
produce transition audit log
reproduce research metrics
```

The replay harness must be deterministic.

Given the same input files and parameters, it must produce the same output artifacts.

---

## Unit Test Requirements

Minimum tests:

```text
NORMAL enters RISK_OFF_DESTINATION when drawdown and BTC trend conditions are both true
NORMAL does not enter when only drawdown condition is true
NORMAL does not enter when only BTC trend condition is true
RISK_OFF_DESTINATION exits when drawdown recovers
RISK_OFF_DESTINATION exits when BTC trend recovers
RISK_OFF_DESTINATION does not exit when neither release condition is true
missing BTC SMA prevents state transition
missing drawdown prevents state transition
prior-day input usage prevents lookahead
state is stable when no transition condition is met
allocation intent weights sum to 1.0 within governed budget
50/50 profile emits correct GLD/BIL weights
75/25 profile emits correct GLD/BIL weights
paper fill model does not fill ETFs on weekends
friction applies only to changed notional
```

---

## Integration Test Requirements

Minimum integration tests:

```text
historical replay emits expected number of state transitions for known sample
historical replay produces deterministic artifacts
allocation intents match state transitions
paper fills only occur after allocation intents
weekend transition queues until next ETF trading day
cost-adjusted equity curve is lower than or equal to pre-cost curve after cost events
no live broker code is imported or invoked
```

---

## Configuration Contract

Candidate config example:

```json
{
  "allocator_id": "defensive_destination_allocator_v1",
  "enabled": false,
  "mode": "paper",
  "governed_budget_id": "fund_v1_defensive_overlay_budget",
  "trigger_dd": -0.18,
  "release_dd": -0.12,
  "release_mode": "either",
  "btc_sma_window": 200,
  "crypto_scale": 0.0,
  "destination_weights": {
    "GLD": 0.5,
    "BIL": 0.5
  },
  "friction_bps": 10.0,
  "fill_timing": "next_etf_daily_close_proxy",
  "allow_weekend_etf_fills": false
}
```

Important defaults:

```text
enabled: false
mode: paper
```

No implementation should default this allocator to live.

---

## Failure Modes To Guard Against

```text
lookahead through same-day BTC or ETF data
implicit liquidation of all crypto sleeves
ETF fills on non-trading days
agent-generated changes to weights or thresholds
runtime code path accidentally imported by research script
paper broker and live broker sharing mutable state
missing data causing false transition
cross-asset capital movement assumed without account support
untracked manual cash movement
cost model omitted from promotion review
```

---

## Human Review Checklist Before Implementation

Before any code implementation, confirm:

```text
The governed budget is explicitly defined.
The allocator is paper-only.
The fill timing convention is selected.
The target destination profile is selected.
The logs/artifacts are accepted.
The test plan is accepted.
The live broker boundary is accepted.
The branch name clearly indicates paper/prototype status.
```

Recommended implementation branch name:

```text
prototype/defensive-destination-paper-replay
```

---

## Current Decision

```text
DESIGN ACCEPTED FOR PAPER-ONLY PROTOTYPE PLANNING
NO LIVE IMPLEMENTATION APPROVED
```

Next recommended step:

```text
Create an isolated paper replay prototype for DefensiveDestinationAllocator on a separate branch.
```

This prototype should emit artifacts only and must not import or invoke live broker code.
