# Campaign #57 — Month-End Equity/Bond Rebalancing Pressure

**Status:** CHARTERED 2026-09-02 by explicit CEO authorization. Planning, feasibility, source acquisition for the untouched confirmation pair, and pre-outcome power analysis are authorized. No confirmatory outcome computation, economic strategy test, Core v1/Core v2 composition change, paper/live trading, order, NAV, exposure, or runtime change is authorized by this charter alone.

**Branch:** `agent/exploration-sandbox-governance-20260901`

**Governance:** `docs/ITERA_EXPLORATION_SANDBOX.md`, `docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md`, `.claude/skills/itera-staff/references/org-charter.md`

## 1. Research question

Does mandate-driven month-end asset-allocation rebalancing create a repeatable, causal relationship between pre-window equity-versus-bond relative performance and opposite-signed equity-versus-bond relative performance during the final three trading sessions of the month?

The mechanism is mechanical allocation maintenance by pensions, target-risk/balanced mandates, and other allocators. It is not framed as generic short-horizon mean reversion.

## 2. Why this campaign exists

The exploration sandbox produced `SCREEN_POSITIVE` on SPY/AGG using a design frozen before outcome inspection:

- 275 valid months, 2003-10 through 2026-08;
- primary 3-session Spearman rho = -0.24861256166873433;
- one-sided within-5-year-block permutation p = 0.000999000999000999;
- causal low-signal minus high-signal relative-return spread = +0.008477770698736769;
- spread permutation p = 0.001998001998001998;
- every eligible leave-one-year-out aggregate rho remained negative;
- decade rhos remained negative in the 2000s, 2010s, and 2020s.

A separately frozen Red Team placebo compared the same three-session construction at windows ending 5, 10, and 15 sessions before month-end. The actual month-end window was more negative in rho and larger in low-minus-high spread than all three placebos, returning `MONTH_END_SPECIFICITY_SURVIVES`.

These findings justify governed research only. They are selection-biased discovery evidence and may not be reused as an untouched holdout.

## 3. Structural fit

Primary Core v2 deficiency mapping: **#2 — single return source (pure trend).** The candidate mechanism is mandate/calendar flow rather than trend.

Possible secondary relevance to deficiency #3 (no rates/fixed-income exposure) is not presumed. Whether a future implementation would trade an equity leg, a bond leg, or a relative pair is deliberately left open until mechanism confirmation and an economic implementation review.

Core v1 remains frozen and is out of scope.

## 4. Frozen mechanism-confirmation specification

### 4.1 Primary window

Final **3 shared trading sessions of each calendar month**.

For each month `m`:

1. identify the final three shared sessions for the equity and bond proxy;
2. cutoff = close immediately before those three sessions;
3. anchor = final shared session of the prior calendar month;
4. signal = equity adjusted-total-return performance from anchor to cutoff minus bond adjusted-total-return performance from anchor to cutoff;
5. outcome = equity adjusted-total-return performance from cutoff to month-end minus bond adjusted-total-return performance over the same interval.

Expected sign: negative association between signal and outcome.

No 1-day, 5-day, quarter-end-only, threshold, or alternate-window variant is confirmatory. Those sandbox diagnostics are discovery-contaminated and cannot rescue a failed Campaign #57 confirmation.

### 4.2 Untouched historical confirmation pair

**VTI / BND**, adjusted daily total-return series.

Rationale frozen before acquisition/outcome inspection:

- VTI is a broad US equity proxy rather than the sandbox SPY instrument;
- BND is a broad US investment-grade bond proxy rather than the sandbox AGG instrument;
- both are highly liquid US ETFs and map directly to the same economic allocation mechanism;
- BND's inception naturally limits the common sample, which is acceptable if the pre-outcome power gate passes.

This is a **cross-instrument historical confirmation**, not a fully independent market-event holdout: VTI/BND and SPY/AGG share the same underlying US equity/bond regimes. A successful historical confirmation therefore does not eliminate the need for future-forward evidence before any capital decision.

The VTI/BND source must not be downloaded or inspected for predictive outcomes until the power/feasibility procedure below has frozen the exact usable interval and demonstrated adequate power.

### 4.3 Primary confirmatory statistics

Exactly two co-primary statistics, both required:

1. Spearman correlation between monthly signal and 3-session relative outcome, expected `< 0`.
2. Causal expanding-tercile low-signal minus high-signal outcome spread, expected `> 0`, with 36 prior valid months required before state assignment.

