# Campaign #50 — Pre-Outcome Support-Gate Amendment

## Status

**PRE-OUTCOME GOVERNANCE AMENDMENT — no real prices, predictors, outcomes, coefficients, rankings, validation results, shortlist results, or 2025 observations were generated or loaded before this amendment.**

This amendment supersedes only the development minimum-total-support values for the 20-session and 60-session horizons in `docs/research/CAMPAIGN_50_EQUITY_BREADTH_STATISTICAL_SPEC.md`.

All other source identities, intervals, predictors, targets, horizons, expected signs, anchor construction, binary-event support gates, OLS/HC3 inference, Holm correction, validation rules, holdout rules, family-level rules, output schemas, and stage boundaries remain unchanged.

## Structural evidence

The date-only feasibility preflight used only the frozen SPY/QQQ session calendar and generated no prices or analytical values.

Maximum stage-contained non-overlapping development anchors after the frozen 220-session lookback:

- 5-session horizon: 207
- 20-session horizon: 51
- 60-session horizon: 17

Original development minimum-total-support gates:

- 5-session horizon: 180
- 20-session horizon: 55
- 60-session horizon: 18

The 20-session and 60-session gates were therefore structurally impossible before candidate completeness or predictor-event support could even be evaluated.

Validation remained structurally feasible under the original gates:

- 5-session horizon: 100 maximum versus 80 minimum
- 20-session horizon: 25 maximum versus 22 minimum
- 60-session horizon: 8 maximum versus 8 minimum

## Ex ante amendment rule

For a structurally impossible development total-support gate, set the amended minimum to the largest round integer not exceeding approximately 95% of the date-only maximum anchor count, while preserving at least one anchor of mechanical headroom.

Applied values:

- 20 sessions: maximum 51; amended minimum 50
- 60 sessions: maximum 17; amended minimum 16

The 5-session development minimum remains 180.

No validation or holdout support gate changes.

## Amended minimum-total-support table

Development:

- 5-session horizon: 180
- 20-session horizon: 50
- 60-session horizon: 16

Validation, unchanged:

- 5-session horizon: 80
- 20-session horizon: 22
- 60-session horizon: 8

Holdout, unchanged:

- 5-session horizon: 40
- 20-session horizon: 11
- 60-session horizon: 4

Binary-predictor event/non-event minimums remain unchanged.

## Governance effect

This amendment corrects a calendar-mechanical impossibility discovered before any empirical Campaign #50 outcome generation.

It does not authorize development/validation execution. After implementation constants and tests are aligned, all non-outcome validation must pass and the authoritative campaign board must record a new execution GO.
