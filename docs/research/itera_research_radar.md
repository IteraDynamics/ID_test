# Itera Research Radar

## Purpose

This memo tracks Itera Dynamics research priorities across crypto, macro, equities, sectors, factors, volatility, portfolio construction, and execution/cost review.

It is a research queue and idea radar.

It is not a trading instruction document.

---

## Current Research Posture

Itera has moved from a crypto-only Fund v1 baseline toward Layer 3 capital destination and defensive allocation research.

Recent work suggests that ticker-first equity research is less useful than role-first portfolio research.

The most important current research question is:

```text
When Fund v1 enters a crypto-hostile state, where should capital go?
```

---

## Active Validated Candidates

### 1. State-Confirmed GLD Risk-Off Allocator

Status:

```text
VALIDATED CANDIDATE — needs additional validation before promotion.
```

Portfolio role:

```text
Layer 3 defensive capital destination / cross-asset allocator.
```

Current candidate rule:

```text
Risk-off when:
  Fund v1 prior-day drawdown <= -18%
  AND BTC prior-day close < BTC SMA200

Release when:
  Fund v1 drawdown recovers to >= -12%
  OR BTC recovers above SMA200

Destination:
  GLD

Crypto scale during risk-off:
  0%
```

Current evidence:

```text
CAGR:    42.68%
MaxDD:  -26.48%
Sharpe:  1.325
Calmar:  1.612
Stress: +0.78%
RiskOff: 29.6%
```

Episode attribution:

```text
18 total episodes
14 included episodes
4 ignored short/no-return episodes
10 wins
4 losses
Win rate: 71.43%
Sum delta versus Fund v1: +40.24 percentage points
Median delta: +1.37 percentage points
```

Interpretation:

GLD is currently the strongest non-crypto candidate found in this branch. It appears to act as a productive diversifier during crypto-hostile regimes, not merely as a cash substitute.

Known cautions:

- Large positive contribution from 2022 and late 2025.
- False positives in periods where crypto recovered while the allocator was defensive.
- Requires capital/cost/deployability review.
- Requires BIL comparison before promotion.
- Requires transition-count and rebalance-friction review.

Next status target:

```text
NEEDS RISK REVIEW + NEEDS CAPITAL REVIEW
```

---

## Validation Queue

### 1. BIL Diagnostic Comparison

Purpose:

Compare GLD against a conservative cash-like destination.

Candidate:

```text
BIL
Trigger / release: -18% / -12%
BTC trend filter: SMA200
Release mode: either
Crypto scale: 0% and 25%
```

Question:

```text
Does BIL provide enough drawdown reduction and stress protection to justify choosing it over GLD, despite lower upside?
```

---

### 2. GLD Capital / Cost Review

Purpose:

Determine whether the GLD allocator remains attractive after practical capital movement assumptions.

Needed checks:

- transition count
- approximate rebalance friction
- capital moved per transition
- whether crypto scale 0% means full sleeve exit or partial fund-level state shift
- GLD deployability in intended brokerage/runtime
- tax/accounting implications if relevant later

---

### 3. GLD Episode Concentration Review

Purpose:

Determine whether the edge is too concentrated in one or two periods.

Needed checks:

- contribution excluding 2022
- contribution excluding late 2025
- contribution excluding both
- median and mean episode delta
- episode-level drawdown improvement
- false positive review

---

### 4. Robustness Around Best Cluster

Purpose:

Confirm that the candidate survives nearby parameters.

Already promising cluster:

```text
Trigger: -18% to -20%
Release: -8% to -12%
BTC SMA: 180 / 200 / 220
Destination: GLD
Crypto scale: 0%
RiskOff: approximately 27% to 30%
```

Next test:

- keep a record of cluster robustness in candidate memo
- avoid over-optimizing to a single top row

---

## Idea Backlog by Research Lane

### Crypto Lane

#### BTC / ETH Relative Strength Allocator

Role:

```text
Crypto allocator modifier.
```

Hypothesis:

Fund v1 may improve if capital rotates dynamically between BTC and ETH based on relative strength instead of static equal-weight sleeve allocation.

First test:

```text
BTC/ETH 30d, 90d, 180d relative momentum.
Compare static equal-weight versus dynamic overweight.
```

Priority:

```text
Medium-high
```

---

#### ETH Sleeve Diagnostic

Role:

```text
Core crypto sleeve review.
```

Hypothesis:

ETH sleeves may contribute differently from BTC across regimes and may require separate parameters or capital weights.

First test:

```text
Decompose Fund v1 contribution by BTC and ETH sleeves across bull, bear, crash, and recovery windows.
```

Priority:

```text
Medium
```

---

### Macro / Cross-Asset Lane

#### UUP Dollar-Strength Crypto Risk Filter

Role:

```text
Defensive governor / regime confirmation.
```

Hypothesis:

A strong dollar may confirm crypto-hostile regimes and reduce false positives in the GLD allocator.

First test:

```text
Add UUP above SMA200 as an additional confirmation condition.
Compare GLD allocator with and without UUP filter.
```

Priority:

```text
High after BIL diagnostic and GLD cost review.
```

---

#### Duration-Filtered Bond Destination

Role:

```text
Conditional capital destination.
```

Hypothesis:

IEF/TLT performed poorly as simple risk-off destinations, but may work only when bond trend is favorable or yields are falling.

First test:

```text
Test IEF/TLT only when ETF is above SMA200 or duration trend is positive.
Benchmark against BIL and GLD.
```

