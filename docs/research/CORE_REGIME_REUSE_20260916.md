# Isolated reuse of Core's regime classifier

User constraint: never modify Core V1 or code consumed by Core. This branch adds
an independent consumer; it changes no pre-existing file. Core paper trading
does not import this package. No orders, targets, runtime state, or strategy
configuration are produced by the new runner.

## Recovered lineage

Source reference: `dbe1b155c83b8490c43271f21ee3199156a4d9a1`, tree
`3e6d4bfb1a0f582b59ce0d863299201668f1845d`.

- `scripts/run_core_v1_paper_live.py::classify_regime` calls
  `BaselineRegimeEngine().classify_bar(df, len(df)-1)` and passes its label into
  `StrategyContext`. Its exception fallback is UNKNOWN.
- `scripts/run_multi_strategy_walkforward.py` calls `run_backtest` without an
  engine override; `research/harness/backtest_engine.py` instantiates the same
  default class and calls `classify_dataframe`.
- `trend_following_v11 -> v9 -> v8` consumes the label for entry tiers,
  blocked regimes, add-ons, and some exits. v9 adds SPY/BTC recovery rules;
  v11 adds BTC extension caps. These are separate from the classifier.
- Selected allocation resides in `runtime/core_v1/allocation.py`. Equity and
  gold use their own SMA decision rules; their metadata includes the generic
  regime label. Recovering the generic classifier is not recovering all of
  Core's investment logic, nor attributing its returns to that classifier.
- The older `FULL_HISTORICAL_REGIME_STATE_SEQUENCE.md` also explicitly pins
  this class and its default parameters. No Markov/HMM comparison was located
  in the inspected working-tree research documentation. The user's reported
  comparison remains unverified, not disproven. This work does not establish
  byte identity to an unidentified historical performance run.

## Exact implementation preserved

The adapter imports the existing class; it copies no indicators or thresholds.
Defaults: EMA 21/55, ATR span 14, high-vol 0.04, mid-vol 0.025, compression
0.012, volatility acceleration and momentum lookbacks 5, min_bars 60.
The first non-warmup observation is index 60 (the 61st row).

Actual priority is HIGH_VOL, VOL_EXPANSION, VOL_COMPRESSION, TREND_UP,
TREND_DOWN, RANGE. Compression precedes trend in code, despite the header's
ordering. ATR uses pandas EWM span 14, despite the helper's Wilder wording.
Both behaviors are preserved. Confidence is an uncalibrated heuristic score.

`source_lock.json` hashes the recovered sources, including their strategy and
runtime context. Checks normalize CRLF/LF only. A source change stops this
research adapter; do not update Core to satisfy the lock.

## Information boundary and parity limits

`CoreRegimeReader.snapshot(completed_bars)` calls Core's exact single-bar API.
`history(completed_bars)` calls its existing batch API. The caller must supply
identical input history to claim identical states: EWM initialization depends
on the start of that history. Historical fold resets and live rolling fetch
windows are not reproduced by running once over a complete CSV.

The runner uses the already supplied BTC/ETH hourly CSVs, plus the existing
Core resampler for 4H. UTC input timestamps denote bucket starts. Output
`available_at` denotes bucket end, with no vendor latency claim. Trailing
unclosed 4H bins are excluded. Internal missing hours are not filled; Core's
resampler aggregates available observations, so partial internal bins are
retained and counted. These gaps remain a data limitation for later research.

Invalid OHLC inputs fail explicitly in the adapter, unlike Core paper's
exception-to-UNKNOWN wrapper. Valid-input classifier output is preserved.

Cross-asset state is deliberately not exported as though already equivalent:
the historical helper computes BTC extension from daily closes/SMA365;
the inspected paper helper uses hourly closes/8760-observation SMA. Daily
labels and as-of availability also require separate handling when replayed
historically. These are existing differences, not changed or resolved here.
No conclusion about Core's reported performance follows from this observation
alone. Reusing those additional states requires a separately explicit choice
of historical versus paper semantics and a point-in-time join test.

## Run and interpretation

Run `scripts/local/run_core_regime_reuse.ps1` in this separate research
checkout. It runs the isolated tests and exports four BTC/ETH 1H/4H state
ledgers, source hashes, missing-hour counts, label frequencies, and sampled
batch-versus-prefix parity checks. It does not download market data or run
Core. The Python environment may need its normal dependency installation.

This is reusable research plumbing, not a profitable strategy or a new OOS
result. Existing history remains development data. The next experiment can
use these frozen states as predeclared conditioning variables, comparing
the same candidate with and without conditioning under matched costs and
timing. Do not choose a profitable state retrospectively and call it OOS.

## Executed verification

Python 3.12.14: 12 isolated tests passed. Full supplied BTC/ETH hourly histories
exported successfully: 70,069 BTC 1H, 17,522 BTC 4H, 70,086 ETH 1H, and
17,525 ETH 4H rows. All 88 sampled prefix comparisons matched exactly.
980 pre-existing tracked files were byte-hash checked; zero changed.
`validation_record.json` contains input fingerprints, counts, and versions.
The PowerShell wrapper was inspected but could not be executed on Linux.

The state distributions differ materially by timeframe: BTC 1H has 56,239
VOL_COMPRESSION rows, versus 4,628 on BTC 4H. These are observed label counts,
not predictive performance. Preserve timeframe identity in downstream tests;
do not interpret the same fixed ATR percentage threshold as the same market
condition across bar durations.
