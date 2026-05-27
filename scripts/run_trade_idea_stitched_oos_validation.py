#!/usr/bin/env python
"""Build stitched out-of-sample validation curves for trade idea finalists.

This script validates the practical walk-forward question:

    If we selected a candidate using only the prior train window, then traded the
    selected candidate during the next test window, what would the combined OOS
    equity curve look like?

It also compares that stitched walk-forward curve against static benchmark
curves over the same OOS test windows:

- always primary_calmar
- always secondary_return
- always prior_current_core
- always crypto_only_benchmark

The script reads existing replay_daily.csv / replay_trades.csv artifacts, applies
asset-class-specific costs, performs train-window selection, stitches selected
OOS daily returns, and writes summary CSVs.

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
    "asset_base": CostCase("asset_base", 10.0, 20.0, 0.0, 2.0),
    "asset_conservative": CostCase("asset_conservative", 10.0, 20.0, 0.0, 5.0),
    "asset_equity_harsh": CostCase("asset_equity_harsh", 10.0, 20.0, 0.0, 10.0),
    "asset_very_harsh": CostCase("asset_very_harsh", 20.0, 30.0, 0.0, 5.0),
}

DEFAULT_CANDIDATES = {
    "primary_calmar": "artifacts/trade_idea_cost_aware_universe_pruning/looser_stop_12pct_max_new_3__crypto_plus_growth_plus_macro_liquid",
    "secondary_return": "artifacts/trade_idea_cost_aware_universe_pruning/looser_stop_12pct_max_new_3__remove_splv",
    "prior_current_core": "artifacts/trade_idea_cost_aware_universe_pruning/looser_stop_12pct_max_new_3__current_core",
    "crypto_only_benchmark": "artifacts/trade_idea_cost_aware_universe_pruning/looser_stop_12pct_max_new_3__crypto_only",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _dateify(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.tz_localize(None)


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
    out = out.dropna(subset=["date", "equity"]).sort_values("date").drop_duplicates("date", keep="last")
    return out.reset_index(drop=True)


def _realized_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty or "status" not in trades.columns:
        return pd.DataFrame()
    out = trades[trades["status"].astype(str).isin(REALIZED_STATUSES)].copy()
    for col in ["notional", "realized_pnl", "realized_return_pct"]:
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
    out = pd.DataFrame(events)
    if out.empty:
        return pd.DataFrame(columns=["date", "cost", "asset_class"])
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
    out["daily_return"] = out["adjusted_equity"].pct_change().fillna(0.0)
    return out


def _load_candidate(label: str, path: Path, case: CostCase, fallback_notional: float) -> pd.DataFrame:
    daily = _read_csv(path / "replay_daily.csv")
    trades = _read_csv(path / "replay_trades.csv")
    realized = _realized_trades(trades)
    events = _cost_events(realized, case, fallback_notional)
    adjusted = _adjusted_daily(daily, events)
    if adjusted.empty:
        return adjusted
    adjusted = adjusted.copy()
    adjusted["candidate"] = label
    return adjusted


def _parse_candidates(values: list[str]) -> dict[str, Path]:
    if not values:
        return {k: Path(v) for k, v in DEFAULT_CANDIDATES.items()}
    out: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise SystemExit(f"Invalid --candidate '{raw}'. Expected label=path")
        label, path = raw.split("=", 1)
        out[label.strip()] = Path(path.strip())
    return out


def _metrics_for_equity(equity: pd.Series, capital: float | None = None) -> dict[str, float]:
    equity = pd.to_numeric(equity, errors="coerce").dropna()
    if equity.empty:
        return {
            "return_pct": float("nan"),
            "cagr_pct": float("nan"),
            "maxdd_pct": float("nan"),
            "sharpe": float("nan"),
            "sortino": float("nan"),
            "calmar": float("nan"),
            "final_equity": float("nan"),
            "worst_day_pct": float("nan"),
        }
    start = float(capital) if capital is not None else float(equity.iloc[0])
    final = float(equity.iloc[-1])
    if isinstance(equity.index, pd.DatetimeIndex):
        days = max((equity.index[-1] - equity.index[0]).days, 1)
    else:
        days = max(len(equity), 1)
    years = max(days / 365.25, 1.0 / 365.25)
    ret_pct = (final / start - 1.0) * 100.0 if start else float("nan")
    cagr_pct = ((final / start) ** (1.0 / years) - 1.0) * 100.0 if start > 0 and final > 0 else float("nan")
    dd = equity / equity.cummax() - 1.0
    maxdd_pct = float(dd.min() * 100.0)
    returns = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    vol = returns.std(ddof=0)
    sharpe = float(returns.mean() / vol * math.sqrt(TRADING_DAYS)) if len(returns) > 1 and vol > 0 else float("nan")
    downside = returns[returns < 0]
    downside_vol = downside.std(ddof=0)
    sortino = float(returns.mean() / downside_vol * math.sqrt(TRADING_DAYS)) if len(downside) > 1 and downside_vol > 0 else float("nan")
    calmar = cagr_pct / abs(maxdd_pct) if maxdd_pct < 0 else float("nan")
    return {
        "return_pct": ret_pct,
        "cagr_pct": cagr_pct,
        "maxdd_pct": maxdd_pct,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "final_equity": final,
        "worst_day_pct": float(returns.min() * 100.0) if not returns.empty else float("nan"),
    }


def _score(metrics: dict[str, float], metric: str) -> float:
    if metric == "calmar":
        return _to_float(metrics.get("calmar"), float("-inf"))
    if metric == "sharpe":
        return _to_float(metrics.get("sharpe"), float("-inf"))
    if metric == "cagr":
        return _to_float(metrics.get("cagr_pct"), float("-inf"))
    if metric == "return":
        return _to_float(metrics.get("return_pct"), float("-inf"))
    if metric == "composite":
        cagr = _to_float(metrics.get("cagr_pct"), -999.0)
        sharpe = _to_float(metrics.get("sharpe"), -999.0)
        maxdd = abs(_to_float(metrics.get("maxdd_pct"), 999.0))
        return cagr + 5.0 * sharpe - 0.5 * maxdd
    raise SystemExit(f"Unknown selection metric: {metric}")


def _slice_candidate(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if df.empty:
        return df
    sub = df[(df["date"] >= start) & (df["date"] <= end)].copy()
    return sub.sort_values("date")


def _equity_from_slice(sub: pd.DataFrame) -> pd.Series:
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.set_index("date")["adjusted_equity"].sort_index()


def _window_rows(start: pd.Timestamp, end: pd.Timestamp, train_years: int, test_years: int, step_years: int) -> list[dict[str, pd.Timestamp]]:
    rows = []
    train_start = start
    while True:
        train_end = train_start + pd.DateOffset(years=train_years) - pd.DateOffset(days=1)
        test_start = train_end + pd.DateOffset(days=1)
        test_end = test_start + pd.DateOffset(years=test_years) - pd.DateOffset(days=1)
        if test_end > end:
            break
        rows.append({"train_start": train_start, "train_end": train_end, "test_start": test_start, "test_end": test_end})
        train_start = train_start + pd.DateOffset(years=step_years)
    return rows


def _select_candidate(loaded: dict[str, pd.DataFrame], window: dict[str, pd.Timestamp], metric: str) -> tuple[str, list[dict[str, Any]]]:
    rows = []
    best_label = ""
    best_score = float("-inf")
    for label, df in loaded.items():
        train = _slice_candidate(df, window["train_start"], window["train_end"])
        eq = _equity_from_slice(train)
        if eq.empty:
            continue
        metrics = _metrics_for_equity(eq)
        score = _score(metrics, metric)
        rows.append({"candidate": label, "selection_score": score, **metrics})
        if score > best_score:
            best_score = score
            best_label = label
    if not best_label:
        raise RuntimeError(f"No candidate could be selected for window {window}")
    return best_label, rows


def _stitch_daily_returns(loaded: dict[str, pd.DataFrame], windows: list[dict[str, pd.Timestamp]], metric: str, capital: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stitched_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    train_score_rows: list[dict[str, Any]] = []
    current_equity = capital

    for i, window in enumerate(windows, start=1):
        selected, score_rows = _select_candidate(loaded, window, metric)
        for row in score_rows:
            train_score_rows.append({"window": i, **window, **row})
        selection_rows.append({"window": i, "selected_candidate": selected, **window})
        test = _slice_candidate(loaded[selected], window["test_start"], window["test_end"])
        if test.empty:
            continue
        first = True
        for _, row in test.iterrows():
            r = 0.0 if first else _to_float(row.get("daily_return"), 0.0)
            first = False
            current_equity *= (1.0 + r)
            stitched_rows.append({
                "date": row["date"],
                "window": i,
                "selected_candidate": selected,
                "daily_return": r,
                "stitched_equity": current_equity,
            })
    return pd.DataFrame(stitched_rows), pd.DataFrame(selection_rows), pd.DataFrame(train_score_rows)


def _static_oos_curve(label: str, df: pd.DataFrame, windows: list[dict[str, pd.Timestamp]], capital: float) -> pd.DataFrame:
    rows = []
    current_equity = capital
    for i, window in enumerate(windows, start=1):
        test = _slice_candidate(df, window["test_start"], window["test_end"])
        if test.empty:
            continue
        first = True
        for _, row in test.iterrows():
            r = 0.0 if first else _to_float(row.get("daily_return"), 0.0)
            first = False
            current_equity *= (1.0 + r)
            rows.append({"date": row["date"], "candidate": label, "window": i, "daily_return": r, "stitched_equity": current_equity})
    return pd.DataFrame(rows)


def _oos_window_scores(loaded: dict[str, pd.DataFrame], windows: list[dict[str, pd.Timestamp]]) -> pd.DataFrame:
    rows = []
    for i, window in enumerate(windows, start=1):
        for label, df in loaded.items():
            test = _slice_candidate(df, window["test_start"], window["test_end"])
            eq = _equity_from_slice(test)
            if eq.empty:
                continue
            metrics = _metrics_for_equity(eq)
            rows.append({"window": i, "candidate": label, **window, **metrics})
    return pd.DataFrame(rows)


def _annual_returns_from_curve(curve: pd.DataFrame, equity_col: str, label_col: str | None = None) -> pd.DataFrame:
    if curve.empty:
        return pd.DataFrame()
    rows = []
    if label_col is None:
        groups = [("stitched_walk_forward", curve)]
    else:
        groups = list(curve.groupby(label_col))
    for label, sub in groups:
        s = sub.sort_values("date").set_index("date")[equity_col]
        year_end = s.resample("YE").last().dropna()
        prior = None
        for dt, end_eq in year_end.items():
            if prior is None:
                year_slice = s[s.index.year == dt.year]
                start_eq = float(year_slice.iloc[0]) if not year_slice.empty else float(s.iloc[0])
            else:
                start_eq = float(prior)
            ret = (float(end_eq) / start_eq - 1.0) * 100.0 if start_eq else float("nan")
            rows.append({"curve": label, "year": int(dt.year), "return_pct": ret, "starting_equity": start_eq, "ending_equity": float(end_eq)})
            prior = float(end_eq)
    return pd.DataFrame(rows)


def _summary_row(label: str, curve: pd.DataFrame, equity_col: str, capital: float) -> dict[str, Any]:
    if curve.empty:
        return {"curve": label}
    eq = curve.sort_values("date").set_index("date")[equity_col]
    metrics = _metrics_for_equity(eq, capital=capital)
    return {"curve": label, "days": int(len(eq)), **metrics}


def _write_markdown(path: Path, summary: pd.DataFrame, selections: pd.DataFrame, annual: pd.DataFrame) -> None:
    lines = ["# Trade Idea Stitched OOS Validation\n", "Research-only stitched OOS validation. No runtime/broker/live execution code is modified.\n"]
    lines.append("## Summary\n")
    lines.append(summary.to_csv(index=False))
    lines.append("\n## Walk-Forward Selections\n")
    lines.append(selections.to_csv(index=False))
    lines.append("\n## Annual Returns\n")
    lines.append(annual.to_csv(index=False))
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Build stitched OOS validation curve for trade idea finalists")
    p.add_argument("--candidate", action="append", default=[], help="Candidate as label=path. Repeatable. Defaults to finalist set.")
    p.add_argument("--cost-case", default="asset_base", choices=list(DEFAULT_COST_CASES.keys()))
    p.add_argument("--selection-metric", default="calmar", choices=["calmar", "sharpe", "cagr", "return", "composite"])
    p.add_argument("--out-dir", default="artifacts/trade_idea_stitched_oos_validation")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--train-years", type=int, default=2)
    p.add_argument("--test-years", type=int, default=1)
    p.add_argument("--step-years", type=int, default=1)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fallback-notional", type=float, default=25_000.0)
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    case = DEFAULT_COST_CASES[args.cost_case]
    candidates = _parse_candidates(args.candidate)
    loaded = {label: _load_candidate(label, path, case, args.fallback_notional) for label, path in candidates.items()}
    windows = _window_rows(pd.Timestamp(args.start), pd.Timestamp(args.end), args.train_years, args.test_years, args.step_years)

    stitched, selections, train_scores = _stitch_daily_returns(loaded, windows, args.selection_metric, args.capital)
    oos_scores = _oos_window_scores(loaded, windows)
    static_curves = pd.concat([_static_oos_curve(label, df, windows, args.capital) for label, df in loaded.items()], ignore_index=True)

    summary_rows = [_summary_row("stitched_walk_forward", stitched, "stitched_equity", args.capital)]
    if not static_curves.empty:
        for label, sub in static_curves.groupby("candidate"):
            summary_rows.append(_summary_row(f"always_{label}", sub, "stitched_equity", args.capital))
    summary = pd.DataFrame(summary_rows).sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    annual = pd.concat([
        _annual_returns_from_curve(stitched, "stitched_equity"),
        _annual_returns_from_curve(static_curves, "stitched_equity", label_col="candidate"),
    ], ignore_index=True)

    stitched.to_csv(out_dir / "stitched_walk_forward_daily.csv", index=False)
    selections.to_csv(out_dir / "walk_forward_selections.csv", index=False)
    train_scores.to_csv(out_dir / "walk_forward_train_scores.csv", index=False)
    oos_scores.to_csv(out_dir / "all_candidate_oos_window_scores.csv", index=False)
    static_curves.to_csv(out_dir / "static_benchmark_oos_daily.csv", index=False)
    summary.to_csv(out_dir / "stitched_oos_summary.csv", index=False)
    annual.to_csv(out_dir / "stitched_oos_annual_returns.csv", index=False)
    (out_dir / "stitched_oos_validation_summary.json").write_text(json.dumps({
        "cost_case": args.cost_case,
        "selection_metric": args.selection_metric,
        "train_years": args.train_years,
        "test_years": args.test_years,
        "step_years": args.step_years,
        "capital": args.capital,
        "candidates": {label: str(path) for label, path in candidates.items()},
        "outputs": {
            "stitched_daily": str(out_dir / "stitched_walk_forward_daily.csv"),
            "summary": str(out_dir / "stitched_oos_summary.csv"),
            "annual_returns": str(out_dir / "stitched_oos_annual_returns.csv"),
            "selections": str(out_dir / "walk_forward_selections.csv"),
            "train_scores": str(out_dir / "walk_forward_train_scores.csv"),
            "oos_scores": str(out_dir / "all_candidate_oos_window_scores.csv"),
            "static_benchmark_daily": str(out_dir / "static_benchmark_oos_daily.csv"),
        },
    }, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir / "stitched_oos_report.md", summary, selections, annual)

    print("\n" + "=" * 170)
    print("  TRADE IDEA STITCHED OOS VALIDATION — SUMMARY")
    print("=" * 170)
    if summary.empty:
        print("  No summary rows.")
    else:
        print(f"  {'Curve':<34} {'Days':>6} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'WorstDay':>9} {'FinalEq':>12}")
        for _, r in summary.iterrows():
            print(
                f"  {str(r.get('curve')):<34} {int(_to_float(r.get('days'), 0)):>6} "
                f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
                f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('sortino'), 3):>8} {_fmt(r.get('calmar'), 3):>8} "
                f"{_fmt(r.get('worst_day_pct')):>9} {_money(r.get('final_equity')):>12}"
            )
    print("-" * 170)
    print("  Selections:")
    if selections.empty:
        print("    none")
    else:
        for _, r in selections.iterrows():
            print(
                f"    Window {int(r['window'])}: {r['selected_candidate']} | "
                f"train {pd.Timestamp(r['train_start']).date()}->{pd.Timestamp(r['train_end']).date()} | "
                f"test {pd.Timestamp(r['test_start']).date()}->{pd.Timestamp(r['test_end']).date()}"
            )
    print("=" * 170)
    print(f"  Outputs: {out_dir}")
    print("  Verdict: STITCHED OOS VALIDATION ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