### 4.4 Null/control

Fixed-seed permutations shuffle signal values within five-year calendar blocks while outcomes stay fixed. This preserves broad era structure while breaking the month-specific mapping.

The same random seed family used in the governed implementation must be fixed before outcome inspection.

### 4.5 Confirmatory decision rule

A historical confirmation passes only if all of the following are true:

- Spearman rho `< 0`;
- one-sided block-permutation p for rho `<= 0.05`;
- causal low-minus-high spread `> 0`;
- one-sided block-permutation p for the spread `<= 0.05`;
- leave-one-calendar-year-out Spearman rho is `< 0` for every eligible year with at least six months of source support;
- source and replay validation pass;
- no timing or adjusted-price defect is found.

Failure of any required condition closes the historical confirmation as negative or invalid according to the failure mode. No alternate proxy, window, threshold, or quarter-end subset may be substituted after outcome inspection.

## 5. Power gate — required before confirmation

Before any VTI/BND predictive outcome is computed:

1. acquire only enough source metadata/calendar information to establish common monthly support without calculating the signal/outcome relationship;
2. run a deterministic power simulation using the frozen monthly calendar and effect-size grid derived conservatively from the sandbox discovery ceiling;
3. selection-bias haircut the sandbox effect before injection; the central injected effect may not exceed 50% of the sandbox rank/spread effect without a separately documented external justification;
4. require at least 80% estimated power for the joint confirmatory gate at the central injected effect;
5. if power is below 80%, classify Campaign #57 `UNDERPOWERED` for this historical confirmation architecture. Do not weaken the gate, add windows, or inspect real confirmation outcomes.

The exact simulation implementation and injected-effect grid must be committed before real VTI/BND outcome computation.

## 6. Data/source requirements

- research-only adjusted daily total-return data;
- deterministic timestamp normalization and shared-session intersection;
- source manifests including provider request, actual coverage, row count, and file hash;
- no use of the canonical Core v1 price files for adjusted-total-return inference;
- fail closed on missing months, duplicate dates, nonpositive prices, or ambiguous session ordering.

Sandbox SPY/AGG adjusted files remain discovery artifacts and are not confirmation inputs.

## 7. Economic implementation gate — not yet authorized

No trade rule is frozen by this charter. A successful mechanism confirmation would authorize a separate economic-design phase only.

That later phase must, before any portfolio recommendation:

- specify whether the economically coherent implementation is equity-only, bond-only, or a relative pair;
- define executable timing using information available at the cutoff close or later;
- include spread/slippage and any financing/shorting assumptions;
- estimate turnover, CAGR/return contribution, Sharpe/Calmar, drawdown, capacity, and materiality at approximately $100k capital;
- compare against a same-calendar no-signal benchmark and a generic mean-reversion control;
- establish that expected live value survives a substantial haircut to the backtest ceiling.

No economic test may mutate Core v1.

## 8. Future-forward holdout

Starting only after Campaign #57's specification is frozen, a future-forward SPY/AGG observation ledger may be accumulated without acting on it. It must record, at each month-end cutoff, the frozen signal and later realized three-session outcome without parameter changes.

A future-forward record is required before any capital deployment decision. The amount of forward evidence required will be set by the later Risk/PM and independent Red Team review; this charter does not invent a capital threshold now.

## 9. Red Team and staff boundaries

The in-thread placebo review that killed the generic-reversal objection was performed in the same broader research context and is therefore **not** the mandatory independent Red Team review required to call the candidate `ALIVE`.

Before any `ALIVE`, `VALIDATED`, Core v2 composition, or capital language:

- run Red Team in a genuinely independent subagent/context against the charter, source manifests, code, and raw outputs without CIO/Quant narrative framing;
- then, and only if Red Team passes, route to Risk/PM for portfolio fit and materiality;
- Core v2 composition/weights and all capital decisions require explicit CEO approval.

## 10. Authorized next step

Authorized now, by CEO direction on 2026-09-02:

1. source/calendar feasibility for untouched VTI/BND adjusted daily data;
2. pre-outcome deterministic power simulation under Section 5;
3. documentation/tests necessary to make those two steps replay-safe and fail-closed.

**Not authorized yet:** real VTI/BND signal/outcome computation, confirmation verdict, economic backtest, strategy implementation, Core v2 composition, portfolio sizing, paper/live trading, or any Core v1 change.
