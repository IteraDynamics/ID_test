#!/usr/bin/env python
"""Validate core allocator policy sweep outputs.

This script is the first validation layer for the structural core allocator track.
It consumes the outputs produced by scripts/run_core_allocator_policy_sweep.py and
adds the same kind of validation funnel used for tactical sleeves:

- finalist summary
- corrected calendar-year returns
- rolling 3/6/12-month return diagnostics
- worst drawdown periods
- train/test walk-forward policy selection
- stitched OOS equity curve for the selected walk-forward policy
- static OOS benchmark curves for each policy over the same OOS windows

It does not re-run the policy sweep. It reads:

    core_allocator_policy_summary.csv
    core_allocator_daily_equity.csv
    core_allocator_daily_weights.csv optional

Research only. No broker/runtime/live execution code is modified.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

TRADING_DAYS = 252.0
DISPLAY_WIDTH = 190


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
            "ann_vol_pct": float("nan"),
            "worst_day_pct": float("nan"),
            "final_equity": float("nan"),
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
    rets = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    vol = rets.std(ddof=0)
    sharpe = float(rets.mean() / vol * math.sqrt(TRADING_DAYS)) if len(rets) > 1 and vol > 0 else float("nan")
    downside = rets[rets < 0]
    dvol = downside.std(ddof=0)
    sortino = float(rets.mean() / dvol * math.sqrt(TRADING_DAYS)) if len(downside) > 1 and dvol > 0 else float("nan")
    calmar = cagr_pct / abs(maxdd_pct) if maxdd_pct < 0 else float("nan")
    ann_vol_pct = float(vol * math.sqrt(TRADING_DAYS) * 100.0) if len(rets) > 1 else float("nan")
    return {
        "return_pct": ret_pct,
        "cagr_pct": cagr_pct,
        "maxdd_pct": maxdd_pct,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "ann_vol_pct": ann_vol_pct,
        "worst_day_pct": float(rets.min() * 100.0) if not rets.empty else float("nan"),
        "final_equity": final,
    }


def _load_daily(path: Path) -> pd.DataFrame:
    daily = _read_csv(path)
    if daily.empty:
        raise SystemExit(f"Missing or empty daily equity file: {path}")
    required = {"date", "policy", "equity"}
    missing = required - set(daily.columns)
    if missing:
        raise SystemExit(f"Daily equity file missing required columns {sorted(missing)}: {path}")
    daily = daily.copy()
    daily["date"] = _dateify(daily["date"])
    daily["equity"] = pd.to_numeric(daily["equity"], errors="coerce")
    daily["net_return"] = pd.to_numeric(daily.get("net_return", pd.Series(0.0, index=daily.index)), errors="coerce").fillna(0.0)
    daily = daily.dropna(subset=["date", "policy", "equity"]).sort_values(["policy", "date"])
    return daily


def _policy_equity(daily: pd.DataFrame, policy: str, start: pd.Timestamp | None = None, end: pd.Timestamp | None = None) -> pd.Series:
    sub = daily[daily["policy"] == policy].copy()
    if start is not None:
        sub = sub[sub["date"] >= start]
    if end is not None:
        sub = sub[sub["date"] <= end]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.sort_values("date").set_index("date")["equity"]


def _calendar_year_returns(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
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


def _monthly_returns(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for policy, sub in daily.groupby("policy"):
        s = sub.sort_values("date").set_index("date")["equity"]
        month_end = s.resample("ME").last().dropna()
        prior = None
        for dt, end_eq in month_end.items():
            if prior is None:
                month_slice = s[(s.index.year == dt.year) & (s.index.month == dt.month)]
                start_eq = float(month_slice.iloc[0]) if not month_slice.empty else float(s.iloc[0])
            else:
                start_eq = float(prior)
            rows.append({
                "policy": policy,
                "month": dt.strftime("%Y-%m"),
                "return_pct": (float(end_eq) / start_eq - 1.0) * 100.0 if start_eq else float("nan"),
                "starting_equity": start_eq,
                "ending_equity": float(end_eq),
            })
            prior = float(end_eq)
    return pd.DataFrame(rows)


def _rolling_returns(daily: pd.DataFrame, windows_months: list[int]) -> pd.DataFrame:
    rows = []
    for policy, sub in daily.groupby("policy"):
        s = sub.sort_values("date").set_index("date")["equity"].resample("D").last().ffill()
        for months in windows_months:
            days = int(round(months * 30.4375))
            rr = (s / s.shift(days) - 1.0).dropna() * 100.0
            if rr.empty:
                continue
            rows.append({
                "policy": policy,
                "window_months": months,
                "best_return_pct": float(rr.max()),
                "worst_return_pct": float(rr.min()),
                "median_return_pct": float(rr.median()),
                "positive_rate_pct": float((rr > 0).mean() * 100.0),
                "observations": int(len(rr)),
                "worst_end_date": rr.idxmin().strftime("%Y-%m-%d"),
                "best_end_date": rr.idxmax().strftime("%Y-%m-%d"),
            })
    return pd.DataFrame(rows)


def _drawdown_periods(daily: pd.DataFrame, top_n: int) -> pd.DataFrame:
    rows = []
    for policy, sub in daily.groupby("policy"):
        s = sub.sort_values("date").set_index("date")["equity"]
        dd = s / s.cummax() - 1.0
        start = None
        peak_date = None
        trough_date = None
        trough_dd = 0.0
        for dt, v in dd.items():
            flag = v < 0
            if flag and start is None:
                pos = s.index.get_loc(dt)
                peak_date = s.index[max(pos - 1, 0)]
                start = dt
                trough_date = dt
                trough_dd = float(v)
            elif flag and start is not None and float(v) < trough_dd:
                trough_dd = float(v)
                trough_date = dt
            elif not flag and start is not None:
                rows.append({
                    "policy": policy,
                    "peak_date": peak_date.strftime("%Y-%m-%d") if peak_date is not None else None,
                    "start_date": start.strftime("%Y-%m-%d"),
                    "trough_date": trough_date.strftime("%Y-%m-%d") if trough_date is not None else None,
                    "recovery_date": dt.strftime("%Y-%m-%d"),
                    "drawdown_pct": trough_dd * 100.0,
                    "duration_days": int((dt - start).days),
                })
                start = None
                peak_date = None
                trough_date = None
                trough_dd = 0.0
        if start is not None:
            rows.append({
                "policy": policy,
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
    return out.sort_values(["policy", "drawdown_pct"]).groupby("policy", as_index=False).head(top_n)


def _score(metrics: dict[str, float], selection_metric: str) -> float:
    if selection_metric == "calmar":
        return _to_float(metrics.get("calmar"), float("-inf"))
    if selection_metric == "sharpe":
        return _to_float(metrics.get("sharpe"), float("-inf"))
    if selection_metric == "cagr":
        return _to_float(metrics.get("cagr_pct"), float("-inf"))
    if selection_metric == "return":
        return _to_float(metrics.get("return_pct"), float("-inf"))
    if selection_metric == "composite":
        cagr = _to_float(metrics.get("cagr_pct"), -999.0)
        sharpe = _to_float(metrics.get("sharpe"), -999.0)
        maxdd = abs(_to_float(metrics.get("maxdd_pct"), 999.0))
        return cagr + 5.0 * sharpe - 0.5 * maxdd
    raise SystemExit(f"Unknown selection metric: {selection_metric}")


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


def _select_policy(daily: pd.DataFrame, policies: list[str], window: dict[str, pd.Timestamp], metric: str) -> tuple[str, list[dict[str, Any]]]:
    rows = []
    best_policy = ""
    best_score = float("-inf")
    for policy in policies:
        eq = _policy_equity(daily, policy, window["train_start"], window["train_end"])
        if eq.empty:
            continue
        metrics = _metrics_for_equity(eq)
        score = _score(metrics, metric)
        row = {"policy": policy, "selection_score": score, **metrics}
        rows.append(row)
        if score > best_score:
            best_policy = policy
            best_score = score
    if not best_policy:
        raise RuntimeError(f"No policy could be selected for window {window}")
    return best_policy, rows


def _daily_returns_for_policy(daily: pd.DataFrame, policy: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    sub = daily[(daily["policy"] == policy) & (daily["date"] >= start) & (daily["date"] <= end)].copy()
    if sub.empty:
        return sub
    sub = sub.sort_values("date")
    sub["derived_return"] = sub["equity"].pct_change().fillna(0.0)
    return sub


def _stitch_walk_forward(daily: pd.DataFrame, policies: list[str], windows: list[dict[str, pd.Timestamp]], metric: str, capital: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    current_equity = capital
    stitched_rows = []
    selection_rows = []
    train_rows = []
    for i, window in enumerate(windows, start=1):
        selected, scores = _select_policy(daily, policies, window, metric)
        for s in scores:
            train_rows.append({"window": i, **window, **s})
        selection_rows.append({"window": i, "selected_policy": selected, **window})
        test = _daily_returns_for_policy(daily, selected, window["test_start"], window["test_end"])
        for _, row in test.iterrows():
            r = _to_float(row.get("derived_return"), 0.0)
            current_equity *= 1.0 + r
            stitched_rows.append({
                "date": row["date"],
                "window": i,
                "selected_policy": selected,
                "daily_return": r,
                "stitched_equity": current_equity,
            })
    return pd.DataFrame(stitched_rows), pd.DataFrame(selection_rows), pd.DataFrame(train_rows)


def _static_oos_curve(daily: pd.DataFrame, policy: str, windows: list[dict[str, pd.Timestamp]], capital: float) -> pd.DataFrame:
    current_equity = capital
    rows = []
    for i, window in enumerate(windows, start=1):
        test = _daily_returns_for_policy(daily, policy, window["test_start"], window["test_end"])
        for _, row in test.iterrows():
            r = _to_float(row.get("derived_return"), 0.0)
            current_equity *= 1.0 + r
            rows.append({
                "date": row["date"],
                "policy": policy,
                "window": i,
                "daily_return": r,
                "stitched_equity": current_equity,
            })
    return pd.DataFrame(rows)


def _oos_window_scores(daily: pd.DataFrame, policies: list[str], windows: list[dict[str, pd.Timestamp]]) -> pd.DataFrame:
    rows = []
    for i, window in enumerate(windows, start=1):
        for policy in policies:
            eq = _policy_equity(daily, policy, window["test_start"], window["test_end"])
            if eq.empty:
                continue
            rows.append({"window": i, "policy": policy, **window, **_metrics_for_equity(eq)})
    return pd.DataFrame(rows)


def _summary_for_curve(name: str, curve: pd.DataFrame, equity_col: str, capital: float) -> dict[str, Any]:
    if curve.empty:
        return {"curve": name, "days": 0}
    s = curve.sort_values("date").set_index("date")[equity_col]
    return {"curve": name, "days": int(len(s)), **_metrics_for_equity(s, capital=capital)}


def _annual_from_curve(name: str, curve: pd.DataFrame, equity_col: str) -> pd.DataFrame:
    if curve.empty:
        return pd.DataFrame()
    s = curve.sort_values("date").set_index("date")[equity_col]
    year_end = s.resample("YE").last().dropna()
    rows = []
    prior = None
    for dt, end_eq in year_end.items():
        if prior is None:
            ys = s[s.index.year == dt.year]
            start_eq = float(ys.iloc[0]) if not ys.empty else float(s.iloc[0])
        else:
            start_eq = float(prior)
        rows.append({"curve": name, "year": int(dt.year), "return_pct": (float(end_eq) / start_eq - 1.0) * 100.0 if start_eq else float("nan"), "starting_equity": start_eq, "ending_equity": float(end_eq)})
        prior = float(end_eq)
    return pd.DataFrame(rows)


def _plain_table(df: pd.DataFrame, cols: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._\n"
    view = df[cols].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_csv(index=False)


def _write_markdown(out_dir: Path, finalist_summary: pd.DataFrame, yearly: pd.DataFrame, rolling: pd.DataFrame, drawdowns: pd.DataFrame, stitched_summary: pd.DataFrame, selections: pd.DataFrame, stitched_annual: pd.DataFrame) -> None:
    lines = ["# Core Allocator Validation Report\n", "Research-only validation. No broker/runtime/live execution code is modified.\n"]
    lines.append("## Full-Period Finalist Summary\n")
    lines.append(_plain_table(finalist_summary, list(finalist_summary.columns)))
    lines.append("\n## Calendar-Year Returns\n")
    lines.append(_plain_table(yearly, list(yearly.columns)))
    lines.append("\n## Rolling Return Diagnostics\n")
    lines.append(_plain_table(rolling, list(rolling.columns)))
    lines.append("\n## Worst Drawdown Periods\n")
    lines.append(_plain_table(drawdowns, list(drawdowns.columns)))
    lines.append("\n## Stitched OOS Summary\n")
    lines.append(_plain_table(stitched_summary, list(stitched_summary.columns)))
    lines.append("\n## Walk-Forward Selections\n")
    lines.append(_plain_table(selections, list(selections.columns)))
    lines.append("\n## Stitched OOS Annual Returns\n")
    lines.append(_plain_table(stitched_annual, list(stitched_annual.columns)))
    (out_dir / "core_allocator_validation_report.md").write_text("\n".join(lines), encoding="utf-8")


def _print_full_summary(summary: pd.DataFrame) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print("  CORE ALLOCATOR VALIDATION — FULL-PERIOD FINALISTS")
    print("=" * DISPLAY_WIDTH)
    if summary.empty:
        print("  No rows.")
        return
    view = summary.sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    print(f"  {'Policy':<36} {'Kind':<20} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Calmar':>8} {'Vol':>8} {'FinalEq':>12}")
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('policy')):<36} {str(r.get('kind')):<20} "
            f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
            f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('calmar'), 3):>8} {_fmt(r.get('ann_vol_pct')):>8} {_money(r.get('final_equity')):>12}"
        )
    print("=" * DISPLAY_WIDTH)


def _print_stitched_summary(summary: pd.DataFrame, selections: pd.DataFrame) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print("  CORE ALLOCATOR VALIDATION — STITCHED OOS")
    print("=" * DISPLAY_WIDTH)
    if summary.empty:
        print("  No rows.")
    else:
        view = summary.sort_values(["calmar", "cagr_pct"], ascending=[False, False])
        print(f"  {'Curve':<42} {'Days':>6} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Calmar':>8} {'WorstDay':>9} {'FinalEq':>12}")
        for _, r in view.iterrows():
            print(
                f"  {str(r.get('curve')):<42} {int(_to_float(r.get('days'), 0)):>6} "
                f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
                f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('calmar'), 3):>8} {_fmt(r.get('worst_day_pct')):>9} {_money(r.get('final_equity')):>12}"
            )
    print("-" * DISPLAY_WIDTH)
    print("  Selections:")
    if selections.empty:
        print("    none")
    else:
        for _, r in selections.iterrows():
            print(
                f"    Window {int(r['window'])}: {r['selected_policy']} | "
                f"train {pd.Timestamp(r['train_start']).date()}->{pd.Timestamp(r['train_end']).date()} | "
                f"test {pd.Timestamp(r['test_start']).date()}->{pd.Timestamp(r['test_end']).date()}"
            )
    print("=" * DISPLAY_WIDTH)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate core allocator policy sweep outputs")
    p.add_argument("--sweep-dir", default="artifacts/core_allocator_policy_sweep")
    p.add_argument("--out-dir", default="artifacts/core_allocator_validation")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--top-n", type=int, default=8)
    p.add_argument("--include-policies", nargs="+", default=[], help="Optional exact policy allowlist. Defaults to top-N by Calmar plus selected core candidates.")
    p.add_argument("--core-candidates", nargs="+", default=["trend_gated_balanced_ma200", "defensive_overlay_balanced", "vol_target_trend_25pct", "vol_target_trend_18pct", "vol_target_trend_12pct", "static_balanced_core", "static_crypto_growth", "crypto_only_equal"])
    p.add_argument("--rolling-windows-months", nargs="+", type=int, default=[3, 6, 12])
    p.add_argument("--top-drawdowns", type=int, default=5)
    p.add_argument("--wf-start", default="2019-01-01")
    p.add_argument("--wf-end", default="2025-12-30")
    p.add_argument("--train-years", type=int, default=2)
    p.add_argument("--test-years", type=int, default=1)
    p.add_argument("--step-years", type=int, default=1)
    p.add_argument("--selection-metric", default="calmar", choices=["calmar", "sharpe", "cagr", "return", "composite"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    sweep_dir = Path(args.sweep_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = _read_csv(sweep_dir / "core_allocator_policy_summary.csv")
    daily = _load_daily(sweep_dir / "core_allocator_daily_equity.csv")
    if summary.empty:
        raise SystemExit(f"Missing or empty summary file: {sweep_dir / 'core_allocator_policy_summary.csv'}")

    if args.include_policies:
        selected_policies = [p for p in args.include_policies if p in set(summary["policy"])]
    else:
        top = summary.sort_values(["calmar", "cagr_pct"], ascending=[False, False]).head(args.top_n)["policy"].astype(str).tolist()
        selected_policies = []
        for p in top + args.core_candidates:
            if p in set(summary["policy"]) and p not in selected_policies:
                selected_policies.append(p)

    finalist_summary = summary[summary["policy"].isin(selected_policies)].copy()
    finalist_daily = daily[daily["policy"].isin(selected_policies)].copy()
    yearly = _calendar_year_returns(finalist_daily)
    monthly = _monthly_returns(finalist_daily)
    rolling = _rolling_returns(finalist_daily, args.rolling_windows_months)
    drawdowns = _drawdown_periods(finalist_daily, args.top_drawdowns)

    windows = _window_rows(pd.Timestamp(args.wf_start), pd.Timestamp(args.wf_end), args.train_years, args.test_years, args.step_years)
    stitched, selections, train_scores = _stitch_walk_forward(finalist_daily, selected_policies, windows, args.selection_metric, args.capital)
    static_curves = pd.concat([_static_oos_curve(finalist_daily, policy, windows, args.capital) for policy in selected_policies], ignore_index=True) if selected_policies else pd.DataFrame()
    oos_scores = _oos_window_scores(finalist_daily, selected_policies, windows)

    stitched_summary_rows = [_summary_for_curve("stitched_walk_forward", stitched, "stitched_equity", args.capital)]
    if not static_curves.empty:
        for policy, sub in static_curves.groupby("policy"):
            stitched_summary_rows.append(_summary_for_curve(f"always_{policy}", sub, "stitched_equity", args.capital))
    stitched_summary = pd.DataFrame(stitched_summary_rows)
    stitched_annual_parts = [_annual_from_curve("stitched_walk_forward", stitched, "stitched_equity")]
    if not static_curves.empty:
        for policy, sub in static_curves.groupby("policy"):
            stitched_annual_parts.append(_annual_from_curve(f"always_{policy}", sub, "stitched_equity"))
    stitched_annual = pd.concat(stitched_annual_parts, ignore_index=True) if stitched_annual_parts else pd.DataFrame()

    finalist_summary.to_csv(out_dir / "core_allocator_finalist_summary.csv", index=False)
    yearly.to_csv(out_dir / "core_allocator_calendar_year_returns.csv", index=False)
    monthly.to_csv(out_dir / "core_allocator_monthly_returns.csv", index=False)
    rolling.to_csv(out_dir / "core_allocator_rolling_return_diagnostics.csv", index=False)
    drawdowns.to_csv(out_dir / "core_allocator_worst_drawdown_periods.csv", index=False)
    stitched.to_csv(out_dir / "core_allocator_stitched_oos_daily.csv", index=False)
    selections.to_csv(out_dir / "core_allocator_walk_forward_selections.csv", index=False)
    train_scores.to_csv(out_dir / "core_allocator_walk_forward_train_scores.csv", index=False)
    oos_scores.to_csv(out_dir / "core_allocator_oos_window_scores.csv", index=False)
    static_curves.to_csv(out_dir / "core_allocator_static_oos_daily.csv", index=False)
    stitched_summary.to_csv(out_dir / "core_allocator_stitched_oos_summary.csv", index=False)
    stitched_annual.to_csv(out_dir / "core_allocator_stitched_oos_annual_returns.csv", index=False)
    (out_dir / "core_allocator_validation_summary.json").write_text(json.dumps({
        "sweep_dir": str(sweep_dir),
        "selected_policies": selected_policies,
        "wf_start": args.wf_start,
        "wf_end": args.wf_end,
        "train_years": args.train_years,
        "test_years": args.test_years,
        "step_years": args.step_years,
        "selection_metric": args.selection_metric,
        "outputs": {
            "finalist_summary": str(out_dir / "core_allocator_finalist_summary.csv"),
            "calendar_year_returns": str(out_dir / "core_allocator_calendar_year_returns.csv"),
            "monthly_returns": str(out_dir / "core_allocator_monthly_returns.csv"),
            "rolling_return_diagnostics": str(out_dir / "core_allocator_rolling_return_diagnostics.csv"),
            "worst_drawdown_periods": str(out_dir / "core_allocator_worst_drawdown_periods.csv"),
            "stitched_oos_summary": str(out_dir / "core_allocator_stitched_oos_summary.csv"),
            "stitched_oos_daily": str(out_dir / "core_allocator_stitched_oos_daily.csv"),
            "walk_forward_selections": str(out_dir / "core_allocator_walk_forward_selections.csv"),
        },
    }, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir, finalist_summary, yearly, rolling, drawdowns, stitched_summary, selections, stitched_annual)

    _print_full_summary(finalist_summary)
    _print_stitched_summary(stitched_summary, selections)
    print(f"  Policies validated: {', '.join(selected_policies)}")
    print(f"  Outputs: {out_dir}")
    print("  Verdict: CORE ALLOCATOR VALIDATION ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
