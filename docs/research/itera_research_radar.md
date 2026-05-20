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
The robust candidate family is a state-confirmed GLD/BIL risk-off allocator.
50% GLD / 50% BIL is the current risk-adjusted leader.
75% GLD / 25% BIL is the higher-return sibling inside the same robust cluster.
GLD-only remains the highest-return but more destination-specific alternative.
BIL-only remains a conservative benchmark / fallback.
```

---

## Active Validated Candidates

### 1. State-Confirmed 50/50 GLD/BIL Risk-Off Allocator

Status:

```text
VALIDATED CANDIDATE — current risk-adjusted leader; concentration and robustness reviews passed; deployability review remains open before promotion consideration.
```

Portfolio role:

```text
Layer 3 defensive capital destination / blended cross-asset allocator.
```

Current candidate rule:

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

Cost-adjusted evidence at 10 bps per changed notional:

```text
CAGR:    37.73%
MaxDD:  -22.80%
Sharpe:  1.233
Calmar:  1.655
Stress: +1.28%
Episode win rate: 71.43%
Episode sum delta: +18.37 percentage points
```

Robustness evidence:

```text
Top row in robustness sweep:
  Trigger: -18%
  Release: -12%
  BTC SMA: 200
  GLD weight: 50%
  CAGR: 37.73%
  MaxDD: -22.80%
  Sharpe: 1.233
  Calmar: 1.655
  Stress: +1.28%
  RiskOff: 29.6%
  Episode win rate: 71.43%
  Episode sum delta: +18.37 percentage points
```

Interpretation:

The 50/50 GLD/BIL blend is the current best risk-adjusted candidate. It gives up return versus GLD-only and 75/25 GLD/BIL, but materially improves drawdown and Calmar. The robustness sweep confirmed this was not an isolated one-row result: nearby 50/50 and 75/25 combinations around the -18% trigger and SMA200 confirmation also passed guardrails.

Known cautions:

- Lower CAGR than GLD-only and 75/25 GLD/BIL.
- Still requires deployability review for cross-asset capital movement.
- Needs a design decision on whether runtime should use 50/50 as default or expose the blend as a configurable defensive destination.

Next status target:

```text
NEEDS DEPLOYABILITY REVIEW — research candidate is now strong enough to require architecture review before any runtime work.
```

---

### 2. State-Confirmed 75/25 GLD/BIL Risk-Off Allocator

Status:

```text
VALIDATED CANDIDATE — higher-return sibling of the 50/50 blend; not current risk-adjusted leader.
```

Portfolio role:

```text
Layer 3 defensive capital destination / return-preserving blended allocator.
```

Representative robustness result:

```text
Trigger: -18%
Release: -12%
BTC SMA: 200
Destination: 75% GLD / 25% BIL
CAGR: 39.87%
MaxDD: -24.36%
Sharpe: 1.274
Calmar: 1.637
Stress: +1.05%
RiskOff: 29.6%
Episode win rate: 71.43%
Episode sum delta: +29.36 percentage points
```

Interpretation:

The 75/25 GLD/BIL blend offers more return and more episode upside than 50/50 while keeping risk-adjusted metrics strong. It is a serious alternative if Itera chooses a more return-preserving risk-off destination.

---

### 3. State-Confirmed GLD Risk-Off Allocator

Status:

```text
VALIDATED CANDIDATE — highest-return non-crypto allocator candidate; not current risk-adjusted leader after blend and robustness review.
```

Portfolio role:

```text
Layer 3 defensive capital destination / cross-asset allocator.
```

Pre-cost evidence:

```text
CAGR:    42.68%
MaxDD:  -26.48%
Sharpe:  1.325
Calmar:  1.612
Stress: +0.78%
RiskOff: 29.6%
```

Cost-adjusted evidence at 10 bps per changed notional:

```text
Cost-adjusted CAGR:   41.98%
Cost-adjusted MaxDD: -26.56%
Cost-adjusted Sharpe: 1.309
Cost-adjusted Calmar: 1.581
Estimated cost:       $23,153.31
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

GLD-only remains the highest-return candidate and the strongest productive diversifier. However, the 50/50 GLD/BIL blend has better cost-adjusted Calmar and materially lower drawdown.

---

### 4. State-Confirmed BIL Risk-Off Allocator

Status:

```text
VALIDATED BENCHMARK — useful conservative fallback, not primary candidate.
```

Portfolio role:

```text
Cash-like defensive capital destination.
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

BIL provides cleaner drawdown reduction and strong stress protection, but gives up substantial upside during recovery episodes. It is useful as the cash-like benchmark and conservative fallback, but the episode attribution does not justify choosing it over GLD or the GLD/BIL blend as the primary destination candidate.

---

## Current GLD / BIL / Blend Read

```text
50/50 GLD/BIL:
  Best cost-adjusted Calmar.
  Lowest drawdown among the top candidates.
  Maintains 71.43% episode win rate.
  Current risk-adjusted leader.

