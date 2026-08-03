# Campaign #51 — Source and Variable Feasibility Inventory

## Status

**PLANNING EVIDENCE ONLY — NO OUTCOMES, MODEL FITTING, RANKING, HOLDOUT ANALYSIS, OR RUNTIME CHANGE AUTHORIZED.**

This inventory implements the planning-only authorization in `docs/ITERA_CAMPAIGN_BOARD.md` for Campaign #51. It documents existing variables, source lineage, leakage constraints, and a narrow recommended family without inspecting Campaign #51 forward outcomes.

## Research objective

Campaign #51 asks whether BTC movement states already supported by Campaign #48 alter the directional value of a separately defined directional variable.

The intended statistical object is an interaction or equivalent conditional-effect estimate. Volatility and drawdown are not treated as unconditional direction predictors.

## Governed source lineage

The strongest common source is the Campaign #48 hourly BTC source:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- data rows: `70,069`
- first timestamp: `2018-01-01 00:00:00`
- last timestamp: `2025-12-31 00:00:00`
- ordered schema: `timestamp,open,high,low,close,volume`
- governed missing timestamp inventory: the exact 36 timestamps frozen by Campaign #48 source-cadence amendment `d9fc7e7103a5033a9dbbe06b7abf93aea27d863b`

No interpolation, forward fill, backward fill, resampling, nearest-row matching, synthetic bars, timestamp shifting, or source repair is permitted.

The Campaign #48 implementation is the formula authority for the existing variables:

- `research/ml/validation/simple_btc_price_state_predictive_baselines.py`
- specification freeze: `e8777df3442d093fd84fb92c25d13aadc2bfe1ed`
- Campaign #48 closure: `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

## Existing directional variables

All variables below use only closes at or before anchor time `t` and are independently defined before Campaign #51 outcomes.

### D1 — 24-hour signed return

`return_trailing_24h[t] = log(close[t] / close[t-24h])`

Properties:

- existing Campaign #48 predictor;
- interpretable as short-horizon signed momentum/reversal state;
- exact 24-hour timestamp window required;
- continuous, avoiding arbitrary sign or quantile thresholds during planning.

### D2 — 72-hour signed return

`return_trailing_72h[t] = log(close[t] / close[t-72h])`

Properties:

- existing Campaign #48 predictor;
- intermediate-horizon signed momentum state;
- mechanically valid but highly nested with D1 and D3;
- not recommended for the initial narrow family because it expands multiplicity while adding a third closely related directional window.

### D3 — 168-hour signed return

`return_trailing_168h[t] = log(close[t] / close[t-168h])`

Properties:

- existing Campaign #48 predictor;
- interpretable as one-week signed trend state;
- exact 168-hour timestamp window required;
- continuous and threshold-free.

### Additional available directional proxies

Campaign #48 also contains:

- `distance_from_mean_trailing_168h = close[t] / mean(close[t-168h:t]) - 1`
- `range_position_trailing_168h = (close[t] - min(close[t-168h:t])) / (max(close[t-168h:t]) - min(close[t-168h:t]))`

These are directionally interpretable price-location variables, but they overlap economically and mathematically with one-week return and drawdown. They are excluded from the initial recommendation to control duplication and candidate count.

Existing runtime intents, exposure states, classifier outputs, and strategy decisions are not recommended as Campaign #51 predictors at this stage. They may contain threshold, training, governance, or implementation dependencies that would complicate leakage and independence review. Campaign #51 can answer its first question using transparent source-derived variables instead.

## Campaign #48-supported movement-state variables

### S1 — 24-hour realized volatility

`realized_volatility_trailing_24h[t] = sqrt(sum(log_return_j^2))`

where the sum covers the 24 exact hourly log returns ending at `t`.

Campaign #48 found this variable positively associated with future absolute return and future realized volatility at 24, 72, and 168 hours.

### S2 — 168-hour realized volatility

`realized_volatility_trailing_168h[t] = sqrt(sum(log_return_j^2))`

where the sum covers the 168 exact hourly log returns ending at `t`.

