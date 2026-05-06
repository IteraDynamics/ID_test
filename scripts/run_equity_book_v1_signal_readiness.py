#!/usr/bin/env python
"""Equity Book v1 — signal readiness artifact runner.

Research-only script. Replays the SPY/QQQ SMA band strategy over daily data and
emits deterministic target-weight and signal-history artifacts.

No broker, runtime, paper-trading, execution, live-state, governor, dashboard,
crypto allocator, or global allocator changes are made.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import StrategyContext
from research.strategies import equity_spy_qqq_sma_band_v1 as strategy


DEFAULT_OUT = "artifacts/equity_book_v1_signal_readiness"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Replay Equity Book v1 SPY/QQQ SMA band signals and emit readiness artifacts",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    p.add_argument("--sma-window", type=int, default=strategy.DEFAULT_SMA_WINDOW)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    return p.parse_args()


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
    if "close" not in df.columns:
        raise ValueError(f"{label} data missing close column; got {list(df.columns)}")
    return df


def _common_prices(spy_df: pd.DataFrame, qqq_df: pd.DataFrame) -> pd.DataFrame:
    spy = pd.to_numeric(spy_df["close"], errors="coerce").dropna().rename("spy_close")
    qqq = pd.to_numeric(qqq_df["close"], errors="coerce").dropna().rename("qqq_close")
    prices = pd.concat([spy, qqq], axis=1).dropna().sort_index()
    if len(prices) < strategy.DEFAULT_SMA_WINDOW:
        raise ValueError(f"Insufficient common SPY/QQQ history: {len(prices)} rows")
    return prices


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


def _perf(eq: pd.Series) -> dict[str, float]:
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
    return {
        "total_return_pct": total * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
    }


def _replay(prices: pd.DataFrame, sma_window: int, capital: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    exposure = 0.0
    for i in range(len(prices)):
        window_df = prices.iloc[: i + 1]
        ctx = StrategyContext(
            regime=RegimeLabel.UNKNOWN,
            current_exposure_frac=exposure,
            asset="EQUITY_BOOK",
            bar_index=i,
            meta={},
        )
        intent = strategy.generate_intent(window_df, ctx, sma_window=sma_window)
        weights = intent.meta["target_weights"]
        rows.append(
            {
                "timestamp": prices.index[i],
                "action": intent.action.value,
                "confidence": intent.confidence,
                "desired_exposure_frac": intent.desired_exposure_frac,
                "target_spy_weight": weights["SPY"],
                "target_qqq_weight": weights["QQQ"],
                "target_cash_weight": weights["cash"],
                "spy_close": intent.meta["spy_close"],
                "qqq_close": intent.meta["qqq_close"],
                "spy_sma": intent.meta["spy_sma"],
                "qqq_sma": intent.meta["qqq_sma"],
                "spy_active": intent.meta["spy_active"],
                "qqq_active": intent.meta["qqq_active"],
                "warmup": intent.meta["warmup"],
                "reason": intent.reason,
                "strategy_id": intent.strategy_id,
            }
        )
        exposure = float(intent.desired_exposure_frac)

    signals = pd.DataFrame(rows).set_index("timestamp")
    returns = prices.pct_change().fillna(0.0)
    exec_weights = signals[["target_spy_weight", "target_qqq_weight"]].shift(1).fillna(0.0)
    exec_weights.columns = ["SPY", "QQQ"]
    strategy_returns = exec_weights["SPY"] * returns["spy_close"] + exec_weights["QQQ"] * returns["qqq_close"]
    passive_returns = 0.50 * returns["spy_close"] + 0.50 * returns["qqq_close"]
    curves = pd.DataFrame(
        {
            "equity_book_sma_band": float(capital) * (1.0 + strategy_returns).cumprod(),
            "spy_qqq_50_50_daily_rebal": float(capital) * (1.0 + passive_returns).cumprod(),
        },
        index=prices.index,
    )
    executed = signals.copy()
    executed["exec_spy_weight"] = exec_weights["SPY"]
    executed["exec_qqq_weight"] = exec_weights["QQQ"]
    executed["exec_cash_weight"] = 1.0 - executed["exec_spy_weight"] - executed["exec_qqq_weight"]
    executed["strategy_return"] = strategy_returns
    return signals, executed, curves


def _write_summary_md(path: Path, payload: dict, perf: pd.DataFrame) -> None:
    lines = [
        "# Equity Book v1 — Signal Readiness",
        "",
        "Research-only replay of the SPY/QQQ SMA band strategy module.",
        "",
        "## Inputs",
        "",
        "```text",
        f"SPY data: {payload['inputs']['spy_data']}",
        f"QQQ data: {payload['inputs']['qqq_data']}",
        f"SMA window: {payload['inputs']['sma_window']}",
        f"Common overlap: {payload['common_overlap']['start']} → {payload['common_overlap']['end']} ({payload['common_overlap']['bars']} bars)",
        "```",
        "",
        "## Performance Summary",
        "",
        perf.to_markdown(index=False),
        "",
        "## Guardrail",
        "",
        "```text",
        "This script produces offline signal and exposure artifacts only.",
        "It does not approve paper trading, live allocation, broker changes, crypto allocator changes, or defensive carry overlays.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spy_df = _read_price_csv(Path(args.spy_data), "SPY")
    qqq_df = _read_price_csv(Path(args.qqq_data), "QQQ")
    prices = _common_prices(spy_df, qqq_df)
    signals, executed, curves = _replay(prices, args.sma_window, args.capital)

    perf = pd.DataFrame(
        [
            {"series": "equity_book_sma_band", **_perf(curves["equity_book_sma_band"])},
            {"series": "spy_qqq_50_50_daily_rebal", **_perf(curves["spy_qqq_50_50_daily_rebal"])},
        ]
    )

    signals.to_csv(out_dir / "signal_history.csv")
    executed.to_csv(out_dir / "executed_weight_history.csv")
    curves.to_csv(out_dir / "equity_curves.csv")
    perf.to_csv(out_dir / "performance_summary.csv", index=False)

    payload = {
        "research_status": "research_only_equity_book_v1_signal_readiness",
        "inputs": {
            "spy_data": args.spy_data,
            "qqq_data": args.qqq_data,
            "sma_window": args.sma_window,
            "capital": args.capital,
        },
        "common_overlap": {"start": str(prices.index[0]), "end": str(prices.index[-1]), "bars": int(len(prices))},
        "strategy_id": strategy.STRATEGY_ID,
        "artifacts": {
            "signal_history": str(out_dir / "signal_history.csv"),
            "executed_weight_history": str(out_dir / "executed_weight_history.csv"),
            "equity_curves": str(out_dir / "equity_curves.csv"),
            "performance_summary": str(out_dir / "performance_summary.csv"),
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
    _write_summary_md(out_dir / "summary.md", payload, perf)

    with pd.option_context("display.max_columns", None, "display.width", 240, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY BOOK V1 — SIGNAL READINESS ===")
        print(f"Common overlap: {prices.index[0]} → {prices.index[-1]} ({len(prices)} bars)")
        print(f"Strategy: {strategy.STRATEGY_ID} | SMA window: {args.sma_window}")
        print("\nPerformance Summary:")
        print(perf.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
