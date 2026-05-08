#!/usr/bin/env python
"""Fund Paper Readiness v1 — static sleeve ledger.

Research-only fund accounting simulation for Itera's promoted two-sleeve
architecture. This script consumes precomputed sleeve equity curves and produces
an explicit paper-fund ledger with NAV, sleeve weights, drift, and rebalance
events.

No broker orders, live trading, runtime integration, dashboard integration, or
dynamic allocation decisions are made.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd


DEFAULT_CURVES = "artifacts/fund_side_by_side_composite_v1_tilted_4s/equity_curves.csv"
DEFAULT_OUT = "artifacts/fund_paper_readiness_v1"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0
WINDOWS = [
    ("FULL", "1900-01-01", "2100-01-01"),
    ("COVID_2020", "2020-02-01", "2020-06-30"),
    ("BEAR_2022", "2022-01-01", "2022-12-31"),
    ("POST_2022_RECOVERY", "2023-01-01", "2024-12-31"),
    ("RECENT_2025_PLUS", "2025-01-01", "2100-01-01"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a static two-sleeve fund paper-readiness ledger",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--curves", default=DEFAULT_CURVES, help="CSV containing CRYPTO_SLEEVE and EQUITY_SLEEVE curves.")
    p.add_argument("--crypto-column", default="CRYPTO_SLEEVE")
    p.add_argument("--equity-column", default="EQUITY_SLEEVE")
    p.add_argument("--target-weights", default="50/50", help="Crypto/equity static target, e.g. 50/50 or 60/40.")
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--rebalance-threshold", type=float, default=0.05, help="Absolute weight drift threshold that triggers a ledger rebalance.")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_curves(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing curves file: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty curves file: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    return df


def _parse_weights(raw: str) -> tuple[float, float]:
    piece = str(raw).strip()
    if "/" in piece:
        left, right = piece.split("/", 1)
        cw = float(left.strip()) / 100.0
        ew = float(right.strip()) / 100.0
    elif ":" in piece:
        left, right = piece.split(":", 1)
        cw = float(left.strip())
        ew = float(right.strip())
    else:
        raise ValueError(f"Invalid target weight format '{raw}', expected 50/50 or 0.5:0.5")
    total = cw + ew
    if total <= 0:
        raise ValueError(f"Invalid non-positive target weights: {raw}")
    cw /= total
    ew /= total
    return cw, ew


def _normalize_curve(s: pd.Series, capital: float) -> pd.Series:
    clean = pd.to_numeric(s, errors="coerce").dropna().astype(float)
    if clean.empty or clean.iloc[0] <= 0:
        raise ValueError("Cannot normalize empty or non-positive curve")
    return capital * clean / clean.iloc[0]


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
    if eq.empty:
        return 0.0
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


def _simulate_ledger(
    crypto_curve: pd.Series,
    equity_curve: pd.Series,
    capital: float,
    crypto_target: float,
    equity_target: float,
    rebalance_threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    aligned = pd.concat(
        [crypto_curve.rename("crypto_curve"), equity_curve.rename("equity_curve")],
        axis=1,
    ).dropna()
    if len(aligned) < 2:
        raise ValueError("Need at least two aligned rows to simulate ledger")

    crypto_rets = aligned["crypto_curve"].pct_change(fill_method=None).fillna(0.0)
    equity_rets = aligned["equity_curve"].pct_change(fill_method=None).fillna(0.0)

    crypto_nav = float(capital) * crypto_target
    equity_nav = float(capital) * equity_target
    high_water = float(capital)
    rows: list[dict[str, Any]] = []
    rebalance_rows: list[dict[str, Any]] = []

    for i, ts in enumerate(aligned.index):
        if i > 0:
            crypto_nav *= 1.0 + float(crypto_rets.loc[ts])
            equity_nav *= 1.0 + float(equity_rets.loc[ts])

        fund_nav_pre = crypto_nav + equity_nav
        crypto_weight_pre = crypto_nav / fund_nav_pre if fund_nav_pre else 0.0
        equity_weight_pre = equity_nav / fund_nav_pre if fund_nav_pre else 0.0
        crypto_drift = crypto_weight_pre - crypto_target
        equity_drift = equity_weight_pre - equity_target
        max_abs_drift = max(abs(crypto_drift), abs(equity_drift))
        rebalance_needed = max_abs_drift >= rebalance_threshold
        rebalance_executed = bool(rebalance_needed)
        rebalance_amount_crypto = 0.0
        rebalance_amount_equity = 0.0

        if rebalance_executed:
            target_crypto_nav = fund_nav_pre * crypto_target
            target_equity_nav = fund_nav_pre * equity_target
            rebalance_amount_crypto = target_crypto_nav - crypto_nav
            rebalance_amount_equity = target_equity_nav - equity_nav
            rebalance_rows.append(
                {
                    "timestamp": ts,
                    "fund_nav_pre_rebalance": fund_nav_pre,
                    "crypto_weight_pre_rebalance": crypto_weight_pre,
                    "equity_weight_pre_rebalance": equity_weight_pre,
                    "crypto_drift_pre_rebalance": crypto_drift,
                    "equity_drift_pre_rebalance": equity_drift,
                    "rebalance_amount_crypto": rebalance_amount_crypto,
                    "rebalance_amount_equity": rebalance_amount_equity,
                    "crypto_target_weight": crypto_target,
                    "equity_target_weight": equity_target,
                }
            )
            crypto_nav = target_crypto_nav
            equity_nav = target_equity_nav

        fund_nav = crypto_nav + equity_nav
        high_water = max(high_water, fund_nav)
        drawdown = fund_nav / high_water - 1.0 if high_water > 0 else 0.0
        crypto_weight = crypto_nav / fund_nav if fund_nav else 0.0
        equity_weight = equity_nav / fund_nav if fund_nav else 0.0
        rows.append(
            {
                "timestamp": ts,
                "fund_nav": fund_nav,
                "fund_return": 0.0,  # filled after frame construction
                "fund_drawdown": drawdown,
                "crypto_nav": crypto_nav,
                "equity_nav": equity_nav,
                "crypto_target_weight": crypto_target,
                "equity_target_weight": equity_target,
                "crypto_actual_weight": crypto_weight,
                "equity_actual_weight": equity_weight,
                "crypto_drift": crypto_weight - crypto_target,
                "equity_drift": equity_weight - equity_target,
                "max_abs_drift_pre_rebalance": max_abs_drift,
                "rebalance_needed": rebalance_needed,
                "rebalance_executed": rebalance_executed,
                "rebalance_amount_crypto": rebalance_amount_crypto,
                "rebalance_amount_equity": rebalance_amount_equity,
                "crypto_return_input": float(crypto_rets.loc[ts]),
                "equity_return_input": float(equity_rets.loc[ts]),
            }
        )

    ledger = pd.DataFrame(rows).set_index("timestamp")
    ledger["fund_return"] = ledger["fund_nav"].pct_change(fill_method=None).fillna(0.0)
    rebalances = pd.DataFrame(rebalance_rows)
    return ledger, rebalances


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if max_rows is not None:
        df = df.head(max_rows)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in df.columns:
            value = row[c]
            if isinstance(value, float):
                vals.append(f"{value:.4f}")
            else:
                vals.append(str(value).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _write_summary_md(path: Path, args: argparse.Namespace, perf: pd.DataFrame, drawdown_summary: pd.DataFrame, ledger: pd.DataFrame, rebalances: pd.DataFrame) -> None:
    final = ledger.iloc[-1]
    lines = [
        "# Fund Paper Readiness v1",
        "",
        "Research-only static sleeve ledger for Itera's promoted two-sleeve fund view.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Curves: {args.curves}",
        f"Crypto column: {args.crypto_column}",
        f"Equity column: {args.equity_column}",
        f"Target weights: {args.target_weights}",
        f"Initial capital: {args.capital}",
        f"Rebalance threshold: {args.rebalance_threshold}",
        "```",
        "",
        "## Final Ledger State",
        "",
        "```text",
        f"Final fund NAV:        {float(final['fund_nav']):,.2f}",
        f"Final crypto NAV:      {float(final['crypto_nav']):,.2f}",
        f"Final equity NAV:      {float(final['equity_nav']):,.2f}",
        f"Final crypto weight:   {float(final['crypto_actual_weight']) * 100.0:.2f}%",
        f"Final equity weight:   {float(final['equity_actual_weight']) * 100.0:.2f}%",
        f"Final drawdown:        {float(final['fund_drawdown']) * 100.0:.2f}%",
        f"Rebalance events:      {len(rebalances)}",
        "```",
        "",
        "## Performance Summary",
        "",
        _md_table(perf, max_rows=40),
        "",
        "## Drawdown / Rebalance Summary",
        "",
        _md_table(drawdown_summary, max_rows=40),
        "",
        "## Recent Rebalance Events",
        "",
        _md_table(rebalances.tail(10), max_rows=10),
        "",
        "## Guardrail",
        "",
        "```text",
        "Research-only ledger simulation. No broker orders, live trading, paper-broker execution, dashboard integration, or dynamic allocator decisions are approved.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.capital <= 0:
        raise ValueError("capital must be positive")
    if not 0.0 <= args.rebalance_threshold <= 1.0:
        raise ValueError("rebalance-threshold must be between 0 and 1")

    crypto_target, equity_target = _parse_weights(args.target_weights)
    curves = _read_curves(Path(args.curves))
    for col in [args.crypto_column, args.equity_column]:
        if col not in curves.columns:
            raise ValueError(f"Missing required column '{col}' in {args.curves}. Columns={list(curves.columns)}")

    # Normalize each source curve to 1.0 before computing returns. The ledger
    # itself owns capital allocation and accounting.
    crypto_curve = _normalize_curve(curves[args.crypto_column], 1.0).rename("crypto")
    equity_curve = _normalize_curve(curves[args.equity_column], 1.0).rename("equity")
    ledger, rebalances = _simulate_ledger(
        crypto_curve=crypto_curve,
        equity_curve=equity_curve,
        capital=args.capital,
        crypto_target=crypto_target,
        equity_target=equity_target,
        rebalance_threshold=args.rebalance_threshold,
    )

    sleeve_nav = ledger[["crypto_nav", "equity_nav", "fund_nav"]].copy()
    sleeve_weights = ledger[["crypto_actual_weight", "equity_actual_weight", "crypto_drift", "equity_drift", "rebalance_needed", "rebalance_executed"]].copy()
    target_allocations = ledger[["crypto_target_weight", "equity_target_weight"]].copy()

    perf_rows = []
    perf_rows.append({"series": "FUND_PAPER_LEDGER", "start": str(ledger.index[0]), "end": str(ledger.index[-1]), "bars": len(ledger), **_perf(ledger["fund_nav"])})
    perf_rows.append({"series": "CRYPTO_SLEEVE_LEDGER", "start": str(ledger.index[0]), "end": str(ledger.index[-1]), "bars": len(ledger), **_perf(ledger["crypto_nav"])})
    perf_rows.append({"series": "EQUITY_SLEEVE_LEDGER", "start": str(ledger.index[0]), "end": str(ledger.index[-1]), "bars": len(ledger), **_perf(ledger["equity_nav"])})
    perf = pd.DataFrame(perf_rows)

    drawdown_rows = []
    for win, start, end in WINDOWS:
        sub = _slice(ledger["fund_nav"], start, end)
        if len(sub) < 20:
            continue
        drawdown_rows.append({"window": win, "start": str(sub.index[0]), "end": str(sub.index[-1]), "bars": len(sub), **_perf(sub)})
    drawdown_summary = pd.DataFrame(drawdown_rows)

    ledger.to_csv(out_dir / "fund_ledger.csv")
    sleeve_nav.to_csv(out_dir / "sleeve_nav.csv")
    sleeve_weights.to_csv(out_dir / "sleeve_weights.csv")
    target_allocations.to_csv(out_dir / "target_allocations.csv")
    rebalances.to_csv(out_dir / "rebalance_events.csv", index=False)
    perf.to_csv(out_dir / "performance_summary.csv", index=False)
    drawdown_summary.to_csv(out_dir / "drawdown_summary.csv", index=False)

    summary = {
        "research_status": "research_only_fund_paper_readiness_v1_static_sleeve_ledger",
        "inputs": {
            "curves": args.curves,
            "crypto_column": args.crypto_column,
            "equity_column": args.equity_column,
            "target_weights": args.target_weights,
            "capital": args.capital,
            "rebalance_threshold": args.rebalance_threshold,
        },
        "final_state": {
            "fund_nav": float(ledger["fund_nav"].iloc[-1]),
            "crypto_nav": float(ledger["crypto_nav"].iloc[-1]),
            "equity_nav": float(ledger["equity_nav"].iloc[-1]),
            "crypto_actual_weight": float(ledger["crypto_actual_weight"].iloc[-1]),
            "equity_actual_weight": float(ledger["equity_actual_weight"].iloc[-1]),
            "fund_drawdown": float(ledger["fund_drawdown"].iloc[-1]),
            "rebalance_events": int(len(rebalances)),
        },
        "artifacts": {
            "fund_ledger": str(out_dir / "fund_ledger.csv"),
            "sleeve_nav": str(out_dir / "sleeve_nav.csv"),
            "sleeve_weights": str(out_dir / "sleeve_weights.csv"),
            "target_allocations": str(out_dir / "target_allocations.csv"),
            "rebalance_events": str(out_dir / "rebalance_events.csv"),
            "performance_summary": str(out_dir / "performance_summary.csv"),
            "drawdown_summary": str(out_dir / "drawdown_summary.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {"status": "ledger_readiness_only", "not_approved": ["live_trading", "broker_integration", "paper_broker_execution", "dashboard_integration", "dynamic_allocator"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", args, perf, drawdown_summary, ledger, rebalances)

    with pd.option_context("display.max_columns", None, "display.width", 360, "display.float_format", "{:.4f}".format):
        print("\n=== FUND PAPER READINESS V1 — STATIC SLEEVE LEDGER ===")
        print(f"Curves: {args.curves}")
        print(f"Target weights: crypto={crypto_target:.2%}, equity={equity_target:.2%}")
        print(f"Rebalance threshold: {args.rebalance_threshold:.2%}")
        print("\nPerformance Summary:")
        print(perf.to_string(index=False))
        print("\nDrawdown Summary:")
        print(drawdown_summary.to_string(index=False) if not drawdown_summary.empty else "No drawdown rows.")
        print("\nFinal Ledger State:")
        print(ledger.tail(1).reset_index().to_string(index=False))
        print(f"\nRebalance events: {len(rebalances)}")
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
