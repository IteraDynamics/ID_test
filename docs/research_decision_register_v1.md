# Research Decision Register v1

## Status

**Branch:** `research/decision-register-v1`

**Purpose:** Maintain a canonical decision register for major Itera research checkpoints.

**Scope:** Research and product/reporting decisions only. This document does not approve paper trading, live allocation, broker/execution changes, dashboard integration, runtime changes, or a global dynamic allocator.

## Why This Exists

Itera now has multiple independent research tracks:

```text
crypto sleeve research
equity core research
defensive-carry equity enhancement research
sector rotation research
breadth / dispersion alpha diagnostics
fund-level side-by-side composite research
```

The risk is no longer lack of research. The risk is losing the thread.

This register answers:

```text
What did we test?
What did we promote?
What did we reject?
What is still open?
What should happen next?
```

## Current Architecture View

### Execution / Research Architecture

```text
Crypto systems run independently.
Equity systems run independently.
No central dynamic allocator currently routes capital between them.
```

### Fund Reporting / Product View

```text
Independent crypto + equity systems may be viewed as a static side-by-side fund composite for investor/reporting analysis.
```

This distinction is important.

The side-by-side composite is not a return to a dynamic allocator. It is a fund-level reporting and product framing layer.

---

# Decision Summary

## Promoted

```text
1. Crypto Risk Budget / calibrated crypto sleeve as independent crypto system candidate.
2. Equity Core v1: SPY/QQQ SMA175 trend-risk book.
3. Defensive Carry: short-duration Treasury proxy risk-off family.
4. Fund Side-by-Side Composite v1 as reporting/product view.
```

## Active Alpha Leads

```text
1. Breadth / Dispersion / Leadership Alpha v1.
2. Key lead: weak_breadth__qqq_leading.
3. Secondary lead: high sector correlation as possible core risk-on confirmation.
```

## Not Promoted / Demoted

```text
1. Sector Rotation v1 initial Top 3 sector momentum design.
2. Duration-heavy risk-off substitutes: IEF, TLT.
3. GLD as default equity risk-off substitute.
4. 70/30 crypto-heavy side-by-side composite as primary fund view.
```

---

# 1. Crypto Risk Budget / Crypto Sleeve

## Status

```text
PROMOTED AS INDEPENDENT CRYPTO SYSTEM CANDIDATE
```

## Relevant Artifacts

```text
artifacts/crypto_risk_budget_v2_capture_audit/equity_curves.csv
artifacts/crypto_risk_budget_v2_sweep/equity_curves.csv
artifacts/fund_tilted_cal_4s_2019-03-08_2025-12-31/equity_curves.csv
```

## Decision

The crypto risk-budget / calibrated crypto sleeve remains a valid independent crypto system candidate.

It should be evaluated independently and also used as an input to fund-level side-by-side reporting.

## Evidence

From the fund side-by-side composite tests, the tilted 4-sleeve crypto sleeve over the common fund window showed:

```text
CRYPTO_SLEEVE
Window: 2019-03-08 → 2025-12-30
CAGR:   18.30%
MaxDD: -18.89%
Sharpe: 1.133
Calmar: 0.969
AnnVol: 16.00%
```

The daily crypto risk-budget `Fund_v1` pass showed:

```text
CRYPTO_SLEEVE
Window: 2019-03-08 → 2025-12-30
CAGR:   18.35%
MaxDD: -17.72%
Sharpe: 1.167
Calmar: 1.036
AnnVol: 15.50%
```

## Benchmark Context

Passive crypto beta delivered much higher raw CAGR during the 2019–2025 crypto bull-cycle window, but with extreme drawdowns:

```text
BTC_ETH_50_50_DAILY_REBAL
CAGR:   62.49%
MaxDD: -76.34%
Sharpe: 1.054
Calmar: 0.819

BTC_HODL
CAGR:   58.28%
MaxDD: -76.67%
Sharpe: 1.046
Calmar: 0.760

ETH_HODL
CAGR:   57.79%
MaxDD: -78.44%
Sharpe: 0.971
Calmar: 0.737
```

## Interpretation

The crypto system is not a raw-beta replacement for BTC/ETH HODL during a massive crypto upcycle.

It is a governed crypto return stream with materially lower drawdown and better fund-composite compatibility.

## Open Questions

```text
1. Should the current tilted 4-sleeve crypto curve become the preferred crypto sleeve input for future fund-level reporting?
2. Should crypto benchmark columns be added to all future multi-sleeve crypto artifacts?
3. Should crypto system validation add more explicit fee/slippage/capacity assumptions?
```

