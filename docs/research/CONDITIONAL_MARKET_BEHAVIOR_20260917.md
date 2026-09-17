# Conditional Market Behavior — Frozen Hypothesis Test — 2026-09-17

## Status
Observation-only research. No production, strategy, portfolio, runtime, threshold, order, NAV, exposure, execution, or Core-label change is authorized.

## Motivation
Prior observation-only work established that (1) PCA4 continuous state materially improves future risk characterization relative to Core alone and (2) a causal continuous instability probability materially predicts whether the current Core label will change. Before any P&L/backtest experiment, test whether these continuous quantities stratify economically relevant future market behavior *within the same current Core label*.

## Primary hypothesis
Conditional on the current Core label, causal continuous state and/or instability contain stable out-of-sample information about the subsequent market distribution that Core alone discards.

## Frozen information sets
- Core label only.
- Core + PCA4 continuous state.
- Core + continuous instability probability.
- Core + PCA4 + continuous instability probability.

Instability is generated causally from the already-frozen Core stability model; no instability cutoff is selected. The primary instability input is the frozen 7-day transition probability because it represents intermediate-horizon regime stability and was specified before this experiment. Other previously frozen horizons may be reported only as sensitivity diagnostics, never selected after outcomes are observed.

## Frozen forward horizons
1, 3, 5, 7, 14 calendar days.

## Frozen future-market outcomes
For each matured forward window:
- cumulative log return;
- realized log variance;
- downside semivariance;
- maximum adverse excursion from the starting price;
- maximum favorable excursion from the starting price;
- absolute cumulative return;
- path efficiency = absolute endpoint log return / sum absolute daily log returns, fail-closed when denominator is zero;
- sign persistence = fraction of non-zero daily returns having the same sign as the window endpoint return, missing when endpoint return is zero or no non-zero daily returns exist.

No trading rule, transaction cost, position, leverage, sizing, entry, exit, stop, target, or P&L is computed.

## Evaluation design
- BTC and ETH;
- 1H and 4H source inputs;
- UTC-midnight sampled panels;
- yearly 2020–2025 walk-forward evaluation;
- all transforms and instability models fit on pre-cutoff matured training data only;
- deterministic/replay-safe/fail-closed;
- evaluation observations retain the authentic current Core label.

## Primary tests
Within each current Core label and fold:
1. Rank observations by causal 7-day instability into fixed within-training-distribution quintile bins, with cut points learned on training data only.
2. Report each future outcome by instability bin without selecting a favorable cutoff.
3. Measure monotonic association between continuous instability and each future outcome using Spearman correlation.
4. Measure incremental predictive value beyond Core using fixed regularized linear models for continuous outcomes: Core-only; Core+PCA4; Core+instability; Core+PCA4+instability. Report out-of-sample squared-error skill relative to Core-only.
5. Report cross-fold sign consistency and results by Core label, asset, timeframe, and year.

## Interpretation discipline
Return-related outcomes are descriptive/economic-behavior diagnostics, not evidence of tradable alpha by themselves. Risk/path outcomes may establish useful conditional structure without directional return predictability.

## Advance rule
Advance toward a separately frozen economic-use/backtest hypothesis only if continuous information demonstrates material, stable OOS stratification of at least one economically relevant future-distribution property beyond Core alone across a substantial majority of eligible folds, without dependence on one asset/timeframe/year or a single sparse Core label. Directional-return predictability is not required.

If the effect is limited to predicting the Core label change itself and does not stratify subsequent market behavior, stop before trading backtests.

## Guardrail
Any subsequent trading comparison requires a new frozen charter specifying the fixed strategy/family, exact information substitution, chronology, costs, metrics, development/validation separation, and advance criteria before P&L is observed.