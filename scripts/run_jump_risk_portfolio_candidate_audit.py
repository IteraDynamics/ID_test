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

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

import scripts.run_jump_risk_portfolio_integration as jr
from research.jump_risk_engine.lab import read_ohlcv


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Audit the leading Jump Risk aligned-upside portfolio candidate.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--core-wfo-dir", default="artifacts/trend_persistence_v0/portfolio_integration/core_wfo")
    p.add_argument("--out-dir", default="artifacts/jump_risk_portfolio_v0")
    p.add_argument("--run-name", default="jump-risk-candidate-audit-v0")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--jump-z", type=float, default=3.0)
    p.add_argument("--absolute-jump", type=float, default=0.05)
    p.add_argument("--quantiles", default="0.90,0.925,0.95,0.975")
    p.add_argument("--boost-scales", default="1.05,1.10,1.15,1.20")
    p.add_argument("--cost-bps", default="0,6,12,20")
    return p.parse_args()


def _grid(raw: str) -> list[float]:
    values = [float(piece.strip()) for piece in raw.split(",") if piece.strip()]
    if not values:
        raise ValueError("Grid cannot be empty")
    return values


def _atomic_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _aligned_scale(
    matrix: pd.DataFrame,
    predictions: dict[tuple[str, str], pd.DataFrame],
    asset: str,
    boost: float,
    lag_bars: int = 0,
) -> pd.Series:
    cols = [c for c in matrix.columns if c.startswith(f"{asset}_") and "trend" in c]
    medium = predictions[(asset, "medium_up")]
    extended = predictions[(asset, "extended_up")]
    idx = medium.index.union(extended.index).sort_values()
    med_high = (medium["probability"] >= medium["train_threshold"]).reindex(idx, method="ffill").fillna(False)
    ext_high = (extended["probability"] >= extended["train_threshold"]).reindex(idx, method="ffill").fillna(False)
    aligned = matrix[cols].sum(axis=1).diff(24).reindex(idx, method="ffill").fillna(0.0) > 0.0
    active = aligned & (med_high | ext_high)
    if lag_bars:
        active = active.shift(lag_bars).fillna(False)
    scale = pd.Series(1.0, index=idx)
    scale.loc[active] = boost
    return scale


def _component_contribution(
    matrix: pd.DataFrame,
    btc_scale: pd.Series,
    eth_scale: pd.Series,
    cost_bps: float,
) -> dict[str, float]:
    pnl = matrix.diff().fillna(0.0)
    btc_cols = [c for c in matrix.columns if c.startswith("BTC_") and "trend" in c]
    eth_cols = [c for c in matrix.columns if c.startswith("ETH_") and "trend" in c]
    btc = jr._align(btc_scale, matrix.index, 1.0)
    eth = jr._align(eth_scale, matrix.index, 1.0)
    btc_increment = float((pnl[btc_cols].sum(axis=1) * (btc - 1.0)).sum())
    eth_increment = float((pnl[eth_cols].sum(axis=1) * (eth - 1.0)).sum())
    rate = cost_bps / 10000.0
    btc_notional = matrix[btc_cols].sum(axis=1).shift(1).fillna(0.0)
    eth_notional = matrix[eth_cols].sum(axis=1).shift(1).fillna(0.0)
    btc_cost = float((btc.diff().abs().fillna(0.0) * btc_notional * rate).sum())
    eth_cost = float((eth.diff().abs().fillna(0.0) * eth_notional * rate).sum())
    return {
        "btc_gross_incremental_pnl": btc_increment,
        "eth_gross_incremental_pnl": eth_increment,
        "btc_cost": btc_cost,
        "eth_cost": eth_cost,
        "net_incremental_pnl": btc_increment + eth_increment - btc_cost - eth_cost,
    }


