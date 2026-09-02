"""Sandbox alpha screen: index-options dealer gamma pressure vs subsequent SPY path behavior.

Research-only and observation-only. This script does not modify Core v1, runtime, portfolio,
orders, NAV, exposure, or production state.

Design frozen before outcome inspection:
- free yearly SPY option-chain mirror, 2008-2025;
- mirror observation date t is shifted one full SPY trading day before it can define a state;
- signed convention: calls +gamma*OI, puts -gamma*OI (explicit model assumption, not observed dealer inventory);
- sign-free geometry: total gamma*OI and strike concentration;
- causal expanding terciles, minimum 126 prior state observations;
- endpoints at 1, 2, 5 trading days:
    continuation = sign(previous SPY daily return) * forward SPY return
    movement = absolute forward SPY return
- negative control: within-year permutation of state labels, fixed seed, 500 repeats.

A SCREEN_POSITIVE requires BOTH:
1. signed-GEX expected-direction separation (low signed GEX > high signed GEX) for continuation
   on at least two of three horizons with one-sided permutation p <= 0.05; and
2. the sign-free low/high total-gamma geometry shows movement separation on at least one horizon
   with permutation p <= 0.05, so the finding is not solely an arbitrary call/put sign convention.

This is a sandbox screen, not confirmation. A positive result only earns governed research.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


HORIZONS = (1, 2, 5)
MIN_PRIOR_STATES = 126
N_PERMUTATIONS = 500
SEED = 20260902
OPTION_COLUMNS = ["date", "expiration", "strike", "type", "open_interest", "gamma"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mirror-dir", default="artifacts/free_options_history_probe")
    p.add_argument("--spy-csv", default="data/SPY_1D.csv")
    p.add_argument("--start-year", type=int, default=2008)
    p.add_argument("--end-year", type=int, default=2025)
    p.add_argument("--output-dir", default="artifacts/dealer_gamma_pressure_screen")
    p.add_argument("--permutations", type=int, default=N_PERMUTATIONS)
    p.add_argument("--seed", type=int, default=SEED)
    return p.parse_args()


def load_spy(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"timestamp", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"SPY_SOURCE_MISSING_COLUMNS:{sorted(missing)}")
    frame = frame[["timestamp", "close"]].copy()
    # UTC conversion safely handles tz-aware and tz-naive strings; only normalized session dates are used.
    frame["date"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date", keep="last")
    frame["ret_1d"] = frame["close"].pct_change()
    return frame.reset_index(drop=True)


def load_gamma_states(mirror_dir: Path, years: range) -> tuple[pd.DataFrame, list[int]]:
    parts: list[pd.DataFrame] = []
    missing_years: list[int] = []
    for year in years:
        path = mirror_dir / f"spy_options_{year}.parquet"
        if not path.exists():
            missing_years.append(year)
            continue
        frame = pd.read_parquet(path, columns=OPTION_COLUMNS)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
        frame["expiration"] = pd.to_datetime(frame["expiration"], errors="coerce").dt.normalize()
        frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
        frame["open_interest"] = pd.to_numeric(frame["open_interest"], errors="coerce")
        frame["gamma"] = pd.to_numeric(frame["gamma"], errors="coerce")
        frame["type"] = frame["type"].astype(str).str.lower().str.strip().replace({"c": "call", "p": "put"})
        frame = frame.dropna(subset=["date", "expiration", "strike", "open_interest", "gamma"])
        frame = frame[(frame["expiration"] >= frame["date"]) & (frame["open_interest"] > 0) & (frame["gamma"] >= 0)]
        frame = frame[frame["type"].isin({"call", "put"})]
        if frame.empty:
            continue

        frame["gamma_oi"] = frame["gamma"] * frame["open_interest"]
        frame["signed_gamma_oi"] = np.where(frame["type"].eq("call"), frame["gamma_oi"], -frame["gamma_oi"])
        daily = frame.groupby("date", as_index=False).agg(
            signed_gex=("signed_gamma_oi", "sum"),
            total_gamma=("gamma_oi", "sum"),
        )
        strike = frame.groupby(["date", "strike"], as_index=False)["gamma_oi"].sum()
        peak = strike.groupby("date", as_index=False)["gamma_oi"].max().rename(columns={"gamma_oi": "peak_strike_gamma"})
        daily = daily.merge(peak, on="date", how="left")
        daily["gamma_concentration"] = np.where(
            daily["total_gamma"] > 0,
            daily["peak_strike_gamma"] / daily["total_gamma"],
            np.nan,
        )
        parts.append(daily)

    if not parts:
        raise ValueError("NO_MIRROR_DATA_LOADED")
    out = pd.concat(parts, ignore_index=True).sort_values("date").drop_duplicates("date", keep="last")
    return out.reset_index(drop=True), missing_years


def causal_tercile(series: pd.Series, min_prior: int = MIN_PRIOR_STATES) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    labels = np.full(len(values), "", dtype=object)
    for i in range(len(values)):
        prior = values[:i]
        prior = prior[np.isfinite(prior)]
        if len(prior) < min_prior or not np.isfinite(values[i]):
            continue
        q1, q2 = np.quantile(prior, [1 / 3, 2 / 3])
        labels[i] = "low" if values[i] <= q1 else ("high" if values[i] >= q2 else "mid")
    return pd.Series(labels, index=series.index, dtype="object")


def attach_outcomes(states: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    # A mirror observation on t is usable only on the next SPY trading date.
    sessions = spy["date"].tolist()
    next_map = {sessions[i]: sessions[i + 1] for i in range(len(sessions) - 1)}
    data = states.copy()
    data["usable_date"] = data["date"].map(next_map)
    data = data.dropna(subset=["usable_date"])

    spy_idx = spy.set_index("date")
    data["impulse_return"] = data["date"].map(spy_idx["ret_1d"])
    usable_positions = {d: i for i, d in enumerate(sessions)}

    for h in HORIZONS:
        vals: list[float] = []
        for usable_date in data["usable_date"]:
            i = usable_positions.get(usable_date)
            if i is None or i + h >= len(spy):
                vals.append(np.nan)
                continue
            start = float(spy.iloc[i - 1]["close"]) if i > 0 else np.nan
            end = float(spy.iloc[i + h - 1]["close"])
            vals.append(end / start - 1.0 if np.isfinite(start) and start > 0 else np.nan)
        data[f"fwd_ret_{h}d"] = vals
        data[f"continuation_{h}d"] = np.sign(data["impulse_return"]) * data[f"fwd_ret_{h}d"]
        data[f"movement_{h}d"] = data[f"fwd_ret_{h}d"].abs()
    return data


def observed_difference(frame: pd.DataFrame, label_col: str, metric: str, expected: str) -> tuple[float, int, int]:
    low = frame.loc[frame[label_col] == "low", metric].dropna()
    high = frame.loc[frame[label_col] == "high", metric].dropna()
    if low.empty or high.empty:
        return np.nan, len(low), len(high)
    if expected == "low_gt_high":
        diff = float(low.mean() - high.mean())
    elif expected == "high_gt_low":
        diff = float(high.mean() - low.mean())
    else:
        raise ValueError(expected)
    return diff, len(low), len(high)


def permutation_pvalue(
    frame: pd.DataFrame,
    label_col: str,
    metric: str,
    expected: str,
    observed: float,
    n_perm: int,
    rng: np.random.Generator,
) -> float:
    if not np.isfinite(observed):
        return np.nan
    data = frame[["usable_date", label_col, metric]].dropna().copy()
    data = data[data[label_col].isin({"low", "high"})]
    if data.empty:
        return np.nan
    labels = data[label_col].to_numpy(copy=True)
    years = pd.to_datetime(data["usable_date"]).dt.year.to_numpy()
    metric_values = data[metric].to_numpy(dtype=float)
    null = np.empty(n_perm, dtype=float)
    for b in range(n_perm):
        shuffled = labels.copy()
        for year in np.unique(years):
            idx = np.flatnonzero(years == year)
            shuffled[idx] = rng.permutation(shuffled[idx])
        low = metric_values[shuffled == "low"]
        high = metric_values[shuffled == "high"]
        if expected == "low_gt_high":
            null[b] = low.mean() - high.mean()
        else:
            null[b] = high.mean() - low.mean()
    return float((1 + np.sum(null >= observed)) / (n_perm + 1))


def yearly_differences(frame: pd.DataFrame, label_col: str, metric: str, expected: str) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    tmp = frame.copy()
    tmp["year"] = pd.to_datetime(tmp["usable_date"]).dt.year
    for year, group in tmp.groupby("year"):
        diff, n_low, n_high = observed_difference(group, label_col, metric, expected)
        out[str(int(year))] = None if not np.isfinite(diff) or min(n_low, n_high) < 5 else float(diff)
    return out


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spy = load_spy(Path(args.spy_csv))
    states, missing_years = load_gamma_states(Path(args.mirror_dir), range(args.start_year, args.end_year + 1))
    states["signed_state"] = causal_tercile(states["signed_gex"])
    states["total_gamma_state"] = causal_tercile(states["total_gamma"])
    states["concentration_state"] = causal_tercile(states["gamma_concentration"])
    panel = attach_outcomes(states, spy)

    rng = np.random.default_rng(args.seed)
    tests: list[dict[str, object]] = []
    for h in HORIZONS:
        specs = [
            ("signed_gex_continuation", "signed_state", f"continuation_{h}d", "low_gt_high"),
            ("total_gamma_movement", "total_gamma_state", f"movement_{h}d", "low_gt_high"),
            ("gamma_concentration_movement", "concentration_state", f"movement_{h}d", "high_gt_low"),
        ]
        for name, label_col, metric, expected in specs:
            diff, n_low, n_high = observed_difference(panel, label_col, metric, expected)
            p = permutation_pvalue(panel, label_col, metric, expected, diff, args.permutations, rng)
            tests.append(
                {
                    "test": name,
                    "horizon_days": h,
                    "expected": expected,
                    "difference": None if not np.isfinite(diff) else diff,
                    "n_low": n_low,
                    "n_high": n_high,
                    "permutation_p_one_sided": None if not np.isfinite(p) else p,
                    "yearly_differences": yearly_differences(panel, label_col, metric, expected),
                }
            )

    signed_passes = [
        t for t in tests
        if t["test"] == "signed_gex_continuation"
        and t["difference"] is not None
        and t["difference"] > 0
        and t["permutation_p_one_sided"] is not None
        and t["permutation_p_one_sided"] <= 0.05
    ]
    geometry_passes = [
        t for t in tests
        if t["test"] in {"total_gamma_movement", "gamma_concentration_movement"}
        and t["difference"] is not None
        and t["difference"] > 0
        and t["permutation_p_one_sided"] is not None
        and t["permutation_p_one_sided"] <= 0.05
    ]

    if missing_years:
        classification = "SCREEN_INCONCLUSIVE"
        reason = "MISSING_YEARLY_MIRROR_FILES"
    elif len(signed_passes) >= 2 and geometry_passes:
        classification = "SCREEN_POSITIVE"
        reason = "FROZEN_SANDBOX_GATE_PASSED"
    else:
        classification = "SCREEN_NEGATIVE"
        reason = "FROZEN_SANDBOX_GATE_FAILED"

    report = {
        "classification": classification,
        "reason": reason,
        "design": {
            "start_year": args.start_year,
            "end_year": args.end_year,
            "one_trading_day_source_lag": True,
            "min_prior_states_for_causal_terciles": MIN_PRIOR_STATES,
            "horizons_days": list(HORIZONS),
            "permutations": args.permutations,
            "seed": args.seed,
            "signed_convention": "call +gamma*OI; put -gamma*OI; model assumption only",
            "positive_gate": "signed continuation expected-direction significant at >=2 horizons AND sign-free gamma geometry movement significant at >=1 horizon",
        },
        "source": {
            "mirror_dir": str(args.mirror_dir),
            "missing_years": missing_years,
            "spy_csv": str(args.spy_csv),
            "mirror_state_dates": int(len(states)),
            "panel_rows": int(len(panel)),
            "date_min": None if panel.empty else pd.Timestamp(panel["date"].min()).date().isoformat(),
            "date_max": None if panel.empty else pd.Timestamp(panel["date"].max()).date().isoformat(),
        },
        "tests": tests,
        "signed_gate_pass_count": len(signed_passes),
        "geometry_gate_pass_count": len(geometry_passes),
        "boundary": "Sandbox screen only. SCREEN_POSITIVE earns governed research; it does not authorize any Core v1/Core v2/runtime/portfolio/paper/live action.",
    }
    report_path = out_dir / "dealer_gamma_pressure_screen.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    panel_cols = [
        "date", "usable_date", "signed_gex", "total_gamma", "gamma_concentration",
        "signed_state", "total_gamma_state", "concentration_state", "impulse_return",
    ] + [f"fwd_ret_{h}d" for h in HORIZONS] + [f"continuation_{h}d" for h in HORIZONS] + [f"movement_{h}d" for h in HORIZONS]
    panel[panel_cols].to_csv(out_dir / "dealer_gamma_pressure_panel.csv", index=False, lineterminator="\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
