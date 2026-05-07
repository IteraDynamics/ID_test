#!/usr/bin/env python
"""Fund Side-by-Side Composite v1.

Research-only investor-view composite. Combines an explicit crypto sleeve equity
curve with an equity sleeve curve under static capital weights.

This is not a dynamic allocator and does not change runtime, broker execution,
paper trading, governors, dashboards, or live allocation.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd


DEFAULT_OUT = "artifacts/fund_side_by_side_composite_v1"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0
DEFAULT_CRYPTO_BENCHMARKS = "BTC_HODL,ETH_HODL,BTC_ETH_50_50_DAILY_REBAL,BTC_ETH_60_40_DAILY_REBAL"
WINDOWS = [
    ("FULL", "1900-01-01", "2100-01-01"),
    ("COVID_2020", "2020-02-01", "2020-06-30"),
    ("BEAR_2022", "2022-01-01", "2022-12-31"),
    ("POST_2022_RECOVERY", "2023-01-01", "2024-12-31"),
    ("RECENT_2025_PLUS", "2025-01-01", "2100-01-01"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a static side-by-side crypto/equity fund composite",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--crypto-curve", required=True, help="CSV containing the crypto sleeve equity curve.")
    p.add_argument("--crypto-column", required=True, help="Column inside --crypto-curve to use as crypto sleeve.")
    p.add_argument("--crypto-benchmark-columns", default=DEFAULT_CRYPTO_BENCHMARKS)
    p.add_argument("--equity-curve", default=None, help="Optional CSV containing an equity sleeve curve.")
    p.add_argument("--equity-column", default=None, help="Column inside --equity-curve to use as equity sleeve.")
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--equity-core-window", type=int, default=175)
    p.add_argument("--weights", default="50/50,60/40,70/30,40/60,30/70", help="Crypto/equity static weights.")
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _parse_csv_list(raw: str) -> list[str]:
    out = []
    for part in str(raw).split(","):
        value = part.strip()
        if value:
            out.append(value)
    return list(dict.fromkeys(out))


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_csv_with_datetime_index(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty CSV: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    return df


def _curve_from_df(df: pd.DataFrame, column: str, label: str) -> pd.Series:
    if column not in df.columns:
        raise ValueError(f"{label} column '{column}' not found. Columns={list(df.columns)}")
    s = pd.to_numeric(df[column], errors="coerce").dropna().astype(float)
    if len(s) < 2:
        raise ValueError(f"{label} curve has insufficient rows: {column}")
    if s.iloc[0] <= 0:
        raise ValueError(f"{label} curve must start positive: {column}")
    return s.rename(label)


def _load_curve(path: Path, column: str, label: str) -> pd.Series:
    return _curve_from_df(_read_csv_with_datetime_index(path), column, label)


def _load_optional_curves(path: Path, columns: Iterable[str]) -> tuple[dict[str, pd.Series], list[str]]:
    df = _read_csv_with_datetime_index(path)
    curves: dict[str, pd.Series] = {}
    skipped: list[str] = []
    for col in columns:
        if col not in df.columns:
            skipped.append(col)
            continue
        try:
            curves[col] = _curve_from_df(df, col, col)
        except Exception:
            skipped.append(col)
    return curves, skipped


def _load_close(path: Path, label: str) -> pd.Series:
    df = _read_csv_with_datetime_index(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "close" not in df.columns:
        raise ValueError(f"{label} data missing close column; got {list(df.columns)}")
    return pd.to_numeric(df["close"], errors="coerce").dropna().rename(label.upper())


def _equity_core_bil_curve(spy: pd.Series, qqq: pd.Series, bil: pd.Series | None, sma_window: int, capital: float) -> pd.Series:
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ")], axis=1).dropna()
    spy_sma = prices["SPY"].rolling(sma_window, min_periods=sma_window).mean()
    qqq_sma = prices["QQQ"].rolling(sma_window, min_periods=sma_window).mean()
    weights = pd.DataFrame(
        {
            "SPY": 0.5 * (prices["SPY"] > spy_sma).astype(float),
            "QQQ": 0.5 * (prices["QQQ"] > qqq_sma).astype(float),
        },
        index=prices.index,
    )
    weights["DEF"] = 1.0 - weights["SPY"] - weights["QQQ"]
    data = prices.copy()
    if bil is not None:
        data = pd.concat([data, bil.rename("DEF")], axis=1).dropna()
        weights = weights.reindex(data.index).fillna(0.0)
        def_rets = data["DEF"].pct_change(fill_method=None).fillna(0.0)
    else:
        weights = weights.reindex(data.index).fillna(0.0)
        def_rets = pd.Series(0.0, index=data.index)
    rets = data[["SPY", "QQQ"]].pct_change(fill_method=None).fillna(0.0)
    exec_w = weights.shift(1).fillna({"SPY": 0.0, "QQQ": 0.0, "DEF": 1.0})
    port_rets = exec_w["SPY"] * rets["SPY"] + exec_w["QQQ"] * rets["QQQ"] + exec_w["DEF"] * def_rets
    return (float(capital) * (1.0 + port_rets).cumprod()).rename("EQUITY_SLEEVE")


def _asset_curve(price: pd.Series, capital: float, name: str) -> pd.Series:
    rets = price.dropna().pct_change(fill_method=None).fillna(0.0)
    return (float(capital) * (1.0 + rets).cumprod()).rename(name)


def _passive_spy_qqq(spy: pd.Series, qqq: pd.Series, capital: float) -> pd.Series:
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ")], axis=1).dropna()
    rets = prices.pct_change(fill_method=None).fillna(0.0)
    return (float(capital) * (1.0 + (0.5 * rets["SPY"] + 0.5 * rets["QQQ"])).cumprod()).rename("PASSIVE_SPY_QQQ_50_50")


def _normalize(s: pd.Series, capital: float) -> pd.Series:
    s = s.dropna().astype(float)
    if s.empty or s.iloc[0] <= 0:
        raise ValueError("Cannot normalize empty/non-positive curve")
    return (float(capital) * s / s.iloc[0]).rename(s.name)


def _parse_weights(raw: str) -> list[tuple[str, float, float]]:
    out = []
    for part in str(raw).split(","):
        piece = part.strip()
        if not piece:
            continue
        if "/" in piece:
            left, right = piece.split("/", 1)
            cw = float(left.strip()) / 100.0
            ew = float(right.strip()) / 100.0
        elif ":" in piece:
            left, right = piece.split(":", 1)
            cw = float(left.strip())
            ew = float(right.strip())
        else:
            raise ValueError(f"Invalid weight format '{piece}', expected 60/40 or 0.6:0.4")
        total = cw + ew
        if total <= 0:
            raise ValueError(f"Invalid non-positive total weight: {piece}")
        cw /= total
        ew /= total
        label = f"FUND_STATIC_CRYPTO{int(round(cw * 100)):02d}_EQUITY{int(round(ew * 100)):02d}"
        out.append((label, cw, ew))
    if not out:
        raise ValueError("No valid weights supplied")
    return out


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return TRADING_DAYS
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return TRADING_DAYS
    med = float(deltas.median())
    if med <= 0:
        return TRADING_DAYS
    if med >= 20 * 3600:
        return TRADING_DAYS
    return float(365.25 * 24 * 3600 / med)


def _max_time_underwater_days(eq: pd.Series) -> float:
    eq = eq.dropna().astype(float)
    dd = eq / eq.cummax() - 1.0
    start = None
    max_days = 0.0
    for ts, flag in (dd < 0).items():
        if flag and start is None:
            start = ts
        elif not flag and start is not None:
            max_days = max(max_days, (ts - start).total_seconds() / 86400.0)
            start = None
    if start is not None:
        max_days = max(max_days, (eq.index[-1] - start).total_seconds() / 86400.0)
    return float(max_days)


def _sortino(eq: pd.Series) -> float:
    rets = eq.dropna().astype(float).pct_change(fill_method=None).dropna()
    if rets.empty:
        return 0.0
    downside = np.minimum(rets, 0.0)
    downside_dev = float(np.sqrt(np.mean(np.square(downside))))
    if downside_dev <= 1e-12:
        return 0.0
    return float((rets.mean() / downside_dev) * math.sqrt(_bars_per_year(eq.index)))


def _perf(eq: pd.Series) -> dict[str, float]:
    eq = eq.dropna().astype(float)
    if len(eq) < 2:
        return {}
    rets = eq.pct_change(fill_method=None).dropna()
    years = max((eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 24 * 3600), 1e-9)
    total = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    std = float(rets.std(ddof=0)) if len(rets) else 0.0
    bpy = _bars_per_year(eq.index)
    sharpe = float((rets.mean() / std) * math.sqrt(bpy)) if std > 1e-12 else 0.0
    ann_vol = float(std * math.sqrt(bpy)) if std > 0 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    worst_90 = float(eq.pct_change(90, fill_method=None).dropna().min()) if len(eq) > 90 else 0.0
    worst_180 = float(eq.pct_change(180, fill_method=None).dropna().min()) if len(eq) > 180 else 0.0
    return {
        "total_return_pct": total * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "sortino": _sortino(eq),
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
        "worst_90d_return_pct": worst_90 * 100.0,
        "worst_180d_return_pct": worst_180 * 100.0,
        "max_time_underwater_days": _max_time_underwater_days(eq),
    }


def _slice(eq: pd.Series, start: str, end: str) -> pd.Series:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    return eq.loc[(eq.index >= start_ts) & (eq.index <= end_ts)].dropna()


def _capture(series: pd.Series, benchmark: pd.Series) -> dict[str, float]:
    common = series.dropna().index.intersection(benchmark.dropna().index)
    if len(common) < 2:
        return {}
    s = _normalize(series.loc[common], 1.0)
    b = _normalize(benchmark.loc[common], 1.0)
    sr = s.pct_change(fill_method=None).dropna()
    br = b.pct_change(fill_method=None).dropna()
    common_rets = sr.index.intersection(br.index)
    sr = sr.loc[common_rets]
    br = br.loc[common_rets]
    b_total = b.iloc[-1] / b.iloc[0] - 1.0
    s_total = s.iloc[-1] / s.iloc[0] - 1.0
    up = br > 0
    down = br < 0
    return {
        "return_capture_ratio": float(s_total / b_total) if abs(b_total) > 1e-12 else 0.0,
        "up_day_capture_ratio": float(sr[up].sum() / br[up].sum()) if up.any() and abs(br[up].sum()) > 1e-12 else 0.0,
        "down_day_capture_ratio": float(sr[down].sum() / br[down].sum()) if down.any() and abs(br[down].sum()) > 1e-12 else 0.0,
        "vol_ratio": float(sr.std(ddof=0) / br.std(ddof=0)) if br.std(ddof=0) > 1e-12 else 0.0,
    }


def _fmt_md_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if pd.isna(value):
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if max_rows is not None:
        df = df.head(max_rows)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt_md_value(row[c]) for c in df.columns) + " |")
    return "\n".join(lines)


def _write_summary_md(path: Path, perf: pd.DataFrame, capture: pd.DataFrame, window_perf: pd.DataFrame, payload: dict) -> None:
    lines = [
        "# Fund Side-by-Side Composite v1",
        "",
        "Research-only investor-view composite of independent crypto and equity systems under static weights.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Crypto curve: {payload['inputs']['crypto_curve']}::{payload['inputs']['crypto_column']}",
        f"Crypto benchmarks loaded: {', '.join(payload['inputs']['loaded_crypto_benchmarks']) or 'none'}",
        f"Equity source: {payload['inputs']['equity_source']}",
        f"Weights: {payload['inputs']['weights']}",
        f"Common overlap: {payload['common_overlap']['start']} → {payload['common_overlap']['end']} ({payload['common_overlap']['bars']} bars)",
        "```",
        "",
        "## Performance Summary",
        "",
        _md_table(perf, max_rows=60),
        "",
        "## Capture Summary",
        "",
        _md_table(capture, max_rows=120),
        "",
        "## Window Performance Summary",
        "",
        _md_table(window_perf, max_rows=120),
        "",
        "## Guardrail",
        "",
        "```text",
        "Research only. This is not a dynamic allocator and does not approve paper trading, live allocation, broker/execution, runtime, dashboard, or global allocator changes.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    crypto = _load_curve(Path(args.crypto_curve), args.crypto_column, "CRYPTO_SLEEVE")
    crypto_benchmarks, skipped_crypto_benchmarks = _load_optional_curves(
        Path(args.crypto_curve), _parse_csv_list(args.crypto_benchmark_columns)
    )

    if args.equity_curve and args.equity_column:
        equity = _load_curve(Path(args.equity_curve), args.equity_column, "EQUITY_SLEEVE")
        equity_source = f"{args.equity_curve}::{args.equity_column}"
    else:
        spy = _load_close(Path(args.spy_data), "SPY")
        qqq = _load_close(Path(args.qqq_data), "QQQ")
        bil = _load_close(Path(args.bil_data), "BIL") if Path(args.bil_data).exists() else None
        equity = _equity_core_bil_curve(spy, qqq, bil, args.equity_core_window, args.capital).rename("EQUITY_SLEEVE")
        equity_source = f"computed_SPY_QQQ_SMA{args.equity_core_window}_{'BIL' if bil is not None else 'CASH'}"

    common = crypto.dropna().index.intersection(equity.dropna().index)
    if len(common) < 20:
        raise ValueError(f"Insufficient common overlap between crypto and equity curves: {len(common)} bars")

    curves: dict[str, pd.Series] = {
        "CRYPTO_SLEEVE": _normalize(crypto.loc[common], args.capital).rename("CRYPTO_SLEEVE"),
        "EQUITY_SLEEVE": _normalize(equity.loc[common], args.capital).rename("EQUITY_SLEEVE"),
    }

    crypto_rets = curves["CRYPTO_SLEEVE"].pct_change(fill_method=None).fillna(0.0)
    equity_rets = curves["EQUITY_SLEEVE"].pct_change(fill_method=None).fillna(0.0)
    for label, cw, ew in _parse_weights(args.weights):
        port_rets = cw * crypto_rets + ew * equity_rets
        curves[label] = (args.capital * (1.0 + port_rets).cumprod()).rename(label)

    # Benchmarks over their own data, normalized to the composite common overlap where possible.
    benchmark_curves: dict[str, pd.Series] = {}
    for name, curve in crypto_benchmarks.items():
        benchmark_curves[name] = curve.rename(name)
    try:
        spy = _load_close(Path(args.spy_data), "SPY")
        qqq = _load_close(Path(args.qqq_data), "QQQ")
        benchmark_curves["SPY_HODL"] = _asset_curve(spy, args.capital, "SPY_HODL")
        benchmark_curves["QQQ_HODL"] = _asset_curve(qqq, args.capital, "QQQ_HODL")
        benchmark_curves["PASSIVE_SPY_QQQ_50_50"] = _passive_spy_qqq(spy, qqq, args.capital)
    except Exception:
        pass

    for name, curve in benchmark_curves.items():
        idx = common.intersection(curve.dropna().index)
        if len(idx) >= 20:
            curves[name] = _normalize(curve.loc[idx], args.capital).rename(name)

    curve_df = pd.concat(curves.values(), axis=1)
    perf_rows = []
    for name, curve in curves.items():
        clean = curve.dropna()
        perf_rows.append({"series": name, "start": str(clean.index[0]), "end": str(clean.index[-1]), "bars": len(clean), **_perf(clean)})
    perf = pd.DataFrame(perf_rows).sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])

    capture_rows = []
    benchmark_names = [
        n for n in [
            "CRYPTO_SLEEVE",
            "EQUITY_SLEEVE",
            "BTC_HODL",
            "ETH_HODL",
            "BTC_ETH_50_50_DAILY_REBAL",
            "BTC_ETH_60_40_DAILY_REBAL",
            "SPY_HODL",
            "QQQ_HODL",
            "PASSIVE_SPY_QQQ_50_50",
        ] if n in curves
    ]
    composite_names = [n for n in curves if n.startswith("FUND_STATIC_")]
    for series_name in composite_names:
        for bench_name in benchmark_names:
            metrics = _capture(curves[series_name], curves[bench_name])
            if metrics:
                capture_rows.append({"series": series_name, "benchmark": bench_name, **metrics})
    capture = pd.DataFrame(capture_rows)

    window_rows = []
    for win_name, start, end in WINDOWS:
        for name, curve in curves.items():
            sub = _slice(curve, start, end)
            if len(sub) < 20:
                continue
            window_rows.append({"window": win_name, "series": name, "start": str(sub.index[0]), "end": str(sub.index[-1]), "bars": len(sub), **_perf(sub)})
    window_perf = pd.DataFrame(window_rows).sort_values(["window", "calmar", "sharpe"], ascending=[True, False, False]) if window_rows else pd.DataFrame()

    curve_df.to_csv(out_dir / "equity_curves.csv")
    perf.to_csv(out_dir / "performance_summary.csv", index=False)
    capture.to_csv(out_dir / "capture_summary.csv", index=False)
    window_perf.to_csv(out_dir / "window_performance_summary.csv", index=False)

    payload = {
        "research_status": "research_only_fund_side_by_side_composite_v1",
        "inputs": {
            "crypto_curve": args.crypto_curve,
            "crypto_column": args.crypto_column,
            "crypto_benchmark_columns_requested": _parse_csv_list(args.crypto_benchmark_columns),
            "loaded_crypto_benchmarks": list(crypto_benchmarks.keys()),
            "skipped_crypto_benchmarks": skipped_crypto_benchmarks,
            "equity_source": equity_source,
            "weights": args.weights,
            "capital": args.capital,
        },
        "common_overlap": {"start": str(common[0]), "end": str(common[-1]), "bars": int(len(common))},
        "artifacts": {
            "equity_curves": str(out_dir / "equity_curves.csv"),
            "performance_summary": str(out_dir / "performance_summary.csv"),
            "capture_summary": str(out_dir / "capture_summary.csv"),
            "window_performance_summary": str(out_dir / "window_performance_summary.csv"),
            "input_summary": str(out_dir / "input_summary.json"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {"status": "diagnostic_only", "not_approved": ["dynamic_allocator", "paper_trading", "live_allocation", "broker_change", "runtime_change", "dashboard_change"]},
    }
    (out_dir / "input_summary.json").write_text(json.dumps(payload["inputs"], indent=2), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", perf, capture, window_perf, payload)

    with pd.option_context("display.max_columns", None, "display.width", 420, "display.float_format", "{:.4f}".format):
        print("\n=== FUND SIDE-BY-SIDE COMPOSITE V1 ===")
        print(f"Crypto input: {args.crypto_curve}::{args.crypto_column}")
        print(f"Crypto benchmarks loaded: {', '.join(crypto_benchmarks.keys()) if crypto_benchmarks else 'none'}")
        if skipped_crypto_benchmarks:
            print(f"Crypto benchmarks skipped: {', '.join(skipped_crypto_benchmarks)}")
        print(f"Equity source: {equity_source}")
        print(f"Common overlap: {common[0]} → {common[-1]} ({len(common)} bars)")
        print("\nPerformance Summary:")
        print(perf.to_string(index=False))
        print("\nCapture Summary:")
        print(capture.to_string(index=False) if not capture.empty else "No capture rows.")
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
