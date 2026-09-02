# Campaign #57 — Month-End Equity/Bond Rebalancing Pressure

**Status:** CHARTERED 2026-09-02 by explicit CEO authorization. **Amended 2026-09-02 before any VTI/BND download or outcome inspection to reserve chronological development, OOS, and final-holdout partitions.** Planning, feasibility, source acquisition for the untouched VTI/BND pair, and pre-outcome power analysis are authorized. No confirmatory outcome computation, economic strategy test, Core v1/Core v2 composition change, paper/live trading, order, NAV, exposure, or runtime change is authorized by this charter alone.

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

### 4.2 VTI/BND historical validation pair

**VTI / BND**, adjusted daily total-return series.

Rationale frozen before acquisition/outcome inspection:

- VTI is a broad US equity proxy rather than the sandbox SPY instrument;
- BND is a broad US investment-grade bond proxy rather than the sandbox AGG instrument;
- both are highly liquid US ETFs and map directly to the same economic allocation mechanism;
- BND's inception naturally limits the common sample, which is acceptable only if the pre-outcome power gates below pass.

This is a **cross-instrument historical validation**, not a fully independent market-event holdout: VTI/BND and SPY/AGG share the same underlying US equity/bond regimes. A successful historical validation therefore does not eliminate the need for future-forward evidence before any capital decision.

The VTI/BND files may be downloaded after this amendment, but predictive outcomes must remain mechanically sealed by partition until the applicable power and stage gates authorize opening them.

### 4.2A Chronological partition amendment — frozen before VTI/BND download

The VTI/BND common valid-month sequence will be partitioned **chronologically by valid-month ordinal position, never randomly and never using returns or signal/outcome values**.

After source/calendar feasibility identifies the ordered list of valid common months:

1. **Development / replication block:** first 50% of valid months.
2. **Chronological OOS block:** next 25% of valid months.
3. **Final historical holdout:** final 25% of valid months.

For odd/non-divisible counts, integer boundaries are deterministic:

- `dev_end = floor(0.50 * N)`;
- `oos_end = floor(0.75 * N)`;
- development = indices `[0, dev_end)`;
- OOS = `[dev_end, oos_end)`;
- final holdout = `[oos_end, N)`.

No date boundary may be moved after source acquisition to improve balance, regime representation, significance, or performance. The exact first/last calendar month of each block will be recorded from source metadata immediately after download, before any signal/outcome computation.

Purpose of the three blocks:

- **Development / replication:** verify the frozen SPY/AGG mechanism on a different proxy pair and permit only pre-authorized implementation diagnostics that do not alter the primary 3-session mechanism.
- **Chronological OOS:** test the frozen rule after all development-stage choices are locked. No parameter or implementation change after opening OOS may be justified by OOS performance.
- **Final historical holdout:** one-shot historical validation after the complete economic/statistical rule is frozen. It is not opened merely because OOS looks promising.

The final holdout is a **hard seal**. Monte Carlo/bootstrap work does not consume it and may not use its returns.

### 4.3 Primary statistics

Exactly two co-primary statistics, both required at each opened validation stage:

1. Spearman correlation between monthly signal and 3-session relative outcome, expected `< 0`.
2. Causal expanding-tercile low-signal minus high-signal outcome spread, expected `> 0`, with 36 prior valid months required before state assignment.

For OOS and final-holdout evaluation, tercile thresholds must be generated causally from information available before each tested month. No percentile threshold may be learned using future OOS/holdout months.

### 4.4 Null/control

Fixed-seed permutations shuffle signal values within five-year calendar blocks while outcomes stay fixed. This preserves broad era structure while breaking the month-specific mapping.

The same random seed family used in the governed implementation must be fixed before outcome inspection.

### 4.5 Staged decision rule

#### Development / replication

Development is not a confirmation and may not be called OOS. It passes only if the frozen expected sign is present for both co-primary statistics and source/replay checks pass. Statistical significance is reported but is not by itself sufficient to promote a changed rule; the rule is already frozen from SPY/AGG.

#### Chronological OOS

OOS may be opened only after:

- partition boundaries are committed;
- development-stage code and rule are frozen;
- OOS-specific power is at least 80% at the central haircutted effect under Section 5.

OOS passes only if all of the following are true:

- Spearman rho `< 0`;
- one-sided block-permutation p for rho `<= 0.05`;
- causal low-minus-high spread `> 0`;
- one-sided block-permutation p for the spread `<= 0.05`;
- source and replay validation pass;
- no timing or adjusted-price defect is found.

#### Final historical holdout

The final holdout may be opened only after:

- OOS passes without any post-OOS parameter/rule modification;
- the complete economic/statistical rule is frozen;
- final-holdout-specific power is at least 80% at the central haircutted effect under Section 5;
- a one-shot holdout decision record is committed before computation.

Final holdout passes under the same co-primary sign/significance requirements as OOS. No alternate proxy, window, threshold, quarter-end subset, or post-hoc weighting may substitute after outcome inspection.

