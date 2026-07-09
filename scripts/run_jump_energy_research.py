from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import research.jump_risk_engine.lab as lab
from research.jump_risk_engine.artifacts import make_run_dir
from research.jump_risk_engine.energy import add_market_energy_features
from research.jump_risk_engine.lab import JumpRiskConfig, read_ohlcv


ENERGY_FEATURE_COLS = [
    "deep_squeeze_flag",
    "deep_squeeze_duration",
    "compression_depth",
    "compression_area_fast",
    "compression_area_slow",
    "deep_compression_area_fast",
    "range_compression_area_fast",
    "expansion_pressure",
    "compression_release_pressure",
    "range_release_pressure",
    "directional_pressure",
    "upside_pressure",
    "downside_pressure",
    "vol_slope_6",
    "vol_accel_6_12",
    "vol_ignition",
    "breakout_tension_fast",
    "breakdown_tension_fast",
    "breakout_tension_slow",
    "breakdown_tension_slow",
    "quiet_absorption",
    "quiet_absorption_area",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Research-only Market Energy + Jump Risk lab. Does not touch Core v1 runtime.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--asset", required=True, help="Asset label, e.g. BTC, ETH, SPY, QQQ, GLD")
    p.add_argument("--data", required=True, help="CSV containing timestamp/date + OHLCV columns")
    p.add_argument("--out-dir", default="artifacts/jump_risk_engine_v0")
    p.add_argument("--run-name", default="market-energy-v0")
    p.add_argument("--horizon-bars", type=int, default=24)
    p.add_argument("--vol-window", type=int, default=96)
    p.add_argument("--fast-window", type=int, default=24)
    p.add_argument("--slow-window", type=int, default=240)
    p.add_argument("--jump-z", type=float, default=3.0)
    p.add_argument("--absolute-jump", type=float, default=0.05)
    p.add_argument("--test-start-year", type=int, default=2020)
    p.add_argument("--models", default="logistic,gbm", help="Comma-separated: logistic,gbm,rf")
    p.add_argument("--targets", default="any,down,up", help="Comma-separated: any,down,up")
    return p.parse_args()


def _fmt(x: object) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.4f}"
    return str(x)


def _best_lift_line(run: dict) -> str:
    diag = (run.get("aggregate") or {}).get("diagnostics") or {}
    lifts = diag.get("lift_at_top_quantiles") or []
    top_10 = next((r for r in lifts if abs(float(r.get("top_quantile", -1)) - 0.10) < 1e-9), None)
    top_5 = next((r for r in lifts if abs(float(r.get("top_quantile", -1)) - 0.05) < 1e-9), None)
    if not top_10 and not top_5:
        return "lift=n/a"
    parts = []
    for label, row in (("top5", top_5), ("top10", top_10)):
        if row:
            rate = row.get("event_rate")
            lift = row.get("lift_vs_unconditional")
            parts.append(f"{label}_rate={rate:.2%} lift={lift:.2f}x" if rate is not None and lift is not None else f"{label}=n/a")
    return " ".join(parts)


