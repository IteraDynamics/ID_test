# Fund Tear Sheet v1 — Research Plan

## Status

**Branch:** `research/fund-tearsheet-v1`

**Purpose:** Convert promoted Itera research outputs into a concise investor-style fund tear sheet.

**Guardrail:** Reporting only. This branch does not approve paper trading, live allocation, broker/execution changes, runtime changes, dashboard integration, or a dynamic crypto/equity allocator.

## Why This Exists

Recent research established the current promoted architecture:

```text
Crypto sleeve: promoted independent system candidate.
Equity sleeve: promoted Equity Core SMA175 + BIL.
Fund view: promoted static side-by-side composite, preferred 50/50.
Equity alpha overlays: not promoted.
Sector rotation: not promoted.
```

The project now needs a clean reporting artifact that answers:

```text
What is the fund concept?
What are the promoted sleeves?
What is the current preferred composite?
How did it perform?
What did it beat?
What did it not beat?
What are the caveats?
```

## Inputs

Primary source artifacts:

```text
artifacts/fund_side_by_side_composite_v1/performance_summary.csv
artifacts/fund_side_by_side_composite_v1/capture_summary.csv
artifacts/fund_side_by_side_composite_v1/window_performance_summary.csv
artifacts/fund_side_by_side_composite_v1_tilted_4s/performance_summary.csv
artifacts/fund_side_by_side_composite_v1_tilted_4s/capture_summary.csv
artifacts/fund_side_by_side_composite_v1_tilted_4s/window_performance_summary.csv
```

Reference docs:

```text
docs/research_decision_register_v1.md
docs/fund_side_by_side_composite_v1_findings.md
docs/equity_alpha_rule_replay_v1_findings.md
```

## Preferred Composite

Primary current view:

```text
FUND_STATIC_CRYPTO50_EQUITY50
```

Secondary view:

```text
FUND_STATIC_CRYPTO60_EQUITY40
```

## Required Outputs

```text
artifacts/fund_tearsheet_v1/
  fund_tearsheet.md
  fund_tearsheet_summary.json
  selected_performance_table.csv
  benchmark_comparison_table.csv
  window_summary_table.csv
```

## Tear Sheet Sections

```text
1. Executive Summary
2. Current Promoted Architecture
3. Preferred Composite
4. Performance Table
5. Benchmark Comparison
6. Window / Stress Period Review
7. What This Beats
8. What This Does Not Beat
9. Research Decisions
10. Caveats
11. Non-Approved Items
```

## Interpretation Rules

Do not use vague claims like:

```text
Itera beat the market.
```

Use precise benchmark-relative language:

```text
The composite nearly matched passive SPY/QQQ 50/50 raw CAGR while cutting max drawdown by more than half and materially improving Sharpe and Calmar.
```

For crypto benchmarks:

```text
The composite did not match passive BTC/ETH raw returns during the 2019–2025 crypto bull-cycle window, but delivered a smoother, lower-drawdown, better risk-adjusted return stream.
```

## Non-Goals

```text
No new strategy research.
No optimizer.
No ML.
No paper trading.
No live trading.
No broker integration.
No dashboard integration.
No dynamic allocator.
```

## Bottom Line

This branch turns the research state into a coherent fund-facing artifact. It is about communication, auditability, and institutional packaging, not new alpha discovery.