## Next Action

```text
Keep as promoted independent crypto sleeve candidate.
Use tilted 4-sleeve crypto as preferred fund-composite input unless later superseded.
```

---

# 2. Equity Core v1

## Status

```text
PROMOTED
```

## Relevant Files

```text
research/strategies/equity_spy_qqq_sma_band_v1.py
scripts/run_equity_book_v1_signal_readiness.py
```

## Decision

Promote Equity Core v1 as:

```text
SPY/QQQ SMA175 trend-risk book
```

This is the base equity participation sleeve.

## Evidence

Signal-readiness replay showed:

```text
EQUITY BOOK SMA BAND / CASH RISK-OFF
Window: 2005-01-03 → 2026-04-29
CAGR:   10.29%
MaxDD: -19.56%
Sharpe: 0.849
Calmar: 0.526
```

Passive SPY/QQQ 50/50 over the full equity window showed:

```text
PASSIVE SPY/QQQ 50/50
CAGR:   12.93%
MaxDD: -53.66%
Sharpe: 0.712
Calmar: 0.241
```

## Interpretation

Equity Core v1 gives up some raw CAGR versus passive SPY/QQQ but dramatically improves drawdown and Calmar.

It is not the alpha engine. It is the governed equity participation anchor.

## Open Questions

```text
1. Should Equity Core use BIL as default risk-off in all future research views?
2. Should a live/paper implementation readiness branch eventually parameterize risk-off asset cleanly?
3. Should the equity core include alpha overlays from breadth/dispersion research?
```

## Next Action

```text
Keep as promoted equity base.
Use SMA175 as the default center setting.
Use BIL-risk-off in fund-level reporting unless explicitly comparing to cash.
```

---

# 3. Defensive Carry / Risk-Off Substitute Research

## Status

```text
PROMOTED SHORT-DURATION TREASURY PROXY FAMILY
```

## Relevant Files

```text
scripts/run_equity_enhancements_v1_defensive_sweep.py
docs/equity_enhancements_v1_defensive_findings.md
```

## Decision

Promote short-duration Treasury proxies as the equity risk-off enhancement family.

Preferred practical candidate:

```text
BIL
```

Best recent-history candidate:

```text
SGOV
```

Secondary candidate:

```text
SHV
```

Reference baseline:

```text
cash
```

Demoted/rejected as default risk-off:

```text
IEF
TLT
GLD
```

## Evidence

Pairwise versus cash showed:

```text
SGOV vs cash over SGOV overlap:
  Delta CAGR:   +0.54 percentage points
  Delta MaxDD:  +1.36 percentage points
  Delta Sharpe: +0.033
  Delta Calmar: +0.140

BIL vs cash over BIL overlap:
  Delta CAGR:   +0.42 percentage points
  Delta MaxDD:  +0.03 percentage points
  Delta Sharpe: +0.025
  Delta Calmar: +0.023

SHV vs cash over SHV overlap:
  Delta CAGR:   +0.37 percentage points
  Delta MaxDD:  +0.03 percentage points
  Delta Sharpe: +0.023
  Delta Calmar: +0.020
```

Duration/gold candidates introduced hidden risk:

```text
IEF vs cash:
  Delta CAGR:   +0.75 percentage points
  Delta MaxDD:  -6.08 percentage points
  Delta Calmar: -0.096

GLD vs cash:
  Delta CAGR:   +1.87 percentage points
  Delta MaxDD: -16.03 percentage points
  Delta Calmar: -0.184

TLT vs cash:
  Delta CAGR:   -0.06 percentage points
  Delta MaxDD: -20.62 percentage points
  Delta Calmar: -0.272
```

## Interpretation

Short-duration Treasury proxies improve the idle/risk-off sleeve modestly and cleanly.

IEF/TLT/GLD are not clean default risk-off substitutes because they add duration or commodity regime risk.

## Open Questions

```text
1. Should BIL become the default risk-off proxy in all equity reporting scripts?
2. Should SGOV be used for recent-history research only, with BIL as long-history practical default?
3. Should cash remain a mandatory benchmark row in every equity report?
```

## Next Action

```text
Use BIL as default practical risk-off in fund/reporting research.
Keep cash as reference baseline.
```

---

# 4. Sector Rotation v1

## Status

```text
NOT PROMOTED
```

## Relevant Files

```text
scripts/run_equity_sector_rotation_v1_sweep.py
docs/equity_sector_rotation_v1_research_plan.md
```

