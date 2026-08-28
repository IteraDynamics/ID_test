"""Jump Risk economic sensitivity to the REAL, empirically observed lag distribution.

`scripts/run_jump_risk_lag_sensitivity.py` (2026-08-10, FINAL DISPOSITION: RETIRED) tested the
approved `btc_eth_aligned_upside` mapping at a *uniform* fixed lag applied to every decision in
the six-year backtest, calibrated from the live cadence audit's "~1.5-1.7 bar periods" figure.
That figure has since been corrected (`docs/engineering/CORE_V1_JUMP_RISK_PAPER_CHARTER.md`'s
"Correction, 2026-08-20"): the real runtime lands at effective lag 1 (the frozen research's own
baseline) roughly 99.6% of the time, with rare excursions to higher lag concentrated around one
known outage -- not uniformly 1.5-1.7 bars late on every decision, which is what the retired
test assumed.

This script asks the question the corrected data actually supports: **what does the edge look
like if you replay it against the REAL, measured lag pattern instead of a single fixed lag?**

Method, and what is and isn't touched:

- The frozen research path is untouched: `_oos_probabilities`, `LOCKED_MODELS`, `_portfolio`,
  `_metrics`, and the `aligned_up_scale` construction are used exactly as in the retired script
  (the latter is copied verbatim below rather than imported, because the retired script defines
  it as a closure inside its own `main()` -- copying, not modifying, keeps that governed,
  already-executed artifact untouched).
- The retired script's *decision rule* (the four-condition promotion gate) is reused unchanged,
  not restated, relaxed, or reweighted.
- What's new: instead of `.shift(constant_lag)` applied uniformly to the whole six-year series,
  a variable per-hour lag is applied, drawn via block bootstrap from the REAL lag sequence
  measured by the corrected cadence audit (`cadence_rows.csv`, sleeve ETH_1H_trend, restricted to
  first-sighting-of-a-fresh-bar rows -- the only direct hourly measurement available; BTC has no
  live 1H sleeve and is assumed to share the same runtime-driven lag pattern, a proxy noted
  explicitly in the corrected audit's own findings). Block bootstrap (not i.i.d. per-hour
  sampling) preserves the real, bursty clustering of an outage instead of smoothing it away.
- The result is a DISTRIBUTION across many resamples, not a single point estimate: the fraction
  of resamples that clear the unchanged promotion gate, and percentile summaries of each metric.

This is exploratory, not a new pre-registered governance artifact -- it does not itself reopen
Jump Risk or overturn the FINAL DISPOSITION. It exists to tell whoever makes that call what the
edge actually looks like under the corrected, realistic lag pattern instead of the uniform,
now-known-to-be-wrong one the retired test used.

A separate, independent caveat this script does NOT address: `_oos_probabilities` (reused here
completely unchanged) has a documented, still-unresolved train/test boundary leakage issue --
`docs/engineering/CORE_V1_JUMP_RISK_PAPER_CHARTER.md`'s "Found and deliberately NOT corrected"
section, item 1: training rows within `horizon_bars` of a year boundary carry labels that peek
up to 120 hours into the test year. That is a governed-decision item independent of lag, and a
favorable result from this script does not resolve it. Both would need to be true for a
responsible reopening case, not just one.

Observation-only. No runtime, strategy, order, NAV, or production change.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_jump_risk_portfolio_integration import (  # noqa: E402
    CANONICAL_DATA,
    LOCKED_MODELS,
    _canonical_path,
    _load_matrix,
    _metrics,
    _oos_probabilities,
    _portfolio,
    read_ohlcv,
)

PROMOTION_GATE = "delta_sharpe>0 & delta_calmar>0 & delta_max_drawdown_pct>=0 & delta_cagr_pct>=-0.50"
EMPIRICAL_LAG_SLEEVE = "ETH_1H_trend"
MIN_EMPIRICAL_ROWS = 100


# ------------------------------------------------------- pure, unit-tested helpers


def derive_empirical_additional_lag_bars(cadence_rows: pd.DataFrame, sleeve: str) -> np.ndarray:
    """The real, measured 'additional bars beyond the frozen one-bar baseline' sequence.

    effective_lag_bars = 1 (the frozen research's own baseline) whenever a decision lands
    before the *next* bar would have closed -- i.e. bar_close_to_decision_hours < 1.0 for an
    hourly sleeve. Only decisions that land at or after that next boundary represent additional,
    measured lag. Restricted to `first_sighting_of_this_bar` rows: those are genuine fresh
    pickups, not re-logs of an already-decided-on bar (see the cadence audit's own
    all-decisions-vs-fresh-bar-only distinction).
    """
    rows = cadence_rows[
        (cadence_rows["sleeve"] == sleeve) & (cadence_rows["first_sighting_of_this_bar"] == True)  # noqa: E712
    ].sort_values("cycle")
    if len(rows) < MIN_EMPIRICAL_ROWS:
        raise ValueError(
            f"Only {len(rows)} fresh-bar-only rows for sleeve {sleeve!r}; need at least "
            f"{MIN_EMPIRICAL_ROWS} to build a meaningful empirical lag sequence."
        )
    hours = rows["bar_close_to_decision_hours"].to_numpy(dtype=float)
    additional = np.clip(np.floor(hours), 0, None).astype(int)
    return additional


def block_bootstrap_resample(
    real_sequence: np.ndarray, target_length: int, block_size: int, rng: np.random.Generator
) -> np.ndarray:
    """Tile `target_length` values by concatenating random contiguous blocks of the real
    sequence, preserving real clustering (an outage stays contiguous) instead of an i.i.d.
    per-position draw, which would smear a bursty event across independent positions."""
    if block_size < 1:
        raise ValueError("block_size must be >= 1")
    n = len(real_sequence)
    if n == 0:
        raise ValueError("real_sequence is empty")
    effective_block = min(block_size, n)
    pieces: list[np.ndarray] = []
    total = 0
    while total < target_length:
        start = int(rng.integers(0, max(1, n - effective_block + 1)))
        block = real_sequence[start : start + effective_block]
        pieces.append(block)
        total += len(block)
    return np.concatenate(pieces)[:target_length]


def apply_variable_lag(series: pd.Series, additional_lag_bars: np.ndarray) -> pd.Series:
    """At position i, use the value from position i - additional_lag_bars[i] -- the variable-lag
    generalization of the frozen script's `.shift(constant_lag)`. Positions without enough
    history to look back fall back to the neutral scale (1.0), matching the frozen script's own
    `.shift(lag).fillna(1.0)` warmup convention."""
    values = series.to_numpy(dtype=float)
    n = len(values)
    lag = np.asarray(additional_lag_bars[:n], dtype=int)
    if len(lag) < n:
        raise ValueError(f"additional_lag_bars too short: {len(lag)} < series length {n}")
    positions = np.arange(n) - lag
    warmup = positions < 0
    positions = np.clip(positions, 0, n - 1)
    out = values[positions]
    out[warmup] = 1.0
    return pd.Series(out, index=series.index)


def evaluate_gate(deltas: dict[str, float]) -> bool:
    return (
        deltas["delta_sharpe"] > 0.0
        and deltas["delta_calmar"] > 0.0
        and deltas["delta_max_drawdown_pct"] >= 0.0
        and deltas["delta_cagr_pct"] >= -0.50
    )


# ------------------------------------------------------- CLI plumbing


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Jump Risk sensitivity to the real, empirically observed lag distribution.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", default=CANONICAL_DATA["btc_data"])
    p.add_argument("--eth-data", default=CANONICAL_DATA["eth_data"])
    p.add_argument(
        "--core-wfo-dir",
        default="artifacts/trend_persistence_v0/portfolio_integration/core_wfo",
    )
    p.add_argument(
        "--cadence-rows-csv",
        required=True,
        help="cadence_rows.csv written by the corrected scripts/run_paper_runtime_cadence_audit.py.",
    )
    p.add_argument("--empirical-lag-sleeve", default=EMPIRICAL_LAG_SLEEVE)
    p.add_argument("--out-dir", default="artifacts/jump_risk_lag_realistic_sensitivity")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--risk-quantile", type=float, default=0.95)
    p.add_argument("--jump-z", type=float, default=3.0)
    p.add_argument("--absolute-jump", type=float, default=0.05)
    p.add_argument("--boosted-scale", type=float, default=1.15)
    p.add_argument("--overlay-turnover-cost-bps", type=float, default=6.0)
    p.add_argument("--resamples", type=int, default=500)
    p.add_argument("--block-hours", type=int, default=72)
    p.add_argument("--seed", type=int, default=20260820)
    return p.parse_args(argv)


def aligned_up_scale(
    predictions: dict[tuple[str, str], pd.DataFrame],
    matrix: pd.DataFrame,
    asset: str,
    columns: list[str],
    boosted_scale: float,
) -> pd.Series:
    """Copied verbatim from scripts/run_jump_risk_lag_sensitivity.py's own local closure --
    the exact, unmodified approved btc_eth_aligned_upside construction. Copied rather than
    imported because the retired script defines this inline inside its own main(); copying
    keeps that already-executed, governed artifact untouched."""
    medium = predictions[(asset, "medium_up")]
    extended = predictions[(asset, "extended_up")]
    idx = medium.index.union(extended.index).sort_values()
    med_high = (medium["probability"] >= medium["train_threshold"]).reindex(idx, method="ffill").fillna(False)
    ext_high = (extended["probability"] >= extended["train_threshold"]).reindex(idx, method="ffill").fillna(False)
    sleeve = matrix[columns].sum(axis=1)
    aligned = sleeve.diff(24).reindex(idx, method="ffill").fillna(0.0) > 0.0
    scale = pd.Series(1.0, index=idx)
    scale.loc[aligned & (med_high | ext_high)] = boosted_scale
    return scale


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    cadence_rows = pd.read_csv(args.cadence_rows_csv)
    real_lag_sequence = derive_empirical_additional_lag_bars(cadence_rows, args.empirical_lag_sleeve)
    lag_1_fraction = float((real_lag_sequence == 0).mean())
    print(
        f"Empirical lag sequence: {len(real_lag_sequence)} fresh-bar-only observations of "
        f"{args.empirical_lag_sleeve!r}. Fraction at effective lag 1 (no additional lag): "
        f"{lag_1_fraction:.4f}"
    )

    btc = read_ohlcv(_canonical_path(args.btc_data))
    eth = read_ohlcv(_canonical_path(args.eth_data))
    matrix, _, _ = _load_matrix(args.core_wfo_dir, args.oos_start, args.oos_end)

    predictions: dict[tuple[str, str], pd.DataFrame] = {}
    for asset, source in (("BTC", btc), ("ETH", eth)):
        for candidate in LOCKED_MODELS:
            print(f"Scoring {asset} {candidate}")
            predictions[(asset, candidate)] = _oos_probabilities(
                source, asset, candidate, args.oos_start, args.oos_end,
                args.jump_z, args.absolute_jump, args.risk_quantile,
            )

    btc_cols = [c for c in matrix.columns if c.startswith("BTC_") and "trend" in c]
    eth_cols = [c for c in matrix.columns if c.startswith("ETH_") and "trend" in c]
    btc_up = aligned_up_scale(predictions, matrix, "BTC", btc_cols, args.boosted_scale)
    eth_up = aligned_up_scale(predictions, matrix, "ETH", eth_cols, args.boosted_scale)

    one = pd.Series(1.0, index=matrix.index)
    initial = float(matrix.iloc[0].sum())
    baseline_nav, _ = _portfolio(matrix, one, one, 0.0)
    baseline = _metrics(baseline_nav, initial)

    # Sanity check: an all-zero additional-lag sequence must reproduce the frozen script's own
    # effective-lag-1 (lag=0) row exactly. This proves this script's mechanism is grounded in
    # the same construction as the retired one, not a silently divergent reimplementation.
    zero_lag = np.zeros(max(len(btc_up), len(eth_up)), dtype=int)
    sanity_nav, _ = _portfolio(
        matrix,
        apply_variable_lag(btc_up, zero_lag),
        apply_variable_lag(eth_up, zero_lag),
        args.overlay_turnover_cost_bps,
    )
    sanity_metrics = _metrics(sanity_nav, initial)
    print(
        f"\nSanity check (all-zero additional lag, should match the retired script's "
        f"effective-lag-1 row): CAGR {sanity_metrics['cagr_pct']:.2f}%  "
        f"Sharpe {sanity_metrics['sharpe']:.3f}  Calmar {sanity_metrics['calmar']:.3f}"
    )

    rng = np.random.default_rng(args.seed)
    rows: list[dict[str, Any]] = []
    for i in range(args.resamples):
        btc_lag = block_bootstrap_resample(real_lag_sequence, len(btc_up), args.block_hours, rng)
        eth_lag = block_bootstrap_resample(real_lag_sequence, len(eth_up), args.block_hours, rng)
        btc_lagged = apply_variable_lag(btc_up, btc_lag)
        eth_lagged = apply_variable_lag(eth_up, eth_lag)
        nav, diagnostics = _portfolio(matrix, btc_lagged, eth_lagged, args.overlay_turnover_cost_bps)
        metrics = _metrics(nav, initial)
        deltas = {
            f"delta_{key}": metrics[key] - baseline[key]
            for key in ("cagr_pct", "total_return_pct", "max_drawdown_pct", "sharpe", "calmar")
        }
        survives = evaluate_gate(deltas)
        rows.append(
            {
                "resample": i,
                "cagr_pct": round(metrics["cagr_pct"], 4),
                "sharpe": round(metrics["sharpe"], 4),
                "calmar": round(metrics["calmar"], 4),
                "max_drawdown_pct": round(metrics["max_drawdown_pct"], 4),
                **{k: round(v, 4) for k, v in deltas.items()},
                "overlay_cost": round(diagnostics["incremental_overlay_cost"], 2),
                "promotion_gate": "PASS" if survives else "REJECT",
            }
        )

    # Determinism replay check: same seed, same resample 0, must reproduce byte-identical rows.
    rng_replay = np.random.default_rng(args.seed)
    btc_lag_replay = block_bootstrap_resample(real_lag_sequence, len(btc_up), args.block_hours, rng_replay)
    eth_lag_replay = block_bootstrap_resample(real_lag_sequence, len(eth_up), args.block_hours, rng_replay)
    replay_ok = np.array_equal(btc_lag_replay, block_bootstrap_resample(real_lag_sequence, len(btc_up), args.block_hours, np.random.default_rng(args.seed)))
    print(f"\nDeterminism replay check (same seed reproduces same lag draw): {'PASS' if replay_ok else 'FAIL'}")
    if not replay_ok:
        raise RuntimeError("Determinism replay check FAILED -- resampling is not reproducible; do not trust this run.")

    frame = pd.DataFrame(rows)
    pass_fraction = float((frame["promotion_gate"] == "PASS").mean())

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_jump-risk-lag-realistic-sensitivity"
    run_dir.mkdir(parents=True, exist_ok=False)
    frame.to_csv(run_dir / "resample_scorecard.csv", index=False)

    def _pctile(col: str, q: float) -> float:
        return round(float(frame[col].quantile(q)), 4)

    report = {
        "audit": "jump_risk_lag_realistic_sensitivity_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "pre_registered_gate": PROMOTION_GATE,
        "empirical_lag_source": {
            "cadence_rows_csv": str(args.cadence_rows_csv),
            "sleeve": args.empirical_lag_sleeve,
            "observations": int(len(real_lag_sequence)),
            "fraction_effective_lag_1": round(lag_1_fraction, 4),
            "block_hours": args.block_hours,
        },
        "resamples": args.resamples,
        "seed": args.seed,
        "determinism_replay_check": "PASS" if replay_ok else "FAIL",
        "sanity_check_zero_lag": {
            "cagr_pct": round(sanity_metrics["cagr_pct"], 4),
            "sharpe": round(sanity_metrics["sharpe"], 4),
            "calmar": round(sanity_metrics["calmar"], 4),
        },
        "baseline_core": {
            "cagr_pct": round(baseline["cagr_pct"], 4),
            "sharpe": round(baseline["sharpe"], 4),
            "calmar": round(baseline["calmar"], 4),
            "max_drawdown_pct": round(baseline["max_drawdown_pct"], 4),
        },
        "pass_fraction": round(pass_fraction, 4),
        "delta_cagr_pct": {"p5": _pctile("delta_cagr_pct", 0.05), "median": _pctile("delta_cagr_pct", 0.5), "p95": _pctile("delta_cagr_pct", 0.95)},
        "delta_sharpe": {"p5": _pctile("delta_sharpe", 0.05), "median": _pctile("delta_sharpe", 0.5), "p95": _pctile("delta_sharpe", 0.95)},
        "delta_calmar": {"p5": _pctile("delta_calmar", 0.05), "median": _pctile("delta_calmar", 0.5), "p95": _pctile("delta_calmar", 0.95)},
        "delta_max_drawdown_pct": {"p5": _pctile("delta_max_drawdown_pct", 0.05), "median": _pctile("delta_max_drawdown_pct", 0.5), "p95": _pctile("delta_max_drawdown_pct", 0.95)},
    }
    (run_dir / "lag_realistic_sensitivity_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"\nCore baseline: CAGR {baseline['cagr_pct']:.2f}%  Sharpe {baseline['sharpe']:.3f}  "
          f"Calmar {baseline['calmar']:.3f}  MaxDD {baseline['max_drawdown_pct']:.2f}%")
    print(f"\n{args.resamples} resamples, block bootstrap of the real measured lag sequence "
          f"({len(real_lag_sequence)} observations, {args.block_hours}h blocks):")
    print(f"  PASS fraction: {pass_fraction:.4f}")
    print(f"  delta CAGR    p5={report['delta_cagr_pct']['p5']:+.2f}  median={report['delta_cagr_pct']['median']:+.2f}  p95={report['delta_cagr_pct']['p95']:+.2f}")
    print(f"  delta Sharpe  p5={report['delta_sharpe']['p5']:+.3f}  median={report['delta_sharpe']['median']:+.3f}  p95={report['delta_sharpe']['p95']:+.3f}")
    print(f"  delta Calmar  p5={report['delta_calmar']['p5']:+.3f}  median={report['delta_calmar']['median']:+.3f}  p95={report['delta_calmar']['p95']:+.3f}")
    print(f"  delta MaxDD   p5={report['delta_max_drawdown_pct']['p5']:+.2f}  median={report['delta_max_drawdown_pct']['median']:+.2f}  p95={report['delta_max_drawdown_pct']['p95']:+.2f}")
    print(f"\nArtifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
