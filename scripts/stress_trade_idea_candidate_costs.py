#!/usr/bin/env python
"""Apply fee/slippage stress to trade idea replay candidates.

This script post-processes existing replay artifacts instead of re-running the
scanner/replay engine. It supports both flat costs and asset-class-specific costs
so crypto can be charged Coinbase-style friction while listed ETFs/equities use
lower retail-platform friction.

Expected candidate directory contents:

- replay_trades.csv
- replay_daily.csv
- replay_summary.json

Research/paper only. No runtime, broker, or live execution code is modified.
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
DISPLAY_WIDTH = 198
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
    # Flat legacy cases: same friction for every asset.
    "none": CostCase("none", 0.0, 0.0, 0.0, 0.0),
    "mild": CostCase("mild", 2.0, 5.0, 2.0, 5.0),
    "realistic": CostCase("realistic", 5.0, 10.0, 5.0, 10.0),
    "harsh": CostCase("harsh", 10.0, 20.0, 10.0, 20.0),
    "very_harsh": CostCase("very_harsh", 20.0, 30.0, 20.0, 30.0),
    # Asset-class cases: crypto remains expensive; ETFs/equities are modeled
    # closer to liquid retail execution.
    "asset_base": CostCase("asset_base", 10.0, 20.0, 0.0, 2.0),
    "asset_conservative": CostCase("asset_conservative", 10.0, 20.0, 0.0, 5.0),
    "asset_equity_harsh": CostCase("asset_equity_harsh", 10.0, 20.0, 0.0, 10.0),
    "asset_very_harsh": CostCase("asset_very_harsh", 20.0, 30.0, 0.0, 5.0),
    "asset_very_harsh_equity_harsh": CostCase("asset_very_harsh_equity_harsh", 20.0, 30.0, 0.0, 10.0),
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


def _candidate_name(path: Path) -> str:
    return path.name.replace(" ", "_")


def _dateify(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.tz_localize(None)


def _find_col(df: pd.DataFrame, names: list[str]) -> str | None:
    cols = {str(c).lower().strip(): c for c in df.columns}
    for name in names:
        if name.lower() in cols:
            return cols[name.lower()]
    return None


def _is_crypto_row(row: pd.Series) -> bool:
    ticker = str(row.get("ticker", row.get("symbol", row.get("asset", "")))).upper()
    bucket = str(row.get("bucket", row.get("asset_bucket", ""))).lower()
    return ticker in CRYPTO_TICKERS or ticker.endswith("-USD") or bucket == "crypto"


def _infer_years(daily_equity: pd.DataFrame, summary: dict[str, Any]) -> float:
    summary_years = _to_float(summary.get("years"), 0.0)
    if summary_years > 0:
        return summary_years
    if not daily_equity.empty and "date" in daily_equity.columns:
        dates = _dateify(daily_equity["date"]).dropna().sort_values()
        if len(dates) >= 2:
            return max((dates.iloc[-1] - dates.iloc[0]).days, 1) / 365.25
    return 1.0


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


def _per_side_bps_for_row(row: pd.Series, cost_case: CostCase) -> float:
    return cost_case.crypto_per_side_bps if _is_crypto_row(row) else cost_case.equity_per_side_bps


def _build_cost_events(realized: pd.DataFrame, cost_case: CostCase, fallback_notional: float) -> pd.DataFrame:
    if realized.empty:
        return pd.DataFrame(columns=["date", "cost", "asset_class"])
    events: list[dict[str, Any]] = []
    for _, row in realized.iterrows():
        notional = _infer_trade_notional(row, fallback_notional)
        per_side_rate = _per_side_bps_for_row(row, cost_case) / 10_000.0
        per_side_cost = notional * per_side_rate
        asset_class = "crypto" if _is_crypto_row(row) else "equity"
        entry_date = row.get("entry_date")
        exit_date = row.get("exit_date")
        if pd.notna(entry_date):
            events.append({"date": entry_date, "cost": per_side_cost, "asset_class": asset_class})
        if pd.notna(exit_date):
            events.append({"date": exit_date, "cost": per_side_cost, "asset_class": asset_class})
    if not events:
        return pd.DataFrame(columns=["date", "cost", "asset_class"])
    out = pd.DataFrame(events)
    out["date"] = _dateify(out["date"])
    out["cost"] = pd.to_numeric(out["cost"], errors="coerce").fillna(0.0)
    return out.dropna(subset=["date"])


def _apply_costs_to_equity(daily_equity: pd.DataFrame, cost_events: pd.DataFrame) -> pd.DataFrame:
    if daily_equity.empty:
        return pd.DataFrame(columns=["date", "equity", "daily_cost", "cumulative_cost", "adjusted_equity"])
    out = daily_equity.copy()
    out["date"] = _dateify(out["date"])
    out = out.sort_values("date").reset_index(drop=True)
    if not cost_events.empty:
        cost_by_day = cost_events.groupby("date", as_index=False)["cost"].sum().sort_values("date")
        out = out.merge(cost_by_day.rename(columns={"cost": "daily_cost"}), on="date", how="left")
        out["daily_cost"] = out["daily_cost"].fillna(0.0)
    else:
        out["daily_cost"] = 0.0
    out["cumulative_cost"] = out["daily_cost"].cumsum()
    out["adjusted_equity"] = out["equity"] - out["cumulative_cost"]
    return out


def _equity_metrics(equity: pd.Series, capital: float, years: float) -> dict[str, float]:
    equity = pd.to_numeric(equity, errors="coerce").dropna()
    if equity.empty:
        return {}
    returns = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    years = max(float(years), 1.0 / 365.25)
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
    monthly = equity.resample("ME").last().pct_change().dropna() if isinstance(equity.index, pd.DatetimeIndex) else pd.Series(dtype=float)
    yearly = equity.resample("YE").last().pct_change().dropna() if isinstance(equity.index, pd.DatetimeIndex) else pd.Series(dtype=float)
    return {
        "final_equity": final_equity,
        "total_return_pct": float(total_return_pct),
        "cagr_pct": float(cagr_pct),
        "maxdd_pct": float(maxdd_pct),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "calmar": float(calmar),
        "ann_vol_pct": float(ann_vol_pct),
        "worst_day_pct": float(returns.min() * 100.0) if not returns.empty else float("nan"),
        "worst_month_pct": float(monthly.min() * 100.0) if not monthly.empty else float("nan"),
        "worst_year_pct": float(yearly.min() * 100.0) if not yearly.empty else float("nan"),
    }


def _cost_totals(cost_events: pd.DataFrame) -> tuple[float, float, float]:
    if cost_events.empty:
        return 0.0, 0.0, 0.0
    total = float(cost_events["cost"].sum())
    crypto = float(cost_events.loc[cost_events["asset_class"] == "crypto", "cost"].sum())
    equity = float(cost_events.loc[cost_events["asset_class"] == "equity", "cost"].sum())
    return total, crypto, equity


def _stress_one(candidate_dir: Path, cost_case: CostCase, args: argparse.Namespace) -> tuple[dict[str, Any], pd.DataFrame]:
    trades = _read_csv(candidate_dir / "replay_trades.csv")
    daily = _read_csv(candidate_dir / "replay_daily.csv")
    summary = _read_json(candidate_dir / "replay_summary.json")
    realized = _realized_trades(trades)
    daily_equity = _normalize_daily_equity(daily)
    years = _infer_years(daily_equity, summary)
    events = _build_cost_events(realized, cost_case, args.fallback_notional)
    adjusted = _apply_costs_to_equity(daily_equity, events)
    total_cost, crypto_cost, equity_cost = _cost_totals(events)

    if adjusted.empty:
        metrics = {}
    else:
        metrics = _equity_metrics(adjusted.set_index("date")["adjusted_equity"], args.capital, years)

    raw_final_equity = _to_float(summary.get("final_equity"), _to_float(daily_equity["equity"].iloc[-1], args.capital) if not daily_equity.empty else args.capital)
    raw_return = _to_float(summary.get("total_return_pct_on_capital"), (raw_final_equity / args.capital - 1.0) * 100.0)
    raw_cagr = _to_float(summary.get("cagr_pct"), ((raw_final_equity / args.capital) ** (1.0 / years) - 1.0) * 100.0 if raw_final_equity > 0 else float("nan"))
    raw_maxdd = _to_float(summary.get("max_drawdown_pct_on_equity"), float("nan"))
    raw_sharpe = _to_float(summary.get("sharpe"), float("nan"))
    raw_sortino = _to_float(summary.get("sortino"), float("nan"))
    raw_calmar = _to_float(summary.get("calmar"), float("nan"))

    if cost_case.crypto_round_trip_bps == 0 and cost_case.equity_round_trip_bps == 0:
        metrics.update({
            "final_equity": raw_final_equity,
            "total_return_pct": raw_return,
            "cagr_pct": raw_cagr,
            "maxdd_pct": raw_maxdd,
            "sharpe": raw_sharpe,
            "sortino": raw_sortino,
            "calmar": raw_calmar,
        })

    adjusted_final = metrics.get("final_equity", float("nan"))
    adjusted_return = metrics.get("total_return_pct", float("nan"))
    adjusted_cagr = metrics.get("cagr_pct", float("nan"))
    return {
        "candidate": _candidate_name(candidate_dir),
        "candidate_dir": str(candidate_dir),
        "cost_case": cost_case.name,
        "crypto_fee_bps_per_side": cost_case.crypto_fee_bps_per_side,
        "crypto_slippage_bps_per_side": cost_case.crypto_slippage_bps_per_side,
        "equity_fee_bps_per_side": cost_case.equity_fee_bps_per_side,
        "equity_slippage_bps_per_side": cost_case.equity_slippage_bps_per_side,
        "crypto_round_trip_bps": cost_case.crypto_round_trip_bps,
        "equity_round_trip_bps": cost_case.equity_round_trip_bps,
        "realized_trades": int(len(realized)),
        "years": years,
        "raw_final_equity": raw_final_equity,
        "raw_cagr_pct": raw_cagr,
        "raw_return_pct": raw_return,
        "raw_maxdd_pct": raw_maxdd,
        "raw_sharpe": raw_sharpe,
        "raw_sortino": raw_sortino,
        "raw_calmar": raw_calmar,
        "total_cost": total_cost,
        "crypto_cost": crypto_cost,
        "equity_cost": equity_cost,
        "cost_drag_pct_of_start_capital": total_cost / args.capital * 100.0 if args.capital else float("nan"),
        "cost_drag_pct_of_raw_profit": total_cost / max(raw_final_equity - args.capital, 1e-9) * 100.0 if raw_final_equity > args.capital else float("nan"),
        "adjusted_final_equity": adjusted_final,
        "adjusted_return_pct": adjusted_return,
        "adjusted_cagr_pct": adjusted_cagr,
        "adjusted_maxdd_pct": metrics.get("maxdd_pct", float("nan")),
        "adjusted_sharpe": metrics.get("sharpe", float("nan")),
        "adjusted_sortino": metrics.get("sortino", float("nan")),
        "adjusted_calmar": metrics.get("calmar", float("nan")),
        "adjusted_ann_vol_pct": metrics.get("ann_vol_pct", float("nan")),
        "adjusted_worst_day_pct": metrics.get("worst_day_pct", float("nan")),
        "adjusted_worst_month_pct": metrics.get("worst_month_pct", float("nan")),
        "adjusted_worst_year_pct": metrics.get("worst_year_pct", float("nan")),
        "cagr_drag_pct_points": raw_cagr - adjusted_cagr,
        "return_drag_pct_points": raw_return - adjusted_return,
        "final_equity_drag": raw_final_equity - adjusted_final,
    }, adjusted


def _parse_custom_cases(values: list[str]) -> dict[str, CostCase]:
    cases: dict[str, CostCase] = {}
    for raw in values:
        # Format: name:crypto_fee:crypto_slip:equity_fee:equity_slip
        parts = raw.split(":")
        if len(parts) != 5:
            raise SystemExit(f"Invalid --custom-cost-case '{raw}'. Expected name:crypto_fee:crypto_slip:equity_fee:equity_slip")
        name, cf, cs, ef, es = parts
        cases[name] = CostCase(name, float(cf), float(cs), float(ef), float(es))
    return cases


def _print_table(df: pd.DataFrame) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print("  TRADE IDEA CANDIDATE — ASSET-CLASS COST / SLIPPAGE STRESS")
    print("=" * DISPLAY_WIDTH)
    if df.empty:
        print("  No rows.")
        return
    view = df.copy()
    view["sort_crypto_rt"] = view["crypto_round_trip_bps"]
    view["sort_equity_rt"] = view["equity_round_trip_bps"]
    view = view.sort_values(["sort_crypto_rt", "sort_equity_rt", "candidate"])
    print(
        f"  {'Candidate':<31} {'CostCase':<29} {'Crt':>6} {'Ert':>6} {'Trades':>7} "
        f"{'RawCAGR':>8} {'AdjCAGR':>8} {'AdjRet':>8} {'AdjDD':>8} {'Sharpe':>8} {'Calmar':>8} "
        f"{'Cost':>10} {'CryptoC':>10} {'EquityC':>10} {'FinalEq':>12}"
    )
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('candidate')):<31} {str(r.get('cost_case')):<29} "
            f"{_fmt(r.get('crypto_round_trip_bps'), 1):>6} {_fmt(r.get('equity_round_trip_bps'), 1):>6} {int(r.get('realized_trades') or 0):>7} "
            f"{_fmt(r.get('raw_cagr_pct')):>8} {_fmt(r.get('adjusted_cagr_pct')):>8} {_fmt(r.get('adjusted_return_pct')):>8} {_fmt(r.get('adjusted_maxdd_pct')):>8} "
            f"{_fmt(r.get('adjusted_sharpe'), 3):>8} {_fmt(r.get('adjusted_calmar'), 3):>8} "
            f"${_to_float(r.get('total_cost')):>9,.0f} ${_to_float(r.get('crypto_cost')):>9,.0f} ${_to_float(r.get('equity_cost')):>9,.0f} ${_to_float(r.get('adjusted_final_equity')):>11,.0f}"
        )
    print("=" * DISPLAY_WIDTH)


def _print_decision_snapshot(df: pd.DataFrame) -> None:
    if df.empty:
        return
    print("\nDECISION SNAPSHOT")
    for case, g in df.groupby("cost_case", sort=False):
        g = g.copy()
        for col in ["adjusted_cagr_pct", "adjusted_calmar", "adjusted_maxdd_pct"]:
            g[col] = pd.to_numeric(g[col], errors="coerce")
        best_cagr = g.sort_values("adjusted_cagr_pct", ascending=False).head(1)
        best_calmar = g.sort_values("adjusted_calmar", ascending=False).head(1)
        if not best_cagr.empty:
            r = best_cagr.iloc[0]
            print(f"  {case:<29} best CAGR  : {r['candidate']} | CAGR={_fmt(r['adjusted_cagr_pct'])}% MaxDD={_fmt(r['adjusted_maxdd_pct'])}% Calmar={_fmt(r['adjusted_calmar'], 3)}")
        if not best_calmar.empty:
            r = best_calmar.iloc[0]
            print(f"  {case:<29} best Calmar: {r['candidate']} | CAGR={_fmt(r['adjusted_cagr_pct'])}% MaxDD={_fmt(r['adjusted_maxdd_pct'])}% Calmar={_fmt(r['adjusted_calmar'], 3)}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stress trade idea candidate replay outputs for asset-class-specific fees/slippage")
    p.add_argument("--candidate-dirs", nargs="+", default=["artifacts/trade_idea_candidate_refinement/bucket_cap_60", "artifacts/trade_idea_candidate_refinement/looser_stop_12pct"])
    p.add_argument("--cost-cases", nargs="+", default=["none", "asset_base", "asset_conservative", "asset_equity_harsh", "asset_very_harsh"], choices=list(DEFAULT_COST_CASES.keys()))
    p.add_argument("--custom-cost-case", nargs="*", default=[], help="Custom cases as name:crypto_fee:crypto_slip:equity_fee:equity_slip")
    p.add_argument("--out-dir", default="artifacts/trade_idea_cost_stress")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fallback-notional", type=float, default=25_000.0)
    p.add_argument("--write-adjusted-daily", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    custom_cases = _parse_custom_cases(args.custom_cost_case)
    cases = [DEFAULT_COST_CASES[name] for name in args.cost_cases] + list(custom_cases.values())
    rows: list[dict[str, Any]] = []
    for candidate_dir_raw in args.candidate_dirs:
        candidate_dir = Path(candidate_dir_raw)
        for case in cases:
            row, adjusted = _stress_one(candidate_dir, case, args)
            rows.append(row)
            if args.write_adjusted_daily and not adjusted.empty:
                candidate_out = out_dir / row["candidate"]
                candidate_out.mkdir(parents=True, exist_ok=True)
                adjusted.to_csv(candidate_out / f"adjusted_daily_{case.name}.csv", index=False)
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "cost_stress_comparison.csv", index=False)
    (out_dir / "cost_stress_comparison.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    _print_table(df)
    _print_decision_snapshot(df)
    print(f"\n  Comparison CSV : {out_dir / 'cost_stress_comparison.csv'}")
    print(f"  Comparison JSON: {out_dir / 'cost_stress_comparison.json'}")
    if args.write_adjusted_daily:
        print(f"  Adjusted daily curves written under: {out_dir}")
    print("  Verdict        : ASSET-CLASS COST STRESS RESEARCH ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
