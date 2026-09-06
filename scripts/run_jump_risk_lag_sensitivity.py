"""Jump Risk economic sensitivity to implementation lag.

The 2026-08-10 live cadence audit established that the paper runtime decides
roughly 1.5-1.7 bar periods after source-bar close, and that zero of 808 logged
cycles met the research timing assumption of acting within the immediately
following hourly bar. The approved `btc_eth_aligned_upside` mapping's +1.09pp
CAGR edge was measured at an effective one-bar lag.

This script answers the remaining question: **what survives at the lag this
infrastructure actually achieves?**

Method: the frozen research path is untouched. Probabilities are produced by
`_oos_probabilities` exactly as in the approved study (one-bar shift included).
Additional lag is then applied to the resulting scale series, which is precisely
equivalent to acting L bars later on the same information. Lag 0 reproduces the
approved study; lag 2-3 spans the observed live cadence.

PRE-REGISTERED DECISION RULE (fixed before this script was first executed):

  The candidate SURVIVES at lag L if, at that lag, it still satisfies the
  original promotion gate against the unchanged Core baseline:
      delta_sharpe > 0 AND delta_calmar > 0
      AND delta_max_drawdown_pct >= 0 AND delta_cagr_pct >= -0.50
  These are the same four conditions used in the approved study; they are not
  restated, relaxed, or reweighted here.

  DISPOSITION:
    - survives at lag >= 2  -> re-charter the candidate at the honest lag
    - survives only at lag <= 1 -> retire; the edge is not reachable live
    - fails at every lag incl. 0 -> investigate reproduction before concluding

Observation-only. No runtime, strategy, order, NAV, or production change.
"""

