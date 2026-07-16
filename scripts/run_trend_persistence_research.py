from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.jump_risk_engine.lab import read_ohlcv
from research.research_engine.cache import CacheKey, ResearchCache, fingerprint_file


FEATURES = [
    "ret_1",
    "ret_fast",
    "ret_slow",
    "trend_strength",
    "trend_acceleration",
    "realized_vol",
    "fast_vol",
    "slow_vol",
    "vol_ratio",
    "vol_rank",
    "distance_fast_sma",
    "distance_slow_sma",
    "distance_high_fast",
    "distance_low_fast",
    "range_position_fast",
    "range_position_slow",
    "volume_z",
    "day_of_week",
]


@dataclass(frozen=True)
class ExperimentConfig:
    asset: str
    timeframe: str
    horizon_bars: int
    fast_window: int
    slow_window: int
    vol_window: int
    jump_z: float
    absolute_floor: float
    test_start_year: int
    min_train_rows: int
    min_train_events: int


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Research-only Trend Persistence v0 discovery runner.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--asset-data", action="append", required=True, metavar="ASSET=PATH")
    p.add_argument("--timeframe", choices=["1h", "1d"], required=True)
    p.add_argument("--horizons", help="Comma-separated horizon bars. Defaults are cadence-native.")
    p.add_argument("--models", default="logistic,gbm")
    p.add_argument("--jump-z-grid", default="1.0,1.5,2.0")
    p.add_argument("--absolute-floor-grid", help="Comma-separated return floors. Defaults depend on cadence.")
    p.add_argument("--test-start-year", type=int, default=2020)
    p.add_argument("--out-dir", default="artifacts/trend_persistence_v0")
    p.add_argument("--cache-dir", default="artifacts/research_engine_v1/cache")
    p.add_argument("--run-name", default="trend-persistence-discovery-v0")
    return p.parse_args()


def _parse_asset_data(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"Expected ASSET=PATH, received {raw!r}")
        asset_raw, path_raw = raw.split("=", 1)
        asset = asset_raw.strip().upper()
        path = Path(path_raw.strip())
        if not asset or not path.exists():
            raise FileNotFoundError(f"Invalid or missing dataset mapping: {raw!r}")
        if asset in result:
            raise ValueError(f"Duplicate asset mapping: {asset}")
        result[asset] = path
    return result


def _parse_float_grid(value: str) -> list[float]:
    result = [float(item.strip()) for item in value.split(",") if item.strip()]
    if not result:
        raise ValueError("Grid cannot be empty")
    return result


def _parse_int_grid(value: str) -> list[int]:
    result = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not result or any(item <= 0 for item in result):
        raise ValueError("Horizons must contain positive integers")
    return result


def _defaults(timeframe: str) -> dict[str, Any]:
    if timeframe == "1h":
        return {
            "horizons": [6, 12, 24, 72, 120],
            "floors": [0.01, 0.02, 0.03],
            "fast": 24,
            "slow": 240,
            "vol": 96,
            "min_train_rows": 5000,
            "min_train_events": 40,
        }
    return {
        "horizons": [5, 10, 20, 40, 60],
        "floors": [0.02, 0.03, 0.05],
        "fast": 10,
        "slow": 60,
        "vol": 20,
        "min_train_rows": 500,
        "min_train_events": 20,
    }


def _future_return(close: pd.Series, horizon: int) -> pd.Series:
    return close.shift(-horizon) / close - 1.0


