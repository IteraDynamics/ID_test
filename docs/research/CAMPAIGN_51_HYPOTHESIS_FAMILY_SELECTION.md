# Campaign #51 Hypothesis-Family Selection

## Decision

Select a narrow, research-only family testing whether previously supported BTC movement states condition the directional value of recent signed return.

This decision is made before Campaign #51 predictor values, forward outcomes, model fits, coefficients, p-values, rankings, support decisions, or economic results are generated.

## Selected family

Directional variables:

1. trailing 24-hour signed log return;
2. trailing 168-hour signed log return.

Conditioning movement states:

1. trailing 24-hour realized volatility;
2. drawdown from the trailing 168-hour close high.

Proposed forward horizons:

1. 24 hours;
2. 72 hours;
3. 168 hours.

Candidate effect:

- one continuous directional variable;
- one continuous movement-state variable;
- their interaction;
- forward directional BTC return as the later outcome, subject to a separately frozen statistical specification.

Candidate count:

- `2 directional variables × 2 movement states × 3 horizons = 12 candidates`.

## Research question

> Does the association between recent signed BTC return and subsequent directional return differ as a function of recent realized volatility or drawdown state?

Campaign #51 does not treat volatility or drawdown as unconditional directional predictors. The interaction asks whether the usefulness or character of an independently defined directional variable changes with the movement state.

## Pre-outcome rationale

### Trailing 24-hour signed return

This is the shortest directional variable already defined in Campaign #48. It represents recent directional impulse and is distinct from the conditioning variables.

### Trailing 168-hour signed return

This represents a slower directional state and gives one economically distinct horizon without adding the nested 72-hour return.

### Trailing 24-hour realized volatility

Campaign #48 supported this variable as a predictor of future movement magnitude and future realized volatility at 24, 72, and 168 hours. It is therefore a justified candidate for conditioning directional information.

### Drawdown from the trailing 168-hour high

Campaign #48 supported deeper drawdown as associated with higher future realized volatility at all three horizons. It represents location within a recent loss state rather than volatility alone.

### Excluded alternatives

The following variables remain documented but are not selected:

- trailing 72-hour signed return;
- trailing 168-hour realized volatility;
- distance from the trailing 168-hour mean;
- position within the trailing 168-hour range.

They are excluded to control nested-variable duplication, interpretation overlap, and multiplicity. Their exclusion is not based on Campaign #51 outcome performance.

## Source and non-outcome feasibility

Governed source:

- `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- SHA-256 `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- 70,069 rows;
- timestamps from `2018-01-01 00:00:00` through `2025-12-31 00:00:00`;
- exact governed inventory of 36 missing timestamps;
- no interpolation, filling, resampling, matching, shifting, synthetic bars, or source repair.

Timestamp-only stage-contained endpoint counts on the existing 168-hour anchor grid:

- development: 248 at 24h, 248 at 72h, 247 at 168h;
- validation: 104 at 24h, 103 at 72h, 103 at 168h;
- untouched confirmation: 51 at 24h, 50 at 72h, 50 at 168h.

The source feasibility preflight passed with:

- prices loaded: false;
- predictors generated: false;
- forward outcomes generated: false;
- models fitted: false;
- holdout outcomes loaded: false;
- runtime modified: false.

Focused timestamp-only helper tests were reported PASS. The exact pytest count was not supplied and is not asserted here.

## Interpretation boundary

Family selection does not establish predictive value, statistical support, economic value, deployable alpha, sizing value, timing value, Core v1 improvement, or production readiness.

A later statistical specification must separately freeze:

- exact model equation and interpretation of the interaction term;
- predictor transformations and standardization;
- stage boundaries and anchor rules;
- minimum support gates;
- covariance estimator;
- expected signs or sign-agnostic interpretation;
- multiplicity correction;
- development, validation, and confirmation pass rules;
- deterministic artifact and replay requirements.

## Authorization boundary

This record selects the hypothesis family only.

It does not authorize:

- generation of Campaign #51 predictors or outcomes;
- model fitting;
- implementation of an analytical runner;
- access to 2025 analytical values;
- economic testing;
- paper trading;
- runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training changes.
