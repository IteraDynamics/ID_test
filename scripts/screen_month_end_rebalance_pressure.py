"""Sandbox alpha screen: month-end equity/bond rebalancing pressure.

Research-only and observation-only. This script does not modify Core v1, runtime,
portfolio, orders, NAV, exposure, or production state.

Frozen design is documented in:
  docs/research/EXPLORATION_MONTH_END_REBALANCE_PRESSURE_SCREEN.md

Primary thesis:
  pre-window SPY-minus-AGG monthly relative performance should negatively predict
  SPY-minus-AGG relative performance over the final 3 shared trading sessions.

Primary gate (frozen before outcome inspection):
- Spearman rho < 0 with one-sided within-5-year-block permutation p <= 0.05;
- causal expanding-tercile low-minus-high outcome spread > 0 with one-sided
  permutation p <= 0.05;
- leave-one-calendar-year-out Spearman rho remains < 0 for every eligible year.

Final 1-session and 5-session windows are descriptive only and cannot rescue a
failed 3-session primary gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


WINDOWS = (1, 3, 5)
PRIMARY_WINDOW = 3
MIN_PRIOR_MONTHS = 36
MIN_VALID_MONTHS = 120
N_PERMUTATIONS = 1000
SEED = 20260902


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spy-csv", default="artifacts/month_end_rebalance_data/SPY_1D.csv")
    p.add_argument("--agg-csv", default="artifacts/month_end_rebalance_data/AGG_1D.csv")
    p.add_argument("--output-dir", default="artifacts/month_end_rebalance_pressure_screen")
    p.add_argument("--permutations", type=int, default=N_PERMUTATIONS)
    p.add_argument("--seed", type=int, default=SEED)
    return p.parse_args()


def load_price(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{name}_SOURCE_MISSING:{path}")
    frame = pd.read_csv(path)
    required = {"timestamp", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{name}_SOURCE_MISSING_COLUMNS:{sorted(missing)}")
    out = frame[["timestamp", "close"]].copy()
    out["date"] = (
        pd.to_datetime(out["timestamp"], errors="coerce", utc=True)
        .dt.tz_convert(None)
        .dt.normalize()
    )
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["date", "close"])
    out = out[out["close"] > 0]
    out = out.sort_values("date").drop_duplicates("date", keep="last")
    return out[["date", "close"]].rename(columns={"close": name.lower()})


def build_month_panel(spy: pd.DataFrame, agg: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    data = spy.merge(agg, on="date", how="inner").sort_values("date").reset_index(drop=True)
    if data.empty:
        raise ValueError("NO_SHARED_SPY_AGG_SESSIONS")
    data["month"] = data["date"].dt.to_period("M")
    groups = {period: group.reset_index(drop=True) for period, group in data.groupby("month", sort=True)}
    periods = sorted(groups)

    rows: list[dict[str, object]] = []
    skipped_no_prior = 0
    skipped_thin_month = 0

    for period in periods:
        prior = period - 1
        if prior not in groups:
            skipped_no_prior += 1
            continue
        current = groups[period]
        prior_group = groups[prior]
        if len(current) < max(WINDOWS) + 1:
            skipped_thin_month += 1
            continue

        anchor = prior_group.iloc[-1]
        record: dict[str, object] = {
            "month": str(period),
            "year": int(period.year),
            "month_number": int(period.month),
            "quarter_end": bool(period.month in {3, 6, 9, 12}),
            "anchor_date": pd.Timestamp(anchor["date"]),
            "month_end_date": pd.Timestamp(current.iloc[-1]["date"]),
        }

        valid = True
        for window in WINDOWS:
            cutoff_pos = len(current) - window - 1
            if cutoff_pos < 0:
                valid = False
                break
            cutoff = current.iloc[cutoff_pos]
            end = current.iloc[-1]

            spy_signal = float(cutoff["spy"] / anchor["spy"] - 1.0)
            agg_signal = float(cutoff["agg"] / anchor["agg"] - 1.0)
            spy_outcome = float(end["spy"] / cutoff["spy"] - 1.0)
            agg_outcome = float(end["agg"] / cutoff["agg"] - 1.0)

            record[f"cutoff_date_{window}d"] = pd.Timestamp(cutoff["date"])
            record[f"signal_{window}d"] = spy_signal - agg_signal
            record[f"outcome_{window}d"] = spy_outcome - agg_outcome

        if valid:
            rows.append(record)

    panel = pd.DataFrame(rows).sort_values("month").reset_index(drop=True)
    diagnostics = {
        "shared_sessions": int(len(data)),
        "calendar_months_seen": int(len(periods)),
        "valid_months": int(len(panel)),
        "skipped_no_prior_month": int(skipped_no_prior),
        "skipped_thin_month": int(skipped_thin_month),
    }
    return panel, diagnostics


def causal_tercile(series: pd.Series, min_prior: int = MIN_PRIOR_MONTHS) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    labels = np.full(len(values), "", dtype=object)
    for i, value in enumerate(values):
        prior = values[:i]
        prior = prior[np.isfinite(prior)]
        if len(prior) < min_prior or not np.isfinite(value):
            continue
        q1, q2 = np.quantile(prior, [1 / 3, 2 / 3])
        labels[i] = "low" if value <= q1 else ("high" if value >= q2 else "mid")
    return pd.Series(labels, index=series.index, dtype="object")


def spearman_rho(signal: pd.Series, outcome: pd.Series) -> float:
    data = pd.DataFrame({"signal": signal, "outcome": outcome}).dropna()
    if len(data) < 3:
        return np.nan
    result = stats.spearmanr(data["signal"], data["outcome"])
    return float(result.statistic)


def tercile_spread(signal: pd.Series, outcome: pd.Series) -> tuple[float, int, int, pd.Series]:
    labels = causal_tercile(signal)
    low = pd.to_numeric(outcome[labels == "low"], errors="coerce").dropna()
    high = pd.to_numeric(outcome[labels == "high"], errors="coerce").dropna()
    if low.empty or high.empty:
        return np.nan, int(len(low)), int(len(high)), labels
    return float(low.mean() - high.mean()), int(len(low)), int(len(high)), labels


def five_year_block(years: pd.Series) -> np.ndarray:
    y = pd.to_numeric(years, errors="coerce").to_numpy(dtype=int)
    return (y // 5) * 5


def permute_within_blocks(values: np.ndarray, blocks: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    shuffled = values.copy()
    for block in np.unique(blocks):
        idx = np.flatnonzero(blocks == block)
        shuffled[idx] = rng.permutation(shuffled[idx])
    return shuffled


def permutation_tests(
    panel: pd.DataFrame,
    signal_col: str,
    outcome_col: str,
    observed_rho: float,
    observed_spread: float,
    n_perm: int,
    seed: int,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    signal = pd.to_numeric(panel[signal_col], errors="coerce").to_numpy(dtype=float)
    outcome = pd.to_numeric(panel[outcome_col], errors="coerce")
    blocks = five_year_block(panel["year"])

    null_rho = np.empty(n_perm, dtype=float)
    null_spread = np.empty(n_perm, dtype=float)

    for i in range(n_perm):
        shuffled = permute_within_blocks(signal, blocks, rng)
        shuffled_series = pd.Series(shuffled, index=panel.index)
        null_rho[i] = spearman_rho(shuffled_series, outcome)
        spread, _, _, _ = tercile_spread(shuffled_series, outcome)
        null_spread[i] = spread

    valid_rho = null_rho[np.isfinite(null_rho)]
    valid_spread = null_spread[np.isfinite(null_spread)]
    p_rho = np.nan if not np.isfinite(observed_rho) or len(valid_rho) == 0 else float(
        (1 + np.sum(valid_rho <= observed_rho)) / (len(valid_rho) + 1)
    )
    p_spread = np.nan if not np.isfinite(observed_spread) or len(valid_spread) == 0 else float(
        (1 + np.sum(valid_spread >= observed_spread)) / (len(valid_spread) + 1)
    )
    return p_rho, p_spread


def leave_one_year_out(panel: pd.DataFrame, signal_col: str, outcome_col: str) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for year in sorted(panel["year"].unique()):
        if int((panel["year"] == year).sum()) < 6:
            continue
        subset = panel[panel["year"] != year]
        rho = spearman_rho(subset[signal_col], subset[outcome_col])
        out[str(int(year))] = None if not np.isfinite(rho) else float(rho)
    return out


def grouped_summary(panel: pd.DataFrame, group_col: str, signal_col: str, outcome_col: str) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, group in panel.groupby(group_col, sort=True):
        rho = spearman_rho(group[signal_col], group[outcome_col])
        out[str(key)] = {
            "n": int(len(group)),
            "spearman_rho": None if not np.isfinite(rho) else float(rho),
            "mean_signal": float(group[signal_col].mean()),
            "mean_outcome": float(group[outcome_col].mean()),
        }
    return out


def window_summary(panel: pd.DataFrame, window: int, n_perm: int, seed: int) -> dict[str, object]:
    signal_col = f"signal_{window}d"
    outcome_col = f"outcome_{window}d"
    rho = spearman_rho(panel[signal_col], panel[outcome_col])
    spread, n_low, n_high, labels = tercile_spread(panel[signal_col], panel[outcome_col])
    rho_p, spread_p = permutation_tests(
        panel,
        signal_col,
        outcome_col,
        rho,
        spread,
        n_perm=n_perm,
        seed=seed + window,
    )
    tmp = panel.copy()
    tmp["state"] = labels
    return {
        "window_sessions": window,
        "spearman_rho": None if not np.isfinite(rho) else float(rho),
        "spearman_permutation_p_one_sided": None if not np.isfinite(rho_p) else float(rho_p),
        "low_minus_high_outcome": None if not np.isfinite(spread) else float(spread),
        "tercile_permutation_p_one_sided": None if not np.isfinite(spread_p) else float(spread_p),
        "n_low": n_low,
        "n_high": n_high,
        "quarter_end": {
            "n": int(tmp["quarter_end"].sum()),
            "spearman_rho": None if not np.isfinite(spearman_rho(tmp.loc[tmp["quarter_end"], signal_col], tmp.loc[tmp["quarter_end"], outcome_col])) else float(spearman_rho(tmp.loc[tmp["quarter_end"], signal_col], tmp.loc[tmp["quarter_end"], outcome_col])),
        },
        "non_quarter_end": {
            "n": int((~tmp["quarter_end"]).sum()),
            "spearman_rho": None if not np.isfinite(spearman_rho(tmp.loc[~tmp["quarter_end"], signal_col], tmp.loc[~tmp["quarter_end"], outcome_col])) else float(spearman_rho(tmp.loc[~tmp["quarter_end"], signal_col], tmp.loc[~tmp["quarter_end"], outcome_col])),
        },
    }


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        spy = load_price(Path(args.spy_csv), "SPY")
        agg = load_price(Path(args.agg_csv), "AGG")
        panel, diagnostics = build_month_panel(spy, agg)
    except Exception as exc:
        report = {
            "classification": "SCREEN_INCONCLUSIVE",
            "reason": "SOURCE_OR_PANEL_FAILURE",
            "error": f"{type(exc).__name__}: {exc}",
            "boundary": "Sandbox only; no runtime/portfolio implication.",
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        (output_dir / "month_end_rebalance_pressure_screen.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return 2

    if len(panel) < MIN_VALID_MONTHS:
        classification = "SCREEN_INCONCLUSIVE"
        reason = "INSUFFICIENT_VALID_MONTHS"
        primary = None
        windows: list[dict[str, object]] = []
        loo: dict[str, float | None] = {}
    else:
        windows = [window_summary(panel, w, args.permutations, args.seed) for w in WINDOWS]
        primary = next(item for item in windows if item["window_sessions"] == PRIMARY_WINDOW)
        loo = leave_one_year_out(panel, "signal_3d", "outcome_3d")
        loo_values = [v for v in loo.values() if v is not None]
        loo_all_negative = bool(loo_values) and all(v < 0 for v in loo_values)

        rho = primary["spearman_rho"]
        rho_p = primary["spearman_permutation_p_one_sided"]
        spread = primary["low_minus_high_outcome"]
        spread_p = primary["tercile_permutation_p_one_sided"]

        passed = (
            rho is not None
            and rho < 0
            and rho_p is not None
            and rho_p <= 0.05
            and spread is not None
            and spread > 0
            and spread_p is not None
            and spread_p <= 0.05
            and loo_all_negative
        )
        classification = "SCREEN_POSITIVE" if passed else "SCREEN_NEGATIVE"
        reason = "FROZEN_SANDBOX_GATE_PASSED" if passed else "FROZEN_SANDBOX_GATE_FAILED"

    panel = panel.copy()
    panel["decade"] = (panel["year"] // 10) * 10
    top_extremes = (
        panel.assign(abs_signal_3d=panel["signal_3d"].abs())
        .sort_values("abs_signal_3d", ascending=False)
        .head(10)[["month", "signal_3d", "outcome_3d", "quarter_end"]]
        .to_dict(orient="records")
    )

    report = {
        "classification": classification,
        "reason": reason,
        "design": {
            "primary_window_sessions": PRIMARY_WINDOW,
            "descriptive_windows_sessions": [1, 5],
            "minimum_prior_months_for_causal_terciles": MIN_PRIOR_MONTHS,
            "minimum_valid_months": MIN_VALID_MONTHS,
            "permutations": args.permutations,
            "seed": args.seed,
            "permutation_blocks": "5-year calendar blocks",
            "positive_gate": "3d rho<0 p<=0.05 AND 3d causal low-high spread>0 p<=0.05 AND every eligible leave-one-year-out rho<0",
        },
        "source": {
            "spy_csv": str(args.spy_csv),
            "agg_csv": str(args.agg_csv),
            "spy_rows": int(len(spy)),
            "agg_rows": int(len(agg)),
            "spy_date_min": spy["date"].min().date().isoformat(),
            "spy_date_max": spy["date"].max().date().isoformat(),
            "agg_date_min": agg["date"].min().date().isoformat(),
            "agg_date_max": agg["date"].max().date().isoformat(),
            "adjusted_data_required": True,
        },
        "panel": diagnostics | {
            "date_min": None if panel.empty else str(panel["month"].min()),
            "date_max": None if panel.empty else str(panel["month"].max()),
        },
        "primary": primary,
        "windows": windows,
        "leave_one_year_out_primary_spearman": loo,
        "yearly_primary": grouped_summary(panel, "year", "signal_3d", "outcome_3d") if not panel.empty else {},
        "decade_primary": grouped_summary(panel, "decade", "signal_3d", "outcome_3d") if not panel.empty else {},
        "top_10_absolute_primary_signals": top_extremes,
        "boundary": "Sandbox screen only. SCREEN_POSITIVE earns governed research; it does not authorize any Core v1/Core v2/runtime/portfolio/paper/live action.",
    }

    report_path = output_dir / "month_end_rebalance_pressure_screen.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    panel.to_csv(output_dir / "month_end_rebalance_pressure_panel.csv", index=False, lineterminator="\n")
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
