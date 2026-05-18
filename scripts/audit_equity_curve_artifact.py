#!/usr/bin/env python
"""Audit an equity-curve artifact before using it in regime attribution.

Research-only utility. Prints timestamp/frequency, column, return, drawdown,
volatility, and discontinuity diagnostics so downstream attribution scripts do
not accidentally target the wrong artifact or mix incompatible frequencies.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd


DOC_BASELINES = {
    "crypto_v1_doc": {
        "total_return_pct": 215.14,
        "cagr_pct": 18.34,
        "max_drawdown_pct": -17.72,
        "sharpe": 1.166,
        "calmar": 1.035,
        "ann_vol_pct": 15.49,
        "source": "docs/iterafund_v0_research_baseline.md",
    }
}


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing equity-curve artifact: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty equity-curve artifact: {path}")

    ts_col = df.columns[0]
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=[ts_col]).set_index(ts_col).sort_index()
    df.index.name = "timestamp"
    if df.empty:
        raise ValueError(f"No valid timestamps in equity-curve artifact: {path}")
    return df


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return 252.0
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    median_seconds = float(deltas.median())
    if median_seconds <= 0:
        return 252.0
    return float((365.25 * 24.0 * 3600.0) / median_seconds)


def _freq_label(index: pd.DatetimeIndex) -> str:
    if len(index) < 3:
        return "unknown"
    median_seconds = float(index.to_series().diff().dropna().dt.total_seconds().median())
    if abs(median_seconds - 3600.0) < 1:
        return "1H"
    if abs(median_seconds - 4 * 3600.0) < 1:
        return "4H"
    if abs(median_seconds - 86400.0) < 1:
        return "1D"
    return f"{median_seconds:.0f}s"


def _max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    return float((equity / running_max - 1.0).min())


def _metrics(series: pd.Series) -> dict[str, float | int]:
    equity = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if len(equity) < 2:
        return {}

    returns = equity.pct_change().replace([math.inf, -math.inf], pd.NA).dropna().astype(float)
    years = max((equity.index[-1] - equity.index[0]).total_seconds() / (365.25 * 24.0 * 3600.0), 1e-9)
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0) if equity.iloc[0] > 0 and equity.iloc[-1] > 0 else -1.0
    bpy = _bars_per_year(equity.index)
    vol = float(returns.std(ddof=0) * math.sqrt(bpy)) if len(returns) > 1 else 0.0
    sharpe = float((returns.mean() / returns.std(ddof=0)) * math.sqrt(bpy)) if returns.std(ddof=0) > 0 else 0.0
    max_dd = _max_drawdown(equity)
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0

    return {
        "bars": int(len(equity)),
        "start_value": float(equity.iloc[0]),
        "end_value": float(equity.iloc[-1]),
        "total_return_pct": total_return * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "calmar": calmar,
        "ann_vol_pct": vol * 100.0,
        "zero_return_pct": float((returns == 0.0).mean() * 100.0) if len(returns) else 0.0,
        "min_return_pct": float(returns.min() * 100.0) if len(returns) else 0.0,
        "max_return_pct": float(returns.max() * 100.0) if len(returns) else 0.0,
        "return_count": int(len(returns)),
    }


def _compare_to_baseline(metrics: dict[str, float | int], baseline: dict[str, float]) -> dict[str, float]:
    fields = ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct"]
    return {
        f"delta_{field}": float(metrics.get(field, 0.0)) - float(baseline[field])
        for field in fields
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--equity-curves", required=True)
    parser.add_argument("--target-column", default=None)
    parser.add_argument("--compare-doc-baseline", choices=list(DOC_BASELINES), default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    path = Path(args.equity_curves)
    df = _load(path)
    numeric_cols = []
    for col in df.columns:
        s = pd.to_numeric(df[col], errors="coerce")
        if s.notna().sum() > 1:
            numeric_cols.append(str(col))

    if args.target_column:
        if args.target_column not in df.columns:
            raise ValueError(f"Target column {args.target_column!r} not found. Available columns: {list(df.columns)}")
        columns = [args.target_column]
    else:
        columns = numeric_cols

    audit = {
        "path": str(path),
        "rows": int(len(df)),
        "start": str(df.index.min()),
        "end": str(df.index.max()),
        "frequency_label": _freq_label(df.index),
        "bars_per_year_inferred": _bars_per_year(df.index),
        "columns": list(df.columns),
        "numeric_columns": numeric_cols,
        "target_columns": columns,
        "metrics": {},
    }

    for col in columns:
        m = _metrics(df[col])
        if args.compare_doc_baseline:
            baseline = DOC_BASELINES[args.compare_doc_baseline]
            m["doc_baseline"] = baseline
            m["doc_baseline_delta"] = _compare_to_baseline(m, baseline)
        audit["metrics"][col] = m

    print("\n=== EQUITY CURVE ARTIFACT AUDIT ===")
    print(f"Path: {path}")
    print(f"Rows: {audit['rows']}")
    print(f"Period: {audit['start']} → {audit['end']}")
    print(f"Frequency: {audit['frequency_label']}  |  inferred bars/year: {audit['bars_per_year_inferred']:.2f}")
    print(f"Columns: {', '.join(audit['columns'])}")

    for col, m in audit["metrics"].items():
        print(f"\nColumn: {col}")
        print(f"  Bars:          {m.get('bars', 0)}")
        print(f"  Start value:   {m.get('start_value', 0.0):,.6f}")
        print(f"  End value:     {m.get('end_value', 0.0):,.6f}")
        print(f"  Total Return:  {m.get('total_return_pct', 0.0):,.2f}%")
        print(f"  CAGR:          {m.get('cagr_pct', 0.0):,.2f}%")
        print(f"  MaxDD:         {m.get('max_drawdown_pct', 0.0):,.2f}%")
        print(f"  Sharpe:        {m.get('sharpe', 0.0):,.3f}")
        print(f"  Calmar:        {m.get('calmar', 0.0):,.3f}")
        print(f"  Ann Vol:       {m.get('ann_vol_pct', 0.0):,.2f}%")
        print(f"  Zero returns:  {m.get('zero_return_pct', 0.0):,.2f}%")
        print(f"  Min return:    {m.get('min_return_pct', 0.0):,.2f}%")
        print(f"  Max return:    {m.get('max_return_pct', 0.0):,.2f}%")
        if args.compare_doc_baseline:
            delta = m["doc_baseline_delta"]
            print("  Delta vs doc baseline:")
            for k, v in delta.items():
                print(f"    {k}: {v:,.4f}")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
        print(f"\nAudit JSON saved to: {out_path}")


if __name__ == "__main__":
    main()