from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Measure Jump Risk portfolio value as a function of implementation lag.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", default=CANONICAL_DATA["btc_data"])
    p.add_argument("--eth-data", default=CANONICAL_DATA["eth_data"])
    p.add_argument(
        "--core-wfo-dir",
        default="artifacts/trend_persistence_v0/portfolio_integration/core_wfo",
    )
    p.add_argument("--out-dir", default="artifacts/jump_risk_lag_sensitivity")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--risk-quantile", type=float, default=0.95)
    p.add_argument("--jump-z", type=float, default=3.0)
    p.add_argument("--absolute-jump", type=float, default=0.05)
    p.add_argument("--boosted-scale", type=float, default=1.15)
    p.add_argument("--overlay-turnover-cost-bps", type=float, default=6.0)
    p.add_argument(
        "--lags",
        type=int,
        nargs="*",
        default=[0, 1, 2, 3, 4],
        help="Additional bars of lag beyond the frozen one-bar research shift.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    btc = read_ohlcv(_canonical_path(args.btc_data))
    eth = read_ohlcv(_canonical_path(args.eth_data))
    matrix, _, _ = _load_matrix(args.core_wfo_dir, args.oos_start, args.oos_end)

    predictions: dict[tuple[str, str], pd.DataFrame] = {}
    for asset, source in (("BTC", btc), ("ETH", eth)):
        for candidate in LOCKED_MODELS:
            print(f"Scoring {asset} {candidate}")
            predictions[(asset, candidate)] = _oos_probabilities(
                source,
                asset,
                candidate,
                args.oos_start,
                args.oos_end,
                args.jump_z,
                args.absolute_jump,
                args.risk_quantile,
            )

    def aligned_up_scale(asset: str, columns: list[str]) -> pd.Series:
        """Exactly the approved btc_eth_aligned_upside construction."""
        medium = predictions[(asset, "medium_up")]
        extended = predictions[(asset, "extended_up")]
        idx = medium.index.union(extended.index).sort_values()
        med_high = (
            (medium["probability"] >= medium["train_threshold"]).reindex(idx, method="ffill").fillna(False)
        )
        ext_high = (
            (extended["probability"] >= extended["train_threshold"]).reindex(idx, method="ffill").fillna(False)
        )
        sleeve = matrix[columns].sum(axis=1)
        aligned = sleeve.diff(24).reindex(idx, method="ffill").fillna(0.0) > 0.0
        scale = pd.Series(1.0, index=idx)
        scale.loc[aligned & (med_high | ext_high)] = args.boosted_scale
        return scale

    btc_cols = [c for c in matrix.columns if c.startswith("BTC_") and "trend" in c]
    eth_cols = [c for c in matrix.columns if c.startswith("ETH_") and "trend" in c]
    btc_up = aligned_up_scale("BTC", btc_cols)
    eth_up = aligned_up_scale("ETH", eth_cols)

    one = pd.Series(1.0, index=matrix.index)
    initial = float(matrix.iloc[0].sum())
    baseline_nav, _ = _portfolio(matrix, one, one, 0.0)
    baseline = _metrics(baseline_nav, initial)

    rows: list[dict[str, Any]] = []
    for lag in sorted(set(args.lags)):
        # Acting L bars later on the same information.
        btc_lagged = btc_up.shift(lag).fillna(1.0) if lag else btc_up
        eth_lagged = eth_up.shift(lag).fillna(1.0) if lag else eth_up
        nav, diagnostics = _portfolio(
            matrix, btc_lagged, eth_lagged, args.overlay_turnover_cost_bps
        )
        metrics = _metrics(nav, initial)
        deltas = {
            f"delta_{key}": metrics[key] - baseline[key]
            for key in ("cagr_pct", "total_return_pct", "max_drawdown_pct", "sharpe", "calmar")
        }
        survives = (
            deltas["delta_sharpe"] > 0.0
            and deltas["delta_calmar"] > 0.0
            and deltas["delta_max_drawdown_pct"] >= 0.0
            and deltas["delta_cagr_pct"] >= -0.50
        )
        rows.append(
            {
                "additional_lag_bars": lag,
                "effective_lag_bars": lag + 1,
                "cagr_pct": round(metrics["cagr_pct"], 4),
                "sharpe": round(metrics["sharpe"], 4),
                "calmar": round(metrics["calmar"], 4),
                "max_drawdown_pct": round(metrics["max_drawdown_pct"], 4),
                **{k: round(v, 4) for k, v in deltas.items()},
                "boosted_fraction_btc": round(diagnostics["btc_boosted_fraction"], 4),
                "boosted_fraction_eth": round(diagnostics["eth_boosted_fraction"], 4),
                "overlay_cost": round(diagnostics["incremental_overlay_cost"], 2),
                "promotion_gate": "PASS" if survives else "REJECT",
            }
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_jump-risk-lag-sensitivity"
    run_dir.mkdir(parents=True, exist_ok=False)
    frame = pd.DataFrame(rows)
    frame.to_csv(run_dir / "lag_sensitivity_scorecard.csv", index=False)

    surviving = [r["effective_lag_bars"] for r in rows if r["promotion_gate"] == "PASS"]
    max_surviving = max(surviving) if surviving else None
    if max_surviving is None:
        disposition = "FAILS_AT_ALL_LAGS_INVESTIGATE_REPRODUCTION"
    elif max_surviving >= 3:
        disposition = "SURVIVES_AT_LIVE_CADENCE_RECHARTER"
    else:
        disposition = "RETIRE_EDGE_NOT_REACHABLE_LIVE"

    report = {
        "audit": "jump_risk_lag_sensitivity_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "pre_registered_gate": PROMOTION_GATE,
        "baseline_core": {
            "cagr_pct": round(baseline["cagr_pct"], 4),
            "sharpe": round(baseline["sharpe"], 4),
            "calmar": round(baseline["calmar"], 4),
            "max_drawdown_pct": round(baseline["max_drawdown_pct"], 4),
        },
        "observed_live_effective_lag_bars": "~1.5-1.7 (2026-08-10 cadence audit)",
        "rows": rows,
        "max_surviving_effective_lag_bars": max_surviving,
        "disposition": disposition,
    }
    (run_dir / "lag_sensitivity_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print("\nCore baseline: "
          f"CAGR {baseline['cagr_pct']:.2f}%  Sharpe {baseline['sharpe']:.3f}  "
          f"Calmar {baseline['calmar']:.3f}  MaxDD {baseline['max_drawdown_pct']:.2f}%")
    print("\nEffective lag = 1 reproduces the approved study.\n")
    header = f"{'eff.lag':>8}{'CAGR%':>9}{'dCAGR':>8}{'Sharpe':>9}{'dSharpe':>9}{'dCalmar':>9}{'dMaxDD':>9}  gate"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['effective_lag_bars']:>8}{row['cagr_pct']:>9.2f}{row['delta_cagr_pct']:>8.2f}"
            f"{row['sharpe']:>9.3f}{row['delta_sharpe']:>9.3f}{row['delta_calmar']:>9.3f}"
            f"{row['delta_max_drawdown_pct']:>9.2f}  {row['promotion_gate']}"
        )
    print(f"\nMax surviving effective lag: {max_surviving}")
    print(f"DISPOSITION: {disposition}")
    print(f"\nArtifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
