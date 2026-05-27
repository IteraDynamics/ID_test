#!/usr/bin/env python
"""Run walk-forward finalist selection for trade idea replay candidates.

This runner uses existing replay outputs and performs a walk-forward selection:

1. Define rolling train/test date windows.
2. Score each candidate on the train window using adjusted post-cost equity.
3. Select the best candidate by a configurable metric.
4. Evaluate the selected candidate on the following out-of-sample test window.

It does not rerun the signal engine or broker/runtime code. It is a research
validation layer over already-generated replay_daily.csv / replay_trades.csv
artifacts.

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
    return out


def _metrics_for_equity(equity: pd.Series, start_equity: float | None = None) -> dict[str, float]:
    equity = pd.to_numeric(equity, errors="coerce").dropna()
    if equity.empty:
        return {"return_pct": float("nan"), "cagr_pct": float("nan"), "maxdd_pct": float("nan"), "sharpe": float("nan"), "calmar": float("nan"), "final_equity": float("nan")}
    start = float(start_equity) if start_equity is not None else float(equity.iloc[0])
    final = float(equity.iloc[-1])
    days = max((equity.index[-1] - equity.index[0]).days, 1) if hasattr(equity.index, "__iter__") else max(len(equity), 1)
    years = max(days / 365.25, 1.0 / 365.25)
    ret_pct = (final / start - 1.0) * 100.0 if start else float("nan")
    cagr_pct = ((final / start) ** (1.0 / years) - 1.0) * 100.0 if start > 0 and final > 0 else float("nan")
    dd = equity / equity.cummax() - 1.0
    maxdd_pct = float(dd.min() * 100.0)
    rets = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    vol = rets.std(ddof=0)
    sharpe = float(rets.mean() / vol * math.sqrt(TRADING_DAYS)) if len(rets) > 1 and vol > 0 else float("nan")
    calmar = cagr_pct / abs(maxdd_pct) if maxdd_pct < 0 else float("nan")
    return {"return_pct": ret_pct, "cagr_pct": cagr_pct, "maxdd_pct": maxdd_pct, "sharpe": sharpe, "calmar": calmar, "final_equity": final}


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


def _slice_equity(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    sub = df[(df["date"] >= start) & (df["date"] <= end)].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.set_index("date")["adjusted_equity"].sort_index()


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
        maxdd = abs(_to_float(metrics.get("maxdd_pct"), 999.0))
        sharpe = _to_float(metrics.get("sharpe"), -999.0)
        return cagr + 5.0 * sharpe - 0.5 * maxdd
    raise SystemExit(f"Unknown selection metric: {metric}")


def main() -> None:
    p = argparse.ArgumentParser(description="Run walk-forward finalist selection over replay outputs")
    p.add_argument("--candidate", action="append", default=[], help="Candidate as label=path. Repeatable. Defaults to finalist set.")
    p.add_argument("--cost-case", default="asset_base", choices=list(DEFAULT_COST_CASES.keys()))
    p.add_argument("--out-dir", default="artifacts/trade_idea_finalist_walk_forward")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--train-years", type=int, default=2)
    p.add_argument("--test-years", type=int, default=1)
    p.add_argument("--step-years", type=int, default=1)
    p.add_argument("--selection-metric", default="calmar", choices=["calmar", "sharpe", "cagr", "return", "composite"])
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fallback-notional", type=float, default=25_000.0)
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    case = DEFAULT_COST_CASES[args.cost_case]
    candidates = _parse_candidates(args.candidate)
    loaded = {label: _load_candidate(label, path, case, args.fallback_notional) for label, path in candidates.items()}

    windows = _window_rows(pd.Timestamp(args.start), pd.Timestamp(args.end), args.train_years, args.test_years, args.step_years)
    train_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []

    for i, w in enumerate(windows, start=1):
        scored: list[tuple[float, str, dict[str, float]]] = []
        for label, df in loaded.items():
            train_eq = _slice_equity(df, w["train_start"], w["train_end"])
            if train_eq.empty:
                continue
            train_metrics = _metrics_for_equity(train_eq)
            score = _score(train_metrics, args.selection_metric)
            train_rows.append({"window": i, "candidate": label, **{k: v for k, v in w.items()}, **train_metrics, "selection_score": score})
            scored.append((score, label, train_metrics))
        if not scored:
            continue
        scored.sort(reverse=True, key=lambda x: x[0])
        selected = scored[0][1]
        selected_rows.append({"window": i, "selected_candidate": selected, "selection_score": scored[0][0], **w})
        for label, df in loaded.items():
            test_eq = _slice_equity(df, w["test_start"], w["test_end"])
            if test_eq.empty:
                continue
            test_metrics = _metrics_for_equity(test_eq)
            test_rows.append({"window": i, "candidate": label, "selected": label == selected, **{k: v for k, v in w.items()}, **test_metrics})

    train_df = pd.DataFrame(train_rows)
    test_df = pd.DataFrame(test_rows)
    selected_df = pd.DataFrame(selected_rows)
    selected_test = test_df[test_df["selected"] == True].copy() if not test_df.empty else pd.DataFrame()

    train_df.to_csv(out_dir / "walk_forward_train_scores.csv", index=False)
    test_df.to_csv(out_dir / "walk_forward_test_scores.csv", index=False)
    selected_df.to_csv(out_dir / "walk_forward_selections.csv", index=False)
    selected_test.to_csv(out_dir / "walk_forward_selected_oos.csv", index=False)
    (out_dir / "walk_forward_summary.json").write_text(json.dumps({
        "cost_case": args.cost_case,
        "selection_metric": args.selection_metric,
        "train_years": args.train_years,
        "test_years": args.test_years,
        "step_years": args.step_years,
        "candidates": {k: str(v) for k, v in candidates.items()},
        "outputs": {
            "train_scores": str(out_dir / "walk_forward_train_scores.csv"),
            "test_scores": str(out_dir / "walk_forward_test_scores.csv"),
            "selections": str(out_dir / "walk_forward_selections.csv"),
            "selected_oos": str(out_dir / "walk_forward_selected_oos.csv"),
        },
    }, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 160)
    print("  TRADE IDEA FINALIST WALK-FORWARD — SELECTED OUT-OF-SAMPLE WINDOWS")
    print("=" * 160)
    if selected_test.empty:
        print("  No selected OOS rows.")
    else:
        print(f"  {'Win':>3} {'Selected':<28} {'Train':<23} {'Test':<23} {'Ret':>8} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>8} {'Calmar':>8} {'FinalEq':>12}")
        for _, r in selected_test.iterrows():
            train = f"{pd.Timestamp(r['train_start']).date()}->{pd.Timestamp(r['train_end']).date()}"
            test = f"{pd.Timestamp(r['test_start']).date()}->{pd.Timestamp(r['test_end']).date()}"
            print(
                f"  {int(r['window']):>3} {str(r['candidate']):<28} {train:<23} {test:<23} "
                f"{_fmt(r['return_pct']):>8} {_fmt(r['cagr_pct']):>8} {_fmt(r['maxdd_pct']):>8} {_fmt(r['sharpe'], 3):>8} {_fmt(r['calmar'], 3):>8} {float(r['final_equity']):>12,.0f}"
            )
        print("-" * 160)
        print(
            f"  Avg OOS return={_fmt(selected_test['return_pct'].mean())}% | "
            f"Median={_fmt(selected_test['return_pct'].median())}% | "
            f"Worst={_fmt(selected_test['return_pct'].min())}% | "
            f"Avg MaxDD={_fmt(selected_test['maxdd_pct'].mean())}% | "
            f"Positive windows={(selected_test['return_pct'] > 0).sum()}/{len(selected_test)}"
        )
    print("=" * 160)
    print(f"  Outputs: {out_dir}")
    print("  Verdict: WALK-FORWARD RESEARCH ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
