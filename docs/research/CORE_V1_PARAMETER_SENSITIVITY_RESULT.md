# Core v1 Parameter Sensitivity Result — 2026-08-12

## Purpose

Days 1–30 item 2 of `docs/ITERA_DESTINATION_CHARTER.md`'s 90-day plan: a report-only,
one-at-a-time perturbation of Core v1's ten frozen constants with no a priori justification,
run against the canonical 2020–2025 walk-forward. This does not authorize, and was never
intended to authorize, any change to Core v1. Under the One Rule, Core v1's parameters remain
frozen regardless of this result.

The question was narrow: does the backtest sit on a knife edge? A strategy whose performance
collapses under a small perturbation is fitted to its sample; one that degrades smoothly and
survives nearby values is expressing a real effect, whatever its selection history.

## Result

21 variants (baseline + 2 perturbations × 10 parameters), full six-fold canonical walk-forward,
`artifacts/core_v1_parameter_sensitivity/20260812T122526Z_core-v1-parameter-sensitivity/`.

| variant | CAGR% | Sharpe | Calmar | MaxDD% | ΔSharpe |
|---|---:|---:|---:|---:|---:|
| baseline | 19.93 | 1.319 | 1.208 | -16.50 | 0.000 |
| equity_sma_period=150 | 20.07 | 1.328 | 1.193 | -16.82 | +0.009 |
| equity_sma_period=200 | 19.90 | 1.315 | 1.138 | -17.49 | -0.004 |
| equity_fast_sma=40 | 19.93 | 1.319 | 1.208 | -16.50 | +0.000 |
| equity_fast_sma=60 | 19.93 | 1.319 | 1.208 | -16.50 | +0.000 |
| equity_derisk_exposure=0.4 | 19.93 | 1.319 | 1.208 | -16.50 | +0.000 |
| equity_derisk_exposure=0.6 | 19.93 | 1.319 | 1.208 | -16.50 | +0.000 |
| equity_entry_buffer=0.0025 | 20.03 | 1.325 | 1.199 | -16.71 | +0.006 |
| equity_entry_buffer=0.01 | 19.60 | 1.296 | 1.164 | -16.84 | -0.022 |
| gold_sma_period=175 | 20.00 | 1.324 | 1.211 | -16.52 | +0.005 |
| gold_sma_period=225 | 20.36 | 1.358 | 1.265 | -16.10 | +0.039 |
| v11_soft_threshold=0.45 | 19.67 | 1.335 | 1.256 | -15.67 | +0.016 |
| v11_soft_threshold=0.75 | 20.40 | 1.316 | 1.225 | -16.65 | -0.003 |
| v11_hard_threshold=0.85 | 19.82 | 1.324 | 1.203 | -16.47 | +0.006 |
| v11_hard_threshold=1.15 | 19.78 | 1.310 | 1.201 | -16.46 | -0.009 |
| v11_soft_entry_cap=0.3 | 19.97 | 1.327 | 1.214 | -16.45 | +0.008 |
| v11_soft_entry_cap=0.5 | 19.81 | 1.307 | 1.198 | -16.54 | -0.011 |
| v11_para_sma_days=300 | 19.93 | 1.319 | 1.208 | -16.50 | +0.000 |
| v11_para_sma_days=430 | 19.93 | 1.319 | 1.208 | -16.50 | +0.000 |
| v9_sma_days=150 | 19.93 | 1.319 | 1.208 | -16.50 | +0.000 |
| v9_sma_days=200 | 19.93 | 1.319 | 1.208 | -16.50 | +0.000 |

## Scope actually exercised: 6 of 10 parameters

Four rows show `ΔSharpe = +0.000` at every perturbed value, which is a different claim than "no
effect" — it means the perturbation never reached the code path that produces NAV. Two distinct
mechanisms produce this, established by direct code inspection and by two read-only diagnostics
(`scripts/diagnose_equity_derisk_reachability.py`, `scripts/diff_sensitivity_variant_nav.py`),
not inferred from the flat rows themselves.

