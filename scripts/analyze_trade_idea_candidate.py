#!/usr/bin/env python
"""Focused tear-sheet analysis for one trade idea replay candidate.

This is intended for post-scoreboard validation after a candidate has become
interesting enough to inspect deeply. It answers questions like:

- Which tickers, buckets, setups, years, and months carry the result?
- Is the result dependent on a small number of outsized winners?
- How much PnL comes from the top 5 / 10 / 25 trades?
- What is the longest underwater period?
- What do rolling 3/6/12-month returns look like?
- How does performance change if top winners are removed?

Research/paper only. No runtime, broker, or live execution code is modified.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


REALIZED_STATUSES = {"target_hit", "stop_hit", "expired", "manual_closed"}
DISPLAY_WIDTH = 198
TRADING_DAYS = 252.0


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


def _fmt_pct(value: Any) -> str:
    txt = _fmt(value)
    return f"{txt}%" if txt != "n/a" else "n/a"


def _fmt_money(value: Any) -> str:
    try:
        v = float(value)
        if math.isnan(v):
            return "n/a"
        return f"${v:,.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _dateify(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.tz_localize(None)
    return out


def _realized(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty or "status" not in trades.columns:
        return pd.DataFrame()
    out = trades[trades["status"].astype(str).isin(REALIZED_STATUSES)].copy()
    out = _numeric(out, ["realized_pnl", "realized_return_pct", "days_open", "score", "entry_price", "exit_price", "notional"])
    out = _dateify(out, ["entry_date", "exit_date", "created_date", "activation_date"])
    return out


def _normalize_daily_equity(daily: pd.DataFrame) -> pd.Series:
    if daily.empty:
        return pd.Series(dtype=float)
    cols = {str(c).lower().strip(): c for c in daily.columns}
    date_col = next((cols[k] for k in ["date", "dt", "timestamp", "time", "datetime"] if k in cols), daily.columns[0])
    equity_col = next((cols[k] for k in ["equity", "portfolio_equity", "account_equity", "ending_equity", "final_equity", "nav"] if k in cols), None)
    if equity_col is None:
        numeric_cols = [c for c in daily.columns if c != date_col and pd.api.types.is_numeric_dtype(daily[c])]
        if not numeric_cols:
            return pd.Series(dtype=float)
        equity_col = numeric_cols[-1]
    out = daily[[date_col, equity_col]].copy()
    out.columns = ["date", "equity"]
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    out["equity"] = pd.to_numeric(out["equity"], errors="coerce")
    out = out.dropna(subset=["date", "equity"]).sort_values("date").drop_duplicates("date", keep="last")
    return out.set_index("date")["equity"] if not out.empty else pd.Series(dtype=float)


def _equity_metrics(equity: pd.Series, capital: float) -> dict[str, Any]:
    equity = pd.to_numeric(equity, errors="coerce").dropna()
    if equity.empty:
        return {}
    returns = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    total_return_pct = (equity.iloc[-1] / capital - 1.0) * 100.0
    years = max(len(equity) / TRADING_DAYS, 1.0 / TRADING_DAYS)
    cagr_pct = ((equity.iloc[-1] / capital) ** (1.0 / years) - 1.0) * 100.0 if equity.iloc[-1] > 0 else float("nan")
    dd = equity / equity.cummax() - 1.0
    maxdd_pct = float(dd.min() * 100.0)
    ann_vol_pct = float(returns.std(ddof=0) * math.sqrt(TRADING_DAYS) * 100.0) if not returns.empty else float("nan")
    sharpe = float(returns.mean() / returns.std(ddof=0) * math.sqrt(TRADING_DAYS)) if returns.std(ddof=0) and returns.std(ddof=0) > 0 else float("nan")
    downside = returns[returns < 0]
    sortino = float(returns.mean() / downside.std(ddof=0) * math.sqrt(TRADING_DAYS)) if len(downside) > 1 and downside.std(ddof=0) > 0 else float("nan")
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


def _drawdown_episodes(equity: pd.Series) -> pd.DataFrame:
    if equity.empty:
        return pd.DataFrame()
    eq = equity.dropna()
    dd = eq / eq.cummax() - 1.0
    episodes = []
    in_dd = False
    start = trough_date = None
    trough = 0.0
    for date, value in dd.items():
        value = float(value)
        if value < 0 and not in_dd:
            in_dd = True
            start = trough_date = date
            trough = value
        elif value < 0 and in_dd:
            if value < trough:
                trough = value
                trough_date = date
        elif value >= 0 and in_dd:
            episodes.append({
                "start": start,
                "trough_date": trough_date,
                "recovery_date": date,
                "max_drawdown_pct": trough * 100.0,
                "days_underwater": int((date - start).days),
                "days_to_trough": int((trough_date - start).days),
            })
            in_dd = False
    if in_dd and start is not None:
        end = eq.index[-1]
        episodes.append({
            "start": start,
            "trough_date": trough_date,
            "recovery_date": pd.NaT,
            "max_drawdown_pct": trough * 100.0,
            "days_underwater": int((end - start).days),
            "days_to_trough": int((trough_date - start).days),
        })
    out = pd.DataFrame(episodes)
    return out.sort_values(["max_drawdown_pct", "days_underwater"], ascending=[True, False]) if not out.empty else out


def _rolling_returns(equity: pd.Series) -> pd.DataFrame:
    if equity.empty:
        return pd.DataFrame()
    monthly_eq = equity.resample("ME").last().dropna()
    rows = []
    for months in [3, 6, 12]:
        rr = monthly_eq.pct_change(months).dropna() * 100.0
        if rr.empty:
            continue
        rows.append({
            "window_months": months,
            "observations": int(len(rr)),
            "avg_return_pct": float(rr.mean()),
            "median_return_pct": float(rr.median()),
            "best_return_pct": float(rr.max()),
            "worst_return_pct": float(rr.min()),
            "positive_rate_pct": float((rr > 0).mean() * 100.0),
        })
    return pd.DataFrame(rows)


def _group_stats(realized: pd.DataFrame, group_col: str, min_trades: int = 1) -> pd.DataFrame:
    if realized.empty or group_col not in realized.columns:
        return pd.DataFrame()
    rows = []
    total_pnl_all = float(realized["realized_pnl"].sum()) if "realized_pnl" in realized.columns else 0.0
    for label, g in realized.groupby(group_col, dropna=False):
        if len(g) < min_trades:
            continue
        rets = g["realized_return_pct"].dropna()
        pnl = g["realized_pnl"].dropna()
        wins = rets[rets > 0]
        losses = rets[rets <= 0]
        total_pnl = float(pnl.sum()) if not pnl.empty else 0.0
        rows.append({
            group_col: str(label),
            "trades": int(len(g)),
            "win_rate_pct": float((rets > 0).mean() * 100.0) if not rets.empty else 0.0,
            "avg_return_pct": float(rets.mean()) if not rets.empty else 0.0,
            "median_return_pct": float(rets.median()) if not rets.empty else 0.0,
            "avg_win_pct": float(wins.mean()) if not wins.empty else 0.0,
            "avg_loss_pct": float(losses.mean()) if not losses.empty else 0.0,
            "expectancy_pct": float(rets.mean()) if not rets.empty else 0.0,
            "total_pnl": total_pnl,
            "pnl_share_pct": total_pnl / total_pnl_all * 100.0 if total_pnl_all else 0.0,
            "avg_days_open": float(g["days_open"].mean()) if "days_open" in g.columns else 0.0,
            "target_hits": int((g["status"] == "target_hit").sum()),
            "stop_hits": int((g["status"] == "stop_hit").sum()),
            "expired": int((g["status"] == "expired").sum()),
        })
    out = pd.DataFrame(rows)
    return out.sort_values(["total_pnl", "expectancy_pct"], ascending=[False, False]) if not out.empty else out


def _period_stats(realized: pd.DataFrame, period: str) -> pd.DataFrame:
    if realized.empty or "exit_date" not in realized.columns:
        return pd.DataFrame()
    df = realized.dropna(subset=["exit_date"]).copy()
    if period == "year":
        df["period"] = df["exit_date"].dt.year.astype(str)
    elif period == "month":
        df["period"] = df["exit_date"].dt.to_period("M").astype(str)
    else:
        raise ValueError(period)
    return _group_stats(df, "period", min_trades=1)


def _concentration(realized: pd.DataFrame, capital: float) -> pd.DataFrame:
    if realized.empty:
        return pd.DataFrame()
    df = realized.sort_values("realized_pnl", ascending=False).copy()
    total_pnl = float(df["realized_pnl"].sum())
    rows = []
    for n in [1, 3, 5, 10, 25, 50]:
        top = df.head(n)
        pnl = float(top["realized_pnl"].sum()) if not top.empty else 0.0
        rows.append({
            "top_n": min(n, len(df)),
            "top_n_pnl": pnl,
            "share_of_total_pnl_pct": pnl / total_pnl * 100.0 if total_pnl else 0.0,
            "return_on_start_capital_pct": pnl / capital * 100.0 if capital else 0.0,
            "remaining_pnl_after_removal": total_pnl - pnl,
            "remaining_return_on_capital_pct": (total_pnl - pnl) / capital * 100.0 if capital else 0.0,
        })
    return pd.DataFrame(rows)


def _top_trade_removal(realized: pd.DataFrame, summary: dict[str, Any], capital: float) -> pd.DataFrame:
    if realized.empty:
        return pd.DataFrame()
    total_pnl = float(realized["realized_pnl"].sum())
    years = _to_float(summary.get("years"), 1.0) or 1.0
    rows = []
    for n in [0, 1, 3, 5, 10, 25, 50]:
        remaining = realized.sort_values("realized_pnl", ascending=False).iloc[n:]
        pnl = float(remaining["realized_pnl"].sum()) if not remaining.empty else 0.0
        final_equity = capital + pnl
        cagr = ((final_equity / capital) ** (1.0 / years) - 1.0) * 100.0 if final_equity > 0 else float("nan")
        rows.append({
            "top_winners_removed": n,
            "remaining_trades": int(len(remaining)),
            "remaining_pnl": pnl,
            "removed_pnl": total_pnl - pnl,
            "remaining_return_on_capital_pct": pnl / capital * 100.0 if capital else 0.0,
            "approx_cagr_from_realized_pnl_pct": cagr,
        })
    return pd.DataFrame(rows)


def _print_header(title: str) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print(f"  {title}")
    print("=" * DISPLAY_WIDTH)


def _print_group_table(title: str, df: pd.DataFrame, label_col: str, limit: int) -> None:
    print("-" * DISPLAY_WIDTH)
    print(f"  {title}")
    print("-" * DISPLAY_WIDTH)
    if df.empty:
        print("  No rows.")
        return
    print(f"  {label_col:<30} {'Trades':>7} {'Win%':>8} {'AvgRet':>9} {'MedRet':>9} {'Exp':>9} {'PnL':>14} {'PnL%':>8} {'Days':>7} {'T/S/E':>11}")
    for _, r in df.head(limit).iterrows():
        tse = f"{int(r.get('target_hits', 0))}/{int(r.get('stop_hits', 0))}/{int(r.get('expired', 0))}"
        print(f"  {str(r.get(label_col)):<30} {int(r.get('trades', 0)):>7} {_fmt_pct(r.get('win_rate_pct')):>8} {_fmt_pct(r.get('avg_return_pct')):>9} {_fmt_pct(r.get('median_return_pct')):>9} {_fmt_pct(r.get('expectancy_pct')):>9} {_fmt_money(r.get('total_pnl')):>14} {_fmt_pct(r.get('pnl_share_pct')):>8} {_fmt(r.get('avg_days_open'), 1):>7} {tse:>11}")


def _print_simple_table(title: str, df: pd.DataFrame, columns: list[str], limit: int = 20) -> None:
    print("-" * DISPLAY_WIDTH)
    print(f"  {title}")
    print("-" * DISPLAY_WIDTH)
    if df.empty:
        print("  No rows.")
        return
    print(df[columns].head(limit).to_string(index=False))


def _print_trade_table(title: str, trades: pd.DataFrame, limit: int, ascending: bool) -> None:
    print("-" * DISPLAY_WIDTH)
    print(f"  {title}")
    print("-" * DISPLAY_WIDTH)
    if trades.empty:
        print("  No trades.")
        return
    df = trades.sort_values("realized_pnl", ascending=ascending).head(limit)
    print(f"  {'Ticker':<8} {'Bucket':<24} {'Setup':<27} {'Exit':<11} {'Entry':<11} {'ExitDate':<11} {'Ret%':>9} {'PnL':>13} {'Days':>5} {'Score':>7}")
    for _, r in df.iterrows():
        entry = r.get("entry_date")
        exit_date = r.get("exit_date")
        entry_s = entry.strftime("%Y-%m-%d") if pd.notna(entry) else "n/a"
        exit_s = exit_date.strftime("%Y-%m-%d") if pd.notna(exit_date) else "n/a"
        print(f"  {str(r.get('ticker')):<8} {str(r.get('bucket')):<24} {str(r.get('setup')):<27} {str(r.get('status')):<11} {entry_s:<11} {exit_s:<11} {_fmt_pct(r.get('realized_return_pct')):>9} {_fmt_money(r.get('realized_pnl')):>13} {int(_to_float(r.get('days_open'))):>5} {_fmt(r.get('score'), 1):>7}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Focused candidate analysis for trade idea replay outputs")
    p.add_argument("--candidate-dir", default="artifacts/trade_idea_risk_sweep/remove_known_weak_tickers__very_aggressive")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--min-trades", type=int, default=5)
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--trade-limit", type=int, default=15)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    candidate_dir = Path(args.candidate_dir)
    out_dir = Path(args.out_dir) if args.out_dir else candidate_dir / "candidate_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    trades = _read_csv(candidate_dir / "replay_trades.csv")
    daily = _read_csv(candidate_dir / "replay_daily.csv")
    summary = _read_json(candidate_dir / "replay_summary.json")
    realized = _realized(trades)
    equity = _normalize_daily_equity(daily)

    by_bucket = _group_stats(realized, "bucket", args.min_trades)
    by_setup = _group_stats(realized, "setup", args.min_trades)
    by_ticker = _group_stats(realized, "ticker", args.min_trades)
    by_year = _period_stats(realized, "year")
    by_month = _period_stats(realized, "month")
    by_exit = _group_stats(realized, "status", min_trades=1).rename(columns={"status": "exit"}) if not realized.empty else pd.DataFrame()
    concentration = _concentration(realized, args.capital)
    removal = _top_trade_removal(realized, summary, args.capital)
    dd_episodes = _drawdown_episodes(equity)
    rolling = _rolling_returns(equity)
    daily_metrics = _equity_metrics(equity, args.capital)

    _print_header("TRADE IDEA CANDIDATE ANALYSIS")
    print(f"  Candidate dir       : {candidate_dir}")
    print(f"  Total orders        : {summary.get('total_orders', 0)}")
    print(f"  Realized trades     : {summary.get('closed_realized_trades', len(realized))}")
    print(f"  Cancelled / Reject  : {summary.get('cancelled_orders', 0)} / {summary.get('rejected_orders', 0)}")
    print(f"  CAGR / Return       : {_fmt_pct(summary.get('cagr_pct'))} / {_fmt_pct(summary.get('total_return_pct_on_capital'))}")
    print(f"  MaxDD / Sharpe      : {_fmt_pct(summary.get('max_drawdown_pct_on_equity'))} / {_fmt(summary.get('sharpe'), 3)}")
    print(f"  Sortino / Calmar    : {_fmt(summary.get('sortino'), 3)} / {_fmt(summary.get('calmar'), 3)}")
    print(f"  Worst M/Y/D         : {_fmt_pct(daily_metrics.get('worst_month_pct'))} / {_fmt_pct(daily_metrics.get('worst_year_pct'))} / {_fmt_pct(summary.get('worst_day_pct'))}")

    _print_group_table("PERFORMANCE BY TICKER", by_ticker, "ticker", args.top_n)
    _print_group_table("PERFORMANCE BY BUCKET", by_bucket, "bucket", args.top_n)
    _print_group_table("PERFORMANCE BY SETUP", by_setup, "setup", args.top_n)
    _print_group_table("PERFORMANCE BY YEAR", by_year, "period", args.top_n)
    _print_group_table("WORST MONTHS", by_month.sort_values("total_pnl", ascending=True) if not by_month.empty else by_month, "period", 12)
    _print_group_table("EXIT BEHAVIOR", by_exit, "exit", args.top_n)

    _print_simple_table("PNL CONCENTRATION", concentration, ["top_n", "top_n_pnl", "share_of_total_pnl_pct", "return_on_start_capital_pct", "remaining_return_on_capital_pct"])
    _print_simple_table("TOP WINNER REMOVAL STRESS", removal, ["top_winners_removed", "remaining_trades", "remaining_pnl", "removed_pnl", "remaining_return_on_capital_pct", "approx_cagr_from_realized_pnl_pct"])
    _print_simple_table("WORST DRAWDOWN EPISODES", dd_episodes, ["start", "trough_date", "recovery_date", "max_drawdown_pct", "days_underwater", "days_to_trough"], limit=10)
    _print_simple_table("ROLLING RETURN SUMMARY", rolling, ["window_months", "observations", "avg_return_pct", "median_return_pct", "best_return_pct", "worst_return_pct", "positive_rate_pct"])
    _print_trade_table("BEST REALIZED TRADES BY PNL", realized, args.trade_limit, ascending=False)
    _print_trade_table("WORST REALIZED TRADES BY PNL", realized, args.trade_limit, ascending=True)
    print("=" * DISPLAY_WIDTH)

    outputs = {
        "by_ticker": by_ticker,
        "by_bucket": by_bucket,
        "by_setup": by_setup,
        "by_year": by_year,
        "by_month": by_month,
        "by_exit": by_exit,
        "pnl_concentration": concentration,
        "top_winner_removal_stress": removal,
        "drawdown_episodes": dd_episodes,
        "rolling_returns": rolling,
        "best_trades_by_pnl": realized.sort_values("realized_pnl", ascending=False).head(args.trade_limit) if not realized.empty else pd.DataFrame(),
        "worst_trades_by_pnl": realized.sort_values("realized_pnl", ascending=True).head(args.trade_limit) if not realized.empty else pd.DataFrame(),
    }
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)

    payload = {
        "candidate_dir": str(candidate_dir),
        "summary": summary,
        "daily_metrics": daily_metrics,
        "analysis_outputs": {name: str(out_dir / f"{name}.csv") for name in outputs},
    }
    (out_dir / "candidate_analysis_summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"  Analysis written to: {out_dir}")
    print("  Verdict: CANDIDATE DIAGNOSTIC ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
