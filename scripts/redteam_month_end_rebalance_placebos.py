"""Red-team placebo check for the month-end equity/bond rebalance sandbox hit.

This is a post-screen adversarial interpretation check, not a new alpha search and not a
change to the frozen sandbox classification. It asks whether the observed 3-session
SPY-minus-AGG reversal is specifically stronger at month-end than at matched non-month-end
windows.

Frozen before placebo outcomes are inspected:
- primary month-end window: final 3 shared trading sessions;
- placebo windows: 3-session windows ending 5, 10, and 15 shared trading sessions before month-end;
- signal for every window: SPY-minus-AGG relative return from prior month-end anchor through the
  close immediately before that 3-session window;
- same adjusted sandbox SPY/AGG files as the original screen;
- report Spearman(signal, outcome) and causal expanding-tercile low-minus-high outcome spread;
- interpretation survives only if actual month-end rho is more negative AND actual low-minus-high
  spread is larger than every placebo window.

A failure does not rewrite the original SCREEN_POSITIVE. It means the evidence does not isolate
month-end rebalancing from generic short-horizon relative mean reversion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

MIN_PRIOR_MONTHS = 36
WINDOW = 3
PLACEBO_OFFSETS = (5, 10, 15)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spy-csv", default="artifacts/month_end_rebalance_data/SPY_1D.csv")
    p.add_argument("--agg-csv", default="artifacts/month_end_rebalance_data/AGG_1D.csv")
    p.add_argument("--output-dir", default="artifacts/month_end_rebalance_pressure_screen")
    return p.parse_args()


def load_price(path: Path, name: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if not {"timestamp", "close"}.issubset(frame.columns):
        raise ValueError(f"{name}_SOURCE_MISSING_COLUMNS")
    out = frame[["timestamp", "close"]].copy()
    out["date"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["date", "close"])
    out = out[out["close"] > 0].sort_values("date").drop_duplicates("date", keep="last")
    return out[["date", "close"]].rename(columns={"close": name.lower()})


def causal_labels(signal: pd.Series) -> pd.Series:
    values = pd.to_numeric(signal, errors="coerce").to_numpy(float)
    labels = np.full(len(values), "", dtype=object)
    for i, value in enumerate(values):
        prior = values[:i]
        prior = prior[np.isfinite(prior)]
        if len(prior) < MIN_PRIOR_MONTHS or not np.isfinite(value):
            continue
        q1, q2 = np.quantile(prior, [1 / 3, 2 / 3])
        labels[i] = "low" if value <= q1 else ("high" if value >= q2 else "mid")
    return pd.Series(labels, index=signal.index)


def stats_for(panel: pd.DataFrame) -> dict[str, float | int | None]:
    valid = panel[["signal", "outcome"]].dropna()
    rho = float(stats.spearmanr(valid["signal"], valid["outcome"]).statistic) if len(valid) >= 3 else np.nan
    labels = causal_labels(panel["signal"])
    low = panel.loc[labels == "low", "outcome"].dropna()
    high = panel.loc[labels == "high", "outcome"].dropna()
    spread = float(low.mean() - high.mean()) if len(low) and len(high) else np.nan
    return {
        "n": int(len(valid)),
        "spearman_rho": None if not np.isfinite(rho) else rho,
        "low_minus_high_outcome": None if not np.isfinite(spread) else spread,
        "n_low": int(len(low)),
        "n_high": int(len(high)),
    }


def build_panels(spy: pd.DataFrame, agg: pd.DataFrame) -> dict[str, pd.DataFrame]:
    data = spy.merge(agg, on="date", how="inner").sort_values("date").reset_index(drop=True)
    data["month"] = data["date"].dt.to_period("M")
    groups = {p: g.reset_index(drop=True) for p, g in data.groupby("month", sort=True)}
    rows: dict[str, list[dict[str, object]]] = {"month_end": []}
    for offset in PLACEBO_OFFSETS:
        rows[f"minus_{offset}_sessions"] = []

    for period in sorted(groups):
        prior = period - 1
        if prior not in groups:
            continue
        current = groups[period]
        anchor = groups[prior].iloc[-1]
        targets = {"month_end": 0, **{f"minus_{o}_sessions": o for o in PLACEBO_OFFSETS}}
        for name, offset in targets.items():
            end_pos = len(current) - 1 - offset
            start_pos = end_pos - WINDOW + 1
            cutoff_pos = start_pos - 1
            if cutoff_pos < 0 or end_pos >= len(current):
                continue
            cutoff = current.iloc[cutoff_pos]
            end = current.iloc[end_pos]
            spy_signal = float(cutoff["spy"] / anchor["spy"] - 1.0)
            agg_signal = float(cutoff["agg"] / anchor["agg"] - 1.0)
            spy_out = float(end["spy"] / cutoff["spy"] - 1.0)
            agg_out = float(end["agg"] / cutoff["agg"] - 1.0)
            rows[name].append({
                "month": str(period),
                "signal": spy_signal - agg_signal,
                "outcome": spy_out - agg_out,
            })
    return {name: pd.DataFrame(vals) for name, vals in rows.items()}


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    spy = load_price(Path(args.spy_csv), "SPY")
    agg = load_price(Path(args.agg_csv), "AGG")
    panels = build_panels(spy, agg)
    results = {name: stats_for(panel) for name, panel in panels.items()}
    primary = results["month_end"]
    placebo_names = [f"minus_{o}_sessions" for o in PLACEBO_OFFSETS]
    rho_survives = all(
        primary["spearman_rho"] is not None
        and results[name]["spearman_rho"] is not None
        and float(primary["spearman_rho"]) < float(results[name]["spearman_rho"])
        for name in placebo_names
    )
    spread_survives = all(
        primary["low_minus_high_outcome"] is not None
        and results[name]["low_minus_high_outcome"] is not None
        and float(primary["low_minus_high_outcome"]) > float(results[name]["low_minus_high_outcome"])
        for name in placebo_names
    )
    interpretation = "MONTH_END_SPECIFICITY_SURVIVES" if rho_survives and spread_survives else "GENERIC_REVERSAL_CONFOUND_NOT_REJECTED"
    report = {
        "status": interpretation,
        "frozen_placebo_offsets_sessions_before_month_end": list(PLACEBO_OFFSETS),
        "window_sessions": WINDOW,
        "results": results,
        "month_end_rho_more_negative_than_all_placebos": rho_survives,
        "month_end_spread_larger_than_all_placebos": spread_survives,
        "boundary": "Red-team interpretation check only. Does not alter the original sandbox classification or authorize any portfolio/runtime action.",
    }
    path = output_dir / "month_end_rebalance_placebo_redteam.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
