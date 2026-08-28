from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import research.jump_risk_engine.lab as lab
from research.harness.metrics import compute_metrics
from research.jump_risk_engine.energy import add_market_energy_features
from research.jump_risk_engine.lab import JumpRiskConfig, read_ohlcv
from scripts.run_core_v1_candidate_wfo import SCENARIOS
from scripts.run_jump_ablation_research import BASELINE_FEATURES, ENERGY_FEATURES, STRUCTURE_FEATURES

CORE_SCENARIO = "candidate_btc1h_hedges_to_btc4h_gld_qqq"
CANONICAL_DATA = {
    "btc_data": "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv",
    "eth_data": "data/ethusd_3600s_2018-01-01_to_2025-12-31.csv",
}

FEATURE_SETS = {
    "baseline_energy": list(dict.fromkeys(BASELINE_FEATURES + ENERGY_FEATURES)),
    "baseline_structure": list(dict.fromkeys(BASELINE_FEATURES + STRUCTURE_FEATURES)),
}

# Frozen from completed Jump Risk v0 research. No model or label retuning is
# performed in this portfolio trial.
LOCKED_MODELS: dict[str, dict[str, Any]] = {
    "immediate_any": {
        "horizon_bars": 2,
        "target": "any",
        "model": "gbm",
        "feature_set": "baseline_energy",
    },
    "immediate_down": {
        "horizon_bars": 2,
        "target": "down",
        "model": "logistic",
        "feature_set": "baseline_structure",
    },
    "medium_up": {
        "horizon_bars": 18,
        "target": "up",
        "model": "gbm",
        "feature_set": "baseline_energy",
    },
    "extended_up": {
        "horizon_bars": 120,
        "target": "up",
        "model": "logistic",
        "feature_set": "baseline_structure",
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Research-only Jump Risk portfolio integration against canonical Core v1.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", default=CANONICAL_DATA["btc_data"])
    p.add_argument("--eth-data", default=CANONICAL_DATA["eth_data"])
    p.add_argument("--core-wfo-dir", default="artifacts/trend_persistence_v0/portfolio_integration/core_wfo")
    p.add_argument("--out-dir", default="artifacts/jump_risk_portfolio_v0")
    p.add_argument("--run-name", default="jump-risk-portfolio-integration-v0")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--risk-quantile", type=float, default=0.95)
    p.add_argument("--reduced-scale", type=float, default=0.50)
    p.add_argument("--boosted-scale", type=float, default=1.15)
    p.add_argument("--overlay-turnover-cost-bps", type=float, default=6.0)
    p.add_argument("--jump-z", type=float, default=3.0)
    p.add_argument("--absolute-jump", type=float, default=0.05)
    return p.parse_args()


def _utc_naive_index(index: pd.Index) -> pd.DatetimeIndex:
    parsed = pd.to_datetime(index, utc=True)
    return parsed.tz_convert(None)


def _atomic_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Missing canonical input: {path}")
    return path


def _load_matrix(core_wfo_dir: str, start: str, end: str) -> tuple[pd.DataFrame, Path, Path]:
    scenario_dir = Path(core_wfo_dir) / CORE_SCENARIO
    matrix_path = scenario_dir / "stitched_sleeve_equity_matrix.csv"
    nav_path = scenario_dir / "stitched_fund_nav_from_sleeves.csv"
    if not matrix_path.exists() or not nav_path.exists():
        raise FileNotFoundError(
            "Canonical Core sleeve artifacts are missing. Run the canonical sleeve finalizer first: "
            f"{matrix_path}, {nav_path}"
        )

    matrix = pd.read_csv(matrix_path, index_col=0, parse_dates=True)
    matrix.index = _utc_naive_index(matrix.index)
    matrix = matrix.apply(pd.to_numeric, errors="coerce").sort_index().ffill().dropna(how="any")

    expected = {
        sleeve for sleeve, weight in SCENARIOS[CORE_SCENARIO].items() if float(weight) > 0.0
    }
    missing = sorted(expected - set(matrix.columns))
    unexpected = sorted(set(matrix.columns) - expected)
    if missing or unexpected:
        raise ValueError(f"Canonical sleeve mismatch; missing={missing}, unexpected={unexpected}")

    nav_frame = pd.read_csv(nav_path, index_col=0, parse_dates=True)
    nav = pd.to_numeric(nav_frame.iloc[:, 0], errors="coerce").dropna().sort_index()
    nav.index = _utc_naive_index(nav.index)

    common = matrix.index.intersection(nav.index)
    matrix = matrix.loc[common]
    nav = nav.loc[common]
    delta = float((matrix.sum(axis=1) - nav).abs().max())
    if delta > 1e-6:
        raise RuntimeError(f"Canonical matrix does not reconcile to Core NAV; max delta={delta}")

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    matrix = matrix.loc[(matrix.index >= start_ts) & (matrix.index <= end_ts)]
    if matrix.empty:
        raise RuntimeError("Canonical matrix has no rows in requested OOS window")
    return matrix, matrix_path, nav_path


def _build_frame(ohlcv: pd.DataFrame, cfg: JumpRiskConfig) -> pd.DataFrame:
    base = lab.build_feature_label_frame(ohlcv, cfg)
    log_ret = np.log(ohlcv["close"].astype(float)).diff()
    frame = add_market_energy_features(
        base,
        close=ohlcv["close"].astype(float),
        high=ohlcv["high"].astype(float),
        low=ohlcv["low"].astype(float),
        ret=log_ret,
        realized_vol=base["realized_vol"],
        fast_vol=base["fast_vol"],
        slow_vol=base["slow_vol"],
        vol_rank=base["vol_rank"],
        range_rank=base["range_rank"],
        fast_window=cfg.fast_window,
        slow_window=cfg.slow_window,
    ).replace([np.inf, -np.inf], np.nan).dropna()
    frame.index = _utc_naive_index(frame.index)
    return frame.sort_index()


def _oos_probabilities_unshifted(
    ohlcv: pd.DataFrame,
    asset: str,
    candidate_name: str,
    oos_start: str,
    oos_end: str,
    jump_z: float,
    absolute_jump: float,
    risk_quantile: float,
) -> pd.DataFrame:
    """Out-of-sample probabilities indexed by the bar whose features produced them.

    This is the pre-shift frame: row ``T`` holds the probability computed from
    bar ``T``'s own features, which is NOT actionable at ``T``. ``_oos_probabilities``
    applies the one-row shift that makes the series actionable. The two are kept
    separately so the timing audit can verify the shift rather than assume it.
    """
    spec = LOCKED_MODELS[candidate_name]
    cfg = JumpRiskConfig(
        asset=asset,
        horizon_bars=int(spec["horizon_bars"]),
        vol_window=96,
        fast_window=24,
        slow_window=240,
        jump_z=jump_z,
        absolute_jump=absolute_jump,
        min_train_rows=500,
        min_train_events=20,
        test_start_year=pd.Timestamp(oos_start).year,
    )
    frame = _build_frame(ohlcv, cfg)
    features = FEATURE_SETS[str(spec["feature_set"])]
    label_col = f"jump_{spec['target']}"
    rows: list[pd.DataFrame] = []

    for year in range(pd.Timestamp(oos_start).year, pd.Timestamp(oos_end).year + 1):
        train = frame[frame.index.year < year]
        test = frame[frame.index.year == year]
        if test.empty:
            continue
        train_events = int(train[label_col].sum())
        train_nonevents = int((train[label_col] == 0).sum())
        if len(train) < cfg.min_train_rows or min(train_events, train_nonevents) < cfg.min_train_events:
            continue

        model = lab._make_model(str(spec["model"]))
        model.fit(train[features].astype(float), train[label_col].astype(int))
        train_prob = model.predict_proba(train[features].astype(float))[:, 1]
        test_prob = model.predict_proba(test[features].astype(float))[:, 1]
        rows.append(
            pd.DataFrame(
                {
                    "probability": test_prob,
                    "label": test[label_col].astype(int),
                    "train_threshold": float(np.quantile(train_prob, risk_quantile)),
                    "test_year": year,
                },
                index=test.index,
            )
        )

    if not rows:
        raise RuntimeError(f"No OOS predictions generated for {asset} {candidate_name}")
    out = pd.concat(rows).sort_index()
    out.index = _utc_naive_index(out.index)
    start_ts = pd.Timestamp(oos_start)
    end_ts = pd.Timestamp(oos_end)
    return out.loc[(out.index >= start_ts) & (out.index <= end_ts)]


def _oos_probabilities(
    ohlcv: pd.DataFrame,
    asset: str,
    candidate_name: str,
    oos_start: str,
    oos_end: str,
    jump_z: float,
    absolute_jump: float,
    risk_quantile: float,
) -> pd.DataFrame:
    """Actionable out-of-sample probabilities indexed by the bar they may act on.

    Row ``T`` holds the probability computed from the immediately preceding row's
    features, so nothing at or after ``T`` informs the value served at ``T``.
    """
    out = _oos_probabilities_unshifted(
        ohlcv,
        asset,
        candidate_name,
        oos_start,
        oos_end,
        jump_z,
        absolute_jump,
        risk_quantile,
    ).copy()
    out["probability"] = out["probability"].shift(1)
    out["train_threshold"] = out["train_threshold"].shift(1)
    return out.dropna(subset=["probability", "train_threshold"])


def _align(series: pd.Series, index: pd.DatetimeIndex, default: float) -> pd.Series:
    clean = series.copy()
    clean.index = _utc_naive_index(clean.index)
    return clean.sort_index().reindex(index, method="ffill").fillna(default).astype(float)


def _metrics(nav: pd.Series, initial: float) -> dict[str, Any]:
    result = compute_metrics(nav.dropna(), [], initial_capital=initial)
    daily = nav.resample("D").last().dropna()
    annual = {
        str(year): float(group.iloc[-1] / group.iloc[0] - 1.0) * 100.0
        for year, group in daily.groupby(daily.index.year)
        if len(group) > 1 and float(group.iloc[0]) != 0.0
    }
    return {
        "cagr_pct": float(result.cagr_pct),
        "total_return_pct": float(result.total_return_pct),
        "max_drawdown_pct": float(result.max_drawdown_pct),
        "sharpe": float(result.sharpe),
        "calmar": float(result.calmar),
        "volatility_ann_pct": float(result.volatility_ann_pct),
        "final_equity": float(result.final_equity),
        "worst_year_pct": min(annual.values()) if annual else None,
        "positive_years": int(sum(value > 0 for value in annual.values())),
        "annual_returns": annual,
    }


def _portfolio(
    matrix: pd.DataFrame,
    btc_scale: pd.Series,
    eth_scale: pd.Series,
    cost_bps: float,
) -> tuple[pd.Series, dict[str, Any]]:
    btc_cols = [c for c in matrix.columns if c.startswith("BTC_") and "trend" in c]
    eth_cols = [c for c in matrix.columns if c.startswith("ETH_") and "trend" in c]
    if not btc_cols or not eth_cols:
        raise RuntimeError(f"Missing active crypto trend sleeves; btc={btc_cols}, eth={eth_cols}")

    btc_scale = _align(btc_scale, matrix.index, 1.0)
    eth_scale = _align(eth_scale, matrix.index, 1.0)
    pnl = matrix.diff().fillna(0.0)
    adjusted = pnl.copy()
    adjusted[btc_cols] = adjusted[btc_cols].mul(btc_scale, axis=0)
    adjusted[eth_cols] = adjusted[eth_cols].mul(eth_scale, axis=0)

    cost_rate = cost_bps / 10000.0
    btc_notional = matrix[btc_cols].sum(axis=1).shift(1).fillna(0.0)
    eth_notional = matrix[eth_cols].sum(axis=1).shift(1).fillna(0.0)
    cost = btc_scale.diff().abs().fillna(0.0) * btc_notional * cost_rate
    cost += eth_scale.diff().abs().fillna(0.0) * eth_notional * cost_rate

    initial = float(matrix.iloc[0].sum())
    nav = initial + adjusted.sum(axis=1).cumsum() - cost.cumsum()
    nav.name = "portfolio_nav"
    diagnostics = {
        "btc_scale_mean": float(btc_scale.mean()),
        "eth_scale_mean": float(eth_scale.mean()),
        "btc_reduced_fraction": float((btc_scale < 1.0).mean()),
        "btc_boosted_fraction": float((btc_scale > 1.0).mean()),
        "eth_reduced_fraction": float((eth_scale < 1.0).mean()),
        "eth_boosted_fraction": float((eth_scale > 1.0).mean()),
        "btc_scale_changes": int((btc_scale.diff().abs() > 1e-12).sum()),
        "eth_scale_changes": int((eth_scale.diff().abs() > 1e-12).sum()),
        "incremental_overlay_cost": float(cost.sum()),
    }
    return nav, diagnostics


def main() -> None:
    args = parse_args()
    if not 0.50 < args.risk_quantile < 1.0:
        raise ValueError("--risk-quantile must be between 0.50 and 1.0")
    if not 0.0 <= args.reduced_scale <= 1.0:
        raise ValueError("--reduced-scale must be between 0 and 1")
    if args.boosted_scale < 1.0:
        raise ValueError("--boosted-scale must be at least 1")

    btc_path = _canonical_path(args.btc_data)
    eth_path = _canonical_path(args.eth_data)
    matrix, matrix_path, nav_path = _load_matrix(args.core_wfo_dir, args.oos_start, args.oos_end)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_{args.run_name}"
    predictions_dir = run_dir / "predictions"
    curves_dir = run_dir / "curves"
    run_dir.mkdir(parents=True, exist_ok=False)
    predictions_dir.mkdir()
    curves_dir.mkdir()
    matrix.to_csv(run_dir / "canonical_core_sleeve_matrix.csv")

    manifest = {
        "experiment": "jump_risk_portfolio_integration_v0",
        "research_only": True,
        "runtime_integration_allowed": False,
        "core_scenario": CORE_SCENARIO,
        "core_weights": SCENARIOS[CORE_SCENARIO],
        "locked_models": LOCKED_MODELS,
        "config": vars(args),
        "input_hashes": {
            "btc": _sha256(btc_path),
            "eth": _sha256(eth_path),
            "core_matrix": _sha256(matrix_path),
            "core_nav": _sha256(nav_path),
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope_note": "v0 tests exposure reduction and aligned upside participation. Hedge activation and true entry-delay require position-level Core artifacts and are not approximated from sleeve NAV.",
    }
    _atomic_json(run_dir / "manifest.json", manifest)

    btc = read_ohlcv(btc_path)
    eth = read_ohlcv(eth_path)
    predictions: dict[tuple[str, str], pd.DataFrame] = {}
    for asset, source in (("BTC", btc), ("ETH", eth)):
        for candidate in LOCKED_MODELS:
            print(f"Generating locked OOS predictions: {asset} {candidate}")
            pred = _oos_probabilities(
                source,
                asset,
                candidate,
                args.oos_start,
                args.oos_end,
                args.jump_z,
                args.absolute_jump,
                args.risk_quantile,
            )
            predictions[(asset, candidate)] = pred
            pred.to_csv(predictions_dir / f"{asset.lower()}_{candidate}.csv")

    one = pd.Series(1.0, index=matrix.index)

    btc_down = predictions[("BTC", "immediate_down")]
    eth_down = predictions[("ETH", "immediate_down")]
    btc_down_high = btc_down["probability"] >= btc_down["train_threshold"]
    eth_down_high = eth_down["probability"] >= eth_down["train_threshold"]
    btc_defensive = pd.Series(1.0, index=btc_down.index)
    eth_defensive = pd.Series(1.0, index=eth_down.index)
    btc_defensive.loc[btc_down_high] = args.reduced_scale
    eth_defensive.loc[eth_down_high] = args.reduced_scale

    def aligned_up_scale(asset: str, matrix_columns: list[str]) -> pd.Series:
        medium = predictions[(asset, "medium_up")]
        extended = predictions[(asset, "extended_up")]
        idx = medium.index.union(extended.index).sort_values()
        med_high = (medium["probability"] >= medium["train_threshold"]).reindex(idx, method="ffill").fillna(False)
        ext_high = (extended["probability"] >= extended["train_threshold"]).reindex(idx, method="ffill").fillna(False)
        sleeve = matrix[matrix_columns].sum(axis=1)
        aligned = sleeve.diff(24).reindex(idx, method="ffill").fillna(0.0) > 0.0
        scale = pd.Series(1.0, index=idx)
        scale.loc[aligned & (med_high | ext_high)] = args.boosted_scale
        return scale

    btc_cols = [c for c in matrix.columns if c.startswith("BTC_") and "trend" in c]
    eth_cols = [c for c in matrix.columns if c.startswith("ETH_") and "trend" in c]
    btc_up = aligned_up_scale("BTC", btc_cols)
    eth_up = aligned_up_scale("ETH", eth_cols)

    btc_combined_idx = btc_defensive.index.union(btc_up.index).sort_values()
    eth_combined_idx = eth_defensive.index.union(eth_up.index).sort_values()
    btc_combined = btc_up.reindex(btc_combined_idx, method="ffill").fillna(1.0)
    eth_combined = eth_up.reindex(eth_combined_idx, method="ffill").fillna(1.0)
    btc_combined.loc[btc_defensive.reindex(btc_combined_idx, method="ffill").fillna(1.0) < 1.0] = args.reduced_scale
    eth_combined.loc[eth_defensive.reindex(eth_combined_idx, method="ffill").fillna(1.0) < 1.0] = args.reduced_scale

    overlays = {
        "core_unchanged": (one, one),
        "btc_down_governor": (btc_defensive, one),
        "btc_eth_down_governor": (btc_defensive, eth_defensive),
        "btc_aligned_upside": (btc_up, one),
        "btc_eth_aligned_upside": (btc_up, eth_up),
        "combined_asymmetric": (btc_combined, eth_combined),
    }

    rows: list[dict[str, Any]] = []
    navs: dict[str, pd.Series] = {}
    annual_rows: list[dict[str, Any]] = []
    initial = float(matrix.iloc[0].sum())

    for name, (btc_scale, eth_scale) in overlays.items():
        print(f"Evaluating portfolio mapping: {name}")
        nav, diagnostics = _portfolio(
            matrix,
            btc_scale,
            eth_scale,
            0.0 if name == "core_unchanged" else args.overlay_turnover_cost_bps,
        )
        metrics = _metrics(nav, initial)
        navs[name] = nav
        nav.to_csv(curves_dir / f"{name}.csv", header=True)
        rows.append({"overlay": name, **{k: v for k, v in metrics.items() if k != "annual_returns"}, **diagnostics})
        for year, value in metrics["annual_returns"].items():
            annual_rows.append({"overlay": name, "year": year, "return_pct": value})

    scorecard = pd.DataFrame(rows)
    baseline = scorecard.loc[scorecard["overlay"] == "core_unchanged"].iloc[0]
    for metric in ["cagr_pct", "total_return_pct", "max_drawdown_pct", "sharpe", "calmar", "worst_year_pct"]:
        scorecard[f"delta_{metric}"] = scorecard[metric] - baseline[metric]
    scorecard["promotion_gate"] = "REJECT"
    candidate_mask = scorecard["overlay"] != "core_unchanged"
    passes = (
        (scorecard["delta_sharpe"] > 0.0)
        & (scorecard["delta_calmar"] > 0.0)
        & (scorecard["delta_max_drawdown_pct"] >= 0.0)
        & (scorecard["delta_cagr_pct"] >= -0.50)
    )
    scorecard.loc[candidate_mask & passes, "promotion_gate"] = "PASS"
    scorecard.loc[~candidate_mask, "promotion_gate"] = "BASELINE"
    scorecard.to_csv(run_dir / "jump_risk_portfolio_scorecard.csv", index=False)
    pd.DataFrame(annual_rows).to_csv(run_dir / "jump_risk_portfolio_annual_returns.csv", index=False)
    pd.concat(navs, axis=1).to_csv(run_dir / "jump_risk_portfolio_navs.csv")
    pd.DataFrame({name: nav / nav.cummax() - 1.0 for name, nav in navs.items()}).to_csv(
        run_dir / "jump_risk_portfolio_drawdowns.csv"
    )

    best = scorecard[scorecard["overlay"] != "core_unchanged"].sort_values(
        ["promotion_gate", "sharpe", "calmar"], ascending=[True, False, False]
    ).iloc[0]
    report = {
        "baseline": baseline.to_dict(),
        "best_overlay": best.to_dict(),
        "decision": "PASS" if bool((scorecard["promotion_gate"] == "PASS").any()) else "COMPLETED — NOT PROMOTED",
        "untested_charter_items": {
            "JR-PI-002_hedge_activation": "Requires canonical inactive hedge sleeve curves or position-level artifacts.",
            "JR-PI-003_entry_delay": "Requires position/allocation transition artifacts; not approximated from sleeve NAV.",
        },
        "promotion_rule": {
            "delta_sharpe": "> 0",
            "delta_calmar": "> 0",
            "delta_max_drawdown_pct": ">= 0",
            "delta_cagr_pct": ">= -0.50",
        },
    }
    _atomic_json(run_dir / "jump_risk_portfolio_report.json", report)

    print()
    print("Jump Risk portfolio integration v0 complete")
    print(f"Out dir: {run_dir}")
    print("Portfolio scorecard:")
    for _, row in scorecard.sort_values("overlay").iterrows():
        print(
            f"- overlay={row['overlay']:<28} gate={row['promotion_gate']:<8} "
            f"cagr={row['cagr_pct']:.2f}% sharpe={row['sharpe']:.3f} "
            f"calmar={row['calmar']:.3f} maxDD={row['max_drawdown_pct']:.2f}%"
        )
    print()
    print("Reference files:")
    for name in [
        "jump_risk_portfolio_scorecard.csv",
        "jump_risk_portfolio_annual_returns.csv",
        "jump_risk_portfolio_navs.csv",
        "jump_risk_portfolio_drawdowns.csv",
        "jump_risk_portfolio_report.json",
        "manifest.json",
    ]:
        print(f"- {run_dir / name}")


if __name__ == "__main__":
    main()
