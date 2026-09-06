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
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd


from research.harness.metrics import compute_metrics


SCENARIOS = {
    "baseline_40_35_15_10": {
        "BTC_1H_trend": 0.10,
        "BTC_4H_trend": 0.10,
        "ETH_1H_trend": 0.10,
        "ETH_4H_trend": 0.10,
        "BTC_1H_hedge": 0.05,
        "ETH_1H_hedge": 0.05,
        "SPY_1D_equity": 0.175,
        "QQQ_1D_equity": 0.175,
        "GLD_1D_gold": 0.15,
    },
    "candidate_btc1h_hedges_to_btc4h_gld_qqq": {
        "BTC_1H_trend": 0.00,
        "BTC_4H_trend": 0.15,
        "ETH_1H_trend": 0.10,
        "ETH_4H_trend": 0.10,
        "BTC_1H_hedge": 0.00,
        "ETH_1H_hedge": 0.00,
        "SPY_1D_equity": 0.175,
        "QQQ_1D_equity": 0.275,
        "GLD_1D_gold": 0.20,
    },
    "candidate_btc1h_half_btc4h_half_qqq": {
        "BTC_1H_trend": 0.00,
        "BTC_4H_trend": 0.15,
        "ETH_1H_trend": 0.10,
        "ETH_4H_trend": 0.10,
        "BTC_1H_hedge": 0.05,
        "ETH_1H_hedge": 0.05,
        "SPY_1D_equity": 0.175,
        "QQQ_1D_equity": 0.225,
        "GLD_1D_gold": 0.15,
    },
}


# Existing runner defaults are already net of execution costs:
# - crypto fee 6 bps
# - equity ETF fee 1 bp
# - crypto base slippage 3 bps
# - crypto dynamic slippage vol factor 50
#
# This script stresses fee/slippage assumptions above those defaults. It does not
# change spread_k because the current audit runner does not expose spread via CLI.
COST_PROFILES = {
    "default_1x": {
        "cost_mult": 1.0,
        "fee": 0.0006,
        "equity_fee": 0.0001,
        "base_slippage": 3.0,
        "slippage_vol_factor": 50.0,
    },
    "cost_1_5x": {
        "cost_mult": 1.5,
        "fee": 0.0009,
        "equity_fee": 0.00015,
        "base_slippage": 4.5,
        "slippage_vol_factor": 75.0,
    },
    "cost_2x": {
        "cost_mult": 2.0,
        "fee": 0.0012,
        "equity_fee": 0.0002,
        "base_slippage": 6.0,
        "slippage_vol_factor": 100.0,
    },
    "cost_3x": {
        "cost_mult": 3.0,
        "fee": 0.0018,
        "equity_fee": 0.0003,
        "base_slippage": 9.0,
        "slippage_vol_factor": 150.0,
    },
}


DEFAULT_SCENARIOS = [
    "baseline_40_35_15_10",
    "candidate_btc1h_hedges_to_btc4h_gld_qqq",
    "candidate_btc1h_half_btc4h_half_qqq",
]

