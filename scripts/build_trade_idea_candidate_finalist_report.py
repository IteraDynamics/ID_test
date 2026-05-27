#!/usr/bin/env python
"""Build allocator-style finalist reports for trade idea replay candidates.

The report compares selected finalist replay directories using asset-class-specific
cost assumptions. It creates:

- finalist summary table
- calendar-year returns
- monthly returns
- rolling 3/6/12-month return diagnostics
- drawdown diagnostics
- trade counts by year/status
- asset-class attribution by year
- Markdown report for review

Research only. No runtime, broker, or live execution code is modified.
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
REALIZED_STATUSES = {"target_hit", "stop_hit", "expired", "manual_closed"}
CRYPTO_TICKERS = {"BTC-USD", "ETH-USD"}


@dataclass(frozen=True)
class CostCase:
    name: str
    crypto_fee_bps_per_side: float
    crypto_slippage_bps_per_side: float
    equity_fee_bps_per_side: float
    equity_slippage_bps_per_side: float

    @property
    def crypto_per_side_bps(self) -> float:
        return self.crypto_fee_bps_per_side + self.crypto_slippage_bps_per_side

    @property
    def equity_per_side_bps(self) -> float:
        return self.equity_fee_bps_per_side + self.equity_slippage_bps_per_side

    @property
    def crypto_round_trip_bps(self) -> float:
        return self.crypto_per_side_bps * 2.0

    @property
    def equity_round_trip_bps(self) -> float:
        return self.equity_per_side_bps * 2.0


DEFAULT_COST_CASES: dict[str, CostCase] = {
    "none": CostCase("none", 0.0, 0.0, 0.0, 0.0),
    "asset_base": CostCase("asset_base", 10.0, 20.0, 0.0, 2.0),
    "asset_conservative": CostCase("asset_conservative", 10.0, 20.0, 0.0, 5.0),
    "asset_equity_harsh": CostCase("asset_equity_harsh", 10.0, 20.0, 0.0, 10.0),
    "asset_very_harsh": CostCase("asset_very_harsh", 20.0, 30.0, 0.0, 5.0),
}


DEFAULT_FINALISTS = {
    "primary_calmar": "artifacts/trade_idea_cost_aware_universe_pruning/looser_stop_12pct_max_new_3__crypto_plus_growth_plus_macro_liquid",
    "secondary_return": "artifacts/trade_idea_cost_aware_universe_pruning/looser_stop_12pct_max_new_3__remove_splv",
    "prior_current_core": "artifacts/trade_idea_cost_aware_universe_pruning/looser_stop_12pct_max_new_3__current_core",
    "crypto_only_benchmark": "artifacts/trade_idea_cost_aware_universe_pruning/looser_stop_12pct_max_new_3__crypto_only",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
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


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "$n/a"


def _pct(value: Any) -> str:
    return f"{_fmt(value)}%"


def _dateify(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.tz_localize(None)


def _find_col(df: pd.DataFrame, names: list[str]) -> str | None:
    cols = {str(c).lower().strip(): c for c in df.columns}
    for name in names:
        if name.lower() in cols:
            return cols[name.lower()]
    return None


def _is_crypto(ticker: str, bucket: str) -> bool:
    t = str(ticker).upper()
    b = str(bucket).lower()
    return t in CRYPTO_TICKERS or t.endswith("-USD") or b == "crypto"


def _normalize_daily_equity(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame(columns=["date", "equity"])
    date_col = _find_col(daily, ["date", "dt", "timestamp", "time", "datetime"]) or daily.columns[0]
    equity_col = _find_col(daily, ["equity", "portfolio_equity", "account_equity", "ending_equity", "final_equity", "nav"])
    if equity_col is None:
        numeric_cols = [c for c in daily.columns if c != date_col and pd.api.types.is_numeric_dtype(daily[c])]
        if not numeric_cols:
            coerced = daily.drop(columns=[date_col], errors="ignore").apply(pd.to_numeric, errors="coerce")
            numeric_cols = [c for c in coerced.columns if coerced[c].notna().any()]
        if not numeric_cols:
            return pd.DataFrame(columns=["date", "equity"])
        equity_col = numeric_cols[-1]
    out = daily[[date_col, equity_col]].copy()
    out.columns = ["date", "equity"]
    out["date"] = _dateify(out["date"])
    out["equity"] = pd.to_numeric(out["equity"], errors="coerce")
    return out.dropna(subset=["date", "equity"]).sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def _realized_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty or "status" not in trades.columns:
        return pd.DataFrame()
    out = trades[trades["status"].astype(str).isin(REALIZED_STATUSES)].copy()
    for col in ["notional", "realized_pnl", "realized_return_pct", "entry_price", "exit_price", "days_open", "score"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ["entry_date", "exit_date", "created_date", "activation_date"]:
        if col in out.columns:
            out[col] = _dateify(out[col])
    if "ticker" not in out.columns:
        out["ticker"] = out.get("symbol", "unknown")
    if "bucket" not in out.columns:
        out["bucket"] = "unknown"
    out["asset_class"] = out.apply(lambda r: "crypto" if _is_crypto(r.get("ticker", ""), r.get("bucket", "")) else "equity", axis=1)
    return out


def _infer_trade_notional(row: pd.Series, fallback_notional: float) -> float:
    notional = _to_float(row.get("notional"), 0.0)
    if notional > 0:
        return notional
    pnl = abs(_to_float(row.get("realized_pnl"), 0.0))
    ret_pct = abs(_to_float(row.get("realized_return_pct"), 0.0))
    if pnl > 0 and ret_pct > 0:
        return pnl / (ret_pct / 100.0)
    return fallback_notional


def _per_side_bps(row: pd.Series, case: CostCase) -> float:
    return case.crypto_per_side_bps if row.get("asset_class") == "crypto" else case.equity_per_side_bps


def _cost_events(realized: pd.DataFrame, case: CostCase, fallback_notional: float) -> pd.DataFrame:
    if realized.empty:
        return pd.DataFrame(columns=["date", "cost", "asset_class"])
    events: list[dict[str, Any]] = []
    for _, row in realized.iterrows():
        notional = _infer_trade_notional(row, fallback_notional)
        cost = notional * (_per_side_bps(row, case) / 10_000.0)
        asset_class = str(row.get("asset_class", "unknown"))
        entry_date = row.get("entry_date")
        exit_date = row.get("exit_date")
        if pd.notna(entry_date):
            events.append({"date": entry_date, "cost": cost, "asset_class": asset_class})
        if pd.notna(exit_date):
            events.append({"date": exit_date, "cost": cost, "asset_class": asset_class})
    if not events:
        return pd.DataFrame(columns=["date", "cost", "asset_class"])
    out = pd.DataFrame(events)
    out["date"] = _dateify(out["date"])
    out["cost"] = pd.to_numeric(out["cost"], errors="coerce").fillna(0.0)
    return out.dropna(subset=["date"])


def _adjusted_daily(daily: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    base = _normalize_daily_equity(daily)
    if base.empty:
        return pd.DataFrame(columns=["date", "equity", "daily_cost", "cumulative_cost", "adjusted_equity"])
    out = base.copy()
    if not events.empty:
        by_day = events.groupby("date", as_index=False)["cost"].sum().sort_values("date")
        out = out.merge(by_day.rename(columns={"cost": "daily_cost"}), on="date", how="left")
        out["daily_cost"] = out["daily_cost"].fillna(0.0)
    else:
        out["daily_cost"] = 0.0
    out["cumulative_cost"] = out["daily_cost"].cumsum()
    out["adjusted_equity"] = out["equity"] - out["cumulative_cost"]
    return out


def _infer_years(daily: pd.DataFrame, summary: dict[str, Any]) -> float:
    summary_years = _to_float(summary.get("years"), 0.0)
    if summary_years > 0:
        return summary_years
    if not daily.empty and "date" in daily.columns:
        dates = _dateify(daily["date"]).dropna().sort_values()
        if len(dates) >= 2:
            return max((dates.iloc[-1] - dates.iloc[0]).days, 1) / 365.25
    return 1.0


def _equity_metrics(equity: pd.Series, capital: float, years: float) -> dict[str, float]:
    equity = pd.to_numeric(equity, errors="coerce").dropna()
    if equity.empty:
        return {}
    returns = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    years = max(years, 1.0 / 365.25)
    final_equity = float(equity.iloc[-1])
    total_return_pct = (final_equity / capital - 1.0) * 100.0
    cagr_pct = ((final_equity / capital) ** (1.0 / years) - 1.0) * 100.0 if final_equity > 0 and capital > 0 else float("nan")
    dd = equity / equity.cummax() - 1.0
    maxdd_pct = float(dd.min() * 100.0)
    vol = returns.std(ddof=0)
    ann_vol_pct = float(vol * math.sqrt(TRADING_DAYS) * 100.0) if len(returns) > 1 else float("nan")
    sharpe = float(returns.mean() / vol * math.sqrt(TRADING_DAYS)) if vol and vol > 0 else float("nan")
    downside = returns[returns < 0]
    downside_vol = downside.std(ddof=0)
    sortino = float(returns.mean() / downside_vol * math.sqrt(TRADING_DAYS)) if len(downside) > 1 and downside_vol > 0 else float("nan")
    calmar = cagr_pct / abs(maxdd_pct) if maxdd_pct < 0 else float("nan")
    return {
        "final_equity": final_equity,
        "total_return_pct": total_return_pct,
        "cagr_pct": cagr_pct,
        "maxdd_pct": maxdd_pct,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "ann_vol_pct": ann_vol_pct,
        "worst_day_pct": float(returns.min() * 100.0) if not returns.empty else float("nan"),
    }


def _calendar_year_returns(adj: pd.DataFrame, label: str, case_name: str) -> pd.DataFrame:
    if adj.empty:
        return pd.DataFrame()
    s = adj.set_index("date")["adjusted_equity"].sort_index()
    yearly = s.resample("YE").last()
    prior = s.resample("YE").first().shift(1)
    first_equity = s.iloc[0]
    rows = []
    for dt, end_eq in yearly.items():
        start = prior.loc[dt]
        if pd.isna(start):
            year_slice = s[s.index.year == dt.year]
            start = float(year_slice.iloc[0]) if not year_slice.empty else first_equity
        ret = (float(end_eq) / float(start) - 1.0) * 100.0 if start else float("nan")
        rows.append({"candidate": label, "cost_case": case_name, "year": int(dt.year), "return_pct": ret, "ending_equity": float(end_eq)})
    return pd.DataFrame(rows)


def _monthly_returns(adj: pd.DataFrame, label: str, case_name: str) -> pd.DataFrame:
    if adj.empty:
        return pd.DataFrame()
    s = adj.set_index("date")["adjusted_equity"].sort_index()
    month_end = s.resample("ME").last()
    month_start = s.resample("ME").first().shift(1)
    rows = []
    for dt, end_eq in month_end.items():
        start = month_start.loc[dt]
        if pd.isna(start):
            month_slice = s[(s.index.year == dt.year) & (s.index.month == dt.month)]
            start = float(month_slice.iloc[0]) if not month_slice.empty else float(s.iloc[0])
        ret = (float(end_eq) / float(start) - 1.0) * 100.0 if start else float("nan")
        rows.append({"candidate": label, "cost_case": case_name, "month": dt.strftime("%Y-%m"), "return_pct": ret, "ending_equity": float(end_eq)})
    return pd.DataFrame(rows)


def _rolling_returns(adj: pd.DataFrame, label: str, case_name: str, windows: list[int]) -> pd.DataFrame:
    if adj.empty:
        return pd.DataFrame()
    s = adj.set_index("date")["adjusted_equity"].sort_index().resample("D").last().ffill()
    rows = []
    for months in windows:
        days = int(round(months * 30.4375))
        rr = s / s.shift(days) - 1.0
        rr = rr.dropna() * 100.0
        if rr.empty:
            continue
        rows.append({
            "candidate": label,
            "cost_case": case_name,
            "window_months": months,
            "best_return_pct": float(rr.max()),
            "worst_return_pct": float(rr.min()),
            "median_return_pct": float(rr.median()),
            "positive_rate_pct": float((rr > 0).mean() * 100.0),
            "ending_observations": int(len(rr)),
            "worst_end_date": rr.idxmin().strftime("%Y-%m-%d"),
            "best_end_date": rr.idxmax().strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(rows)


def _drawdown_periods(adj: pd.DataFrame, label: str, case_name: str, top_n: int) -> pd.DataFrame:
    if adj.empty:
        return pd.DataFrame()
    s = adj.set_index("date")["adjusted_equity"].sort_index()
    dd = s / s.cummax() - 1.0
    in_dd = dd < 0
    rows = []
    start = None
    trough_date = None
    trough_dd = 0.0
    peak_date = None
    for dt, flag in in_dd.items():
        if flag and start is None:
            pos = s.index.get_loc(dt)
            peak_idx = max(pos - 1, 0)
            start = dt
            peak_date = s.index[peak_idx]
            trough_date = dt
            trough_dd = float(dd.loc[dt])
        elif flag and start is not None:
            if float(dd.loc[dt]) < trough_dd:
                trough_dd = float(dd.loc[dt])
                trough_date = dt
        elif not flag and start is not None:
            rows.append({
                "candidate": label,
                "cost_case": case_name,
                "peak_date": peak_date.strftime("%Y-%m-%d") if peak_date is not None else None,
                "start_date": start.strftime("%Y-%m-%d"),
                "trough_date": trough_date.strftime("%Y-%m-%d") if trough_date is not None else None,
                "recovery_date": dt.strftime("%Y-%m-%d"),
                "drawdown_pct": trough_dd * 100.0,
                "duration_days": int((dt - start).days),
            })
            start = None
            trough_date = None
            peak_date = None
            trough_dd = 0.0
    if start is not None:
        rows.append({
            "candidate": label,
            "cost_case": case_name,
            "peak_date": peak_date.strftime("%Y-%m-%d") if peak_date is not None else None,
            "start_date": start.strftime("%Y-%m-%d"),
            "trough_date": trough_date.strftime("%Y-%m-%d") if trough_date is not None else None,
            "recovery_date": None,
            "drawdown_pct": trough_dd * 100.0,
            "duration_days": int((s.index[-1] - start).days),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("drawdown_pct").head(top_n)


def _trade_counts_by_year(realized: pd.DataFrame, label: str) -> pd.DataFrame:
    if realized.empty:
        return pd.DataFrame()
    date_col = "exit_date" if "exit_date" in realized.columns else "entry_date"
    out = realized.copy()
    out["year"] = pd.to_datetime(out[date_col], errors="coerce").dt.year
    out = out.dropna(subset=["year"])
    rows = []
    for (year, status), sub in out.groupby(["year", "status"], dropna=False):
        rows.append({"candidate": label, "year": int(year), "status": str(status), "trades": int(len(sub)), "gross_pnl": float(sub.get("realized_pnl", pd.Series(dtype=float)).sum())})
    return pd.DataFrame(rows)


def _asset_attribution_by_year(realized: pd.DataFrame, label: str, case: CostCase, fallback_notional: float) -> pd.DataFrame:
    if realized.empty:
        return pd.DataFrame()
    out = realized.copy()
    date_col = "exit_date" if "exit_date" in out.columns else "entry_date"
    out["year"] = pd.to_datetime(out[date_col], errors="coerce").dt.year
    out = out.dropna(subset=["year"])
    rows = []
    for _, row in out.iterrows():
        notional = _infer_trade_notional(row, fallback_notional)
        total_cost = notional * (_per_side_bps(row, case) / 10_000.0) * 2.0
        rows.append({
            "candidate": label,
            "cost_case": case.name,
            "year": int(row["year"]),
            "asset_class": row.get("asset_class", "unknown"),
            "ticker": row.get("ticker", "unknown"),
            "bucket": row.get("bucket", "unknown"),
            "status": row.get("status", "unknown"),
            "gross_pnl": _to_float(row.get("realized_pnl"), 0.0),
            "cost": total_cost,
            "net_pnl": _to_float(row.get("realized_pnl"), 0.0) - total_cost,
        })
    detail = pd.DataFrame(rows)
    if detail.empty:
        return detail
    group = detail.groupby(["candidate", "cost_case", "year", "asset_class"], as_index=False).agg(
        trades=("net_pnl", "size"),
        gross_pnl=("gross_pnl", "sum"),
        cost=("cost", "sum"),
        net_pnl=("net_pnl", "sum"),
    )
    return group.sort_values(["candidate", "cost_case", "year", "asset_class"])


def _load_candidate(label: str, path: Path, case: CostCase, args: argparse.Namespace) -> dict[str, Any]:
    daily = _read_csv(path / "replay_daily.csv")
    trades = _read_csv(path / "replay_trades.csv")
    summary = _read_json(path / "replay_summary.json")
    realized = _realized_trades(trades)
    events = _cost_events(realized, case, args.fallback_notional)
    adjusted = _adjusted_daily(daily, events)
    years = _infer_years(_normalize_daily_equity(daily), summary)
    metrics = _equity_metrics(adjusted.set_index("date")["adjusted_equity"], args.capital, years) if not adjusted.empty else {}
    total_cost = float(events["cost"].sum()) if not events.empty else 0.0
    crypto_cost = float(events.loc[events["asset_class"] == "crypto", "cost"].sum()) if not events.empty else 0.0
    equity_cost = float(events.loc[events["asset_class"] == "equity", "cost"].sum()) if not events.empty else 0.0
    gross_pnl = float(realized.get("realized_pnl", pd.Series(dtype=float)).sum()) if not realized.empty else 0.0
    return {
        "label": label,
        "path": path,
        "summary": summary,
        "realized": realized,
        "events": events,
        "adjusted": adjusted,
        "row": {
            "candidate": label,
            "cost_case": case.name,
            "candidate_dir": str(path),
            "crypto_round_trip_bps": case.crypto_round_trip_bps,
            "equity_round_trip_bps": case.equity_round_trip_bps,
            "trades": int(len(realized)),
            "target_hits": int((realized.get("status", pd.Series(dtype=str)) == "target_hit").sum()) if not realized.empty else 0,
            "stop_hits": int((realized.get("status", pd.Series(dtype=str)) == "stop_hit").sum()) if not realized.empty else 0,
            "expired": int((realized.get("status", pd.Series(dtype=str)) == "expired").sum()) if not realized.empty else 0,
            "gross_pnl": gross_pnl,
            "total_cost": total_cost,
            "crypto_cost": crypto_cost,
            "equity_cost": equity_cost,
            "net_pnl": gross_pnl - total_cost,
            "final_equity": metrics.get("final_equity", float("nan")),
            "return_pct": metrics.get("total_return_pct", float("nan")),
            "cagr_pct": metrics.get("cagr_pct", float("nan")),
            "maxdd_pct": metrics.get("maxdd_pct", float("nan")),
            "sharpe": metrics.get("sharpe", float("nan")),
            "sortino": metrics.get("sortino", float("nan")),
            "calmar": metrics.get("calmar", float("nan")),
            "ann_vol_pct": metrics.get("ann_vol_pct", float("nan")),
            "worst_day_pct": metrics.get("worst_day_pct", float("nan")),
        },
    }


def _parse_finalist_args(values: list[str]) -> dict[str, Path]:
    if not values:
        return {k: Path(v) for k, v in DEFAULT_FINALISTS.items()}
    out: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise SystemExit(f"Invalid --finalist '{raw}'. Expected label=path")
        label, path = raw.split("=", 1)
        out[label.strip()] = Path(path.strip())
    return out


def _print_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print("  TRADE IDEA FINALIST REPORT — SUMMARY")
    print("=" * DISPLAY_WIDTH)
    if df.empty:
        print("  No rows.")
        return
    view = df.sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    print(f"  {'Candidate':<32} {'Case':<20} {'Trades':>7} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Calmar':>8} {'Cost':>10} {'NetPnL':>12} {'FinalEq':>12}")
    for _, r in view.iterrows():
        print(
            f"  {str(r['candidate']):<32} {str(r['cost_case']):<20} {int(r['trades']):>7} "
            f"{_fmt(r['cagr_pct']):>8} {_fmt(r['return_pct']):>8} {_fmt(r['maxdd_pct']):>8} {_fmt(r['sharpe'], 3):>8} {_fmt(r['calmar'], 3):>8} "
            f"{_money(r['total_cost']):>10} {_money(r['net_pnl']):>12} {_money(r['final_equity']):>12}"
        )
    print("=" * DISPLAY_WIDTH)


def _markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._\n"
    view = df[columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_markdown(index=False) + "\n"


def _write_markdown(out_dir: Path, summary: pd.DataFrame, yearly: pd.DataFrame, rolling: pd.DataFrame, drawdowns: pd.DataFrame, trade_counts: pd.DataFrame, attribution: pd.DataFrame, args: argparse.Namespace) -> None:
    md = []
    md.append("# Trade Idea Candidate Finalist Report\n")
    md.append("Research-only finalist comparison. No runtime, broker, or live execution code is modified.\n")
    md.append(f"Cost case: `{args.cost_case}`. Capital: `{args.capital:,.0f}`.\n")
    md.append("## Summary\n")
    md.append(_markdown_table(summary.sort_values(["calmar", "cagr_pct"], ascending=[False, False]), ["candidate", "trades", "cagr_pct", "return_pct", "maxdd_pct", "sharpe", "sortino", "calmar", "total_cost", "net_pnl", "final_equity"]))
    md.append("## Calendar-Year Returns\n")
    if not yearly.empty:
        pivot = yearly.pivot_table(index="year", columns="candidate", values="return_pct", aggfunc="first").reset_index()
        md.append(pivot.to_markdown(index=False) + "\n")
    else:
        md.append("_No rows._\n")
    md.append("## Rolling Return Diagnostics\n")
    md.append(_markdown_table(rolling.sort_values(["window_months", "worst_return_pct"]), ["candidate", "window_months", "worst_return_pct", "median_return_pct", "best_return_pct", "positive_rate_pct", "worst_end_date", "best_end_date"]))
    md.append("## Worst Drawdown Periods\n")
    md.append(_markdown_table(drawdowns, ["candidate", "drawdown_pct", "peak_date", "start_date", "trough_date", "recovery_date", "duration_days"], max_rows=30))
    md.append("## Trade Counts by Year / Status\n")
    md.append(_markdown_table(trade_counts.sort_values(["candidate", "year", "status"]), ["candidate", "year", "status", "trades", "gross_pnl"]))
    md.append("## Asset-Class Attribution by Year\n")
    md.append(_markdown_table(attribution.sort_values(["candidate", "year", "asset_class"]), ["candidate", "year", "asset_class", "trades", "gross_pnl", "cost", "net_pnl"]))
    (out_dir / "finalist_report.md").write_text("\n".join(md), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build finalist report for trade idea candidate selection")
    p.add_argument("--finalist", action="append", default=[], help="Finalist as label=path. Repeatable. Defaults to primary, secondary, current_core, crypto_only.")
    p.add_argument("--cost-case", default="asset_base", choices=list(DEFAULT_COST_CASES.keys()))
    p.add_argument("--out-dir", default="artifacts/trade_idea_candidate_finalist_report")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fallback-notional", type=float, default=25_000.0)
    p.add_argument("--rolling-windows-months", nargs="+", type=int, default=[3, 6, 12])
    p.add_argument("--top-drawdowns", type=int, default=5)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    case = DEFAULT_COST_CASES[args.cost_case]
    finalists = _parse_finalist_args(args.finalist)

    loaded = []
    for label, path in finalists.items():
        loaded.append(_load_candidate(label, path, case, args))

    summary = pd.DataFrame([item["row"] for item in loaded])
    yearly = pd.concat([_calendar_year_returns(item["adjusted"], item["label"], case.name) for item in loaded], ignore_index=True) if loaded else pd.DataFrame()
    monthly = pd.concat([_monthly_returns(item["adjusted"], item["label"], case.name) for item in loaded], ignore_index=True) if loaded else pd.DataFrame()
    rolling = pd.concat([_rolling_returns(item["adjusted"], item["label"], case.name, args.rolling_windows_months) for item in loaded], ignore_index=True) if loaded else pd.DataFrame()
    drawdowns = pd.concat([_drawdown_periods(item["adjusted"], item["label"], case.name, args.top_drawdowns) for item in loaded], ignore_index=True) if loaded else pd.DataFrame()
    trade_counts = pd.concat([_trade_counts_by_year(item["realized"], item["label"]) for item in loaded], ignore_index=True) if loaded else pd.DataFrame()
    attribution = pd.concat([_asset_attribution_by_year(item["realized"], item["label"], case, args.fallback_notional) for item in loaded], ignore_index=True) if loaded else pd.DataFrame()

    summary.to_csv(out_dir / "finalist_summary.csv", index=False)
    yearly.to_csv(out_dir / "calendar_year_returns.csv", index=False)
    monthly.to_csv(out_dir / "monthly_returns.csv", index=False)
    rolling.to_csv(out_dir / "rolling_return_diagnostics.csv", index=False)
    drawdowns.to_csv(out_dir / "worst_drawdown_periods.csv", index=False)
    trade_counts.to_csv(out_dir / "trade_counts_by_year_status.csv", index=False)
    attribution.to_csv(out_dir / "asset_class_attribution_by_year.csv", index=False)

    json_summary = {
        "cost_case": case.name,
        "capital": args.capital,
        "finalists": {label: str(path) for label, path in finalists.items()},
        "outputs": {
            "summary": str(out_dir / "finalist_summary.csv"),
            "calendar_year_returns": str(out_dir / "calendar_year_returns.csv"),
            "monthly_returns": str(out_dir / "monthly_returns.csv"),
            "rolling_return_diagnostics": str(out_dir / "rolling_return_diagnostics.csv"),
            "worst_drawdown_periods": str(out_dir / "worst_drawdown_periods.csv"),
            "trade_counts_by_year_status": str(out_dir / "trade_counts_by_year_status.csv"),
            "asset_class_attribution_by_year": str(out_dir / "asset_class_attribution_by_year.csv"),
            "markdown_report": str(out_dir / "finalist_report.md"),
        },
    }
    (out_dir / "finalist_report_summary.json").write_text(json.dumps(json_summary, indent=2), encoding="utf-8")
    _write_markdown(out_dir, summary, yearly, rolling, drawdowns, trade_counts, attribution, args)

    _print_summary(summary)
    print("\n  Report written:")
    print(f"    {out_dir / 'finalist_report.md'}")
    print(f"    {out_dir / 'finalist_summary.csv'}")
    print(f"    {out_dir / 'calendar_year_returns.csv'}")
    print(f"    {out_dir / 'rolling_return_diagnostics.csv'}")
    print(f"    {out_dir / 'worst_drawdown_periods.csv'}")
    print(f"    {out_dir / 'asset_class_attribution_by_year.csv'}")
    print("  Verdict: FINALIST RESEARCH REPORT ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