Failure of any required condition closes the applicable stage as negative or invalid according to the failure mode. A failed OOS or final holdout cannot be rescued by recombining partitions.

## 5. Power gates — required before opening each VTI/BND outcome stage

Before any VTI/BND predictive outcome is computed:

1. acquire source files and inspect **only metadata/calendar structure** needed to establish valid common months and partition boundaries;
2. record exact development/OOS/final-holdout calendar intervals from the deterministic 50/25/25 rule;
3. run deterministic power simulations using the frozen monthly calendar and effect-size grid derived conservatively from the sandbox discovery ceiling;
4. selection-bias haircut the sandbox effect before injection; the central injected effect may not exceed 50% of the sandbox rank/spread effect without a separately documented external justification;
5. estimate power separately for development, OOS, and final holdout using each block's own month count/calendar structure;
6. require at least **80% estimated power for the OOS joint gate** before OOS may be opened;
7. require at least **80% estimated power for the final-holdout joint gate** before the final holdout may ever be opened;
8. if either OOS or final-holdout power is below 80%, classify that historical architecture `UNDERPOWERED` for the affected stage. Do not weaken the gate, move partition boundaries, merge OOS with holdout, add windows, or inspect the sealed outcomes.

The exact simulation implementation, injected-effect grid, random seeds, and partition manifest must be committed before real VTI/BND outcome computation.

## 6. Monte Carlo / bootstrap role

Monte Carlo or bootstrap analysis is **not a substitute for OOS or the final holdout**.

It may be run only on data from stages already legitimately opened, and before the final holdout it must exclude final-holdout returns entirely.

Its purpose is to estimate:

- sampling uncertainty around the observed effect;
- sequence risk and drawdown dispersion for any later economic implementation;
- plausible Sharpe/Calmar/CAGR ranges under resampled event sequences;
- probability of negative or disappointing finite-sample outcomes despite a positive underlying edge.

Any bootstrap must respect the monthly/event structure and any measured serial dependence; naive IID reshuffling is not automatically acceptable.

## 7. Data/source requirements

- research-only adjusted daily total-return data;
- deterministic timestamp normalization and shared-session intersection;
- source manifests including provider request, actual coverage, row count, and file hash;
- no use of the canonical Core v1 price files for adjusted-total-return inference;
- fail closed on missing months, duplicate dates, nonpositive prices, or ambiguous session ordering;
- partition manifest containing `N`, ordinal boundaries, and exact month ranges must be written before any predictive outcome computation.

Sandbox SPY/AGG adjusted files remain discovery artifacts and are not confirmation inputs.

## 8. Economic implementation gate — not yet authorized

No trade rule is frozen by this charter. A successful mechanism validation would authorize a separate economic-design phase only.

That later phase must, before any portfolio recommendation:

- specify whether the economically coherent implementation is equity-only, bond-only, or a relative pair;
- define executable timing using information available at the cutoff close or later;
- include spread/slippage and any financing/shorting assumptions;
- estimate turnover, CAGR/return contribution, Sharpe/Calmar, drawdown, capacity, and materiality at approximately $100k capital;
- compare against a same-calendar no-signal benchmark and a generic mean-reversion control;
- establish that expected live value survives a substantial haircut to the backtest ceiling.

No economic test may mutate Core v1.

## 9. Future-forward holdout

Starting only after Campaign #57's specification is frozen, a future-forward SPY/AGG observation ledger may be accumulated without acting on it. It must record, at each month-end cutoff, the frozen signal and later realized three-session outcome without parameter changes.

A future-forward record is required before any capital deployment decision. The amount of forward evidence required will be set by the later Risk/PM and independent Red Team review; this charter does not invent a capital threshold now.

## 10. Red Team and staff boundaries

The in-thread placebo review that killed the generic-reversal objection was performed in the same broader research context and is therefore **not** the mandatory independent Red Team review required to call the candidate `ALIVE`.

Before any `ALIVE`, `VALIDATED`, Core v2 composition, or capital language:

- run Red Team in a genuinely independent subagent/context against the charter, source manifests, code, and raw outputs without CIO/Quant narrative framing;
- then, and only if Red Team passes, route to Risk/PM for portfolio fit and materiality;
- Core v2 composition/weights and all capital decisions require explicit CEO approval.

## 11. Authorized next step

Authorized now, by CEO direction on 2026-09-02 and the same-day pre-download partition amendment:

1. download adjusted daily VTI/BND data for research-only use;
2. inspect source/calendar metadata only;
3. write and commit the deterministic 50/25/25 partition manifest;
4. run separate pre-outcome power simulations for development, OOS, and final holdout;
5. documentation/tests necessary to make those steps replay-safe and fail-closed.

**Not authorized yet:** any VTI/BND signal/outcome computation, development result, OOS result, final-holdout result, economic backtest, strategy implementation, Core v2 composition, portfolio sizing, paper/live trading, or any Core v1 change.