## Decision

Do not promote the initial Top 3 sector momentum / SMA200 design as an equity alpha sleeve.

## Evidence

Best sector variant:

```text
SECTOR_TOP3_MOM126_SMA200_SPYFILTER_BIL
CAGR:   9.87%
MaxDD: -16.74%
Sharpe: 0.775
Calmar: 0.590
```

Equity Core + BIL over the comparable period:

```text
EQUITY_CORE_SMA175_BIL
CAGR:   17.03%
MaxDD: -19.53%
Sharpe: 1.181
Calmar: 0.872
```

## Interpretation

The sector strategy reduced drawdown slightly, but gave up too much CAGR and Sharpe.

No-SPY-filter variants were especially weak:

```text
NO_SPYFILTER_BIL:
  CAGR:   11.20%
  MaxDD: -26.54%
  Sharpe: 0.699
  Calmar: 0.422

NO_SPYFILTER_CASH:
  CAGR:    7.32%
  MaxDD: -43.20%
  Sharpe: 0.534
  Calmar: 0.170
```

## Open Questions

```text
1. Is sector rotation structurally weak here, or was the initial configuration too naive?
2. Should sector rotation only activate during high-dispersion regimes?
3. Should sector rotation be revisited only after breadth/dispersion diagnostics mature?
```

## Next Action

```text
Do not continue vanilla sector-parameter sweeps for now.
Revisit only as a conditional strategy gated by dispersion/market-structure signals.
```

---

# 5. Equity Alpha v1 — Breadth / Dispersion / Leadership Diagnostics

## Status

```text
ACTIVE ALPHA LEAD
```

## Relevant Files

```text
scripts/run_equity_alpha_breadth_dispersion_v1.py
docs/equity_alpha_breadth_dispersion_v1_research_plan.md
```

## Decision

Promote the breadth/dispersion/leadership framework as the first active equity alpha lead.

Do not promote a trading strategy yet.

## Key Lead

Primary candidate regime:

```text
weak_breadth__qqq_leading
```

For Equity Core + BIL, this regime showed strong forward-return separation:

```text
21d forward:
  mean:   +3.64%
  median: +4.38%
  hit:    89.08%
  n:      119

63d forward:
  mean:   +12.27%
  median: +13.69%
  hit:    95.80%
  n:      119

126d forward:
  mean:   +19.85%
  hit:    95.80%
  n:      119
```

Edge summary showed:

```text
126d weak_breadth__qqq_leading vs weak_breadth__qqq_lagging:
  edge spread: +15.51 percentage points

63d weak_breadth__qqq_leading vs weak_breadth__qqq_lagging:
  edge spread: +10.61 percentage points
```

## Secondary Lead

High sector correlation may be a core risk-on confirmation state:

```text
EQUITY_CORE_BIL, 126d forward:
  high corr mean: +11.36%
  low corr mean:  +5.39%
  edge:           +5.97 percentage points

EQUITY_CORE_BIL, 63d forward:
  high corr mean: +6.67%
  low corr mean:  +0.74%
  edge:           +5.93 percentage points
```

## Interpretation

The diagnostics challenge the simplistic rule:

```text
weak breadth = bearish
```

A better interpretation may be:

```text
weak breadth + QQQ leadership = narrow growth acceleration / concentrated recovery regime
weak breadth + QQQ lagging = caution regime
high sector correlation = broad index-level risk-on confirmation
```

## Open Questions

```text
1. Can weak_breadth__qqq_leading be converted into a monetizable rule without overfitting?
2. Should it boost exposure, suppress de-risking, or simply classify regime quality?
3. Does weak_breadth__qqq_lagging improve outcomes as a risk-reduction trigger?
4. Does high correlation improve Equity Core as a confirmation filter?
5. Are these effects stable across subperiods and not just post-2020 artifacts?
```

## Next Action

```text
Build Equity Alpha v1 Rule Replay.
```

Candidate replay rules:

```text
1. Boost/allow Equity Core during weak_breadth__qqq_leading.
2. Reduce Equity Core during weak_breadth__qqq_lagging.
3. Confirm Equity Core risk-on during high sector correlation.
4. Combined overlay:
   bullish = weak_breadth__qqq_leading OR high_corr
   caution = weak_breadth__qqq_lagging OR low_corr
```

---

# 6. Fund Side-by-Side Composite v1

## Status

```text
PROMOTED AS FUND REPORTING / PRODUCT VIEW
```

## Relevant Files

