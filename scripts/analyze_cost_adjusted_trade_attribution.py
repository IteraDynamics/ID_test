#!/usr/bin/env python
"""Analyze cost-adjusted trade attribution for trade idea replay candidates.

This script reads one or more replay candidate directories containing
`replay_trades.csv` and attributes gross and post-cost PnL by dimensions such as
Ticker, bucket, setup, status, year, and interaction groups.

It supports both flat cost cases and asset-class-specific cost cases so crypto
can be charged Coinbase-style friction while listed ETFs/equities use lower
retail-platform friction.

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


REALIZED_STATUSES = {"target_hit", "stop_hit", "expired", "manual_closed"}
DISPLAY_WIDTH = 190
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
    "mild": CostCase("mild", 2.0, 5.0, 2.0, 5.0),
    "realistic": CostCase("realistic", 5.0, 10.0, 5.0, 10.0),
    "harsh": CostCase("harsh", 10.0, 20.0, 10.0, 20.0),
    "very_harsh": CostCase("very_harsh", 20.0, 30.0, 20.0, 30.0),
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


def _candidate_name(path: Path) -> str:
    return path.name.replace(" ", "_")


def _parse_custom_cases(values: list[str]) -> dict[str, CostCase]:
    cases: dict[str, CostCase] = {}
    for raw in values:
        parts = raw.split(":")
        if len(parts) != 5:
            raise SystemExit(f"Invalid --custom-cost-case '{raw}'. Expected name:crypto_fee:crypto_slip:equity_fee:equity_slip")
        name, cf, cs, ef, es = parts
        cases[name] = CostCase(name, float(cf), float(cs), float(ef), float(es))
    return cases


def _find_column(df: pd.DataFrame, candidates: list[str], fallback: str | None = None) -> str | None:
    lower_map = {str(c).lower().strip(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return fallback


def _is_crypto(ticker: str, bucket: str) -> bool:
    t = str(ticker).upper()
    b = str(bucket).lower()
    return t in CRYPTO_TICKERS or t.endswith("-USD") or b == "crypto"


def _prepare_trades(candidate_dir: Path, cost_case: CostCase, fallback_notional: float, capital: float) -> pd.DataFrame:
    trades = _read_csv(candidate_dir / "replay_trades.csv")
    if trades.empty:
        return pd.DataFrame()

    status_col = _find_column(trades, ["status"])
    if status_col is None:
        return pd.DataFrame()

    out = trades[trades[status_col].astype(str).isin(REALIZED_STATUSES)].copy()
    if out.empty:
        return out

    out["candidate"] = _candidate_name(candidate_dir)
    out["cost_case"] = cost_case.name

    ticker_col = _find_column(out, ["ticker", "symbol", "asset"])
    bucket_col = _find_column(out, ["bucket", "asset_bucket", "group"])
    setup_col = _find_column(out, ["setup", "signal_setup", "signal_type", "strategy"])
    pnl_col = _find_column(out, ["realized_pnl", "pnl", "gross_pnl"])
    ret_col = _find_column(out, ["realized_return_pct", "return_pct", "ret_pct"])
    notional_col = _find_column(out, ["notional", "position_notional", "entry_notional"])
    score_col = _find_column(out, ["score", "priority_score"])
    exit_date_col = _find_column(out, ["exit_date", "closed_date", "date"])
    entry_date_col = _find_column(out, ["entry_date", "activation_date", "created_date"])
    days_col = _find_column(out, ["days_open", "holding_days", "duration_days"])

    out["ticker"] = out[ticker_col].astype(str) if ticker_col else "unknown"
    out["bucket"] = out[bucket_col].astype(str) if bucket_col else "unknown"
    out["setup"] = out[setup_col].astype(str) if setup_col else "unknown"
    out["status"] = out[status_col].astype(str)
    out["asset_class"] = out.apply(lambda r: "crypto" if _is_crypto(r["ticker"], r["bucket"]) else "equity", axis=1)
    out["gross_pnl"] = pd.to_numeric(out[pnl_col], errors="coerce").fillna(0.0) if pnl_col else 0.0
    out["realized_return_pct"] = pd.to_numeric(out[ret_col], errors="coerce") if ret_col else pd.NA
    out["score"] = pd.to_numeric(out[score_col], errors="coerce") if score_col else pd.NA
    out["days_open"] = pd.to_numeric(out[days_col], errors="coerce") if days_col else pd.NA

    if notional_col:
        out["notional"] = pd.to_numeric(out[notional_col], errors="coerce")
    else:
        out["notional"] = pd.NA

    missing_notional = out["notional"].isna() | (out["notional"] <= 0)
    if ret_col:
        ret_abs = out["realized_return_pct"].abs() / 100.0
        inferred = out["gross_pnl"].abs() / ret_abs.replace(0, pd.NA)
        out.loc[missing_notional, "notional"] = inferred[missing_notional]
    out["notional"] = pd.to_numeric(out["notional"], errors="coerce").fillna(float(fallback_notional))

    out["per_side_bps"] = out["asset_class"].map({"crypto": cost_case.crypto_per_side_bps, "equity": cost_case.equity_per_side_bps})
    out["entry_cost"] = out["notional"] * (out["per_side_bps"] / 10_000.0)
    out["exit_cost"] = out["notional"] * (out["per_side_bps"] / 10_000.0)
    out["total_cost"] = out["entry_cost"] + out["exit_cost"]
    out["net_pnl"] = out["gross_pnl"] - out["total_cost"]
    out["net_return_pct"] = out["net_pnl"] / out["notional"] * 100.0
    out["gross_pnl_pct_capital"] = out["gross_pnl"] / capital * 100.0 if capital else pd.NA
    out["net_pnl_pct_capital"] = out["net_pnl"] / capital * 100.0 if capital else pd.NA

    if exit_date_col:
        out["exit_date"] = pd.to_datetime(out[exit_date_col], errors="coerce").dt.tz_localize(None)
    elif entry_date_col:
        out["exit_date"] = pd.to_datetime(out[entry_date_col], errors="coerce").dt.tz_localize(None)
    else:
        out["exit_date"] = pd.NaT

    out["year"] = out["exit_date"].dt.year.astype("Int64").astype(str).replace("<NA>", "unknown")
    out["month"] = out["exit_date"].dt.to_period("M").astype(str).replace("NaT", "unknown")
    return out


def _summary_table(df: pd.DataFrame, group_cols: list[str], capital: float) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.groupby(group_cols, dropna=False)
    rows = []
    total_net = float(df["net_pnl"].sum())
    total_gross = float(df["gross_pnl"].sum())
    for keys, sub in g:
        if not isinstance(keys, tuple):
            keys = (keys,)
        gross = float(sub["gross_pnl"].sum())
        cost = float(sub["total_cost"].sum())
        net = float(sub["net_pnl"].sum())
        trades = int(len(sub))
        wins = int((sub["net_pnl"] > 0).sum())
        row = {col: key for col, key in zip(group_cols, keys)}
        row.update({
            "trades": trades,
            "wins": wins,
            "losses": int((sub["net_pnl"] <= 0).sum()),
            "win_rate_pct": wins / trades * 100.0 if trades else 0.0,
            "target_hits": int((sub["status"] == "target_hit").sum()),
            "stop_hits": int((sub["status"] == "stop_hit").sum()),
            "expired": int((sub["status"] == "expired").sum()),
            "gross_pnl": gross,
            "total_cost": cost,
            "crypto_cost": float(sub.loc[sub["asset_class"] == "crypto", "total_cost"].sum()),
            "equity_cost": float(sub.loc[sub["asset_class"] == "equity", "total_cost"].sum()),
            "net_pnl": net,
            "gross_pnl_pct_capital": gross / capital * 100.0 if capital else float("nan"),
            "cost_pct_capital": cost / capital * 100.0 if capital else float("nan"),
            "net_pnl_pct_capital": net / capital * 100.0 if capital else float("nan"),
            "avg_gross_pnl": gross / trades if trades else 0.0,
            "avg_cost": cost / trades if trades else 0.0,
            "avg_net_pnl": net / trades if trades else 0.0,
            "avg_net_return_pct": float(sub["net_return_pct"].mean()),
            "median_net_return_pct": float(sub["net_return_pct"].median()),
            "avg_days_open": float(sub["days_open"].mean()) if "days_open" in sub else float("nan"),
            "avg_score": float(sub["score"].mean()) if "score" in sub else float("nan"),
            "net_share_of_total_net_pct": net / total_net * 100.0 if abs(total_net) > 1e-9 else float("nan"),
            "gross_share_of_total_gross_pct": gross / total_gross * 100.0 if abs(total_gross) > 1e-9 else float("nan"),
            "cost_as_pct_of_gross_pnl": cost / gross * 100.0 if abs(gross) > 1e-9 else float("nan"),
        })
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.sort_values("net_pnl", ascending=False) if not out.empty else out


def _write_table(df: pd.DataFrame, out_dir: Path, name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / f"{name}.csv", index=False)
    (out_dir / f"{name}.json").write_text(df.to_json(orient="records", indent=2), encoding="utf-8")


def _print_top_bottom(title: str, df: pd.DataFrame, label_cols: list[str], top_n: int) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print(f"  {title}")
    print("=" * DISPLAY_WIDTH)
    if df.empty:
        print("  No rows.")
        return
    def label(row: pd.Series) -> str:
        return " / ".join(str(row.get(c, "")) for c in label_cols)
    view = df.sort_values("net_pnl", ascending=False)
    print(f"  {'Group':<50} {'Trades':>7} {'NetPnL':>12} {'Gross':>12} {'Cost':>10} {'Win%':>8} {'AvgNet':>10} {'AvgRet':>8} {'Target':>7} {'Stop':>6} {'Exp':>6}")
    for _, r in view.head(top_n).iterrows():
        print(f"  {label(r):<50} {int(r.get('trades') or 0):>7} {_money(r.get('net_pnl')):>12} {_money(r.get('gross_pnl')):>12} {_money(r.get('total_cost')):>10} {_fmt(r.get('win_rate_pct')):>8} {_money(r.get('avg_net_pnl')):>10} {_fmt(r.get('avg_net_return_pct')):>8} {int(r.get('target_hits') or 0):>7} {int(r.get('stop_hits') or 0):>6} {int(r.get('expired') or 0):>6}")
    print("  " + "-" * (DISPLAY_WIDTH - 2))
    for _, r in view.tail(top_n).sort_values("net_pnl", ascending=True).iterrows():
        print(f"  {label(r):<50} {int(r.get('trades') or 0):>7} {_money(r.get('net_pnl')):>12} {_money(r.get('gross_pnl')):>12} {_money(r.get('total_cost')):>10} {_fmt(r.get('win_rate_pct')):>8} {_money(r.get('avg_net_pnl')):>10} {_fmt(r.get('avg_net_return_pct')):>8} {int(r.get('target_hits') or 0):>7} {int(r.get('stop_hits') or 0):>6} {int(r.get('expired') or 0):>6}")


def _print_candidate_rollup(df: pd.DataFrame, capital: float) -> None:
    roll = _summary_table(df, ["candidate", "cost_case"], capital=capital)
    print("\n" + "=" * DISPLAY_WIDTH)
    print("  ASSET-CLASS COST-ADJUSTED TRADE ATTRIBUTION — CANDIDATE ROLLUP")
    print("=" * DISPLAY_WIDTH)
    if roll.empty:
        print("  No rows.")
        return
    print(f"  {'Candidate':<38} {'CostCase':<29} {'Trades':>7} {'NetPnL':>12} {'Gross':>12} {'Cost':>10} {'CryptoC':>9} {'EquityC':>9} {'Win%':>8} {'AvgNet':>10} {'Target':>7} {'Stop':>6} {'Exp':>6}")
    for _, r in roll.sort_values(["cost_case", "net_pnl"], ascending=[True, False]).iterrows():
        print(f"  {str(r.get('candidate')):<38} {str(r.get('cost_case')):<29} {int(r.get('trades') or 0):>7} {_money(r.get('net_pnl')):>12} {_money(r.get('gross_pnl')):>12} {_money(r.get('total_cost')):>10} {_money(r.get('crypto_cost')):>9} {_money(r.get('equity_cost')):>9} {_fmt(r.get('win_rate_pct')):>8} {_money(r.get('avg_net_pnl')):>10} {int(r.get('target_hits') or 0):>7} {int(r.get('stop_hits') or 0):>6} {int(r.get('expired') or 0):>6}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze asset-class-specific cost-adjusted trade attribution")
    p.add_argument("--candidate-dirs", nargs="+", default=["artifacts/trade_idea_turnover_sweep/looser_stop_12pct__max_new_3", "artifacts/trade_idea_turnover_sweep/bucket_cap_60__max_new_3"])
    p.add_argument("--cost-cases", nargs="+", default=["asset_base", "asset_conservative", "asset_very_harsh"], choices=list(DEFAULT_COST_CASES.keys()))
    p.add_argument("--custom-cost-case", nargs="*", default=[], help="Custom cases as name:crypto_fee:crypto_slip:equity_fee:equity_slip")
    p.add_argument("--out-dir", default="artifacts/trade_idea_cost_attribution")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fallback-notional", type=float, default=25_000.0)
    p.add_argument("--top-n", type=int, default=12)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    custom_cases = _parse_custom_cases(args.custom_cost_case)
    cases = [DEFAULT_COST_CASES[name] for name in args.cost_cases] + list(custom_cases.values())
    all_rows: list[pd.DataFrame] = []
    for candidate_raw in args.candidate_dirs:
        candidate_dir = Path(candidate_raw)
        for case in cases:
            trades = _prepare_trades(candidate_dir, case, args.fallback_notional, args.capital)
            if not trades.empty:
                all_rows.append(trades)
    if not all_rows:
        print("No realized trades found in candidate dirs.")
        return
    trades_all = pd.concat(all_rows, ignore_index=True)
    trades_all.to_csv(out_dir / "cost_adjusted_trades.csv", index=False)
    dimensions = {
        "by_candidate": ["candidate", "cost_case"],
        "by_asset_class": ["candidate", "cost_case", "asset_class"],
        "by_ticker": ["candidate", "cost_case", "ticker"],
        "by_bucket": ["candidate", "cost_case", "bucket"],
        "by_setup": ["candidate", "cost_case", "setup"],
        "by_status": ["candidate", "cost_case", "status"],
        "by_year": ["candidate", "cost_case", "year"],
        "by_month": ["candidate", "cost_case", "month"],
        "by_ticker_setup": ["candidate", "cost_case", "ticker", "setup"],
        "by_bucket_setup": ["candidate", "cost_case", "bucket", "setup"],
        "by_bucket_status": ["candidate", "cost_case", "bucket", "status"],
        "by_setup_status": ["candidate", "cost_case", "setup", "status"],
        "by_ticker_status": ["candidate", "cost_case", "ticker", "status"],
    }
    tables: dict[str, pd.DataFrame] = {}
    for name, cols in dimensions.items():
        table = _summary_table(trades_all, cols, args.capital)
        tables[name] = table
        _write_table(table, out_dir, name)
    summary = {"candidate_dirs": args.candidate_dirs, "cost_cases": [c.name for c in cases], "capital": args.capital, "fallback_notional": args.fallback_notional, "realized_trade_rows": int(len(trades_all)), "outputs": {name: str(out_dir / f"{name}.csv") for name in dimensions}}
    (out_dir / "cost_attribution_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _print_candidate_rollup(trades_all, args.capital)
    _print_top_bottom("BY ASSET CLASS", tables["by_asset_class"], ["candidate", "cost_case", "asset_class"], args.top_n)
    _print_top_bottom("BY TICKER", tables["by_ticker"], ["candidate", "cost_case", "ticker"], args.top_n)
    _print_top_bottom("BY BUCKET", tables["by_bucket"], ["candidate", "cost_case", "bucket"], args.top_n)
    _print_top_bottom("BY SETUP", tables["by_setup"], ["candidate", "cost_case", "setup"], args.top_n)
    _print_top_bottom("BY EXIT / STATUS", tables["by_status"], ["candidate", "cost_case", "status"], args.top_n)
    _print_top_bottom("BY BUCKET + STATUS", tables["by_bucket_status"], ["candidate", "cost_case", "bucket", "status"], args.top_n)
    _print_top_bottom("BY TICKER + STATUS", tables["by_ticker_status"], ["candidate", "cost_case", "ticker", "status"], args.top_n)
    print(f"\n  Detailed trades CSV : {out_dir / 'cost_adjusted_trades.csv'}")
    print(f"  Summary JSON        : {out_dir / 'cost_attribution_summary.json'}")
    print(f"  Attribution tables  : {out_dir}")
    print("  Verdict             : ASSET-CLASS COST-ADJUSTED ATTRIBUTION ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
