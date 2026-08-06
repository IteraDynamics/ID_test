# Core v1 — Live Benchmark Registration

## Status

**PRE-REGISTERED — frozen before further live record accrues.**

Registered 2026-08-06, with approximately 30 days of live paper record elapsed since the
2026-07-07 inception. From this date forward, Core v1's live paper performance is evaluated
against the benchmarks below. Benchmarks may be added prospectively; they may never be changed,
removed, or substituted retroactively.

## Why this document exists

A NAV chart measured against zero flatters every strategy in a bull market and indicts every
strategy in a bear market. Core v1 is a trend-filtered beta book; its live claim is that its
timing layer adds value over holding the same assets statically. That claim is only testable
against comparators fixed in advance.

## Registered benchmarks

### Benchmark A — Static-weight twin (primary)

The same six-sleeve universe at canonical Core v1 target weights, held statically with no
timing, no trend filters, and no de-risk governors:

| Asset | Weight |
|---|---:|
| BTC | 15.0% |
| ETH | 20.0% |
| SPY | 17.5% |
| QQQ | 27.5% |
| GLD | 20.0% |

Rules:

- fully invested at the weights above at all times;
- rebalanced to target weights at the first daily close of each calendar month;
- same governed price sources as the paper runtime;
- transaction costs applied at the same fee/slippage assumptions as the paper runtime;
- inception aligned to the live series: 2026-07-07, starting capital 100,000 USD.

Benchmark A extends the Campaign #52 static-control concept to the live period. Core v1's
timing layer is doing its job if and only if, over meaningful horizons, canonical Core v1 beats
Benchmark A on risk-adjusted terms (drawdown and Calmar foremost) — beating it on raw return in
all periods is not expected and not required.

### Benchmark B — Conservative mixed reference

60% SPY / 40% cash (cash accrues at 0%), rebalanced at the first daily close of each calendar
month, same inception and starting capital.

Benchmark B is deliberately implementable from already-governed sources with no new data
dependency. A bond-based 60/40 variant (e.g., SPY/AGG) may be registered later as Benchmark B2,
prospectively only, once a governed bond source exists.

## Measurement rules

1. Comparison unit: month-end NAV in USD, from the paper runtime's persisted state for Core v1
   and from deterministic computation over governed daily closes for benchmarks.
2. All series net of modeled costs under identical assumptions.
3. Reported metrics: cumulative return, annualized return, maximum drawdown, Calmar, and
   annualized Sharpe (zero benchmark), each computed identically across all series.
4. Benchmark computations must be deterministic and reproducible from governed sources; when
   benchmark series are first implemented, their construction code and artifact hashes are
   recorded under the existing artifact conventions.
5. No retroactive modification: weights, rebalance rules, cost assumptions, inception date, and
   metric definitions above are frozen. Errors, if found, are corrected by a documented
   amendment that preserves the original record, never by silent restatement.
6. Evaluation cadence: monthly, in the letter series (`docs/letters/`). Interim readings carry
   no decision authority.

## Implementation record (2026-08-06)

Recorded at first implementation, before any benchmark computation over real governed data.
These details complete the measurement rules above and are frozen with them.

- Engine: `research/live_benchmarks.py` (deterministic, stdlib-only, fail-closed).
- Runner: `scripts/run_core_v1_live_benchmarks.py` — computes every artifact twice in-memory
  and fails closed unless byte-identical; writes `benchmark_a_nav.csv`, `benchmark_b_nav.csv`,
  `benchmark_metrics.json`, and `manifest.json` (source paths, SHA-256, frozen parameters)
  under `artifacts/core_v1_live_benchmarks/`.
- Synthetic validation: `tests/test_live_benchmarks.py` — 16 tests including hand-computed
  scenarios; a full pass is required before any governed run (synthetic PASS recorded
  2026-08-06, 16 passed).
- Crypto daily close rule: for hourly sources, the daily close of a UTC day is the close of
  the last hourly bar observed within that day; days with no bars are absent and are never
  interpolated or repaired.
- Valuation calendar: union of all asset session dates from inception; assets without a fresh
  close on a valuation date are carried at their last known close.
- Rebalance day: the first session of each calendar month (after the inception month) on which
  every equity-family asset in the benchmark has a fresh close.
- Initial deployment: each sleeve's traded notional is `weight x capital / (1 + fee)` so that
  cash is exactly conserved; rebalance fees are charged on absolute turnover notional with
  targets sized against fee-adjusted NAV.
- Fee assumptions (matching `scripts/export_core_v1_canonical_sleeve_matrix.py` defaults):
  crypto 0.0006, equity/gold 0.0001, cash 0.
- Metric definitions: annualization over 365.25 days; Sharpe from valuation-calendar simple
  returns with sample standard deviation, zero benchmark; Calmar null when maximum drawdown
  is zero.

The governed run is executed where the governed data lives:

    uv run python scripts/run_core_v1_live_benchmarks.py --end <period-end> \
        --btc-data <btc hourly csv> --eth-data <eth hourly csv> \
        --spy-data data/SPY_1D.csv --qqq-data data/QQQ_1D.csv --gld-data data/GLD_1D.csv

Its artifact digests are recorded in the letter that first reports the results.

## Authorization boundary

This registration authorizes benchmark computation and reporting only. It does not authorize
any change to Core v1, the paper runtime, orders, exposure, NAV handling, or production
behavior, and it is not a performance claim.
