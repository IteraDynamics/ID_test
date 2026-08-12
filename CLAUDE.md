# Itera Dynamics — operating context

Read this before proposing or implementing anything. The governance in `docs/` is the
authority; this file is the index and the non-negotiables.

## What this is

A solo-operated quantitative research and paper-trading system. **Core v1** is a six-sleeve
trend-filtered portfolio (BTC 4H, ETH 1H, ETH 4H, SPY, QQQ, GLD) running unattended in paper
since **2026-07-07**. Research proceeds as numbered, pre-registered campaigns.

## The One Rule

**The moonshot never touches the floor.**

Core v1's parameters, weights and logic are **frozen**. They change only through full
governance. A live record is only meaningful if the measured thing stays fixed; retuning resets
the record and invalidates the pre-registered degradation band.

Clarified 2026-08-11: this forbids *mutating* Core v1. It does **not** forbid building a
successor. A Core v2 developed in parallel — own charter, own runtime, own inception — costs the
existing record nothing. But a successor must address a **named structural deficiency**, not
re-parameterise. Changing SMA 175 to 200 is retuning under another name and is prohibited.

If asked to "improve returns", do not tune. See
`docs/ITERA_DESTINATION_CHARTER.md`.

## Standing research amendments

All campaigns after 2026-08-06. Full text: `docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md`.

1. **Power analysis mandatory.** No campaign runs below ~50% power at plausible effect sizes.
   An underpowered null is not a research result.
2. **Multiplicity conservatism belongs at confirmation.** Discovery uses FDR or top-k; the
   untouched holdout carries the strict standard. The holdout must be exercisable.
3. **One living document per campaign**, `docs/research/CAMPAIGN_<N>_<NAME>.md`. A spec may not
   be frozen the same session it is drafted.
4. **Horizon feasibility precedes specification.** The effect's decay horizon must exceed the
   measured runtime cadence by a stated margin.
5. **Tradeability precedes specification.** Name the instrument, the venue this operator can
   verifiably trade it on, and whether research source and execution venue differ.

## Hard operating facts

Measured, not assumed. Re-measure before citing; these can change.

- **Runtime cadence: ~1.5–1.7 bar periods behind bar close**, consistently across timeframes
  (808 cycles, 2026-08-10). This infrastructure supports multi-day signals well and sub-daily
  signals badly. It is why Jump Risk was retired.
- **Jurisdiction: US.** Binance returns HTTP 451 and Bybit 403. Reachable: Deribit (deepest
  history), OKX (~92-day cap), Hyperliquid, dYdX, Coinbase.
- **Execution venue: Coinbase Derivatives Exchange (CDE).** Note CDE ≠ Coinbase International
  (INTX); they are different venues with different products. CDE lists perpetual-style futures
  as very-long-dated contracts (`BIP-20DEC30-CDE` is "BTC PERP"). Derivatives eligibility is
  **not yet completed**.
- **Capital scale ~$100k.** Assess economic materiality in dollars before chartering. Every
  edge examined so far lands at roughly $400–1,500/yr. Say so plainly.
- **Core v1 backtest (~20% CAGR, Sharpe 1.34) is a selection-biased ceiling**, not an
  expectation. Live expectation ~0.7–0.9 Sharpe; drawdown planning assumption -26% to -35%.
  Never restate the backtest as an expectation. See
  `docs/research/CORE_V1_LIVE_EXPECTATION_AND_DEGRADATION_BAND.md`.
- **`research/harness/backtest_engine.py` silently discards `desired_exposure_frac` on `HOLD`
  intents** (line ~232) — a shortcut that works because every strategy but one echoes current
  exposure on ordinary holds. `equity_sma175_v3`'s partial de-risk branch is the sole exception,
  so the backtest/audit/WFO engine has never modeled it; the live paper runtime (which reads the
  field unconditionally) has run it as coded since inception. Live record unaffected; canonical
  backtest ceiling carries a narrow, unquantified asterisk. Details and scope:
  `docs/research/CORE_V1_PARAMETER_SENSITIVITY_RESULT.md`. Not yet fixed — correcting it changes
  every canonical artifact retroactively and is its own governed decision.

## Retired — do not revive

- **Jump Risk Engine v0** — research validated and lookahead-free, but 98% of its edge expires
  by the second bar and the runtime is ~1.5 bars late. Reopening requires independently
  measured cadence of ≤1 effective bar.
- **Trend Persistence Engine v0** — all mappings degraded Core at research lag, and its 3h
  "central finding" candidates consume 53% of their horizon in decision lag. Any future work is
  restricted to the 60h+ candidates and must be chartered as new research.

## Commands

```bash
uv run python -m pytest tests/ -q          # correct invocation
uv run pytest                              # WRONG - resolves a pytest outside the venv
                                           # and reports phantom collection errors
```

Long-running: `scripts/export_core_v1_canonical_sleeve_matrix.py` (~20 min),
`scripts/run_core_v1_parameter_sensitivity.py` (~2 h),
`scripts/run_jump_risk_timing_audit.py` (~30 min).

## Conventions

- Research code is **stdlib-only where practical**, fail-closed, deterministic, replay-verified.
- Canonical artifacts are LF-only with SHA-256 digests; runners verify replay identity by
  computing twice and comparing bytes.
- Governance documents are **append-only**. Closed campaigns are immutable.
- Data lives locally on the operator's machines; the repo holds one 2026 BTC file.
  `artifacts/` and `data/*.csv` are gitignored.
- Scope commits explicitly. Do not `git add -A` — it has twice swept unintended `uv.lock`
  changes into commits.

## Two habits that have repeatedly mattered

**A check that cannot fail is not evidence.** The Jump Risk timing audit passed for months
because both sides of its comparison were derived from the same value. When writing any
validation, prove it can fail — ideally with a canary that must fire on every run.

**Measure the constraint before doing the work.** Four feasibility gates — latency, venue
reachability, tradeability, data availability — have each redirected or killed a campaign
*before* the expensive part. Run them first.
