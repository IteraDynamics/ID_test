#!/usr/bin/env python
"""Equity Book v1 — SMA parameter stability and walk-forward audit.

Research-only script. Tests whether the SPY/QQQ 50/50 SMA-to-cash finalist is
stable across nearby SMA windows and walk-forward train/test folds.

This script is intentionally standalone for Equity Book v1. It does not use or
modify crypto runtime, broker, paper-trading, execution, governors, dashboards,
live state, or global allocator logic.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_OUT = "artifacts/equity_book_v1_parameter_stability"
DEFAULT_WINDOWS = "100,125,150,175,200,225,250"
DEFAULT_STATIC_WINDOWS = "150,200"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0


@dataclass(frozen=True)
class Fold:
    fold_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    def to_dict(self) -> dict[str, object]:
        return {
            "fold_id": self.fold_id,
            "train_start": str(self.train_start.date()),
            "train_end": str(self.train_end.date()),
            "test_start": str(self.test_start.date()),
            "test_end": str(self.test_end.date()),
        }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Audit Equity Book v1 SMA parameter stability with walk-forward folds",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--ma-windows", default=DEFAULT_WINDOWS, help="Comma-separated SMA windows to evaluate.")
    p.add_argument("--static-windows", default=DEFAULT_STATIC_WINDOWS, help="Comma-separated static SMA windows to compare in each OOS fold.")
    p.add_argument("--mode", choices=["rolling", "expanding"], default="rolling", help="Fold construction mode.")
    p.add_argument("--train-years", type=int, default=8, help="Rolling train length, or minimum train years for expanding mode.")
    p.add_argument("--test-years", type=int, default=1, help="Test fold length in calendar years.")
    p.add_argument("--step-years", type=int, default=1, help="Years to advance between folds.")
    p.add_argument("--selection-metric", choices=["calmar", "sharpe", "sortino", "cagr"], default="calmar")
    p.add_argument("--target-return", type=float, default=0.0, help="Per-bar target return for Sortino.")
    return p.parse_args()


def _parse_ints(raw: str, label: str) -> list[int]:
    out: list[int] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        value = int(part)
        if value <= 1:
            raise ValueError(f"{label} values must be > 1; got {value}")
        out.append(value)
    if not out:
        raise ValueError(f"No {label} values supplied")
    return sorted(set(out))


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_price_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label} data file: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty {label} data file: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    df.columns = [str(c).strip().lower() for c in df.columns]
    required = {"open", "high", "low", "close"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{label} data missing required columns {missing}; got {list(df.columns)}")
    df = df.dropna(subset=["close"])
    if df.empty:
        raise ValueError(f"No valid {label} close rows in {path}")
    return df


def _common_prices(spy_df: pd.DataFrame, qqq_df: pd.DataFrame) -> pd.DataFrame:
    spy = pd.to_numeric(spy_df["close"], errors="coerce").dropna().rename("SPY")
    qqq = pd.to_numeric(qqq_df["close"], errors="coerce").dropna().rename("QQQ")
    prices = pd.concat([spy, qqq], axis=1).dropna().sort_index()
    if len(prices) < 252 * 3:
        raise ValueError(f"Insufficient common SPY/QQQ history: {len(prices)} rows")
    return prices


def _build_folds(index: pd.DatetimeIndex, mode: str, train_years: int, test_years: int, step_years: int) -> list[Fold]:
    if train_years < 1 or test_years < 1 or step_years < 1:
        raise ValueError("train-years, test-years, and step-years must be positive")
    data_start = pd.Timestamp(index.min()).normalize()
    data_end = pd.Timestamp(index.max()).normalize()
    folds: list[Fold] = []

    train_anchor = data_start
    test_start = data_start + pd.DateOffset(years=train_years)
    fold_id = 1
    while test_start <= data_end:
        test_end = test_start + pd.DateOffset(years=test_years) - pd.Timedelta(days=1)
        if test_end > data_end:
            test_end = data_end
        if mode == "expanding":
            train_start = train_anchor
        else:
            train_start = test_start - pd.DateOffset(years=train_years)
        train_end = test_start - pd.Timedelta(days=1)
        if train_end <= train_start or test_end <= test_start:
            break
        train_rows = index[(index >= train_start) & (index <= train_end)]
        test_rows = index[(index >= test_start) & (index <= test_end)]
        if len(train_rows) >= 252 and len(test_rows) >= 60:
            folds.append(Fold(fold_id, train_start, train_end, test_start, test_end))
            fold_id += 1
        test_start = test_start + pd.DateOffset(years=step_years)
    if not folds:
        raise ValueError("No valid walk-forward folds constructed")
    return folds


def _weights_for_sma_cash(prices: pd.DataFrame, ma_window: int) -> pd.DataFrame:
    spy_above = (prices["SPY"] > prices["SPY"].rolling(ma_window, min_periods=ma_window).mean()).astype(float)
    qqq_above = (prices["QQQ"] > prices["QQQ"].rolling(ma_window, min_periods=ma_window).mean()).astype(float)
    return pd.DataFrame({"SPY": 0.5 * spy_above, "QQQ": 0.5 * qqq_above}, index=prices.index)


def _weights_for_passive_5050(prices: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"SPY": 0.5, "QQQ": 0.5}, index=prices.index)


def _shift_for_closed_bar_execution(weights: pd.DataFrame) -> pd.DataFrame:
    return weights.shift(1).fillna(0.0)


def _equity_from_weights(prices: pd.DataFrame, desired_weights: pd.DataFrame, capital: float) -> pd.Series:
    weights = _shift_for_closed_bar_execution(desired_weights.reindex(prices.index).fillna(0.0))
    returns = prices.pct_change().fillna(0.0)
    portfolio_returns = (weights * returns).sum(axis=1)
    return float(capital) * (1.0 + portfolio_returns).cumprod()


def _normalise(s: pd.Series) -> pd.Series:
    s = s.dropna().astype(float)
    if len(s) < 2 or float(s.iloc[0]) <= 0:
        return pd.Series(dtype=float)
    return s / float(s.iloc[0])


def _window_slice(s: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    inclusive_end = end + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    return s.loc[(s.index >= start) & (s.index <= inclusive_end)].dropna()


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


def _sortino(eq: pd.Series, target_return: float = 0.0) -> float:
    rets = eq.dropna().astype(float).pct_change().dropna()
    if rets.empty:
        return 0.0
    excess = rets - float(target_return)
    downside = np.minimum(excess, 0.0)
    downside_dev = float(np.sqrt(np.mean(np.square(downside))))
    if downside_dev <= 1e-12:
        return 0.0
    return float((excess.mean() / downside_dev) * math.sqrt(_bars_per_year(eq.index)))


def _perf(eq: pd.Series, target_return: float = 0.0) -> dict[str, float]:
    eq = _normalise(eq)
    if len(eq) < 2:
        return {}
    rets = eq.pct_change().dropna()
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
    return {
        "total_return_pct": total * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "sortino": _sortino(eq, target_return),
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
        "max_time_underwater_days": _max_time_underwater_days(eq),
    }


def _selection_value(metrics: dict[str, float], metric: str) -> float:
    if metric == "calmar":
        return float(metrics.get("calmar", -np.inf))
    if metric == "sharpe":
        return float(metrics.get("sharpe", -np.inf))
    if metric == "sortino":
        return float(metrics.get("sortino", -np.inf))
    if metric == "cagr":
        return float(metrics.get("cagr_pct", -np.inf))
    raise ValueError(f"Unsupported selection metric: {metric}")


def _evaluate_grid(
    prices: pd.DataFrame,
    ma_windows: list[int],
    static_windows: list[int],
    folds: list[Fold],
    capital: float,
    selection_metric: str,
    target_return: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    all_windows = sorted(set(ma_windows + static_windows))
    curves: dict[str, pd.Series] = {}
    for ma in all_windows:
        curves[f"SPY_QQQ_50_50_SMA{ma}_CASH"] = _equity_from_weights(prices, _weights_for_sma_cash(prices, ma), capital)
    curves["SPY_QQQ_50_50_DAILY_REBAL"] = _equity_from_weights(prices, _weights_for_passive_5050(prices), capital)

    grid_rows = []
    selected_rows = []
    oos_rows = []

    for fold in folds:
        train_metrics_by_ma: dict[int, dict[str, float]] = {}
        test_metrics_by_ma: dict[int, dict[str, float]] = {}
        for ma in ma_windows:
            name = f"SPY_QQQ_50_50_SMA{ma}_CASH"
            train_eq = _window_slice(curves[name], fold.train_start, fold.train_end)
            test_eq = _window_slice(curves[name], fold.test_start, fold.test_end)
            train_metrics = _perf(train_eq, target_return)
            test_metrics = _perf(test_eq, target_return)
            train_metrics_by_ma[ma] = train_metrics
            test_metrics_by_ma[ma] = test_metrics
            grid_rows.append(
                {
                    **fold.to_dict(),
                    "ma_window": ma,
                    "series": name,
                    "selection_metric": selection_metric,
                    "train_selection_value": _selection_value(train_metrics, selection_metric),
                    **{f"train_{k}": v for k, v in train_metrics.items()},
                    **{f"test_{k}": v for k, v in test_metrics.items()},
                }
            )

        selected_ma = max(
            ma_windows,
            key=lambda ma: (
                _selection_value(train_metrics_by_ma[ma], selection_metric),
                train_metrics_by_ma[ma].get("sharpe", -np.inf),
                train_metrics_by_ma[ma].get("cagr_pct", -np.inf),
            ),
        )
        selected_name = f"SPY_QQQ_50_50_SMA{selected_ma}_CASH"
        selected_test_metrics = test_metrics_by_ma[selected_ma]
        passive_test_metrics = _perf(_window_slice(curves["SPY_QQQ_50_50_DAILY_REBAL"], fold.test_start, fold.test_end), target_return)
        selected_rows.append(
            {
                **fold.to_dict(),
                "selected_ma_window": selected_ma,
                "selected_series": selected_name,
                "selection_metric": selection_metric,
                "train_selection_value": _selection_value(train_metrics_by_ma[selected_ma], selection_metric),
                **{f"selected_train_{k}": v for k, v in train_metrics_by_ma[selected_ma].items()},
                **{f"selected_test_{k}": v for k, v in selected_test_metrics.items()},
                **{f"passive_5050_test_{k}": v for k, v in passive_test_metrics.items()},
                "delta_test_cagr_pct_vs_passive_5050": selected_test_metrics.get("cagr_pct", 0.0) - passive_test_metrics.get("cagr_pct", 0.0),
                "delta_test_max_drawdown_pct_vs_passive_5050": selected_test_metrics.get("max_drawdown_pct", 0.0) - passive_test_metrics.get("max_drawdown_pct", 0.0),
                "delta_test_sharpe_vs_passive_5050": selected_test_metrics.get("sharpe", 0.0) - passive_test_metrics.get("sharpe", 0.0),
                "delta_test_calmar_vs_passive_5050": selected_test_metrics.get("calmar", 0.0) - passive_test_metrics.get("calmar", 0.0),
            }
        )

        compare_names = [selected_name, "SPY_QQQ_50_50_DAILY_REBAL"] + [f"SPY_QQQ_50_50_SMA{ma}_CASH" for ma in static_windows]
        for name in list(dict.fromkeys(compare_names)):
            test_metrics = _perf(_window_slice(curves[name], fold.test_start, fold.test_end), target_return)
            oos_rows.append({**fold.to_dict(), "series": name, **test_metrics})

    full_rows = []
    for name, curve in curves.items():
        full_rows.append({"series": name, **_perf(curve, target_return)})
    full_summary = pd.DataFrame(full_rows).sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])
    return pd.DataFrame(grid_rows), pd.DataFrame(selected_rows), pd.DataFrame(oos_rows), full_summary


def _aggregate(selected: pd.DataFrame, oos: pd.DataFrame, static_windows: list[int]) -> pd.DataFrame:
    rows = []
    if not selected.empty:
        rows.append(
            {
                "series": "WALK_FORWARD_SELECTED",
                "folds": int(len(selected)),
                "median_oos_cagr_pct": float(selected["selected_test_cagr_pct"].median()),
                "median_oos_max_drawdown_pct": float(selected["selected_test_max_drawdown_pct"].median()),
                "median_oos_sharpe": float(selected["selected_test_sharpe"].median()),
                "median_oos_calmar": float(selected["selected_test_calmar"].median()),
                "pct_folds_positive_oos_return": float((selected["selected_test_total_return_pct"] > 0).mean() * 100.0),
                "pct_folds_better_dd_than_passive_5050": float((selected["delta_test_max_drawdown_pct_vs_passive_5050"] > 0).mean() * 100.0),
                "pct_folds_better_calmar_than_passive_5050": float((selected["delta_test_calmar_vs_passive_5050"] > 0).mean() * 100.0),
            }
        )
    for name, grp in oos.groupby("series"):
        if name == "SPY_QQQ_50_50_DAILY_REBAL" or any(name == f"SPY_QQQ_50_50_SMA{ma}_CASH" for ma in static_windows):
            rows.append(
                {
                    "series": name,
                    "folds": int(len(grp)),
                    "median_oos_cagr_pct": float(grp["cagr_pct"].median()),
                    "median_oos_max_drawdown_pct": float(grp["max_drawdown_pct"].median()),
                    "median_oos_sharpe": float(grp["sharpe"].median()),
                    "median_oos_calmar": float(grp["calmar"].median()),
                    "pct_folds_positive_oos_return": float((grp["total_return_pct"] > 0).mean() * 100.0),
                    "pct_folds_better_dd_than_passive_5050": np.nan,
                    "pct_folds_better_calmar_than_passive_5050": np.nan,
                }
            )
    return pd.DataFrame(rows)


def _fmt(v: object, floatfmt: str = ".4f") -> str:
    if isinstance(v, float):
        return format(v, floatfmt)
    if pd.isna(v):
        return ""
    return str(v).replace("|", "\\|").replace("\n", " ")


def _md_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if cols is not None:
        df = df[[c for c in cols if c in df.columns]]
    if max_rows is not None:
        df = df.head(max_rows)
    columns = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt(row[c]) for c in df.columns) + " |")
    return "\n".join(lines)


def _write_summary_md(
    path: Path,
    selected: pd.DataFrame,
    aggregate: pd.DataFrame,
    full_summary: pd.DataFrame,
    ma_counts: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    selected_cols = [
        "fold_id", "train_start", "train_end", "test_start", "test_end", "selected_ma_window",
        "selected_test_total_return_pct", "selected_test_cagr_pct", "selected_test_max_drawdown_pct",
        "selected_test_sharpe", "selected_test_calmar", "delta_test_cagr_pct_vs_passive_5050",
        "delta_test_max_drawdown_pct_vs_passive_5050", "delta_test_calmar_vs_passive_5050",
    ]
    agg_cols = [
        "series", "folds", "median_oos_cagr_pct", "median_oos_max_drawdown_pct", "median_oos_sharpe",
        "median_oos_calmar", "pct_folds_positive_oos_return", "pct_folds_better_dd_than_passive_5050",
        "pct_folds_better_calmar_than_passive_5050",
    ]
    full_cols = ["series", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct"]
    lines = [
        "# Equity Book v1 — SMA Parameter Stability / Walk-Forward Audit",
        "",
        "Research-only audit of whether the SPY/QQQ 50/50 SMA-to-cash finalist is stable across nearby SMA windows and out-of-sample folds.",
        "",
        "## Inputs",
        "",
        "```text",
        f"SPY data: {args.spy_data}",
        f"QQQ data: {args.qqq_data}",
        f"MA windows: {args.ma_windows}",
        f"Static windows: {args.static_windows}",
        f"Mode: {args.mode}",
        f"Train years: {args.train_years}",
        f"Test years: {args.test_years}",
        f"Step years: {args.step_years}",
        f"Selection metric: {args.selection_metric}",
        "Risk-off: cash only",
        "```",
        "",
        "## Selected Window Counts",
        "",
        _md_table(ma_counts),
        "",
        "## Walk-Forward Selected OOS Results",
        "",
        _md_table(selected, selected_cols, max_rows=80),
        "",
        "## Aggregate OOS Summary",
        "",
        _md_table(aggregate, agg_cols),
        "",
        "## Full-Period Static Window Summary",
        "",
        _md_table(full_summary, full_cols, max_rows=20),
        "",
        "## Guardrail",
        "",
        "```text",
        "This audit is diagnostic only.",
        "It does not approve paper trading, live allocation, broker changes, crypto allocator changes, or defensive carry overlays.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    ma_windows = _parse_ints(args.ma_windows, "MA window")
    static_windows = _parse_ints(args.static_windows, "static window")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spy_df = _read_price_csv(Path(args.spy_data), "SPY")
    qqq_df = _read_price_csv(Path(args.qqq_data), "QQQ")
    prices = _common_prices(spy_df, qqq_df)
    folds = _build_folds(prices.index, args.mode, args.train_years, args.test_years, args.step_years)

    grid, selected, oos, full_summary = _evaluate_grid(
        prices=prices,
        ma_windows=ma_windows,
        static_windows=static_windows,
        folds=folds,
        capital=args.capital,
        selection_metric=args.selection_metric,
        target_return=args.target_return,
    )
    aggregate = _aggregate(selected, oos, static_windows)
    ma_counts = selected["selected_ma_window"].value_counts().sort_index().rename_axis("selected_ma_window").reset_index(name="fold_count")
    ma_counts["fold_pct"] = ma_counts["fold_count"] / float(len(selected)) * 100.0

    grid.to_csv(out_dir / "parameter_grid_by_fold.csv", index=False)
    selected.to_csv(out_dir / "walk_forward_selected_folds.csv", index=False)
    oos.to_csv(out_dir / "walk_forward_oos_comparison.csv", index=False)
    aggregate.to_csv(out_dir / "walk_forward_aggregate_summary.csv", index=False)
    ma_counts.to_csv(out_dir / "selected_ma_counts.csv", index=False)
    full_summary.to_csv(out_dir / "full_period_static_summary.csv", index=False)

    payload = {
        "research_status": "research_only_equity_book_v1_parameter_stability",
        "inputs": {
            "spy_data": args.spy_data,
            "qqq_data": args.qqq_data,
            "capital": args.capital,
            "ma_windows": ma_windows,
            "static_windows": static_windows,
            "mode": args.mode,
            "train_years": args.train_years,
            "test_years": args.test_years,
            "step_years": args.step_years,
            "selection_metric": args.selection_metric,
            "target_return": args.target_return,
        },
        "folds": [fold.to_dict() for fold in folds],
        "artifacts": {
            "parameter_grid_by_fold": str(out_dir / "parameter_grid_by_fold.csv"),
            "walk_forward_selected_folds": str(out_dir / "walk_forward_selected_folds.csv"),
            "walk_forward_oos_comparison": str(out_dir / "walk_forward_oos_comparison.csv"),
            "walk_forward_aggregate_summary": str(out_dir / "walk_forward_aggregate_summary.csv"),
            "selected_ma_counts": str(out_dir / "selected_ma_counts.csv"),
            "full_period_static_summary": str(out_dir / "full_period_static_summary.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {
            "status": "diagnostic_only",
            "not_approved": [
                "runtime_change",
                "paper_trading_change",
                "live_allocation_change",
                "broker_change",
                "crypto_allocator_change",
                "defensive_carry_overlay",
            ],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", selected, aggregate, full_summary, ma_counts, args)

    selected_cols = [
        "fold_id", "train_start", "train_end", "test_start", "test_end", "selected_ma_window",
        "selected_test_total_return_pct", "selected_test_cagr_pct", "selected_test_max_drawdown_pct",
        "selected_test_sharpe", "selected_test_calmar", "delta_test_cagr_pct_vs_passive_5050",
        "delta_test_max_drawdown_pct_vs_passive_5050", "delta_test_calmar_vs_passive_5050",
    ]
    agg_cols = [
        "series", "folds", "median_oos_cagr_pct", "median_oos_max_drawdown_pct", "median_oos_sharpe",
        "median_oos_calmar", "pct_folds_positive_oos_return", "pct_folds_better_dd_than_passive_5050",
        "pct_folds_better_calmar_than_passive_5050",
    ]
    full_cols = ["series", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct"]

    with pd.option_context("display.max_columns", None, "display.width", 320, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY BOOK V1 — SMA PARAMETER STABILITY / WALK-FORWARD AUDIT ===")
        print(f"Common overlap: {prices.index[0]} → {prices.index[-1]} ({len(prices)} bars)")
        print(f"Folds: {len(folds)} | Mode: {args.mode} | Train years: {args.train_years} | Test years: {args.test_years}")
        print("\nSelected MA Counts:")
        print(ma_counts.to_string(index=False))
        print("\nWalk-Forward Selected OOS Results:")
        print(selected[[c for c in selected_cols if c in selected.columns]].to_string(index=False))
        print("\nAggregate OOS Summary:")
        print(aggregate[[c for c in agg_cols if c in aggregate.columns]].to_string(index=False))
        print("\nFull-Period Static Window Summary:")
        print(full_summary[[c for c in full_cols if c in full_summary.columns]].to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
