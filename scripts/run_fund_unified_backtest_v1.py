#!/usr/bin/env python
"""Fund Unified Backtest v1.

Research-only unified net-of-cost backtest for Itera's crypto sleeve plus the
signal-driven equity MR overlay target book.

Backtest mechanics:
  - Targets are closed-bar daily target weights.
  - Initial allocation is established without charging strategy friction by default.
  - Portfolio weights drift with asset returns between rebalance dates.
  - Rebalance costs are charged only when target drift exceeds threshold.
  - Crypto costs use research.harness.execution_model.ExecutionConfig.
  - Equity costs use explicit fixed bps assumptions.

No fund target book mutation, crypto stream mutation, live trading, broker
integration, paper broker execution, order generation, runtime deployment, or
dynamic allocation is performed.
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
ASSETS = ["BTC", "ETH", "SPY", "QQQ", "BIL"]
ALL_WEIGHTS = ASSETS + ["CASH"]
CRYPTO_TARGET_COLS = {"BTC": ["btc_1h_target_weight", "btc_4h_target_weight"], "ETH": ["eth_1h_target_weight", "eth_4h_target_weight"]}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run unified crypto + equity fund backtest with costs", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
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
    p.add_argument("--rebalance-threshold-bps", type=float, default=25.0, help="Minimum absolute aggregate target/current weight delta before charging rebalance costs.")
    p.add_argument("--charge-initial-costs", action="store_true", help="Charge costs on first allocation from cash. Default excludes initial deployment friction from strategy costs.")
    p.add_argument("--accounting-tolerance", type=float, default=1e-6)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _normalize_datetime_series(s: pd.Series) -> pd.Series:
    dt = pd.to_datetime(s, errors="coerce")
    try:
        if getattr(dt.dt, "tz", None) is not None:
            dt = dt.dt.tz_localize(None)
    except Exception:
        pass
    return dt.dt.normalize()


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
    df[time_col] = _normalize_datetime_series(df[time_col])
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    return df.groupby(level=0).last()


def _load_equity_target_book(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required equity MR overlay target book: {path}")
    raw = pd.read_csv(path)
    if raw.empty:
        raise ValueError(f"Empty required equity MR overlay target book: {path}")
    time_col = _detect_time_col(raw)
    raw["timestamp"] = _normalize_datetime_series(raw[time_col])
    raw = raw.dropna(subset=["timestamp"])
    required = ["timestamp", "instrument", "target_weight"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"Equity target book missing required columns: {missing}. Available={list(raw.columns)}")
    raw["instrument"] = raw["instrument"].astype(str).str.upper().str.strip()
    raw["target_weight"] = pd.to_numeric(raw["target_weight"], errors="coerce").fillna(0.0)
    pivot = raw.pivot_table(index="timestamp", columns="instrument", values="target_weight", aggfunc="last").fillna(0.0)
    for asset in ["SPY", "QQQ", "BIL"]:
        if asset not in pivot.columns:
            pivot[asset] = 0.0
    pivot = pivot[["SPY", "QQQ", "BIL"]].sort_index()
    pivot["equity_total_weight"] = pivot[["SPY", "QQQ", "BIL"]].sum(axis=1)
    bad = pivot[(pivot["equity_total_weight"] - 1.0).abs() > 1e-6]
    if not bad.empty:
        raise ValueError(f"Equity target book accounting failed for {len(bad)} rows. Example total={bad['equity_total_weight'].iloc[0]}")
    return pivot[["SPY", "QQQ", "BIL"]]


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
    out["CRYPTO_CASH"] = pd.to_numeric(df["crypto_cash_or_risk_off_weight"], errors="coerce").fillna(0.0) if "crypto_cash_or_risk_off_weight" in df.columns else 1.0 - out["BTC"] - out["ETH"]
    out["crypto_source_status"] = df.get("source_status", pd.Series("unknown", index=df.index)).astype(str)
    out["crypto_total_weight"] = out[["BTC", "ETH", "CRYPTO_CASH"]].sum(axis=1)
    bad = out[(out["crypto_total_weight"] - 1.0).abs() > 1e-6]
    if not bad.empty:
        raise ValueError(f"Crypto target accounting failed for {len(bad)} rows. Example total={bad['crypto_total_weight'].iloc[0]}")
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
    out["total_accounted_weight"] = out[ALL_WEIGHTS].sum(axis=1)
    out["accounting_error"] = out["total_accounted_weight"] - 1.0
    out["accounting_ok"] = out["accounting_error"].abs() <= tol
    out["crypto_source_status"] = c["crypto_source_status"].astype(str)
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
    max_days = 0.0
    start = None
    for ts, flag in (dd < 0).items():
        if flag and start is None:
            start = ts
        elif not flag and start is not None:
            max_days = max(max_days, (ts - start).total_seconds() / 86400.0)
            start = None
    if start is not None:
        max_days = max(max_days, (eq.index[-1] - start).total_seconds() / 86400.0)
    return {"total_return_pct": total * 100.0, "cagr_pct": cagr * 100.0, "max_drawdown_pct": max_dd * 100.0, "sharpe": sharpe, "sortino": sortino, "calmar": calmar, "ann_vol_pct": ann_vol * 100.0, "worst_90d_return_pct": worst_90 * 100.0, "worst_180d_return_pct": worst_180 * 100.0, "max_time_underwater_days": max_days}


def _drift_weights(weights: pd.Series, returns: pd.Series) -> pd.Series:
    growth = weights.copy()
    for asset in ASSETS:
        growth[asset] = weights[asset] * (1.0 + float(returns[asset]))
    growth["CASH"] = weights["CASH"]
    total = float(growth.sum())
    if total <= 0:
        raise ValueError("Portfolio weight drift produced non-positive total")
    return growth / total


def _trade_cost(asset: str, dw: float, nav: float, px: pd.DataFrame, atr: pd.DataFrame, ts: pd.Timestamp, equity_slip_bps: float, equity_commission_bps: float, crypto_config: ExecutionConfig) -> dict[str, Any]:
    notional = abs(dw) * nav
    direction = "BUY" if dw > 0 else "SELL"
    if asset in ["BTC", "ETH"]:
        fill = compute_fill(float(px.loc[ts, asset]), notional, nav, float(atr.loc[ts, asset]), direction, crypto_config)
        return {"cost_usd": fill.total_cost_usd, "cost_bps": fill.cost_bps, "fee_usd": fill.fee_usd, "slippage_usd": fill.slippage_usd, "spread_usd": fill.spread_usd}
    cost_bps = equity_slip_bps + equity_commission_bps
    return {"cost_usd": notional * cost_bps / 10_000.0, "cost_bps": cost_bps, "fee_usd": notional * equity_commission_bps / 10_000.0, "slippage_usd": notional * equity_slip_bps / 10_000.0, "spread_usd": 0.0}


def _run_backtest(targets: pd.DataFrame, prices: dict[str, pd.DataFrame], capital: float, equity_slip_bps: float, equity_commission_bps: float, crypto_config: ExecutionConfig, rebalance_threshold_bps: float, charge_initial_costs: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    price_close = pd.DataFrame({asset: df["close"] for asset, df in prices.items()}).sort_index().ffill()
    atr_pct = pd.DataFrame({asset: df["atr_pct"] for asset, df in prices.items()}).sort_index().ffill().fillna(0.0)
    idx = targets.index.intersection(price_close.index).sort_values()
    if len(idx) < 2:
        raise ValueError("Insufficient overlapping dates between targets and price data")
    target = targets.reindex(idx)[ALL_WEIGHTS].fillna(0.0)
    px = price_close.reindex(idx).ffill()
    atr = atr_pct.reindex(idx).ffill().fillna(0.0)
    nav_gross = capital
    nav_net = capital
    current_w_gross = target.iloc[0].copy()
    current_w_net = target.iloc[0].copy()
    trades: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    initial_cost_usd = 0.0
    if charge_initial_costs:
        for asset in ASSETS:
            dw = float(current_w_net[asset])
            if abs(dw) <= 1e-12:
                continue
            cost = _trade_cost(asset, dw, nav_net, px, atr, idx[0], equity_slip_bps, equity_commission_bps, crypto_config)
            nav_net -= cost["cost_usd"]
            initial_cost_usd += cost["cost_usd"]
            trades.append({"timestamp": idx[0], "trade_type": "initial_allocation", "asset": asset, "direction": "BUY", "delta_weight": dw, "notional_usd": abs(dw) * nav_net, **cost, "nav_after_cost": nav_net})
    threshold = rebalance_threshold_bps / 10_000.0
    for i, ts in enumerate(idx):
        if i > 0:
            prev_ts = idx[i - 1]
            asset_rets = px.loc[ts, ASSETS] / px.loc[prev_ts, ASSETS] - 1.0
            gross_ret = float((current_w_gross[ASSETS] * asset_rets).sum())
            net_ret = float((current_w_net[ASSETS] * asset_rets).sum())
            nav_gross *= 1.0 + gross_ret
            nav_net *= 1.0 + net_ret
            current_w_gross = _drift_weights(current_w_gross, asset_rets)
            current_w_net = _drift_weights(current_w_net, asset_rets)
        desired = target.loc[ts]
        gross_delta = desired - current_w_gross
        net_delta = desired - current_w_net
        gross_turnover = float(gross_delta.abs().sum())
        net_turnover = float(net_delta.abs().sum())
        rebalance_triggered = net_turnover >= threshold
        day_cost = 0.0
        executed_turnover = 0.0
        if rebalance_triggered:
            for asset in ASSETS:
                dw = float(net_delta[asset])
                if abs(dw) <= 1e-12:
                    continue
                cost = _trade_cost(asset, dw, nav_net, px, atr, ts, equity_slip_bps, equity_commission_bps, crypto_config)
                notional = abs(dw) * nav_net
                nav_net -= cost["cost_usd"]
                day_cost += cost["cost_usd"]
                executed_turnover += abs(dw)
                trades.append({"timestamp": ts, "trade_type": "rebalance", "asset": asset, "direction": "BUY" if dw > 0 else "SELL", "delta_weight": dw, "notional_usd": notional, **cost, "nav_after_cost": nav_net})
            current_w_gross = desired.copy()
            current_w_net = desired.copy()
        rows.append({"timestamp": ts, "gross_nav": nav_gross, "net_nav": nav_net, "daily_cost_usd": day_cost, "initial_cost_usd": initial_cost_usd if i == 0 else 0.0, "rebalance_triggered": rebalance_triggered, "gross_turnover_needed": gross_turnover, "net_turnover_needed": net_turnover, "executed_turnover": executed_turnover, **{f"target_{a.lower()}_weight": float(desired[a]) for a in ALL_WEIGHTS}, **{f"actual_{a.lower()}_weight": float(current_w_net[a]) for a in ALL_WEIGHTS}})
    curves = pd.DataFrame(rows).set_index("timestamp")
    trades_df = pd.DataFrame(trades)
    summary_rows = [{"series": label, **_perf(curves[col])} for label, col in [("gross_before_costs", "gross_nav"), ("net_after_costs", "net_nav")]]
    total_cost = float(curves["daily_cost_usd"].sum() + curves["initial_cost_usd"].sum())
    rebalance_cost = float(curves["daily_cost_usd"].sum())
    summary_rows.append({"series": "cost_summary", "total_cost_usd": total_cost, "initial_cost_usd": float(curves["initial_cost_usd"].sum()), "rebalance_cost_usd": rebalance_cost, "total_cost_pct_start_nav": total_cost / capital * 100.0, "avg_daily_turnover_needed_pct": float(curves["net_turnover_needed"].mean() * 100.0), "avg_executed_turnover_pct": float(curves["executed_turnover"].mean() * 100.0), "total_executed_turnover": float(curves["executed_turnover"].sum()), "rebalance_count": int(curves["rebalance_triggered"].sum())})
    return curves, trades_df, pd.DataFrame(summary_rows)


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if max_rows is not None:
        df = df.head(max_rows)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = [f"{row[c]:.6f}" if isinstance(row[c], float) else str(row[c]).replace("|", "\\|") for c in df.columns]
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
        bad = targets.loc[~targets["accounting_ok"], ALL_WEIGHTS + ["total_accounted_weight", "accounting_error"]].head(5)
        raise SystemExit("Fail-closed: unified target accounting is not 100% valid\n" + bad.to_string())
    prices = {"BTC": _read_price(Path(args.btc_data), "BTC"), "ETH": _read_price(Path(args.eth_data), "ETH"), "SPY": _read_price(Path(args.spy_data), "SPY"), "QQQ": _read_price(Path(args.qqq_data), "QQQ"), "BIL": _read_price(Path(args.bil_data), "BIL")}
    crypto_config = ExecutionConfig.from_env()
    curves, trades, summary = _run_backtest(targets, prices, args.capital, args.equity_slippage_bps, args.equity_commission_bps, crypto_config, args.rebalance_threshold_bps, args.charge_initial_costs)
    targets.to_csv(out_dir / "unified_fund_targets.csv")
    curves.to_csv(out_dir / "unified_fund_curves.csv")
    trades.to_csv(out_dir / "unified_fund_trade_costs.csv", index=False)
    summary.to_csv(out_dir / "unified_fund_backtest_summary.csv", index=False)
    payload = {"research_status": "research_only_unified_fund_backtest_v1", "crypto_cost_model": crypto_config.__dict__, "equity_cost_model": {"equity_slippage_bps": args.equity_slippage_bps, "equity_commission_bps": args.equity_commission_bps}, "execution_policy": {"rebalance_threshold_bps": args.rebalance_threshold_bps, "charge_initial_costs": args.charge_initial_costs}, "inputs": vars(args), "outputs": {"targets": str(out_dir / "unified_fund_targets.csv"), "curves": str(out_dir / "unified_fund_curves.csv"), "trades": str(out_dir / "unified_fund_trade_costs.csv"), "summary": str(out_dir / "unified_fund_backtest_summary.csv"), "summary_md": str(out_dir / "summary.md"), "summary_json": str(out_dir / "summary.json")}, "guardrails": {"research_only": True, "broker_ready": False, "generates_orders": False, "mutates_target_book": False}}
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (out_dir / "summary.md").write_text("\n".join(["# Fund Unified Backtest v1", "", "Research-only unified crypto + equity MR overlay backtest, net of modeled costs.", "", "## Execution Policy", "", "```text", f"Rebalance threshold bps: {args.rebalance_threshold_bps}", f"Charge initial costs: {args.charge_initial_costs}", f"Crypto ExecutionConfig: {crypto_config}", f"Equity slippage bps: {args.equity_slippage_bps}", f"Equity commission bps: {args.equity_commission_bps}", "```", "", "## Summary", "", _md_table(summary), "", "## Guardrail", "", "```text", "Research only. No target-book mutation, live trading, broker integration, paper-broker execution, order generation, runtime deployment, or dynamic allocator changes are approved.", "```", ""]), encoding="utf-8")
    with pd.option_context("display.max_columns", None, "display.width", 900, "display.float_format", "{:.6f}".format):
        print("\n=== FUND UNIFIED BACKTEST V1 ===")
        print("\nExecution/cost assumptions:")
        print(f"Rebalance threshold bps: {args.rebalance_threshold_bps}")
        print(f"Charge initial costs: {args.charge_initial_costs}")
        print(f"Crypto: {crypto_config}")
        print(f"Equity: slippage_bps={args.equity_slippage_bps}, commission_bps={args.equity_commission_bps}")
        print("\nSummary:")
        print(summary.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