DEFAULT_PROFILES = ["default_1x", "cost_1_5x", "cost_2x", "cost_3x"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run Core v1 cost-sensitivity WFO tests for baseline and leading candidates.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--scenarios", nargs="+", default=DEFAULT_SCENARIOS, choices=sorted(SCENARIOS))
    p.add_argument("--profiles", nargs="+", default=DEFAULT_PROFILES, choices=sorted(COST_PROFILES))
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--spy-data", required=True)
    p.add_argument("--qqq-data", required=True)
    p.add_argument("--bil-data", required=True)
    p.add_argument("--gld-data", required=True)
    p.add_argument("--data-start", default="2019-01-01")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--out-dir", default="artifacts/core_v1_cost_sensitivity")
    return p.parse_args()


def years(start: str, end: str) -> list[tuple[str, str, str]]:
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    out: list[tuple[str, str, str]] = []
    for year in range(s.year, e.year + 1):
        ys = max(pd.Timestamp(f"{year}-01-01"), s)
        ye = min(pd.Timestamp(f"{year}-12-31"), e)
        out.append((str(year), str(ys.date()), str(ye.date())))
    return out


def run_fold(
    args: argparse.Namespace,
    profile_name: str,
    scenario_name: str,
    year: str,
    start: str,
    end: str,
) -> tuple[str, Path]:
    weights = SCENARIOS[scenario_name]
    profile = COST_PROFILES[profile_name]
    fold_dir = Path(args.out_dir) / profile_name / scenario_name / "folds" / year
    fold_dir.mkdir(parents=True, exist_ok=True)

    patch = fold_dir / "run_fold_patch.py"
    patch.write_text(
        f'''
from argparse import Namespace
from pathlib import Path
import sys

# run_fold_patch.py lives under:
# artifacts/core_v1_cost_sensitivity/<profile>/<scenario>/folds/<year>/
# parents[6] is the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[6]))

import scripts.run_core_v1_sleeve_contribution_audit as audit
from scripts.run_multi_strategy_fund import _build_sleeves as base_build

WEIGHTS = {weights!r}


def custom_build_sleeves(args):
    specs = base_build(args)
    labels = {{s.label for s in specs}}
    missing = set(WEIGHTS) - labels
    if missing:
        raise ValueError(f"Missing sleeve labels: {{sorted(missing)}}")
    total = sum(WEIGHTS.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"Scenario weights sum to {{total}}, not 1.0")
    out = []
    for s in specs:
        w = WEIGHTS.get(s.label, 0.0)
        s.capital = args.capital * w
        if s.capital > 0:
            out.append(s)
    return out


audit._build_sleeves = custom_build_sleeves

args = Namespace(
    btc_data=r"{args.btc_data}",
    eth_data=r"{args.eth_data}",
    spy_data=r"{args.spy_data}",
    qqq_data=r"{args.qqq_data}",
    bil_data=r"{args.bil_data}",
    gld_data=r"{args.gld_data}",
    capital=100000.0,
    trend_weight=0.40,
    equity_weight=0.35,
    gold_weight=0.15,
    hedge_weight=0.10,
    mr_weight=0.00,
    data_start="{args.data_start}",
    oos_start="{start}",
    oos_end="{end}",
    fee={profile['fee']},
    equity_fee={profile['equity_fee']},
    base_slippage={profile['base_slippage']},
    slippage_vol_factor={profile['slippage_vol_factor']},
    cooldown=2,
    mr_cooldown=12,
    rebalance_threshold=0.02,
    out_dir=r"{fold_dir}",
)

audit.run_audit(args)
''',
        encoding="utf-8",
    )

    proc = subprocess.run([sys.executable, str(patch)], capture_output=True, text=True)
    (fold_dir / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (fold_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"{profile_name}/{scenario_name} fold {year} failed. See {fold_dir / 'stderr.txt'}")
    return year, fold_dir


def load_nav(path: Path) -> pd.Series:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().sort_index()


def metrics(nav: pd.Series) -> dict:
    m = compute_metrics(nav, [], initial_capital=100000.0)
    return {
        "cagr_pct": round(m.cagr_pct, 2),
        "total_return_pct": round(m.total_return_pct, 2),
        "max_drawdown_pct": round(m.max_drawdown_pct, 2),
        "sharpe": round(m.sharpe, 3),
        "calmar": round(m.calmar, 3),
        "final_equity": round(m.final_equity, 2),
    }


def annual(nav: pd.Series) -> dict[str, float]:
    d = nav.resample("D").last().dropna()
    return {
        str(y): round((g.iloc[-1] / g.iloc[0] - 1) * 100, 2)
        for y, g in d.groupby(d.index.year)
        if len(g) > 1 and float(g.iloc[0]) != 0.0
    }


def run_profile_scenario(args: argparse.Namespace, profile_name: str, scenario_name: str) -> dict:
    out = Path(args.out_dir) / profile_name / scenario_name
    out.mkdir(parents=True, exist_ok=True)

    folds = years(args.oos_start, args.oos_end)
    workers = max(1, min(args.workers, len(folds)))
    print(f"Running {profile_name} / {scenario_name}: {len(folds)} folds with {workers} workers")

    fold_dirs: list[tuple[str, Path]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run_fold, args, profile_name, scenario_name, y, s, e) for y, s, e in folds]
        for fut in as_completed(futs):
            year, fold_dir = fut.result()
            nav = load_nav(fold_dir / "stitched_fund_nav_from_sleeves.csv")
            print(f"  Fold {year} complete: {metrics(nav)}")
            fold_dirs.append((year, fold_dir))

    running = 100000.0
    parts: list[pd.Series] = []
    for year, fold_dir in sorted(fold_dirs):
        nav = load_nav(fold_dir / "stitched_fund_nav_from_sleeves.csv")
        scale = running / nav.iloc[0]
        nav = nav * scale
        parts.append(nav)
        running = float(nav.iloc[-1])

    stitched = pd.concat(parts).sort_index()
    stitched = stitched[~stitched.index.duplicated(keep="last")]
    stitched.name = scenario_name
    stitched.to_csv(out / "stitched_oos_nav.csv", header=True)

    profile = COST_PROFILES[profile_name]
    result = {
        "cost_profile": profile_name,
        "cost_mult": profile["cost_mult"],
        "scenario": scenario_name,
        "fee": profile["fee"],
        "equity_fee": profile["equity_fee"],
        "base_slippage": profile["base_slippage"],
        "slippage_vol_factor": profile["slippage_vol_factor"],
        **metrics(stitched),
    }
    result.update({f"ret_{k}": v for k, v in annual(stitched).items()})
    pd.DataFrame([result]).to_csv(out / "summary.csv", index=False)
    print(pd.DataFrame([result]).to_string(index=False))
    print(f"Wrote {out / 'summary.csv'}")
    return result


def add_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for profile_name, grp in summary.groupby("cost_profile", sort=False):
        if "baseline_40_35_15_10" not in set(grp["scenario"]):
            rows.append(grp)
            continue
        base = grp.loc[grp["scenario"] == "baseline_40_35_15_10"].iloc[0]
        g = grp.copy()
        for col in ["cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "final_equity", "ret_2022", "ret_2025"]:
            if col in g.columns:
                g[f"delta_{col}"] = g[col] - base[col]
        rows.append(g)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    args = parse_args()
    root = Path(args.out_dir)
    root.mkdir(parents=True, exist_ok=True)

    results = []
    for profile_name in args.profiles:
        for scenario_name in args.scenarios:
            results.append(run_profile_scenario(args, profile_name, scenario_name))

    summary = pd.DataFrame(results)
    summary = add_deltas(summary)
    summary = summary.sort_values(["cost_mult", "scenario"]).reset_index(drop=True)
    summary.to_csv(root / "summary.csv", index=False)

    display_cols = [
        "cost_profile",
        "scenario",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "calmar",
        "final_equity",
        "ret_2022",
        "ret_2025",
        "delta_cagr_pct",
        "delta_max_drawdown_pct",
        "delta_sharpe",
        "delta_calmar",
    ]
    display_cols = [c for c in display_cols if c in summary.columns]
    print("\n=== COST SENSITIVITY SUMMARY ===")
    print(summary[display_cols].round(3).to_string(index=False))
    print(f"\nWrote {root / 'summary.csv'}")


if __name__ == "__main__":
    main()
