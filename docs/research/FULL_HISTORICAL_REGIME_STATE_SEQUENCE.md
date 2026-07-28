# Campaign #46 — Full Historical Regime State Sequence

## Status

Specification frozen for source-only implementation on `agent/campaign-46-full-regime-state-source`.

Campaign #46 is deterministic, replay-safe, research-only, observation-only, anchor-local, and fail-closed. It does not authorize predictive-return generation, model training, threshold changes, signals, strategy changes, orders, execution, portfolio construction, NAV changes, exposure mutation, dashboard changes, or runtime integration.

## Immediate objective

Generate and govern a complete BTC hourly historical regime-state ledger and transition inventory from the governed BTC hourly OHLCV source using the existing immutable `BaselineRegimeEngine`, then determine only whether the resulting source population can satisfy Campaign #45's frozen independent-support gates.

A successful Campaign #46 result establishes source feasibility only. It does not establish alpha or authorize Campaign #45 predictive testing.

## Frozen source inputs

### Governed BTC hourly OHLCV source

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- row count: `70,069`
- ordered schema: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- first timestamp: `2018-01-01 00:00:00`
- last timestamp: `2025-12-31 00:00:00`
- timestamp convention: timezone-naive exact hourly labels

No alternate source, interpolation, filling, resampling, nearest-row matching, as-of matching, or field substitution is authorized.

### Corrected governed gap evidence

The governed source identity above was unchanged during preflight. A deterministic full-row diagnostic established:

- discontinuities: `14`
- missing hourly timestamps: `36`
- largest elapsed interval: `16` hours
- largest missing block: `15` timestamps

The earlier specification value of `30` missing timestamps was incorrect and is superseded by this pre-result correction. The correction changes source metadata only. It does not change the source file, classifier, state construction, purge method, support gate, or predictive authorization.

Exact discontinuity inventory:

| Prior timestamp | Next timestamp | Elapsed hours | Missing timestamps |
|---|---:|---:|---:|
| `2018-02-01 04:00:00` | `2018-02-01 08:00:00` | 4 | 3 |
| `2018-05-10 03:00:00` | `2018-05-10 05:00:00` | 2 | 1 |
| `2018-05-30 02:00:00` | `2018-05-30 04:00:00` | 2 | 1 |
| `2018-06-04 02:00:00` | `2018-06-04 04:00:00` | 2 | 1 |
| `2018-08-10 00:00:00` | `2018-08-10 16:00:00` | 16 | 15 |
| `2018-12-26 01:00:00` | `2018-12-26 03:00:00` | 2 | 1 |
| `2019-04-11 12:00:00` | `2019-04-11 14:00:00` | 2 | 1 |
| `2019-06-20 14:00:00` | `2019-06-20 16:00:00` | 2 | 1 |
| `2019-10-31 19:00:00` | `2019-10-31 21:00:00` | 2 | 1 |
| `2020-01-30 16:00:00` | `2020-01-30 18:00:00` | 2 | 1 |
| `2020-09-04 22:00:00` | `2020-09-05 00:00:00` | 2 | 1 |
| `2020-10-20 19:00:00` | `2020-10-20 21:00:00` | 2 | 1 |
| `2023-03-04 17:00:00` | `2023-03-04 21:00:00` | 4 | 3 |
| `2025-10-25 15:00:00` | `2025-10-25 21:00:00` | 6 | 5 |

## Frozen classifier

Campaign #46 must consume unchanged:

- file: `research/regimes/baseline_engine.py`
- class: `BaselineRegimeEngine`
- historical API: `classify_dataframe()`

Instantiate exactly with `BaselineRegimeEngine()` and use constructor defaults:

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

Only existing `RegimeLabel` values are eligible:

- `UNKNOWN`
- `HIGH_VOL`
- `VOL_EXPANSION`
- `TREND_UP`
- `TREND_DOWN`
- `VOL_COMPRESSION`
- `RANGE`

No new, merged, learned, or relabeled state is authorized.

## Anchor locality

