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
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd


from research.harness.metrics import compute_metrics
from research.harness.resampler import align_equity_curves


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Parallel fold wrapper for Core v1 sleeve contribution audit.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", default=None)
    p.add_argument("--spy-data", default=None)
    p.add_argument("--qqq-data", default=None)
    p.add_argument("--bil-data", default=None)
    p.add_argument("--gld-data", default=None)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--trend-weight", type=float, default=0.40)
    p.add_argument("--equity-weight", type=float, default=0.35)
    p.add_argument("--gold-weight", type=float, default=0.15)
    p.add_argument("--hedge-weight", type=float, default=0.10)
    p.add_argument("--mr-weight", type=float, default=0.00)
    p.add_argument("--data-start", default="2019-01-01")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--equity-fee", type=float, default=0.0001)
    p.add_argument("--base-slippage", type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--cooldown", type=int, default=2)
    p.add_argument("--mr-cooldown", type=int, default=12)
    p.add_argument("--rebalance-threshold", type=float, default=0.02)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--out-dir", default="artifacts/core_v1_sleeve_contribution/baseline_40_35_15_10_parallel")
    return p.parse_args()


def build_folds(oos_start: str, oos_end: str) -> list[tuple[str, str, str]]:
    start = pd.Timestamp(oos_start)
    end = pd.Timestamp(oos_end)
    folds: list[tuple[str, str, str]] = []
    for year in range(start.year, end.year + 1):
        fold_start = max(pd.Timestamp(f"{year}-01-01"), start)
        fold_end = min(pd.Timestamp(f"{year}-12-31"), end)
        if fold_start <= fold_end:
            folds.append((str(year), str(fold_start.date()), str(fold_end.date())))
    return folds


def optional_args(args: argparse.Namespace) -> list[str]:
    pairs = [
        ("--eth-data", args.eth_data),
        ("--spy-data", args.spy_data),
        ("--qqq-data", args.qqq_data),
        ("--bil-data", args.bil_data),
        ("--gld-data", args.gld_data),
    ]
    out: list[str] = []
    for flag, value in pairs:
        if value:
            out.extend([flag, str(value)])
    return out


def run_one_fold(args: argparse.Namespace, fold: tuple[str, str, str], fold_dir: Path) -> dict:
    label, start, end = fold
    cmd = [
        sys.executable,
        "scripts/run_core_v1_sleeve_contribution_audit.py",
        "--btc-data", str(args.btc_data),
        *optional_args(args),
        "--capital", str(args.capital),
        "--trend-weight", str(args.trend_weight),
        "--equity-weight", str(args.equity_weight),
        "--gold-weight", str(args.gold_weight),
        "--hedge-weight", str(args.hedge_weight),
        "--mr-weight", str(args.mr_weight),
        "--data-start", str(args.data_start),
        "--oos-start", start,
        "--oos-end", end,
        "--fee", str(args.fee),
        "--equity-fee", str(args.equity_fee),
        "--base-slippage", str(args.base_slippage),
        "--slippage-vol-factor", str(args.slippage_vol_factor),
        "--cooldown", str(args.cooldown),
        "--mr-cooldown", str(args.mr_cooldown),
        "--rebalance-threshold", str(args.rebalance_threshold),
        "--out-dir", str(fold_dir),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    (fold_dir / "subprocess_stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (fold_dir / "subprocess_stderr.txt").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"Fold {label} failed with code {proc.returncode}. See {fold_dir}")
    summary_path = fold_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    return {"label": label, "start": start, "end": end, "dir": str(fold_dir), "summary": summary}


def load_series(path: Path, name: str) -> pd.Series:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if df.empty:
        return pd.Series(dtype=float, name=name)
    s = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna()
    s.name = name
    return s.sort_index()


def perf_dict(eq: pd.Series, initial_capital: float) -> dict:
    m = compute_metrics(eq.dropna(), [], initial_capital=initial_capital)
    return {
        "cagr_pct": round(m.cagr_pct, 2),
        "total_return_pct": round(m.total_return_pct, 2),
        "max_drawdown_pct": round(m.max_drawdown_pct, 2),
        "sharpe": round(m.sharpe, 3),
        "calmar": round(m.calmar, 3),
        "volatility_ann_pct": round(m.volatility_ann_pct, 2),
        "initial_equity": round(m.initial_equity, 2),
        "final_equity": round(m.final_equity, 2),
    }


def annual_returns(eq: pd.Series) -> dict[str, float]:
    daily = eq.resample("D").last().dropna()
    out: dict[str, float] = {}
    for yr, grp in daily.groupby(daily.index.year):
        if len(grp) >= 5 and float(grp.iloc[0]) != 0:
            out[str(yr)] = round((float(grp.iloc[-1]) / float(grp.iloc[0]) - 1.0) * 100.0, 2)
    return out


def combine_fold_artifacts(args: argparse.Namespace, fold_results: list[dict], out_dir: Path) -> dict:
    combined_dir = out_dir / "combined"
    combined_dir.mkdir(parents=True, exist_ok=True)

    running_nav = float(args.capital)
    fund_parts: list[pd.Series] = []
    sleeve_parts: dict[str, list[pd.Series]] = {}
    summary_frames: list[pd.DataFrame] = []
    annual_frames: list[pd.DataFrame] = []
    audit_frames: list[pd.DataFrame] = []

    for fr in sorted(fold_results, key=lambda x: x["label"]):
        fold_dir = Path(fr["dir"])
        fund_path = fold_dir / "stitched_fund_nav_from_sleeves.csv"
        fund = load_series(fund_path, f"fold_{fr['label']}_fund")
        if fund.empty:
            continue
        scale = running_nav / float(fund.iloc[0])
        scaled_fund = fund * scale
        scaled_fund.name = "fund_nav"
        fund_parts.append(scaled_fund)
        running_nav = float(scaled_fund.iloc[-1])

        sleeve_dir = fold_dir / "stitched_sleeves"
        if sleeve_dir.exists():
            for path in sleeve_dir.glob("*.csv"):
                sleeve = path.stem
                curve = load_series(path, sleeve)
                if curve.empty:
                    continue
                sleeve_parts.setdefault(sleeve, []).append(curve * scale)

        ss = fold_dir / "sleeve_fold_summary.csv"
        if ss.exists():
            df = pd.read_csv(ss)
            df["outer_fold_scale"] = scale
            if "scaled_pnl_dollars" in df.columns:
                df["outer_scaled_pnl_dollars"] = df["scaled_pnl_dollars"] * scale
            summary_frames.append(df)

        ar = fold_dir / "scaled_sleeve_annual_returns.csv"
        if ar.exists():
            annual_frames.append(pd.read_csv(ar))

        audit = fold_dir / "sleeve_cross_asset_state_audit.csv"
        if audit.exists():
            audit_frames.append(pd.read_csv(audit))

    fund_all = pd.concat(fund_parts).sort_index() if fund_parts else pd.Series(dtype=float, name="fund_nav")
    fund_all = fund_all[~fund_all.index.duplicated(keep="last")]
    fund_all.to_csv(combined_dir / "stitched_fund_nav_from_sleeves.csv", header=True)

    stitched_sleeves: dict[str, pd.Series] = {}
    sleeve_out = combined_dir / "stitched_sleeves"
    sleeve_out.mkdir(parents=True, exist_ok=True)
    for sleeve, parts in sleeve_parts.items():
        curve = pd.concat(parts).sort_index()
        curve = curve[~curve.index.duplicated(keep="last")]
        curve.name = sleeve
        stitched_sleeves[sleeve] = curve
        curve.to_csv(sleeve_out / f"{sleeve}.csv", header=True)

    if stitched_sleeves:
        matrix = align_equity_curves(stitched_sleeves, base_freq="1h")
        matrix.to_csv(combined_dir / "stitched_sleeve_equity_matrix.csv")
        matrix.resample("D").last().pct_change().dropna(how="all").corr().to_csv(combined_dir / "sleeve_daily_return_correlation.csv")

    sleeve_summary = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    if not sleeve_summary.empty:
        sleeve_summary.to_csv(combined_dir / "sleeve_fold_summary.csv", index=False)
        pnl_col = "outer_scaled_pnl_dollars" if "outer_scaled_pnl_dollars" in sleeve_summary.columns else "scaled_pnl_dollars"
        if pnl_col not in sleeve_summary.columns:
            pnl_col = "pnl_dollars"
        grouped = sleeve_summary.groupby(["sleeve", "family"], as_index=False).agg(
            capital=("capital", "first"),
            pnl_dollars=(pnl_col, "sum"),
            n_trades=("n_trades", "sum"),
            avg_sharpe=("sharpe", "mean"),
            worst_fold_dd=("max_drawdown_pct", "min"),
            best_fold_return=("total_return_pct", "max"),
            worst_fold_return=("total_return_pct", "min"),
        ).sort_values("pnl_dollars", ascending=False)
        grouped.to_csv(combined_dir / "sleeve_contribution_summary.csv", index=False)
        sleeve_contrib = grouped.to_dict(orient="records")
    else:
        sleeve_contrib = []

    if annual_frames:
        pd.concat(annual_frames, ignore_index=True).to_csv(combined_dir / "scaled_sleeve_annual_returns.csv", index=False)
    if audit_frames:
        pd.concat(audit_frames, ignore_index=True).to_csv(combined_dir / "sleeve_cross_asset_state_audit.csv", index=False)

    summary = {
        "fund_metrics": perf_dict(fund_all, args.capital) if not fund_all.empty else {},
        "fund_annual_returns": annual_returns(fund_all) if not fund_all.empty else {},
        "sleeve_contribution_summary": sleeve_contrib,
        "fold_results": fold_results,
        "config": vars(args),
    }
    (combined_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    folds_dir = out_dir / "folds"
    folds_dir.mkdir(parents=True, exist_ok=True)

    folds = build_folds(args.oos_start, args.oos_end)
    workers = max(1, min(int(args.workers), len(folds)))
    print(f"Running {len(folds)} fold audits with {workers} workers")

    fold_results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(run_one_fold, args, fold, folds_dir / fold[0]): fold
            for fold in folds
        }
        for future in as_completed(future_map):
            fold = future_map[future]
            result = future.result()
            fold_results.append(result)
            m = result.get("summary", {}).get("fund_metrics", {})
            print(
                f"Fold {fold[0]} complete: CAGR {m.get('cagr_pct', 0):.2f}% "
                f"MaxDD {m.get('max_drawdown_pct', 0):.2f}% "
                f"Sharpe {m.get('sharpe', 0):.3f}"
            )

    summary = combine_fold_artifacts(args, fold_results, out_dir)
    m = summary.get("fund_metrics", {})
    print(
        "Combined reconstructed fund → "
        f"CAGR {m.get('cagr_pct', 0):.2f}% "
        f"MaxDD {m.get('max_drawdown_pct', 0):.2f}% "
        f"Sharpe {m.get('sharpe', 0):.3f} "
        f"Calmar {m.get('calmar', 0):.3f}"
    )
    print(f"Wrote combined artifacts to {out_dir / 'combined'}")


if __name__ == "__main__":
    main()