def main() -> None:
    args = parse_args()
    quantiles = _grid(args.quantiles)
    boosts = _grid(args.boost_scales)
    costs = _grid(args.cost_bps)

    matrix, matrix_path, nav_path = jr._load_matrix(args.core_wfo_dir, args.oos_start, args.oos_end)
    btc_path = jr._canonical_path(jr.CANONICAL_DATA["btc_data"])
    eth_path = jr._canonical_path(jr.CANONICAL_DATA["eth_data"])
    btc = read_ohlcv(btc_path)
    eth = read_ohlcv(eth_path)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_{args.run_name}"
    run_dir.mkdir(parents=True, exist_ok=False)

    initial = float(matrix.iloc[0].sum())
    one = pd.Series(1.0, index=matrix.index)
    baseline_nav, _ = jr._portfolio(matrix, one, one, 0.0)
    baseline = jr._metrics(baseline_nav, initial)

    rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    contribution_rows: list[dict[str, Any]] = []

    for quantile in quantiles:
        predictions: dict[tuple[str, str], pd.DataFrame] = {}
        for asset, source in (("BTC", btc), ("ETH", eth)):
            for candidate in ("medium_up", "extended_up"):
                predictions[(asset, candidate)] = jr._oos_probabilities(
                    source,
                    asset,
                    candidate,
                    args.oos_start,
                    args.oos_end,
                    args.jump_z,
                    args.absolute_jump,
                    quantile,
                )

        for boost in boosts:
            btc_scale = _aligned_scale(matrix, predictions, "BTC", boost)
            eth_scale = _aligned_scale(matrix, predictions, "ETH", boost)
            btc_aligned = jr._align(btc_scale, matrix.index, 1.0)
            eth_aligned = jr._align(eth_scale, matrix.index, 1.0)

            action_rows.append({
                "risk_quantile": quantile,
                "boosted_scale": boost,
                "btc_active_fraction": float((btc_aligned > 1.0).mean()),
                "eth_active_fraction": float((eth_aligned > 1.0).mean()),
                "btc_scale_changes": int((btc_aligned.diff().abs() > 1e-12).sum()),
                "eth_scale_changes": int((eth_aligned.diff().abs() > 1e-12).sum()),
                "btc_average_scale": float(btc_aligned.mean()),
                "eth_average_scale": float(eth_aligned.mean()),
                "average_crypto_scale_increase_pct": float((((btc_aligned + eth_aligned) / 2.0).mean() - 1.0) * 100.0),
            })

            for cost in costs:
                nav, diagnostics = jr._portfolio(matrix, btc_scale, eth_scale, cost)
                metrics = jr._metrics(nav, initial)
                row = {
                    "risk_quantile": quantile,
                    "boosted_scale": boost,
                    "cost_bps": cost,
                    **{k: v for k, v in metrics.items() if k != "annual_returns"},
                    "delta_cagr_pct": metrics["cagr_pct"] - baseline["cagr_pct"],
                    "delta_sharpe": metrics["sharpe"] - baseline["sharpe"],
                    "delta_calmar": metrics["calmar"] - baseline["calmar"],
                    "delta_max_drawdown_pct": metrics["max_drawdown_pct"] - baseline["max_drawdown_pct"],
                    **diagnostics,
                }
                row["promotion_gate"] = "PASS" if (
                    row["delta_sharpe"] > 0
                    and row["delta_calmar"] > 0
                    and row["delta_max_drawdown_pct"] >= 0
                    and row["delta_cagr_pct"] >= -0.50
                ) else "REJECT"
                rows.append(row)
                contribution_rows.append({
                    "risk_quantile": quantile,
                    "boosted_scale": boost,
                    "cost_bps": cost,
                    **_component_contribution(matrix, btc_scale, eth_scale, cost),
                })

    # Alignment audit at the locked center. The production candidate already has
    # a one-bar probability lag inside _oos_probabilities. Additional lag should
    # degrade gradually; a large improvement from negative lag would be suspicious.
    center_q = 0.95
    center_boost = 1.15
    center_cost = 6.0
    center_predictions: dict[tuple[str, str], pd.DataFrame] = {}
    for asset, source in (("BTC", btc), ("ETH", eth)):
        for candidate in ("medium_up", "extended_up"):
            center_predictions[(asset, candidate)] = jr._oos_probabilities(
                source, asset, candidate, args.oos_start, args.oos_end,
                args.jump_z, args.absolute_jump, center_q,
            )

    alignment_rows: list[dict[str, Any]] = []
    for extra_lag in (0, 1, 2, 6, 12, 24):
        btc_scale = _aligned_scale(matrix, center_predictions, "BTC", center_boost, extra_lag)
        eth_scale = _aligned_scale(matrix, center_predictions, "ETH", center_boost, extra_lag)
        nav, _ = jr._portfolio(matrix, btc_scale, eth_scale, center_cost)
        metrics = jr._metrics(nav, initial)
        alignment_rows.append({
            "extra_lag_bars": extra_lag,
            "effective_probability_lag_bars": extra_lag + 1,
            "cagr_pct": metrics["cagr_pct"],
            "sharpe": metrics["sharpe"],
            "calmar": metrics["calmar"],
            "max_drawdown_pct": metrics["max_drawdown_pct"],
            "delta_sharpe": metrics["sharpe"] - baseline["sharpe"],
            "delta_calmar": metrics["calmar"] - baseline["calmar"],
        })

    sensitivity = pd.DataFrame(rows)
    actions = pd.DataFrame(action_rows).drop_duplicates()
    contributions = pd.DataFrame(contribution_rows)
    alignment = pd.DataFrame(alignment_rows)
    sensitivity.to_csv(run_dir / "jump_risk_threshold_cost_sensitivity.csv", index=False)
    actions.to_csv(run_dir / "jump_risk_action_frequency.csv", index=False)
    contributions.to_csv(run_dir / "jump_risk_asset_contribution.csv", index=False)
    alignment.to_csv(run_dir / "jump_risk_alignment_lag_audit.csv", index=False)

    center = sensitivity[
        np.isclose(sensitivity["risk_quantile"], center_q)
        & np.isclose(sensitivity["boosted_scale"], center_boost)
        & np.isclose(sensitivity["cost_bps"], center_cost)
    ].iloc[0].to_dict()
    nearby = sensitivity[
        sensitivity["risk_quantile"].isin([0.925, 0.95, 0.975])
        & sensitivity["boosted_scale"].isin([1.10, 1.15, 1.20])
        & sensitivity["cost_bps"].isin([6.0, 12.0])
    ]
    summary = {
        "experiment": "jump_risk_portfolio_candidate_audit_v0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline": baseline,
        "locked_center": center,
        "nearby_configs": int(len(nearby)),
        "nearby_passes": int((nearby["promotion_gate"] == "PASS").sum()),
        "nearby_pass_rate": float((nearby["promotion_gate"] == "PASS").mean()) if len(nearby) else None,
        "all_configs": int(len(sensitivity)),
        "all_passes": int((sensitivity["promotion_gate"] == "PASS").sum()),
        "alignment_audit": alignment.to_dict(orient="records"),
        "input_hashes": {
            "btc": jr._sha256(btc_path),
            "eth": jr._sha256(eth_path),
            "core_matrix": jr._sha256(matrix_path),
            "core_nav": jr._sha256(nav_path),
        },
    }
    _atomic_json(run_dir / "jump_risk_candidate_audit_summary.json", summary)

    print()
    print("Jump Risk portfolio candidate audit complete")
    print(f"Out dir: {run_dir}")
    print(f"Locked center: CAGR {center['cagr_pct']:.2f}% Sharpe {center['sharpe']:.3f} Calmar {center['calmar']:.3f} MaxDD {center['max_drawdown_pct']:.2f}%")
    print(f"Nearby pass rate: {summary['nearby_passes']}/{summary['nearby_configs']} ({summary['nearby_pass_rate'] * 100.0:.1f}%)")
    print("Reference files:")
    for name in [
        "jump_risk_threshold_cost_sensitivity.csv",
        "jump_risk_action_frequency.csv",
        "jump_risk_asset_contribution.csv",
        "jump_risk_alignment_lag_audit.csv",
        "jump_risk_candidate_audit_summary.json",
    ]:
        print(f"- {run_dir / name}")


if __name__ == "__main__":
    main()
