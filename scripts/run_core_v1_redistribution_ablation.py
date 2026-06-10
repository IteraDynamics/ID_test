from __future__ import annotations

from pathlib import Path

import pandas as pd

from research.harness.metrics import compute_metrics

ROOT = Path("artifacts/core_v1_sleeve_contribution/baseline_40_35_15_10_parallel")
FOLDS = ROOT / "folds"
OUT = Path("artifacts/core_v1_sleeve_ablations/redistribution_baseline")
OUT.mkdir(parents=True, exist_ok=True)

# Redistribution scenarios use validated fold-level sleeve curves.
# A donor sleeve is removed from the fund. Its starting capital for each fold is
# redeployed into one or more target sleeve return streams for that same fold.
# This is an attribution/reallocation proxy, not a live portfolio policy change.
SCENARIOS = {
    "baseline_reconstructed": [],
    "BTC_1H_to_BTC_4H": [
        {"donor": "BTC_1H_trend", "targets": {"BTC_4H_trend": 1.0}},
    ],
    "ETH_4H_to_ETH_1H": [
        {"donor": "ETH_4H_trend", "targets": {"ETH_1H_trend": 1.0}},
    ],
    "BTC_hedge_to_ETH_hedge": [
        {"donor": "BTC_1H_hedge", "targets": {"ETH_1H_hedge": 1.0}},
    ],
    "hedges_to_GLD": [
        {"donor": "BTC_1H_hedge", "targets": {"GLD_1D_gold": 1.0}},
        {"donor": "ETH_1H_hedge", "targets": {"GLD_1D_gold": 1.0}},
    ],
    "hedges_to_QQQ": [
        {"donor": "BTC_1H_hedge", "targets": {"QQQ_1D_equity": 1.0}},
        {"donor": "ETH_1H_hedge", "targets": {"QQQ_1D_equity": 1.0}},
    ],
    "hedges_to_cash": [
        {"donor": "BTC_1H_hedge", "targets": {"CASH": 1.0}},
        {"donor": "ETH_1H_hedge", "targets": {"CASH": 1.0}},
    ],
    "BTC_1H_to_half_BTC4H_half_QQQ": [
        {"donor": "BTC_1H_trend", "targets": {"BTC_4H_trend": 0.5, "QQQ_1D_equity": 0.5}},
    ],
    "BTC_1H_and_hedges_to_BTC4H_GLD_QQQ": [
        {"donor": "BTC_1H_trend", "targets": {"BTC_4H_trend": 0.5, "QQQ_1D_equity": 0.5}},
        {"donor": "BTC_1H_hedge", "targets": {"GLD_1D_gold": 0.5, "QQQ_1D_equity": 0.5}},
        {"donor": "ETH_1H_hedge", "targets": {"GLD_1D_gold": 0.5, "QQQ_1D_equity": 0.5}},
    ],
}


def load_curve(path: Path, name: str | None = None) -> pd.Series:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if df.empty:
        return pd.Series(dtype=float, name=name or path.stem)
    s = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().sort_index()
    s.name = name or path.stem
    return s


def perf(nav: pd.Series) -> dict:
    m = compute_metrics(nav.dropna(), [], initial_capital=100_000.0)
    return {
        "cagr_pct": round(m.cagr_pct, 2),
        "total_return_pct": round(m.total_return_pct, 2),
        "max_drawdown_pct": round(m.max_drawdown_pct, 2),
        "sharpe": round(m.sharpe, 3),
        "calmar": round(m.calmar, 3),
        "final_equity": round(m.final_equity, 2),
    }


def annual(nav: pd.Series) -> dict[str, float]:
    daily = nav.resample("D").last().dropna()
    out: dict[str, float] = {}
    for y, grp in daily.groupby(daily.index.year):
        if len(grp) > 1 and float(grp.iloc[0]) != 0.0:
            out[str(y)] = round((float(grp.iloc[-1]) / float(grp.iloc[0]) - 1.0) * 100.0, 2)
    return out


