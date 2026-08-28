---
name: monthly-letter
description: Produce an Itera Dynamics monthly letter. Runs the governed benchmark and comparison runners against the paper export, fills the standing template, records artifact digests, and checks the pre-registered degradation triggers. Use at month end, or whenever a letter, performance report, or benchmark-relative reading is requested.
---

# Producing a monthly letter

The letter series is the Path 2 deliverable. Its value is entirely in being **boring,
unbroken, and never restated** — a twelve-month run of dull letters is a track record; a
brilliant letter that revises last month's numbers is not.

Letters live in `docs/letters/YYYY-MM_LETTER_NNN.md`. Read the two most recent before writing;
they are the format authority. The numbering is sequential across the whole series, not per
month.

## Non-negotiables

- **Never restate a published letter.** Corrections go in the *next* letter, named as
  corrections. Published letters are immutable.
- **Everything is paper.** Say so in the header. Never present historical research results as
  live performance.
- **The backtest is not an expectation.** Sharpe 1.34 is a selection-biased ceiling. If it
  appears at all, it appears with that label.
- **Report before interpreting, and refuse to interpret when the sample cannot support it.**
  Letter #002 reported 25 valuation dates and stated plainly that no interpretation was
  warranted. That refusal is the house style, not a hedge.
- **Digests go in the letter.** Every figure traces to a named artifact and its SHA-256.

## Step 1 — Get the paper export

The runtime host is the operator's machine. They run:

```
uv run python scripts/export_core_v1_paper_data.py
```

and the export directory is copied to wherever the letter is being produced. Nothing in this
skill regenerates paper NAV — the runtime's export is the record.

## Step 2 — Extend the governed price sources

The benchmark end date is bounded by the **shortest** governed source, not by the calendar.
Letter #002 reported through 2026-07-31 for exactly this reason. Before running, confirm every
source covers the intended period end:

- `data/btcusd_*.csv`, `data/ethusd_*.csv` (hourly, crypto)
- `data/SPY_1D.csv`, `data/QQQ_1D.csv`, `data/GLD_1D.csv` (daily)

The engine fails closed with `SOURCE_COVERAGE_FAILURE` if a source is stale beyond
`--max-staleness-days`. That is correct behaviour — fetch the data, never widen the tolerance
to make a run pass.

If sources cannot reach month end, the letter reports the shorter window and **says why in the
letter**, stating that the window is the mechanical consequence of the source endpoint and was
not chosen after seeing results.

## Step 3 — Run the two governed runners

```
uv run python scripts/run_core_v1_live_benchmarks.py --end YYYY-MM-DD
uv run python scripts/run_core_v1_live_comparison.py --paper-export <export-dir>
```

Both verify replay identity by computing every artifact twice in memory and comparing bytes.
Both must report `status: PASS`. A failure is a finding, not an obstacle: diagnose it, and if
it affects a previously published figure, that is a correction for this letter.

Artifacts land in `artifacts/core_v1_live_benchmarks/` and
`artifacts/core_v1_live_comparison/`. Collect the SHA-256 of each file from the run output or
the manifests.

## Step 4 — Check the pre-registered triggers

Against `docs/research/CORE_V1_LIVE_EXPECTATION_AND_DEGRADATION_BAND.md`, state explicitly
whether each of T1–T4 has fired, is approached, or is untouched. Do this every letter, even
when the answer is "none", because the value of a pre-commitment is the record of it being
checked when it was inconvenient.

Never move a trigger threshold in the direction of comfort. If a trigger fires, the letter
reports that it fired.

## Step 5 — Write the letter

Standing template, established in Letter #001:

**Header** — letter number, issue date, period reported, portfolio and canonical scenario,
`Status: PAPER`.

**Performance** — the three series (Core v1 paper, Benchmark A static twin, Benchmark B 60/40)
under identical metric definitions, rebased to a common start. Report final NAV, return, max
drawdown, and the spreads. Note that the paper series carries realized fills and costs while
the benchmarks carry modeled costs, and that the difference is not adjusted for.

**Positioning** — sleeve states at period end, which filters are engaged, cash fraction,
allocation drift versus target.

**Operations** — signal events, sleeve decisions, market-data rows, fills, incidents,
interventions. Incidents are reported even when self-resolved with no impact.

**Research** — what closed this period. Include defects found and closed *before* publication;
that is evidence of the process working, and concealing it would be the actual failure.

**Governed artifact identities** — every artifact filename and its SHA-256.

**Next period** — the specific committed items.

Close with the standing footer noting the template and the no-restatement rule.

## Interpretation discipline

Sample sizes here are small and will be for a year. The honest sentence is usually some form of
"this is recorded to establish the measurement, not to evaluate the strategy."

Descriptive facts may be stated without inference — e.g. "the gold sleeve was flat in cash for
the entire window while Benchmark A held 20% GLD statically" — as long as no causal claim is
attached. If a favourable extended window exists but was not the governed period, say so
explicitly rather than either hiding it or using it; Letter #002 did exactly this.

## Commit

Scope the commit explicitly — `git add docs/letters/<file>` and the specific artifacts, never
`git add -A`. Artifacts under `artifacts/` are gitignored; the digests in the letter are their
record.
