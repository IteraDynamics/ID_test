---
name: exploration-screen
description: >
  Run a cheap, pre-campaign Itera alpha screen under docs/ITERA_EXPLORATION_SANDBOX.md.
  Use when the CEO says "find alpha", "give me a backtest", "screen this idea", "test this
  quickly", or asks for an immediately-testable strategy without first chartering a full
  campaign. This skill is for deciding whether an idea deserves governed research, never for
  validating, sizing, or deploying it.
---

# Itera Exploration Screen

Read, in order:

1. `docs/ITERA_CAMPAIGN_BOARD.md`
2. `ops/status.md`
3. `ops/campaign-log.md`
4. `docs/ITERA_EXPLORATION_SANDBOX.md`
5. `docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md` Amendment 6

Core v1 is frozen. A screen may not modify runtime, strategy, weights, parameters, orders, NAV,
exposure, production state, or live/paper capital.

## Step 1 — pick for prior, not convenience

Before code, write a six-line screen card:

- Mechanism: the persistent friction or compelled/non-alpha-maximizing behavior creating the edge.
- Survival argument: why modern competition has not trivially arbitraged it away.
- Instrument/venue: what would be traded and whether the operator can access it.
- Horizon sanity: expected decay horizon versus measured runtime cadence.
- Falsification: the result that kills the screen.
- Time budget: normally one working session, hard stop at one day without CIO escalation.

Prefer forced hedging, benchmark/index flows, mechanical rebalancing, funding/liquidation/margin
mechanics, dealer inventory constraints, expiry/roll structure, mandate-driven flows, segmentation,
or regulatory/capital constraints. A famous anomaly or easy dataset is not a mechanism.

## Step 2 — build the cheapest valid test

Minimum requirements:

- coherent universe with explicit filtering;
- causal timestamp handling and fail-closed ambiguity;
- costs/slippage where they can decide the sign;
- negative/random/permutation/benchmark control when meaningful;
- sample/trade/window counts and coverage gaps;
- thin-universe and outlier-dominance diagnostics;
- robust aggregation for fat-tailed cross-sections;
- deterministic seed/output for fixed inputs;
- no write path outside research artifacts/logging.

Do not build campaign-level power simulation, FDR family, untouched holdout, or a full campaign
charter at this stage. The point is to avoid paying those costs for ideas that die cheaply.

## Step 3 — classify mechanically

Exactly one result:

- `SCREEN_NEGATIVE`
- `SCREEN_INCONCLUSIVE`
- `SCREEN_POSITIVE`
- `SCREEN_INVALID`

`SCREEN_INVALID` means fix the infrastructure defect and rerun; never count the invalid result.
`SCREEN_POSITIVE` means only "worth a governed campaign." Never call it alive, validated, or
confirmed.

## Step 4 — log and route

Log the screen in `ops/campaign-log.md` as `Exploration screen` with mechanism, classification,
headline evidence, control result, and reusable infrastructure findings.

If negative: close autonomously.

If inconclusive: state the missing evidence; do not reinterpret as a null.

If positive: stop. Hand to CIO for campaign promotion. The sandbox data is discovery-contaminated
and cannot serve as the untouched confirmation holdout. Independent Red Team review is mandatory
before any candidate is called alive; Risk/PM and CEO approval are mandatory before Core v2
composition or sizing.

Every reported backtest number remains a selection-biased ceiling, not a live expectation.
