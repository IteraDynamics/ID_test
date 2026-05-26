#!/usr/bin/env python
"""Compare trade idea replay candidates against simple buy-and-hold benchmarks.

This script turns the trade idea research loop into a scoreboard:

    - selected trade-radar risk-sweep candidates
    - SPY buy-and-hold
    - QQQ buy-and-hold
    - BTC buy-and-hold
    - ETH buy-and-hold
    - BTC/ETH 50/50 buy-and-hold, daily rebalanced by mark-to-market weights

The goal is not to make a strategy look good. The goal is to answer the
capital-allocation question: does this candidate deserve attention versus the
obvious alternatives?

Research/paper only. No runtime, broker, or live execution code is modified.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_CANDIDATES = [
    "remove_known_weak_tickers__very_aggressive",
    "crypto_plus_growth_core__aggressive_institutional",
    "crypto_plus_growth_core__very_aggressive",
    "crypto_plus_growth__very_aggressive",
    "all_assets__very_aggressive",
]

DEFAULT_BENCHMARKS = ["SPY", "QQQ", "BTC-USD", "ETH-USD"]
TRADING_DAYS = 252.0


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _to_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        v = float(value)
        if math.isnan(v):
            return "n/a"
        return f"{v:.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _candidate_summary_to_row(summary: dict[str, Any], source_path: Path) -> dict[str, Any]:
    name = summary.get("scenario") or source_path.parent.name
    return {
        "name": name,
        "type": "trade_radar",
        "universe": summary.get("universe"),
        "risk_band": summary.get("risk_band"),
        "ticker_count": summary.get("ticker_count"),
        "total_return_pct": summary.get("total_return_pct_on_capital"),
        "cagr_pct": summary.get("cagr_pct"),
        "maxdd_pct": summary.get("max_drawdown_pct_on_equity"),
        "sharpe": summary.get("sharpe"),
        "sortino": summary.get("sortino"),
        "calmar": summary.get("calmar"),
        "ann_vol_pct": summary.get("annualized_vol_pct"),
        "win_rate_pct": summary.get("win_rate_pct"),
        "expectancy_pct": summary.get("expectancy_pct_per_realized_trade"),
        "realized_trades": summary.get("closed_realized_trades"),
        "best_day_pct": summary.get("best_day_pct"),
        "worst_day_pct": summary.get("worst_day_pct"),
        "final_equity": summary.get("final_equity"),
        "source": str(source_path),
    }


def _normalize_price_frame(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    cols = {str(c).lower().strip(): c for c in df.columns}
    date_col = None
    for key in ["date", "timestamp", "time", "datetime"]:
        if key in cols:
            date_col = cols[key]
            break
    if date_col is None:
        date_col = df.columns[0]

    close_col = None
    for key in ["close", "adj close", "adj_close", "price"]:
        if key in cols:
            close_col = cols[key]
            break
    if close_col is None:
        numeric_cols = [c for c in df.columns if c != date_col and pd.api.types.is_numeric_dtype(df[c])]
        if not numeric_cols:
            raise ValueError(f"Could not identify close column for {ticker}; columns={list(df.columns)}")
        close_col = numeric_cols[-1]

    out = df[[date_col, close_col]].copy()
    out.columns = ["date", ticker]
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    out[ticker] = pd.to_numeric(out[ticker], errors="coerce")
    out = out.dropna(subset=["date", ticker]).sort_values("date")
    out = out.drop_duplicates(subset=["date"], keep="last")
    return out


def _load_price(data_dir: Path, ticker: str) -> pd.DataFrame:
    candidates = [
        data_dir / f"{ticker}.csv",
        data_dir / f"{ticker.lower()}.csv",
        data_dir / f"{ticker.replace('-', '_')}.csv",
        data_dir / f"{ticker.replace('-', '').lower()}.csv",
    ]
    for path in candidates:
        if path.exists():
            return _normalize_price_frame(pd.read_csv(path), ticker)

    # Fallback: search one level deep for a file that starts with or contains ticker.
    safe = ticker.lower().replace("-", "").replace("_", "")
    for path in sorted(data_dir.glob("*.csv")):
        stem = path.stem.lower().replace("-", "").replace("_", "")
        if stem == safe or stem.startswith(safe) or safe in stem:
            return _normalize_price_frame(pd.read_csv(path), ticker)

    raise FileNotFoundError(f"No CSV found for {ticker} in {data_dir}")


def _equity_metrics(equity: pd.Series, capital: float) -> dict[str, Any]:
    equity = pd.to_numeric(equity, errors="coerce").dropna()
    if equity.empty:
        return {}

    returns = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    total_return_pct = (equity.iloc[-1] / capital - 1.0) * 100.0
    years = max(len(equity) / TRADING_DAYS, 1.0 / TRADING_DAYS)
    cagr_pct = ((equity.iloc[-1] / capital) ** (1.0 / years) - 1.0) * 100.0 if equity.iloc[-1] > 0 and capital > 0 else float("nan")

    peak = equity.cummax()
    dd = equity / peak - 1.0
    maxdd_pct = dd.min() * 100.0
    ann_vol_pct = returns.std(ddof=0) * math.sqrt(TRADING_DAYS) * 100.0 if not returns.empty else float("nan")
    sharpe = (returns.mean() / returns.std(ddof=0) * math.sqrt(TRADING_DAYS)) if returns.std(ddof=0) and returns.std(ddof=0) > 0 else float("nan")
    downside = returns[returns < 0]
    sortino = (returns.mean() / downside.std(ddof=0) * math.sqrt(TRADING_DAYS)) if len(downside) > 1 and downside.std(ddof=0) > 0 else float("nan")
    calmar = cagr_pct / abs(maxdd_pct) if maxdd_pct < 0 else float("nan")

    monthly = equity.resample("ME").last().pct_change().dropna() if isinstance(equity.index, pd.DatetimeIndex) else pd.Series(dtype=float)
    yearly = equity.resample("YE").last().pct_change().dropna() if isinstance(equity.index, pd.DatetimeIndex) else pd.Series(dtype=float)

    return {
        "total_return_pct": total_return_pct,
        "cagr_pct": cagr_pct,
        "maxdd_pct": maxdd_pct,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "ann_vol_pct": ann_vol_pct,
        "best_day_pct": returns.max() * 100.0 if not returns.empty else float("nan"),
        "worst_day_pct": returns.min() * 100.0 if not returns.empty else float("nan"),
        "best_month_pct": monthly.max() * 100.0 if not monthly.empty else float("nan"),
        "worst_month_pct": monthly.min() * 100.0 if not monthly.empty else float("nan"),
        "best_year_pct": yearly.max() * 100.0 if not yearly.empty else float("nan"),
        "worst_year_pct": yearly.min() * 100.0 if not yearly.empty else float("nan"),
        "positive_day_rate_pct": (returns > 0).mean() * 100.0 if not returns.empty else float("nan"),
        "years": years,
        "final_equity": equity.iloc[-1],
    }


def _buy_hold_row(data_dir: Path, ticker: str, start: str, end: str, capital: float) -> tuple[dict[str, Any], pd.Series]:
    px = _load_price(data_dir, ticker)
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    px = px[(px["date"] >= start_dt) & (px["date"] <= end_dt)].copy()
    if px.empty:
        raise ValueError(f"No price rows for {ticker} between {start} and {end}")
    px = px.set_index("date")[ticker]
    equity = capital * (px / px.iloc[0])
    metrics = _equity_metrics(equity, capital)
    row = {
        "name": f"{ticker}_buy_hold",
        "type": "benchmark",
        "universe": ticker,
        "risk_band": "buy_hold",
        "ticker_count": 1,
        "win_rate_pct": None,
        "expectancy_pct": None,
        "realized_trades": None,
        "source": str(data_dir),
    }
    row.update(metrics)
    return row, equity


def _combo_5050_row(data_dir: Path, tickers: list[str], start: str, end: str, capital: float, name: str) -> tuple[dict[str, Any], pd.Series]:
    frames = []
    for ticker in tickers:
        px = _load_price(data_dir, ticker)
        px = px[(px["date"] >= pd.to_datetime(start)) & (px["date"] <= pd.to_datetime(end))]
        frames.append(px.set_index("date")[ticker])
    prices = pd.concat(frames, axis=1, join="inner").dropna()
    prices.columns = tickers
    if prices.empty:
        raise ValueError(f"No overlapping price rows for {tickers} between {start} and {end}")
    normalized = prices.divide(prices.iloc[0])
    weights = [1.0 / len(tickers)] * len(tickers)
    equity = capital * normalized.mul(weights, axis=1).sum(axis=1)
    metrics = _equity_metrics(equity, capital)
    row = {
        "name": name,
        "type": "benchmark",
        "universe": "+".join(tickers),
        "risk_band": "buy_hold_50_50",
        "ticker_count": len(tickers),
        "win_rate_pct": None,
        "expectancy_pct": None,
        "realized_trades": None,
        "source": str(data_dir),
    }
    row.update(metrics)
    return row, equity


def _load_trade_radar_candidates(risk_sweep_dir: Path, candidates: list[str]) -> list[dict[str, Any]]:
    rows = []
    for scenario in candidates:
        summary_path = risk_sweep_dir / scenario / "replay_summary.json"
        summary = _read_json(summary_path)
        if not summary:
            rows.append({"name": scenario, "type": "trade_radar", "source": str(summary_path), "error": "missing_summary"})
            continue
        rows.append(_candidate_summary_to_row(summary, summary_path))
    return rows


def _score_sort(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["calmar_num"] = pd.to_numeric(out.get("calmar"), errors="coerce")
    out["sharpe_num"] = pd.to_numeric(out.get("sharpe"), errors="coerce")
    out["cagr_num"] = pd.to_numeric(out.get("cagr_pct"), errors="coerce")
    return out.sort_values(["calmar_num", "sharpe_num", "cagr_num"], ascending=[False, False, False])


def _print_scoreboard(df: pd.DataFrame) -> None:
    print("\n" + "=" * 188)
    print("  TRADE IDEA SCOREBOARD — STRATEGY VS BENCHMARKS")
    print("=" * 188)
    if df.empty:
        print("  No rows.")
        return

    view = _score_sort(df)
    print(
        f"  {'Name':<49} {'Type':<13} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} "
        f"{'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'AnnVol':>8} {'WorstM':>8} {'WorstY':>8} {'WorstD':>8}"
    )
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('name')):<49} {str(r.get('type')):<13} "
            f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('total_return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
            f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('sortino'), 3):>8} {_fmt(r.get('calmar'), 3):>8} "
            f"{_fmt(r.get('ann_vol_pct')):>8} {_fmt(r.get('worst_month_pct')):>8} {_fmt(r.get('worst_year_pct')):>8} {_fmt(r.get('worst_day_pct')):>8}"
        )
    print("=" * 188)


def _print_trade_radar_vs_benchmarks(df: pd.DataFrame) -> None:
    if df.empty:
        return
    trade = _score_sort(df[df["type"] == "trade_radar"])
    bench = _score_sort(df[df["type"] == "benchmark"])
    if trade.empty or bench.empty:
        return

    best_trade = trade.iloc[0]
    best_bench = bench.iloc[0]
    print("\n" + "=" * 188)
    print("  DECISION SNAPSHOT")
    print("=" * 188)
    print(
        f"  Best trade radar by Calmar : {best_trade.get('name')} | "
        f"CAGR={_fmt(best_trade.get('cagr_pct'))}% MaxDD={_fmt(best_trade.get('maxdd_pct'))}% "
        f"Sharpe={_fmt(best_trade.get('sharpe'), 3)} Calmar={_fmt(best_trade.get('calmar'), 3)}"
    )
    print(
        f"  Best benchmark by Calmar   : {best_bench.get('name')} | "
        f"CAGR={_fmt(best_bench.get('cagr_pct'))}% MaxDD={_fmt(best_bench.get('maxdd_pct'))}% "
        f"Sharpe={_fmt(best_bench.get('sharpe'), 3)} Calmar={_fmt(best_bench.get('calmar'), 3)}"
    )
    print("=" * 188)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare trade radar candidates against buy-and-hold benchmarks")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--risk-sweep-dir", default="artifacts/trade_idea_risk_sweep")
    p.add_argument("--out-dir", default="artifacts/trade_idea_scoreboard")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--candidates", nargs="+", default=DEFAULT_CANDIDATES)
    p.add_argument("--benchmarks", nargs="+", default=DEFAULT_BENCHMARKS)
    p.add_argument("--skip-btc-eth-5050", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    risk_sweep_dir = Path(args.risk_sweep_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    rows.extend(_load_trade_radar_candidates(risk_sweep_dir, args.candidates))

    equity_curves = {}
    for ticker in args.benchmarks:
        row, equity = _buy_hold_row(data_dir, ticker, args.start, args.end, args.capital)
        rows.append(row)
        equity_curves[row["name"]] = equity.rename(row["name"])

    if not args.skip_btc_eth_5050 and "BTC-USD" in args.benchmarks and "ETH-USD" in args.benchmarks:
        row, equity = _combo_5050_row(data_dir, ["BTC-USD", "ETH-USD"], args.start, args.end, args.capital, "BTC_ETH_50_50_buy_hold")
        rows.append(row)
        equity_curves[row["name"]] = equity.rename(row["name"])

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "strategy_scoreboard.csv", index=False)
    (out_dir / "strategy_scoreboard.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    if equity_curves:
        pd.concat(equity_curves.values(), axis=1).to_csv(out_dir / "benchmark_equity_curves.csv")

    _print_scoreboard(df)
    _print_trade_radar_vs_benchmarks(df)
    print(f"  Scoreboard CSV : {out_dir / 'strategy_scoreboard.csv'}")
    print(f"  Scoreboard JSON: {out_dir / 'strategy_scoreboard.json'}")
    print(f"  Benchmark curves: {out_dir / 'benchmark_equity_curves.csv'}")
    print("  Verdict         : SCOREBOARD RESEARCH ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
