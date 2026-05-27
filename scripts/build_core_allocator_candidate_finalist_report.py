#!/usr/bin/env python
"""Build a finalist report for fixed structural core allocator candidates.

This report intentionally focuses on fixed structural policies, not the failed
walk-forward policy selector. It compares:

- core_aggressive: trend_gated_balanced_ma200
- core_balanced:   vol_target_trend_18pct
- core_defensive:  vol_target_trend_12pct

The script consumes outputs from:

    scripts/run_core_allocator_policy_sweep.py
    scripts/validate_core_allocator_policy_sweep.py

and writes an allocator-facing report that answers:

- Which candidate is the best flagship core?
- Which candidate is the most fund-shaped?
- What were the calendar-year and monthly returns?
- What were the worst drawdown periods?
- What were the rolling 3/6/12-month outcomes?
- What assets did each policy actually hold by year?
- How exposed was each policy on average?

Research only. No broker/runtime/live execution code is modified.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

DISPLAY_WIDTH = 190

DEFAULT_FINALISTS = {
    "core_aggressive": "trend_gated_balanced_ma200",
    "core_balanced": "vol_target_trend_18pct",
    "core_defensive": "vol_target_trend_12pct",
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


def _parse_finalists(values: list[str]) -> dict[str, str]:
    if not values:
        return dict(DEFAULT_FINALISTS)
    out: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise SystemExit(f"Invalid --finalist '{raw}'. Expected alias=policy")
        alias, policy = raw.split("=", 1)
        out[alias.strip()] = policy.strip()
    return out


def _load_daily(path: Path) -> pd.DataFrame:
    daily = _read_csv(path)
    if daily.empty:
        raise SystemExit(f"Missing or empty daily equity file: {path}")
    daily = daily.copy()
    daily["date"] = _dateify(daily["date"])
    daily["equity"] = pd.to_numeric(daily["equity"], errors="coerce")
    for col in ["net_return", "gross_return", "turnover", "cost_return", "gross_exposure"]:
        if col in daily.columns:
            daily[col] = pd.to_numeric(daily[col], errors="coerce")
    return daily.dropna(subset=["date", "policy", "equity"]).sort_values(["policy", "date"])


def _load_weights(path: Path) -> pd.DataFrame:
    weights = _read_csv(path)
    if weights.empty:
        return pd.DataFrame()
    weights = weights.copy()
    if "date" in weights.columns:
        weights["date"] = _dateify(weights["date"])
    return weights.dropna(subset=["date", "policy"]).sort_values(["policy", "date"])


def _filter_alias(df: pd.DataFrame, finalists: dict[str, str], policy_col: str = "policy") -> pd.DataFrame:
    if df.empty or policy_col not in df.columns:
        return pd.DataFrame()
    reverse = {policy: alias for alias, policy in finalists.items()}
    out = df[df[policy_col].isin(reverse)].copy()
    if out.empty:
        return out
    out.insert(0, "alias", out[policy_col].map(reverse))
    return out


def _finalist_summary(summary: pd.DataFrame, finalists: dict[str, str]) -> pd.DataFrame:
    out = _filter_alias(summary, finalists)
    if out.empty:
        return out
    cols = [
        "alias", "policy", "kind", "cagr_pct", "return_pct", "maxdd_pct", "sharpe",
        "sortino", "calmar", "ann_vol_pct", "avg_gross_exposure", "annual_turnover",
        "total_cost_pct", "final_equity",
    ]
    cols = [c for c in cols if c in out.columns]
    return out[cols].sort_values(["calmar", "cagr_pct"], ascending=[False, False])


def _calendar_returns(yearly: pd.DataFrame, finalists: dict[str, str]) -> pd.DataFrame:
    out = _filter_alias(yearly, finalists)
    if out.empty:
        return out
    cols = ["alias", "policy", "year", "return_pct", "starting_equity", "ending_equity"]
    return out[[c for c in cols if c in out.columns]].sort_values(["alias", "year"])


def _monthly_summary(monthly: pd.DataFrame, finalists: dict[str, str]) -> pd.DataFrame:
    out = _filter_alias(monthly, finalists)
    if out.empty:
        return out
    rows = []
    for (alias, policy), sub in out.groupby(["alias", "policy"]):
        r = pd.to_numeric(sub["return_pct"], errors="coerce").dropna()
        if r.empty:
            continue
        rows.append({
            "alias": alias,
            "policy": policy,
            "months": int(len(r)),
            "positive_months": int((r > 0).sum()),
            "positive_rate_pct": float((r > 0).mean() * 100.0),
            "best_month_pct": float(r.max()),
            "worst_month_pct": float(r.min()),
            "median_month_pct": float(r.median()),
            "avg_month_pct": float(r.mean()),
        })
    return pd.DataFrame(rows).sort_values(["positive_rate_pct", "median_month_pct"], ascending=[False, False])


def _rolling_focus(rolling: pd.DataFrame, finalists: dict[str, str]) -> pd.DataFrame:
    out = _filter_alias(rolling, finalists)
    if out.empty:
        return out
    cols = [
        "alias", "policy", "window_months", "worst_return_pct", "median_return_pct",
        "best_return_pct", "positive_rate_pct", "observations", "worst_end_date", "best_end_date",
    ]
    return out[[c for c in cols if c in out.columns]].sort_values(["alias", "window_months"])


def _drawdown_focus(drawdowns: pd.DataFrame, finalists: dict[str, str], top_n: int) -> pd.DataFrame:
    out = _filter_alias(drawdowns, finalists)
    if out.empty:
        return out
    cols = [
        "alias", "policy", "peak_date", "start_date", "trough_date", "recovery_date",
        "drawdown_pct", "duration_days",
    ]
    out = out[[c for c in cols if c in out.columns]].sort_values(["alias", "drawdown_pct"])
    return out.groupby("alias", as_index=False).head(top_n)


def _oos_summary(stitched_summary: pd.DataFrame, finalists: dict[str, str]) -> pd.DataFrame:
    if stitched_summary.empty or "curve" not in stitched_summary.columns:
        return pd.DataFrame()
    rows = []
    for alias, policy in finalists.items():
        curve = f"always_{policy}"
        match = stitched_summary[stitched_summary["curve"] == curve].copy()
        if match.empty:
            continue
        match.insert(0, "alias", alias)
        match.insert(1, "policy", policy)
        rows.append(match)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    cols = ["alias", "policy", "days", "cagr_pct", "return_pct", "maxdd_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "worst_day_pct", "final_equity"]
    return out[[c for c in cols if c in out.columns]].sort_values(["calmar", "cagr_pct"], ascending=[False, False])


def _oos_annual(stitched_annual: pd.DataFrame, finalists: dict[str, str]) -> pd.DataFrame:
    if stitched_annual.empty or "curve" not in stitched_annual.columns:
        return pd.DataFrame()
    rows = []
    for alias, policy in finalists.items():
        curve = f"always_{policy}"
        match = stitched_annual[stitched_annual["curve"] == curve].copy()
        if match.empty:
            continue
        match.insert(0, "alias", alias)
        match.insert(1, "policy", policy)
        rows.append(match)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    cols = ["alias", "policy", "year", "return_pct", "starting_equity", "ending_equity"]
    return out[[c for c in cols if c in out.columns]].sort_values(["alias", "year"])


def _asset_weight_summary(weights: pd.DataFrame, finalists: dict[str, str]) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame()
    out = _filter_alias(weights, finalists)
    if out.empty:
        return out
    meta = {"alias", "policy", "date"}
    asset_cols = [c for c in out.columns if c not in meta]
    rows = []
    out["year"] = out["date"].dt.year
    for (alias, policy, year), sub in out.groupby(["alias", "policy", "year"]):
        row = {"alias": alias, "policy": policy, "year": int(year)}
        gross = 0.0
        for col in asset_cols:
            val = float(pd.to_numeric(sub[col], errors="coerce").fillna(0.0).mean())
            row[f"avg_{col}_weight"] = val
            gross += val
        row["avg_gross_exposure"] = gross
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["alias", "year"])


def _asset_weight_lifetime(weights: pd.DataFrame, finalists: dict[str, str]) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame()
    out = _filter_alias(weights, finalists)
    if out.empty:
        return out
    meta = {"alias", "policy", "date"}
    asset_cols = [c for c in out.columns if c not in meta]
    rows = []
    for (alias, policy), sub in out.groupby(["alias", "policy"]):
        row = {"alias": alias, "policy": policy}
        gross = 0.0
        for col in asset_cols:
            vals = pd.to_numeric(sub[col], errors="coerce").fillna(0.0)
            avg = float(vals.mean())
            row[f"avg_{col}_weight"] = avg
            row[f"active_{col}_rate_pct"] = float((vals > 0.001).mean() * 100.0)
            gross += avg
        row["avg_gross_exposure"] = gross
        rows.append(row)
    return pd.DataFrame(rows).sort_values("alias")


def _yearly_return_pivot(yearly: pd.DataFrame) -> pd.DataFrame:
    if yearly.empty:
        return yearly
    pivot = yearly.pivot_table(index="year", columns="alias", values="return_pct", aggfunc="first").reset_index()
    return pivot


def _write_markdown(
    path: Path,
    full_summary: pd.DataFrame,
    oos_summary: pd.DataFrame,
    yearly: pd.DataFrame,
    oos_yearly: pd.DataFrame,
    monthly_summary: pd.DataFrame,
    rolling: pd.DataFrame,
    drawdowns: pd.DataFrame,
    weight_lifetime: pd.DataFrame,
    weight_yearly: pd.DataFrame,
) -> None:
    lines: list[str] = []
    lines.append("# Core Allocator Candidate Finalist Report\n")
    lines.append("Research-only report for fixed structural core allocator candidates. No broker/runtime/live execution code is modified.\n")
    lines.append("## Candidate Map\n")
    lines.append("- core_aggressive: trend_gated_balanced_ma200\n- core_balanced: vol_target_trend_18pct\n- core_defensive: vol_target_trend_12pct\n")
    lines.append("## Full-Period Summary\n")
    lines.append(full_summary.to_csv(index=False) if not full_summary.empty else "_No rows._\n")
    lines.append("\n## Static OOS Summary\n")
    lines.append(oos_summary.to_csv(index=False) if not oos_summary.empty else "_No rows._\n")
    lines.append("\n## Full-Period Calendar-Year Returns\n")
    lines.append(yearly.to_csv(index=False) if not yearly.empty else "_No rows._\n")
    lines.append("\n## OOS Calendar-Year Returns\n")
    lines.append(oos_yearly.to_csv(index=False) if not oos_yearly.empty else "_No rows._\n")
    lines.append("\n## Monthly Return Summary\n")
    lines.append(monthly_summary.to_csv(index=False) if not monthly_summary.empty else "_No rows._\n")
    lines.append("\n## Rolling Return Diagnostics\n")
    lines.append(rolling.to_csv(index=False) if not rolling.empty else "_No rows._\n")
    lines.append("\n## Worst Drawdown Periods\n")
    lines.append(drawdowns.to_csv(index=False) if not drawdowns.empty else "_No rows._\n")
    lines.append("\n## Lifetime Average Asset Weights\n")
    lines.append(weight_lifetime.to_csv(index=False) if not weight_lifetime.empty else "_No rows._\n")
    lines.append("\n## Yearly Average Asset Weights\n")
    lines.append(weight_yearly.to_csv(index=False) if not weight_yearly.empty else "_No rows._\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def _print_report(full_summary: pd.DataFrame, oos_summary: pd.DataFrame) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print("  CORE ALLOCATOR CANDIDATE FINALIST REPORT")
    print("=" * DISPLAY_WIDTH)
    print("  Full-period finalists:")
    if full_summary.empty:
        print("    No rows.")
    else:
        print(f"  {'Alias':<18} {'Policy':<34} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Calmar':>8} {'Vol':>8} {'AvgExp':>8} {'FinalEq':>12}")
        for _, r in full_summary.iterrows():
            print(
                f"  {str(r.get('alias')):<18} {str(r.get('policy')):<34} "
                f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
                f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('calmar'), 3):>8} {_fmt(r.get('ann_vol_pct')):>8} "
                f"{_fmt(r.get('avg_gross_exposure')):>8} {_money(r.get('final_equity')):>12}"
            )
    print("-" * DISPLAY_WIDTH)
    print("  Static OOS finalists:")
    if oos_summary.empty:
        print("    No rows.")
    else:
        print(f"  {'Alias':<18} {'Policy':<34} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Calmar':>8} {'WorstDay':>9} {'FinalEq':>12}")
        for _, r in oos_summary.iterrows():
            print(
                f"  {str(r.get('alias')):<18} {str(r.get('policy')):<34} "
                f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
                f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('calmar'), 3):>8} {_fmt(r.get('worst_day_pct')):>9} "
                f"{_money(r.get('final_equity')):>12}"
            )
    print("=" * DISPLAY_WIDTH)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build core allocator candidate finalist report")
    p.add_argument("--sweep-dir", default="artifacts/core_allocator_policy_sweep")
    p.add_argument("--validation-dir", default="artifacts/core_allocator_validation_low_vol")
    p.add_argument("--out-dir", default="artifacts/core_allocator_candidate_finalist_report")
    p.add_argument("--finalist", action="append", default=[], help="Finalist alias=policy. Repeatable. Defaults to core_aggressive/core_balanced/core_defensive.")
    p.add_argument("--top-drawdowns", type=int, default=5)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    sweep_dir = Path(args.sweep_dir)
    validation_dir = Path(args.validation_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    finalists = _parse_finalists(args.finalist)

    sweep_summary = _read_csv(sweep_dir / "core_allocator_policy_summary.csv")
    daily = _load_daily(sweep_dir / "core_allocator_daily_equity.csv")
    weights = _load_weights(sweep_dir / "core_allocator_daily_weights.csv")

    validation_yearly = _read_csv(validation_dir / "core_allocator_calendar_year_returns.csv")
    validation_monthly = _read_csv(validation_dir / "core_allocator_monthly_returns.csv")
    validation_rolling = _read_csv(validation_dir / "core_allocator_rolling_return_diagnostics.csv")
    validation_drawdowns = _read_csv(validation_dir / "core_allocator_worst_drawdown_periods.csv")
    stitched_summary = _read_csv(validation_dir / "core_allocator_stitched_oos_summary.csv")
    stitched_annual = _read_csv(validation_dir / "core_allocator_stitched_oos_annual_returns.csv")

    full_summary = _finalist_summary(sweep_summary, finalists)
    yearly = _calendar_returns(validation_yearly, finalists)
    if yearly.empty:
        # Fall back to daily if validation yearly output is unavailable.
        yearly_rows = []
        for alias, policy in finalists.items():
            sub = daily[daily["policy"] == policy].copy()
            if sub.empty:
                continue
            s = sub.sort_values("date").set_index("date")["equity"]
            prior = None
            for dt, end_eq in s.resample("YE").last().dropna().items():
                if prior is None:
                    ys = s[s.index.year == dt.year]
                    start_eq = float(ys.iloc[0]) if not ys.empty else float(s.iloc[0])
                else:
                    start_eq = float(prior)
                yearly_rows.append({"alias": alias, "policy": policy, "year": int(dt.year), "return_pct": (float(end_eq) / start_eq - 1.0) * 100.0, "starting_equity": start_eq, "ending_equity": float(end_eq)})
                prior = float(end_eq)
        yearly = pd.DataFrame(yearly_rows)

    monthly = _monthly_summary(validation_monthly, finalists)
    rolling = _rolling_focus(validation_rolling, finalists)
    drawdowns = _drawdown_focus(validation_drawdowns, finalists, args.top_drawdowns)
    oos = _oos_summary(stitched_summary, finalists)
    oos_yearly = _oos_annual(stitched_annual, finalists)
    weight_yearly = _asset_weight_summary(weights, finalists)
    weight_lifetime = _asset_weight_lifetime(weights, finalists)
    yearly_pivot = _yearly_return_pivot(yearly)
    oos_yearly_pivot = _yearly_return_pivot(oos_yearly.rename(columns={"curve": "policy"}) if "alias" in oos_yearly.columns else oos_yearly)

    full_summary.to_csv(out_dir / "core_allocator_finalist_full_period_summary.csv", index=False)
    oos.to_csv(out_dir / "core_allocator_finalist_static_oos_summary.csv", index=False)
    yearly.to_csv(out_dir / "core_allocator_finalist_calendar_year_returns.csv", index=False)
    yearly_pivot.to_csv(out_dir / "core_allocator_finalist_calendar_year_returns_pivot.csv", index=False)
    oos_yearly.to_csv(out_dir / "core_allocator_finalist_oos_annual_returns.csv", index=False)
    oos_yearly_pivot.to_csv(out_dir / "core_allocator_finalist_oos_annual_returns_pivot.csv", index=False)
    monthly.to_csv(out_dir / "core_allocator_finalist_monthly_summary.csv", index=False)
    rolling.to_csv(out_dir / "core_allocator_finalist_rolling_return_diagnostics.csv", index=False)
    drawdowns.to_csv(out_dir / "core_allocator_finalist_worst_drawdown_periods.csv", index=False)
    weight_yearly.to_csv(out_dir / "core_allocator_finalist_yearly_asset_weights.csv", index=False)
    weight_lifetime.to_csv(out_dir / "core_allocator_finalist_lifetime_asset_weights.csv", index=False)
    _write_markdown(
        out_dir / "core_allocator_candidate_finalist_report.md",
        full_summary,
        oos,
        yearly,
        oos_yearly,
        monthly,
        rolling,
        drawdowns,
        weight_lifetime,
        weight_yearly,
    )
    (out_dir / "core_allocator_candidate_finalist_report_summary.json").write_text(json.dumps({
        "sweep_dir": str(sweep_dir),
        "validation_dir": str(validation_dir),
        "finalists": finalists,
        "outputs": {
            "report_md": str(out_dir / "core_allocator_candidate_finalist_report.md"),
            "full_period_summary": str(out_dir / "core_allocator_finalist_full_period_summary.csv"),
            "static_oos_summary": str(out_dir / "core_allocator_finalist_static_oos_summary.csv"),
            "calendar_year_returns": str(out_dir / "core_allocator_finalist_calendar_year_returns.csv"),
            "oos_annual_returns": str(out_dir / "core_allocator_finalist_oos_annual_returns.csv"),
            "monthly_summary": str(out_dir / "core_allocator_finalist_monthly_summary.csv"),
            "rolling_return_diagnostics": str(out_dir / "core_allocator_finalist_rolling_return_diagnostics.csv"),
            "worst_drawdown_periods": str(out_dir / "core_allocator_finalist_worst_drawdown_periods.csv"),
            "yearly_asset_weights": str(out_dir / "core_allocator_finalist_yearly_asset_weights.csv"),
            "lifetime_asset_weights": str(out_dir / "core_allocator_finalist_lifetime_asset_weights.csv"),
        },
    }, indent=2), encoding="utf-8")

    _print_report(full_summary, oos)
    print(f"  Finalists: {', '.join([f'{a}={p}' for a, p in finalists.items()])}")
    print(f"  Outputs: {out_dir}")
    print("  Verdict: CORE ALLOCATOR FINALIST REPORT ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
