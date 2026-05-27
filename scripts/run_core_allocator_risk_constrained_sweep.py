#!/usr/bin/env python
"""Run risk-constrained structural core allocator sweeps.

This script extends the core allocator research track from "find a return engine"
toward "shape the return engine into a better risk engine".

It tests volatility-targeted, trend-gated, and drawdown-throttled structural
allocators with explicit controls for:

- target volatility
- max gross exposure
- max crypto allocation
- max single-asset allocation
- drawdown throttle
- monthly loss throttle
- crash-state throttle
- weekly/monthly rebalance cadence

Primary goal:

    Improve OOS Sharpe and Calmar while keeping drawdowns closer to fund-grade.

Research only. No broker/runtime/live execution code is modified.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict
from itertools import product
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
    base_weights: dict[str, float]
    ma_days: int
    vol_target_ann: float
    vol_lookback_days: int
    max_gross: float
    max_crypto: float
    max_asset: float
    drawdown_throttle: float
    drawdown_cut: float
    monthly_loss_throttle: float
    monthly_loss_cut: float
    crash_ma_days: int
    crash_cut: float
    defensive_cash_weight: float


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _dateify(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.tz_localize(None)


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {str(c).lower().strip(): c for c in df.columns}
    for c in candidates:
        if c.lower() in cols:
            return cols[c.lower()]
    return None


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


def _candidate_paths(data_dir: Path, ticker: str) -> list[Path]:
    safe = ticker.replace("/", "_")
    names = [
        f"{safe}.csv", f"{safe}_daily.csv", f"{safe}_1d.csv", f"{safe}_prices.csv", f"{safe}_history.csv",
        f"{safe.lower()}.csv", f"{safe.lower()}_daily.csv", f"{safe.lower()}_1d.csv", f"{safe.lower()}_prices.csv", f"{safe.lower()}_history.csv",
    ]
    paths = [data_dir / n for n in names]
    paths.extend(sorted(data_dir.glob(f"**/{safe}.csv")))
    paths.extend(sorted(data_dir.glob(f"**/{safe}_*.csv")))
    paths.extend(sorted(data_dir.glob(f"**/{safe.lower()}.csv")))
    paths.extend(sorted(data_dir.glob(f"**/{safe.lower()}_*.csv")))
    out: list[Path] = []
    seen: set[Path] = set()
    for p in paths:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out


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
        raise SystemExit(f"No price data found in {data_dir}")
    prices = pd.concat(series, axis=1).sort_index().ffill().dropna(how="all")
    if missing:
        print(f"Warning: missing price data for: {', '.join(missing)}")
    return prices.dropna()


def _normalize(weights: dict[str, float], available: list[str]) -> dict[str, float]:
    filt = {k: float(v) for k, v in weights.items() if k in available and float(v) > 0}
    total = sum(filt.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in filt.items()}


def _cap_and_normalize_row(row: pd.Series, max_asset: float, max_crypto: float, max_gross: float) -> pd.Series:
    w = row.clip(lower=0.0).copy()
    if w.sum() <= 0:
        return w
    w = w / w.sum()
    if max_asset > 0:
        for _ in range(8):
            over = w > max_asset
            if not over.any():
                break
            excess = float((w[over] - max_asset).sum())
            w[over] = max_asset
            under = w < max_asset
            under_sum = float(w[under].sum())
            if under_sum <= 0 or excess <= 0:
                break
            w[under] += excess * (w[under] / under_sum)
    crypto_cols = [c for c in w.index if c in CRYPTO_ASSETS]
    crypto_sum = float(w[crypto_cols].sum()) if crypto_cols else 0.0
    if crypto_sum > max_crypto and crypto_sum > 0:
        scale = max_crypto / crypto_sum
        freed = crypto_sum - max_crypto
        w[crypto_cols] *= scale
        non_crypto = [c for c in w.index if c not in crypto_cols]
        non_crypto_sum = float(w[non_crypto].sum()) if non_crypto else 0.0
        if non_crypto and non_crypto_sum > 0:
            w[non_crypto] += freed * (w[non_crypto] / non_crypto_sum)
    total = float(w.sum())
    if total > 0:
        w = w / total * min(max_gross, 1.0)
    return w.fillna(0.0)


def _base_weight_frame(prices: pd.DataFrame, spec: PolicySpec) -> pd.DataFrame:
    returns = prices.pct_change().fillna(0.0)
    weights = _normalize(spec.base_weights, list(prices.columns))
    base = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    for asset, weight in weights.items():
        base[asset] = weight

    ma = prices.rolling(spec.ma_days, min_periods=max(20, spec.ma_days // 4)).mean()
    risk_on = prices > ma
    trend_w = base.where(risk_on, 0.0)

    # When primary risk assets are mostly off, permit a small defensive sleeve rather than forcing full cash.
    defensive_cols = [c for c in trend_w.columns if c in DEFENSIVE_ASSETS]
    if defensive_cols and spec.defensive_cash_weight > 0:
        gross = trend_w.sum(axis=1)
        weak = gross < 0.25
        for c in defensive_cols:
            trend_w.loc[weak, c] = trend_w.loc[weak, c] + spec.defensive_cash_weight / len(defensive_cols)

    trend_w = trend_w.apply(lambda r: _cap_and_normalize_row(r, spec.max_asset, spec.max_crypto, spec.max_gross), axis=1)

    provisional = (trend_w.shift(1).fillna(0.0) * returns).sum(axis=1)
    realized_vol = provisional.rolling(spec.vol_lookback_days, min_periods=max(20, spec.vol_lookback_days // 2)).std() * math.sqrt(TRADING_DAYS)
    scale = (spec.vol_target_ann / realized_vol).clip(lower=0.0, upper=spec.max_gross).replace([float("inf"), float("-inf")], pd.NA).fillna(0.0)
    vol_w = trend_w.mul(scale, axis=0)
    vol_w = vol_w.apply(lambda r: _cap_and_normalize_row(r, spec.max_asset, spec.max_crypto, min(spec.max_gross, float(r.sum()) if float(r.sum()) > 0 else spec.max_gross)), axis=1)
    return vol_w.fillna(0.0)


def _apply_path_risk_controls(raw_w: pd.DataFrame, returns: pd.DataFrame, prices: pd.DataFrame, spec: PolicySpec) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    w = raw_w.copy()
    provisional = (w.shift(1).fillna(0.0) * returns).sum(axis=1)
    provisional_equity = (1.0 + provisional).cumprod()
    dd = provisional_equity / provisional_equity.cummax() - 1.0

    throttle = pd.Series(1.0, index=w.index)
    if spec.drawdown_throttle > 0:
        throttle.loc[dd <= -abs(spec.drawdown_throttle)] *= spec.drawdown_cut

    month_start = provisional_equity.groupby(provisional_equity.index.to_period("M")).transform("first")
    mtd = provisional_equity / month_start - 1.0
    if spec.monthly_loss_throttle > 0:
        throttle.loc[mtd <= -abs(spec.monthly_loss_throttle)] *= spec.monthly_loss_cut

    if "BTC-USD" in prices.columns and spec.crash_ma_days > 0:
        btc_ma = prices["BTC-USD"].rolling(spec.crash_ma_days, min_periods=max(20, spec.crash_ma_days // 4)).mean()
        btc_crash = prices["BTC-USD"] < btc_ma
        high_crypto = w[[c for c in w.columns if c in CRYPTO_ASSETS]].sum(axis=1) > 0.05
        throttle.loc[btc_crash & high_crypto] *= spec.crash_cut

    w = w.mul(throttle.clip(lower=0.0, upper=1.0), axis=0).fillna(0.0)
    return w, dd, throttle


def _metrics(equity: pd.Series, capital: float) -> dict[str, float]:
    equity = pd.to_numeric(equity, errors="coerce").dropna()
    if equity.empty:
        return {}
    rets = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    final = float(equity.iloc[-1])
    days = max((equity.index[-1] - equity.index[0]).days, 1) if isinstance(equity.index, pd.DatetimeIndex) else max(len(equity), 1)
    years = max(days / 365.25, 1 / 365.25)
    ret_pct = (final / capital - 1.0) * 100.0
    cagr_pct = ((final / capital) ** (1.0 / years) - 1.0) * 100.0 if final > 0 else float("nan")
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


def _resample_weights(raw_w: pd.DataFrame, rebalance: str) -> pd.DataFrame:
    if rebalance.lower() == "daily":
        return raw_w
    return raw_w.resample(rebalance).last().reindex(raw_w.index).ffill().fillna(0.0)


def _run_policy(spec: PolicySpec, prices: pd.DataFrame, capital: float, fee_bps: float, rebalance: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    returns = prices.pct_change().fillna(0.0)
    raw_w = _base_weight_frame(prices, spec)
    raw_w, provisional_dd, throttle = _apply_path_risk_controls(raw_w, returns, prices, spec)
    raw_w = _resample_weights(raw_w, rebalance)

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
        "crypto_exposure": raw_w[[c for c in raw_w.columns if c in CRYPTO_ASSETS]].sum(axis=1).values if any(c in CRYPTO_ASSETS for c in raw_w.columns) else 0.0,
        "throttle": throttle.values,
        "provisional_drawdown": provisional_dd.values,
    })
    weights = raw_w.copy()
    weights.insert(0, "date", raw_w.index)
    weights.insert(1, "policy", spec.name)

    row = _metrics(equity, capital)
    row.update({
        "policy": spec.name,
        "vol_target_ann": spec.vol_target_ann,
        "ma_days": spec.ma_days,
        "vol_lookback_days": spec.vol_lookback_days,
        "max_gross": spec.max_gross,
        "max_crypto": spec.max_crypto,
        "max_asset": spec.max_asset,
        "drawdown_throttle": spec.drawdown_throttle,
        "drawdown_cut": spec.drawdown_cut,
        "monthly_loss_throttle": spec.monthly_loss_throttle,
        "monthly_loss_cut": spec.monthly_loss_cut,
        "crash_ma_days": spec.crash_ma_days,
        "crash_cut": spec.crash_cut,
        "defensive_cash_weight": spec.defensive_cash_weight,
        "avg_gross_exposure": float(raw_w.sum(axis=1).mean()),
        "avg_crypto_exposure": float(raw_w[[c for c in raw_w.columns if c in CRYPTO_ASSETS]].sum(axis=1).mean()) if any(c in CRYPTO_ASSETS for c in raw_w.columns) else 0.0,
        "avg_turnover_daily": float(turnover.mean()),
        "annual_turnover": float(turnover.mean() * TRADING_DAYS),
        "total_cost_pct": float(cost.sum() * 100.0),
        "fee_bps": fee_bps,
        "rebalance": rebalance,
        "throttled_days_pct": float((throttle < 0.999).mean() * 100.0),
    })
    return daily, weights, row


def _calendar_returns(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for policy, sub in daily.groupby("policy"):
        s = sub.sort_values("date").set_index("date")["equity"]
        prior = None
        for dt, end_eq in s.resample("YE").last().dropna().items():
            if prior is None:
                ys = s[s.index.year == dt.year]
                start_eq = float(ys.iloc[0]) if not ys.empty else float(s.iloc[0])
            else:
                start_eq = float(prior)
            rows.append({"policy": policy, "year": int(dt.year), "return_pct": (float(end_eq) / start_eq - 1.0) * 100.0, "starting_equity": start_eq, "ending_equity": float(end_eq)})
            prior = float(end_eq)
    return pd.DataFrame(rows)


def _static_oos_summary(daily: pd.DataFrame, policies: list[str], capital: float, start: str, end: str) -> pd.DataFrame:
    rows = []
    for policy in policies:
        sub = daily[(daily["policy"] == policy) & (daily["date"] >= pd.Timestamp(start)) & (daily["date"] <= pd.Timestamp(end))].copy()
        if sub.empty:
            continue
        eq = sub.sort_values("date").set_index("date")["equity"]
        rows.append({"policy": policy, **_metrics(eq / float(eq.iloc[0]) * capital, capital)})
    return pd.DataFrame(rows)


def _score_row(row: dict[str, Any], min_cagr: float, max_dd: float, min_sharpe: float, min_calmar: float) -> float:
    cagr = float(row.get("cagr_pct", float("nan")))
    dd = abs(float(row.get("maxdd_pct", float("nan"))))
    sharpe = float(row.get("sharpe", float("nan")))
    calmar = float(row.get("calmar", float("nan")))
    if any(math.isnan(x) for x in [cagr, dd, sharpe, calmar]):
        return -9999.0
    score = (calmar * 100.0) + (sharpe * 25.0) + (cagr * 0.5) - max(0.0, dd - max_dd) * 5.0
    if cagr < min_cagr:
        score -= (min_cagr - cagr) * 3.0
    if sharpe < min_sharpe:
        score -= (min_sharpe - sharpe) * 50.0
    if calmar < min_calmar:
        score -= (min_calmar - calmar) * 50.0
    return score


def _build_specs(available: list[str], limit_fast: bool) -> list[PolicySpec]:
    base_balanced = _normalize({"BTC-USD": 0.30, "ETH-USD": 0.15, "QQQ": 0.25, "SPY": 0.15, "TLT": 0.075, "GLD": 0.075}, available)
    base_defensive = _normalize({"BTC-USD": 0.22, "ETH-USD": 0.08, "QQQ": 0.20, "SPY": 0.20, "TLT": 0.15, "GLD": 0.15}, available)
    base_crypto_light = _normalize({"BTC-USD": 0.20, "ETH-USD": 0.05, "QQQ": 0.30, "SPY": 0.25, "TLT": 0.10, "GLD": 0.10}, available)
    bases = [("bal", base_balanced), ("def", base_defensive), ("cl", base_crypto_light)]

    if limit_fast:
        vol_targets = [0.10, 0.12, 0.15, 0.18]
        max_cryptos = [0.25, 0.35]
        dd_throttles = [0.10, 0.15]
        monthly_throttles = [0.06]
        max_grosses = [0.75, 1.00]
        crash_cuts = [0.50]
    else:
        vol_targets = [0.08, 0.10, 0.12, 0.15, 0.18, 0.22]
        max_cryptos = [0.20, 0.25, 0.35, 0.45]
        dd_throttles = [0.08, 0.10, 0.15, 0.20]
        monthly_throttles = [0.04, 0.06, 0.08]
        max_grosses = [0.60, 0.75, 0.90, 1.00]
        crash_cuts = [0.35, 0.50, 0.70]

    specs: list[PolicySpec] = []
    for (base_name, base), vol, mc, dd, ml, mg, cc in product(bases, vol_targets, max_cryptos, dd_throttles, monthly_throttles, max_grosses, crash_cuts):
        if not base:
            continue
        name = f"rc_{base_name}_vol{int(vol*100):02d}_mc{int(mc*100):02d}_mg{int(mg*100):02d}_dd{int(dd*100):02d}_ml{int(ml*100):02d}_cc{int(cc*100):02d}"
        specs.append(PolicySpec(
            name=name,
            base_weights=base,
            ma_days=200,
            vol_target_ann=vol,
            vol_lookback_days=60,
            max_gross=mg,
            max_crypto=mc,
            max_asset=0.35,
            drawdown_throttle=dd,
            drawdown_cut=0.50,
            monthly_loss_throttle=ml,
            monthly_loss_cut=0.50,
            crash_ma_days=200,
            crash_cut=cc,
            defensive_cash_weight=0.20,
        ))
    return specs


def _print_summary(summary: pd.DataFrame, title: str, top_n: int) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print(f"  {title}")
    print("=" * DISPLAY_WIDTH)
    if summary.empty:
        print("  No rows.")
        return
    view = summary.head(top_n)
    print(f"  {'Policy':<58} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Calmar':>8} {'Vol':>8} {'AvgExp':>8} {'AvgCrypto':>10} {'Thr%':>7} {'FinalEq':>12}")
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('policy')):<58} {_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
            f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('calmar'), 3):>8} {_fmt(r.get('ann_vol_pct')):>8} "
            f"{_fmt(r.get('avg_gross_exposure')):>8} {_fmt(r.get('avg_crypto_exposure')):>10} {_fmt(r.get('throttled_days_pct')):>7} {_money(r.get('final_equity')):>12}"
        )
    print("=" * DISPLAY_WIDTH)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run risk-constrained core allocator sweep")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--assets", nargs="+", default=DEFAULT_ASSETS)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--oos-start", default="2021-01-01")
    p.add_argument("--oos-end", default="2024-12-31")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fee-bps", type=float, default=2.0)
    p.add_argument("--rebalance", default="W-FRI")
    p.add_argument("--out-dir", default="artifacts/core_allocator_risk_constrained_sweep")
    p.add_argument("--fast", action="store_true", help="Use smaller parameter grid")
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--target-maxdd", type=float, default=25.0)
    p.add_argument("--target-min-cagr", type=float, default=12.0)
    p.add_argument("--target-min-sharpe", type=float, default=1.0)
    p.add_argument("--target-min-calmar", type=float, default=0.9)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prices = _load_prices(Path(args.data_dir), args.assets)
    prices = prices[(prices.index >= pd.Timestamp(args.start)) & (prices.index <= pd.Timestamp(args.end))].ffill().dropna()
    if prices.empty:
        raise SystemExit("No aligned price data after filtering.")

    specs = _build_specs(list(prices.columns), args.fast)
    daily_parts: list[pd.DataFrame] = []
    weight_parts: list[pd.DataFrame] = []
    rows: list[dict[str, Any]] = []

    print(f"Running {len(specs)} risk-constrained policies...")
    for i, spec in enumerate(specs, start=1):
        daily, weights, row = _run_policy(spec, prices, args.capital, args.fee_bps, args.rebalance)
        row["risk_score"] = _score_row(row, args.target_min_cagr, args.target_maxdd, args.target_min_sharpe, args.target_min_calmar)
        daily_parts.append(daily)
        weight_parts.append(weights)
        rows.append(row)
        if i % 100 == 0:
            print(f"  completed {i}/{len(specs)}")

    daily_df = pd.concat(daily_parts, ignore_index=True) if daily_parts else pd.DataFrame()
    weights_df = pd.concat(weight_parts, ignore_index=True) if weight_parts else pd.DataFrame()
    summary = pd.DataFrame(rows)
    summary = summary.sort_values(["risk_score", "calmar", "sharpe", "cagr_pct"], ascending=[False, False, False, False])
    top_policies = summary.head(args.top_n)["policy"].astype(str).tolist()
    top_daily = daily_df[daily_df["policy"].isin(top_policies)].copy()
    top_weights = weights_df[weights_df["policy"].isin(top_policies)].copy()
    annual = _calendar_returns(top_daily)
    oos = _static_oos_summary(top_daily, top_policies, args.capital, args.oos_start, args.oos_end)
    oos = oos.merge(summary[["policy", "risk_score", "avg_gross_exposure", "avg_crypto_exposure", "throttled_days_pct"]], on="policy", how="left")
    oos = oos.sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])

    constraints = summary[
        (summary["cagr_pct"] >= args.target_min_cagr)
        & (summary["maxdd_pct"].abs() <= args.target_maxdd)
        & (summary["sharpe"] >= args.target_min_sharpe)
        & (summary["calmar"] >= args.target_min_calmar)
    ].copy()

    summary.to_csv(out_dir / "risk_constrained_policy_summary.csv", index=False)
    constraints.to_csv(out_dir / "risk_constrained_policy_constraints_pass.csv", index=False)
    oos.to_csv(out_dir / "risk_constrained_policy_oos_summary.csv", index=False)
    annual.to_csv(out_dir / "risk_constrained_policy_annual_returns_top.csv", index=False)
    top_daily.to_csv(out_dir / "risk_constrained_policy_daily_equity_top.csv", index=False)
    top_weights.to_csv(out_dir / "risk_constrained_policy_daily_weights_top.csv", index=False)
    (out_dir / "risk_constrained_sweep_summary.json").write_text(json.dumps({
        "assets_used": list(prices.columns),
        "start": args.start,
        "end": args.end,
        "oos_start": args.oos_start,
        "oos_end": args.oos_end,
        "policies_tested": len(specs),
        "constraints": {
            "target_maxdd": args.target_maxdd,
            "target_min_cagr": args.target_min_cagr,
            "target_min_sharpe": args.target_min_sharpe,
            "target_min_calmar": args.target_min_calmar,
        },
        "outputs": {
            "summary": str(out_dir / "risk_constrained_policy_summary.csv"),
            "constraints_pass": str(out_dir / "risk_constrained_policy_constraints_pass.csv"),
            "oos_summary": str(out_dir / "risk_constrained_policy_oos_summary.csv"),
            "annual_returns_top": str(out_dir / "risk_constrained_policy_annual_returns_top.csv"),
            "daily_equity_top": str(out_dir / "risk_constrained_policy_daily_equity_top.csv"),
            "daily_weights_top": str(out_dir / "risk_constrained_policy_daily_weights_top.csv"),
        },
    }, indent=2), encoding="utf-8")

    _print_summary(summary, "RISK-CONSTRAINED CORE ALLOCATOR SWEEP — FULL PERIOD TOP", args.top_n)
    _print_summary(oos, "RISK-CONSTRAINED CORE ALLOCATOR SWEEP — STATIC OOS TOP", min(args.top_n, len(oos)))
    print(f"  Constraint pass count: {len(constraints)} / {len(summary)}")
    print(f"  Assets used: {', '.join(prices.columns)}")
    print(f"  Outputs: {out_dir}")
    print("  Verdict: RISK-CONSTRAINED CORE RESEARCH ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
