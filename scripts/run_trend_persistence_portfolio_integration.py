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
import math
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone

REPO_ROOT = Path(__file__).resolve().parent.parent

import scripts.run_trend_persistence_research as persistence
from research.harness.metrics import compute_metrics
from research.jump_risk_engine.lab import read_ohlcv
from scripts.run_core_v1_candidate_wfo import SCENARIOS
from scripts.run_trend_persistence_ablation import FEATURE_SETS


CORE_SCENARIO = "candidate_btc1h_hedges_to_btc4h_gld_qqq"
CANONICAL_DATA = {
    "btc_data": "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv",
    "eth_data": "data/ethusd_3600s_2018-01-01_to_2025-12-31.csv",
    "spy_data": "data/SPY_1D.csv",
    "qqq_data": "data/QQQ_1D.csv",
    "bil_data": "data/BIL_1D.csv",
    "gld_data": "data/GLD_1D.csv",
}

# Locked from the completed robustness study. The WARN BTC-long candidate is
# intentionally excluded from the primary portfolio tests.
LOCKED_MODELS: dict[str, dict[str, Any]] = {
    "btc_immediate": {
        "asset": "BTC",
        "horizon_bars": 3,
        "jump_z": 1.0,
        "absolute_floor": 0.03,
        "model": "logistic",
        "feature_set": "momentum_volatility",
    },
    "eth_immediate": {
        "asset": "ETH",
        "horizon_bars": 3,
        "jump_z": 1.0,
        "absolute_floor": 0.03,
        "model": "logistic",
        "feature_set": "all_features",
    },
    "btc_medium": {
        "asset": "BTC",
        "horizon_bars": 60,
        "jump_z": 2.0,
        "absolute_floor": 0.02,
        "model": "logistic",
        "feature_set": "all_features",
    },
}

OVERLAYS = {
    "core_unchanged": "No persistence overlay.",
    "btc_immediate_gate": "Reduce BTC trend sleeve when immediate persistence is in its low training quantile.",
    "btc_eth_immediate_gate": "Apply independent immediate-persistence confirmation gates to BTC and ETH sleeves.",
    "btc_medium_scaling": "Scale BTC trend sleeve down/normal/up using medium-horizon persistence quantiles.",
    "combined_persistence_governor": "Blend BTC immediate and medium persistence; independently gate ETH using immediate persistence.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Research-only Trend Persistence portfolio integration against canonical Core v1.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--btc-data", default=CANONICAL_DATA["btc_data"])
    parser.add_argument("--eth-data", default=CANONICAL_DATA["eth_data"])
    parser.add_argument("--spy-data", default=CANONICAL_DATA["spy_data"])
    parser.add_argument("--qqq-data", default=CANONICAL_DATA["qqq_data"])
    parser.add_argument("--bil-data", default=CANONICAL_DATA["bil_data"])
    parser.add_argument("--gld-data", default=CANONICAL_DATA["gld_data"])
    parser.add_argument("--data-start", default="2019-01-01")
    parser.add_argument("--oos-start", default="2020-01-01")
    parser.add_argument("--oos-end", default="2025-12-31")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--fee", type=float, default=0.0006)
    parser.add_argument("--equity-fee", type=float, default=0.0001)
    parser.add_argument("--base-slippage", type=float, default=3.0)
    parser.add_argument("--slippage-vol-factor", type=float, default=50.0)
    parser.add_argument("--low-quantile", type=float, default=0.25)
    parser.add_argument("--high-quantile", type=float, default=0.75)
    parser.add_argument("--reduced-scale", type=float, default=0.50)
    parser.add_argument("--boosted-scale", type=float, default=1.25)
    parser.add_argument(
        "--overlay-turnover-cost-bps",
        type=float,
        default=6.0,
        help="Conservative incremental cost applied when an overlay scale changes.",
    )
    parser.add_argument("--core-wfo-dir", default="artifacts/trend_persistence_v0/portfolio_integration/core_wfo")
    parser.add_argument("--out-dir", default="artifacts/trend_persistence_v0/portfolio_integration")
    parser.add_argument("--run-name", default="trend-persistence-portfolio-integration-v0")
    parser.add_argument(
        "--skip-core-run",
        action="store_true",
        help="Reuse an existing canonical sleeve matrix under --core-wfo-dir.",
    )
    return parser.parse_args()


