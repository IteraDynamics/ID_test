# RRE Core v1 Entry/Add-on Deferral — Frozen Pre-Outcome Specification — 2026-09-18

## Status

**FROZEN DESIGN / PRE-OUTCOME ONLY.**

This document defines one downstream economic hypothesis before any counterfactual P&L is computed. It does not authorize production, paper/live runtime, strategy, Core-label, allocation, order, NAV, exposure, execution, cost, or threshold changes. The historical Core v1 control remains unchanged.

No economic result has been observed under this specification at freeze time.

## Scientific question

When authentic Core v1 has already decided to **increase** long crypto exposure, does a causal estimate that the current Core semantic regime is unusually unstable identify exposure increases that are better **deferred until the next native decision opportunity**?

The RRE is not permitted to create direction, reverse direction, force an exit, enlarge an exposure target, relabel Core, or replace any existing Core signal.

## Rationale fixed before outcome observation

Prior observation-only research established distinct roles:

- Core label = semantic/discrete state used by the authentic strategy;
- PCA4 = continuous state/risk information;
- frozen stability model = probability that the current Core label changes within a future horizon;
- stability's strongest demonstrated incremental information is short/intermediate-horizon transition occurrence, not destination or directional return;
- generic PCA4 inverse-variance sizing already failed economically in a separate simplified experiment.

Accordingly this experiment uses transition instability only as a veto/defer condition on new exposure increases. It does not use PCA4 directly as a sizing rule.

## Canonical Core control

The control must preserve the selected runtime allocation:

- BTC_4H_trend 0.15
- ETH_1H_trend 0.10
- ETH_4H_trend 0.10
- SPY_1D_equity 0.175
- QQQ_1D_equity 0.275
- GLD_1D_gold 0.20

Explicit zero-weight sleeves remain zero and are not experimental sleeves: BTC_1H_trend, BTC_1H_hedge, ETH_1H_hedge.

The control preserves authentic BaselineRegimeEngine, trend_following_v11 and its v9/v8 lineage, cross-asset BTC/SPY state injection, parabolic caps, cash-yield handling, execution semantics, costs, rebalance threshold, fold construction, and allocation.

The known historical equity de-risk backtest/live parity caveat remains disclosed and is not repaired here.

## Eligible sleeves

Only BTC_4H_trend, ETH_1H_trend, and ETH_4H_trend are eligible. No RRE model is extrapolated to SPY, QQQ, or GLD.

## Eligible intervention event

An event is eligible only when all are true:

1. authentic Core strategy output is ENTER_LONG;
2. canonical desired exposure is strictly greater than current pre-decision exposure;
3. it would otherwise represent an exposure increase under unchanged Core semantics;
4. a causal frozen-model instability score is available and passes chronology/validity checks.

This includes initial entries and existing add-on intents. HOLD, FLAT, EXIT_LONG, reductions, and unchanged targets are never modified.

## Frozen instability model

Use the already-frozen **7-calendar-day transition model** from CORE_REGIME_STABILITY_20260917.md: Core + PCA4 + trajectory + episode age, with identical features, PCA/trajectory construction, logistic regression regularization, preprocessing, and training-only chronology.

No architecture refit, hyperparameter search, feature selection, probability recalibration, or alternate horizon is allowed.

For each annual evaluation fold, train only on observations whose labels are fully matured before cutoff. The event score must use only information available at that event. Missing/non-finite/unavailable scores fail closed to canonical Core behavior: no deferral.

## Frozen threshold derivation

The cutoff is derived **without returns, P&L, Sharpe, drawdown, trade outcomes, or any economic variable**.

For each annual fold, compute the instability-score distribution on eligible matured training predictions only. The cutoff is the **training-distribution 80th percentile** of predicted 7-day transition probability.

An eligible increase is deferred iff p_transition_7d >= training_q80.

Q80 is frozen as a sparse upper-instability-quintile definition using only the transition model's own probability distribution. It is not selected from economic outcomes.

