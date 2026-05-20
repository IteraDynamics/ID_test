# State-Confirmed GLD/BIL Allocator — Decision Memo

## Candidate

```text
State-confirmed GLD/BIL defensive destination allocator
```

## Decision

```text
PROCEED TO PAPER-DESIGN PHASE
NOT APPROVED FOR LIVE RUNTIME
NOT APPROVED FOR BROKER INTEGRATION
NOT APPROVED FOR AGENTIC OVERRIDES
```

## Status

```text
VALIDATED RESEARCH CANDIDATE
```

The candidate has sufficient research evidence to justify paper-design and architecture work, but it is not production-ready and must not be wired into live execution.

---

## Recommended Default Profile

```text
50% GLD / 50% BIL
```

Rationale:

- best risk-adjusted profile in the current research set
- strongest Calmar among the tested blend candidates
- materially lower drawdown than GLD-only
- maintains the same episode win rate as GLD-only in the current diagnostic
- reduces reliance on one destination asset

Representative result:

```text
Trigger: -18%
Release: -12%
BTC SMA: 200
Destination: 50% GLD / 50% BIL
Crypto scale: 0%
Friction: 10 bps per changed notional

CAGR:    37.73%
MaxDD:  -22.80%
Sharpe:  1.233
Calmar:  1.655
Stress: +1.28%
Episode win rate: 71.43%
Episode sum delta: +18.37 percentage points
```

---

## Return-Preserving Alternative

```text
75% GLD / 25% BIL
```

Rationale:

- higher CAGR than 50/50
- higher episode delta than 50/50
- slightly lower Calmar and higher drawdown than 50/50
- useful if Itera chooses a more return-preserving defensive destination

Representative result:

```text
Trigger: -18%
Release: -12%
BTC SMA: 200
Destination: 75% GLD / 25% BIL
Crypto scale: 0%
Friction: 10 bps per changed notional

CAGR:    39.87%
MaxDD:  -24.36%
Sharpe:  1.274
Calmar:  1.637
Stress: +1.05%
Episode win rate: 71.43%
Episode sum delta: +29.36 percentage points
```

---

## Higher-Return Alternative

```text
GLD-only
```

Rationale:

- highest CAGR among the current defensive destination candidates
- highest episode sum delta
- more destination-specific risk than blended GLD/BIL
- lower Calmar than the 50/50 blend after blend review

Representative cost-adjusted result:

```text
CAGR:    41.98%
MaxDD:  -26.56%
Sharpe:  1.309
Calmar:  1.581
```

---

## Conservative Benchmark

```text
BIL-only
```

Rationale:

- useful conservative fallback / cash-like benchmark
- protects in major stress episodes
- underperforms when crypto rebounds while risk-off remains active
- weaker episode attribution than GLD or GLD/BIL blends

Representative result:

```text
CAGR:    34.04%
MaxDD:  -25.91%
Sharpe:  1.149
Calmar:  1.313
Stress: +1.42%
Episode win rate: 42.86%
Episode sum delta: -3.96 percentage points
```

---

## Evidence Summary

The candidate family passed the current research sequence:

```text
state-confirmed sweep
candidate diagnostic
BIL comparison
transition-cost review
GLD/BIL blend review
concentration review
blend robustness sweep
architecture / deployability memo
```

### Robustness Sweep Read

The robustness sweep tested 81 nearby combinations across:

```text
trigger_dds: -18%, -20%, -22%
release_dds: -8%, -10%, -12%
BTC SMA windows: 180, 200, 220
GLD/BIL weights: 75/25, 50/50, 25/75
```

The top cluster centered around:

```text
Trigger: -18%
BTC SMA: 200
Release: -8% to -12%
Blend: 50/50 and 75/25 GLD/BIL
RiskOff: approximately 29.6%
```

Interpretation:

```text
The result does not appear to be a one-row accident.
The strongest rows form a coherent nearby cluster.
```

### Concentration Review Read

The candidate remained strong after excluding major contribution windows.

Excluding both 2022 and late-2025:

```text
Baseline Calmar:      1.007
GLD-only Calmar:      1.837
50/50 blend Calmar:   1.720
```

Interpretation:

```text
The 50/50 blend does not appear to be dependent only on 2022 or late-2025.
```

---

## Architecture Decision

The candidate should be classified as:

```text
Layer 3 portfolio-level defensive destination overlay
```

It should not be classified as:

```text
Layer 1 regime engine
Layer 2 alpha strategy
standalone discretionary macro trade
agent-operated trading system
live broker directive
```

Reason:

The candidate does not produce alpha from GLD/BIL independently. It redirects a governed capital budget when Fund v1 is in a crypto-hostile state.

---

## Open Blocking Questions Before Implementation

### Governed Capital Budget

The largest unresolved design question is:

```text
Does crypto_scale = 0% mean full liquidation of all crypto sleeves,
or only rerouting a defined governed defensive-overlay allocation budget?
```

Decision in architecture memo:

```text
Use a defined governed allocation budget.
Do not implicitly liquidate all runtime crypto positions.
```

This must be enforced in design before implementation.

### Cross-Asset Rails

The candidate crosses:

```text
crypto exposure
ETF exposure
```

Open questions:

- Can the intended account/broker structure hold both crypto and ETFs?
- If not, is this paper-only until multi-asset execution exists?
- How are ETF market hours handled against 24/7 crypto markets?
- What is the next available execution window after state transition?
- Can capital move between crypto and ETF rails without manual transfer?

### Paper Trading

Before runtime integration, a paper model must represent:

```text
multi-asset positions
cash
crypto exposure
GLD exposure
BIL exposure
state changes
transition costs
weekend / holiday behavior
allocation intents
simulated fills
```

---

## Promotion Gates

### Already Passed

```text
candidate diagnostic
BIL comparison
transition/cost first pass
blend review
concentration review
robustness sweep
architecture memo
```

### Still Required

```text
paper-design memo
state-machine unit tests
historical replay harness
paper-trading representation
runtime logging design
manual review before live branch
```

### Optional Future Research

```text
UUP dollar confirmation filter
higher-friction sensitivity
chronological subperiod / walk-forward style validation
defensive sector comparison
crypto scale sensitivity
```

---

## Implementation Boundary

Allowed next work:

```text
paper-design documentation
state-machine design
replay harness design
paper-only allocator prototype on a separate branch
```

Not allowed from this decision:

```text
live broker changes
runtime execution changes
production governor changes
automated agent overrides
capital allocation changes without human approval
```

---

## Final Decision

```text
PROCEED TO PAPER-DESIGN PHASE
```

The 50/50 GLD/BIL allocator is the current risk-adjusted defensive destination candidate.

The 75/25 GLD/BIL allocator is retained as the higher-return sibling.

No live runtime promotion is approved.

Next recommended work:

```text
Create a paper-design specification for a DefensiveDestinationAllocator.
```
