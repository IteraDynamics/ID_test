from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.harness.metrics import compute_metrics


DEFAULT_SCENARIO = "candidate_btc1h_hedges_to_btc4h_gld_qqq"
DEFAULT_MATRIX = (
    "artifacts/trend_persistence_v0/portfolio_integration/core_wfo/"
    f"{DEFAULT_SCENARIO}/stitched_sleeve_equity_matrix.csv"
)
DEFAULT_NAV = (
    "artifacts/trend_persistence_v0/portfolio_integration/core_wfo/"
    f"{DEFAULT_SCENARIO}/stitched_fund_nav_from_sleeves.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a formal Core v1 sleeve-level attribution report from the canonical sleeve matrix.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--matrix", default=DEFAULT_MATRIX)
    parser.add_argument("--nav", default=DEFAULT_NAV)
    parser.add_argument("--initial-capital", type=float, default=100000.0)
    parser.add_argument("--out-dir", default="artifacts/core_v1_sleeve_attribution")
    parser.add_argument("--report-title", default="Core v1 Sleeve-Level Attribution Report")
    return parser.parse_args()


def _read_matrix(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    frame = frame.apply(pd.to_numeric, errors="coerce").sort_index().ffill().dropna(how="all")
    if frame.empty:
        raise ValueError(f"Empty sleeve matrix: {path}")
    return frame


def _read_series(path: Path) -> pd.Series:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    series = pd.to_numeric(frame.iloc[:, 0], errors="coerce").dropna().sort_index()
    series.index = pd.to_datetime(series.index).tz_localize(None)
    if series.empty:
        raise ValueError(f"Empty NAV series: {path}")
    return series


def _metrics(nav: pd.Series, initial_capital: float) -> dict[str, float]:
    result = compute_metrics(nav.dropna(), [], initial_capital=initial_capital)
    return {
        "cagr_pct": float(result.cagr_pct),
        "total_return_pct": float(result.total_return_pct),
        "max_drawdown_pct": float(result.max_drawdown_pct),
        "sharpe": float(result.sharpe),
        "calmar": float(result.calmar),
        "volatility_ann_pct": float(result.volatility_ann_pct),
        "final_equity": float(result.final_equity),
    }


def _annual_return(nav: pd.Series) -> pd.Series:
    daily = nav.resample("D").last().dropna()
    return daily.groupby(daily.index.year).apply(lambda x: float(x.iloc[-1] / x.iloc[0] - 1.0))


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _standalone_sleeve_nav(curve: pd.Series) -> pd.Series:
    initial = float(curve.iloc[0])
    return initial + curve.diff().fillna(0.0).cumsum()


def _leave_one_out_nav(matrix: pd.DataFrame, sleeve: str, initial_capital: float) -> pd.Series:
    pnl = matrix.diff().fillna(0.0)
    kept = pnl.drop(columns=[sleeve]).sum(axis=1)
    nav = initial_capital + kept.cumsum()
    nav.name = f"core_without_{sleeve}"
    return nav


def _variance_contribution(matrix: pd.DataFrame) -> pd.DataFrame:
    daily = matrix.resample("D").last().pct_change().dropna(how="all")
    daily = daily.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    portfolio = daily.sum(axis=1)
    portfolio_var = float(portfolio.var())
    rows: list[dict[str, float | str]] = []
    for sleeve in daily.columns:
        covariance = float(daily[sleeve].cov(portfolio))
        contribution = covariance / portfolio_var if portfolio_var > 0 else np.nan
        rows.append(
            {
                "sleeve": sleeve,
                "daily_covariance_with_fund": covariance,
                "variance_contribution_fraction": contribution,
                "variance_contribution_pct": contribution * 100.0 if np.isfinite(contribution) else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("variance_contribution_fraction", ascending=False)


def _major_drawdowns(nav: pd.Series, count: int = 5) -> pd.DataFrame:
    dd = _drawdown(nav)
    candidates: list[dict[str, object]] = []
    in_dd = False
    start = peak = trough = recovery = None
    trough_value = 0.0
    for ts, value in dd.items():
        if value < 0 and not in_dd:
            in_dd = True
            start = ts
            peak = nav.loc[:ts].idxmax()
            trough = ts
            trough_value = float(value)
        elif in_dd and value < trough_value:
            trough = ts
            trough_value = float(value)
        elif in_dd and value >= 0:
            recovery = ts
            candidates.append(
                {
                    "peak": peak,
                    "start": start,
                    "trough": trough,
                    "recovery": recovery,
                    "max_drawdown_pct": trough_value * 100.0,
                }
            )
            in_dd = False
    if in_dd:
        candidates.append(
            {
                "peak": peak,
                "start": start,
                "trough": trough,
                "recovery": pd.NaT,
                "max_drawdown_pct": trough_value * 100.0,
            }
        )
    return pd.DataFrame(candidates).sort_values("max_drawdown_pct").head(count).reset_index(drop=True)


def _fmt(value: float, digits: int = 2) -> str:
    return "n/a" if pd.isna(value) else f"{value:.{digits}f}"


def _write_markdown(
    path: Path,
    title: str,
    baseline: dict[str, float],
    contribution: pd.DataFrame,
    standalone: pd.DataFrame,
    leave_one_out: pd.DataFrame,
    risk: pd.DataFrame,
    major_dd: pd.DataFrame,
) -> None:
    lines = [
        f"# {title}",
        "",
        "**Status:** Historical research attribution  ",
        "**Runtime impact:** None  ",
        "",
        "## Executive Summary",
        "",
        "This report attributes the canonical Core v1 walk-forward portfolio to its active sleeves using exact sleeve-level equity curves. Accounting attribution reconciles to the canonical fund NAV. Leave-one-out results are counterfactual research reconstructions that remove one sleeve's realized P&L while leaving the remaining sleeve paths unchanged; they are informative but are not a substitute for rerunning the full allocator.",
        "",
        "## Canonical Core Baseline",
        "",
        f"- CAGR: {_fmt(baseline['cagr_pct'])}%",
        f"- Total return: {_fmt(baseline['total_return_pct'])}%",
        f"- Sharpe: {_fmt(baseline['sharpe'], 3)}",
        f"- Calmar: {_fmt(baseline['calmar'], 3)}",
        f"- Maximum drawdown: {_fmt(baseline['max_drawdown_pct'])}%",
        f"- Final equity: ${baseline['final_equity']:,.2f}",
        "",
        "## Dollar Contribution",
        "",
        contribution.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Standalone Sleeve Metrics",
        "",
        standalone.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Leave-One-Out Portfolio Impact",
        "",
        leave_one_out.to_markdown(index=False, floatfmt=".3f"),
        "",
        "Interpretation: positive metric deltas in the `without_minus_core` columns mean the portfolio improved after removing the sleeve. Negative values mean the sleeve improved the canonical portfolio on that metric.",
        "",
        "## Risk Contribution",
        "",
        risk.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Major Fund Drawdowns",
        "",
        major_dd.to_markdown(index=False),
        "",
        "## Generated Figures",
        "",
        "- `figures/cumulative_sleeve_pnl.png`",
        "- `figures/sleeve_dollar_contribution.png`",
        "- `figures/sleeve_daily_return_correlation.png`",
        "- `figures/leave_one_out_sharpe_calmar.png`",
        "- `figures/fund_and_sleeve_drawdowns.png`",
        "",
        "## Methodological Limits",
        "",
        "- Historical and walk-forward results are not live performance.",
        "- Sleeve-return correlations and variance attribution are calculated from daily changes in the stitched sleeve curves.",
        "- Leave-one-out analysis does not rerun dynamic capital allocation, rebalancing, or interaction effects; it removes one realized sleeve P&L stream from the canonical path.",
        "- A sleeve can have low standalone return yet still be valuable through diversification and drawdown mitigation.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    matrix_path = (REPO_ROOT / args.matrix).resolve()
    nav_path = (REPO_ROOT / args.nav).resolve()
    out_dir = (REPO_ROOT / args.out_dir).resolve()
    figures_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    matrix = _read_matrix(matrix_path)
    canonical_nav = _read_series(nav_path)
    common = matrix.index.intersection(canonical_nav.index)
    matrix = matrix.loc[common]
    canonical_nav = canonical_nav.loc[common]

    reconciliation = float((matrix.sum(axis=1) - canonical_nav).abs().max())
    if reconciliation > 1e-6:
        raise RuntimeError(f"Canonical matrix does not reconcile to fund NAV; max delta={reconciliation}")

    baseline = _metrics(canonical_nav, args.initial_capital)
    initial_values = matrix.iloc[0]
    ending_values = matrix.iloc[-1]
    pnl_dollars = ending_values - initial_values
    contribution = pd.DataFrame(
        {
            "sleeve": matrix.columns,
            "initial_capital": initial_values.values,
            "ending_equity": ending_values.values,
            "pnl_dollars": pnl_dollars.values,
            "share_of_total_pnl_pct": pnl_dollars.values / float(pnl_dollars.sum()) * 100.0,
            "return_on_assigned_capital_pct": pnl_dollars.values / initial_values.values * 100.0,
        }
    ).sort_values("pnl_dollars", ascending=False)

    standalone_rows: list[dict[str, float | str]] = []
    for sleeve in matrix.columns:
        nav = _standalone_sleeve_nav(matrix[sleeve])
        metrics = _metrics(nav, float(nav.iloc[0]))
        standalone_rows.append({"sleeve": sleeve, **metrics})
    standalone = pd.DataFrame(standalone_rows).sort_values("sharpe", ascending=False)

    loo_rows: list[dict[str, float | str]] = []
    loo_navs: dict[str, pd.Series] = {}
    for sleeve in matrix.columns:
        nav = _leave_one_out_nav(matrix, sleeve, args.initial_capital)
        loo_navs[sleeve] = nav
        metrics = _metrics(nav, args.initial_capital)
        loo_rows.append(
            {
                "removed_sleeve": sleeve,
                **metrics,
                "without_minus_core_cagr_pct": metrics["cagr_pct"] - baseline["cagr_pct"],
                "without_minus_core_sharpe": metrics["sharpe"] - baseline["sharpe"],
                "without_minus_core_calmar": metrics["calmar"] - baseline["calmar"],
                "without_minus_core_max_drawdown_pct": metrics["max_drawdown_pct"] - baseline["max_drawdown_pct"],
            }
        )
    leave_one_out = pd.DataFrame(loo_rows).sort_values("without_minus_core_sharpe", ascending=False)

    daily_returns = matrix.resample("D").last().pct_change().dropna(how="all")
    correlation = daily_returns.corr()
    risk = _variance_contribution(matrix)
    major_dd = _major_drawdowns(canonical_nav)

    annual_pnl = matrix.diff().fillna(0.0).resample("YE").sum()
    annual_pnl.index = annual_pnl.index.year
    annual_pnl.index.name = "year"

    contribution.to_csv(out_dir / "sleeve_contribution_summary.csv", index=False)
    standalone.to_csv(out_dir / "sleeve_standalone_metrics.csv", index=False)
    leave_one_out.to_csv(out_dir / "sleeve_leave_one_out_metrics.csv", index=False)
    risk.to_csv(out_dir / "sleeve_variance_contribution.csv", index=False)
    correlation.to_csv(out_dir / "sleeve_daily_return_correlation.csv")
    annual_pnl.to_csv(out_dir / "sleeve_annual_pnl_dollars.csv")
    major_dd.to_csv(out_dir / "fund_major_drawdowns.csv", index=False)

    cumulative_pnl = matrix.subtract(matrix.iloc[0], axis=1)
    ax = cumulative_pnl.plot(figsize=(12, 7), linewidth=1.4)
    ax.set_title("Core v1 cumulative sleeve P&L")
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative P&L ($)")
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(figures_dir / "cumulative_sleeve_pnl.png", dpi=180)
    plt.close()

    ax = contribution.sort_values("pnl_dollars").plot.barh(
        x="sleeve", y="pnl_dollars", figsize=(10, 6), legend=False
    )
    ax.set_title("Core v1 sleeve dollar contribution")
    ax.set_xlabel("P&L contribution ($)")
    ax.set_ylabel("")
    ax.grid(True, axis="x", alpha=0.25)
    plt.tight_layout()
    plt.savefig(figures_dir / "sleeve_dollar_contribution.png", dpi=180)
    plt.close()

    fig, ax = plt.subplots(figsize=(9, 8))
    image = ax.imshow(correlation.values, aspect="auto")
    ax.set_xticks(range(len(correlation.columns)), correlation.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(correlation.index)), correlation.index)
    ax.set_title("Core v1 sleeve daily-return correlation")
    for i in range(len(correlation.index)):
        for j in range(len(correlation.columns)):
            ax.text(j, i, f"{correlation.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(figures_dir / "sleeve_daily_return_correlation.png", dpi=180)
    plt.close()

    comparison = leave_one_out.set_index("removed_sleeve")[["sharpe", "calmar"]]
    comparison.loc["CORE_BASELINE"] = [baseline["sharpe"], baseline["calmar"]]
    ax = comparison.plot.bar(figsize=(12, 6))
    ax.set_title("Core v1 leave-one-out Sharpe and Calmar")
    ax.set_xlabel("Removed sleeve")
    ax.set_ylabel("Ratio")
    ax.grid(True, axis="y", alpha=0.25)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(figures_dir / "leave_one_out_sharpe_calmar.png", dpi=180)
    plt.close()

    drawdowns = pd.DataFrame({"CORE": _drawdown(canonical_nav)})
    for sleeve in matrix.columns:
        drawdowns[sleeve] = _drawdown(_standalone_sleeve_nav(matrix[sleeve]))
    ax = (drawdowns * 100.0).plot(figsize=(12, 7), linewidth=1.1)
    ax.set_title("Core v1 fund and sleeve drawdowns")
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(figures_dir / "fund_and_sleeve_drawdowns.png", dpi=180)
    plt.close()

    summary = {
        "report": args.report_title,
        "matrix": str(matrix_path),
        "nav": str(nav_path),
        "rows": len(matrix),
        "sleeves": list(matrix.columns),
        "reconciliation_delta": reconciliation,
        "baseline": baseline,
        "largest_positive_contributor": contribution.iloc[0].to_dict(),
        "largest_negative_contributor": contribution.iloc[-1].to_dict(),
        "best_leave_one_out_sharpe_delta": leave_one_out.iloc[0].to_dict(),
        "methodological_note": "Leave-one-out removes realized sleeve P&L from the canonical path; it does not rerun allocation or rebalancing.",
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    _write_markdown(
        out_dir / "CORE_V1_SLEEVE_ATTRIBUTION_REPORT.md",
        args.report_title,
        baseline,
        contribution.round(4),
        standalone.round(4),
        leave_one_out.round(4),
        risk.round(6),
        major_dd,
    )

    print("Core v1 sleeve attribution report complete")
    print(f"Rows: {len(matrix):,}")
    print(f"Sleeves: {list(matrix.columns)}")
    print(f"Reconciliation delta: {reconciliation:.12f}")
    print(f"Report: {out_dir / 'CORE_V1_SLEEVE_ATTRIBUTION_REPORT.md'}")
    print(f"Tables and figures: {out_dir}")


if __name__ == "__main__":
    main()
