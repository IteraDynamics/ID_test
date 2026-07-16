# Jump Risk Portfolio Integration v0 — Research Charter

**Branch:** `research/jump-risk-portfolio-v0`  
**Status:** Portfolio Trial  
**Runtime integration allowed:** No

## Objective

Determine whether the validated Jump Risk Engine v0 candidates improve the canonical Core v1 portfolio after strictly out-of-sample prediction generation, implementation lag, and conservative incremental trading costs.

The research question is economic, not merely predictive:

> Can jump-risk probabilities be mapped into portfolio actions that improve Core v1's risk-adjusted performance without materially sacrificing return?

## Frozen baseline

The portfolio baseline is the canonical Core v1 scenario:

`candidate_btc1h_hedges_to_btc4h_gld_qqq`

Canonical walk-forward reference:

- Initial capital: $100,000
- Final NAV: $297,331.76
- CAGR: 19.93%
- Sharpe: 1.318
- Calmar: 1.208
- Maximum drawdown: -16.50%
- OOS rows: 52,374

The canonical sleeve matrix must reconcile to the canonical fund NAV before any trial is accepted.

## Frozen Jump Risk evidence

Initial portfolio work will use only candidates already supported by the completed Jump Risk research program. No horizon, feature-family, or label retuning is allowed inside the portfolio trial.

Primary crypto candidates:

| Lane | Horizon | Model | Features | BTC ROC AUC | BTC Top-5 Lift | ETH transfer ROC AUC | ETH transfer lift |
|---|---:|---|---|---:|---:|---:|---:|
| Immediate any jump | 2h | GBM | Energy | 0.8036 | 7.30x | 0.7628 | 5.76x |
| Immediate down jump | 2h | Logistic | Structure | 0.7641 | 7.57x | 0.7418 | 4.83x |
| Medium upside | 18h | GBM | Energy | 0.7054 | 4.90x | 0.6828 | 3.46x |
| Extended upside | 120h | Logistic | Structure | 0.7692 | 5.30x | 0.7115 | 2.57x |

Daily ETF WARN candidates are excluded from the primary v0 portfolio trial.

## Predeclared integration hypotheses

### JR-PI-001 — Down-jump exposure governor

Reduce only existing directional crypto exposure when immediate downside-jump risk enters a high training-distribution quantile.

Purpose: reduce drawdown and improve Calmar without broadly suppressing normal trend exposure.

### JR-PI-002 — Hedge activation

Activate otherwise inactive BTC/ETH hedge sleeves only during elevated immediate downside-jump risk.

Purpose: test a targeted defensive use rather than scaling down profitable Core sleeves.

### JR-PI-003 — Entry delay

Delay a new or increased crypto trend allocation for one bar when immediate downside-jump risk is elevated.

Purpose: avoid adverse entry timing while preserving established positions.

### JR-PI-004 — Upside participation filter

Permit limited additional participation only when medium or extended upside-jump probability is high and Core is already directionally aligned.

Purpose: test conditional upside acceleration without allowing the jump model to create standalone direction.

### JR-PI-005 — Combined asymmetric governor

Use immediate downside risk defensively and medium/extended upside risk only as a secondary confirmation signal.

Purpose: test whether asymmetric mappings are superior to symmetric continuous scaling.

## Guardrails

- Core remains the sole directional strategy.
- Jump Risk may condition exposure, hedging, entry timing, or limited aligned participation only.
- All probabilities must be generated with expanding walk-forward training.
- Predictions must be lagged before affecting the governed return interval.
- Thresholds must come from training distributions only.
- Incremental turnover costs must be charged.
- No live or paper-runtime files may be modified during v0.
- No portfolio implementation may retune the frozen predictive models.

## Promotion criteria

Relative to canonical Core, an implementation must satisfy all default promotion gates:

- Sharpe delta greater than zero
- Calmar delta greater than zero
- Maximum-drawdown delta nonnegative
- CAGR degradation no worse than 0.50 percentage points

Additionally, the result must:

- Avoid dependence on one calendar year
- Show stable benefit across reasonable nearby action thresholds
- Preserve canonical baseline reproduction
- Provide exposure, turnover, cost, and action-frequency diagnostics

## Required outputs

Each run must write:

- Manifest with frozen model definitions
- Strictly OOS probability files
- Canonical sleeve matrix used
- Portfolio NAV and drawdown curves
- Scorecard against Core
- Annual-return comparison
- Action-frequency and cost diagnostics
- Promotion decision
- Reproducibility hashes or fingerprints

## Decision policy

Possible outcomes:

- **PASS:** At least one implementation satisfies all promotion gates and robustness checks.
- **RESEARCH FOLLOW-UP:** No implementation passes, but a narrowly defined economic mapping warrants a separately chartered study.
- **COMPLETED — NOT PROMOTED:** Predictive Jump Risk evidence remains valid, but no tested portfolio implementation improves Core.

No result changes Core v1 automatically. A passing portfolio trial only creates a runtime-promotion candidate for separate implementation and paper-observation review.
