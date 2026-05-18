"""Walk-forward result aggregation, reporting, and artifact generation."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.ml.validation.walk_forward import FoldResult


# ── Aggregation ───────────────────────────────────────────────────────────────

def _safe_mean(values: list) -> float | None:
    clean = [v for v in values if v is not None and not math.isnan(float(v))]
    return round(float(np.mean(clean)), 4) if clean else None


def _safe_median(values: list) -> float | None:
    clean = [v for v in values if v is not None and not math.isnan(float(v))]
    return round(float(np.median(clean)), 4) if clean else None


def aggregate(fold_results: list[FoldResult]) -> dict[str, Any]:
    """Compute aggregate statistics across all non-skipped folds."""
    active = [r for r in fold_results if not r.skipped]
    n = len(active)
    n_total = len(fold_results)

    if n == 0:
        return {"error": "All folds were skipped.", "n_folds": 0}

    delta_keys = [
        "delta_cagr_pct",
        "delta_max_drawdown_pct",
        "delta_sharpe",
        "delta_calmar",
        "delta_total_slippage_cost",
        "delta_turnover_x_nav_adj",
        "delta_avg_cost_per_trade_bps",
    ]

    delta_means: dict[str, Any] = {}
    delta_medians: dict[str, Any] = {}
    for k in delta_keys:
        vals = [r.delta.get(k) for r in active]
        delta_means[k] = _safe_mean(vals)
        delta_medians[k] = _safe_median(vals)

    improved_sharpe = sum(1 for r in active if r.cal_improved_sharpe)
    improved_calmar = sum(1 for r in active if r.cal_improved_calmar)
    improved_dd = sum(1 for r in active if r.cal_improved_dd)
    improved_slippage = sum(1 for r in active if r.cal_improved_slippage)

    # Best/worst fold by delta_calmar
    best = max(active, key=lambda r: r.delta.get("delta_calmar") or float("-inf"))
    worst = min(active, key=lambda r: r.delta.get("delta_calmar") or float("inf"))

    conclusion = _conclude(n, improved_sharpe, improved_calmar, improved_dd)

    return {
        "n_folds_total": n_total,
        "n_folds_active": n,
        "n_folds_skipped": n_total - n,
        "improved_sharpe": improved_sharpe,
        "improved_calmar": improved_calmar,
        "improved_dd": improved_dd,
        "improved_slippage": improved_slippage,
        "delta_means": delta_means,
        "delta_medians": delta_medians,
        "best_fold_id": best.fold_spec.fold_id,
        "best_fold_delta_calmar": best.delta.get("delta_calmar"),
        "worst_fold_id": worst.fold_spec.fold_id,
        "worst_fold_delta_calmar": worst.delta.get("delta_calmar"),
        "conclusion": conclusion,
    }


def _conclude(n: int, improved_sharpe: int, improved_calmar: int, improved_dd: int) -> str:
    """Produce a plain-English robustness assessment."""
    if n == 0:
        return "no data"

    robust_threshold = max(1, int(round(0.75 * n)))  # ≥ 75% of folds
    mixed_threshold = max(1, int(round(0.50 * n)))    # ≥ 50% of folds

    # Primary signal: risk-adjusted return (Sharpe + Calmar)
    primary = min(improved_sharpe, improved_calmar)
    # Secondary: drawdown reduction
    secondary = improved_dd

    if primary >= robust_threshold and secondary >= mixed_threshold:
        return "likely robust"
    elif primary >= mixed_threshold or secondary >= robust_threshold:
        return "mixed / regime-dependent"
    else:
        return "likely overfit"


# ── Serialisation ─────────────────────────────────────────────────────────────

def _fold_to_dict(r: FoldResult) -> dict[str, Any]:
    return {
        "fold": r.fold_spec.to_dict(),
        "skipped": r.skipped,
        "skip_reason": r.skip_reason,
        "training": {
            "n_train_samples": r.n_train_samples,
            "calibrator_fitted": r.calibrator_fitted,
            "calibration_method": r.calibration_method,
        },
        "calibration_quality": {
            "n_test_cycles": r.n_test_cycles,
            "win_rate_test": r.win_rate_test,
            "brier_before": r.brier_before,
            "brier_after": r.brier_after,
            "ece_before": r.ece_before,
            "ece_after": r.ece_after,
        },
        "baseline": r.baseline,
        "calibrated": r.calibrated,
        "delta": r.delta,
        "improvements": {
            "sharpe": r.cal_improved_sharpe,
            "calmar": r.cal_improved_calmar,
            "dd": r.cal_improved_dd,
            "slippage": r.cal_improved_slippage,
        },
    }


def to_json(fold_results: list[FoldResult], agg: dict) -> dict:
    return {
        "schema_version": "1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "folds": [_fold_to_dict(r) for r in fold_results],
        "aggregate": agg,
    }


def to_dataframe(fold_results: list[FoldResult]) -> pd.DataFrame:
    """One row per fold with key metrics for both baseline and calibrated."""
    rows = []
    for r in fold_results:
        if r.skipped:
            rows.append({
                "fold_id": r.fold_spec.fold_id,
                "test_period": f"{r.fold_spec.test_start}→{r.fold_spec.test_end}",
                "skipped": True,
            })
            continue

        def _g(d: dict, k: str):
            return d.get(k)

        rows.append({
            "fold_id": r.fold_spec.fold_id,
            "train_period": f"{r.fold_spec.train_start}→{r.fold_spec.train_end}",
            "test_period": f"{r.fold_spec.test_start}→{r.fold_spec.test_end}",
            "skipped": False,
            "n_train_samples": r.n_train_samples,
            "calibrator_fitted": r.calibrator_fitted,
            "calibration_method": r.calibration_method,
            "n_test_cycles": r.n_test_cycles,
            "win_rate_test": r.win_rate_test,
            "brier_before": r.brier_before,
            "brier_after": r.brier_after,
            "ece_before": r.ece_before,
            "ece_after": r.ece_after,
            # Baseline
            "base_cagr": _g(r.baseline, "cagr_pct"),
            "base_dd": _g(r.baseline, "max_drawdown_pct"),
            "base_sharpe": _g(r.baseline, "sharpe"),
            "base_calmar": _g(r.baseline, "calmar"),
            "base_slippage": _g(r.baseline, "total_slippage_cost"),
            "base_turnover_nav": _g(r.baseline, "turnover_x_nav_adj"),
            "base_trades": _g(r.baseline, "n_trades"),
            # Calibrated
            "cal_cagr": _g(r.calibrated, "cagr_pct"),
            "cal_dd": _g(r.calibrated, "max_drawdown_pct"),
            "cal_sharpe": _g(r.calibrated, "sharpe"),
            "cal_calmar": _g(r.calibrated, "calmar"),
            "cal_slippage": _g(r.calibrated, "total_slippage_cost"),
            "cal_turnover_nav": _g(r.calibrated, "turnover_x_nav_adj"),
            "cal_trades": _g(r.calibrated, "n_trades"),
            # Deltas
            "delta_cagr": _g(r.delta, "delta_cagr_pct"),
            "delta_dd": _g(r.delta, "delta_max_drawdown_pct"),
            "delta_sharpe": _g(r.delta, "delta_sharpe"),
            "delta_calmar": _g(r.delta, "delta_calmar"),
            "delta_slippage": _g(r.delta, "delta_total_slippage_cost"),
        })
    return pd.DataFrame(rows)


# ── Markdown summary ──────────────────────────────────────────────────────────

def to_markdown(fold_results: list[FoldResult], agg: dict) -> str:
    active = [r for r in fold_results if not r.skipped]
    lines: list[str] = []

    lines.append("# Walk-Forward Validation Report")
    lines.append("")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # ── Fold-by-fold performance table ────────────────────────────────────
    lines.append("## Fold-by-Fold Strategy Performance")
    lines.append("")
    lines.append("| Fold | Test Period | | CAGR | Max DD | Sharpe | Calmar | Slippage |")
    lines.append("|------|------------|---|-----:|-------:|-------:|-------:|---------:|")

    for r in fold_results:
        if r.skipped:
            lines.append(f"| {r.fold_spec.fold_id} | {r.fold_spec.test_start}→{r.fold_spec.test_end} | — | *skipped* | | | | |")
            continue

        def _fmt(d, k, fmt=".1f"):
            v = d.get(k)
            return f"{v:{fmt}}" if v is not None else "—"

        for label, d in [("Base", r.baseline), ("Cal ", r.calibrated)]:
            mark = ""
            if label == "Cal ":
                marks = []
                if r.cal_improved_sharpe:
                    marks.append("✓S")
                if r.cal_improved_calmar:
                    marks.append("✓C")
                if r.cal_improved_dd:
                    marks.append("✓DD")
                mark = " ".join(marks)
            slip = d.get("total_slippage_cost")
            slip_str = f"${slip:,.0f}" if slip is not None else "—"
            lines.append(
                f"| {r.fold_spec.fold_id} | {r.fold_spec.test_start}→{r.fold_spec.test_end} "
                f"| {label} "
                f"| {_fmt(d, 'cagr_pct')}% "
                f"| {_fmt(d, 'max_drawdown_pct')}% "
                f"| {_fmt(d, 'sharpe', '.3f')} "
                f"| {_fmt(d, 'calmar', '.3f')} "
                f"| {slip_str} {mark}|"
            )
    lines.append("")

    # ── Calibration quality table ─────────────────────────────────────────
    lines.append("## Calibration Quality (Out-of-Sample)")
    lines.append("")
    lines.append("| Fold | Test Period | Train Samples | Test Cycles | Win Rate | Brier Before | Brier After | ECE Before | ECE After |")
    lines.append("|------|------------|:-------------:|:-----------:|:--------:|:------------:|:-----------:|:----------:|:---------:|")

    for r in fold_results:
        if r.skipped:
            continue

        def _fv(v, fmt=".4f"):
            return f"{v:{fmt}}" if v is not None and not (isinstance(v, float) and math.isnan(v)) else "—"

        lines.append(
            f"| {r.fold_spec.fold_id} "
            f"| {r.fold_spec.test_start}→{r.fold_spec.test_end} "
            f"| {r.n_train_samples} "
            f"| {r.n_test_cycles} "
            f"| {_fv(r.win_rate_test, '.1%')} "
            f"| {_fv(r.brier_before)} "
            f"| {_fv(r.brier_after)} "
            f"| {_fv(r.ece_before)} "
            f"| {_fv(r.ece_after)} |"
        )
    lines.append("")

    # ── Delta table ───────────────────────────────────────────────────────
    lines.append("## Delta Metrics (Calibrated − Baseline, Test Periods Only)")
    lines.append("")
    lines.append("Positive DD delta = less drawdown (improvement). Negative slippage delta = lower cost (improvement).")
    lines.append("")
    lines.append("| Fold | ΔCAGR | ΔMax DD | ΔSharpe | ΔCalmar | ΔSlippage | Improved? |")
    lines.append("|------|------:|--------:|--------:|--------:|----------:|:---------:|")

    for r in fold_results:
        if r.skipped:
            continue
        flags = []
        if r.cal_improved_sharpe:
            flags.append("Sharpe")
        if r.cal_improved_calmar:
            flags.append("Calmar")
        if r.cal_improved_dd:
            flags.append("DD")
        if r.cal_improved_slippage:
            flags.append("Slip")
        flag_str = ", ".join(flags) if flags else "none"

        def _d(k, fmt=".2f"):
            v = r.delta.get(k)
            return f"{v:{fmt}}" if v is not None else "—"

        slip = r.delta.get("delta_total_slippage_cost")
        slip_str = f"${slip:,.0f}" if slip is not None else "—"

        lines.append(
            f"| {r.fold_spec.fold_id} "
            f"| {_d('delta_cagr_pct')}pp "
            f"| {_d('delta_max_drawdown_pct')}pp "
            f"| {_d('delta_sharpe', '.3f')} "
            f"| {_d('delta_calmar', '.3f')} "
            f"| {slip_str} "
            f"| {flag_str} |"
        )
    lines.append("")

    # ── Aggregate summary ─────────────────────────────────────────────────
    lines.append("## Aggregate Summary")
    lines.append("")
    n_active = agg.get("n_folds_active", 0)
    lines.append(f"- Active folds: **{n_active}** / {agg.get('n_folds_total', 0)}")
    lines.append(f"- Folds where calibration improved Sharpe: **{agg.get('improved_sharpe', 0)} / {n_active}**")
    lines.append(f"- Folds where calibration improved Calmar: **{agg.get('improved_calmar', 0)} / {n_active}**")
    lines.append(f"- Folds where calibration reduced Max DD:  **{agg.get('improved_dd', 0)} / {n_active}**")
    lines.append(f"- Folds where calibration reduced Slippage: **{agg.get('improved_slippage', 0)} / {n_active}**")
    lines.append("")

    dm = agg.get("delta_means", {})
    lines.append("**Mean deltas across folds (calibrated − baseline):**")
    lines.append("")

    def _am(k, fmt=".2f", suffix=""):
        v = dm.get(k)
        return f"{v:{fmt}}{suffix}" if v is not None else "—"

    lines.append(f"| Metric | Mean Δ | Median Δ |")
    lines.append(f"|--------|-------:|---------:|")
    dmed = agg.get("delta_medians", {})

    def row(label, key, fmt=".2f", suffix=""):
        mv = dm.get(key)
        mdv = dmed.get(key)
        ms = f"{mv:{fmt}}{suffix}" if mv is not None else "—"
        mds = f"{mdv:{fmt}}{suffix}" if mdv is not None else "—"
        return f"| {label} | {ms} | {mds} |"

    lines.append(row("ΔCAGR (pp)", "delta_cagr_pct"))
    lines.append(row("ΔMax DD (pp)", "delta_max_drawdown_pct"))
    lines.append(row("ΔSharpe", "delta_sharpe", ".3f"))
    lines.append(row("ΔCalmar", "delta_calmar", ".3f"))
    lines.append(row("ΔSlippage ($)", "delta_total_slippage_cost", ",.0f"))
    lines.append(row("ΔTurnover NAV", "delta_turnover_x_nav_adj", ".1f", "x"))
    lines.append("")

    best_id = agg.get("best_fold_id")
    worst_id = agg.get("worst_fold_id")
    bdc = agg.get("best_fold_delta_calmar")
    wdc = agg.get("worst_fold_delta_calmar")
    bdc_str = f"{bdc:.3f}" if bdc is not None else "—"
    wdc_str = f"{wdc:.3f}" if wdc is not None else "—"
    lines.append(f"- Best fold by ΔCalmar: **Fold {best_id}** (Δ={bdc_str})")
    lines.append(f"- Worst fold by ΔCalmar: **Fold {worst_id}** (Δ={wdc_str})")
    lines.append("")

    conclusion = agg.get("conclusion", "unknown")
    emoji = {"likely robust": "✅", "mixed / regime-dependent": "⚠️", "likely overfit": "❌"}.get(conclusion, "❓")
    lines.append(f"## Conclusion")
    lines.append("")
    lines.append(f"**{emoji} {conclusion.upper()}**")
    lines.append("")
    if conclusion == "likely robust":
        lines.append(
            "Calibration consistently improved risk-adjusted performance across "
            "multiple out-of-sample folds. The effect generalises across time periods "
            "and is worth keeping in the production pipeline."
        )
    elif conclusion == "mixed / regime-dependent":
        lines.append(
            "Calibration improved performance in some folds but not others. "
            "The effect may be regime-dependent (e.g. works in trending markets "
            "but not ranging ones). Proceed with caution — monitor live performance "
            "closely before relying on calibration for position sizing."
        )
    else:
        lines.append(
            "Calibration failed to consistently improve out-of-sample performance. "
            "The training-period improvement is likely an artefact of the small "
            "sample size. Do not rely on this calibrator for live deployment without "
            "substantially more trade history."
        )

    return "\n".join(lines)


# ── Chart generation ──────────────────────────────────────────────────────────

def _plot_performance(fold_results: list[FoldResult], out_path: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    active = [r for r in fold_results if not r.skipped]
    if not active:
        return

    fold_ids = [r.fold_spec.fold_id for r in active]
    labels = [f"F{r.fold_spec.fold_id}\n{r.fold_spec.test_start[:4]}" for r in active]
    x = range(len(active))
    width = 0.35

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("Walk-Forward: Baseline vs Calibrated (Test Periods)", fontsize=13)

    metrics = [
        ("cagr_pct", "CAGR (%)", axes[0, 0]),
        ("max_drawdown_pct", "Max DD (%)", axes[0, 1]),
        ("sharpe", "Sharpe", axes[1, 0]),
        ("calmar", "Calmar", axes[1, 1]),
    ]

    for key, ylabel, ax in metrics:
        base_vals = [r.baseline.get(key) or 0 for r in active]
        cal_vals = [r.calibrated.get(key) or 0 for r in active]
        bars1 = ax.bar([i - width / 2 for i in x], base_vals, width, label="Baseline", color="#4C72B0")
        bars2 = ax.bar([i + width / 2 for i in x], cal_vals, width, label="Calibrated", color="#DD8452")
        ax.set_ylabel(ylabel)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.legend(fontsize=8)
        ax.axhline(0, color="black", linewidth=0.5)
        ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close()


def _plot_calibration(fold_results: list[FoldResult], out_path: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    active = [r for r in fold_results if not r.skipped and r.brier_before is not None]
    if not active:
        return

    labels = [f"F{r.fold_spec.fold_id}\n{r.fold_spec.test_start[:4]}" for r in active]
    x = range(len(active))
    width = 0.35

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    fig.suptitle("Walk-Forward: Calibration Quality (Out-of-Sample)", fontsize=13)

    for ax, before_attr, after_attr, title in [
        (ax1, "brier_before", "brier_after", "Brier Score (lower = better)"),
        (ax2, "ece_before", "ece_after", "ECE (lower = better)"),
    ]:
        before = [getattr(r, before_attr) or 0 for r in active]
        after = [getattr(r, after_attr) or 0 for r in active]
        ax.bar([i - width / 2 for i in x], before, width, label="Before cal.", color="#4C72B0")
        ax.bar([i + width / 2 for i in x], after, width, label="After cal.", color="#DD8452")
        ax.set_title(title)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close()


# ── Save all artifacts ────────────────────────────────────────────────────────

def save_report(
    fold_results: list[FoldResult],
    strategy_id: str,
    out_dir: Path | str,
    run_id: str | None = None,
) -> Path:
    """Write all report artifacts to disk and return the output directory path."""
    run_id = run_id or time.strftime("%Y%m%d_%H%M%S")
    out = Path(out_dir) / strategy_id / run_id
    out.mkdir(parents=True, exist_ok=True)

    agg = aggregate(fold_results)

    # fold_results.json
    payload = to_json(fold_results, agg)
    with open(out / "fold_results.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    # fold_results.csv
    df = to_dataframe(fold_results)
    df.to_csv(out / "fold_results.csv", index=False)

    # summary.json
    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(agg, f, indent=2, default=str)

    # summary.md
    md = to_markdown(fold_results, agg)
    with open(out / "summary.md", "w", encoding="utf-8") as f:
        f.write(md)

    # Charts
    _plot_performance(fold_results, out / "chart_performance.png")
    _plot_calibration(fold_results, out / "chart_calibration.png")

    return out
