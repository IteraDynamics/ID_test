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

Current answer:

```text
GLD is the primary validated candidate.
BIL is a conservative benchmark / fallback candidate.
Transition friction does not appear to invalidate GLD under the first cost review.
```

---

## Active Validated Candidates

### 1. State-Confirmed GLD Risk-Off Allocator

Status:

```text
VALIDATED CANDIDATE — primary non-crypto allocator candidate; transition/cost review passed under first assumption; still needs concentration review and blend comparison before promotion consideration.
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

Current evidence before transition costs:

```text
CAGR:    42.68%
MaxDD:  -26.48%
Sharpe:  1.325
Calmar:  1.612
Stress: +0.78%
RiskOff: 29.6%
```

Transition/cost review at 10 bps per changed notional:

```text
Transitions:     33
Gross turnover:  $23,153,306.69
Estimated cost:  $23,153.31

Cost-adjusted CAGR:   41.98%
Cost-adjusted MaxDD: -26.56%
Cost-adjusted Sharpe: 1.309
Cost-adjusted Calmar: 1.581
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

GLD is currently the strongest non-crypto candidate found in this branch. It appears to act as a productive diversifier during crypto-hostile regimes, not merely as a cash substitute. The first transition/cost review did not invalidate the candidate: Calmar only moved from 1.612 to 1.581 under a 10 bps friction assumption.

Known cautions:

- Large positive contribution from 2022 and late 2025.
- False positives in periods where crypto recovered while the allocator was defensive.
- Requires GLD/BIL blend comparison before promotion consideration.
- Requires concentration review excluding major contribution windows.
- Requires final deployability review before any runtime integration.

Next status target:

```text
NEEDS RISK REVIEW — episode concentration and false-positive review remain open.
```

---

### 2. State-Confirmed BIL Risk-Off Allocator

Status:

```text
VALIDATED BENCHMARK — useful conservative fallback, not primary candidate.
```

Portfolio role:

```text
Cash-like defensive capital destination.
```

Candidate rule tested:

```text
Risk-off when:
  Fund v1 prior-day drawdown <= -18%
  AND BTC prior-day close < BTC SMA200

Release when:
  Fund v1 drawdown recovers to >= -12%
  OR BTC recovers above SMA200

Destination:
  BIL

Crypto scale during risk-off:
  0%
```

Current evidence:

```text
CAGR:    34.04%
MaxDD:  -25.91%
Sharpe:  1.149
Calmar:  1.313
Stress: +1.42%
RiskOff: 29.6%
```

Episode attribution:

```text
18 total episodes
14 included episodes
4 ignored short/no-return episodes
6 wins
8 losses
Win rate: 42.86%
Sum delta versus Fund v1: -3.96 percentage points
Median delta: -0.11 percentage points
```

Interpretation:

BIL provides cleaner drawdown reduction and strong stress protection, but gives up substantial upside during recovery episodes. It is useful as the cash-like benchmark and conservative fallback, but the episode attribution does not justify choosing it over GLD as the primary destination candidate.

Known cautions:

- BIL protects in major bear/stress episodes.
- BIL underperforms when crypto rebounds while the risk-off state remains active.
- BIL may still be useful in a blended GLD/BIL destination.

---

## Current GLD vs BIL Read

```text
GLD:
  Higher CAGR, higher Sharpe, higher Calmar, positive episode attribution.
  Better productive diversifier.
  Still strong after first transition-cost review.

BIL:
  Lower drawdown, slightly better stress window, weaker episode attribution.
  Better conservative benchmark / cash-like fallback.
```

Decision:

```text
Proceed with GLD as the primary candidate.
Keep BIL as benchmark and blend component.
Do not promote BIL-only over GLD-only at this stage.
```

---

## Validation Queue

### 1. GLD/BIL Blend Test

Purpose:

Test whether a blended destination can keep much of GLD's upside while reducing destination-specific risk.

Candidate blends:

```text
75% GLD / 25% BIL
50% GLD / 50% BIL
25% GLD / 75% BIL
```

Question:

```text
Can a blend preserve GLD's positive episode attribution while improving drawdown/stress behavior?
```

Priority:

```text
Highest
```

---

### 2. GLD Episode Concentration Review

Purpose:

Determine whether the edge is too concentrated in one or two periods.

Needed checks:

- contribution excluding 2022
- contribution excluding late 2025
- contribution excluding both
- median and mean episode delta
- episode-level drawdown improvement
- false positive review

Priority:

```text
High
```

---

### 3. GLD Deployability Review

Purpose:

Confirm that the candidate can be mapped cleanly into intended runtime/broker constraints if eventually promoted.

Needed checks:

- whether GLD is available in the intended brokerage/runtime path
- whether crypto scale 0% means full sleeve exit or partial fund-level state shift
- whether capital can move between crypto and ETF rails in the actual operating structure
- whether paper trading and live infrastructure can represent the cross-asset state change

Priority:

```text
High, but after blend/concentration research.
```

---

### 4. Robustness Around Best Cluster

Purpose:

Confirm that the candidate survives nearby parameters.

Promising cluster:

```text
Trigger: -18% to -20%
Release: -8% to -12%
BTC SMA: 180 / 200 / 220
Destination: GLD
Crypto scale: 0%
RiskOff: approximately 27% to 30%
```

Priority:

```text
Medium-high
```

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
High after GLD/BIL blend and concentration review.
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
Highest
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

Status:

```text
FIRST PASS COMPLETE
```

Result:

```text
10 bps transition cost assumption did not invalidate GLD candidate.
Cost-adjusted Calmar remained 1.581 versus baseline 0.929.
```

Next execution/cost questions:

```text
- Test higher friction assumptions if desired.
- Confirm deployability across crypto and ETF rails.
- Confirm runtime representation of cross-asset capital movement.
```

Priority:

```text
Open only for deployability review, not immediate research blocker.
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

### 1. GLD/BIL Blend Test

Reason:

BIL is not better than GLD as a standalone destination, but it may still be useful as a stabilizing blend component.

Command target:

```text
risk-off overlay with destination blend
```

---

### 2. GLD Episode Concentration Review

Reason:

Need to confirm GLD does not depend too heavily on 2022 and late 2025.

Command target:

```text
candidate diagnostic with exclusion windows / contribution attribution
```

---

### 3. GLD Deployability Review

Reason:

The capital movement is conceptually cross-asset. Before runtime integration, confirm how crypto-to-ETF capital routing can be represented.

Command target:

```text
design memo before any runtime changes
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

The next immediate action is:

```text
Build GLD/BIL blend test.
```

The next structural build remains:

```text
Use artifacts/research_radar/context_pack.md as the seed for future radar updates.
```

---

## Notes

This radar should be updated after each meaningful research result.

It should eventually be generated by an agentic research-radar cycle, but the output must remain a research memo and queue, not a trading signal.