def fold_dirs() -> list[Path]:
    dirs = [p for p in FOLDS.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: p.name)


def load_fold_curves(fold_dir: Path) -> tuple[pd.Series, dict[str, pd.Series]]:
    fund = load_curve(fold_dir / "stitched_fund_nav_from_sleeves.csv", "fund_nav")
    sleeve_dir = fold_dir / "stitched_sleeves"
    sleeves = {p.stem: load_curve(p, p.stem) for p in sleeve_dir.glob("*.csv")}
    return fund, sleeves


def aligned_sleeve_on_fund(fund: pd.Series, sleeve: pd.Series) -> pd.Series:
    return sleeve.reindex(fund.index).ffill().bfill()


def replacement_curve(fund: pd.Series, donor: pd.Series, target: str, sleeves: dict[str, pd.Series], weight: float) -> pd.Series:
    donor_on_fund = aligned_sleeve_on_fund(fund, donor)
    donor_initial = float(donor_on_fund.iloc[0]) * float(weight)

    if target.upper() == "CASH":
        return pd.Series(donor_initial, index=fund.index, name=f"replacement_{target}")

    if target not in sleeves:
        raise FileNotFoundError(f"Missing target sleeve curve: {target}")
    target_on_fund = aligned_sleeve_on_fund(fund, sleeves[target])
    target_initial = float(target_on_fund.iloc[0])
    if target_initial == 0.0:
        raise ValueError(f"Target sleeve starts at zero: {target}")
    growth = target_on_fund / target_initial
    return donor_initial * growth


def apply_scenario_to_fold(fund: pd.Series, sleeves: dict[str, pd.Series], reallocations: list[dict]) -> pd.Series:
    nav = fund.copy()
    for spec in reallocations:
        donor_name = spec["donor"]
        targets = spec["targets"]
        if donor_name not in sleeves:
            raise FileNotFoundError(f"Missing donor sleeve curve: {donor_name}")
        donor = aligned_sleeve_on_fund(fund, sleeves[donor_name])
        nav = nav - donor
        replacement = pd.Series(0.0, index=fund.index)
        weight_sum = sum(float(w) for w in targets.values())
        if abs(weight_sum - 1.0) > 1e-9:
            raise ValueError(f"Target weights for {donor_name} sum to {weight_sum}, not 1.0")
        for target_name, weight in targets.items():
            replacement = replacement + replacement_curve(fund, donor, target_name, sleeves, float(weight))
        nav = nav + replacement
    return nav


def run_scenario(name: str, reallocations: list[dict]) -> dict:
    running_nav = 100_000.0
    parts: list[pd.Series] = []

    for fold_dir in fold_dirs():
        fund, sleeves = load_fold_curves(fold_dir)
        scale = running_nav / float(fund.iloc[0])
        fund = fund * scale
        sleeves = {k: v * scale for k, v in sleeves.items()}
        fold_nav = apply_scenario_to_fold(fund, sleeves, reallocations)
        fold_nav.name = name
        parts.append(fold_nav)
        running_nav = float(fold_nav.iloc[-1])

    nav = pd.concat(parts).sort_index()
    nav = nav[~nav.index.duplicated(keep="last")]
    nav.name = name
    nav.to_csv(OUT / f"{name}_nav.csv", header=True)

    row = {"scenario": name}
    row["reallocations"] = ";".join(
        f"{r['donor']}=>" + "+".join(f"{w:g}*{t}" for t, w in r["targets"].items())
        for r in reallocations
    )
    row.update(perf(nav))
    row.update({f"ret_{k}": v for k, v in annual(nav).items()})
    return row


def main() -> None:
    rows = [run_scenario(name, reallocations) for name, reallocations in SCENARIOS.items()]
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "redistribution_summary.csv", index=False)
    print(df.to_string(index=False))
    print(f"\nWrote {OUT / 'redistribution_summary.csv'}")


if __name__ == "__main__":
    main()
