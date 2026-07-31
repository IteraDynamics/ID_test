# Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

## Status

**DRAFT GOVERNING SPECIFICATION — design only; not frozen.**

No Campaign #49 confirmation outcome may be generated, calculated, viewed, inspected, ranked, or interpreted under this draft.

Campaign #49 is research-only, observation-only, deterministic, replay-safe, chronological, leakage-safe, and fail-closed.

It authorizes no runtime, regime, threshold, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Plain-English question

Campaign #49 asks:

> Do the volatility-state persistence and drawdown-linked future-volatility associations discovered in Campaign #48 survive an honestly independent, separately frozen confirmation design?

Campaign #49 is not a new feature-discovery campaign. It must not search for better predictors, transformations, horizons, thresholds, interactions, or labels.

## Governed lineage

Campaign #49 begins from the Campaign #48 closure commit:

`77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

Campaign #48 canonical publication:

`fd7ee01`

Campaign #48 established 15 supported horizon-specific associations across five scientific groups:

1. trailing 24-hour realized volatility positively associated with future absolute return;
2. trailing 24-hour realized volatility positively associated with future realized volatility;
3. trailing 168-hour realized volatility positively associated with future absolute return;
4. trailing 168-hour realized volatility positively associated with future realized volatility;
5. deeper drawdown from the trailing 168-hour high associated with higher future realized volatility.

Each group was supported at exact 24-hour, 72-hour, and 168-hour horizons.

No Campaign #48 directional-return association was supported. Campaign #49 will not reopen directional-return discovery.

## Confirmation principle

The primary confirmation claim must rely on BTC hourly observations that were not part of the Campaign #48 governed source ending at:

`2025-12-31 00:00:00`

Historical reuse may be used only for implementation testing, source reconciliation, or explicitly labeled sensitivity analysis. It may not be described as independent confirmation.

At the time of this draft, no repository-tracked post-2025 hourly BTC confirmation source has been identified.

Therefore Campaign #49 must stop before specification freeze unless an authorized source is identified with fixed bytes, schema, timestamp coverage, and provenance.

## Proposed primary confirmation source contract

The eventual frozen source must be a single immutable hourly BTC close series beginning strictly after the Campaign #48 source endpoint.

The frozen specification must record:

- repository path;
- source provider and acquisition method;
- SHA-256;
- byte count;
- data-row count;
- exact ordered schema;
- first and last timestamp;
- timezone convention;
- complete missing-hour inventory;
- duplicate and ordering checks;
- close-value validity requirements;
- whether the source was available or inspected before the Campaign #49 design freeze.

No source substitution, downloading during governed execution, interpolation, filling, resampling, nearest-row matching, as-of matching, shifting, synthetic bars, or timestamp repair is permitted.

## Frozen predictor formulas carried forward from Campaign #48

Only three predictors are eligible for confirmation.

Let `C_t` denote the exact hourly close at timestamp `t`, and let hourly log return be:

`r_u = ln(C_u / C_{u-1h})`

### Predictor P1 — trailing 24-hour realized volatility

`rv_24_t = sqrt(sum(r_u^2))`

using all 24 exact hourly returns with endpoint timestamps in `(t-24h, t]`.

### Predictor P2 — trailing 168-hour realized volatility

`rv_168_t = sqrt(sum(r_u^2))`

using all 168 exact hourly returns with endpoint timestamps in `(t-168h, t]`.

### Predictor P3 — drawdown from trailing 168-hour high

Let `high_168_t` be the maximum of the 169 exact hourly closes in `[t-168h, t]`.

`drawdown_168_t = (C_t / high_168_t) - 1`

No additional predictor is authorized.

## Frozen outcome formulas carried forward from Campaign #48

Only two outcome families are eligible for confirmation.

For horizon `h` in `{24, 72, 168}`:

### Family M — future absolute return magnitude

`forward_return_h = ln(C_{t+h} / C_t)`

`forward_absolute_return_h = abs(forward_return_h)`

### Family V — future realized volatility

`forward_realized_volatility_h = sqrt(sum(r_u^2))`

using all `h` exact hourly returns with endpoint timestamps in `(t, t+h]`.

No directional-return confirmation family is included because Campaign #48 did not support one.

## Exact horizon-specific candidate inventory

The proposed confirmation inventory contains exactly the 15 Campaign #48 supported associations:

1. P1 → M at 24 hours;
2. P1 → M at 72 hours;
3. P1 → M at 168 hours;
4. P1 → V at 24 hours;
5. P1 → V at 72 hours;
6. P1 → V at 168 hours;
7. P2 → M at 24 hours;
8. P2 → M at 72 hours;
9. P2 → M at 168 hours;
10. P2 → V at 24 hours;
11. P2 → V at 72 hours;
12. P2 → V at 168 hours;
13. P3 → V at 24 hours;
14. P3 → V at 72 hours;
15. P3 → V at 168 hours.

No candidate may be added, removed, combined, replaced, or reprioritized after confirmation outcomes are generated or inspected.

## Proposed anchor construction

This section is not yet frozen.

The preferred design uses horizon-specific non-overlapping anchor grids rather than forcing all horizons onto the 168-hour Campaign #48 grid.

For each horizon `h`:

- the anchor origin is the earliest exact source timestamp with a complete 168-hour predictor window and complete `h`-hour outcome window;
- scheduled anchors advance by exactly `h` hours;
- an anchor is retained only when every timestamp required by the applicable predictor and outcome exists;
- missing scheduled anchors are not shifted or replaced;
- adjacent outcomes within the same horizon do not overlap.

Rationale:

- 24-hour claims receive one non-overlapping observation per day;
- 72-hour claims receive one non-overlapping observation per three days;
- 168-hour claims receive one non-overlapping observation per week;
- the design preserves temporal independence more directly than a common weekly grid while avoiding artificial loss of short-horizon confirmation power.

This differs from Campaign #48 anchor construction and therefore requires explicit pre-outcome approval at specification freeze. Predictor and outcome formulas remain unchanged.

## Proposed estimator

Each horizon-specific candidate uses ordinary least squares containing:

- an intercept;
- exactly one standardized predictor;
- no regimes;
- no fixed effects;
- no additional price controls;
- no interactions.

HC3 heteroskedasticity-consistent covariance is proposed.

Reported quantities:

- coefficient on the standardized predictor;
- HC3 standard error;
- two-sided normal p-value;
- 95% normal confidence interval using `1.959963984540054`.

Predictor standardization uses the complete confirmation sample for the candidate with population standard deviation `ddof=0`. Because the source is prospectively untouched and no parameter selection occurs, there is no development/evaluation split for scaling.

Outcomes are not standardized.

## Proposed confirmation direction

The expected coefficient sign is frozen from Campaign #48:

- P1 → M: positive;
- P1 → V: positive;
- P2 → M: positive;
- P2 → V: positive;
- P3 → V: negative.

A zero, nonfinite, or opposite-sign coefficient fails directional replication.

## Proposed multiplicity and decision rule

This section is not yet frozen.

The preferred primary rule treats the 15 horizon-specific associations as one confirmatory family and applies Holm family-wise error-rate control at alpha `0.05`.

A horizon-specific association is confirmed only when:

1. its coefficient has the Campaign #48 expected sign;
2. its two-sided Holm-adjusted p-value is `<= 0.05`;
3. its candidate passes all sample, variance, rank, and estimator gates.

A scientific group is confirmed only when at least two of its three horizons confirm and the remaining horizon has the expected sign.

The campaign-level result is positive only when at least three of the five scientific groups confirm, including at least one future-absolute-return group and at least one future-realized-volatility group.

Rationale:

- Holm is stricter than the discovery-stage Benjamini-Hochberg rule;
- group-level replication prevents one isolated horizon from carrying a scientific claim;
- the campaign-level conjunctive rule requires breadth across both movement magnitude and volatility persistence.

Alternative rules must be resolved before freeze. No rule may be changed after outcomes are generated or inspected.

## Proposed minimum sample gates

This section is not yet frozen because the available untouched source horizon is not yet established.

Initial design target:

- at least 180 candidate-complete 24-hour anchors;
- at least 90 candidate-complete 72-hour anchors;
- at least 52 candidate-complete 168-hour anchors.

These targets imply approximately six months, nine months, and one year of usable untouched hourly data respectively after accounting for the predictor lookback and missing windows.

Because all three horizons are part of every scientific group, the primary Campaign #49 confirmation should not run until the 168-hour horizon meets its minimum gate.

A candidate failing its horizon-specific minimum is unrankable and cannot confirm.

The final frozen sample thresholds require explicit power and feasibility review before implementation authorization.

## Effect-size compatibility

Statistical significance alone should not permit exaggerated interpretation.

The frozen design should include a prespecified compatibility check comparing the confirmation coefficient with the Campaign #48 discovery coefficient.

Preferred rule:

- expected sign must match;
- the confirmation estimate must be finite and nonzero;
- the confirmation 95% confidence interval must overlap a prespecified discovery compatibility interval recorded from Campaign #48 canonical results;
- the confirmation point estimate must not exceed the absolute Campaign #48 estimate by more than a prespecified multiplier without explicit caution.

The exact compatibility construction is unresolved and must be frozen before outcomes.

## Rankability and failure states

A candidate is rankable only when:

- the frozen source reconciles exactly;
- the candidate meets its horizon-specific minimum support;
- predictor and outcome values are finite;
- predictor population standard deviation is finite and strictly positive;
- the two-column OLS design has full rank;
- the coefficient is finite and nonzero;
- the HC3 standard error is finite and strictly positive;
- the p-value is finite.

Every candidate remains visible.

Proposed deterministic statuses:

1. `CONFIRMED_ASSOCIATION`;
2. `MULTIPLICITY_NOT_MET`;
3. `DIRECTION_NOT_REPLICATED`;
4. `EFFECT_COMPATIBILITY_NOT_MET`;
5. `INSUFFICIENT_CONFIRMATION_SUPPORT`;
6. `OUTCOME_OR_PREDICTOR_UNAVAILABLE`;
7. `ZERO_OR_NONFINITE_VARIANCE`;
8. `RANK_DEFICIENT_DESIGN`;
9. `ESTIMATOR_FAILURE`.

Failure precedence must be frozen in the implementation handoff.

## Required canonical outputs

The exact output set is unresolved, but should include at minimum:

- confirmation source manifest;
- anchor inventories by horizon;
- exact candidate inventory;
- confirmation results in CSV and JSON;
- group-level decision table;
- campaign-level decision record;
- deterministic report;
- canonical manifest.

All outputs must be UTF-8, LF-only, strict JSON where applicable, and free of wall-clock timestamps, machine-specific absolute paths, random identifiers, unordered mappings, or nonfinite JSON values.

## Preflight requirement

Before any confirmation outcome is generated, the future runner must support preflight-only mode verifying:

- source identity and provenance;
- ordered schema;
- timestamp parsing, timezone, uniqueness, ordering, alignment, endpoints, and complete missing-hour inventory;
- finite strictly positive closes;
- exact predictor, outcome, candidate, expected-sign, anchor-grid, multiplicity, and sample-gate inventories;
- deterministic anticipated anchor counts by horizon;
- absence of confirmation outcome generation.

Preflight must explicitly report `confirmation_outcomes_generated:false`.

## Replay and immutability

A future implementation must require:

1. governed source hash before generation;
2. one canonical generation;
3. hashes of all canonical outputs;
4. a second canonical generation from the same source;
5. byte identity across all outputs;
6. post-generation preflight;
7. proof that governed source bytes remained unchanged.

Any mismatch is a hard failure and prohibits publication.

## Interpretation boundary

Campaign #49 can confirm a statistical association only.

It does not establish:

- deployable alpha;
- directional forecasting ability;
- economic value;
- transaction-cost robustness;
- portfolio improvement;
- sizing value;
- timing value;
- superiority to Core v1;
- production readiness.

Only a successfully confirmed result may be proposed for a later separately frozen incremental economic-value campaign.

## Stop conditions before specification freeze

Work must stop before freeze if:

- no genuinely untouched authorized hourly BTC source exists;
- source provenance or bytes cannot be frozen;
- the untouched sample cannot meet the minimum 168-hour confirmation gate;
- the multiplicity or group-level confirmation rule remains ambiguous;
- effect-size compatibility remains ambiguous;
- any design decision is informed by viewing Campaign #49 outcomes;
- any runtime or strategy change is proposed.

## Design-review decisions still required

1. Confirm the untouched source and its exact coverage.
2. Confirm horizon-specific non-overlapping grids versus a common 168-hour grid.
3. Confirm Holm correction across all 15 candidates.
4. Confirm the two-of-three horizon group rule.
5. Confirm the three-of-five campaign rule.
6. Freeze minimum sample requirements.
7. Freeze effect-size compatibility intervals using Campaign #48 canonical results only.
8. Freeze exact output schemas and status precedence in a later implementation handoff.
