# Runtime Governors

Governors are Layer 3 components that constrain or scale risk after strategy intent is generated and before execution is routed to a broker.

They are not alpha modules. They do not decide whether a strategy has an edge. Their job is to protect capital, enforce operating constraints, and make risk behavior auditable.

## Role in the architecture

```text
Layer 1 Regime Engine
        ↓
Layer 2 StrategyIntent
        ↓
Layer 3 Allocator
        ↓
Layer 3 Governors
        ↓
Broker / Execution
```

Governors must not call brokers directly and must not mutate strategy state.

## Current governor types

### DrawdownGovernor

Tracks portfolio NAV high-water mark and can halt new buy activity when portfolio drawdown breaches a threshold.

Primary role:

- fail-closed protection against portfolio drawdown
- allow exits / sells even when buys are halted

### ExposureGovernor

Constrains target exposure and order admissibility.

Primary role:

- cap exposure
- enforce minimum notionals
- block low-confidence or invalid entries

### DefensiveExposureGovernor

Research-promoted Fund v2 candidate.

Primary role:

- compute a defensive exposure scale from closed-bar BTC/ETH market state
- reduce Fund v1 exposure during high-risk conditions
- never increase risk above the allocator output

Default promoted profile:

- risk index: equal-weight normalized BTC + ETH close index
- trigger: 20% drawdown from 90-day rolling high and below 200-day EMA
- release: drawdown below 12% or recovery above trend
- confirmation: 24 bars
- release confirmation: 48 bars
- exposure scale: 0.75

Status:

- researched
- cost-adjusted
- unit-tested
- not active in the current Fund v1 paper trader

## Design rules

All governors must be:

- deterministic
- closed-bar only
- no-lookahead
- auditable
- low-churn
- fail-closed when uncertain

Governors should emit or expose enough metadata to support dashboard display and operator review.

## Runtime integration rule

New governors must not silently alter Fund v1 paper-trading behavior.

Any governor integration must be either:

1. isolated from the active runtime path, or
2. explicitly feature-gated and disabled by default.

Example:

```text
DEFENSIVE_OVERLAY_ENABLED=0
```

## Testing expectations

A governor should include tests for:

- activation
- release
- no excessive flipping
- state persistence
- monotonic risk behavior, where applicable

The defensive governor is covered by:

```powershell
python -m pytest tests/test_defensive_exposure_governor.py -q
```
