# Sleeve 4 Search — Research Plan

## Status

**Branch:** `research/sleeve-4-search`

**Research status:** open.

**Runtime status:** no Fund v1 runtime changes approved.

This branch starts after closing HMM Regime v1 as a shadow diagnostic / attribution layer. HMM did not materially improve the existing calibrated crypto sleeve as a direct governor, which suggests the current crypto sleeve already captures much of the useful regime structure.

The next open problem is not another regime model. The next open problem is the fourth sleeve role.

## Current Core Candidate

The current portfolio core candidate is the three-sleeve structure:

```text
Crypto Sleeve v1  — primary return engine
SPY Equity v1     — defensive equity stabilizer
QQQ Growth v1b    — growth equity expression / candidate small-allocation component
```

The documented three-sleeve candidate produced respectable portfolio-level behavior. The `60% Crypto / 20% SPY / 20% QQQ` region preserved the crypto-forward thesis while improving risk-adjusted shape versus simpler Crypto/SPY allocation.

However, this structure still feels incomplete because SPY and QQQ are both equity-beta expressions. QQQ improved the portfolio but did not solve the deeper missing-sleeve problem: a truly differentiated fourth return/risk source.

## Why This Branch Exists

The purpose of this branch is to search for Sleeve 4 by role, not by favorite instrument.

The failed/closed research sequence so far:

```text
Vol sleeve search:
- Short-vol had attractive carry properties in a short/favorable window.
- Short-vol carried embedded left-tail risk and failed promotion standards after shock analysis.
- Long-vol via decaying VIX products was rejected in current form.

HMM search:
- HMM was useful as regime explanation and attribution.
- HMM did not materially improve the existing crypto sleeve as a governor.
- HMM is archived as shadow diagnostic, not runtime logic.
```

The fourth sleeve remains unresolved.

## Research Objective

Find or reject a fourth-sleeve role that improves the current core portfolio without adding unacceptable hidden fragility.

The fourth sleeve should ideally provide one or more of the following:

```text
1. Lower drawdown.
2. Higher Sharpe / Calmar.
3. Better stress-window behavior.
4. Lower dependence on crypto/equity risk-on conditions.
5. A plausible real-world implementation path.
```

The fourth sleeve does **not** need to be exciting. It needs to be useful.

## Candidate Sleeve Roles

### A. Defensive Carry / Cash / T-Bill Sleeve

Role:

```text
Capital preservation and dry-powder sleeve.
```

Purpose:

```text
Give the portfolio a low-risk destination rather than forcing all capital into crypto, SPY, QQQ, or fragile carry.
```

Initial proxies:

```text
Cash / zero-return sleeve
SHV / BIL / SGOV-style T-bill proxy
Short-duration Treasury proxy
```

Hypothesis:

```text
A simple defensive carry sleeve may improve MaxDD, volatility, and drawdown behavior even if it reduces CAGR.
```

### B. Duration / Treasury Sleeve

Role:

```text
Macro defensive sleeve / equity stress diversifier.
```

Initial proxies:

```text
IEF
TLT
SHY
```

Caution:

```text
Duration can fail during inflation/rate-shock regimes, especially 2022.
```

### C. Gold / Real Asset Sleeve

Role:

```text
Non-equity macro diversifier.
```

Initial proxy:

```text
GLD
```

Hypothesis:

```text
Gold may provide a different macro exposure than equities and crypto, but may not improve portfolio-level behavior enough to justify inclusion.
```

### D. Managed Futures / Trend Proxy Sleeve

Role:

```text
Crisis-alpha / trend-dislocation sleeve.
```

Initial proxies:

```text
DBMF
KMLM
CTA-style proxy where data availability permits
```

Caution:

```text
ETF history may be short, and proxy selection can dominate results.
```

### E. Capped Short-Vol Carry Sleeve

Role:

```text
High-risk carry sleeve, explicitly capped.
```

Initial proxy:

```text
SVIX / short-vol proxy
```

Constraint:

```text
Maximum research allocation: 5% unless explicit tail-risk justification exists.
```

Important:

```text
This is not a safe diversifier. It is dangerous carry. It must remain shock-tested.
```

### F. Crypto Market-Neutral / Relative-Value Sleeve

