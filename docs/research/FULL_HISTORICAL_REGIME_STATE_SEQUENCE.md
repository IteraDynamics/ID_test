# Campaign #46 — Full Historical Regime State Sequence

## Status

Specification frozen for implementation review on `agent/campaign-46-full-regime-state-source`.

Campaign #46 is source-foundation work only. It is deterministic, replay-safe, research-only, observation-only, anchor-local, and fail-closed. It does not authorize predictive-return generation, model training, threshold changes, signals, strategy changes, orders, execution, portfolio construction, NAV changes, exposure mutation, dashboard changes, or runtime integration.

## Immediate objective

Generate and govern a complete BTC hourly historical regime-state ledger and derived transition inventory from the already-governed BTC hourly OHLCV source using the existing immutable `BaselineRegimeEngine` classification logic.

The campaign exists solely to determine whether Campaign #45 can be supplied with a sufficiently supported, anchor-local population of historical regime states and transitions.

## Exact research question

Can Itera deterministically reconstruct a complete, leakage-safe BTC hourly regime-state sequence and transition inventory that contains enough chronologically independent observations to satisfy Campaign #45's frozen support gates, without inspecting forward returns or changing regime logic?

## Strategic contribution

Campaign #46 creates a reusable governed market-state ledger for future research. It replaces ad hoc reconstruction and sparse decision-cycle logs with a canonical, timestamped source artifact that can support transition, duration, spacing, persistence, and clustering studies.

A successful Campaign #46 result establishes source feasibility only. It does not establish alpha or authorize Campaign #45 predictive testing by itself.

## Frozen source inputs

### Governed BTC hourly OHLCV source

Repository-relative local path:

`data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`

Required immutable identity:

- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- row count: `70,069`
- exact ordered schema: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- first timestamp: `2018-01-01 00:00:00`
- last timestamp: `2025-12-31 00:00:00`
- timestamp convention: timezone-naive exact hourly labels

No alternate price source, interpolation, filling, resampling, nearest-row matching, as-of matching, or field substitution is authorized.

### Existing regime classifier

- `research/regimes/baseline_engine.py`
- class: `BaselineRegimeEngine`
- historical API: `classify_dataframe()`

Campaign #46 must call the existing classifier. It must not copy, fork, modify, reinterpret, or tune the classifier rules.

## Frozen classifier configuration

Campaign #46 must use the constructor defaults exactly:

- `fast_ema = 21`
- `slow_ema = 55`
- `atr_period = 14`
- `high_vol_threshold = 0.04`
- `mid_vol_threshold = 0.025`
- `compression_threshold = 0.012`
- `vol_expansion_lookback = 5`
- `momentum_lookback = 5`
- `min_bars = 60`

Any source-code or default-value disagreement fails closed.

## Frozen state labels

Only the existing `RegimeLabel` values emitted by `BaselineRegimeEngine` are eligible:

- `UNKNOWN`
- `HIGH_VOL`
- `VOL_EXPANSION`
- `TREND_UP`
- `TREND_DOWN`
- `VOL_COMPRESSION`
- `RANGE`

No new state, merged state, learned state, relabeling, hierarchy, or post-hoc category is authorized.

## Anchor locality and timing

Each state row is anchored to the exact timestamp of the closed source bar classified by the engine.

For row position `i`, all classification inputs must be bounded by source rows `0..i`. The implementation must verify that the output timestamp and `bar_index` reconcile exactly to the source row.

`UNKNOWN` warmup rows remain visible and must not be reclassified.

## Frozen state-sequence schema

Each state row must contain at least:

- `bar_index`
- `timestamp`
- `regime_label`
- `confidence`
- `reason`
- `atr_pct`
- `atr_accel`
- `ema_roc`
- `ema_spread`
- `is_warmup`
- `source_row_digest`

Rows must preserve exact ascending source order and reconcile one-to-one with every governed OHLCV row.

## Frozen transition definition

A transition occurs at state row `i` only when:

1. `i > 0`;
2. current and prior labels are both non-null;
3. `current_label != prior_label`.

Each transition anchor is the exact current-row timestamp.

Transition rows must contain at least:

- deterministic `transition_id`;
- `transition_ordinal`;
- `anchor_bar_index`;
- `anchor_timestamp`;
- `prior_regime_label`;
- `current_regime_label`;
- `ordered_transition` as `<prior> -> <current>`;
- `prior_state_start_timestamp`;
- `prior_state_duration_bars`;
- `prior_transition_timestamp` or strict JSON `null`;
- `spacing_since_prior_transition_bars` or strict JSON `null`;
- `current_state_age_bars`, fixed as `1` at the transition anchor;
- `anchor_source_row_digest`.

`UNKNOWN` transitions must remain visible in the complete transition ledger but are ineligible for Campaign #45 support feasibility unless a later Campaign #45 transition explicitly authorizes them.

## State runs

The implementation must derive deterministic contiguous state runs. Each run must contain:

