#!/usr/bin/env python
"""IteraDynamics — confidence-threshold sweep helper.

Runs baseline + calibrated backtests across a set of confidence gates and writes
an easy-to-compare table (CSV/JSON/Markdown) plus per-run artifacts.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from research.harness.artifacts import save_artifacts
from research.harness.backtest_engine import run_backtest
from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import compute_metrics
from research.ml.calibration.model_store import load_calibrator
from research.strategies import REGISTRY as STRATEGY_REGISTRY

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sweep_confidence_thresholds")


def _parse_csv_floats(raw: str | None) -> list[float]:
    if raw is None or raw.strip() == "":
        return []
    out: list[float] = []
    for chunk in raw.split(","):
        s = chunk.strip()
        if not s:
            continue
        out.append(float(s))
    return out


def _threshold_label(t: float) -> str:
    return f"mc{t:.3f}".replace(".", "p")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sweep calibrated confidence-gate thresholds and compare outputs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data", required=True, help="Path to OHLCV CSV")
    p.add_argument(
        "--strategy",
        required=True,
        choices=list(STRATEGY_REGISTRY.keys()),
        help="Strategy to backtest",
    )
    p.add_argument("--asset", default="BTC", help="Asset label")
    p.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    p.add_argument("--capital", type=float, default=100_000.0, help="Initial capital (USD)")
    p.add_argument("--fee", type=float, default=None, help="Taker fee rate (e.g. 0.0008)")
    p.add_argument("--base-slippage", type=float, default=None, help="Base slippage floor in bps")
    p.add_argument("--slippage-size-factor", type=float, default=None, help="Slippage bps per 100%% NAV turnover")
    p.add_argument("--slippage-vol-factor", type=float, default=None, help="Slippage bps per 100%% ATR")
    p.add_argument("--cooldown", type=int, default=None, help="Minimum bars between trades")
    p.add_argument("--rebalance-threshold", type=float, default=0.05, help="Min exposure delta to trade")
    p.add_argument(
        "--calibrators-dir",
        default=None,
        help="Directory for calibrator JSON files (default: artifacts/ml_models/)",
    )
    p.add_argument(
        "--percentiles",
        default="10,25,50",
        help="Percentiles from calibrated entry-confidence distribution to test",
    )
    p.add_argument(
        "--thresholds",
        default="",
        help="Additional explicit thresholds to test, comma-separated (e.g. 0.35,0.40,0.45)",
    )
    p.add_argument(
        "--out-dir",
        default="artifacts/comparison/threshold_sweep",
        help="Output directory for sweep artifacts",
    )
    p.add_argument("--no-chart", action="store_true", help="Skip chart generation")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    runs_dir = out_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    log.info("Loading data: %s", args.data)
    df = load_ohlcv(args.data, start=args.start, end=args.end, asset=args.asset)
    for warning in validate_ohlcv(df):
        log.warning("Data warning: %s", warning)
    log.info("Loaded %d bars (%s -> %s)", len(df), df.index[0], df.index[-1])

    strategy_module = STRATEGY_REGISTRY[args.strategy]
    strategy_id = args.strategy

    exec_config = ExecutionConfig.from_env()
    if args.fee is not None:
        exec_config.taker_fee_rate = args.fee
    if args.base_slippage is not None:
        exec_config.base_slippage_bps = args.base_slippage
    if args.slippage_size_factor is not None:
        exec_config.slippage_size_factor = args.slippage_size_factor
    if args.slippage_vol_factor is not None:
        exec_config.slippage_vol_factor = args.slippage_vol_factor
    if args.cooldown is not None:
        exec_config.cooldown_bars = args.cooldown

    calibrator = load_calibrator(strategy_id, models_dir=args.calibrators_dir)
    if calibrator is None or not calibrator.is_fitted:
        raise SystemExit(
            f"No fitted calibrator found for '{strategy_id}' in "
            f"{args.calibrators_dir or 'artifacts/ml_models/'}"
        )
    calibrators = {strategy_id: calibrator}
    log.info(
        "Loaded calibrator for %s (method=%s n_samples=%d)",
        strategy_id,
        calibrator.calibration_method,
        calibrator.n_samples,
    )

    def run_one(label: str, use_calibrator: bool, min_conf: float | None) -> dict:
        cals = calibrators if use_calibrator else None
        result = run_backtest(
            df=df,
            strategy_module=strategy_module,
            initial_capital=args.capital,
            exec_config=exec_config,
            rebalance_threshold=args.rebalance_threshold,
            asset=args.asset,
            calibrators=cals,
            min_confidence_to_enter=min_conf,
        )
        metrics = compute_metrics(result.equity_curve, result.trades, result.params)
        save_artifacts(
            result=result,
            metrics=metrics,
            run_id=label,
            out_dir=runs_dir / label,
            save_chart=not args.no_chart,
        )
        blocked = int(result.params.get("blocked_entry_intents", 0))
        total_entries = int(result.params.get("total_entry_intents", 0))
        blocked_pct = (100.0 * blocked / total_entries) if total_entries > 0 else 0.0
        return {
            "label": label,
            "calibrated": use_calibrator,
            "min_confidence": min_conf,
            "final_equity": metrics.final_equity,
            "total_return_pct": metrics.total_return_pct,
            "cagr_pct": metrics.cagr_pct,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "sharpe": metrics.sharpe,
            "n_trades": metrics.n_trades,
            "blocked_entry_intents": blocked,
            "total_entry_intents": total_entries,
            "blocked_entry_pct": round(blocked_pct, 2),
        }

    # Discovery run (calibrated, no gate) provides percentile-based thresholds.
    discovery = run_one("calibrated_no_gate", use_calibrator=True, min_conf=None)
    discovery_summary_path = runs_dir / "calibrated_no_gate" / "summary.json"
    with open(discovery_summary_path, "r", encoding="utf-8") as f:
        discovery_summary = json.load(f)
    conf_stats = discovery_summary.get("backtest_params", {}).get("entry_confidence_stats", {})

    percentile_values: list[float] = []
    for p in _parse_csv_floats(args.percentiles):
        key = f"p{int(p)}"
        if key in conf_stats:
            percentile_values.append(float(conf_stats[key]))

    explicit_values = _parse_csv_floats(args.thresholds)
    sweep_thresholds = sorted({round(v, 6) for v in (percentile_values + explicit_values)})

    rows: list[dict] = []
    rows.append(run_one("baseline", use_calibrator=False, min_conf=None))
    rows.append(discovery)
    for t in sweep_thresholds:
        rows.append(run_one(_threshold_label(t), use_calibrator=True, min_conf=t))

    # Write comparison outputs
    csv_path = out_dir / "comparison.csv"
    json_path = out_dir / "comparison.json"
    md_path = out_dir / "comparison.md"
    pct_path = out_dir / "derived_thresholds.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    with open(pct_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "entry_confidence_stats": conf_stats,
                "percentiles_requested": _parse_csv_floats(args.percentiles),
                "percentile_thresholds_used": percentile_values,
                "explicit_thresholds_used": explicit_values,
                "all_thresholds_used": sweep_thresholds,
            },
            f,
            indent=2,
        )

    # CSV
    headers = list(rows[0].keys()) if rows else []
    lines = [",".join(headers)]
    for row in rows:
        vals: list[str] = []
        for h in headers:
            v = row[h]
            vals.append("" if v is None else str(v))
        lines.append(",".join(vals))
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Markdown
    md_lines = [
        f"# Confidence Threshold Sweep: {args.strategy} / {args.asset}",
        "",
        "## Derived entry-confidence stats",
        f"- n_entry_intents: {conf_stats.get('n_entry_intents', 0)}",
        f"- min/p25/p50/p75/max: "
        f"{conf_stats.get('min', 0)} / {conf_stats.get('p25', 0)} / "
        f"{conf_stats.get('p50', 0)} / {conf_stats.get('p75', 0)} / {conf_stats.get('max', 0)}",
        "",
        "## Results",
        "| label | calibrated | min_confidence | return_pct | cagr_pct | sharpe | max_dd_pct | trades | blocked_pct |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        md_lines.append(
            "| {label} | {calibrated} | {min_confidence} | {total_return_pct:.4f} | "
            "{cagr_pct:.4f} | {sharpe:.4f} | {max_drawdown_pct:.4f} | {n_trades} | "
            "{blocked_entry_pct:.2f} |".format(**row)
        )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    log.info("Sweep complete. Outputs:")
    log.info("  %s", csv_path)
    log.info("  %s", json_path)
    log.info("  %s", md_path)
    log.info("  %s", pct_path)
    print("\nTop-level outputs:")
    print(f"  {csv_path}")
    print(f"  {json_path}")
    print(f"  {md_path}")
    print(f"  {pct_path}")
    print(f"  per-run artifacts under: {runs_dir}")


if __name__ == "__main__":
    main()