There is one primary cutoff only. No q70/q75/q85/q90 sweep, alternate probability threshold, per-asset/timeframe/Core-label threshold, or post-result threshold adjustment is permitted.

If the matured training prediction set is insufficient to compute q80 deterministically, the fold/score fails closed to canonical behavior and the reason is recorded.

## Frozen intervention semantics

At an eligible event above cutoff:

- replace only that event's exposure-increase target with current pre-decision exposure;
- create no pending order, remembered signal, synthetic target, timer, cooldown override, or forced future entry;
- on the next native closed bar, run authentic Core normally using experimental-arm actual exposure and then-current causal RRE score;
- if Core again requests an increase and instability remains above q80, defer again;
- once Core requests an increase while instability is below q80, allow authentic Core target unchanged;
- all authentic exits/reductions execute immediately and unchanged.

Thus deferral is a repeated bar-by-bar veto while the frozen condition holds, not a guaranteed one-bar-later fill. RRE can never increase exposure above authentic Core.

## Paired replay requirement

Control and experimental arms consume the same governed source data, fold boundaries, Core code, labels, strategy code, cross-asset state, allocation, cost model, and execution model. The only permitted difference is the deterministic deferral above on eligible crypto exposure-increase intents.

Event audit must include timestamp, fold, sleeve, Core label, canonical action, pre-decision exposure, canonical target, causal instability probability, training q80, eligibility, deferred flag, experimental target, and reason code.

## Development/validation handling

History used here has already been inspected in prior Itera work; no period is globally pristine OOS. Annual walk-forward folds preserve causal chronology. Any later untouched confirmation requires a genuinely untouched period/dataset and separate authorization.

## Primary economic endpoint

Primary endpoint: **paired net Sharpe difference, experimental minus canonical Core control**, using canonical fund-level returns under identical costs.

## Secondary diagnostics

Report CAGR/cumulative return, maximum drawdown, Calmar, turnover/cost, deferred-event counts/fractions, initial-entry versus add-on deferrals, exposure-time difference, asset/timeframe contribution, annual paired results, behavior by Core label, and descriptive 1d/3d/7d post-event returns.

## Frozen advance gate

Advance only if all hold:

1. mean paired net Sharpe difference is positive;
2. experimental net Sharpe exceeds control in at least 16 of 24 asset/timeframe/year sleeve-level diagnostic folds where defined;
3. each eligible sleeve has positive mean paired Sharpe difference across its defined annual folds;
4. fund-level maximum drawdown is not worse by more than 10% relative to control drawdown magnitude;
5. mean paired Sharpe difference stays positive under frozen base-cost and existing higher-cost stress cases;
6. at least 20 eligible exposure-increase events are deferred in aggregate and at least 3 per eligible sleeve.

If fewer than 24 sleeve/year diagnostics are defined, requirement 2 becomes ceiling(two-thirds of defined diagnostics), reported explicitly.

Failure of any gate rejects this exact mechanism. No threshold rescue, sleeve deletion, horizon swap, Core-label subset, or retuning is allowed after results.

## Engineering guardrails

Fail closed if canonical control qualification is not PASS; selected allocation differs; governed source hashes differ; Core strategy/regime identity drifts; instability model identity drifts; training maturity is violated; future information enters an RRE score; experimental target exceeds canonical target; a non-eligible sleeve/action is modified; or independent deterministic replays differ.

No production/paper/live files may be edited.

## Interpretation boundaries

A PASS supports only: a predeclared causal Core-instability veto on authentic Core v1 crypto exposure increases improved the historical paired economic profile under this frozen replay design. It does not authorize deployment or replacement of Core.

A FAIL rejects this entry/add-on-deferral mechanism, not the established observation-only PCA4 risk-state or stability transition-risk findings.

## Next authorized engineering step

Implementation may build an offline-only deterministic replay adapter and tests for this exact frozen intervention. It must not compute or expose economic results until synthetic causality, threshold, target-monotonicity, non-eligible-action, source/config, and deterministic-replay tests pass.