For source row `i`, all classification inputs must be bounded by rows `0..i`. Output timestamp and `bar_index` must reconcile exactly to the source row. `UNKNOWN` warmup rows remain visible and must not be reclassified.

## Frozen state sequence

Each state row must include:

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

Rows preserve exact ascending source order and reconcile one-to-one with all `70,069` source rows.

## Frozen state runs and transitions

A new state run begins at row zero or when the label changes from the immediately preceding observed row. Timestamp gaps do not independently start runs. `duration_bars` counts observed source rows.

A transition occurs when adjacent observed rows have different labels. Its anchor is the current row timestamp. Complete transitions involving `UNKNOWN` remain visible but are excluded from Campaign #45 source-feasibility counts.

Transition IDs, run IDs, ordinals, ordering, durations, and spacing are deterministic as frozen in the implementation handoff.

## Independent-support feasibility

Campaign #46 must not construct forward returns. It reports only:

1. total transitions;
2. eligible non-`UNKNOWN` transitions;
3. duplicate-anchor validation;
4. deterministic greedy transition set separated by at least `168` exact clock hours;
5. eligible counts by ordered transition;
6. three chronological folds with remainder allocated to earlier folds;
7. whether at least `20` purged observations exist overall;
8. whether each fold contains at least `5` observations.

No returns, coefficients, p-values, effect directions, rankings, or deployability claims are permitted.

## Deterministic purge

Order eligible transitions by `(anchor_timestamp, anchor_bar_index, transition_id)` ascending. Select the first, then select a later transition only when it is at least `168` exact hours after the most recently selected transition. No category optimization or fold balancing is permitted.

## Canonical outputs

Under `artifacts/full_historical_regime_state_sequence/`:

- `btc_hourly_regime_state_sequence.csv`
- `btc_hourly_regime_state_sequence.json`
- `btc_hourly_regime_state_runs.csv`
- `btc_hourly_regime_transitions.csv`
- `btc_hourly_regime_transitions.json`
- `btc_hourly_regime_support_feasibility.json`
- `btc_hourly_regime_state_report.md`
- `btc_hourly_regime_state_manifest.json`

All text outputs must be LF-only, deterministically ordered, strict JSON with sorted keys and `allow_nan=false`, finite numeric values only, and repository-relative source identifiers.

## Required preflight

Before generation, verify:

1. exact source path and existence;
2. SHA-256, bytes, rows, schema, first timestamp, and last timestamp;
3. strict timestamp ordering, uniqueness, and exact-hour alignment;
4. finite numeric values and OHLC consistency;
5. exactly `36` missing hourly timestamps across `14` discontinuities, with largest elapsed interval `16` hours and largest missing block `15` timestamps;
6. classifier file identity in the manifest;
7. frozen classifier defaults;
8. frozen label set;
9. output directory absent or empty;
10. source identity unchanged before and after generation.

Any disagreement fails closed before publication.

## Acceptance gates

Campaign #46 is complete only when:

1. specification and handoff predate result inspection;
2. focused tests pass;
3. corrected governed preflight passes;
4. all `70,069` source rows reconcile one-to-one;
5. state-run and transition counts reconcile;
6. classifications are anchor-local;
7. classifier and thresholds remain unchanged;
8. two governed runs produce byte-identical outputs;
9. canonical text is LF-only and JSON is strict;
10. full repository tests pass with no new failures;
11. scope review confirms no predictive outcomes or production/runtime/model/threshold/signal/strategy/order/portfolio/NAV/exposure/dashboard changes;
12. Campaign #45 source feasibility is reported without forward-return inspection.

## Authorized file surfaces

Campaign #46 may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`
- this specification
- `docs/research/FULL_HISTORICAL_REGIME_STATE_SEQUENCE_IMPLEMENTATION_HANDOFF.md`
- `research/ml/validation/full_historical_regime_state_sequence.py`
- `scripts/run_full_historical_regime_state_sequence.py`
- `tests/test_full_historical_regime_state_sequence.py`
- `artifacts/full_historical_regime_state_sequence/**`

No modification to the regime engine, regime contracts, runtime, strategies, allocation, execution, portfolio, NAV, exposure, or dashboards is authorized.