def _build_frame(ohlcv: pd.DataFrame, cfg: ExperimentConfig) -> pd.DataFrame:
    close = ohlcv["close"].astype(float)
    high = ohlcv["high"].astype(float)
    low = ohlcv["low"].astype(float)
    ret_1 = close.pct_change()
    log_ret = np.log(close).diff()

    fast_sma = close.rolling(cfg.fast_window, min_periods=max(5, cfg.fast_window // 2)).mean()
    slow_sma = close.rolling(cfg.slow_window, min_periods=max(20, cfg.slow_window // 2)).mean()
    ret_fast = close.pct_change(cfg.fast_window)
    ret_slow = close.pct_change(cfg.slow_window)
    realized_vol = log_ret.rolling(cfg.vol_window, min_periods=max(10, cfg.vol_window // 2)).std()
    fast_vol = log_ret.rolling(cfg.fast_window, min_periods=max(5, cfg.fast_window // 2)).std()
    slow_vol = log_ret.rolling(cfg.slow_window, min_periods=max(20, cfg.slow_window // 2)).std()
    vol_rank = realized_vol.rolling(cfg.slow_window, min_periods=max(20, cfg.slow_window // 2)).rank(pct=True)

    high_fast = high.rolling(cfg.fast_window, min_periods=max(5, cfg.fast_window // 2)).max()
    low_fast = low.rolling(cfg.fast_window, min_periods=max(5, cfg.fast_window // 2)).min()
    high_slow = high.rolling(cfg.slow_window, min_periods=max(20, cfg.slow_window // 2)).max()
    low_slow = low.rolling(cfg.slow_window, min_periods=max(20, cfg.slow_window // 2)).min()

    if ohlcv["volume"].notna().sum() > 0:
        volume = np.log(ohlcv["volume"].astype(float).replace(0, np.nan))
        volume_z = (volume - volume.rolling(cfg.slow_window, min_periods=20).mean()) / volume.rolling(
            cfg.slow_window, min_periods=20
        ).std()
    else:
        volume_z = pd.Series(0.0, index=ohlcv.index)

    future_return = _future_return(close, cfg.horizon_bars)
    trend_direction = np.sign(ret_fast).replace(0, np.nan)
    magnitude_floor = np.maximum(
        cfg.absolute_floor,
        cfg.jump_z * realized_vol * math.sqrt(cfg.horizon_bars),
    )
    signed_future = future_return * trend_direction
    continuation = (signed_future >= magnitude_floor).astype(int)
    failure = (signed_future <= -magnitude_floor).astype(int)

    frame = pd.DataFrame(
        {
            "asset": cfg.asset,
            "close": close,
            "ret_1": ret_1,
            "ret_fast": ret_fast,
            "ret_slow": ret_slow,
            "trend_strength": fast_sma / slow_sma - 1.0,
            "trend_acceleration": ret_fast - ret_slow,
            "realized_vol": realized_vol,
            "fast_vol": fast_vol,
            "slow_vol": slow_vol,
            "vol_ratio": fast_vol / slow_vol,
            "vol_rank": vol_rank,
            "distance_fast_sma": close / fast_sma - 1.0,
            "distance_slow_sma": close / slow_sma - 1.0,
            "distance_high_fast": close / high_fast - 1.0,
            "distance_low_fast": close / low_fast - 1.0,
            "range_position_fast": (close - low_fast) / (high_fast - low_fast).replace(0, np.nan),
            "range_position_slow": (close - low_slow) / (high_slow - low_slow).replace(0, np.nan),
            "volume_z": volume_z,
            "day_of_week": close.index.dayofweek.astype(float),
            "trend_direction": trend_direction,
            "future_return": future_return,
            "magnitude_floor": magnitude_floor,
            "continuation": continuation,
            "failure": failure,
        },
        index=ohlcv.index,
    )
    frame.index.name = "timestamp"
    return frame.replace([np.inf, -np.inf], np.nan).dropna()


def _model(name: str) -> Pipeline:
    if name == "logistic":
        return Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", LogisticRegression(C=0.25, class_weight="balanced", max_iter=2000, random_state=42)),
            ]
        )
    if name == "gbm":
        return Pipeline(
            [
                ("model", GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.04, random_state=42)),
            ]
        )
    raise ValueError(f"Unsupported model: {name}")


def _safe_auc(y: np.ndarray, p: np.ndarray) -> float | None:
    return None if len(np.unique(y)) < 2 else float(roc_auc_score(y, p))


def _safe_ap(y: np.ndarray, p: np.ndarray) -> float | None:
    return None if int(y.sum()) == 0 else float(average_precision_score(y, p))


def _top_lift(y: pd.Series, p: pd.Series, quantile: float = 0.05) -> tuple[int, int, float | None, float | None]:
    joined = pd.DataFrame({"y": y.astype(int), "p": p.astype(float)}).dropna().sort_values("p", ascending=False)
    if joined.empty:
        return 0, 0, None, None
    n = max(1, int(round(len(joined) * quantile)))
    top = joined.head(n)
    events = int(top["y"].sum())
    rate = float(top["y"].mean())
    base = float(joined["y"].mean())
    lift = float(rate / base) if base > 0 else None
    return n, events, rate, lift


def _walk_forward(frame: pd.DataFrame, cfg: ExperimentConfig, model_name: str) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    probs: list[pd.Series] = []
    labels: list[pd.Series] = []
    for year in sorted(y for y in frame.index.year.unique() if y >= cfg.test_start_year):
        train = frame[frame.index.year < year]
        test = frame[frame.index.year == year]
        train_events = int(train["continuation"].sum())
        train_nonevents = int((train["continuation"] == 0).sum())
        if (
            len(train) < cfg.min_train_rows
            or train_events < cfg.min_train_events
            or train_nonevents < cfg.min_train_events
            or test.empty
        ):
            folds.append(
                {
                    "test_year": int(year),
                    "status": "SKIP_LOW_SAMPLE",
                    "train_rows": int(len(train)),
                    "train_events": train_events,
                    "test_rows": int(len(test)),
                    "test_events": int(test["continuation"].sum()),
                }
            )
            continue
        estimator = _model(model_name)
        estimator.fit(train[FEATURES].astype(float), train["continuation"].astype(int))
        p = pd.Series(estimator.predict_proba(test[FEATURES].astype(float))[:, 1], index=test.index)
        y = test["continuation"].astype(int)
        folds.append(
            {
                "test_year": int(year),
                "status": "PASS",
                "train_rows": int(len(train)),
                "train_events": train_events,
                "test_rows": int(len(test)),
                "test_events": int(y.sum()),
                "event_rate": float(y.mean()),
                "roc_auc": _safe_auc(y.to_numpy(), p.to_numpy()),
                "average_precision": _safe_ap(y.to_numpy(), p.to_numpy()),
                "brier": float(brier_score_loss(y, p)) if y.nunique() > 1 else None,
            }
        )
        probs.append(p)
        labels.append(y)

    if not probs:
        return {"status": "PARTIAL", "reason": "no valid walk-forward folds", "folds": folds}

    p_all = pd.concat(probs).sort_index()
    y_all = pd.concat(labels).sort_index()
    top5_n, top5_events, top5_rate, top5_lift = _top_lift(y_all, p_all)
    return {
        "status": "PASS",
        "rows": int(len(y_all)),
        "events": int(y_all.sum()),
        "event_rate": float(y_all.mean()),
        "roc_auc": _safe_auc(y_all.to_numpy(), p_all.to_numpy()),
        "average_precision": _safe_ap(y_all.to_numpy(), p_all.to_numpy()),
        "brier": float(brier_score_loss(y_all, p_all)) if y_all.nunique() > 1 else None,
        "top5_n": top5_n,
        "top5_events": top5_events,
        "top5_event_rate": top5_rate,
        "top5_lift": top5_lift,
        "folds": folds,
    }


def _atomic_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    args = parse_args()
    mappings = _parse_asset_data(args.asset_data)
    defaults = _defaults(args.timeframe)
    horizons = _parse_int_grid(args.horizons) if args.horizons else defaults["horizons"]
    floors = _parse_float_grid(args.absolute_floor_grid) if args.absolute_floor_grid else defaults["floors"]
    z_grid = _parse_float_grid(args.jump_z_grid)
    models = [item.strip().lower() for item in args.models.split(",") if item.strip()]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_{args.run_name}"
    run_dir.mkdir(parents=True, exist_ok=False)
    results_dir = run_dir / "results"
    results_dir.mkdir()

    manifest = {
        "experiment": "trend_persistence_v0",
        "research_only": True,
        "runtime_integration_allowed": False,
        "timeframe": args.timeframe,
        "assets": {asset: str(path) for asset, path in mappings.items()},
        "horizons": horizons,
        "jump_z_grid": z_grid,
        "absolute_floor_grid": floors,
        "models": models,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_json(run_dir / "manifest.json", manifest)

    cache = ResearchCache(args.cache_dir)
    summary_rows: list[dict[str, Any]] = []
    total = len(mappings) * len(horizons) * len(z_grid) * len(floors) * len(models)
    position = 0

    for asset, path in mappings.items():
        ohlcv = read_ohlcv(path)
        fingerprint = fingerprint_file(path)
        for horizon in horizons:
            for jump_z in z_grid:
                for floor in floors:
                    cfg = ExperimentConfig(
                        asset=asset,
                        timeframe=args.timeframe,
                        horizon_bars=horizon,
                        fast_window=defaults["fast"],
                        slow_window=defaults["slow"],
                        vol_window=defaults["vol"],
                        jump_z=jump_z,
                        absolute_floor=floor,
                        test_start_year=args.test_start_year,
                        min_train_rows=defaults["min_train_rows"],
                        min_train_events=defaults["min_train_events"],
                    )
                    key = CacheKey(
                        namespace="trend-persistence-v0-frame",
                        asset=asset,
                        timeframe=args.timeframe,
                        dataset_fingerprint=fingerprint,
                        parameters=asdict(cfg),
                        version="v0",
                    )
                    frame, cache_hit = cache.get_or_build_frame(
                        key,
                        lambda cfg=cfg, ohlcv=ohlcv: _build_frame(ohlcv, cfg),
                        metadata={"experiment": "trend_persistence_v0", "source": str(path)},
                    )
                    for model_name in models:
                        position += 1
                        print(
                            f"[{position}/{total}] asset={asset} h={horizon} z={jump_z:g} floor={floor:g} model={model_name}",
                            flush=True,
                        )
                        started = time.perf_counter()
                        result = _walk_forward(frame, cfg, model_name)
                        elapsed = time.perf_counter() - started
                        payload = {
                            "config": asdict(cfg),
                            "model": model_name,
                            "cache_hit": cache_hit,
                            "elapsed_seconds": elapsed,
                            "result": result,
                        }
                        stem = f"{asset.lower()}_h{horizon}_z{jump_z:g}_floor{floor:g}_{model_name}".replace(".", "p")
                        _atomic_json(results_dir / f"{stem}.json", payload)
                        summary_rows.append(
                            {
                                "asset": asset,
                                "timeframe": args.timeframe,
                                "horizon_bars": horizon,
                                "jump_z": jump_z,
                                "absolute_floor": floor,
                                "model": model_name,
                                "cache_hit": cache_hit,
                                "elapsed_seconds": elapsed,
                                **{key: value for key, value in result.items() if key != "folds"},
                            }
                        )
                        pd.DataFrame(summary_rows).to_csv(run_dir / "trend_persistence_summary.csv", index=False)
                        print(
                            f"  status={result.get('status')} auc={result.get('roc_auc')} ap={result.get('average_precision')} "
                            f"top5_lift={result.get('top5_lift')} elapsed={elapsed / 60.0:.1f}m",
                            flush=True,
                        )

    summary = pd.DataFrame(summary_rows)
    ranked = summary[summary["status"] == "PASS"].sort_values(
        ["top5_lift", "roc_auc", "events"], ascending=[False, False, False], na_position="last"
    )
    ranked.groupby("asset", as_index=False).head(10).to_csv(run_dir / "trend_persistence_top_candidates.csv", index=False)
    print()
    print("Trend Persistence v0 discovery complete")
    print(f"Out dir: {run_dir}")
    print(f"Configurations: {len(summary_rows)}")
    print(f"Summary: {run_dir / 'trend_persistence_summary.csv'}")
    print(f"Top candidates: {run_dir / 'trend_persistence_top_candidates.csv'}")


if __name__ == "__main__":
    main()
