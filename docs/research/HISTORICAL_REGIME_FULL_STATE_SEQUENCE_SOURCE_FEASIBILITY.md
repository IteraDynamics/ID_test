# Campaign #45 — Full Historical Regime-State Sequence Source Feasibility

## Status

Observation-only source-feasibility decision for Campaign #45 on `agent/campaign-45-historical-regime-transitions`.

This document does not authorize predictive-return construction, result inspection, model training, regime-rule changes, runtime integration, thresholds, signals, strategies, orders, execution, portfolio construction, NAV, exposure, or dashboard changes.

## Decision

No already governed, repository-tracked full historical BTC regime-state sequence was identified.

Campaign #45 therefore remains a NO-GO for predictive implementation against the current collapse-only source population.

A compliant path exists, but it requires a separate source-foundation campaign that deterministically generates and governs a complete anchor-local BTC hourly regime-state sequence before Campaign #45 can be reconsidered.

## Repository evidence

The existing paper-runtime export and replay surfaces record regime labels at decision cycles, but they do not provide a governed complete historical bar-by-bar state sequence. The replay documentation explicitly states that exported market data contains only the single last bar used by each strategy call rather than the full historical lookback window. Those exports are therefore unsuitable as the canonical source for a complete historical regime sequence.

The repository does contain `research/regimes/baseline_engine.py`, whose `BaselineRegimeEngine`:

- is deterministic;
- classifies each closed bar using only rows through that bar;
- exposes `classify_dataframe(df)` for an offline full-series pass;
- emits `UNKNOWN` during its fixed warmup period;
- uses the existing frozen regime labels and constructor parameters;
- does not require outcome data to assign state labels.

The classifier is a viable source-construction mechanism. Its existence is not equivalent to an already governed historical artifact.

## Proposed source-foundation campaign

Before Campaign #45 predictive testing, create a separate observation-only source campaign with the immediate objective:

> Generate, validate, and publish a deterministic full BTC hourly regime-state sequence from the already governed BTC OHLCV source using the existing `BaselineRegimeEngine` without changing classifier logic or inspecting forward outcomes.

The source campaign must freeze, before generation:

1. exact BTC source path, SHA-256, byte count, row count, schema, timestamp convention, first timestamp, and last timestamp;
2. exact `BaselineRegimeEngine` source blob identity;
3. exact constructor parameters, including all defaults or explicitly supplied values;
4. exact bar-completion and timestamp semantics;
5. exact warmup handling;
6. exact state schema;
7. exact transition derivation rules;
8. exact handling of source gaps;
9. exact independent-anchor feasibility diagnostic;
10. canonical serialization, replay, and source-immutability requirements.

## Proposed canonical source outputs

Under a new source-only artifact directory, subject to a separate board authorization:

- `btc_hourly_regime_state_sequence.json`;
- `btc_hourly_regime_state_sequence.csv`;
- `btc_hourly_regime_transition_inventory.json`;
- `btc_hourly_regime_transition_inventory.csv`;
- `btc_hourly_regime_state_manifest.json`;
- `btc_hourly_regime_state_report.md`.

These are source and feasibility artifacts only. They must contain no forward returns, candidate coefficients, p-values, rankings, alpha claims, or strategy recommendations.

## Minimum state-row schema

Each eligible hourly row should contain only anchor-local information:

- exact timestamp;
- bar index;
- regime label;
- regime confidence;
- existing classifier sub-signals;
- warmup or availability state;
- source identity;
- classifier identity;
- research-only and runtime-integration flags.

## Minimum transition-row schema

Each actual non-self state change should contain:

- transition ID;
- transition timestamp;
- prior regime label;
- current regime label;
- prior-state start timestamp;
- prior-state age in exact governed hours or rows;
- current-state start timestamp;
- time since previous transition where available;
- source identity;
- classifier identity.

No future duration, later recovery, future price, or later-state information may be included.

## Fail-closed requirements

The source campaign must stop without publication when any of the following occurs:

- BTC source identity differs from the frozen manifest;
- classifier source identity differs from the frozen blob;
- classifier parameters are missing or ambiguous;
- timestamps are duplicated or non-increasing;
- required OHLCV fields are absent or invalid;
- classification uses an incomplete or mutable bar;
- a state label cannot be reproduced from data bounded by its timestamp;
- transition ordering or state-age calculation is ambiguous;
- source gaps are silently filled, interpolated, resampled, or matched approximately;
- two governed runs are not byte-identical;
- canonical text is not LF-only;
- source bytes change before versus after generation.

## Campaign #45 re-entry gate

Campaign #45 may not resume predictive implementation merely because the full sequence artifact exists.

A source-only feasibility report must first establish, without constructing forward outcomes, that the sequence provides:

- at least 20 chronologically purged independent eligible transition observations overall;
- at least 5 independent observations in each proposed chronological evaluation fold;
- exact anchor-local availability for the frozen predictor classes;
- exact BTC-control lookback availability;
- exact horizon coverage feasibility at 24, 72, and 168 hours;
- no dependence on overlapping collapse-episode membership for independence.

If these conditions fail, Campaign #45 should close as infeasible under the available history rather than weaken its gates.

## Authorization boundary

Authorized by the current board only:

- this feasibility document;
- repository inspection supporting the decision;
- a later proposal for a source-foundation campaign.

Not authorized by this document:

- source-generation implementation;
- new runners or tests;
- generated state artifacts;
- predictive outcomes;
- Campaign #45 result generation;
- changes to `BaselineRegimeEngine`;
- runtime, threshold, signal, strategy, order, portfolio, NAV, exposure, execution, or dashboard behavior.

## Recommended next decision

Open a separate source-foundation campaign for the deterministic full BTC hourly regime-state sequence. Keep Campaign #45 suspended until that campaign proves sufficient independent transition support and publishes replay-safe canonical source artifacts.