- `state_run_id`;
- `state_run_ordinal`;
- `regime_label`;
- `start_bar_index`;
- `end_bar_index`;
- `start_timestamp`;
- `end_timestamp`;
- `duration_bars`;
- `entered_from_regime_label` or strict JSON `null`;
- `exited_to_regime_label` or strict JSON `null`.

## Independent-support feasibility

Campaign #46 must not construct forward returns.

It must report source-only feasibility counts for Campaign #45 under the already-frozen maximum-horizon purge of `168` hours:

1. total non-`UNKNOWN` transitions;
2. transitions after removing exact duplicate timestamps;
3. maximum deterministic chronologically purged transition set using greedy ascending timestamp selection with minimum separation of `168` exact hours;
4. eligible counts by ordered transition category;
5. chronological thirds of the purged transition set, with deterministic remainder allocation to earlier folds;
6. whether at least `20` purged observations exist overall;
7. whether at least `5` purged observations exist in each of three chronological folds.

These are feasibility counts only. They must not include returns, outcome availability, coefficients, p-values, effect directions, or candidate ranking.

## Deterministic purge algorithm

Order eligible non-`UNKNOWN` transitions by:

`(anchor_timestamp, anchor_bar_index, transition_id)` ascending.

Select the first transition. Thereafter select a transition only when its anchor timestamp is at least `168` exact hours after the most recently selected anchor timestamp.

No optimization for maximizing category support, balancing folds, or preserving specific transitions is permitted.

## Canonical outputs

Planned outputs under `artifacts/full_historical_regime_state_sequence/`:

- `btc_hourly_regime_state_sequence.csv`
- `btc_hourly_regime_state_sequence.json`
- `btc_hourly_regime_state_runs.csv`
- `btc_hourly_regime_transitions.csv`
- `btc_hourly_regime_transitions.json`
- `btc_hourly_regime_support_feasibility.json`
- `btc_hourly_regime_state_report.md`
- `btc_hourly_regime_state_manifest.json`

All text outputs must be LF-only, deterministically ordered, strict JSON with sorted keys and `allow_nan=false`, finite numeric values only, and repo-relative source identifiers.

## Required preflight

Before generation, implementation must verify:

1. exact BTC source path and existence;
2. SHA-256, byte count, row count, ordered schema, first timestamp, and last timestamp;
3. timestamp parsing, strict ordering, uniqueness, and exact hour alignment;
4. numeric finiteness, signs, and OHLC consistency;
5. exactly `30` missing hourly timestamps across `14` discontinuities, with largest elapsed interval `16` hours and `15` missing timestamps;
6. exact classifier file identity captured in the manifest;
7. classifier default parameters equal the frozen configuration;
8. state-label enum equals the frozen label set;
9. output directory is newly created or explicitly empty;
10. source identities remain unchanged before and after generation.

Any disagreement fails closed before canonical publication.

## Required focused tests

Focused tests must cover at least:

- exact source identity and structural validation;
- missing or changed source failure;
- classifier-default mismatch failure;
- one-to-one state-row reconciliation;
- no-look-ahead classification behavior;
- preservation of `UNKNOWN` warmup rows;
- exact state-change detection;
- state-run duration and boundary reconciliation;
- duplicate-anchor rejection;
- deterministic transition identifiers and ordering;
- exact 168-hour greedy purge behavior;
- chronological fold allocation;
- support-feasibility pass and fail states;
- strict finite serialization;
- LF-only outputs;
- two-run byte identity;
- governed-source immutability;
- output-directory fail-closed behavior.

## Acceptance gates

Campaign #46 is complete only when:

1. this specification predates implementation and result inspection;
2. focused tests pass;
3. governed preflight passes;
4. state rows reconcile one-to-one to all `70,069` source rows;
5. transition and state-run counts reconcile exactly;
6. all classifications are anchor-local;
7. no classifier or threshold logic changes occur;
8. two governed runs produce byte-identical canonical outputs;
9. canonical text outputs are LF-only;
10. the full repository suite passes with no new failures;
11. scope review confirms no predictive outcomes, runtime, model-training, threshold, signal, strategy, intent, order, execution, portfolio, NAV, exposure, or dashboard changes;
12. Campaign #45 support feasibility is reported without forward-return inspection.

## Authorized implementation file surfaces

After a separate implementation GO recorded on the campaign board, Campaign #46 may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- this specification;
- one implementation handoff under `docs/research/`;
- one new observation-only module under `research/ml/validation/`;
- one new runner under `scripts/`;
- focused Campaign #46 tests under `tests/`;
- `artifacts/full_historical_regime_state_sequence/**`.

No modification to `research/regimes/baseline_engine.py`, regime contracts, runtime code, strategies, thresholds, allocation, execution, portfolio, NAV, exposure, or dashboards is authorized.

## Current authorization state

Specification creation and board transition are authorized. Implementation, canonical generation, and artifact publication remain unauthorized until the implementation handoff freezes exact code interfaces, source hashes, output schemas, preflight behavior, and publication protocol and the board records a separate implementation GO.
