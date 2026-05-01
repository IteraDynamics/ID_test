#!/usr/bin/env python
"""Shadow-test HMM crypto composite defensive governor schedules.

Research-only hypothesis test. This script joins crypto composite HMM regimes to
an existing equity curve artifact and evaluates fixed, deterministic exposure
scale schedules against the crypto sleeve forward-return stream.

Important:
- Does NOT modify Fund v1 runtime behavior.
- Does NOT create a production governor.
- Does NOT route orders or change strategy intent.

The purpose is to answer whether composite-regime attribution is strong enough
to justify a deeper governor research pass.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEFAULT_COMPOSITE_PATH = Path(
    "artifacts/hmm_regime_v1_crypto_composite/crypto_composite_regimes.csv"
)
DEFAULT_OUT_DIR = Path("artifacts/hmm_regime_v1_crypto_composite_governor")
REGIME_COLUMN = "composite_regime"
DEFAULT_TARGET_SERIES = "portfolio"


@dataclass(frozen=True)
class ScheduleConfig:
    name: str
    default_scale: float
    regime_scales: dict[str, float]
    description: str


SCHEDULES = [
    ScheduleConfig(
        name="baseline_no_governor",
        default_scale=1.00,
        regime_scales={},
        description="No scaling; reproduces the base target return stream.",
    ),
    ScheduleConfig(
        name="risk_off_only_light",
        default_scale=1.00,
        regime_scales={"STRUCTURAL_RISK_OFF": 0.75},
        description="Simple first-pass risk-off-only reduction.",
    ),
    ScheduleConfig(
        name="risk_off_only_moderate",
        default_scale=1.00,
        regime_scales={"STRUCTURAL_RISK_OFF": 0.50},
        description="Moderate first-pass risk-off-only reduction.",
    ),
    ScheduleConfig(
        name="risk_off_and_mixed_light",
        default_scale=1.00,
        regime_scales={
            "STRUCTURAL_RISK_OFF": 0.75,
            "MIXED": 0.85,
        },
        description="Light reduction in structural risk-off and fully mixed regimes only.",
    ),
]


def _read_time_indexed_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[~df.index.isna()].sort_index()
    if df.empty:
        raise ValueError(f"No valid timestamp rows in artifact: {path}")
    return df


def _median_interval_seconds(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return 0.0
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return 0.0
    return float(deltas.median())


def _frequency_label(seconds: float) -> str:
    if seconds <= 0:
        return "unknown"
    if abs(seconds - 3600.0) < 1:
        return "1H"
    if abs(seconds - 4 * 3600.0) < 1:
        return "4H"
    if abs(seconds - 86400.0) < 1:
        return "1D"
    return f"{seconds:.0f}s"


def _validate_frequency_compatibility(
    composite: pd.DataFrame,
    equity: pd.DataFrame,
    allow_mixed_frequency: bool,
) -> dict[str, float | str]:
    composite_seconds = _median_interval_seconds(composite.index)
    equity_seconds = _median_interval_seconds(equity.index)
    diagnostics = {
        "composite_median_interval_seconds": composite_seconds,
        "equity_median_interval_seconds": equity_seconds,
        "composite_frequency": _frequency_label(composite_seconds),
        "equity_frequency": _frequency_label(equity_seconds),
    }
    if composite_seconds <= 0 or equity_seconds <= 0:
        raise ValueError(f"Could not infer input frequencies: {diagnostics}")
    ratio = max(composite_seconds, equity_seconds) / min(composite_seconds, equity_seconds)
    diagnostics["frequency_ratio"] = ratio
    if ratio > 1.5 and not allow_mixed_frequency:
        raise ValueError(
            "Refusing mixed-frequency governor join. "
            f"Diagnostics: {diagnostics}. "
            "Pass --allow-mixed-frequency only after explicitly confirming this is intended."
        )
    return diagnostics


def _infer_bars_per_year(index: pd.DatetimeIndex) -> float:
    seconds = _median_interval_seconds(index)
    if seconds <= 0:
        return 365.25 * 24.0
    return float((365.25 * 24.0 * 3600.0) / seconds)


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return float(dd.min())


def _metrics_from_returns(returns: pd.Series, bars_per_year: float) -> dict[str, float | int]:
    returns = returns.dropna().astype(float)
    n = int(len(returns))
    if n == 0:
        return {
            "bars": 0,
            "total_return": 0.0,
            "cagr": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "calmar": 0.0,
            "ann_vol": 0.0,
            "avg_bar_return": 0.0,
            "avg_bar_return_bps": 0.0,
            "hit_rate": 0.0,
        }

    equity = (1.0 + returns).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    years = n / bars_per_year if bars_per_year > 0 else 0.0
    cagr = float((1.0 + total_return) ** (1.0 / years) - 1.0) if years > 0 and total_return > -1.0 else -1.0
    ann_vol = float(returns.std(ddof=0) * math.sqrt(bars_per_year)) if n > 1 else 0.0
    sharpe = float((returns.mean() / returns.std(ddof=0)) * math.sqrt(bars_per_year)) if returns.std(ddof=0) > 0 else 0.0
    max_dd = _max_drawdown(equity)
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0

    return {
        "bars": n,
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "calmar": calmar,
        "ann_vol": ann_vol,
        "avg_bar_return": float(returns.mean()),
        "avg_bar_return_bps": float(returns.mean() * 10_000.0),
        "hit_rate": float((returns > 0).mean()),
    }


def _join_regimes_to_returns(
    composite: pd.DataFrame,
    equity: pd.DataFrame,
    target_series: str,
) -> pd.DataFrame:
    if REGIME_COLUMN not in composite.columns:
        raise ValueError(f"Composite artifact missing required column: {REGIME_COLUMN}")
    if target_series not in equity.columns:
        available = ", ".join(str(col) for col in equity.columns)
        raise ValueError(f"Target series '{target_series}' not found. Available columns: [{available}]")

    equity[target_series] = pd.to_numeric(equity[target_series], errors="coerce")
    equity = equity.dropna(subset=[target_series])

    start = max(composite.index.min(), equity.index.min())
    end = min(composite.index.max(), equity.index.max())
    if pd.isna(start) or pd.isna(end) or start >= end:
        raise ValueError(f"No overlapping period: start={start}, end={end}")

    composite_slice = composite.loc[start:end].copy()
    equity_slice = equity.loc[start:end, [target_series]].copy()
    forward_return_col = f"fwd_ret_{target_series}"
    equity_slice[forward_return_col] = equity_slice[target_series].pct_change().shift(-1)

    joined = composite_slice.join(equity_slice[[forward_return_col]], how="inner").sort_index()
    joined = joined.dropna(subset=[REGIME_COLUMN, forward_return_col])
    return joined


def _apply_schedule(
    joined: pd.DataFrame,
    target_series: str,
    schedule: ScheduleConfig,
    transition_cost_bps_per_unit: float,
) -> pd.DataFrame:
    ret_col = f"fwd_ret_{target_series}"
    out = joined[[REGIME_COLUMN, ret_col]].copy()
    out["schedule"] = schedule.name
    out["scale"] = out[REGIME_COLUMN].map(schedule.regime_scales).fillna(schedule.default_scale).astype(float)
    out["base_return"] = out[ret_col]
    out["gross_governed_return"] = out[ret_col] * out["scale"]
    out["scale_delta"] = out["scale"].diff().abs().fillna(0.0)
    out["transition_cost_return"] = out["scale_delta"] * (transition_cost_bps_per_unit / 10_000.0)
    out["governed_return"] = out["gross_governed_return"] - out["transition_cost_return"]
    out["return_delta"] = out["governed_return"] - out["base_return"]
    out["scale_change"] = out["scale_delta"] > 1e-12
    return out


def _build_schedule_summary(
    scheduled_frames: list[pd.DataFrame],
    bars_per_year: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    baseline_metrics: dict[str, float | int] | None = None

    for frame in scheduled_frames:
        schedule = str(frame["schedule"].iloc[0])
        metrics = _metrics_from_returns(frame["governed_return"], bars_per_year)
        if schedule == "baseline_no_governor":
            baseline_metrics = metrics

        rows.append(
            {
                "schedule": schedule,
                **metrics,
                "avg_scale": float(frame["scale"].mean()),
                "min_scale": float(frame["scale"].min()),
                "pct_scaled_bars": float((frame["scale"] < 1.0).mean()),
                "scale_changes": int(frame["scale_change"].sum()),
                "total_scale_turnover": float(frame["scale_delta"].sum()),
                "total_transition_cost_return": float(frame["transition_cost_return"].sum()),
                "avg_transition_cost_bps": float(frame["transition_cost_return"].mean() * 10_000.0),
                "avg_return_delta_bps": float(frame["return_delta"].mean() * 10_000.0),
                "sum_return_delta": float(frame["return_delta"].sum()),
            }
        )

    summary = pd.DataFrame(rows)
    if baseline_metrics is not None:
        for col in ["total_return", "cagr", "max_drawdown", "sharpe", "calmar", "ann_vol", "avg_bar_return_bps"]:
            base = float(baseline_metrics[col])
            summary[f"delta_{col}"] = summary[col] - base
    return summary


def _build_regime_scale_summary(scheduled_frames: list[pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for frame in scheduled_frames:
        schedule = str(frame["schedule"].iloc[0])
        for regime, grp in frame.groupby(REGIME_COLUMN, sort=False):
            rows.append(
                {
                    "schedule": schedule,
                    "composite_regime": regime,
                    "bars": int(len(grp)),
                    "avg_scale": float(grp["scale"].mean()),
                    "base_avg_return_bps": float(grp["base_return"].mean() * 10_000.0),
                    "gross_governed_avg_return_bps": float(grp["gross_governed_return"].mean() * 10_000.0),
                    "net_governed_avg_return_bps": float(grp["governed_return"].mean() * 10_000.0),
                    "transition_cost_return": float(grp["transition_cost_return"].sum()),
                    "sum_return_delta": float(grp["return_delta"].sum()),
                }
            )
    return pd.DataFrame(rows)


def _format_markdown_value(value: object, floatfmt: str = ".6f") -> str:
    if isinstance(value, float):
        return format(value, floatfmt)
    return str(value)


def _to_markdown_table(df: pd.DataFrame, floatfmt: str = ".6f") -> str:
    if df.empty:
        return "_No rows._"
    columns = [str(col) for col in df.columns]
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in df.iterrows():
        values = [_format_markdown_value(row[col], floatfmt=floatfmt) for col in df.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--composite", default=str(DEFAULT_COMPOSITE_PATH))
    parser.add_argument("--equity-curves", required=True)
    parser.add_argument("--target-series", required=True)
    parser.add_argument("--transition-cost-bps", type=float, default=10.0, help="Cost in bps per 1.00 exposure-scale change")
    parser.add_argument("--allow-mixed-frequency", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    composite_path = Path(args.composite)
    equity_curves_path = Path(args.equity_curves)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    composite = _read_time_indexed_csv(composite_path)
    equity = _read_time_indexed_csv(equity_curves_path)
    frequency_diagnostics = _validate_frequency_compatibility(
        composite,
        equity,
        allow_mixed_frequency=args.allow_mixed_frequency,
    )
    joined = _join_regimes_to_returns(composite, equity, args.target_series)
    bars_per_year = _infer_bars_per_year(joined.index)

    scheduled_frames = [
        _apply_schedule(joined, args.target_series, schedule, args.transition_cost_bps)
        for schedule in SCHEDULES
    ]
    schedule_returns = pd.concat(scheduled_frames).sort_index()
    schedule_summary = _build_schedule_summary(scheduled_frames, bars_per_year)
    regime_scale_summary = _build_regime_scale_summary(scheduled_frames)

    schedule_returns.to_csv(out_dir / "governor_schedule_returns.csv")
    schedule_summary.to_csv(out_dir / "governor_schedule_summary.csv", index=False)
    regime_scale_summary.to_csv(out_dir / "governor_regime_scale_summary.csv", index=False)

    payload = {
        "research_status": "shadow_mode_only",
        "inputs": {
            "composite_regimes": str(composite_path),
            "equity_curves": str(equity_curves_path),
            "target_series": args.target_series,
            "transition_cost_bps_per_unit_scale_change": args.transition_cost_bps,
        },
        "alignment": {
            "method": "inner join on matching timestamps; composite regime at time t joined to next-bar target return after t",
            "bars": int(len(joined)),
            "start": str(joined.index.min()),
            "end": str(joined.index.max()),
            "bars_per_year_inferred": float(bars_per_year),
            "frequency_diagnostics": frequency_diagnostics,
            "allow_mixed_frequency": bool(args.allow_mixed_frequency),
        },
        "metric_notes": [
            "Transition costs are modeled as cost_bps * abs(scale_t - scale_t-1).",
            "Scaled return assumes de-risked capital earns zero return for the next bar.",
            "Materially mixed-frequency joins are refused by default.",
            "This is research-only signal evidence, not a production governor.",
        ],
        "schedules": [
            {
                "name": schedule.name,
                "default_scale": schedule.default_scale,
                "regime_scales": schedule.regime_scales,
                "description": schedule.description,
            }
            for schedule in SCHEDULES
        ],
        "artifacts": {
            "governor_schedule_returns": str(out_dir / "governor_schedule_returns.csv"),
            "governor_schedule_summary": str(out_dir / "governor_schedule_summary.csv"),
            "governor_regime_scale_summary": str(out_dir / "governor_regime_scale_summary.csv"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {
            "status": "research_only_shadow_governor_hypothesis",
            "next_step": "review_cost_adjusted_schedule_results_and_select_any_candidate_for_deeper_validation",
            "not_approved": [
                "fund_v1_runtime_change",
                "direct_strategy_gating",
                "allocator_integration",
                "production_layer_1_replacement",
            ],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print("\n=== HMM CRYPTO COMPOSITE GOVERNOR SHADOW TEST ===")
    print(f"Composite: {composite_path}")
    print(f"Equity curves: {equity_curves_path}")
    print(f"Target series: {args.target_series}")
    print(
        "Frequencies: "
        f"composite={frequency_diagnostics['composite_frequency']} "
        f"equity={frequency_diagnostics['equity_frequency']} "
        f"ratio={frequency_diagnostics['frequency_ratio']:.2f}"
    )
    print(f"Transition cost: {args.transition_cost_bps:.4f} bps per 1.00 exposure-scale change")
    with pd.option_context("display.max_columns", None, "display.width", 260, "display.float_format", "{:.6f}".format):
        print("\nSchedule Summary:")
        print(schedule_summary.to_string(index=False))
        print("\nRanking By Calmar / Sharpe:")
        print(
            schedule_summary.sort_values(["calmar", "sharpe", "max_drawdown"], ascending=[False, False, False])
            .to_string(index=False)
        )
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
