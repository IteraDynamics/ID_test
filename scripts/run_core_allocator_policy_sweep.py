#!/usr/bin/env python
"""Run first-pass structural core allocator policy sweeps.

This is the start of the Core Allocator research track. It is intentionally
separate from tactical trade-entry research.

The script reads daily close data for a configurable universe, builds portfolio
policies, and compares:

- equal-weight / static structural portfolios
- trend-gated portfolios
- volatility-targeted trend portfolios
- relative-momentum rotation portfolios
- defensive-overlay portfolios

The goal is to determine whether structural allocation can become the durable
compounding engine, with tactical sleeves acting as satellites.

Research only. No broker/runtime/live execution code is modified.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

TRADING_DAYS = 252.0
DISPLAY_WIDTH = 190

DEFAULT_ASSETS = ["BTC-USD", "ETH-USD", "QQQ", "SPY", "TLT", "GLD"]
CRYPTO_ASSETS = {"BTC-USD", "ETH-USD"}
DEFENSIVE_ASSETS = {"TLT", "GLD"}


@dataclass(frozen=True)
class PolicySpec:
    name: str
    kind: str
    weights: dict[str, float]
    ma_days: int = 200
    vol_target_ann: float = 0.18
    vol_lookback_days: int = 60
    max_leverage: float = 1.0
    momentum_lookback_days: int = 126
    top_n: int = 2
    defensive_weight: float = 0.25


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        v = float(value)
        if math.isnan(v):
            return "n/a"
        return f"{v:.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "$n/a"


def _dateify(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.tz_localize(None)


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {str(c).lower().strip(): c for c in df.columns}
    for c in candidates:
        if c.lower() in cols:
            return cols[c.lower()]
    return None


def _candidate_paths(data_dir: Path, ticker: str) -> list[Path]:
    safe = ticker.replace("/", "_")
    names = [
        f"{safe}.csv",
        f"{safe}_daily.csv",
        f"{safe}_1d.csv",
        f"{safe}_prices.csv",
        f"{safe}_history.csv",
        f"{safe.lower()}.csv",
        f"{safe.lower()}_daily.csv",
        f"{safe.lower()}_1d.csv",
        f"{safe.lower()}_prices.csv",
        f"{safe.lower()}_history.csv",
    ]
    paths = [data_dir / n for n in names]
    paths.extend(sorted(data_dir.glob(f"**/{safe}.csv")))
    paths.extend(sorted(data_dir.glob(f"**/{safe}_*.csv")))
    paths.extend(sorted(data_dir.glob(f"**/{safe.lower()}.csv")))
    paths.extend(sorted(data_dir.glob(f"**/{safe.lower()}_*.csv")))
    seen: set[Path] = set()
    uniq = []
    for p in paths:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def _load_price_series(data_dir: Path, ticker: str) -> pd.Series:
    for path in _candidate_paths(data_dir, ticker):
        if not path.exists() or path.stat().st_size == 0:
            continue
        df = _read_csv(path)
        if df.empty:
            continue
        date_col = _find_col(df, ["date", "dt", "timestamp", "time", "datetime"])
        close_col = _find_col(df, ["close", "adj_close", "adj close", "price", "close_price"])
        if date_col is None or close_col is None:
            continue
        out = df[[date_col, close_col]].copy()
        out.columns = ["date", ticker]
        out["date"] = _dateify(out["date"])
        out[ticker] = pd.to_numeric(out[ticker], errors="coerce")
        out = out.dropna(subset=["date", ticker]).sort_values("date").drop_duplicates("date", keep="last")
        if not out.empty:
            return out.set_index("date")[ticker]
    return pd.Series(dtype=float, name=ticker)


def _load_prices(data_dir: Path, assets: list[str]) -> pd.DataFrame:
    series = []
    missing = []
    for ticker in assets:
        s = _load_price_series(data_dir, ticker)
        if s.empty:
            missing.append(ticker)
        else:
            series.append(s.rename(ticker))
    if not series:
        raise SystemExit(f"No price series found in {data_dir}. Tried assets: {', '.join(assets)}")
    prices = pd.concat(series, axis=1).sort_index().ffill()
    prices = prices.dropna(how="all")
    if missing:
        print(f"Warning: missing price data for: {', '.join(missing)}")
    return prices


def _metrics(equity: pd.Series, capital: float) -> dict[str, float]:
    equity = pd.to_numeric(equity, errors="coerce").dropna()
    if equity.empty:
        return {}
    rets = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    final = float(equity.iloc[-1])
    days = max((equity.index[-1] - equity.index[0]).days, 1) if isinstance(equity.index, pd.DatetimeIndex) else max(len(equity), 1)
    years = max(days / 365.25, 1.0 / 365.25)
    ret_pct = (final / capital - 1.0) * 100.0
    cagr_pct = ((final / capital) ** (1.0 / years) - 1.0) * 100.0 if final > 0 and capital > 0 else float("nan")
    dd = equity / equity.cummax() - 1.0
    maxdd_pct = float(dd.min() * 100.0)
    vol = rets.std(ddof=0)
    sharpe = float(rets.mean() / vol * math.sqrt(TRADING_DAYS)) if len(rets) > 1 and vol > 0 else float("nan")
    downside = rets[rets < 0]
    dvol = downside.std(ddof=0)
    sortino = float(rets.mean() / dvol * math.sqrt(TRADING_DAYS)) if len(downside) > 1 and dvol > 0 else float("nan")
    calmar = cagr_pct / abs(maxdd_pct) if maxdd_pct < 0 else float("nan")
    return {
        "final_equity": final,
        "return_pct": ret_pct,
        "cagr_pct": cagr_pct,
        "maxdd_pct": maxdd_pct,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "ann_vol_pct": float(vol * math.sqrt(TRADING_DAYS) * 100.0) if len(rets) > 1 else float("nan"),
        "worst_day_pct": float(rets.min() * 100.0) if not rets.empty else float("nan"),
    }


def _normalize_weights(weights: dict[str, float], available: list[str]) -> dict[str, float]:
    filt = {k: float(v) for k, v in weights.items() if k in available and float(v) > 0}
    total = sum(filt.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in filt.items()}


def _base_specs(available: list[str]) -> list[PolicySpec]:
    crypto = [a for a in ["BTC-USD", "ETH-USD"] if a in available]
    risk = [a for a in ["BTC-USD", "ETH-USD", "QQQ", "SPY"] if a in available]
    all_assets = available
    static_balanced = _normalize_weights({"BTC-USD": 0.30, "ETH-USD": 0.15, "QQQ": 0.25, "SPY": 0.15, "TLT": 0.075, "GLD": 0.075}, available)
    static_crypto_growth = _normalize_weights({"BTC-USD": 0.40, "ETH-USD": 0.20, "QQQ": 0.25, "SPY": 0.15}, available)
    static_defensive = _normalize_weights({"BTC-USD": 0.25, "ETH-USD": 0.10, "QQQ": 0.20, "SPY": 0.20, "TLT": 0.125, "GLD": 0.125}, available)
    specs = [
        PolicySpec("static_balanced_core", "static", static_balanced),
        PolicySpec("static_crypto_growth", "static", static_crypto_growth),
        PolicySpec("static_defensive_core", "static", static_defensive),
        PolicySpec("trend_gated_balanced_ma200", "trend_gated", static_balanced, ma_days=200),
        PolicySpec("trend_gated_crypto_growth_ma200", "trend_gated", static_crypto_growth, ma_days=200),
        PolicySpec("trend_gated_balanced_ma120", "trend_gated", static_balanced, ma_days=120),
        PolicySpec("vol_target_trend_12pct", "vol_target_trend", static_balanced, ma_days=200, vol_target_ann=0.12, vol_lookback_days=60),
        PolicySpec("vol_target_trend_18pct", "vol_target_trend", static_balanced, ma_days=200, vol_target_ann=0.18, vol_lookback_days=60),
        PolicySpec("vol_target_trend_25pct", "vol_target_trend", static_balanced, ma_days=200, vol_target_ann=0.25, vol_lookback_days=60),
        PolicySpec("relative_momentum_top2_6m", "relative_momentum", {a: 1.0 for a in all_assets}, momentum_lookback_days=126, top_n=min(2, len(all_assets))),
        PolicySpec("relative_momentum_top3_6m", "relative_momentum", {a: 1.0 for a in all_assets}, momentum_lookback_days=126, top_n=min(3, len(all_assets))),
        PolicySpec("relative_momentum_top2_12m", "relative_momentum", {a: 1.0 for a in all_assets}, momentum_lookback_days=252, top_n=min(2, len(all_assets))),
        PolicySpec("defensive_overlay_balanced", "defensive_overlay", static_balanced, ma_days=200, defensive_weight=0.30),
    ]
    if crypto:
        specs.append(PolicySpec("crypto_only_equal", "static", {a: 1.0 / len(crypto) for a in crypto}))
    if risk:
        specs.append(PolicySpec("risk_assets_equal", "static", {a: 1.0 / len(risk) for a in risk}))
    return [s for s in specs if s.weights]


def _static_weights(spec: PolicySpec, returns: pd.DataFrame) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=returns.index, columns=returns.columns)
    weights = _normalize_weights(spec.weights, list(returns.columns))
    for a, v in weights.items():
        w[a] = v
    return w


def _trend_gated_weights(spec: PolicySpec, prices: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    base = _static_weights(spec, returns)
    ma = prices.rolling(spec.ma_days, min_periods=max(20, spec.ma_days // 4)).mean()
    risk_on = prices > ma
    w = base.where(risk_on, 0.0)
    gross = w.sum(axis=1).replace(0.0, pd.NA)
    w = w.div(gross, axis=0).fillna(0.0)
    return w


def _vol_target_trend_weights(spec: PolicySpec, prices: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    trend_w = _trend_gated_weights(spec, prices, returns)
    provisional = (trend_w.shift(1).fillna(0.0) * returns).sum(axis=1)
    realized_vol = provisional.rolling(spec.vol_lookback_days, min_periods=max(20, spec.vol_lookback_days // 2)).std() * math.sqrt(TRADING_DAYS)
    scale = (spec.vol_target_ann / realized_vol).clip(lower=0.0, upper=spec.max_leverage).replace([float("inf"), float("-inf")], pd.NA).fillna(0.0)
    return trend_w.mul(scale, axis=0)


def _relative_momentum_weights(spec: PolicySpec, prices: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    mom = prices.pct_change(spec.momentum_lookback_days)
    w = pd.DataFrame(0.0, index=returns.index, columns=returns.columns)
    for dt, row in mom.iterrows():
        eligible = row.dropna().sort_values(ascending=False)
        eligible = eligible[eligible > 0]
        if eligible.empty:
            continue
        top = list(eligible.head(spec.top_n).index)
        for a in top:
            w.loc[dt, a] = 1.0 / len(top)
    return w.fillna(0.0)


def _defensive_overlay_weights(spec: PolicySpec, prices: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    base = _trend_gated_weights(spec, prices, returns)
    defensive = [a for a in returns.columns if a in DEFENSIVE_ASSETS]
    if not defensive:
        return base
    risk_gross = base.sum(axis=1)
    weak = risk_gross < 0.50
    overlay = pd.DataFrame(0.0, index=returns.index, columns=returns.columns)
    for a in defensive:
        overlay[a] = spec.defensive_weight / len(defensive)
    w = base.copy()
    w.loc[weak, :] = (base.loc[weak, :] * (1.0 - spec.defensive_weight)).add(overlay.loc[weak, :], fill_value=0.0)
    gross = w.sum(axis=1).clip(lower=0.0, upper=1.0)
    over = gross > 1.0
    if over.any():
        w.loc[over, :] = w.loc[over, :].div(gross.loc[over], axis=0)
    return w.fillna(0.0)


def _weights_for_policy(spec: PolicySpec, prices: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    if spec.kind == "static":
        return _static_weights(spec, returns)
    if spec.kind == "trend_gated":
        return _trend_gated_weights(spec, prices, returns)
    if spec.kind == "vol_target_trend":
        return _vol_target_trend_weights(spec, prices, returns)
    if spec.kind == "relative_momentum":
        return _relative_momentum_weights(spec, prices, returns)
    if spec.kind == "defensive_overlay":
        return _defensive_overlay_weights(spec, prices, returns)
    raise SystemExit(f"Unknown policy kind: {spec.kind}")


def _run_policy(spec: PolicySpec, prices: pd.DataFrame, capital: float, fee_bps: float, rebalance: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    returns = prices.pct_change().fillna(0.0)
    raw_w = _weights_for_policy(spec, prices, returns)
    if rebalance != "daily":
        sampled = raw_w.resample(rebalance).last().reindex(raw_w.index).ffill().fillna(0.0)
        raw_w = sampled
    exec_w = raw_w.shift(1).fillna(0.0)
    gross_rets = (exec_w * returns).sum(axis=1)
    turnover = raw_w.diff().abs().sum(axis=1).fillna(raw_w.abs().sum(axis=1))
    cost = turnover * (fee_bps / 10_000.0)
    net_rets = gross_rets - cost
    equity = capital * (1.0 + net_rets).cumprod()
    daily = pd.DataFrame({
        "date": prices.index,
        "policy": spec.name,
        "gross_return": gross_rets.values,
        "turnover": turnover.values,
        "cost_return": cost.values,
        "net_return": net_rets.values,
        "equity": equity.values,
        "gross_exposure": raw_w.sum(axis=1).values,
    })
    weights = raw_w.copy()
    weights.insert(0, "date", raw_w.index)
    weights.insert(1, "policy", spec.name)
    metrics = _metrics(equity, capital)
    metrics.update({
        "policy": spec.name,
        "kind": spec.kind,
        "avg_gross_exposure": float(raw_w.sum(axis=1).mean()),
        "avg_turnover_daily": float(turnover.mean()),
        "annual_turnover": float(turnover.mean() * TRADING_DAYS),
        "total_cost_pct": float(cost.sum() * 100.0),
        "fee_bps": fee_bps,
        "rebalance": rebalance,
    })
    return daily, weights, metrics


def _annual_returns(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if daily.empty:
        return pd.DataFrame()
    for policy, sub in daily.groupby("policy"):
        s = sub.sort_values("date").set_index("date")["equity"]
        year_end = s.resample("YE").last().dropna()
        prior = None
        for dt, end_eq in year_end.items():
            if prior is None:
                year_slice = s[s.index.year == dt.year]
                start_eq = float(year_slice.iloc[0]) if not year_slice.empty else float(s.iloc[0])
            else:
                start_eq = float(prior)
            rows.append({
                "policy": policy,
                "year": int(dt.year),
                "return_pct": (float(end_eq) / start_eq - 1.0) * 100.0 if start_eq else float("nan"),
                "starting_equity": start_eq,
                "ending_equity": float(end_eq),
            })
            prior = float(end_eq)
    return pd.DataFrame(rows)


def _print_summary(summary: pd.DataFrame) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print("  CORE ALLOCATOR POLICY SWEEP — SUMMARY")
    print("=" * DISPLAY_WIDTH)
    if summary.empty:
        print("  No rows.")
        return
    view = summary.sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    print(f"  {'Policy':<36} {'Kind':<20} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Calmar':>8} {'Vol':>8} {'AvgExp':>8} {'AnnTurn':>9} {'Cost%':>8} {'FinalEq':>12}")
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('policy')):<36} {str(r.get('kind')):<20} "
            f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
            f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('calmar'), 3):>8} {_fmt(r.get('ann_vol_pct')):>8} "
            f"{_fmt(r.get('avg_gross_exposure')):>8} {_fmt(r.get('annual_turnover')):>9} {_fmt(r.get('total_cost_pct')):>8} {_money(r.get('final_equity')):>12}"
        )
    print("=" * DISPLAY_WIDTH)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run core allocator policy sweep")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--assets", nargs="+", default=DEFAULT_ASSETS)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fee-bps", type=float, default=2.0, help="One-way turnover cost in bps applied to allocation turnover")
    p.add_argument("--rebalance", default="W-FRI", help="Pandas resample frequency for allocation updates; use daily for daily")
    p.add_argument("--out-dir", default="artifacts/core_allocator_policy_sweep")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prices = _load_prices(Path(args.data_dir), args.assets)
    prices = prices[(prices.index >= pd.Timestamp(args.start)) & (prices.index <= pd.Timestamp(args.end))].ffill().dropna(how="all")
    prices = prices.dropna(axis=1, how="all")
    prices = prices.dropna()
    if prices.empty:
        raise SystemExit("No usable aligned price data after date filtering.")

    available = list(prices.columns)
    specs = _base_specs(available)
    all_daily = []
    all_weights = []
    rows = []
    for spec in specs:
        daily, weights, metrics = _run_policy(spec, prices, args.capital, args.fee_bps, args.rebalance)
        all_daily.append(daily)
        all_weights.append(weights)
        rows.append(metrics)

    daily_df = pd.concat(all_daily, ignore_index=True) if all_daily else pd.DataFrame()
    weights_df = pd.concat(all_weights, ignore_index=True) if all_weights else pd.DataFrame()
    summary = pd.DataFrame(rows)
    annual = _annual_returns(daily_df)

    summary.to_csv(out_dir / "core_allocator_policy_summary.csv", index=False)
    annual.to_csv(out_dir / "core_allocator_annual_returns.csv", index=False)
    daily_df.to_csv(out_dir / "core_allocator_daily_equity.csv", index=False)
    weights_df.to_csv(out_dir / "core_allocator_daily_weights.csv", index=False)
    (out_dir / "core_allocator_policy_sweep_summary.json").write_text(json.dumps({
        "assets_requested": args.assets,
        "assets_used": available,
        "start": args.start,
        "end": args.end,
        "capital": args.capital,
        "fee_bps": args.fee_bps,
        "rebalance": args.rebalance,
        "outputs": {
            "summary": str(out_dir / "core_allocator_policy_summary.csv"),
            "annual_returns": str(out_dir / "core_allocator_annual_returns.csv"),
            "daily_equity": str(out_dir / "core_allocator_daily_equity.csv"),
            "daily_weights": str(out_dir / "core_allocator_daily_weights.csv"),
        },
    }, indent=2), encoding="utf-8")

    _print_summary(summary)
    print(f"  Assets used: {', '.join(available)}")
    print(f"  Outputs: {out_dir}")
    print("  Verdict: CORE ALLOCATOR RESEARCH ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
