#!/usr/bin/env python
"""Run risk-contribution-aware core allocator sweeps.

This script is the next step after the blunt risk-constrained allocator sweep.
Instead of simply cutting gross exposure after drawdowns, it tries to improve the
quality of risk before losses arrive.

Core ideas:

- Use inverse-volatility scaling inside the structural base universe.
- Cap BTC/ETH by realized volatility contribution, not only nominal weight.
- Dynamically reduce crypto risk budget when BTC is below MA200 or BTC volatility
  is rising versus its own longer baseline.
- Redistribute freed budget to non-crypto assets and defensive assets.
- Rank by static OOS Sharpe/Calmar first, full-period metrics second.

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
class RiskContributionSpec:
    name: str
    base_weights: dict[str, float]
    ma_days: int
    vol_lookback_days: int
    long_vol_lookback_days: int
    target_vol_ann: float
    max_gross: float
    base_crypto_risk_cap: float
    stressed_crypto_risk_cap: float
    max_asset_weight: float
    min_defensive_weight: float
    crypto_trend_cut: float
    crypto_vol_rising_cut: float
    rebalance: str


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


def _metrics(equity: pd.Series, capital: float) -> dict[str, float]:
    equity = pd.to_numeric(equity, errors="coerce").dropna()
    if equity.empty:
        return {}
    rets = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    final = float(equity.iloc[-1])
    days = max((equity.index[-1] - equity.index[0]).days, 1) if isinstance(equity.index, pd.DatetimeIndex) else max(len(equity), 1)
    years = max(days / 365.25, 1 / 365.25)
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


def _cap_asset_weights(row: pd.Series, max_asset_weight: float) -> pd.Series:
    w = row.clip(lower=0.0).copy()
    total = float(w.sum())
    if total <= 0:
        return w
    w = w / total
    if max_asset_weight <= 0:
        return w
    for _ in range(12):
        over = w > max_asset_weight
        if not over.any():
            break
        excess = float((w[over] - max_asset_weight).sum())
        w[over] = max_asset_weight
        under = w < max_asset_weight
        under_sum = float(w[under].sum())
        if excess <= 0 or under_sum <= 0:
            break
        w[under] += excess * (w[under] / under_sum)
    total = float(w.sum())
    return w / total if total > 0 else w


def _crypto_risk_share(weights: pd.Series, ann_vol: pd.Series) -> float:
    risk = (weights.abs() * ann_vol.reindex(weights.index).fillna(0.0)).clip(lower=0.0)
    total = float(risk.sum())
    if total <= 0:
        return 0.0
    crypto_cols = [c for c in weights.index if c in CRYPTO_ASSETS]
    return float(risk[crypto_cols].sum() / total) if crypto_cols else 0.0


def _cap_crypto_risk(row: pd.Series, ann_vol_row: pd.Series, crypto_cap: float) -> pd.Series:
    w = row.clip(lower=0.0).copy()
    total = float(w.sum())
    if total <= 0:
        return w
    w = w / total
    crypto_cols = [c for c in w.index if c in CRYPTO_ASSETS]
    non_crypto_cols = [c for c in w.index if c not in CRYPTO_ASSETS]
    if not crypto_cols or not non_crypto_cols:
        return w
    for _ in range(16):
        share = _crypto_risk_share(w, ann_vol_row)
        if share <= crypto_cap + 1e-6:
            break
        crypto_weight = float(w[crypto_cols].sum())
        if crypto_weight <= 0:
            break
        scale = max(0.0, crypto_cap / share)
        new_crypto = w[crypto_cols] * scale
        freed = float(w[crypto_cols].sum() - new_crypto.sum())
        w[crypto_cols] = new_crypto
        non_crypto_weight = float(w[non_crypto_cols].sum())
        if freed > 0 and non_crypto_weight > 0:
            w[non_crypto_cols] += freed * (w[non_crypto_cols] / non_crypto_weight)
        else:
            break
    total = float(w.sum())
    return w / total if total > 0 else w


def _ensure_defensive_weight(row: pd.Series, min_defensive_weight: float) -> pd.Series:
    w = row.clip(lower=0.0).copy()
    total = float(w.sum())
    if total <= 0:
        return w
    w = w / total
    defensive = [c for c in w.index if c in DEFENSIVE_ASSETS]
    if not defensive or min_defensive_weight <= 0:
        return w
    current = float(w[defensive].sum())
    if current >= min_defensive_weight:
        return w
    need = min_defensive_weight - current
    non_def = [c for c in w.index if c not in defensive]
    non_def_sum = float(w[non_def].sum()) if non_def else 0.0
    if non_def_sum <= 0:
        return w
    w[non_def] *= max(0.0, (non_def_sum - need) / non_def_sum)
    for c in defensive:
        w[c] += need / len(defensive)
    total = float(w.sum())
    return w / total if total > 0 else w


def _dynamic_crypto_cap(spec: RiskContributionSpec, prices: pd.DataFrame, ann_vol: pd.DataFrame) -> pd.Series:
    cap = pd.Series(spec.base_crypto_risk_cap, index=prices.index, dtype=float)
    if "BTC-USD" not in prices.columns:
        return cap
    btc_ma = prices["BTC-USD"].rolling(spec.ma_days, min_periods=max(20, spec.ma_days // 4)).mean()
    btc_below_ma = prices["BTC-USD"] < btc_ma
    cap.loc[btc_below_ma] = cap.loc[btc_below_ma] * spec.crypto_trend_cut

    btc_short_vol = ann_vol["BTC-USD"] if "BTC-USD" in ann_vol.columns else pd.Series(index=prices.index, dtype=float)
    btc_long_vol = prices["BTC-USD"].pct_change().rolling(spec.long_vol_lookback_days, min_periods=max(30, spec.long_vol_lookback_days // 3)).std() * math.sqrt(TRADING_DAYS)
    btc_vol_rising = btc_short_vol > btc_long_vol
    cap.loc[btc_vol_rising] = cap.loc[btc_vol_rising] * spec.crypto_vol_rising_cut
    return cap.clip(lower=spec.stressed_crypto_risk_cap, upper=spec.base_crypto_risk_cap)


def _build_weights(prices: pd.DataFrame, spec: RiskContributionSpec) -> pd.DataFrame:
    returns = prices.pct_change().fillna(0.0)
    ann_vol = returns.rolling(spec.vol_lookback_days, min_periods=max(20, spec.vol_lookback_days // 2)).std() * math.sqrt(TRADING_DAYS)
    inv_vol = 1.0 / ann_vol.replace(0.0, pd.NA)
    base = _normalize(spec.base_weights, list(prices.columns))
    base_frame = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    for asset, weight in base.items():
        base_frame[asset] = weight

    ma = prices.rolling(spec.ma_days, min_periods=max(20, spec.ma_days // 4)).mean()
    trend_on = prices > ma
    raw = base_frame.where(trend_on, 0.0)
    risk_adjusted = raw * inv_vol.reindex_like(raw).fillna(0.0)

    crypto_cap = _dynamic_crypto_cap(spec, prices, ann_vol)
    rows = []
    for dt, row in risk_adjusted.iterrows():
        w = row.copy()
        if float(w.sum()) <= 0:
            w = pd.Series(0.0, index=risk_adjusted.columns)
            defensive = [c for c in w.index if c in DEFENSIVE_ASSETS]
            if defensive:
                for c in defensive:
                    w[c] = 1.0 / len(defensive)
        w = _cap_asset_weights(w, spec.max_asset_weight)
        w = _cap_crypto_risk(w, ann_vol.loc[dt], float(crypto_cap.loc[dt]))
        w = _ensure_defensive_weight(w, spec.min_defensive_weight)
        w = _cap_asset_weights(w, spec.max_asset_weight)
        gross = float(w.sum())
        if gross > 0:
            w = w / gross * min(1.0, spec.max_gross)
        rows.append(w)
    weights = pd.DataFrame(rows, index=prices.index, columns=prices.columns).fillna(0.0)

    provisional = (weights.shift(1).fillna(0.0) * returns).sum(axis=1)
    realized_port_vol = provisional.rolling(spec.vol_lookback_days, min_periods=max(20, spec.vol_lookback_days // 2)).std() * math.sqrt(TRADING_DAYS)
    scale = (spec.target_vol_ann / realized_port_vol).clip(lower=0.0, upper=spec.max_gross).replace([float("inf"), float("-inf")], pd.NA).fillna(0.0)
    weights = weights.mul(scale, axis=0).fillna(0.0)
    weights = weights.clip(lower=0.0)
    gross = weights.sum(axis=1).replace(0.0, pd.NA)
    over = gross > spec.max_gross
    if over.any():
        weights.loc[over] = weights.loc[over].div(gross.loc[over], axis=0) * spec.max_gross
    return weights.fillna(0.0)


def _resample_weights(weights: pd.DataFrame, rebalance: str) -> pd.DataFrame:
    if rebalance.lower() == "daily":
        return weights
    return weights.resample(rebalance).last().reindex(weights.index).ffill().fillna(0.0)


def _run_policy(spec: RiskContributionSpec, prices: pd.DataFrame, capital: float, fee_bps: float) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    returns = prices.pct_change().fillna(0.0)
    weights = _build_weights(prices, spec)
    weights = _resample_weights(weights, spec.rebalance)
    exec_w = weights.shift(1).fillna(0.0)
    gross_rets = (exec_w * returns).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    cost = turnover * (fee_bps / 10_000.0)
    net_rets = gross_rets - cost
    equity = capital * (1.0 + net_rets).cumprod()
    crypto_cols = [c for c in weights.columns if c in CRYPTO_ASSETS]
    defensive_cols = [c for c in weights.columns if c in DEFENSIVE_ASSETS]
    daily = pd.DataFrame({
        "date": prices.index,
        "policy": spec.name,
        "gross_return": gross_rets.values,
        "turnover": turnover.values,
        "cost_return": cost.values,
        "net_return": net_rets.values,
        "equity": equity.values,
        "gross_exposure": weights.sum(axis=1).values,
        "crypto_exposure": weights[crypto_cols].sum(axis=1).values if crypto_cols else 0.0,
        "defensive_exposure": weights[defensive_cols].sum(axis=1).values if defensive_cols else 0.0,
    })
    weight_out = weights.copy()
    weight_out.insert(0, "date", weights.index)
    weight_out.insert(1, "policy", spec.name)

    row = _metrics(equity, capital)
    row.update(asdict(spec))
    row.update({
        "avg_gross_exposure": float(weights.sum(axis=1).mean()),
        "avg_crypto_exposure": float(weights[crypto_cols].sum(axis=1).mean()) if crypto_cols else 0.0,
        "avg_defensive_exposure": float(weights[defensive_cols].sum(axis=1).mean()) if defensive_cols else 0.0,
        "avg_turnover_daily": float(turnover.mean()),
        "annual_turnover": float(turnover.mean() * TRADING_DAYS),
        "total_cost_pct": float(cost.sum() * 100.0),
        "fee_bps": fee_bps,
    })
    return daily, weight_out, row


def _static_oos_summary(daily: pd.DataFrame, policies: list[str], capital: float, start: str, end: str) -> pd.DataFrame:
    rows = []
    for policy in policies:
        sub = daily[(daily["policy"] == policy) & (daily["date"] >= pd.Timestamp(start)) & (daily["date"] <= pd.Timestamp(end))].copy()
        if sub.empty:
            continue
        eq = sub.sort_values("date").set_index("date")["equity"]
        norm_eq = eq / float(eq.iloc[0]) * capital
        rows.append({"policy": policy, **_metrics(norm_eq, capital)})
    return pd.DataFrame(rows)


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


def _rank_score(row: pd.Series) -> float:
    oos_sharpe = float(row.get("oos_sharpe", float("nan")))
    oos_calmar = float(row.get("oos_calmar", float("nan")))
    oos_cagr = float(row.get("oos_cagr_pct", float("nan")))
    oos_dd = abs(float(row.get("oos_maxdd_pct", float("nan"))))
    full_sharpe = float(row.get("sharpe", float("nan")))
    full_calmar = float(row.get("calmar", float("nan")))
    if any(math.isnan(x) for x in [oos_sharpe, oos_calmar, oos_cagr, oos_dd, full_sharpe, full_calmar]):
        return -9999.0
    return (oos_sharpe * 35.0) + (oos_calmar * 85.0) + (oos_cagr * 0.9) + (full_sharpe * 10.0) + (full_calmar * 10.0) - max(0.0, oos_dd - 25.0) * 3.5


def _build_specs(available: list[str], fast: bool, rebalance: str) -> list[RiskContributionSpec]:
    base_balanced = _normalize({"BTC-USD": 0.30, "ETH-USD": 0.15, "QQQ": 0.25, "SPY": 0.15, "TLT": 0.075, "GLD": 0.075}, available)
    base_defensive = _normalize({"BTC-USD": 0.20, "ETH-USD": 0.08, "QQQ": 0.20, "SPY": 0.22, "TLT": 0.15, "GLD": 0.15}, available)
    base_crypto_light = _normalize({"BTC-USD": 0.16, "ETH-USD": 0.04, "QQQ": 0.30, "SPY": 0.25, "TLT": 0.12, "GLD": 0.13}, available)
    bases = [("bal", base_balanced), ("def", base_defensive), ("cl", base_crypto_light)]

    if fast:
        target_vols = [0.10, 0.12, 0.15, 0.18]
        max_grosses = [0.75, 0.90, 1.00]
        base_crypto_caps = [0.20, 0.25, 0.35]
        stressed_caps = [0.05, 0.10]
        min_defensive = [0.10, 0.20]
    else:
        target_vols = [0.08, 0.10, 0.12, 0.15, 0.18, 0.22]
        max_grosses = [0.60, 0.75, 0.90, 1.00]
        base_crypto_caps = [0.15, 0.20, 0.25, 0.35, 0.45]
        stressed_caps = [0.03, 0.05, 0.10, 0.15]
        min_defensive = [0.05, 0.10, 0.20, 0.30]

    specs: list[RiskContributionSpec] = []
    for (base_name, base), tv, mg, bcc, sc, md in product(bases, target_vols, max_grosses, base_crypto_caps, stressed_caps, min_defensive):
        if not base or sc > bcc:
            continue
        name = f"rca_{base_name}_tv{int(tv*100):02d}_mg{int(mg*100):03d}_crc{int(bcc*100):02d}_sc{int(sc*100):02d}_def{int(md*100):02d}"
        specs.append(RiskContributionSpec(
            name=name,
            base_weights=base,
            ma_days=200,
            vol_lookback_days=60,
            long_vol_lookback_days=180,
            target_vol_ann=tv,
            max_gross=mg,
            base_crypto_risk_cap=bcc,
            stressed_crypto_risk_cap=sc,
            max_asset_weight=0.35,
            min_defensive_weight=md,
            crypto_trend_cut=0.50,
            crypto_vol_rising_cut=0.60,
            rebalance=rebalance,
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
    print(f"  {'Policy':<62} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Calmar':>8} {'OOS_CAGR':>9} {'OOS_DD':>8} {'OOS_Sh':>8} {'OOS_Cal':>8} {'AvgCr':>7} {'FinalEq':>12}")
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('policy')):<62} {_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
            f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('calmar'), 3):>8} {_fmt(r.get('oos_cagr_pct')):>9} {_fmt(r.get('oos_maxdd_pct')):>8} "
            f"{_fmt(r.get('oos_sharpe'), 3):>8} {_fmt(r.get('oos_calmar'), 3):>8} {_fmt(r.get('avg_crypto_exposure')):>7} {_money(r.get('final_equity')):>12}"
        )
    print("=" * DISPLAY_WIDTH)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run risk-contribution-aware core allocator sweep")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--assets", nargs="+", default=DEFAULT_ASSETS)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--oos-start", default="2021-01-01")
    p.add_argument("--oos-end", default="2024-12-31")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fee-bps", type=float, default=2.0)
    p.add_argument("--rebalance", default="W-FRI")
    p.add_argument("--out-dir", default="artifacts/core_allocator_risk_contribution_sweep")
    p.add_argument("--fast", action="store_true")
    p.add_argument("--top-n", type=int, default=20)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prices = _load_prices(Path(args.data_dir), args.assets)
    prices = prices[(prices.index >= pd.Timestamp(args.start)) & (prices.index <= pd.Timestamp(args.end))].ffill().dropna()
    if prices.empty:
        raise SystemExit("No aligned price data after filtering.")

    specs = _build_specs(list(prices.columns), args.fast, args.rebalance)
    print(f"Running {len(specs)} risk-contribution-aware policies...")

    daily_parts: list[pd.DataFrame] = []
    weight_parts: list[pd.DataFrame] = []
    rows: list[dict[str, Any]] = []
    for i, spec in enumerate(specs, start=1):
        daily, weights, row = _run_policy(spec, prices, args.capital, args.fee_bps)
        oos_df = _static_oos_summary(daily, [spec.name], args.capital, args.oos_start, args.oos_end)
        if not oos_df.empty:
            o = oos_df.iloc[0].to_dict()
            row.update({
                "oos_cagr_pct": o.get("cagr_pct"),
                "oos_return_pct": o.get("return_pct"),
                "oos_maxdd_pct": o.get("maxdd_pct"),
                "oos_sharpe": o.get("sharpe"),
                "oos_sortino": o.get("sortino"),
                "oos_calmar": o.get("calmar"),
                "oos_final_equity": o.get("final_equity"),
                "oos_worst_day_pct": o.get("worst_day_pct"),
            })
        else:
            row.update({"oos_cagr_pct": float("nan"), "oos_return_pct": float("nan"), "oos_maxdd_pct": float("nan"), "oos_sharpe": float("nan"), "oos_sortino": float("nan"), "oos_calmar": float("nan")})
        daily_parts.append(daily)
        weight_parts.append(weights)
        rows.append(row)
        if i % 100 == 0:
            print(f"  completed {i}/{len(specs)}")

    daily_df = pd.concat(daily_parts, ignore_index=True) if daily_parts else pd.DataFrame()
    weights_df = pd.concat(weight_parts, ignore_index=True) if weight_parts else pd.DataFrame()
    summary = pd.DataFrame(rows)
    summary["rank_score"] = summary.apply(_rank_score, axis=1)
    summary = summary.sort_values(["rank_score", "oos_calmar", "oos_sharpe", "oos_cagr_pct"], ascending=[False, False, False, False])
    top_policies = summary.head(args.top_n)["policy"].astype(str).tolist()
    top_daily = daily_df[daily_df["policy"].isin(top_policies)].copy()
    top_weights = weights_df[weights_df["policy"].isin(top_policies)].copy()
    annual = _calendar_returns(top_daily)
    pass_constraints = summary[
        (summary["oos_cagr_pct"] >= 12.0)
        & (summary["oos_maxdd_pct"].abs() <= 25.0)
        & (summary["oos_sharpe"] >= 1.0)
        & (summary["oos_calmar"] >= 0.75)
    ].copy()

    summary.to_csv(out_dir / "risk_contribution_policy_summary.csv", index=False)
    pass_constraints.to_csv(out_dir / "risk_contribution_policy_constraints_pass.csv", index=False)
    top_daily.to_csv(out_dir / "risk_contribution_policy_daily_equity_top.csv", index=False)
    top_weights.to_csv(out_dir / "risk_contribution_policy_daily_weights_top.csv", index=False)
    annual.to_csv(out_dir / "risk_contribution_policy_annual_returns_top.csv", index=False)
    (out_dir / "risk_contribution_sweep_summary.json").write_text(json.dumps({
        "assets_used": list(prices.columns),
        "start": args.start,
        "end": args.end,
        "oos_start": args.oos_start,
        "oos_end": args.oos_end,
        "policies_tested": len(specs),
        "constraints": {
            "oos_cagr_min": 12.0,
            "oos_maxdd_abs_max": 25.0,
            "oos_sharpe_min": 1.0,
            "oos_calmar_min": 0.75,
        },
        "outputs": {
            "summary": str(out_dir / "risk_contribution_policy_summary.csv"),
            "constraints_pass": str(out_dir / "risk_contribution_policy_constraints_pass.csv"),
            "daily_equity_top": str(out_dir / "risk_contribution_policy_daily_equity_top.csv"),
            "daily_weights_top": str(out_dir / "risk_contribution_policy_daily_weights_top.csv"),
            "annual_returns_top": str(out_dir / "risk_contribution_policy_annual_returns_top.csv"),
        },
    }, indent=2), encoding="utf-8")

    _print_summary(summary, "RISK-CONTRIBUTION CORE ALLOCATOR SWEEP — RANKED TOP", args.top_n)
    print(f"  Constraint pass count: {len(pass_constraints)} / {len(summary)}")
    print(f"  Assets used: {', '.join(prices.columns)}")
    print(f"  Outputs: {out_dir}")
    print("  Verdict: RISK-CONTRIBUTION CORE RESEARCH ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