75/25 GLD/BIL:
  Higher CAGR and episode delta than 50/50.
  Slightly lower Calmar and higher drawdown than 50/50.
  Strong return-preserving alternative.

GLD-only:
  Highest CAGR and strongest episode sum delta.
  Better productive diversifier.
  More destination-specific risk.

BIL-only:
  Conservative benchmark / fallback.
  Lower return and weak episode attribution.
```

Decision:

```text
Proceed with 50/50 GLD/BIL as the current risk-adjusted candidate.
Keep 75/25 GLD/BIL as a serious return-preserving alternative.
Keep GLD-only as the higher-return alternative.
Keep BIL-only as benchmark / fallback.
```

---

## Validation Queue

### 1. Deployability Review

Purpose:

Confirm that the candidate can be mapped cleanly into intended runtime/broker constraints if eventually promoted.

Needed checks:

- whether GLD and BIL are available in the intended brokerage/runtime path
- whether crypto scale 0% means full sleeve exit or partial fund-level state shift
- whether capital can move between crypto and ETF rails in the actual operating structure
- whether paper trading and live infrastructure can represent the cross-asset state change
- whether this should be modeled as a destination allocator, defensive sleeve, or portfolio-level overlay

Priority:

```text
Highest
```

---

### 2. Candidate Architecture Memo

Purpose:

Turn the validated research candidate into a design proposal before touching runtime code.

Needed decisions:

- Is the allocator a Layer 3 defensive governor or a separate cross-asset sleeve?
- What is the promoted default destination: 50/50, 75/25, or configurable GLD/BIL blend?
- What exact state variables are allowed in runtime?
- What artifacts/logs must be produced for auditability?
- What paper-trading simulation must exist before live integration?

Priority:

```text
High
```

---

### 3. Optional UUP Dollar Filter

Purpose:

Test whether an additional dollar-strength confirmation improves false-positive behavior.

Question:

```text
Does adding UUP above SMA200 improve the GLD/BIL allocator, or does it overfilter and reduce the useful defensive response?
```

Priority:

```text
Medium-high, but after deployability/architecture memo.
```

---

### 4. Defensive Sector Matrix

Purpose:

Test whether defensive sectors provide a better or worse defensive destination than GLD/BIL.

Priority:

```text
Medium
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

A strong dollar may confirm crypto-hostile regimes and reduce false positives in the GLD/BIL allocator.

First test:

```text
Add UUP above SMA200 as an additional confirmation condition.
Compare GLD/BIL allocator with and without UUP filter.
```

Priority:

```text
Medium-high after deployability/architecture review.
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
Benchmark against BIL and GLD/BIL blend.
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
Risk-off destination matrix using USMV, SPLV, XLU, XLP, XLV versus GLD/BIL, GLD, BIL, and cash.
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
Compare defensive sectors against GLD/BIL, GLD, and BIL during state-confirmed risk-off windows.
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

#### Crypto Scale Sensitivity

Role:

```text
Risk-off allocation sizing.
```

Hypothesis:

Full crypto exit during risk-off may be too aggressive; partial exposure may reduce false-positive opportunity cost.

Current evidence:

Top GLD and GLD/BIL candidates favored crypto scale 0%, but 25% variants remain interesting.

First test:

```text
Candidate diagnostic comparison for crypto_scale 0%, 25%, and 50% using 50/50 GLD/BIL destination.
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
10 bps transition cost assumption did not invalidate the GLD-only candidate.
The GLD/BIL blend and robustness reviews included the same 10 bps transition-cost assumption.
50/50 GLD/BIL remained the best Calmar result after costs.
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

Simple broad-equity destination logic did not beat cash, BIL, GLD, or the GLD/BIL blend for the specific role of crypto risk-off parking.

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

### 1. Deployability Review

Reason:

The candidate is now strong enough that the next blocker is not another backtest; it is whether the capital movement can be represented safely and realistically in Itera architecture.

Command target:

```text
design memo before any runtime changes
```

---

### 2. Candidate Architecture Memo

Reason:

Need to decide whether this belongs as a Layer 3 defensive governor, separate cross-asset sleeve, or portfolio overlay before implementation.

Command target:

```text
docs/research/candidates/state_confirmed_gld_bil_allocator_v1/architecture_memo.md
```

---

### 3. Optional UUP Dollar Filter

Reason:

May improve macro confirmation and reduce false positives, but could also overfilter.

Command target:

```text
state-confirmed sweep with additional UUP condition
```

---

### 4. Defensive Sector Matrix

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
Write deployability / architecture memo for state-confirmed GLD/BIL allocator before any runtime changes.
```

The next structural build remains:

```text
Use artifacts/research_radar/context_pack.md as the seed for future radar updates.
```

---

## Notes

This radar should be updated after each meaningful research result.

It should eventually be generated by an agentic research-radar cycle, but the output must remain a research memo and queue, not a trading signal.