def _write_outputs(report: dict, frame: pd.DataFrame, out: Path, cfg: JumpRiskConfig) -> None:
    stem = f"{cfg.asset.lower()}_h{cfg.horizon_bars}_z{cfg.jump_z:g}_abs{cfg.absolute_jump:g}".replace(".", "p")
    (out / f"{stem}_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    frame.reset_index().to_csv(out / f"{stem}_dataset.csv", index=False)

    summary_rows: list[dict] = []
    lift_rows: list[dict] = []
    profile_rows: list[dict] = []
    prediction_paths: list[str] = []

    for run in report["runs"]:
        pred_frame = run.pop("_predictions", pd.DataFrame())
        if not pred_frame.empty:
            pred_path = out / f"{stem}_{run['target']}_{run['model']}_oos_predictions.csv"
            pred_frame.reset_index().to_csv(pred_path, index=False)
            prediction_paths.append(str(pred_path))
            run["aggregate"]["oos_predictions_csv"] = str(pred_path)

        agg = run["aggregate"]
        summary_rows.append(
            {
                "asset": cfg.asset,
                "target": run["target"],
                "model": run["model"],
                "status": agg.get("status"),
                "rows": agg.get("rows"),
                "events": agg.get("events"),
                "event_rate": agg.get("event_rate"),
                "roc_auc": agg.get("roc_auc"),
                "average_precision": agg.get("average_precision"),
                "brier": agg.get("brier"),
                "reason": agg.get("reason"),
                "oos_predictions_csv": agg.get("oos_predictions_csv"),
            }
        )
        diag = agg.get("diagnostics") or {}
        for row in diag.get("lift_at_top_quantiles", []):
            lift_rows.append({"asset": cfg.asset, "target": run["target"], "model": run["model"], **row})
        for group_name, rows in (diag.get("feature_profiles") or {}).items():
            for row in rows:
                profile_rows.append({"asset": cfg.asset, "target": run["target"], "model": run["model"], "group": group_name, **row})

    report["prediction_csvs"] = prediction_paths
    (out / f"{stem}_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(summary_rows).to_csv(out / f"{stem}_summary.csv", index=False)
    pd.DataFrame(lift_rows).to_csv(out / f"{stem}_lift.csv", index=False)
    pd.DataFrame(profile_rows).to_csv(out / f"{stem}_feature_profiles.csv", index=False)


def main() -> None:
    args = parse_args()
    cfg = JumpRiskConfig(
        asset=args.asset.upper(),
        horizon_bars=args.horizon_bars,
        vol_window=args.vol_window,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        jump_z=args.jump_z,
        absolute_jump=args.absolute_jump,
        test_start_year=args.test_start_year,
    )
    models = tuple(x.strip() for x in args.models.split(",") if x.strip())
    targets = tuple(x.strip() for x in args.targets.split(",") if x.strip())

    out = make_run_dir(args.out_dir, "market_energy", cfg, args.run_name)

    ohlcv = read_ohlcv(args.data)
    base_frame = lab.build_feature_label_frame(ohlcv, cfg)
    enriched = add_market_energy_features(
        base_frame,
        close=ohlcv["close"].astype(float),
        high=ohlcv["high"].astype(float),
        low=ohlcv["low"].astype(float),
        ret=pd.Series(pd.NA, index=ohlcv.index).astype("float64").combine_first((ohlcv["close"].astype(float).pipe(lambda s: s / s.shift(1)).pipe(lambda s: s.apply(lambda x: pd.NA if pd.isna(x) else x))).pipe(lambda s: pd.Series(pd.NA, index=s.index))),
        realized_vol=base_frame["realized_vol"],
        fast_vol=base_frame["fast_vol"],
        slow_vol=base_frame["slow_vol"],
        vol_rank=base_frame["vol_rank"],
        range_rank=base_frame["range_rank"],
        fast_window=cfg.fast_window,
        slow_window=cfg.slow_window,
    )

    # The intentionally ugly ret construction above keeps the function signature explicit,
    # but for actual energy calculations we want log returns aligned to the raw OHLCV index.
    enriched = add_market_energy_features(
        base_frame,
        close=ohlcv["close"].astype(float),
        high=ohlcv["high"].astype(float),
        low=ohlcv["low"].astype(float),
        ret=pd.Series(pd.NA, index=ohlcv.index).astype("float64").combine_first(
            pd.Series(pd.NA, index=ohlcv.index).astype("float64")
        ).fillna((ohlcv["close"].astype(float).pipe(lambda s: s.apply(lambda _: 0.0)))),
        realized_vol=base_frame["realized_vol"],
        fast_vol=base_frame["fast_vol"],
        slow_vol=base_frame["slow_vol"],
        vol_rank=base_frame["vol_rank"],
        range_rank=base_frame["range_rank"],
        fast_window=cfg.fast_window,
        slow_window=cfg.slow_window,
    )

    # Correct the return-dependent energy columns using real log returns. We do this after
    # preserving the explicit module call above so the runner remains a thin research layer.
    log_ret = (ohlcv["close"].astype(float).pipe(lambda s: s / s.shift(1))).apply(lambda x: pd.NA if pd.isna(x) else __import__("math").log(float(x)))
    enriched = add_market_energy_features(
        base_frame,
        close=ohlcv["close"].astype(float),
        high=ohlcv["high"].astype(float),
        low=ohlcv["low"].astype(float),
        ret=log_ret.astype(float),
        realized_vol=base_frame["realized_vol"],
        fast_vol=base_frame["fast_vol"],
        slow_vol=base_frame["slow_vol"],
        vol_rank=base_frame["vol_rank"],
        range_rank=base_frame["range_rank"],
        fast_window=cfg.fast_window,
        slow_window=cfg.slow_window,
    ).replace([float("inf"), float("-inf")], pd.NA).dropna()

    original_features = list(lab.FEATURE_COLS)
    for col in ENERGY_FEATURE_COLS:
        if col not in lab.FEATURE_COLS:
            lab.FEATURE_COLS.append(col)

    runs: list[dict] = []
    for target in targets:
        for model in models:
            runs.append(lab.run_walk_forward(enriched, cfg, target, model))

    label_summary = {
        "asset": cfg.asset,
        "rows": int(len(enriched)),
        "start": enriched.index.min().isoformat(),
        "end": enriched.index.max().isoformat(),
        "horizon_bars": cfg.horizon_bars,
        "jump_z": cfg.jump_z,
        "absolute_jump": cfg.absolute_jump,
        "jump_any_rate": float(enriched["jump_any"].mean()),
        "jump_down_rate": float(enriched["jump_down"].mean()),
        "jump_up_rate": float(enriched["jump_up"].mean()),
        "median_threshold": float(enriched["jump_threshold"].median()),
        "p90_future_abs": float(enriched["future_abs"].quantile(0.90)),
        "p99_future_abs": float(enriched["future_abs"].quantile(0.99)),
        "base_feature_count": len(original_features),
        "energy_feature_count": len(ENERGY_FEATURE_COLS),
        "total_feature_count": len(lab.FEATURE_COLS),
    }
    report = {"config": asdict(cfg), "experiment": "market_energy_v0", "label_summary": label_summary, "runs": runs}
    _write_outputs(report, enriched, out, cfg)

    print("Market Energy Jump Risk research complete")
    print(f"Asset: {cfg.asset}")
    print(f"Rows: {label_summary['rows']}")
    print(f"Window: {label_summary['start']} -> {label_summary['end']}")
    print(f"Jump-any rate: {label_summary['jump_any_rate']:.2%}")
    print(f"Jump-down rate: {label_summary['jump_down_rate']:.2%}")
    print(f"Jump-up rate: {label_summary['jump_up_rate']:.2%}")
    print(f"Out dir: {out}")
    print()
    print("Model summary:")
    for run in report["runs"]:
        agg = run["aggregate"]
        print(
            f"- target={run['target']:<4} model={run['model']:<8} status={agg.get('status'):<7} "
            f"auc={_fmt(agg.get('roc_auc'))} ap={_fmt(agg.get('average_precision'))} {_best_lift_line(run)}"
        )


if __name__ == "__main__":
    main()