Role:

```text
Potentially orthogonal crypto-native alpha.
```

Examples:

```text
BTC/ETH relative strength
Cross-asset spread / pairs behavior
Funding/carry proxy if data exists
Volatility-neutral crypto rotation
```

Caution:

```text
More complex data and execution assumptions. Should not be first unless simpler role tests fail.
```

## Initial Benchmark Portfolio

The default benchmark for Sleeve 4 tests should be the three-sleeve core:

```text
60% Crypto / 20% SPY / 20% QQQ
```

Alternative benchmark for sensitivity:

```text
70% Crypto / 30% SPY
```

The fourth sleeve should be tested against the core, not evaluated only standalone.

## Initial Allocation Tests

First pass should evaluate simple static allocations:

```text
Core baseline:
60% Crypto / 20% SPY / 20% QQQ / 0% Sleeve4

Defensive carry variants:
55% Crypto / 20% SPY / 15% QQQ / 10% Sleeve4
50% Crypto / 20% SPY / 20% QQQ / 10% Sleeve4
50% Crypto / 25% SPY / 15% QQQ / 10% Sleeve4
45% Crypto / 25% SPY / 20% QQQ / 10% Sleeve4

Conservative cap variant:
55% Crypto / 22.5% SPY / 17.5% QQQ / 5% Sleeve4
```

For capped short-vol, do not test above 5% in the first pass unless explicitly requested.

## Required Metrics

Every Sleeve 4 test must report:

```text
Total Return
CAGR
MaxDD
Sharpe
Calmar
Annualized Volatility
Worst rolling 90-day return
Worst rolling 180-day return
Yearly returns
Correlation matrix
Drawdown contribution / sleeve behavior during portfolio drawdowns
```

## Required Stress Windows

Every candidate should be reviewed across:

```text
2020 COVID stress if data exists
2021 crypto/equity risk-on
2022 inflation / rates / crypto crash
2023 recovery
2024-2025 continuation / recent behavior
```

If a proxy does not have enough history, the test must explicitly say so.

## Promotion Criteria

A Sleeve 4 candidate can only remain active if it improves at least one major portfolio objective without unacceptable damage elsewhere.

Preferred evidence:

```text
- improves Calmar versus 60/20/20 core;
- improves MaxDD or worst rolling drawdown;
- does not materially reduce Sharpe;
- does not depend entirely on one short/favorable window;
- does not introduce unbounded or poorly modeled tail risk;
- has a plausible implementation path.
```

## Rejection Criteria

Reject or archive a candidate if:

```text
- standalone result is structurally unacceptable;
- portfolio improvement is tiny and fragile;
- benefit disappears in stress windows;
- it adds hidden convexity/tail risk without adequate compensation;
- it only works because of a short proxy history;
- it is effectively duplicating SPY/QQQ beta.
```

## First Recommended Experiment

Start with the boring benchmark:

```text
Defensive Carry Sleeve v1
```

Reason:

```text
It answers whether the current core needs a capital-preservation sleeve before chasing more complex orthogonal alpha.
```

First implementation should be simple:

```text
1. Create/load a cash or T-bill proxy curve.
2. Blend it with the 60/20/20 core using static allocations.
3. Compare portfolio metrics and stress windows.
4. Decide whether defensive carry earns a place as Sleeve 4 baseline.
```

## Research Guardrails

This branch is research-only.

Not approved:

```text
Fund v1 runtime changes
Paper-trading changes
Production allocation changes
Execution changes
Strategy/gating changes
```

Approved:

```text
Research scripts
Artifact generation
Portfolio comparison docs
Static allocation tests
Stress analysis
```

## Working Hypothesis

The most likely outcome is not that Sleeve 4 is a spectacular alpha source.

The most likely useful outcome is:

```text
Crypto + SPY + QQQ is the core.
Sleeve 4 is either a modest capital-preservation sleeve or remains empty until a truly orthogonal alpha sleeve is found.
```

That is still a valid fund architecture conclusion.

## Bottom Line

This branch should not chase novelty. It should answer one question:

```text
Can we improve the current three-sleeve core with a fourth sleeve that is genuinely useful, stress-survivable, and implementation-realistic?
```
