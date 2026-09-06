from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

SCENARIOS = [
    "baseline_40_35_15_10",
    "candidate_btc1h_hedges_to_btc4h_gld_qqq",
    "candidate_btc1h_half_btc4h_half_qqq",
]
BASELINE = "baseline_40_35_15_10"

STRESS_WINDOWS = {
    "covid_2020_drawdown": ("2020-02-19", "2020-03-23"),
    "covid_2020_drawdown_recovery": ("2020-02-19", "2020-06-30"),
    "bear_tightening_2021_2022": ("2021-11-09", "2022-12-19"),
    "bear_tightening_recovery": ("2021-11-09", "2023-11-22"),
    "calendar_2022": ("2022-01-01", "2022-12-31"),
    "calendar_2025": ("2025-01-01", "2025-12-31"),
}

CANONICAL_DATA = {
    "btc_data": "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv",
    "eth_data": "data/ethusd_3600s_2018-01-01_to_2025-12-31.csv",
    "spy_data": "data/SPY_1D.csv",
    "qqq_data": "data/QQQ_1D.csv",
    "bil_data": "data/BIL_1D.csv",
    "gld_data": "data/GLD_1D.csv",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Core v1 regime attribution for baseline, leading candidate, and fallback.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--btc-data", default=CANONICAL_DATA["btc_data"])
    p.add_argument("--eth-data", default=CANONICAL_DATA["eth_data"])
    p.add_argument("--spy-data", default=CANONICAL_DATA["spy_data"])
    p.add_argument("--qqq-data", default=CANONICAL_DATA["qqq_data"])
    p.add_argument("--bil-data", default=CANONICAL_DATA["bil_data"])
    p.add_argument("--gld-data", default=CANONICAL_DATA["gld_data"])
    p.add_argument("--data-start", default="2019-01-01")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--equity-fee", type=float, default=0.0001)
    p.add_argument("--base-slippage", type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--out-dir", default="artifacts/core_v1_regime_attribution")
    p.add_argument(
        "--skip-run",
        action="store_true",
        help="Reuse existing per-scenario stitched_oos_nav.csv files in --out-dir.",
    )
    return p.parse_args()


def require_canonical_paths(args: argparse.Namespace) -> None:
    expected = {k: (REPO_ROOT / v).resolve() for k, v in CANONICAL_DATA.items()}
    actual = {
        "btc_data": (REPO_ROOT / args.btc_data).resolve(),
        "eth_data": (REPO_ROOT / args.eth_data).resolve(),
        "spy_data": (REPO_ROOT / args.spy_data).resolve(),
        "qqq_data": (REPO_ROOT / args.qqq_data).resolve(),
        "bil_data": (REPO_ROOT / args.bil_data).resolve(),
        "gld_data": (REPO_ROOT / args.gld_data).resolve(),
    }
    drift = {k: str(v) for k, v in actual.items() if v != expected[k]}
    if drift:
        raise ValueError(
            "Non-canonical data path supplied. Core v1 regime attribution must use "
            f"{CANONICAL_DATA}. Drift: {drift}"
        )


def run_scenarios(args: argparse.Namespace) -> None:
    if args.skip_run:
        return

    runner = REPO_ROOT / "scripts" / "run_core_v1_candidate_wfo.py"
    for scenario in SCENARIOS:
        cmd = [
            sys.executable,
            str(runner),
            "--scenario",
            scenario,
            "--workers",
            str(args.workers),
            "--btc-data",
            args.btc_data,
            "--eth-data",
            args.eth_data,
            "--spy-data",
            args.spy_data,
            "--qqq-data",
            args.qqq_data,
            "--bil-data",
            args.bil_data,
            "--gld-data",
            args.gld_data,
            "--data-start",
            args.data_start,
            "--oos-start",
            args.oos_start,
            "--oos-end",
            args.oos_end,
            "--fee",
            str(args.fee),
            "--equity-fee",
            str(args.equity_fee),
            "--base-slippage",
            str(args.base_slippage),
            "--slippage-vol-factor",
            str(args.slippage_vol_factor),
            "--out-dir",
            args.out_dir,
        ]
        print("Running canonical WFO:", " ".join(cmd))
        subprocess.run(cmd, check=True)


def load_navs(out_dir: Path) -> dict[str, pd.Series]:
    navs: dict[str, pd.Series] = {}
    for scenario in SCENARIOS:
        path = out_dir / scenario / "stitched_oos_nav.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing stitched NAV for {scenario}: {path}")
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        nav = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().sort_index()
        nav.name = scenario
        navs[scenario] = nav
    return navs


def daily_nav(nav: pd.Series) -> pd.Series:
    out = nav.resample("D").last().dropna()
    out = out[~out.index.duplicated(keep="last")]
    return out


def daily_returns(nav: pd.Series) -> pd.Series:
    d = daily_nav(nav)
    return d.pct_change().dropna()


def load_close(path: str, name: str) -> pd.Series:
    df = pd.read_csv(REPO_ROOT / path)
    date_col = None
    for col in ("timestamp", "date", "datetime", "time"):
        if col in df.columns:
            date_col = col
            break
    if date_col is None:
        date_col = df.columns[0]
    if "close" not in df.columns:
        raise ValueError(f"{path} missing close column")
    idx = pd.to_datetime(df[date_col], utc=False)
    close = pd.Series(pd.to_numeric(df["close"], errors="coerce").values, index=idx, name=name).dropna().sort_index()
    return close


def build_regime_labels(args: argparse.Namespace, index: pd.DatetimeIndex) -> pd.DataFrame:
    labels = pd.DataFrame(index=pd.DatetimeIndex(index).sort_values().unique())
    labels.index.name = "date"
    labels["year"] = labels.index.year.astype(str)

    spy = load_close(args.spy_data, "SPY").resample("D").last().dropna()
    qqq = load_close(args.qqq_data, "QQQ").resample("D").last().dropna()
    btc = load_close(args.btc_data, "BTC").resample("D").last().dropna()

    spy_up = (spy > spy.rolling(175, min_periods=175).mean()).shift(1)
    qqq_up = (qqq > qqq.rolling(175, min_periods=175).mean()).shift(1)
    equity = pd.DataFrame({"spy_up": spy_up, "qqq_up": qqq_up}).reindex(labels.index, method="ffill")
    labels["equity_regime"] = "equity_mixed"
    labels.loc[(equity["spy_up"] == True) & (equity["qqq_up"] == True), "equity_regime"] = "equity_uptrend"
    labels.loc[(equity["spy_up"] == False) & (equity["qqq_up"] == False), "equity_regime"] = "equity_downtrend"

    btc_ma50 = btc.rolling(50, min_periods=50).mean()
    btc_ma200 = btc.rolling(200, min_periods=200).mean()
    btc_up = ((btc > btc_ma200) & (btc_ma50 > btc_ma200)).shift(1)
    btc_down = ((btc < btc_ma200) & (btc_ma50 < btc_ma200)).shift(1)
    crypto = pd.DataFrame({"btc_up": btc_up, "btc_down": btc_down}).reindex(labels.index, method="ffill")
    labels["crypto_regime"] = "crypto_mixed"
    labels.loc[crypto["btc_up"] == True, "crypto_regime"] = "crypto_uptrend"
    labels.loc[crypto["btc_down"] == True, "crypto_regime"] = "crypto_downtrend"

    btc_ret = btc.pct_change()
    rv21 = btc_ret.rolling(21, min_periods=21).std() * math.sqrt(365)
    q33 = rv21.rolling(252, min_periods=63).quantile(0.33).shift(1)
    q67 = rv21.rolling(252, min_periods=63).quantile(0.67).shift(1)
    rv21_lagged = rv21.shift(1)
    vol = pd.DataFrame({"rv21": rv21_lagged, "q33": q33, "q67": q67}).reindex(labels.index, method="ffill")
    labels["vol_regime"] = "vol_mid"
    labels.loc[vol["rv21"] <= vol["q33"], "vol_regime"] = "vol_low"
    labels.loc[vol["rv21"] >= vol["q67"], "vol_regime"] = "vol_high"

    labels["stress_window"] = "none"
    for name, (start, end) in STRESS_WINDOWS.items():
        mask = (labels.index >= pd.Timestamp(start)) & (labels.index <= pd.Timestamp(end))
        labels.loc[mask, "stress_window"] = name

    return labels.reset_index()


def max_drawdown_from_returns(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    eq = (1.0 + returns).cumprod()
    dd = eq / eq.cummax() - 1.0
    return float(dd.min())


def rolling_worst(returns: pd.Series, days: int) -> float:
    if len(returns) < days:
        return float("nan")
    return float((1.0 + returns).rolling(days).apply(lambda x: x.prod() - 1.0, raw=True).min())


def bucket_metrics(returns: pd.Series) -> dict[str, float | int]:
    returns = pd.to_numeric(returns, errors="coerce").dropna()
    n = int(len(returns))
    if n == 0:
        return {
            "n_days": 0,
            "total_return_pct": float("nan"),
            "annualized_return_pct": float("nan"),
            "volatility_ann_pct": float("nan"),
            "sharpe": float("nan"),
            "max_drawdown_pct": float("nan"),
            "worst_21d_return_pct": float("nan"),
            "worst_63d_return_pct": float("nan"),
            "positive_day_rate_pct": float("nan"),
            "final_equity": float("nan"),
        }

    growth = float((1.0 + returns).prod())
    total_return = growth - 1.0
    ann_return = growth ** (252.0 / n) - 1.0 if n >= 21 and growth > 0 else float("nan")
    vol = float(returns.std(ddof=0) * math.sqrt(252)) if n >= 2 else float("nan")
    sharpe = float(returns.mean() / returns.std(ddof=0) * math.sqrt(252)) if n >= 30 and returns.std(ddof=0) > 0 else float("nan")
    hit = float((returns > 0).mean())

    return {
        "n_days": n,
        "total_return_pct": round(total_return * 100.0, 2),
        "annualized_return_pct": round(ann_return * 100.0, 2) if pd.notna(ann_return) else float("nan"),
        "volatility_ann_pct": round(vol * 100.0, 2) if pd.notna(vol) else float("nan"),
        "sharpe": round(sharpe, 3) if pd.notna(sharpe) else float("nan"),
        "max_drawdown_pct": round(max_drawdown_from_returns(returns) * 100.0, 2),
        "worst_21d_return_pct": round(rolling_worst(returns, 21) * 100.0, 2) if n >= 21 else float("nan"),
        "worst_63d_return_pct": round(rolling_worst(returns, 63) * 100.0, 2) if n >= 63 else float("nan"),
        "positive_day_rate_pct": round(hit * 100.0, 2),
        "final_equity": round(100000.0 * growth, 2),
    }


def add_baseline_deltas(df: pd.DataFrame, bucket_col: str) -> pd.DataFrame:
    base = df[df["scenario"] == BASELINE].set_index(bucket_col)
    out = df.copy()
    for col in ("total_return_pct", "annualized_return_pct", "volatility_ann_pct", "sharpe", "max_drawdown_pct", "worst_21d_return_pct", "worst_63d_return_pct", "positive_day_rate_pct", "final_equity"):
        out[f"delta_vs_baseline_{col}"] = out.apply(
            lambda row: round(row[col] - base.loc[row[bucket_col], col], 4)
            if row[bucket_col] in base.index and pd.notna(row[col]) and pd.notna(base.loc[row[bucket_col], col])
            else float("nan"),
            axis=1,
        )
    return out


def summarize_by_label(
    scenario_returns: pd.DataFrame,
    labels: pd.DataFrame,
    label_col: str,
    output_bucket_col: str,
) -> pd.DataFrame:
    merged = scenario_returns.merge(labels[["date", label_col]], on="date", how="left")
    rows = []
    for (scenario, bucket), grp in merged.groupby(["scenario", label_col], dropna=False):
        rows.append({"scenario": scenario, output_bucket_col: bucket, **bucket_metrics(grp["daily_return"])})
    return add_baseline_deltas(pd.DataFrame(rows), output_bucket_col).sort_values([output_bucket_col, "scenario"])


def summarize_stress_windows(scenario_returns: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scenario, grp in scenario_returns.groupby("scenario"):
        s = grp.set_index("date")["daily_return"].sort_index()
        for name, (start, end) in STRESS_WINDOWS.items():
            r = s.loc[pd.Timestamp(start) : pd.Timestamp(end)]
            rows.append({"scenario": scenario, "stress_window": name, "start": start, "end": end, **bucket_metrics(r)})
    return add_baseline_deltas(pd.DataFrame(rows), "stress_window").sort_values(["stress_window", "scenario"])


def drawdown_state(nav: pd.Series) -> pd.Series:
    d = daily_nav(nav)
    dd = d / d.cummax() - 1.0
    state = pd.Series("recovery", index=d.index, name="drawdown_state")
    state.loc[dd >= -0.001] = "new_high"
    state.loc[(dd < -0.001) & (dd > -0.05)] = "shallow_drawdown"
    state.loc[dd <= -0.10] = "deep_drawdown"
    # One-day lag avoids labeling the return using its own close.
    return state.shift(1).fillna("new_high")


def summarize_drawdown_state(navs: dict[str, pd.Series], scenario_returns: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scenario, nav in navs.items():
        states = drawdown_state(nav).reset_index()
        states.columns = ["date", "drawdown_state"]
        ret = scenario_returns[scenario_returns["scenario"] == scenario].merge(states, on="date", how="left")
        for bucket, grp in ret.groupby("drawdown_state", dropna=False):
            rows.append({"scenario": scenario, "drawdown_state": bucket, **bucket_metrics(grp["daily_return"])})
    return add_baseline_deltas(pd.DataFrame(rows), "drawdown_state").sort_values(["drawdown_state", "scenario"])


def summarize_drawdown_events(navs: dict[str, pd.Series]) -> pd.DataFrame:
    rows = []
    for scenario, nav in navs.items():
        d = daily_nav(nav)
        dd = d / d.cummax() - 1.0
        in_dd = False
        peak_date = trough_date = None
        trough_dd = 0.0
        for date, value in dd.items():
            if not in_dd and value < -0.001:
                in_dd = True
                peak_date = d.loc[:date].idxmax()
                trough_date = date
                trough_dd = float(value)
            elif in_dd:
                if value < trough_dd:
                    trough_dd = float(value)
                    trough_date = date
                if value >= -0.001:
                    rows.append(
                        {
                            "scenario": scenario,
                            "peak": str(pd.Timestamp(peak_date).date()),
                            "trough": str(pd.Timestamp(trough_date).date()),
                            "recovery": str(pd.Timestamp(date).date()),
                            "drawdown_pct": round(trough_dd * 100.0, 2),
                            "recovery_days": int((pd.Timestamp(date) - pd.Timestamp(peak_date)).days),
                        }
                    )
                    in_dd = False
        if in_dd:
            rows.append(
                {
                    "scenario": scenario,
                    "peak": str(pd.Timestamp(peak_date).date()),
                    "trough": str(pd.Timestamp(trough_date).date()),
                    "recovery": "",
                    "drawdown_pct": round(trough_dd * 100.0, 2),
                    "recovery_days": "",
                }
            )
    return pd.DataFrame(rows).sort_values(["scenario", "drawdown_pct"]).groupby("scenario").head(5)


def make_daily_returns_frame(navs: dict[str, pd.Series]) -> pd.DataFrame:
    rows = []
    for scenario, nav in navs.items():
        d = daily_nav(nav)
        r = d.pct_change()
        df = pd.DataFrame({"date": d.index, "scenario": scenario, "nav": d.values, "daily_return": r.values})
        rows.append(df.dropna(subset=["daily_return"]))
    return pd.concat(rows, ignore_index=True)


def write_gate_report(out_dir: Path, tables: dict[str, pd.DataFrame], args: argparse.Namespace) -> None:
    year = tables["year_summary"]
    stress = tables["stress_window_summary"]
    dd_events = tables["drawdown_events"]

    def row(df: pd.DataFrame, scenario: str, col: str, value: str) -> pd.Series:
        hit = df[(df["scenario"] == scenario) & (df[col] == value)]
        return hit.iloc[0] if not hit.empty else pd.Series(dtype=object)

    lead = "candidate_btc1h_hedges_to_btc4h_gld_qqq"
    fallback = "candidate_btc1h_half_btc4h_half_qqq"

    lead_full = pd.read_csv(out_dir / lead / "summary.csv").iloc[0].to_dict()
    base_full = pd.read_csv(out_dir / BASELINE / "summary.csv").iloc[0].to_dict()
    fall_full = pd.read_csv(out_dir / fallback / "summary.csv").iloc[0].to_dict()

    lines = [
        "# Core v1 Regime Attribution Results",
        "",
        "## Purpose",
        "",
        "This artifact answers whether the leading Core v1 candidate wins broadly or is carried by one narrow/favorable regime.",
        "",
        "## Canonical data provenance",
        "",
    ]
    for key, path in CANONICAL_DATA.items():
        lines.append(f"- `{path}`")
    lines += [
        "",
        "The runner rejects non-canonical data paths to prevent the prior 2019-start crypto file parity drift from re-entering accepted validation.",
        "",
        "## Full-period parity check",
        "",
        "| Scenario | CAGR | Total return | MaxDD | Sharpe | Calmar | Final equity |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in (base_full, lead_full, fall_full):
        lines.append(
            f"| {r['scenario']} | {r['cagr_pct']:.2f}% | {r['total_return_pct']:.2f}% | "
            f"{r['max_drawdown_pct']:.2f}% | {r['sharpe']:.3f} | {r['calmar']:.3f} | {r['final_equity']:,.2f} |"
        )

    lines += [
        "",
        "## Annual attribution",
        "",
        "Candidate annual deltas versus baseline:",
        "",
        "| Year | Leading delta total return | Fallback delta total return |",
        "|---|---:|---:|",
    ]
    for yr in sorted(year["year"].dropna().unique()):
        lead_row = row(year, lead, "year", yr)
        fall_row = row(year, fallback, "year", yr)
        lines.append(
            f"| {yr} | {lead_row.get('delta_vs_baseline_total_return_pct', float('nan')):+.2f} pts | "
            f"{fall_row.get('delta_vs_baseline_total_return_pct', float('nan')):+.2f} pts |"
        )

    lines += [
        "",
        "## Stress-window attribution",
        "",
        "| Window | Leading delta total return | Leading delta maxDD | Fallback delta total return | Fallback delta maxDD |",
        "|---|---:|---:|---:|---:|",
    ]
    for window in STRESS_WINDOWS:
        lead_row = row(stress, lead, "stress_window", window)
        fall_row = row(stress, fallback, "stress_window", window)
        lines.append(
            f"| {window} | {lead_row.get('delta_vs_baseline_total_return_pct', float('nan')):+.2f} pts | "
            f"{lead_row.get('delta_vs_baseline_max_drawdown_pct', float('nan')):+.2f} pts | "
            f"{fall_row.get('delta_vs_baseline_total_return_pct', float('nan')):+.2f} pts | "
            f"{fall_row.get('delta_vs_baseline_max_drawdown_pct', float('nan')):+.2f} pts |"
        )

    lines += [
        "",
        "## Drawdown event check",
        "",
        "Largest reconstructed daily drawdown events:",
        "",
        "| Scenario | Peak | Trough | Recovery | Drawdown | Recovery days |",
        "|---|---|---|---|---:|---:|",
    ]
    for _, r in dd_events.iterrows():
        lines.append(
            f"| {r['scenario']} | {r['peak']} | {r['trough']} | {r['recovery']} | {r['drawdown_pct']:.2f}% | {r['recovery_days']} |"
        )

    lead_2022 = row(year, lead, "year", "2022")
    lead_2025 = row(year, lead, "year", "2025")
    fall_2022 = row(year, fallback, "year", "2022")
    lines += [
        "",
        "## Gate interpretation",
        "",
        f"- Leading candidate 2022 annual delta versus baseline: {lead_2022.get('delta_vs_baseline_total_return_pct', float('nan')):+.2f} pts.",
        f"- Leading candidate 2025 annual delta versus baseline: {lead_2025.get('delta_vs_baseline_total_return_pct', float('nan')):+.2f} pts.",
        f"- Conservative fallback 2022 annual delta versus baseline: {fall_2022.get('delta_vs_baseline_total_return_pct', float('nan')):+.2f} pts.",
        "",
        "Use this gate as follows:",
        "",
        "- GREEN if the leading candidate beats baseline across full-period metrics, is not carried by only one calendar year, remains acceptable in risk-off/crypto-down/high-vol buckets, and improves recovery behavior enough to justify the 2022 blemish.",
        "- YELLOW if the leading candidate wins full-period but attribution shows material dependence on one regime, with the conservative fallback providing smoother confirmation.",
        "- RED if edge is isolated to one narrow favorable bucket or risk-off/high-vol behavior is materially worse than baseline without offsetting recovery improvement.",
        "",
        "## Output files",
        "",
    ]
    for name in [
        "year_summary.csv",
        "stress_window_summary.csv",
        "drawdown_state_summary.csv",
        "drawdown_events.csv",
        "equity_regime_summary.csv",
        "crypto_regime_summary.csv",
        "vol_regime_summary.csv",
        "scenario_daily_returns.csv",
        "regime_labels.csv",
    ]:
        lines.append(f"- `{name}`")
    lines += ["", "_Research only. Not financial advice._"]
    (out_dir / "CORE_V1_REGIME_ATTRIBUTION_RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    require_canonical_paths(args)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_scenarios(args)
    navs = load_navs(out_dir)
    scenario_returns = make_daily_returns_frame(navs)
    scenario_returns.to_csv(out_dir / "scenario_daily_returns.csv", index=False)

    labels = build_regime_labels(args, pd.DatetimeIndex(scenario_returns["date"].unique()))
    labels.to_csv(out_dir / "regime_labels.csv", index=False)

    tables = {
        "year_summary": summarize_by_label(scenario_returns, labels, "year", "year"),
        "stress_window_summary": summarize_stress_windows(scenario_returns),
        "drawdown_state_summary": summarize_drawdown_state(navs, scenario_returns),
        "equity_regime_summary": summarize_by_label(scenario_returns, labels, "equity_regime", "equity_regime"),
        "crypto_regime_summary": summarize_by_label(scenario_returns, labels, "crypto_regime", "crypto_regime"),
        "vol_regime_summary": summarize_by_label(scenario_returns, labels, "vol_regime", "vol_regime"),
        "drawdown_events": summarize_drawdown_events(navs),
    }

    for name, table in tables.items():
        table.to_csv(out_dir / f"{name}.csv", index=False)

    metadata = {
        "scenarios": SCENARIOS,
        "baseline": BASELINE,
        "canonical_data": CANONICAL_DATA,
        "costs": {
            "fee": args.fee,
            "equity_fee": args.equity_fee,
            "base_slippage": args.base_slippage,
            "slippage_vol_factor": args.slippage_vol_factor,
        },
        "regime_labeling": {
            "equity": "SPY and QQQ above/below 175D SMA using one-day-lagged signals.",
            "crypto": "BTC close and 50D/200D trend using one-day-lagged signals.",
            "vol": "BTC 21D realized vol versus one-day-lagged rolling 252D 33/67 percentiles.",
            "drawdown_state": "Scenario-specific daily portfolio drawdown state, one-day lagged.",
        },
        "stress_windows": STRESS_WINDOWS,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    write_gate_report(out_dir, tables, args)

    print(f"Wrote Core v1 regime attribution artifacts to {out_dir}")


if __name__ == "__main__":
    main()
