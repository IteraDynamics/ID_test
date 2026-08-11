# Jump Risk Engine v0 — Final Research Report

**Branch:** `research/jump-risk-portfolio-v0`  
**Research lifecycle:** Complete  
**Runtime integration allowed:** No  
**Promotion status:** Approved as a paper-trading candidate, pending timing audit and operational implementation

## Executive Summary

Jump Risk Engine v0 tests whether observable market state can rank the probability of future discontinuous price moves and whether those probabilities can improve the canonical Core v1 portfolio.

The predictive research produced robust BTC candidates for immediate any-jump risk, immediate downside-jump risk, medium-horizon upside-jump risk, and extended-horizon upside-jump risk. Locked BTC-selected candidates transferred to ETH without retuning. A broad daily ETF audit produced only WARN candidates and was not promoted.

Portfolio integration produced a clear asymmetric result:

- Defensive downside governors reduced portfolio quality and were rejected.
- Aligned-upside participation improved Core when Jump Risk increased existing BTC and ETH trend participation only while Core was already directionally aligned.

The leading implementation, `btc_eth_aligned_upside`, improved the canonical walk-forward baseline after a one-bar implementation lag and 6 bps incremental overlay cost.

| Metric | Canonical Core | Jump Risk candidate | Delta |
|---|---:|---:|---:|
| CAGR | 19.93% | 21.02% | +1.09 pp |
| Sharpe | 1.318 | 1.400 | +0.082 |
| Calmar | 1.208 | 1.347 | +0.139 |
| Maximum drawdown | -16.50% | -15.60% | +0.90 pp |

The candidate improved five of six OOS calendar years. A nearby-parameter audit reported 18 of 18 predeclared nearby configurations passing the portfolio gates.

## Research Question

Can market-state features rank future jump risk, and can those rankings be mapped into portfolio actions that improve Core v1 without allowing Jump Risk to create standalone direction?

## Data and Scope

Primary research used canonical hourly BTC and ETH OHLCV data from 2018 through 2025, with expanding annual walk-forward testing beginning in 2020.

The canonical portfolio baseline is:

`candidate_btc1h_hedges_to_btc4h_gld_qqq`

Active sleeves:

- BTC 4H trend — 15.0%
- ETH 1H trend — 10.0%
- ETH 4H trend — 10.0%
- SPY — 17.5%
- QQQ — 27.5%
- GLD — 20.0%

All portfolio trials use the reconciled 52,374-row canonical sleeve matrix whose row-wise sum matches the canonical Core NAV.

## Label Definition

A future window is labeled as a jump when its maximum absolute move exceeds both:

1. an absolute-return floor, and
2. a rolling-volatility multiple scaled by the forecast horizon.

Separate targets were evaluated for:

- any jump,
- downside jump,
- upside jump.

Features at timestamp `t` use only information available at or before `t`; labels use bars strictly after `t`.

## Feature Families

The research included price-derived state features covering:

- returns and momentum,
- realized volatility and volatility-of-volatility,
- compression and squeeze state,
- range and breakout proximity,
- market structure,
- volume state,
- market-energy features,
- calendar controls.

Feature-family ablation was used to select candidate-specific feature sets rather than assuming one universal feature family.

## Locked Predictive Candidates

| Lane | Horizon | Model | Feature family | BTC ROC AUC | BTC Top-5 lift | ETH transfer ROC AUC | ETH transfer lift |
|---|---:|---|---|---:|---:|---:|---:|
| Immediate any jump | 2h | GBM | Energy | 0.8036 | 7.30x | 0.7628 | 5.76x |
| Immediate down jump | 2h | Logistic | Structure | 0.7641 | 7.57x | 0.7418 | 4.83x |
| Medium upside | 18h | GBM | Energy | 0.7054 | 4.90x | 0.6828 | 3.46x |
| Extended upside | 120h | Logistic | Structure | 0.7692 | 5.30x | 0.7115 | 2.57x |

These are ranking results for rare-event labels. They do not imply calibrated certainty or live profitability.

## Robustness and Transfer

The leading BTC candidates survived nearby jump-threshold definitions. Exact BTC-selected models were then applied to ETH without retuning and retained meaningful ranking power.

A daily SPY/QQQ/GLD generalization audit reviewed 180 configurations:

- 150 INVALID
- 30 WARN
- 0 VALID

Daily ETF candidates were therefore excluded from the primary portfolio trial.

## Portfolio Integration

The portfolio trial froze the predictive models and tested economic mappings against canonical Core.

### Rejected mappings

- `btc_down_governor`
- `btc_eth_down_governor`
- `combined_asymmetric`

Reducing established trend exposure before predicted downside jumps degraded Sharpe, Calmar, and drawdown behavior. The model's downside ranking skill did not translate into a useful exposure-suppression policy.

### Passing mappings

