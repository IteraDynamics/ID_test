from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


CANONICAL_BASELINE = {
    "cagr_pct": 18.51,
    "max_drawdown_pct": -17.88,
    "sharpe": 1.223,
    "calmar": 1.035,
    "final_equity": 277005.29,
}

STRESS_WINDOWS = {
    "covid_2020": ("2020-02-15", "2020-04-30"),
    "full_2020": ("2020-01-01", "2020-12-31"),
    "riskoff_2022": ("2022-01-01", "2022-12-31"),
    "chop_2025": ("2025-01-01", "2025-12-31"),
    "full_oos": ("2020-01-01", "2025-12-31"),
}


def find_date_col(df: pd.DataFrame) -> str:
    candidates = ["date", "datetime", "timestamp", "time"]
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        try:
            parsed = pd.to_datetime(df[c], errors="coerce")
            if parsed.notna().mean() > 0.9:
                return c
        except Exception:
            pass
    raise ValueError(f"Could not infer date column from {list(df.columns)}")


def find_nav_col(df: pd.DataFrame, date_col: str) -> str:
    preferred = [
        "nav",
        "fund_nav",
        "stitched_nav",
        "equity",
        "portfolio_value",
        "portfolio_nav",
        "value",
    ]
    lowered = {c.lower(): c for c in df.columns}
    for p in preferred:
        if p in lowered and lowered[p] != date_col:
            return lowered[p]

    numeric_cols = []
    for c in df.columns:
        if c == date_col:
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().mean() > 0.9:
            numeric_cols.append(c)

    if not numeric_cols:
        raise ValueError(f"Could not infer NAV column from {list(df.columns)}")

    return numeric_cols[-1]


def load_nav(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = find_date_col(df)
    nav_col = find_nav_col(df, date_col)

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col]),
            "nav": pd.to_numeric(df[nav_col], errors="coerce"),
        }
    )
    out = out.dropna().sort_values("date").drop_duplicates("date")
    out["ret"] = out["nav"].pct_change().fillna(0.0)
    out["cummax"] = out["nav"].cummax()
    out["drawdown"] = out["nav"] / out["cummax"] - 1.0
    return out


def metrics(nav: pd.DataFrame) -> dict:
    start = nav["nav"].iloc[0]
    end = nav["nav"].iloc[-1]
    days = (nav["date"].iloc[-1] - nav["date"].iloc[0]).days
    years = days / 365.25 if days > 0 else np.nan

    total_return = end / start - 1.0
    cagr = (end / start) ** (1.0 / years) - 1.0 if years and years > 0 else np.nan
    maxdd = nav["drawdown"].min()

    rets = nav["ret"].dropna()
    sharpe = np.sqrt(252) * rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) > 0 else np.nan
    calmar = cagr / abs(maxdd) if maxdd < 0 else np.nan

    return {
        "cagr_pct": cagr * 100,
        "total_return_pct": total_return * 100,
        "max_drawdown_pct": maxdd * 100,
        "sharpe": sharpe,
        "calmar": calmar,
        "final_equity": end,
    }


def period_return(nav: pd.DataFrame, start: str, end: str) -> float:
    mask = (nav["date"] >= pd.Timestamp(start)) & (nav["date"] <= pd.Timestamp(end))
    sub = nav.loc[mask]
    if len(sub) < 2:
        return np.nan
    return (sub["nav"].iloc[-1] / sub["nav"].iloc[0] - 1.0) * 100


def period_maxdd(nav: pd.DataFrame, start: str, end: str) -> float:
    mask = (nav["date"] >= pd.Timestamp(start)) & (nav["date"] <= pd.Timestamp(end))
    sub = nav.loc[mask].copy()
    if len(sub) < 2:
        return np.nan
    sub["local_cummax"] = sub["nav"].cummax()
    sub["local_dd"] = sub["nav"] / sub["local_cummax"] - 1.0
    return sub["local_dd"].min() * 100


def worst_rolling(nav: pd.DataFrame, window: int) -> float:
    nav = nav.copy()
    nav[f"roll_{window}"] = nav["nav"].pct_change(window)
    return nav[f"roll_{window}"].min() * 100