def _atomic_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def _require_canonical_paths(args: argparse.Namespace) -> None:
    for field, relative in CANONICAL_DATA.items():
        actual = (REPO_ROOT / getattr(args, field)).resolve()
        expected = (REPO_ROOT / relative).resolve()
        if actual != expected:
            raise ValueError(f"{field} must use canonical path {relative}; received {actual}")
        if not actual.exists():
            raise FileNotFoundError(f"Missing canonical data file: {actual}")


def _run_core_wfo(args: argparse.Namespace) -> Path:
    scenario_dir = Path(args.core_wfo_dir) / CORE_SCENARIO
    matrix_path = scenario_dir / "stitched_sleeve_equity_matrix.csv"
    nav_path = scenario_dir / "stitched_fund_nav_from_sleeves.csv"
    if args.skip_core_run:
        if not matrix_path.exists() or not nav_path.exists():
            raise FileNotFoundError(
                "--skip-core-run requested but canonical sleeve outputs are missing: "
                f"{matrix_path}, {nav_path}"
            )
        return scenario_dir

    runner = REPO_ROOT / "scripts" / "run_core_v1_candidate_wfo.py"
    cmd = [
        sys.executable,
        str(runner),
        "--scenario",
        CORE_SCENARIO,
        "--workers",
        str(args.workers),
        "--btc-data",
        args.btc_data,
        "--eth-data",
        args.eth_data,
        "--spy-data",
        args.spy_data,
        "--qqq-data",
        args.qqq_data,
        "--bil-data",
        args.bil_data,
        "--gld-data",
        args.gld_data,
        "--data-start",
        args.data_start,
        "--oos-start",
        args.oos_start,
        "--oos-end",
        args.oos_end,
        "--fee",
        str(args.fee),
        "--equity-fee",
        str(args.equity_fee),
        "--base-slippage",
        str(args.base_slippage),
        "--slippage-vol-factor",
        str(args.slippage_vol_factor),
        "--out-dir",
        args.core_wfo_dir,
    ]
    print("Running canonical Core v1 WFO:")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    if not matrix_path.exists() or not nav_path.exists():
        raise FileNotFoundError("Core WFO completed without required sleeve outputs")
    return scenario_dir