| Overlay | CAGR | Sharpe | Calmar | Max DD | Gate |
|---|---:|---:|---:|---:|---|
| Core unchanged | 19.93% | 1.318 | 1.208 | -16.50% | BASELINE |
| BTC aligned upside | 20.33% | 1.348 | 1.247 | -16.31% | PASS |
| BTC + ETH aligned upside | 21.02% | 1.400 | 1.347 | -15.60% | PASS |

The leading mapping permits a limited 1.15x scale only when:

- Core already has positive aligned trend behavior,
- medium or extended upside-jump probability exceeds a training-distribution threshold,
- the signal is lagged one bar before affecting portfolio P&L.

Jump Risk never creates standalone directional exposure.

## Annual Consistency

The leading candidate improved Core in five of six OOS years:

| Year | Core | Candidate | Difference |
|---:|---:|---:|---:|
| 2020 | 41.45% | 43.79% | +2.34 pp |
| 2021 | 28.42% | 29.49% | +1.06 pp |
| 2022 | -8.34% | -7.38% | +0.96 pp |
| 2023 | 27.19% | 29.53% | +2.34 pp |
| 2024 | 26.43% | 27.30% | +0.88 pp |
| 2025 | 9.78% | 9.22% | -0.56 pp |

The improvement is not attributable to a single calendar year.

## Candidate Audit

The locked center used:

- risk quantile: 0.95
- boost scale: 1.15x
- incremental cost: 6 bps
- effective probability lag: one bar

Results:

- Nearby promotion-gate pass rate: 18/18
- BTC active fraction: approximately 6.5%
- ETH active fraction: approximately 8.8%
- BTC gross incremental P&L: approximately $10,040
- ETH gross incremental P&L: approximately $16,502

Both assets contributed positively, with ETH contributing more.

The parameter surface was tested across risk quantiles 0.90–0.975, boost scales 1.05–1.20, and costs up to 20 bps. Performance degraded coherently as costs rose rather than collapsing abruptly.

## Critical Timing Finding

The economic benefit is short-lived.

| Effective probability lag | CAGR | Sharpe | Calmar | Max DD |
|---:|---:|---:|---:|---:|
| 1 bar | 21.02% | 1.400 | 1.347 | -15.60% |
| 2 bars | 19.95% | 1.305 | 1.201 | -16.61% |
| 3 bars | 19.78% | 1.291 | 1.184 | -16.70% |
| 7 bars | 19.61% | 1.270 | 1.168 | -16.79% |
| 13 bars | 19.69% | 1.275 | 1.156 | -17.04% |
| 25 bars | 19.75% | 1.288 | 1.171 | -16.87% |

This does not establish leakage, but it makes exact timestamp availability and execution sequencing a mandatory precondition for paper integration.

## Lessons Learned

1. Predictive skill does not guarantee economic value.
2. Suppressing established trend exposure was harmful even when downside-jump ranking was strong.
3. The useful mapping was asymmetric: Core determines direction; Jump Risk determines when to lean modestly into an already-valid position.
4. Cross-asset transfer materially strengthens the research case.
5. The edge appears transient and must be operationally achievable within one hourly decision cycle.

## Final Research Decision

| Dimension | Decision |
|---|---|
| Predictive engine | VALIDATED |
| BTC-to-ETH transfer | VALIDATED |
| Daily ETF generalization | NOT VALIDATED; WARN only |
| Downside exposure governors | REJECTED |
| BTC aligned-upside mapping | PORTFOLIO PASS |
| BTC + ETH aligned-upside mapping | LEADING PORTFOLIO CANDIDATE |
| Research lifecycle | COMPLETE |
| Paper-trading promotion | APPROVED SUBJECT TO TIMING AUDIT |
| Production/runtime promotion | NOT APPROVED |

The research phase is closed. Subsequent work belongs in a separate engineering branch and must not retune the frozen research parameters.

---

## Addendum — Retirement, 2026-08-11

The research phase closed as recorded above. The engineering phase has now also closed, with a
negative operational result.

Finding 5 of this document states: *"The edge appears transient and must be operationally
achievable within one hourly decision cycle."* That condition was tested and is not met.

| Stage | Date | Outcome |
|---|---|---|
| Timing provenance audit | 2026-08-10 | PASS — no lookahead; canary verified the detector fires |
| Live runtime cadence audit | 2026-08-10 | ~1.5-1.7 effective bars; 0 of 808 cycles within assumption |
| Lag sensitivity re-test | 2026-08-11 | 98% of the edge expires by bar 2; REJECT at achievable lag |

**Paper-trading promotion is WITHDRAWN. Jump Risk Engine v0 is RETIRED.**

Nothing in the predictive research is retracted. The signal was validated, transferred
cross-asset untuned, and was independently confirmed free of lookahead by an audit built
specifically to be capable of failing. The mapping was economically positive at the lag the
research assumed. It is not reachable at the lag the infrastructure achieves.

Governing record: `docs/engineering/CORE_V1_JUMP_RISK_PAPER_CHARTER.md`.