def drawdown_episodes(nav: pd.DataFrame, scenario: str, top_n: int = 5) -> list[dict]:
    rows = []
    in_dd = False
    peak_date = None
    trough_date = None
    recovery_date = None
    trough_dd = 0.0
    peak_nav = None

    for idx, r in nav.iterrows():
        date = r["date"]
        dd = r["drawdown"]
        navv = r["nav"]

        if not in_dd and dd < 0:
            in_dd = True
            peak_idx = nav.loc[:idx, "nav"].idxmax()
            peak_date = nav.loc[peak_idx, "date"]
            peak_nav = nav.loc[peak_idx, "nav"]
            trough_date = date
            trough_dd = dd
            recovery_date = None

        if in_dd:
            if dd < trough_dd:
                trough_dd = dd
                trough_date = date

            if peak_nav is not None and navv >= peak_nav:
                recovery_date = date
                rows.append(
                    {
                        "scenario": scenario,
                        "peak_date": peak_date.date(),
                        "trough_date": trough_date.date(),
                        "recovery_date": recovery_date.date(),
                        "drawdown_pct": trough_dd * 100,
                        "days_peak_to_trough": (trough_date - peak_date).days,
                        "days_to_recovery": (recovery_date - peak_date).days,
                    }
                )
                in_dd = False

    if in_dd:
        rows.append(
            {
                "scenario": scenario,
                "peak_date": peak_date.date() if peak_date is not None else None,
                "trough_date": trough_date.date() if trough_date is not None else None,
                "recovery_date": None,
                "drawdown_pct": trough_dd * 100,
                "days_peak_to_trough": (trough_date - peak_date).days if peak_date is not None else None,
                "days_to_recovery": None,
            }
        )

    return sorted(rows, key=lambda x: x["drawdown_pct"])[:top_n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="artifacts/core_v1_candidate_wfo")
    ap.add_argument("--out", default="artifacts/core_v1_candidate_wfo/validation")
    args = ap.parse_args()

    root = Path(args.root)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    nav_paths = sorted(root.glob("*/stitched_oos_nav.csv"))
    if not nav_paths:
        raise SystemExit(f"No stitched_oos_nav.csv files found under {root}")

    summaries = []
    stress_rows = []
    dd_rows = []

    for p in nav_paths:
        scenario = p.parent.name
        nav = load_nav(p)

        row = {"scenario": scenario}
        row.update(metrics(nav))

        for year in range(2020, 2026):
            row[f"ret_{year}"] = period_return(nav, f"{year}-01-01", f"{year}-12-31")

        row["worst_21d_return_pct"] = worst_rolling(nav, 21)
        row["worst_63d_return_pct"] = worst_rolling(nav, 63)
        row["worst_126d_return_pct"] = worst_rolling(nav, 126)

        summaries.append(row)

        for name, (s, e) in STRESS_WINDOWS.items():
            stress_rows.append(
                {
                    "scenario": scenario,
                    "window": name,
                    "start": s,
                    "end": e,
                    "return_pct": period_return(nav, s, e),
                    "max_drawdown_pct": period_maxdd(nav, s, e),
                }
            )

        dd_rows.extend(drawdown_episodes(nav, scenario, top_n=5))

    summary = pd.DataFrame(summaries)
    stress = pd.DataFrame(stress_rows)
    drawdowns = pd.DataFrame(dd_rows)

    if "baseline_40_35_15_10" in set(summary["scenario"]):
        summary["_sort"] = np.where(summary["scenario"] == "baseline_40_35_15_10", 0, 1)
        summary = summary.sort_values(["_sort", "sharpe"], ascending=[True, False]).drop(columns=["_sort"])
    else:
        summary = summary.sort_values("sharpe", ascending=False)

    summary.to_csv(out_dir / "validation_summary.csv", index=False)
    stress.to_csv(out_dir / "stress_windows.csv", index=False)
    drawdowns.to_csv(out_dir / "worst_drawdown_episodes.csv", index=False)

    print("\n=== VALIDATION SUMMARY ===")
    cols = [
        "scenario",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "calmar",
        "final_equity",
        "ret_2022",
        "ret_2025",
        "worst_21d_return_pct",
        "worst_63d_return_pct",
        "worst_126d_return_pct",
    ]
    print(summary[cols].round(3).to_string(index=False))

    if "baseline_40_35_15_10" in set(summary["scenario"]):
        base = summary.loc[summary["scenario"] == "baseline_40_35_15_10"].iloc[0]
        print("\n=== BASELINE PARITY CHECK ===")
        for k, expected in CANONICAL_BASELINE.items():
            actual = base[k]
            print(f"{k}: actual={actual:.4f}, expected~={expected:.4f}, diff={actual - expected:.4f}")

        print("\n=== DELTA VS BASELINE ===")
        deltas = summary.copy()
        for k in [
            "cagr_pct",
            "max_drawdown_pct",
            "sharpe",
            "calmar",
            "final_equity",
            "ret_2022",
            "ret_2025",
        ]:
            deltas[k] = deltas[k] - base[k]
        print(
            deltas[
                [
                    "scenario",
                    "cagr_pct",
                    "max_drawdown_pct",
                    "sharpe",
                    "calmar",
                    "final_equity",
                    "ret_2022",
                    "ret_2025",
                ]
            ]
            .round(3)
            .to_string(index=False)
        )

    print("\nWrote:")
    print(f"  {out_dir / 'validation_summary.csv'}")
    print(f"  {out_dir / 'stress_windows.csv'}")
    print(f"  {out_dir / 'worst_drawdown_episodes.csv'}")


if __name__ == "__main__":
    main()