Campaign #48 found this variable positively associated with future absolute return and future realized volatility at 24, 72, and 168 hours.

### S3 — drawdown from the 168-hour high

`drawdown_from_high_trailing_168h[t] = close[t] / max(close[t-168h:t]) - 1`

The value is non-positive. More negative values represent deeper drawdown.

Campaign #48 found deeper drawdown associated with higher future realized volatility at 24, 72, and 168 hours.

## Duplication and dependency analysis

The three movement states are not independent:

- S1 and S2 are nested realized-volatility measures;
- S2 and S3 may both become extreme during stressed markets;
- D3 and S3 use the same 168-hour close window;
- D1, D2, and D3 are nested signed-return windows.

Testing every combination would create a large, redundant family and weaken interpretability. The initial family should therefore use two directional windows and two movement-state variables.

## Recommended narrow family

Recommended directional variables:

- D1: `return_trailing_24h`
- D3: `return_trailing_168h`

Recommended conditioning variables:

- S1: `realized_volatility_trailing_24h`
- S3: `drawdown_from_high_trailing_168h`

Recommended forward directional-return horizons for later specification:

- 24 hours
- 72 hours
- 168 hours

This produces exactly:

`2 directional variables × 2 conditioning variables × 3 horizons = 12 interaction candidates`

The family fits the planning charter's preferred 6–12 range.

### Why exclude 168-hour realized volatility initially

S2 is a supported and economically valid movement state, but it is nested with S1 and uses the same maximum window as D3 and S3. Excluding it from the initial family reduces redundancy and keeps the candidate family at 12. It remains a documented alternative, not a result-driven fallback.

### Why use continuous interactions

A later frozen specification should prefer continuous, stage-standardized main effects and an interaction term rather than high/low state thresholds. This avoids threshold optimization and preserves information.

A possible later model form is:

`future_directional_return = beta0 + betaD*D + betaS*S + betaI*(D*S) + error`

The Campaign #51 candidate effect would be `betaI`, subject to a separately frozen estimator, support rule, multiplicity correction, sign/interpretation rule, and stage-separation design.

This inventory does not authorize that model or calculate any coefficient.

## Proposed chronological feasibility frame

For calendar-only feasibility review, the timestamp preflight uses these proposed, not-yet-frozen intervals:

- development: `2018-01-01 00:00:00` through `2022-12-31 23:00:00`
- validation: `2023-01-01 00:00:00` through `2024-12-31 23:00:00`
- untouched confirmation: `2025-01-01 00:00:00` through `2025-12-31 00:00:00`

Anchors follow the existing Campaign #48 weekly grid:

- origin: first governed timestamp plus 168 hours;
- spacing: exactly 168 hours;
- predictor eligibility: every exact hourly timestamp in the trailing 168-hour inclusive window exists;
- horizon feasibility: the exact future endpoint timestamp exists and remains inside the same proposed stage;
- no close values or forward returns are loaded by the feasibility preflight.

The exact counts must be produced by `scripts/preflight_campaign51_source_variable_feasibility.py` before family selection.

## Leakage and isolation requirements

A later implementation must:

- compute predictors using timestamps and closes at or before anchor `t` only;
- fit all standardization parameters within the relevant development stage only;
- keep each forward endpoint inside its stage;
- prevent 2025 values from entering development or validation analytical structures;
- freeze the candidate family before any forward outcome generation;
- retain failed and unrankable candidates visibly;
- keep Campaign #51 research code disconnected from runtime, strategy, order, exposure, and NAV surfaces.

## Inventory conclusion

The source and transparent variable inventory supports a narrow 12-candidate Campaign #51 family in principle:

- two existing signed-return variables;
- two Campaign #48-supported movement-state variables;
- three existing Campaign #48 horizons;
- continuous interaction-based conditioning;
- one governed hourly BTC source.

Family selection should remain pending until the timestamp-only feasibility preflight passes and exact stage/horizon counts are recorded. No Campaign #51 outcome has been generated or inspected by this inventory.
