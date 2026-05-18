#!/usr/bin/env python
"""Equity Book v1 — fresh daily SPY/QQQ baseline research.

Research-only script. Builds transparent SPY/QQQ daily baseline strategies and
benchmarks them against passive SPY, passive QQQ, and a daily rebalanced
SPY/QQQ 50/50 book.

No runtime, broker, paper-trading, allocator, live-state, or crypto files are
read or modified. Risk-off is cash only; defensive carry overlays are out of
scope for this baseline pass.
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


DEFAULT_OUT = "artifacts/equity_book_v1_baselines"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0


@dataclass(frozen=True)
class StrategySpec:
    name: str
    description: str
    weights: pd.DataFrame
    params: dict[str, object]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run Equity Book v1 daily SPY/QQQ baseline strategies",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument(
        "--ma-windows",
        default="100,150,200,250",
        help="Comma-separated moving-average windows for trend baselines.",
    )
    p.add_argument(
        "--lookbacks",
        default="63,126,252",
        help="Comma-separated momentum lookbacks for rotation baselines.",
    )
    p.add_argument(
        "--target-return",
        type=float,
        default=0.0,
        help="Per-bar target return for Sortino.",
    )
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


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _common_prices(spy_df: pd.DataFrame, qqq_df: pd.DataFrame) -> pd.DataFrame:
    spy = pd.to_numeric(spy_df["close"], errors="coerce").dropna().rename("SPY")
    qqq = pd.to_numeric(qqq_df["close"], errors="coerce").dropna().rename("QQQ")
    prices = pd.concat([spy, qqq], axis=1).dropna().sort_index()
    if len(prices) < 252:
        raise ValueError(f"Insufficient common SPY/QQQ history: {len(prices)} rows")
    return prices


def _as_weight_frame(index: pd.DatetimeIndex, spy: pd.Series | float, qqq: pd.Series | float) -> pd.DataFrame:
    if isinstance(spy, pd.Series):
        spy_w = spy.reindex(index).fillna(0.0).astype(float)
    else:
        spy_w = pd.Series(float(spy), index=index)
    if isinstance(qqq, pd.Series):
        qqq_w = qqq.reindex(index).fillna(0.0).astype(float)
    else:
        qqq_w = pd.Series(float(qqq), index=index)
    w = pd.DataFrame({"SPY": spy_w, "QQQ": qqq_w}, index=index)
    # Cash is implicit. Keep long-only, no leverage for this first baseline pass.
    w = w.clip(lower=0.0, upper=1.0)
    gross = w.sum(axis=1)
    too_high = gross > 1.0
    if too_high.any():
        w.loc[too_high, ["SPY", "QQQ"]] = w.loc[too_high, ["SPY", "QQQ"]].div(gross.loc[too_high], axis=0)
    return w


def _shift_for_closed_bar_execution(weights: pd.DataFrame) -> pd.DataFrame:
    """Use yesterday's close-derived signal for today's close-to-close return."""
    return weights.shift(1).fillna(0.0)


def _equity_from_weights(prices: pd.DataFrame, desired_weights: pd.DataFrame, capital: float) -> pd.Series:
    weights = _shift_for_closed_bar_execution(desired_weights.reindex(prices.index).fillna(0.0))
    returns = prices.pct_change().fillna(0.0)
    portfolio_returns = (weights * returns).sum(axis=1)
    equity = float(capital) * (1.0 + portfolio_returns).cumprod()
    equity.name = "equity"
    return equity


def _build_strategies(prices: pd.DataFrame, ma_windows: Iterable[int], lookbacks: Iterable[int]) -> list[StrategySpec]:
    index = prices.index
    strategies: list[StrategySpec] = []

    strategies.append(
        StrategySpec(
            name="SPY_HODL",
            description="Passive 100% SPY buy-and-hold benchmark.",
            weights=_as_weight_frame(index, 1.0, 0.0),
            params={"type": "benchmark", "risk_off": "none"},
        )
    )
    strategies.append(
        StrategySpec(
            name="QQQ_HODL",
            description="Passive 100% QQQ buy-and-hold benchmark.",
            weights=_as_weight_frame(index, 0.0, 1.0),
            params={"type": "benchmark", "risk_off": "none"},
        )
    )
    strategies.append(
        StrategySpec(
            name="SPY_QQQ_50_50_DAILY_REBAL",
            description="Passive SPY/QQQ 50/50 daily rebalanced benchmark.",
            weights=_as_weight_frame(index, 0.5, 0.5),
            params={"type": "benchmark", "risk_off": "none"},
        )
    )

    for ma in ma_windows:
        spy_above = (prices["SPY"] > prices["SPY"].rolling(ma, min_periods=ma).mean()).astype(float)
        qqq_above = (prices["QQQ"] > prices["QQQ"].rolling(ma, min_periods=ma).mean()).astype(float)

        strategies.append(
            StrategySpec(
                name=f"SPY_SMA{ma}_CASH",
                description=f"100% SPY when SPY closes above its {ma}-day SMA; otherwise cash.",
                weights=_as_weight_frame(index, spy_above, 0.0),
                params={"type": "single_asset_trend", "asset": "SPY", "ma_window": ma, "risk_off": "cash"},
            )
        )
        strategies.append(
            StrategySpec(
                name=f"QQQ_SMA{ma}_CASH",
                description=f"100% QQQ when QQQ closes above its {ma}-day SMA; otherwise cash.",
                weights=_as_weight_frame(index, 0.0, qqq_above),
                params={"type": "single_asset_trend", "asset": "QQQ", "ma_window": ma, "risk_off": "cash"},
            )
        )
        strategies.append(
            StrategySpec(
                name=f"SPY_QQQ_50_50_SMA{ma}_CASH",
                description=f"50% SPY sleeve and 50% QQQ sleeve; each sleeve is active only above its own {ma}-day SMA.",
                weights=_as_weight_frame(index, 0.5 * spy_above, 0.5 * qqq_above),
                params={"type": "dual_asset_trend", "ma_window": ma, "risk_off": "cash"},
            )
        )
        strategies.append(
            StrategySpec(
                name=f"SPY_QQQ_50_50_SMA{ma}_HALF_RISK_OFF",
                description=f"50/50 SPY/QQQ book with partial exposure: each sleeve is 50% active above its {ma}-day SMA and 25% active below it.",
                weights=_as_weight_frame(index, 0.25 + 0.25 * spy_above, 0.25 + 0.25 * qqq_above),
                params={"type": "dual_asset_partial_trend", "ma_window": ma, "risk_off": "half_exposure_cash"},
            )
        )

    for lb in lookbacks:
        mom = prices.pct_change(lb)
        spy_positive = mom["SPY"] > 0.0
        qqq_positive = mom["QQQ"] > 0.0
        spy_winner = mom["SPY"] >= mom["QQQ"]
        qqq_winner = mom["QQQ"] > mom["SPY"]

        dual_spy = (spy_winner & spy_positive).astype(float)
        dual_qqq = (qqq_winner & qqq_positive).astype(float)
        strategies.append(
            StrategySpec(
                name=f"SPY_QQQ_DUAL_MOM_{lb}D_CASH",
                description=f"Own the stronger of SPY/QQQ by {lb}-day return if that return is positive; otherwise cash.",
                weights=_as_weight_frame(index, dual_spy, dual_qqq),
                params={"type": "dual_momentum", "lookback": lb, "risk_off": "cash"},
            )
        )

        # Relative strength with no absolute momentum cash gate; always owns the winner.
        rs_spy = spy_winner.astype(float)
        rs_qqq = qqq_winner.astype(float)
        strategies.append(
            StrategySpec(
                name=f"SPY_QQQ_REL_STRENGTH_{lb}D_ALWAYS_IN",
                description=f"Own the stronger of SPY/QQQ by {lb}-day return; always invested.",
                weights=_as_weight_frame(index, rs_spy, rs_qqq),
                params={"type": "relative_strength_rotation", "lookback": lb, "risk_off": "none"},
            )
        )

    return strategies


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
    eq = eq.dropna().astype(float)
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
    worst_90 = float(eq.pct_change(90).dropna().min()) if len(eq) > 90 else 0.0
    worst_180 = float(eq.pct_change(180).dropna().min()) if len(eq) > 180 else 0.0
    return {
        "total_return_pct": total * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "sortino": _sortino(eq, target_return),
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
        "worst_90d_return_pct": worst_90 * 100.0,
        "worst_180d_return_pct": worst_180 * 100.0,
        "time_underwater_pct": float((dd < 0).mean() * 100.0),
        "max_time_underwater_days": _max_time_underwater_days(eq),
    }


def _capture(strategy: pd.Series, benchmark: pd.Series) -> dict[str, float]:
    s = (strategy / float(strategy.dropna().iloc[0])).dropna()
    b = (benchmark / float(benchmark.dropna().iloc[0])).dropna()
    common = s.index.intersection(b.index)
    s = s.loc[common]
    b = b.loc[common]
    sr = s.pct_change().dropna()
    br = b.pct_change().dropna()
    joined = pd.concat([sr.rename("s"), br.rename("b")], axis=1).dropna()
    if joined.empty:
        return {"return_capture_ratio": 0.0, "up_day_capture_ratio": 0.0, "down_day_capture_ratio": 0.0, "vol_ratio": 0.0}
    s_total = float(s.loc[joined.index[-1]] / s.loc[joined.index[0]] - 1.0)
    b_total = float(b.loc[joined.index[-1]] / b.loc[joined.index[0]] - 1.0)
    up = joined["b"] > 0.0
    down = joined["b"] < 0.0
    up_denom = float(joined.loc[up, "b"].sum())
    down_denom = float(joined.loc[down, "b"].sum())
    return {
        "return_capture_ratio": float(s_total / b_total) if abs(b_total) > 1e-12 else 0.0,
        "up_day_capture_ratio": float(joined.loc[up, "s"].sum() / up_denom) if abs(up_denom) > 1e-12 else 0.0,
        "down_day_capture_ratio": float(joined.loc[down, "s"].sum() / down_denom) if abs(down_denom) > 1e-12 else 0.0,
        "vol_ratio": float(joined["s"].std(ddof=0) / joined["b"].std(ddof=0)) if joined["b"].std(ddof=0) > 0 else 0.0,
    }


def _yearly(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, curve in curves.items():
        s = curve.dropna().astype(float)
        yr = s.resample("YE").last().pct_change().dropna()
        for ts, ret in yr.items():
            rows.append({"series": name, "year": int(ts.year), "return_pct": float(ret * 100.0)})
    return pd.DataFrame(rows)


def _exposure_summary(spec: StrategySpec) -> dict[str, float | str]:
    w = _shift_for_closed_bar_execution(spec.weights)
    gross = w.sum(axis=1)
    rows: dict[str, float | str] = {
        "series": spec.name,
        "avg_spy_weight_pct": float(w["SPY"].mean() * 100.0),
        "avg_qqq_weight_pct": float(w["QQQ"].mean() * 100.0),
        "avg_gross_exposure_pct": float(gross.mean() * 100.0),
        "time_in_market_pct": float((gross > 1e-12).mean() * 100.0),
        "cash_time_pct": float((gross <= 1e-12).mean() * 100.0),
        "turnover_1way_pct_sum": float(w.diff().abs().sum(axis=1).sum() * 100.0 / 2.0),
        "description": spec.description,
    }
    return rows


def _capture_table(curves: pd.DataFrame, benchmarks: list[str]) -> pd.DataFrame:
    rows = []
    for series in curves.columns:
        if series in benchmarks:
            continue
        for benchmark in benchmarks:
            rows.append({"series": series, "benchmark": benchmark, **_capture(curves[series], curves[benchmark])})
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


def _write_summary_md(path: Path, perf: pd.DataFrame, capture: pd.DataFrame, exposure: pd.DataFrame, args: argparse.Namespace, common: pd.DatetimeIndex) -> None:
    perf_cols = ["series", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "worst_90d_return_pct", "worst_180d_return_pct", "max_time_underwater_days"]
    capture_cols = ["series", "benchmark", "return_capture_ratio", "up_day_capture_ratio", "down_day_capture_ratio", "vol_ratio"]
    exposure_cols = ["series", "avg_gross_exposure_pct", "time_in_market_pct", "cash_time_pct", "turnover_1way_pct_sum"]
    lines = [
        "# Equity Book v1 — Fresh Baseline Sweep",
        "",
        "Research-only daily SPY/QQQ baseline sweep. No runtime, paper-trading, broker, governor, live-state, or crypto files are modified.",
        "",
        "## Inputs",
        "",
        "```text",
        f"SPY data: {args.spy_data}",
        f"QQQ data: {args.qqq_data}",
        f"Common overlap: {common[0]} → {common[-1]} ({len(common)} bars)",
        f"MA windows: {args.ma_windows}",
        f"Momentum lookbacks: {args.lookbacks}",
        "Risk-off: cash only",
        "```",
        "",
        "## Top Performance Rows",
        "",
        _md_table(perf, perf_cols, max_rows=20),
        "",
        "## Benchmark Capture Summary",
        "",
        _md_table(capture, capture_cols, max_rows=60),
        "",
        "## Exposure Summary",
        "",
        _md_table(exposure, exposure_cols, max_rows=40),
        "",
        "## Guardrail",
        "",
        "```text",
        "This is baseline research only. It does not approve a strategy for paper trading or live allocation.",
        "Do not combine these outputs with the crypto book or create a global allocator from this run.",
        "Do not add SGOV/BIL/SHV defensive-carry overlays until the base SPY/QQQ book is evaluated.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    ma_windows = _parse_ints(args.ma_windows, "MA window")
    lookbacks = _parse_ints(args.lookbacks, "lookback")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spy_df = _read_price_csv(Path(args.spy_data), "SPY")
    qqq_df = _read_price_csv(Path(args.qqq_data), "QQQ")
    prices = _common_prices(spy_df, qqq_df)
    strategies = _build_strategies(prices, ma_windows, lookbacks)

    curves = pd.DataFrame({spec.name: _equity_from_weights(prices, spec.weights, args.capital) for spec in strategies})
    curves.index.name = "timestamp"

    perf = pd.DataFrame([{"series": name, **_perf(curves[name], args.target_return)} for name in curves.columns])
    perf = perf.sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])

    benchmark_names = ["SPY_HODL", "QQQ_HODL", "SPY_QQQ_50_50_DAILY_REBAL"]
    capture = _capture_table(curves, benchmark_names)
    exposure = pd.DataFrame([_exposure_summary(spec) for spec in strategies])
    yearly = _yearly(curves)
    params = pd.DataFrame(
        [
            {"series": spec.name, "description": spec.description, **spec.params}
            for spec in strategies
        ]
    )

    curves.to_csv(out_dir / "equity_curves.csv")
    perf.to_csv(out_dir / "performance_summary.csv", index=False)
    capture.to_csv(out_dir / "benchmark_capture_summary.csv", index=False)
    exposure.to_csv(out_dir / "exposure_summary.csv", index=False)
    yearly.to_csv(out_dir / "yearly_returns.csv", index=False)
    params.to_csv(out_dir / "strategy_params.csv", index=False)

    payload = {
        "research_status": "research_only_equity_book_v1_fresh_baselines",
        "inputs": {
            "spy_data": args.spy_data,
            "qqq_data": args.qqq_data,
            "capital": args.capital,
            "ma_windows": ma_windows,
            "lookbacks": lookbacks,
            "target_return": args.target_return,
        },
        "common_overlap": {"start": str(curves.index[0]), "end": str(curves.index[-1]), "bars": int(len(curves))},
        "strategy_count": int(len(strategies)),
        "benchmark_series": benchmark_names,
        "risk_off": "cash_only",
        "artifacts": {
            "equity_curves": str(out_dir / "equity_curves.csv"),
            "performance_summary": str(out_dir / "performance_summary.csv"),
            "benchmark_capture_summary": str(out_dir / "benchmark_capture_summary.csv"),
            "exposure_summary": str(out_dir / "exposure_summary.csv"),
            "yearly_returns": str(out_dir / "yearly_returns.csv"),
            "strategy_params": str(out_dir / "strategy_params.csv"),
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
    _write_summary_md(out_dir / "summary.md", perf, capture, exposure, args, curves.index)

    perf_cols = ["series", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "worst_90d_return_pct", "worst_180d_return_pct", "max_time_underwater_days"]
    capture_cols = ["series", "benchmark", "return_capture_ratio", "up_day_capture_ratio", "down_day_capture_ratio", "vol_ratio"]
    with pd.option_context("display.max_columns", None, "display.width", 280, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY BOOK V1 — FRESH BASELINE SWEEP ===")
        print(f"Common overlap: {curves.index[0]} → {curves.index[-1]} ({len(curves)} bars)")
        print(f"Strategies: {len(strategies)}")
        print("\nPerformance Summary:")
        print(perf[[c for c in perf_cols if c in perf.columns]].to_string(index=False))
        print("\nBenchmark Capture Summary:")
        print(capture[[c for c in capture_cols if c in capture.columns]].to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
