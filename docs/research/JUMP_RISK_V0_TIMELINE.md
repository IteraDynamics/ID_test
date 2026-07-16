# Jump Risk Engine v0 — Research Timeline

**Lifecycle:** Complete  
**Final research branch:** `research/jump-risk-portfolio-v0`

## Phase 1 — Research hypothesis

Defined the primary question: whether observable market state can rank future discontinuous price moves without claiming exact timing, direction, or magnitude certainty.

Established separate labels for:

- any jump,
- downside jump,
- upside jump.

## Phase 2 — Discovery and feature expansion

Built the research-only Jump Risk lab with strictly forward labels and state features derived only from information available at or before each timestamp.

Expanded the feature space across:

- return and momentum state,
- realized volatility,
- volatility acceleration,
- compression and squeeze conditions,
- range position and breakout proximity,
- volume state,
- market-energy features,
- market structure.

## Phase 3 — Ablation and targeted horizon research

Compared feature families and model classes rather than assuming one model or one universal feature set.

Targeted horizon refinement identified four leading BTC candidates:

- immediate any jump, 2h,
- immediate downside jump, 2h,
- medium upside jump, 18h,
- extended upside jump, 120h.

## Phase 4 — Candidate locking and robustness

Locked model class, horizon, target, and feature family before portfolio testing.

Tested nearby jump-threshold definitions. Leading candidates retained meaningful ranking power rather than depending on one exact label threshold.

## Phase 5 — Cross-asset transfer

Applied the exact BTC-selected candidates to ETH without retuning.

All four candidates retained useful ranking power, providing the strongest evidence that the immediate and upside signals were not purely BTC-specific.

## Phase 6 — Daily-asset generalization audit

Extended the research to SPY, QQQ, and GLD using daily-native configurations.

Formal audit result:

- 180 configurations reviewed,
- 150 INVALID,
- 30 WARN,
- 0 VALID.

Daily ETF candidates were retained only as research leads and excluded from portfolio promotion.

## Phase 7 — Portfolio integration charter

Created `docs/research/JUMP_RISK_PORTFOLIO_V0_CHARTER.md`.

Predeclared:

- frozen canonical Core baseline,
- frozen predictive models,
- strict expanding walk-forward probabilities,
- one-bar implementation lag,
- training-distribution thresholds,
- incremental turnover costs,
- explicit promotion gates,
- no standalone direction from Jump Risk.

## Phase 8 — Canonical Core sleeve integration

Reused the reconciled canonical Core sleeve matrix with 52,374 OOS rows.

Tested:

- BTC downside governor,
- BTC + ETH downside governor,
- BTC aligned-upside participation,
- BTC + ETH aligned-upside participation,
- combined asymmetric governor.

Outcome:

- downside governors rejected,
- aligned-upside variants passed,
- BTC + ETH aligned upside became the leading candidate.

## Phase 9 — Candidate audit

Audited the leading candidate across:

- risk quantiles 0.90, 0.925, 0.95, 0.975,
- boost scales 1.05x, 1.10x, 1.15x, 1.20x,
- incremental costs of 0, 6, 12, and 20 bps,
- effective probability lags of 1, 2, 3, 7, 13, and 25 bars.

Key results:

- locked center: CAGR 21.02%, Sharpe 1.400, Calmar 1.347, max drawdown -15.60%,
- nearby pass rate: 18/18,
- BTC and ETH both contributed positively,
- action frequency remained sparse,
- cost response was coherent,
- benefit decayed sharply after the first implementation bar.

## Phase 10 — Research closure

Final decision:

- predictive engine validated,
- BTC-to-ETH transfer validated,
- downside-governor mappings rejected,
- aligned-upside portfolio mapping validated,
- paper-trading candidacy approved subject to exact timing verification,
- runtime production promotion withheld.

The research lifecycle is complete. Operational integration proceeds separately on `feature/core-v1-jump-risk-paper` with frozen research parameters.