```text
scripts/run_fund_side_by_side_composite_v1.py
docs/fund_side_by_side_composite_v1_research_plan.md
docs/fund_side_by_side_composite_v1_findings.md
```

## Decision

Promote the side-by-side composite as an investor-facing fund-level reporting view.

This is not a dynamic allocator.

Preferred initial composite:

```text
50% crypto / 50% equity
```

Secondary candidate:

```text
60% crypto / 40% equity
```

Demote:

```text
70% crypto / 30% equity
```

## Evidence — Tilted 4-Sleeve Crypto + Equity Core BIL

```text
FUND_STATIC_CRYPTO50_EQUITY50
Window: 2019-03-08 → 2025-12-30
CAGR:   18.32%
MaxDD: -14.15%
Sharpe: 1.617
Sortino: 2.512
Calmar: 1.295
AnnVol: 10.80%
Worst 90d:  -10.08%
Worst 180d: -11.22%
```

Versus standalone sleeves:

```text
CRYPTO_SLEEVE
CAGR:   18.30%
MaxDD: -18.89%
Sharpe: 1.133
Calmar: 0.969

EQUITY_SLEEVE
CAGR:   17.03%
MaxDD: -19.53%
Sharpe: 1.181
Calmar: 0.872
```

Versus passive SPY/QQQ 50/50:

```text
PASSIVE_SPY_QQQ_50_50
CAGR:   18.97%
MaxDD: -30.86%
Sharpe: 0.909
Calmar: 0.615
AnnVol: 21.78%
```

## Expanded Crypto Benchmark Context

Using the `Fund_v1` daily crypto artifact with passive crypto benchmarks:

```text
FUND_STATIC_CRYPTO50_EQUITY50
CAGR:   18.25%
MaxDD: -14.14%
Sharpe: 1.563
Calmar: 1.291

BTC_ETH_50_50_DAILY_REBAL
CAGR:   62.49%
MaxDD: -76.34%
Sharpe: 1.054
Calmar: 0.819

BTC_HODL
CAGR:   58.28%
MaxDD: -76.67%
Sharpe: 1.046
Calmar: 0.760
```

## Market-Beating Interpretation

Do not say:

```text
Itera beat the market.
```

Preferred language:

```text
The side-by-side composite nearly matched passive SPY/QQQ 50/50 raw CAGR while reducing max drawdown by more than half and materially improving Sharpe and Calmar.
```

For passive crypto:

```text
The composite did not match passive BTC/ETH raw returns during the 2019–2025 crypto bull-cycle window, but it delivered a much smoother return stream with dramatically lower drawdown, lower volatility, and better Sharpe/Calmar than passive BTC/ETH baskets.
```

## Open Questions

```text
1. Should the 50/50 composite become the default investor-facing fund tear-sheet view?
2. Should 60/40 be shown as an aggressive variant?
3. Should the composite runner become a standard report script in CI, or remain manual research for now?
4. Should crypto passive benchmarks be embedded in all future crypto sleeve artifacts?
```

## Next Action

```text
Keep as promoted reporting/product view.
Do not implement as live allocator.
```

---

# Current Priority Stack

## Priority 1 — Finish Decision Register

```text
Status: current branch
Goal: merge this canonical decision register.
```

## Priority 2 — Equity Alpha Rule Replay

```text
Branch suggestion: research/equity-alpha-rule-replay-v1
Goal: convert breadth/dispersion diagnostics into candidate overlays and test whether the information is monetizable.
```

## Priority 3 — Fund Tear Sheet / Reporting Package

```text
Branch suggestion: research/fund-tearsheet-v1
Goal: generate a clean investor-style report from fund side-by-side composite outputs.
```

## Priority 4 — Implementation Readiness Review

```text
Goal: decide which promoted research components should become reusable modules versus staying as scripts/docs.
```

---

# Explicit Non-Decisions

This register does not approve:

```text
paper trading
live allocation
broker/execution changes
a dynamic crypto/equity allocator
a dashboard integration
a new capital-routing engine
ML model deployment
sector rotation promotion
```

---

# Bottom Line

Itera now has a coherent research state:

```text
Crypto sleeve: promoted independent system candidate.
Equity Core: promoted governed equity base.
Defensive Carry: promoted BIL/short-duration Treasury proxy family.
Sector Rotation: initial vanilla design not promoted.
Breadth/Dispersion: active alpha lead.
Fund Composite: promoted investor-facing reporting/product view.
```

The next research implementation should be the equity alpha rule replay, not another broad sweep.