def _load_matrix(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    frame = frame.apply(pd.to_numeric, errors="coerce").sort_index().ffill().dropna(how="all")

    # Scenario dictionaries retain explicit zero-weight sleeves for comparison and
    # provenance. Canonical matrix exports correctly omit those inactive sleeves,
    # so validation must require only sleeves with positive deployed weight.
    expected = {
        sleeve
        for sleeve, weight in SCENARIOS[CORE_SCENARIO].items()
        if float(weight) > 0.0
    }
    missing = sorted(expected - set(frame.columns))
    if missing:
        raise ValueError(f"Sleeve matrix is missing active canonical sleeves: {missing}")

    unexpected = sorted(set(frame.columns) - expected)
    if unexpected:
        raise ValueError(f"Sleeve matrix contains unexpected canonical sleeves: {unexpected}")
    return frame


def _build_cfg(name: str, test_start_year: int = 2020) -> persistence.ExperimentConfig:
    spec = LOCKED_MODELS[name]
    defaults = persistence._defaults("1h")
    return persistence.ExperimentConfig(
        asset=spec["asset"],
        timeframe="1h",
        horizon_bars=spec["horizon_bars"],
        fast_window=defaults["fast"],
        slow_window=defaults["slow"],
        vol_window=defaults["vol"],
        jump_z=spec["jump_z"],
        absolute_floor=spec["absolute_floor"],
        test_start_year=test_start_year,
        min_train_rows=defaults["min_train_rows"],
        min_train_events=defaults["min_train_events"],
    )


def _oos_probabilities(
    ohlcv: pd.DataFrame,
    candidate_name: str,
    oos_start: str,
    oos_end: str,
) -> pd.DataFrame:
    spec = LOCKED_MODELS[candidate_name]
    cfg = _build_cfg(candidate_name, pd.Timestamp(oos_start).year)
    frame = persistence._build_frame(ohlcv, cfg)
    features = FEATURE_SETS[spec["feature_set"]]
    rows: list[pd.DataFrame] = []

    for year in range(pd.Timestamp(oos_start).year, pd.Timestamp(oos_end).year + 1):
        train = frame[frame.index.year < year]
        test = frame[frame.index.year == year]
        if test.empty:
            continue
        if len(train) < cfg.min_train_rows or int(train["continuation"].sum()) < cfg.min_train_events:
            continue

        estimator = clone(persistence._model(spec["model"]))
        estimator.fit(train[features].astype(float), train["continuation"].astype(int))
        train_prob = estimator.predict_proba(train[features].astype(float))[:, 1]
        test_prob = estimator.predict_proba(test[features].astype(float))[:, 1]
        rows.append(
            pd.DataFrame(
                {
                    "probability": test_prob,
                    "trend_direction": test["trend_direction"].astype(float),
                    "continuation": test["continuation"].astype(int),
                    "train_q25": float(np.quantile(train_prob, 0.25)),
                    "train_q75": float(np.quantile(train_prob, 0.75)),
                    "test_year": year,
                },
                index=test.index,
            )
        )

    if not rows:
        raise RuntimeError(f"No OOS predictions generated for {candidate_name}")
    out = pd.concat(rows).sort_index()
    out = out.loc[pd.Timestamp(oos_start) : pd.Timestamp(oos_end)]
    # One-bar lag ensures the portfolio only acts on information available before
    # the return interval being governed.
    for col in ["probability", "trend_direction", "train_q25", "train_q75"]:
        out[col] = out[col].shift(1)
    return out.dropna(subset=["probability", "train_q25", "train_q75"])


def _annualized_metrics(nav: pd.Series, initial_capital: float) -> dict[str, Any]:
    nav = nav.dropna()
    metrics = compute_metrics(nav, [], initial_capital=initial_capital)
    daily = nav.resample("D").last().dropna()
    annual = {
        str(year): float(group.iloc[-1] / group.iloc[0] - 1.0)
        for year, group in daily.groupby(daily.index.year)
        if len(group) > 1 and float(group.iloc[0]) != 0.0
    }
    return {
        "cagr_pct": float(metrics.cagr_pct),
        "total_return_pct": float(metrics.total_return_pct),
        "max_drawdown_pct": float(metrics.max_drawdown_pct),
        "sharpe": float(metrics.sharpe),
        "calmar": float(metrics.calmar),
        "volatility_ann_pct": float(metrics.volatility_ann_pct),
        "final_equity": float(metrics.final_equity),
        "worst_year_pct": min(annual.values()) * 100.0 if annual else None,
        "positive_years": int(sum(value > 0 for value in annual.values())),
        "annual_returns": {year: value * 100.0 for year, value in annual.items()},
    }


def _scale_from_signal(prob: pd.Series, low: pd.Series, high: pd.Series, reduced: float, boosted: float, allow_boost: bool) -> pd.Series:
    scale = pd.Series(1.0, index=prob.index)
    scale.loc[prob <= low] = reduced
    if allow_boost:
        scale.loc[prob >= high] = boosted
    return scale


def _align_signal(signal: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    return signal.reindex(index, method="ffill").fillna(1.0).astype(float)


def _portfolio_from_scales(
    matrix: pd.DataFrame,
    btc_scale: pd.Series,
    eth_scale: pd.Series,
    turnover_cost_bps: float,
) -> tuple[pd.Series, dict[str, Any]]:
    pnl = matrix.diff().fillna(0.0)
    btc_columns = [column for column in matrix.columns if column.startswith("BTC_") and "trend" in column]
    eth_columns = [column for column in matrix.columns if column.startswith("ETH_") and "trend" in column]
    btc_scale = _align_signal(btc_scale, matrix.index)
    eth_scale = _align_signal(eth_scale, matrix.index)

    adjusted = pnl.copy()
    adjusted[btc_columns] = adjusted[btc_columns].mul(btc_scale, axis=0)
    adjusted[eth_columns] = adjusted[eth_columns].mul(eth_scale, axis=0)

    cost_rate = turnover_cost_bps / 10000.0
    btc_notional = matrix[btc_columns].sum(axis=1).shift(1).fillna(0.0)
    eth_notional = matrix[eth_columns].sum(axis=1).shift(1).fillna(0.0)
    overlay_cost = btc_scale.diff().abs().fillna(0.0) * btc_notional * cost_rate
    overlay_cost += eth_scale.diff().abs().fillna(0.0) * eth_notional * cost_rate

    initial = float(matrix.iloc[0].sum())
    nav = initial + adjusted.sum(axis=1).cumsum() - overlay_cost.cumsum()
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
        "incremental_overlay_cost": float(overlay_cost.sum()),
    }
    return nav, diagnostics


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def main() -> None:
    args = parse_args()
    _require_canonical_paths(args)
    if not 0.0 < args.low_quantile < args.high_quantile < 1.0:
        raise ValueError("Quantiles must satisfy 0 < low < high < 1")
    if not 0.0 <= args.reduced_scale <= 1.0:
        raise ValueError("--reduced-scale must be between 0 and 1")
    if args.boosted_scale < 1.0:
        raise ValueError("--boosted-scale must be at least 1")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_{args.run_name}"
    run_dir.mkdir(parents=True, exist_ok=False)
    predictions_dir = run_dir / "predictions"
    curves_dir = run_dir / "curves"
    predictions_dir.mkdir()
    curves_dir.mkdir()

    manifest = {
        "experiment": "trend_persistence_portfolio_integration_v0",
        "research_only": True,
        "runtime_integration_allowed": False,
        "core_scenario": CORE_SCENARIO,
        "core_weights": SCENARIOS[CORE_SCENARIO],
        "locked_models": LOCKED_MODELS,
        "overlays": OVERLAYS,
        "config": vars(args),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_json(run_dir / "manifest.json", manifest)

    scenario_dir = _run_core_wfo(args)
    matrix = _load_matrix(scenario_dir / "stitched_sleeve_equity_matrix.csv")
    matrix = matrix.loc[pd.Timestamp(args.oos_start) : pd.Timestamp(args.oos_end)]
    matrix.to_csv(run_dir / "core_sleeve_equity_matrix.csv")

    btc = read_ohlcv(REPO_ROOT / args.btc_data)
    eth = read_ohlcv(REPO_ROOT / args.eth_data)
    predictions: dict[str, pd.DataFrame] = {}
    for name, spec in LOCKED_MODELS.items():
        source = btc if spec["asset"] == "BTC" else eth
        print(f"Generating locked OOS predictions: {name}")
        pred = _oos_probabilities(source, name, args.oos_start, args.oos_end)
        predictions[name] = pred
        pred.to_csv(predictions_dir / f"{name}.csv")

    btc_i = predictions["btc_immediate"]
    eth_i = predictions["eth_immediate"]
    btc_m = predictions["btc_medium"]

    btc_i_gate = _scale_from_signal(
        btc_i["probability"], btc_i["train_q25"], btc_i["train_q75"], args.reduced_scale, args.boosted_scale, False
    )
    eth_i_gate = _scale_from_signal(
        eth_i["probability"], eth_i["train_q25"], eth_i["train_q75"], args.reduced_scale, args.boosted_scale, False
    )
    btc_m_scale = _scale_from_signal(
        btc_m["probability"], btc_m["train_q25"], btc_m["train_q75"], args.reduced_scale, args.boosted_scale, True
    )

    common_btc_index = btc_i.index.union(btc_m.index).sort_values()
    btc_i_rank = ((btc_i["probability"] - btc_i["train_q25"]) / (btc_i["train_q75"] - btc_i["train_q25"]).replace(0, np.nan)).clip(0, 1)
    btc_m_rank = ((btc_m["probability"] - btc_m["train_q25"]) / (btc_m["train_q75"] - btc_m["train_q25"]).replace(0, np.nan)).clip(0, 1)
    combined_rank = pd.concat(
        [btc_i_rank.reindex(common_btc_index, method="ffill"), btc_m_rank.reindex(common_btc_index, method="ffill")], axis=1
    ).mean(axis=1)
    combined_btc = pd.Series(1.0, index=common_btc_index)
    combined_btc.loc[combined_rank <= 0.25] = args.reduced_scale
    combined_btc.loc[combined_rank >= 0.75] = args.boosted_scale

    one = pd.Series(1.0, index=matrix.index)
    overlay_scales = {
        "core_unchanged": (one, one),
        "btc_immediate_gate": (btc_i_gate, one),
        "btc_eth_immediate_gate": (btc_i_gate, eth_i_gate),
        "btc_medium_scaling": (btc_m_scale, one),
        "combined_persistence_governor": (combined_btc, eth_i_gate),
    }

    rows: list[dict[str, Any]] = []
    navs: dict[str, pd.Series] = {}
    diagnostics_by_overlay: dict[str, Any] = {}
    initial_capital = float(matrix.iloc[0].sum())

    for name, (btc_scale, eth_scale) in overlay_scales.items():
        print(f"Evaluating portfolio overlay: {name}")
        nav, diagnostics = _portfolio_from_scales(
            matrix,
            btc_scale,
            eth_scale,
            0.0 if name == "core_unchanged" else args.overlay_turnover_cost_bps,
        )
        metrics = _annualized_metrics(nav, initial_capital)
        nav.to_csv(curves_dir / f"{name}.csv", header=True)
        navs[name] = nav
        diagnostics_by_overlay[name] = diagnostics
        rows.append(
            {
                "overlay": name,
                **{key: value for key, value in metrics.items() if key != "annual_returns"},
                **diagnostics,
            }
        )

    scorecard = pd.DataFrame(rows)
    baseline = scorecard.loc[scorecard["overlay"] == "core_unchanged"].iloc[0]
    for metric in ["cagr_pct", "total_return_pct", "max_drawdown_pct", "sharpe", "calmar", "worst_year_pct"]:
        scorecard[f"delta_{metric}"] = scorecard[metric] - baseline[metric]
    scorecard["promotion_gate"] = "REJECT"
    nonbaseline = scorecard["overlay"] != "core_unchanged"
    passes = (
        (scorecard["delta_sharpe"] > 0)
        & (scorecard["delta_calmar"] > 0)
        & (scorecard["delta_max_drawdown_pct"] >= 0)
        & (scorecard["delta_cagr_pct"] >= -0.50)
    )
    scorecard.loc[nonbaseline & passes, "promotion_gate"] = "PASS"
    scorecard.loc[scorecard["overlay"] == "core_unchanged", "promotion_gate"] = "BASELINE"
    scorecard.to_csv(run_dir / "trend_persistence_portfolio_scorecard.csv", index=False)

    annual_rows: list[dict[str, Any]] = []
    for name, nav in navs.items():
        annual = _annualized_metrics(nav, initial_capital)["annual_returns"]
        for year, value in annual.items():
            annual_rows.append({"overlay": name, "year": year, "return_pct": value})
    pd.DataFrame(annual_rows).to_csv(run_dir / "trend_persistence_portfolio_annual_returns.csv", index=False)

    aligned_nav = pd.concat(navs, axis=1).dropna(how="all")
    aligned_nav.to_csv(run_dir / "trend_persistence_portfolio_navs.csv")
    pd.DataFrame({name: _drawdown(nav) for name, nav in navs.items()}).to_csv(
        run_dir / "trend_persistence_portfolio_drawdowns.csv"
    )

    best = scorecard[scorecard["overlay"] != "core_unchanged"].sort_values(
        ["promotion_gate", "sharpe", "calmar"], ascending=[True, False, False]
    ).iloc[0]
    report = {
        "baseline": scorecard.loc[scorecard["overlay"] == "core_unchanged"].iloc[0].to_dict(),
        "best_overlay": best.to_dict(),
        "diagnostics": diagnostics_by_overlay,
        "promotion_rule": {
            "sharpe_delta": "> 0",
            "calmar_delta": "> 0",
            "max_drawdown_delta_pct": ">= 0 (less negative or unchanged)",
            "cagr_delta_pct": ">= -0.50",
        },
    }
    _atomic_json(run_dir / "trend_persistence_portfolio_report.json", report)

    print()
    print("Trend Persistence portfolio integration complete")
    print(f"Out dir: {run_dir}")
    print("Portfolio scorecard:")
    for _, row in scorecard.sort_values("overlay").iterrows():
        print(
            f"- overlay={row['overlay']:<31} gate={row['promotion_gate']:<8} "
            f"cagr={row['cagr_pct']:.2f}% sharpe={row['sharpe']:.3f} "
            f"calmar={row['calmar']:.3f} maxDD={row['max_drawdown_pct']:.2f}%"
        )
    print()
    print("Reference files:")
    print(f"- {run_dir / 'trend_persistence_portfolio_scorecard.csv'}")
    print(f"- {run_dir / 'trend_persistence_portfolio_annual_returns.csv'}")
    print(f"- {run_dir / 'trend_persistence_portfolio_navs.csv'}")
    print(f"- {run_dir / 'trend_persistence_portfolio_drawdowns.csv'}")
    print(f"- {run_dir / 'trend_persistence_portfolio_report.json'}")
    print(f"- {run_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
