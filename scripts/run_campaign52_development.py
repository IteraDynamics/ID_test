from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from research.harness.campaign52_development import (
    CONTROL_IDS,
    DEVELOPMENT_FOLDS,
    atomic_promote,
    bootstrap_seed,
    development_decision,
    holm_adjust,
    primary_metrics,
    static_mean_values,
    transform_block_permutation,
    transform_lag,
    transform_static,
    validate_development_records,
)
from research.harness.campaign52_target_replay import (
    TARGET_HEADER,
    TargetRecord,
    run_capture_or_replay,
    serialize_targets,
)
from research.harness.cross_asset_state import compute_btc_macro_state, inject_btc_macro_state
from research.harness.resampler import align_equity_curves
from scripts.run_campaign52_governed_equivalence import (
    SOURCE_SHA256,
    canonical_json,
    sha256_file,
    trade_economics,
    verify_sources,
    write_series,
)
from scripts.run_core_v1_sleeve_contribution_audit import (
    load_data,
    make_execution_configs,
    sleeve_df,
)
from scripts.run_multi_strategy_fund import _build_sleeves
from scripts.run_multi_strategy_walkforward import _build_folds


class Campaign52DevelopmentRunnerError(RuntimeError):
    pass


def build_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Campaign 52 governed development hypothesis test.")
    p.add_argument("--equivalence-root", default="artifacts/campaign52_governed_equivalence")
    p.add_argument("--out-dir", default="artifacts/campaign52_development_execution")
    p.add_argument("--btc-data", default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--eth-data", default="data/ethusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--gld-data", default="data/GLD_1D.csv")
    p.add_argument("--data-start", default="2018-01-01")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2022-12-31")
    p.add_argument("--capital", type=float, default=100000.0)
    p.add_argument("--trend-weight", type=float, default=0.40)
    p.add_argument("--equity-weight", type=float, default=0.35)
    p.add_argument("--gold-weight", type=float, default=0.15)
    p.add_argument("--hedge-weight", type=float, default=0.10)
    p.add_argument("--mr-weight", type=float, default=0.00)
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--equity-fee", type=float, default=0.0001)
    p.add_argument("--base-slippage", type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--cooldown", type=int, default=2)
    p.add_argument("--mr-cooldown", type=int, default=12)
    p.add_argument("--rebalance-threshold", type=float, default=0.02)
    p.add_argument(
        "--pass-workers",
        type=int,
        choices=(1, 2),
        default=2,
        help="Run the two required independent passes concurrently by default.",
    )
    return p.parse_args()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_naive(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def verify_equivalence_root(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest_path = root / "equivalence_manifest.json"
    pass1_path = root / "pass_1" / "artifact_sha256.json"
    pass2_path = root / "pass_2" / "artifact_sha256.json"
    for path in (manifest_path, pass1_path, pass2_path):
        if not path.is_file():
            raise Campaign52DevelopmentRunnerError(f"EQUIVALENCE_INPUT_MISSING:{path}")
    manifest = _load_json(manifest_path)
    required = {
        "status": "PASS",
        "campaign": 52,
        "canonical_capture_equal": True,
        "capture_replay_equal": True,
        "independent_passes": 2,
        "counterfactuals_generated": False,
        "performance_metrics_calculated": False,
        "bootstrap_run": False,
        "runtime_modified": False,
        "strategy_modified": False,
        "weights_modified": False,
    }
    for key, expected in required.items():
        if manifest.get(key) != expected:
            raise Campaign52DevelopmentRunnerError(f"EQUIVALENCE_MANIFEST_FAILURE:{key}")
    if manifest.get("source_sha256") != SOURCE_SHA256:
        raise Campaign52DevelopmentRunnerError("EQUIVALENCE_SOURCE_HASH_MISMATCH")
    pass1 = _load_json(pass1_path)
    pass2 = _load_json(pass2_path)
    if pass1 != pass2 or pass1 != manifest.get("artifact_sha256"):
        raise Campaign52DevelopmentRunnerError("EQUIVALENCE_PASS_HASH_MAP_MISMATCH")
    return manifest, pass1


def load_target_csv(path: Path) -> list[TargetRecord]:
    lowered = path.as_posix().lower().split("/")
    if any(token in lowered for token in ("validation", "2023", "2024", "2025")):
        raise Campaign52DevelopmentRunnerError("VALIDATION_TARGET_PATH_FORBIDDEN")
    rows: list[TargetRecord] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != TARGET_HEADER:
            raise Campaign52DevelopmentRunnerError(f"TARGET_HEADER_MISMATCH:{path}")
        for row in reader:
            rows.append(
                TargetRecord(
                    stage=row["stage"],
                    fold=row["fold"],
                    timestamp=_utc_naive(row["timestamp"]),
                    sleeve_label=row["sleeve_label"],
                    asset=row["asset"],
                    native_timeframe=row["native_timeframe"],
                    strategy_id=row["strategy_id"],
                    action=row["action"],
                    desired_exposure_frac=float(row["desired_exposure_frac"]),
                    signed_target_exposure=float(row["signed_target_exposure"]),
                    sequence_number=int(row["sequence_number"]),
                )
            )
    validate_development_records(rows)
    return rows


def import_development_targets(
    root: Path, hashes: Mapping[str, str]
) -> dict[tuple[str, str], list[TargetRecord]]:
    imported: dict[tuple[str, str], list[TargetRecord]] = {}
    target_paths = sorted(
        key
        for key in hashes
        if key.startswith("development/") and key.endswith("/targets.csv")
    )
    if len(target_paths) != 27:
        raise Campaign52DevelopmentRunnerError(
            f"DEVELOPMENT_TARGET_FILE_COUNT:{len(target_paths)}"
        )
    for relative in target_paths:
        parts = relative.split("/")
        if len(parts) != 4 or parts[1] not in DEVELOPMENT_FOLDS:
            raise Campaign52DevelopmentRunnerError(
                f"INVALID_DEVELOPMENT_TARGET_PATH:{relative}"
            )
        path = root / "pass_1" / relative
        if not path.is_file() or sha256_file(path) != hashes[relative]:
            raise Campaign52DevelopmentRunnerError(f"TARGET_HASH_MISMATCH:{relative}")
        records = load_target_csv(path)
        key = (parts[1], parts[2])
        if key in imported:
            raise Campaign52DevelopmentRunnerError(f"DUPLICATE_TARGET_STREAM:{key}")
        imported[key] = records
    return imported


def replay_ready(records: Sequence[TargetRecord], control_id: str) -> list[TargetRecord]:
    out: list[TargetRecord] = []
    for record in records:
        target = float(record.signed_target_exposure)
        out.append(
            replace(
                record,
                strategy_id=f"campaign52:{control_id}",
                action="HOLD",
                desired_exposure_frac=min(1.0, abs(target)),
            )
        )
    return out


def _write_trade_json(path: Path, trades: Sequence[Any]) -> None:
    canonical_json(path, trade_economics(list(trades)))


def _secondary_metrics(
    daily_nav: pd.Series, trades: Sequence[Any]
) -> dict[str, float | int]:
    log_returns = np.log(daily_nav / daily_nav.shift(1)).dropna()
    std = float(log_returns.std(ddof=1)) if len(log_returns) > 1 else 0.0
    vol = std * math.sqrt(365.25)
    sharpe = float(log_returns.mean() / std * math.sqrt(365.25)) if std > 0 else 0.0

    def worst_days(days: int) -> float:
        values = daily_nav / daily_nav.shift(days) - 1.0
        return float(values.min()) if values.notna().any() else float("nan")

    dd = daily_nav / daily_nav.cummax() - 1.0
    durations: list[int] = []
    current = 0
    for value in dd:
        if value < 0:
            current += 1
        elif current:
            durations.append(current)
            current = 0
    if current:
        durations.append(current)
    total_cost = float(
        sum(
            float(t.fee_usd) + float(t.slippage_usd) + float(t.spread_usd)
            for t in trades
        )
    )
    turnover = float(sum(float(t.notional_usd) for t in trades) / daily_nav.mean())
    return {
        "annualized_volatility": vol,
        "sharpe_zero_benchmark": sharpe,
        "worst_21_calendar_day_return": worst_days(21),
        "worst_63_calendar_day_return": worst_days(63),
        "longest_drawdown_duration_days": max(durations, default=0),
        "median_drawdown_recovery_duration_days": (
            float(np.median(durations)) if durations else 0.0
        ),
        "total_fees_slippage_spread": total_cost,
        "turnover_notional_over_average_nav": turnover,
        "final_equity": float(daily_nav.iloc[-1]),
    }


def _bootstrap_comparison(
    canonical_nav: pd.Series, control_nav: pd.Series, control_id: str
) -> dict[str, Any]:
    common = canonical_nav.index.intersection(control_nav.index)
    can = canonical_nav.loc[common]
    ctl = control_nav.loc[common]
    can_lr = np.log(can / can.shift(1)).dropna().to_numpy(dtype=float)
    ctl_lr = np.log(ctl / ctl.shift(1)).dropna().to_numpy(dtype=float)
    if len(can_lr) != len(ctl_lr) or len(can_lr) < 21:
        raise Campaign52DevelopmentRunnerError(
            f"PAIRED_DAILY_ALIGNMENT_FAILURE:{control_id}"
        )
    n = len(can_lr)
    block = 21
    reps = 10_000
    starts = np.arange(n - block + 1)
    blocks_needed = math.ceil(n / block)
    rng = np.random.default_rng(bootstrap_seed(control_id))
    chosen = rng.choice(starts, size=(reps, blocks_needed), replace=True)
    indices = (chosen[:, :, None] + np.arange(block)[None, None, :]).reshape(
        reps, -1
    )[:, :n]
    can_s = can_lr[indices]
    ctl_s = ctl_lr[indices]
    paired_means = (can_s - ctl_s).mean(axis=1)
    can_paths = np.exp(np.cumsum(can_s, axis=1))
    ctl_paths = np.exp(np.cumsum(ctl_s, axis=1))
    can_dd = 1.0 - np.min(
        can_paths / np.maximum.accumulate(can_paths, axis=1), axis=1
    )
    ctl_dd = 1.0 - np.min(
        ctl_paths / np.maximum.accumulate(ctl_paths, axis=1), axis=1
    )
    annual_factor = 365.25 / n
    can_ret = np.exp(can_s.sum(axis=1) * annual_factor) - 1.0
    ctl_ret = np.exp(ctl_s.sum(axis=1) * annual_factor) - 1.0
    can_calmar = np.divide(
        can_ret, can_dd, out=np.full(reps, np.nan), where=can_dd > 0
    )
    ctl_calmar = np.divide(
        ctl_ret, ctl_dd, out=np.full(reps, np.nan), where=ctl_dd > 0
    )
    return {
        "control_id": control_id,
        "seed": bootstrap_seed(control_id),
        "block_length": block,
        "replications": reps,
        "paired_days": n,
        "observed_mean_daily_log_return_difference": float((can_lr - ctl_lr).mean()),
        "mean_difference_ci95": [
            float(np.percentile(paired_means, 2.5)),
            float(np.percentile(paired_means, 97.5)),
        ],
        "one_sided_p": float(
            (np.count_nonzero(paired_means <= 0.0) + 1) / (reps + 1)
        ),
        "drawdown_difference_ci95": [
            float(np.percentile(ctl_dd - can_dd, 2.5)),
            float(np.percentile(ctl_dd - can_dd, 97.5)),
        ],
        "calmar_difference_ci95": [
            float(np.nanpercentile(can_calmar - ctl_calmar, 2.5)),
            float(np.nanpercentile(can_calmar - ctl_calmar, 97.5)),
        ],
    }


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): sha256_file(p)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _prepare_replay_inputs(
    args: argparse.Namespace,
    raw: Mapping[str, pd.DataFrame],
    specs: Sequence[Any],
    folds: Sequence[Any],
    base_cfg: Any,
    mr_cfg: Any,
    equity_cfg: Any,
) -> dict[tuple[str, str], tuple[pd.DataFrame, Any, pd.Series | None]]:
    """Build immutable fold/sleeve replay inputs once per independent pass."""
    btc_state_full = compute_btc_macro_state(raw["BTC"])
    spy_close = raw["SPY"]["close"]
    spy_sma175_full = (spy_close > spy_close.rolling(175).mean()).rename(
        "spy_above_sma175"
    )
    btc_para_full = btc_state_full["btc_parabolic_hard"].rename("btc_in_parabolic")
    bil_df = pd.read_csv(args.bil_data, index_col=0, parse_dates=True)
    bil_yield_full = pd.to_numeric(bil_df["close"], errors="raise").pct_change().fillna(0.0)

    prepared: dict[tuple[str, str], tuple[pd.DataFrame, Any, pd.Series | None]] = {}
    for fold in folds:
        raw_window = {
            asset: frame.loc[fold.is_start : fold.oos_end]
            for asset, frame in raw.items()
        }
        btc_state_window = btc_state_full.loc[fold.is_start : fold.oos_end]
        spy_window = spy_sma175_full.loc[fold.is_start : fold.oos_end]
        btc_para_window = btc_para_full.loc[fold.is_start : fold.oos_end]
        bil_window = bil_yield_full.loc[fold.is_start : fold.oos_end]
        for spec in specs:
            frame = sleeve_df(raw_window, spec)
            if spec.family == "trend":
                frame = inject_btc_macro_state(frame, btc_state_window)
            if spec.family in ("trend", "hedge"):
                frame = frame.copy()
                frame["spy_above_sma175"] = spy_window.reindex(
                    frame.index, method="ffill"
                )
            if spec.family == "equity":
                frame = frame.copy()
                frame["btc_in_parabolic"] = btc_para_window.reindex(
                    frame.index, method="ffill"
                )
            cfg = (
                equity_cfg
                if spec.family in ("equity", "gold")
                else mr_cfg
                if spec.family == "mr"
                else base_cfg
            )
            cash_yield = bil_window if spec.family in ("equity", "gold") else None
            prepared[(fold.label, spec.label)] = (frame, cfg, cash_yield)
    if len(prepared) != len(folds) * len(specs):
        raise Campaign52DevelopmentRunnerError("PREPARED_REPLAY_INPUT_COUNT_MISMATCH")
    return prepared


def _one_pass(
    args: argparse.Namespace,
    pass_root: Path,
    imported: Mapping[tuple[str, str], Sequence[TargetRecord]],
    raw: Mapping[str, pd.DataFrame],
) -> dict[str, Any]:
    specs = [s for s in _build_sleeves(args) if s.capital > 0]
    folds = [
        f
        for f in _build_folds(args.data_start, args.oos_start, args.oos_end)
        if f.label in DEVELOPMENT_FOLDS
    ]
    base_cfg, mr_cfg, equity_cfg = make_execution_configs(args)

    print(f"{pass_root.name} START prepare replay inputs", flush=True)
    prepared = _prepare_replay_inputs(
        args, raw, specs, folds, base_cfg, mr_cfg, equity_cfg
    )
    print(f"{pass_root.name} DONE prepare replay inputs count={len(prepared)}", flush=True)

    print(f"{pass_root.name} START transformations", flush=True)
    all_records = [r for key in sorted(imported) for r in imported[key]]
    means = static_mean_values(all_records)
    canonical_json(pass_root / "static_mean_manifest.json", means)
    fold_starts = {f.label: _utc_naive(f.is_start) for f in folds}
    fold_ends = {f.label: _utc_naive(f.oos_end) for f in folds}

    transformed: dict[str, dict[tuple[str, str], list[TargetRecord]]] = {}
    transformation_manifest: dict[str, Any] = {"controls": {}}
    for cid in CONTROL_IDS:
        transformed[cid] = {}
        if cid == "static_dev_mean_target":
            for key, records in imported.items():
                transformed[cid][key] = replay_ready(
                    transform_static(records, means), cid
                )
            transformation_manifest["controls"][cid] = {
                "type": "static",
                "means": means,
            }
        elif cid.startswith("lag_"):
            lag = int(cid.split("_")[1].removesuffix("h"))
            counts: dict[str, Any] = {}
            for key, records in imported.items():
                result, info = transform_lag(records, lag)
                transformed[cid][key] = replay_ready(result, cid)
                counts[f"{key[0]}/{key[1]}"] = info
            transformation_manifest["controls"][cid] = {
                "type": "lag",
                "lag_hours": lag,
                "streams": counts,
            }
        else:
            combined, info = transform_block_permutation(
                all_records,
                cid,
                fold_starts=fold_starts,
                fold_ends=fold_ends,
            )
            by_key: dict[tuple[str, str], list[TargetRecord]] = {}
            for record in combined:
                by_key.setdefault((record.fold, record.sleeve_label), []).append(record)
            for key in imported:
                transformed[cid][key] = replay_ready(by_key[key], cid)
            transformation_manifest["controls"][cid] = info
    canonical_json(pass_root / "transformation_manifest.json", transformation_manifest)
    print(f"{pass_root.name} DONE transformations", flush=True)

    target_hashes: dict[str, str] = {}
    for cid in CONTROL_IDS:
        for key in sorted(transformed[cid]):
            fold, sleeve = key
            path = pass_root / "controls" / cid / fold / sleeve / "targets.csv"
            serialize_targets(transformed[cid][key], path)
            target_hashes[path.relative_to(pass_root).as_posix()] = sha256_file(path)
    canonical_json(pass_root / "control_target_sha256.json", target_hashes)

    families: dict[str, Mapping[tuple[str, str], Sequence[TargetRecord]]] = {
        "canonical": imported,
        **transformed,
    }
    daily_navs: dict[str, pd.Series] = {}
    metrics: dict[str, dict[str, Any]] = {}

    for family_id, streams in families.items():
        print(f"{pass_root.name} START family={family_id}", flush=True)
        running_nav = float(args.capital)
        fold_navs: list[pd.Series] = []
        all_trades: list[Any] = []
        for fold in folds:
            curves: dict[str, pd.Series] = {}
            for spec in specs:
                key = (fold.label, spec.label)
                frame, cfg, cash_yield = prepared[key]
                result = run_capture_or_replay(
                    df=frame,
                    strategy_module=None,
                    target_records=list(streams[key]),
                    initial_capital=spec.capital,
                    exec_config=cfg,
                    asset=spec.asset,
                    rebalance_threshold=args.rebalance_threshold,
                    cash_yield_series=cash_yield,
                    stage="development",
                    fold=fold.label,
                    sleeve_label=spec.label,
                    native_timeframe=spec.timeframe,
                ).result
                base = pass_root / "families" / family_id / fold.label / spec.label
                _write_trade_json(base / "trades.json", result.trades)
                write_series(base / "exposure.csv", result.position_series, "exposure")
                write_series(base / "equity.csv", result.equity_curve, "equity")
                curves[spec.label] = result.equity_curve
                all_trades.extend(result.trades)
            fund = (
                align_equity_curves(curves, base_freq="1h")
                .sum(axis=1)
                .loc[fold.oos_start : fold.oos_end]
                .dropna()
            )
            scale = running_nav / float(fund.iloc[0])
            scaled = fund * scale
            running_nav = float(scaled.iloc[-1])
            fold_navs.append(scaled)
            write_series(
                pass_root / "families" / family_id / fold.label / "fold_fund_nav.csv",
                scaled,
                "nav",
            )
        stitched = pd.concat(fold_navs).sort_index()
        stitched = stitched[~stitched.index.duplicated(keep="last")]
        daily = stitched.resample("1D").last().dropna().rename("nav")
        write_series(pass_root / "families" / family_id / "stitched_nav.csv", stitched, "nav")
        write_series(pass_root / "families" / family_id / "daily_nav.csv", daily, "nav")
        daily_navs[family_id] = daily
        metrics[family_id] = {
            **primary_metrics(daily),
            **_secondary_metrics(daily, all_trades),
        }
        print(f"{pass_root.name} DONE family={family_id}", flush=True)

    canonical_json(pass_root / "metrics.json", metrics)
    inference: dict[str, Any] = {}
    raw_p: dict[str, float] = {}
    print(f"{pass_root.name} START bootstrap", flush=True)
    for cid in CONTROL_IDS:
        print(f"{pass_root.name} START bootstrap control={cid}", flush=True)
        result = _bootstrap_comparison(daily_navs["canonical"], daily_navs[cid], cid)
        inference[cid] = result
        raw_p[cid] = float(result["one_sided_p"])
        print(f"{pass_root.name} DONE bootstrap control={cid}", flush=True)
    adjusted = holm_adjust(raw_p)
    for cid in CONTROL_IDS:
        inference[cid]["holm_adjusted_p"] = adjusted[cid]
    canonical_json(pass_root / "inference.json", inference)
    decision = development_decision(
        metrics["canonical"], {cid: metrics[cid] for cid in CONTROL_IDS}, adjusted
    )
    canonical_json(pass_root / "development_decision.json", decision)
    hashes = _hash_tree(pass_root)
    canonical_json(pass_root / "artifact_sha256.json", hashes)
    print(f"{pass_root.name} PASS complete", flush=True)
    return {
        "hashes": hashes,
        "decision": decision,
        "metrics": metrics,
        "inference": inference,
    }


def _run_pass_worker(
    args: argparse.Namespace,
    pass_root: Path,
    equivalence_root: Path,
    artifact_hashes: Mapping[str, str],
) -> dict[str, Any]:
    print(f"{pass_root.name} START load", flush=True)
    imported = import_development_targets(equivalence_root, artifact_hashes)
    raw = load_data(args)
    print(f"{pass_root.name} DONE load", flush=True)
    return _one_pass(args, pass_root, imported, raw)


def main() -> None:
    args = build_args()
    if args.oos_start != "2020-01-01" or args.oos_end != "2022-12-31":
        raise Campaign52DevelopmentRunnerError("DEVELOPMENT_WINDOW_FROZEN")
    source_hashes = verify_sources(args)
    equivalence_root = Path(args.equivalence_root)
    _manifest, artifact_hashes = verify_equivalence_root(equivalence_root)

    final_root = Path(args.out_dir)
    temp_root = final_root.with_name(final_root.name + ".tmp")
    if final_root.exists() or temp_root.exists():
        raise Campaign52DevelopmentRunnerError("STALE_OUTPUT_EXISTS")
    temp_root.mkdir(parents=True)
    try:
        canonical_json(
            temp_root / "input_identity_manifest.json",
            {
                "campaign": 52,
                "stage": "development",
                "source_sha256": source_hashes,
                "equivalence_manifest_sha256": sha256_file(
                    equivalence_root / "equivalence_manifest.json"
                ),
                "equivalence_artifact_sha256": artifact_hashes,
                "validation_targets_opened": False,
                "canonical_strategy_invoked": False,
                "calendar_compatible_block_permutation": True,
                "replay_inputs_cached_per_pass": True,
            },
        )
        if args.pass_workers == 2:
            print("START independent passes workers=2", flush=True)
            with ProcessPoolExecutor(max_workers=2) as pool:
                future1 = pool.submit(
                    _run_pass_worker,
                    args,
                    temp_root / "pass_1",
                    equivalence_root,
                    artifact_hashes,
                )
                future2 = pool.submit(
                    _run_pass_worker,
                    args,
                    temp_root / "pass_2",
                    equivalence_root,
                    artifact_hashes,
                )
                pass1 = future1.result()
                pass2 = future2.result()
        else:
            print("START independent passes workers=1", flush=True)
            imported = import_development_targets(equivalence_root, artifact_hashes)
            raw = load_data(args)
            pass1 = _one_pass(args, temp_root / "pass_1", imported, raw)
            pass2 = _one_pass(args, temp_root / "pass_2", imported, raw)
        if pass1["hashes"] != pass2["hashes"]:
            raise Campaign52DevelopmentRunnerError("INDEPENDENT_PASS_ARTIFACT_MISMATCH")
        if pass1["decision"] != pass2["decision"]:
            raise Campaign52DevelopmentRunnerError("INDEPENDENT_PASS_DECISION_MISMATCH")
        canonical_json(temp_root / "artifact_sha256.json", pass1["hashes"])
        summary = {
            "status": "PASS",
            "campaign": 52,
            "stage": "development",
            "type": "chronological_state_value_hypothesis_test",
            "development_gate_passed": bool(
                pass1["decision"]["development_gate_passed"]
            ),
            "classification": pass1["decision"]["classification"],
            "controls": list(CONTROL_IDS),
            "independent_passes": 2,
            "parallel_pass_workers": args.pass_workers,
            "bootstrap_replications_per_control": 10_000,
            "calendar_compatible_block_permutation": True,
            "replay_inputs_cached_per_pass": True,
            "validation_targets_opened": False,
            "canonical_strategy_invoked": False,
            "runtime_modified": False,
            "strategy_modified": False,
            "weights_modified": False,
        }
        canonical_json(temp_root / "development_decision_manifest.json", summary)
        atomic_promote(temp_root, final_root)
        print(json.dumps(summary, sort_keys=True))
    except Exception:
        if temp_root.exists():
            shutil.rmtree(temp_root)
        raise


if __name__ == "__main__":
    main()
