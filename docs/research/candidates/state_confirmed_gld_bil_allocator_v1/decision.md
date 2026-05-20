# State-Confirmed GLD/BIL Allocator — Decision Memo

## Candidate

```text
State-confirmed GLD/BIL defensive destination allocator
```

## Updated Decision

```text
PARTIAL PASS — WATCHLISTED DEFENSIVE OVERLAY
NOT APPROVED FOR LIVE RUNTIME
NOT APPROVED FOR BROKER INTEGRATION
NOT APPROVED FOR ADAPTIVE OPTIMIZATION
NOT APPROVED FOR AGENTIC OVERRIDES
```

## Status

```text
FIXED-RULE DEFENSIVE OVERLAY CANDIDATE
```

The candidate has useful defensive-overlay evidence, especially for drawdown reduction. However, rolling out-of-sample validation was mixed, so it should not be promoted as a production runtime feature or adaptive allocator.

---

## Recommended Reference Profile

```text
50% GLD / 50% BIL
```

Rationale:

- strongest fixed-rule defensive profile in the current research set
- improves drawdown materially versus baseline in chronological subperiods
- improves Calmar in all fixed-rule chronological subperiods
- simpler and more defensible than rolling parameter optimization
- reduces reliance on one destination asset

Representative full-sample research result:

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

- higher CAGR than 50/50 in the original blend review
- higher episode delta than 50/50
- slightly lower Calmar and higher drawdown than 50/50
- useful as a comparison profile if this candidate is revisited

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

## Evidence Summary

The candidate family passed several historical research checks:

```text
state-confirmed sweep
candidate diagnostic
BIL comparison
transition-cost review
GLD/BIL blend review
concentration review
blend robustness sweep
architecture / deployability memo
paper replay prototype
research-vs-paper reconciliation
```

The candidate then received a more conservative walk-forward review.

---

## Walk-Forward Review

Reference:

```text
docs/research/candidates/state_confirmed_gld_bil_allocator_v1/walk_forward_review.md
```

### Fixed-Rule Chronological Validation

The fixed 50/50 GLD/BIL rule improved Calmar and drawdown in all tested chronological subperiods.

```text
Fixed-rule Calmar win rate: 100.0%
Fixed-rule drawdown improvement: 100.0%
```

Interpretation:

```text
The fixed rule is useful as a defensive overlay and is not obviously dependent on one full-sample period.
```

### Rolling Walk-Forward Parameter Selection

Rolling out-of-sample validation was mixed.

```text
Rolling OOS Calmar win rate: 50.0%
Rolling OOS drawdown improvement rate: 75.0%
```

Interpretation:

```text
The allocator appears more reliable as a fixed-rule drawdown-control mechanism than as a rolling-optimized return enhancer.
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
adaptive optimizer
```

Reason:

The candidate does not produce independent alpha from GLD/BIL. It redirects a governed capital budget when Fund v1 is in a crypto-hostile state.

---

## Current Interpretation

The candidate is best understood as:

```text
portfolio insurance / capital-preservation overlay
```

Not as:

```text
new alpha sleeve
adaptive asset allocator
production-ready runtime governor
```

The research evidence supports retaining it as a watchlisted defensive overlay candidate. It does not support immediate runtime promotion.

---

## Implementation Boundary

Allowed future work:

```text
paper-only monitoring
additional validation if needed
comparison against future defensive candidates
manual review if live multi-asset infrastructure becomes available
```

Not allowed from this decision:

```text
live broker changes
runtime execution changes
production governor changes
automated agent overrides
adaptive optimization
capital allocation changes without human approval
```

---

## Final Decision

```text
RETAIN AS WATCHLISTED DEFENSIVE OVERLAY
STOP ACTIVE PARAMETER TUNING
DO NOT PROMOTE TO LIVE RUNTIME
PIVOT TO RETURN-ENGINE RESEARCH
```

Recommended next research target:

```text
BTC/ETH relative-strength allocator
```

Reason:

```text
GLD/BIL answered a defensive capital-preservation question. Itera now needs return-engine research that stays inside the core crypto universe and tests whether dynamic BTC/ETH selection can create timing/selection alpha beyond static exposure.
```