**`v9_sma_days`, `v11_para_sma_days` — structurally dead in this harness, for any data.**
Both constants live exclusively inside an "asset-local fallback" branch (`trend_following_v9.py`
`_asset_local_above_sma175`, `trend_following_v11.py` `_asset_local_extension`) that only
executes when the canonical macro-state columns (`btc_above_sma175`, `btc_extension_sma365`)
are absent from the sleeve dataframe. `research/harness/cross_asset_state.inject_btc_macro_state`
unconditionally injects both columns for every trend sleeve in this harness
(`run_core_v1_sleeve_contribution_audit.py:220-222`). The fallback branch, and both constants
with it, cannot execute regardless of price history. This is the documented intended design —
the v11 docstring states "canonical research runs should show only `explicit_btc`" — not a
defect.

**`equity_fast_sma`, `equity_derisk_exposure` — dead in this harness due to an engine gap,
live in the paper runtime.** `equity_sma175_v3.py`'s partial de-risk branch issues
`StrategyIntent(action=Action.HOLD, desired_exposure_frac=DERISKED_EXPOSURE, ...)`. Every other
`HOLD` intent in the strategy suite (all ~20 modules checked) sets
`desired_exposure_frac=ctx.current_exposure_frac` — the universal convention that "hold" means
"echo current exposure." `research/harness/backtest_engine.py:230-234` exploits that convention
as a shortcut: `elif intent.action == Action.HOLD: target_exposure = current_exposure`, never
reading `desired_exposure_frac` at all. The de-risk branch is the sole exception to the
convention in the entire codebase, and the shortcut silently discards it.

- `diagnose_equity_derisk_reachability.py` confirmed the branch's necessary market condition
  (SPY/QQQ above SMA175, below its fast SMA, while BTC extension exceeds 100% of its 365-day
  SMA) occurs on real sessions — 23–27 for QQQ, 1–6 for SPY, concentrated late Feb/early Mar
  2021.
- `diff_sensitivity_variant_nav.py` then confirmed the resulting NAV is byte-identical to
  baseline across all 52,374 hourly rows for both perturbed constants — not a small,
  rounded-away effect, but zero, confirming the engine-level explanation over a data-reachability
  one.

`scripts/run_core_v1_paper_live.py:704` reads `desired_exposure_frac` unconditionally for every
action, so the live paper runtime **has** executed this branch as coded since inception; the
backtest engine has never modeled it.

## What this does and does not establish

**Established, on the 6 parameters actually exercised** (`equity_sma_period`,
`equity_entry_buffer`, `gold_sma_period`, and the three `v11` threshold/cap constants): no
collapse. ΔSharpe ranges from -0.022 to +0.039 against a baseline of 1.319 — smooth degradation,
no knife edge. `equity_entry_buffer=0.01` is the worst case; `gold_sma_period=225` is the best.
Per this document's own governing constraint, **a higher score is not a finding and authorizes
no change** — `gold_sma_period=225` scoring above baseline is not evidence Core v1 should be
retuned to 225.

**Not established:** anything about the 4 excluded parameters' fragility, since they were never
tested. This pass is single-parameter perturbation only; it says nothing about joint/correlated
shifts across multiple constants at once.

**Separately, and outside this pass's original scope:** the backtest/audit engine and the live
paper runtime have not been simulating identical logic at the equity de-risk margin since
inception. The live paper NAV record is not affected — the live runtime reads the strategy
correctly. The canonical backtest ceiling (Sharpe 1.34, `CORE_V1_LIVE_EXPECTATION_AND_
DEGRADATION_BAND.md`) and every WFO/audit artifact computed through `backtest_engine.py` carry
an unquantified asterisk: bounded to one branch of one sleeve, a handful of sessions across six
years, but not yet sized. No prior published result is retracted by this — the gap was never
previously known to exist, so nothing was claimed about the de-risk branch's contribution one
way or the other. Whether and how to correct `backtest_engine.py`, and whether to re-run any
canonical artifact against the correction, is a separate governed decision, not resolved here.

## Closure

The 90-day plan's Days 1–30 item 2 is complete. The direction question it was chartered to
answer — see `docs/ITERA_DESTINATION_CHARTER.md`'s "Pending evidence" section — is answered:
Sharpe holds across every parameter this pass could actually exercise. Under that section's own
logic, improvement is not available through retuning; the legitimate direction is a successor
addressing a named structural deficiency, which is what Campaign #53 is already pursuing.
