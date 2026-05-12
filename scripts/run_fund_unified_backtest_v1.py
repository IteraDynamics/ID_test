#!/usr/bin/env python
"""Fund Unified Backtest v1.

Research-only unified net-of-cost backtest for Itera's crypto sleeve plus the
signal-driven equity MR overlay target book.

Inputs:
  - crypto daily target stream from Crypto Target Stream v1
  - equity daily target book from Equity MR Overlay Target Book v1
  - daily OHLC CSVs for SPY, QQQ, BIL, BTC, ETH

Costs:
  - Crypto uses research.harness.execution_model.ExecutionConfig and compute_fill
  - Equities use explicit fixed bps assumptions, default 5 bps slippage and
    0 bps commissions, with CLI overrides

No fund target book mutation, crypto stream mutation, live trading, broker
integration, paper broker execution, order generation, fills, runtime deployment,
or dynamic allocation is performed.
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

import pandas as pd

from research.harness.execution_model import ExecutionConfig, compute_atr_pct_series, compute_fill

DEFAULT_CRYPTO_TARGETS = "artifacts/crypto_target_stream_v1/crypto_target_exposure_daily.csv"
DEFAULT_EQUITY_TARGET_BOOK = "artifacts/equity_mr_overlay_target_book_v1/equity_mr_overlay_target_book.csv"
DEFAULT_OUT = "artifacts/fund_unified_backtest_v1"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0

CRYPTO_TARGET_COLS = {
    "BTC": ["btc_1h_target_weight", "btc_4h_target_weight"],
    "ETH": ["eth_1h_target_weight", "eth_4h_target_weight"],
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run unified crypto + equity fund backtest with costs",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--crypto-targets", default=DEFAULT_CRYPTO_TARGETS)
    p.add_argument("--equity-target-book", default=DEFAULT_EQUITY_TARGET_BOOK)
    p.add_argument("--btc-data", default="data/BTC_1D.csv")
    p.add_argument("--eth-data", default="data/ETH_1D.csv")
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--crypto-weight", type=float, default=0.50)
    p.add_argument("--equity-weight", type=float, default=0.50)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--equity-slippage-bps", type=float, default=5.0)
    p.add_argument("--equity-commission-bps", type=float, default=0.0)
    p.add_argument("--accounting-tolerance", type=float, default=1e-6)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_price(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {label} price data: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty required {label} price data: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(columns={"adj close": "close", "adj_close": "close", "adjusted_close": "close"})
    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} price data missing required OHLC columns: {missing}. Available={list(df.columns)}")
    out = df[[c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]].copy()
    for c in out.columns:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    if out.empty:
        raise ValueError(f"No valid {label} OHLC rows after cleanup: {path}")
    out["atr_pct"] = compute_atr_pct_series(out, period=14)
    return out


def _read_indexed(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {label}: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty required {label}: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    df.index = pd.to_datetime(df.index.normalize())
    return df.groupby(level=0).last()


def _load_equity_target_book(path: Path) -> pd.DataFrame:
    raw = _read_indexed(path, "equity MR overlay target book")
    required = ["instrument", "target_weight"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"Equity target book missing required columns: {missing}. Available={list(raw.columns)}")
    pivot = raw.pivot_table(index=raw.index, columns="instrument", values="target_weight", aggfunc="last").fillna(0.0)
    for asset in ["SPY", "QQQ", "BIL"]:
        if asset not in pivot.columns:
            pivot[asset] = 0.0
    return pivot[["SPY", "QQQ", "BIL"]].sort_index()


def _load_crypto_targets(path: Path) -> pd.DataFrame:
    df = _read_indexed(path, "crypto target stream")
    missing = []
    for cols in CRYPTO_TARGET_COLS.values():
        missing.extend([c for c in cols if c not in df.columns])
    if missing:
        raise ValueError(f"Crypto target stream missing required component columns: {missing}. Available={list(df.columns)}")
    out = pd.DataFrame(index=df.index)
    out["BTC"] = df[CRYPTO_TARGET_COLS["BTC"]].apply(pd.to_numeric, errors="coerce").fillna(0.0).sum(axis=1)
    out["ETH"] = df[CRYPTO_TARGET_COLS["ETH"]].apply(pd.to_numeric, errors="coerce").fillna(0.0).sum(axis=1)
    if "crypto_cash_or_risk_off_weight" in df.columns:
        out["CRYPTO_CASH"] = pd.to_numeric(df["crypto_cash_or_risk_off_weight"], errors="coerce").fillna(0.0)
    else:
        out["CRYPTO_CASH"] = 1.0 - out["BTC"] - out["ETH"]
    out["crypto_source_status"] = df.get("source_status", pd.Series("unknown", index=df.index)).astype(str)
    out["crypto_broker_ready"] = df.get("broker_ready", pd.Series(False, index=df.index))
    out["crypto_total_weight"] = out[["BTC", "ETH", "CRYPTO_CASH"]].sum(axis=1)
    return out.sort_index()


def _combine_targets(crypto: pd.DataFrame, equity: pd.DataFrame, crypto_w: float, equity_w: float, tol: float) -> pd.DataFrame:
    total = crypto_w + equity_w
    if total <= 0:
        raise ValueError("crypto-weight + equity-weight must be positive")
    crypto_w = crypto_w / total
    equity_w = equity_w / total
    common = crypto.index.intersection(equity.index).sort_values()
    if len(common) == 0:
        raise ValueError("No overlapping dates between crypto and equity targets")
    c = crypto.reindex(common)
    e = equity.reindex(common).fillna(0.0)
    out = pd.DataFrame(index=common)
    out["BTC"] = crypto_w * c["BTC"]
    out["ETH"] = crypto_w * c["ETH"]
    out["SPY"] = equity_w * e["SPY"]
    out["QQQ"] = equity_w * e["QQQ"]
    out["BIL"] = equity_w * e["BIL"]
    out["CASH"] = crypto_w * c["CRYPTO_CASH"]
    out["total_accounted_weight"] = out[["BTC", "ETH", "SPY", "QQQ", "BIL", "CASH"]].sum(axis=1)
    out["accounting_error"] = out["total_accounted_weight"] - 1.0
    out["accounting_ok"] = out["accounting_error"].abs() <= tol
    out["crypto_source_status"] = c["crypto_source_status"].astype(str)
    out["crypto_total_weight"] = c["crypto_total_weight"]
    return out


def _perf(eq: pd.Series) -> dict[str, float]:
    eq = eq.dropna().astype(float)
    if len(eq) < 2:
        return {k: 0.0 for k in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "worst_90d_return_pct", "worst_180d_return_pct", "max_time_underwater_days"]}
    rets = eq.pct_change(fill_method=None).dropna()
    years = max((eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 24 * 3600), 1e-9)
    total = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    std = float(rets.std(ddof=0))
    sharpe = float((rets.mean() / std) * math.sqrt(TRADING_DAYS)) if std > 1e-12 else 0.0
    downside = rets.clip(upper=0.0)
    downside_dev = float((downside.pow(2).mean()) ** 0.5)
    sortino = float((rets.mean() / downside_dev) * math.sqrt(TRADING_DAYS)) if downside_dev > 1e-12 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    ann_vol = float(std * math.sqrt(TRADING_DAYS)) if std > 0 else 0.0
    worst_90 = float(eq.pct_change(90, fill_method=None).dropna().min()) if len(eq) > 90 else 0.0
    worst_180 = float(eq.pct_change(180, fill_method=None).dropna().min()) if len(eq) > 180 else 0.0
    underwater = dd < 0
    max_days = 0.0
    start = None
    for ts, flag in underwater.items():
        if flag and start is None:
            start = ts
        elif not flag and start is not None:
            max_days = max(max_days, (ts - start).total_seconds() / 86400.0)
            start = None
    if start is not None:
        max_days = max(max_days, (eq.index[-1] - start).total_seconds() / 86400.0)
    return {
        "total_return_pct": total * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
        "worst_90d_return_pct": worst_90 * 100.0,
        "worst_180d_return_pct": worst_180 * 100.0,
        "max_time_underwater_days": max_days,
    }


def _run_backtest(targets: pd.DataFrame, prices: dict[str, pd.DataFrame], capital: float, equity_slip_bps: float, equity_commission_bps: float, crypto_config: ExecutionConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    price_close = pd.DataFrame({asset: df["close"] for asset, df in prices.items()}).sort_index().ffill()
    atr_pct = pd.DataFrame({asset: df["atr_pct"] for asset, df in prices.items()}).sort_index().ffill().fillna(0.0)
    idx = targets.index.intersection(price_close.index).sort_values()
    if len(idx) < 2:
        raise ValueError("Insufficient overlapping dates between targets and price data")
    w = targets.reindex(idx)[["BTC", "ETH", "SPY", "QQQ", "BIL", "CASH"]].fillna(0.0)
    px = price_close.reindex(idx).ffill()
    atr = atr_pct.reindex(idx).ffill().fillna(0.0)

    nav_gross = capital
    nav_net = capital
    rows: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    prev_w = pd.Series(0.0, index=w.columns)
    prev_w["CASH"] = 1.0

    gross_curve = []
    net_curve = []
    dates = []
    for i, ts in enumerate(idx):
        if i > 0:
            prev_ts = idx[i - 1]
            asset_rets = px.loc[ts, ["BTC", "ETH", "SPY", "QQQ", "BIL"]] / px.loc[prev_ts, ["BTC", "ETH", "SPY", "QQQ", "BIL"]] - 1.0
            gross_ret = float((prev_w[["BTC", "ETH", "SPY", "QQQ", "BIL"]] * asset_rets).sum())
            nav_gross *= 1.0 + gross_ret
            nav_net *= 1.0 + gross_ret
        target_w = w.loc[ts]
        delta = target_w - prev_w
        day_cost = 0.0
        day_turnover = float(delta.abs().sum())
        for asset in ["BTC", "ETH", "SPY", "QQQ", "BIL"]:
            dw = float(delta[asset])
            notional = abs(dw) * nav_net
            if notional <= 1e-9:
                continue
            direction = "BUY" if dw > 0 else "SELL"
            if asset in ["BTC", "ETH"]:
                fill = compute_fill(
                    mid_price=float(px.loc[ts, asset]),
                    notional=notional,
                    nav=nav_net,
                    atr_pct=float(atr.loc[ts, asset]),
                    direction=direction,
                    config=crypto_config,
                )
                cost = fill.total_cost_usd
                cost_bps = fill.cost_bps
                fee_usd = fill.fee_usd
                slippage_usd = fill.slippage_usd
                spread_usd = fill.spread_usd
            else:
                cost_bps = equity_slip_bps + equity_commission_bps
                cost = notional * cost_bps / 10_000.0
                fee_usd = notional * equity_commission_bps / 10_000.0
                slippage_usd = notional * equity_slip_bps / 10_000.0
                spread_usd = 0.0
            nav_net -= cost
            day_cost += cost
            trades.append({
                "timestamp": ts,
                "asset": asset,
                "direction": direction,
                "delta_weight": dw,
                "notional_usd": notional,
                "cost_usd": cost,
                "cost_bps": cost_bps,
                "fee_usd": fee_usd,
                "slippage_usd": slippage_usd,
                "spread_usd": spread_usd,
                "nav_after_cost": nav_net,
            })
        prev_w = target_w
        dates.append(ts)
        gross_curve.append(nav_gross)
        net_curve.append(nav_net)
        rows.append({
            "timestamp": ts,
            "gross_nav": nav_gross,
            "net_nav": nav_net,
            "daily_cost_usd": day_cost,
            "daily_turnover": day_turnover,
            "btc_weight": float(target_w["BTC"]),
            "eth_weight": float(target_w["ETH"]),
            "spy_weight": float(target_w["SPY"]),
            "qqq_weight": float(target_w["QQQ"]),
            "bil_weight": float(target_w["BIL"]),
            "cash_weight": float(target_w["CASH"]),
        })
    curves = pd.DataFrame(rows).set_index("timestamp")
    trades_df = pd.DataFrame(trades)
    summary_rows = []
    gross_perf = _perf(curves["gross_nav"])
    net_perf = _perf(curves["net_nav"])
    for label, perf in [("gross_before_costs", gross_perf), ("net_after_costs", net_perf)]:
        row = {"series": label, **perf}
        summary_rows.append(row)
    total_cost = float(curves["daily_cost_usd"].sum())
    summary_rows.append({"series": "cost_summary", "total_cost_usd": total_cost, "total_cost_pct_start_nav": total_cost / capital * 100.0, "avg_daily_turnover_pct": float(curves["daily_turnover"].mean() * 100.0), "total_turnover": float(curves["daily_turnover"].sum())})
    summary = pd.DataFrame(summary_rows)
    return curves, trades_df, summary


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
            v = row[c]
            vals.append(f"{v:.6f}" if isinstance(v, float) else str(v).replace("|", "\\|"))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    crypto = _load_crypto_targets(Path(args.crypto_targets))
    equity = _load_equity_target_book(Path(args.equity_target_book))
    targets = _combine_targets(crypto, equity, args.crypto_weight, args.equity_weight, args.accounting_tolerance)
    if not bool(targets["accounting_ok"].all()):
        raise SystemExit("Fail-closed: unified target accounting is not 100% valid")
    prices = {
        "BTC": _read_price(Path(args.btc_data), "BTC"),
        "ETH": _read_price(Path(args.eth_data), "ETH"),
        "SPY": _read_price(Path(args.spy_data), "SPY"),
        "QQQ": _read_price(Path(args.qqq_data), "QQQ"),
        "BIL": _read_price(Path(args.bil_data), "BIL"),
    }
    crypto_config = ExecutionConfig.from_env()
    curves, trades, summary = _run_backtest(targets, prices, args.capital, args.equity_slippage_bps, args.equity_commission_bps, crypto_config)

    targets.to_csv(out_dir / "unified_fund_targets.csv")
    curves.to_csv(out_dir / "unified_fund_curves.csv")
    trades.to_csv(out_dir / "unified_fund_trade_costs.csv", index=False)
    summary.to_csv(out_dir / "unified_fund_backtest_summary.csv", index=False)
    payload = {
        "research_status": "research_only_unified_fund_backtest_v1",
        "crypto_cost_model": crypto_config.__dict__,
        "equity_cost_model": {"equity_slippage_bps": args.equity_slippage_bps, "equity_commission_bps": args.equity_commission_bps},
        "inputs": vars(args),
        "outputs": {
            "targets": str(out_dir / "unified_fund_targets.csv"),
            "curves": str(out_dir / "unified_fund_curves.csv"),
            "trades": str(out_dir / "unified_fund_trade_costs.csv"),
            "summary": str(out_dir / "unified_fund_backtest_summary.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "guardrails": {"research_only": True, "broker_ready": False, "generates_orders": False, "simulates_fills": False, "mutates_target_book": False},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (out_dir / "summary.md").write_text("\n".join([
        "# Fund Unified Backtest v1",
        "",
        "Research-only unified crypto + equity MR overlay backtest, net of modeled costs.",
        "",
        "## Cost Assumptions",
        "",
        "```text",
        f"Crypto ExecutionConfig: {crypto_config}",
        f"Equity slippage bps: {args.equity_slippage_bps}",
        f"Equity commission bps: {args.equity_commission_bps}",
        "```",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Guardrail",
        "",
        "```text",
        "Research only. No target-book mutation, live trading, broker integration, paper-broker execution, order generation, runtime deployment, or dynamic allocator changes are approved.",
        "```",
        "",
    ]), encoding="utf-8")

    with pd.option_context("display.max_columns", None, "display.width", 900, "display.float_format", "{:.6f}".format):
        print("\n=== FUND UNIFIED BACKTEST V1 ===")
        print("\nCost assumptions:")
        print(f"Crypto: {crypto_config}")
        print(f"Equity: slippage_bps={args.equity_slippage_bps}, commission_bps={args.equity_commission_bps}")
        print("\nSummary:")
        print(summary.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
