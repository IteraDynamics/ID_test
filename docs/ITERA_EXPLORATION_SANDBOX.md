# Itera Exploration Sandbox

**Status:** ADOPTED 2026-09-01 by CEO direction.

## Purpose

The sandbox is a cheap, fast screening layer between an idea and a governed research campaign. It exists to reduce the procedural cost of asking whether an idea deserves serious research without lowering the evidentiary standard for believing, deploying, or adding an edge.

A sandbox result is never a confirmed finding, never a Core v2 component, and never an authorization for paper/live trading.

Core v1 remains frozen. Nothing in this protocol authorizes any Core v1 behavior, parameter, weight, source, order, NAV, exposure, or runtime change.

## Staff review that produced this rule

The CEO directed staff on 2026-09-01 to institutionalize the lesson from the off-charter pairs and low-volatility screens. This environment can read/write the repository but cannot spawn genuinely independent subagent contexts, so the staff consultation was run sequentially against the checked-in seat mandates and is explicitly weaker than a Claude Code multi-subagent review. No sandbox-positive candidate may be called alive until an independent Red Team review is run in an environment that supports it.

Seat conclusions:

- **CIO:** approve a screening layer, but improve candidate priors. Convenience, novelty, and available data are not enough. Prefer mechanisms caused by persistent non-alpha-maximizing behavior: forced hedging, mechanical rebalancing, benchmark/index flows, funding/liquidation mechanics, dealer inventory constraints, expiry structure, mandate-driven flows, or similar structural frictions.
- **Quant Researcher:** screens must remain reproducible and falsifiable even when cheap: coherent universe, causal timing, deterministic output, realistic costs when material, and a negative/control comparison where one is meaningful.
- **Red Team:** the sandbox must not become a route around independent review. A positive screen earns a campaign review only; it cannot be labeled validated or alive. Outlier dominance, windowing, autocorrelation, multiplicity, sign, universe construction, and holdout contamination remain mandatory adversarial checks before promotion.
- **Risk/PM:** no portfolio weight, Core v2 composition decision, or capital allocation may be inferred from a sandbox backtest. Portfolio fit begins only after research validity survives Red Team.
- **Ops/Compliance:** cheap tradeability and horizon sanity checks remain mandatory even in exploration; there is no value screening an instrument the operator cannot access or an effect that expires before the system can act.
- **Performance:** sandbox numbers are backtest screens, not expectations. They must be labeled as selection-biased ceilings and must not enter live/paper performance reporting.

## Entry standard

Before code is written, record a short screen card containing:

1. **Mechanism:** what persistent economic friction or compelled behavior should create the edge?
2. **Why now / why not arbitraged away:** the structural reason the effect could survive modern competition.
3. **Instrument and venue:** what would actually be traded, and whether the operator can access it.
4. **Horizon sanity:** expected effect horizon versus measured runtime cadence; exact power analysis is not required at sandbox stage.
5. **Falsification:** the result that kills the screen.
6. **Budget:** target wall-clock research effort, normally no more than one working session and never more than one day without CIO escalation.

A famous anomaly, paper, or textbook strategy is not a sufficient mechanism by itself. If the only rationale is historical publication, novelty, or easy data access, the screen should normally be deprioritized.

## Minimum screen requirements

A sandbox implementation must:

- use a coherent, explicitly filtered universe;
- enforce causal timestamps and fail closed on ambiguous time alignment;
- include transaction costs/slippage when they can plausibly decide the sign of the result;
- include a negative control, permutation/randomized comparator, benchmark, or other falsification control when the mechanism admits one;
- report sample size, trade/window count, coverage gaps, and skipped periods;
- expose diagnostics capable of revealing thin-universe or single-observation domination;
- use robust aggregation when fat tails can dominate a mean;
- be deterministic/replayable for a fixed input set and seed;
- write outputs to artifacts or stdout without modifying runtime, strategy, portfolio, or production state.

The sandbox does **not** require campaign-level power simulation, FDR design, a frozen holdout, a campaign number, a full campaign document, or a later-day specification freeze. Those costs are paid only after a screen earns promotion.

## Screen classifications

Every screen ends in exactly one of these states:

- `SCREEN_NEGATIVE` — mechanism failed the screen or underperformed its control. Close and log it.
- `SCREEN_INCONCLUSIVE` — data/coverage/power/implementation limits prevent a useful read. Do not interpret as evidence against the mechanism.
- `SCREEN_POSITIVE` — effect is economically/statistically interesting enough to justify governed research. This is **not** `ALIVE`, `VALIDATED`, or `CONFIRMED`.
- `SCREEN_INVALID` — infrastructure, universe, timing, or implementation defect invalidated the run. Fix the defect and rerun; never count the invalid result.

## Promotion rule

A `SCREEN_POSITIVE` candidate returns to the normal governed pipeline before any claim of validity:

1. CIO checks fit against the research queue and named structural deficiencies.
2. A normal campaign is chartered or the candidate is attached to an already-authorized campaign.
3. Horizon feasibility, tradeability, materiality, power, frozen specification, discovery/confirmation, and untouched holdout rules apply in full.
4. Independent Red Team review is mandatory before the candidate can be called alive.
5. Risk/PM review and CEO approval are required before any Core v2 composition/weight decision.

No sandbox artifact may be reused as the untouched confirmation holdout for the promoted campaign. The sandbox data is discovery-contaminated by definition.

## Candidate-selection priority

For alpha hunting, prefer hypotheses with a structural counterparty or compelled flow over generic transformations of price history. High-priority mechanism classes include:

- forced or mandate-driven hedging;
- index/benchmark/reconstitution flows;
- mechanical rebalance flows;
- funding, liquidation, margin, or collateral mechanics;
- dealer inventory/option-hedging constraints;
- expiry/roll/calendar structure;
- segmentation or access frictions;
- capital/regulatory constraints that force non-economic timing.

This list is illustrative, not a pre-approved candidate list. Every actual screen still needs its own mechanism card.

## Logging

Sandbox screens are logged in `ops/campaign-log.md` with the label `Exploration screen` rather than assigned a campaign number. The log must record the mechanism, screen classification, headline evidence, the control that killed/kept it alive, and any reusable infrastructure finding.

The current snapshot belongs in `ops/status.md`; CEO authorizations and process changes belong in `ops/decisions.md`.