Priority:

```text
Medium
```

---

### Equity / Factor Lane

#### Low-Volatility Defensive Destination Basket

Role:

```text
Defensive equity destination.
```

Hypothesis:

USMV/SPLV and defensive sectors may offer equity-market participation with lower drawdown during crypto-hostile states.

First test:

```text
Risk-off destination matrix using USMV, SPLV, XLU, XLP, XLV versus GLD, BIL, and cash.
```

Priority:

```text
Medium
```

---

#### Factor ETF Destination Matrix

Role:

```text
Cross-asset / equity factor candidate search.
```

Candidate instruments:

```text
MTUM
QUAL
VTV
VUG
RSP
IWM
MDY
```

First test:

```text
Destination matrix during state-confirmed crypto risk-off windows.
```

Priority:

```text
Low-medium
```

---

### Sector Lane

#### Defensive Sector Matrix

Role:

```text
Sector-level defensive destination research.
```

Candidate instruments:

```text
XLU
XLP
XLV
```

First test:

```text
Compare defensive sectors against GLD and BIL during state-confirmed risk-off windows.
```

Priority:

```text
Medium
```

---

#### Growth / AI Infrastructure Risk-On Basket

Role:

```text
Potential risk-on enhancer, not defensive destination.
```

Candidate instruments:

```text
XLK
SMH
IGV
QQQ
QQQE
```

First test:

```text
Only after defensive allocator research stabilizes. Test as risk-on allocation during crypto-friendly regimes, not risk-off parking.
```

Priority:

```text
Low for now
```

---

### Volatility / Risk Lane

#### BTC Realized Volatility Confirmation

Role:

```text
Risk-off confirmation / false-positive reducer.
```

Hypothesis:

Risk-off should require not only drawdown and trend break, but also volatility expansion or realized stress.

First test:

```text
Add BTC realized volatility percentile or volatility z-score to state-confirmed sweep.
```

Priority:

```text
Medium-high
```

---

### Portfolio Construction Lane

#### GLD/BIL Blend During Risk-Off

Role:

```text
Capital destination blend.
```

Hypothesis:

A blend of GLD and BIL may preserve much of GLD's upside while reducing destination-specific risk.

First test:

```text
During state-confirmed risk-off, allocate 50/50 or 75/25 between GLD and BIL.
Compare to GLD-only and BIL-only.
```

Priority:

```text
High after BIL diagnostic.
```

---

#### Crypto Scale Sensitivity

Role:

```text
Risk-off allocation sizing.
```

Hypothesis:

Full crypto exit during risk-off may be too aggressive; partial exposure may reduce false-positive opportunity cost.

Current evidence:

Top GLD candidates favored crypto scale 0%, but 25% variants remain interesting.

First test:

```text
Candidate diagnostic comparison for crypto_scale 0%, 25%, and 50%.
```

Priority:

```text
Medium
```

---

### Execution / Cost Lane

#### Transition Cost and Rebalance Review

Role:

```text
CFO-style capital practicality review.
```

Hypothesis:

The GLD allocator's apparent improvement may be reduced by transition friction and state changes.

First test:

```text
Count transitions, estimate turnover, apply conservative ETF and crypto trading friction to overlay returns.
```

Priority:

```text
High
```

---

## Recently Archived / Deprioritized

### Drawdown-Only Risk-Off Governor

Status:

```text
ARCHIVE
```

Reason:

Drawdown-only trigger/release logic stayed defensive too often and behaved more like a permanent allocation replacement than a tactical governor.

---

### SPY / QQQ As Standalone Risk-Off Destination

Status:

```text
LOW PRIORITY
```

Reason:

Simple broad-equity destination logic did not beat cash, BIL, or GLD for the specific role of crypto risk-off parking.

---

### TLT / IEF As Unfiltered Risk-Off Destination

Status:

```text
LOW PRIORITY unless duration trend filter is added
```

Reason:

Unfiltered duration assets were hurt badly in the 2022 rate shock and performed poorly in the initial destination matrix.

---

## Highest-Value Next Tests

### 1. BIL Candidate Diagnostic

Reason:

Needed to compare GLD against the conservative benchmark.

Command target:

```text
run_state_confirmed_candidate_diagnostic.py with BIL destination
```

---

### 2. GLD Transition / Cost Review

Reason:

Needed before moving from validated candidate to promotion consideration.

Command target:

```text
new or extended diagnostic to count transitions and estimate friction
```

---

### 3. GLD/BIL Blend Test

Reason:

May reduce reliance on GLD while preserving diversification value.

Command target:

```text
risk-off overlay with destination blend
```

---

### 4. UUP Dollar Filter

Reason:

May improve macro confirmation and reduce false positives.

Command target:

```text
state-confirmed sweep with additional UUP condition
```

---

### 5. Defensive Sector Matrix

Reason:

Useful for validating whether sectors provide a better or worse defensive destination than GLD/BIL.

Command target:

```text
state-confirmed destination matrix with XLU, XLP, XLV, USMV, SPLV
```

---

## Current Research Decision

The next immediate action remains:

```text
Run BIL candidate diagnostic when available.
```

The next structural build is:

```text
Generate a research radar context-pack script so future radar updates can be seeded from repo state and artifacts instead of chat memory.
```

---

## Notes

This radar should be updated after each meaningful research result.

It should eventually be generated by an agentic research-radar cycle, but the output must remain a research memo and queue, not a trading signal.