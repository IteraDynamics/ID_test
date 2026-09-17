# Core vs PCA4 Controlled Economic Comparison — Frozen Charter

**Date:** 2026-09-17  
**Status:** FROZEN — research-only economic experiment. No production/runtime/portfolio authorization.

## Question
Holding trading logic and all economic assumptions fixed, does causal PCA4 market-state information add OOS economic value beyond the authentic current Core regime label?

## Scientific rationale
Prior observation-only work established that PCA4 materially improves characterization of future realized variance and movement magnitude beyond Core, while the separate instability probability primarily predicts Core-label transition and adds little robust future-distribution information after PCA4. This experiment tests economic usefulness of the PCA4 information only; instability is excluded from trading decisions.

## Hard guardrails
- Research/backtest only. No production, paper-trading, runtime, strategy, portfolio, order, NAV, exposure, execution, threshold, or Core-label change is authorized.
- Core implementation and labels remain untouched.
- PCA transforms are fit on pre-cutoff training data only.
- No parameter, threshold, rule, cost assumption, asset, horizon, or evaluation metric may be selected after observing economic results.
- Core and Core+PCA4 arms must share identical timestamps, prices, costs, execution convention, signal family, gross-exposure ceiling, and missing-data treatment. The only permitted difference is information available to the regime-conditioning component.
- Missing/unavailable PCA4 fails closed to the Core-only behavior for that timestamp; it never receives an imputed favorable state.
- Stability/transition probability is diagnostic only and is not an input to either trading arm.

## Frozen universe and chronology
- Assets: BTC and ETH.
- Source state timeframes: 1H and 4H, evaluated on the existing UTC-midnight research panel.
- Annual walk-forward evaluation folds: 2020, 2021, 2022, 2023, 2024, 2025.
- All state transforms/decoders for an evaluation year use only causally available pre-cutoff observations with matured labels.
- No random train/test shuffling.

## Frozen economic-use mechanism
This experiment is deliberately narrow. It does **not** search for directional alpha in PCA4.

A single symmetric directional signal is used in both arms: the authentic Core trend direction only (`TREND_UP` = +1, `TREND_DOWN` = -1, all other Core labels = 0). PCA4 is permitted only to estimate conditional forward risk and therefore scale the magnitude of that already-fixed direction; it cannot change the sign or create a position when Core direction is zero.

### Core-only arm
For each evaluation observation, estimate the forward 7-calendar-day realized log-variance expectation from the matured pre-cutoff training sample using current Core label only, with the same fixed Ridge decoder used by the research family. Convert predicted variance to a relative risk multiplier using the training-period unconditional predicted-risk reference. The multiplier is clipped to the frozen symmetric range `[0.5, 1.5]` solely as an experiment safety bound. Target research exposure is `Core direction × risk multiplier`.

### Core+PCA4 arm
Identical construction except the forward 7-calendar-day realized log-variance decoder receives current Core label plus causal PCA1–PCA4 coordinates. Same Ridge alpha, reference construction, clipping range, direction, timestamps, and all economic assumptions.

The risk multiplier is inverse-volatility-like: `sqrt(reference_variance / predicted_variance)` after converting log variance back to variance. Non-finite or non-positive risk estimates fail closed to multiplier 1.0. The reference is derived from training data only.

This is an information-substitution experiment, not an optimized volatility-targeting strategy. No annualized volatility target is introduced.

## Frozen return/execution convention
- Research position decided at the UTC-midnight state timestamp using only information available at that timestamp.
- Position applies to the subsequent one-calendar-day close-to-close return, matching the daily research panel cadence.
- Rebalanced once per panel observation.
- No leverage beyond the frozen absolute multiplier ceiling 1.5.
- Turnover is absolute change in target exposure.
- Primary comparison is gross to isolate information value.
- Cost sensitivity is reported mechanically at fixed round-trip-equivalent linear turnover charges of 0, 5, 10, and 20 bps per unit turnover. These are sensitivities, not claims about executable venue costs, and none may be selected as the preferred result after observation.

## Frozen outputs
For every asset × source timeframe × evaluation year × arm:
- observations
- cumulative return
- CAGR-equivalent annualized geometric return where defined
- annualized volatility
- Sharpe with zero risk-free rate
- maximum drawdown
- Calmar where defined
- mean absolute exposure
- turnover
- fraction of observations invested
- net results at each frozen cost sensitivity

Paired fold comparisons must additionally report Core+PCA4 minus Core for cumulative/net return, Sharpe, max drawdown, and Calmar, plus win counts across eligible folds.

## Primary endpoint and advance rule
Primary endpoint: paired OOS **net Sharpe difference at 10 bps turnover cost** for Core+PCA4 versus Core.

The hypothesis advances only if all are true:
1. Core+PCA4 has positive paired net-Sharpe difference in at least 16 of 24 eligible asset × timeframe × year folds;
2. mean paired net-Sharpe difference is positive;
3. the result is not dependent on one asset or one source timeframe: each asset and each timeframe must have positive mean paired net-Sharpe difference;
4. Core+PCA4 does not worsen mean maximum drawdown by more than 10% relative on the paired 10-bps results;
5. the sign of mean paired Sharpe difference remains positive at 0, 5, 10, and 20 bps.

Failure of any primary rule means this specific economic-use hypothesis does not advance. Secondary metrics cannot rescue a failed primary gate.

## Interpretation discipline
A pass establishes only that the frozen PCA4 risk-conditioning mechanism merits a separately governed validation/economic follow-up. It does not authorize production use, capital, paper trading, Core modification, a confidence field, or a new strategy.

A failure does not invalidate PCA4 as a market-state/risk representation; it only rejects this frozen economic-use mechanism.
