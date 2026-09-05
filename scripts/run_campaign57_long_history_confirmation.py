"""Campaign #57 one-shot long-history historical confirmation.

Research-only. This runner is the first Campaign #57 code authorized to read
VFINX/VBMFX adjusted closes. It must be committed before execution.

Governance:
  docs/research/CAMPAIGN_57_VALIDATION_ARCHITECTURE_AMENDMENT_2.md

Frozen primary confirmation test:
- final 3 shared trading sessions of each calendar month;
- signal = equity minus bond adjusted-total-return performance from prior
  month-end anchor through the cutoff close;
- outcome = equity minus bond adjusted-total-return performance from cutoff
  through month-end;
- Spearman rho must be < 0;
- one-sided permutation p <= 0.05;
- 10,000 permutations, shuffling signal within five-year calendar blocks;
- fixed seed 20260957.

Frozen robustness diagnostics. A primary pass is CLEAN only if all are true:
1. causal expanding-tercile low-minus-high outcome spread > 0;
2. every decade/era bucket with >=24 valid months has Spearman rho < 0;
3. every eligible leave-one-calendar-year-out aggregate Spearman rho < 0;
4. Spearman rho remains < 0 after removing the 10 largest absolute-signal months;
5. actual month-end Spearman rho is more negative than each otherwise-analogous
   3-session placebo ending 5, 10, and 15 sessions before month-end.

Classification:
- primary fails -> HISTORICAL_CONFIRMATION_NEGATIVE
- primary passes + all robustness directions pass -> HISTORICAL_CONFIRMATION_POSITIVE
- primary passes + any robustness direction fails -> HISTORICAL_CONFIRMATION_CONDITIONAL
- source/timing failure -> HISTORICAL_CONFIRMATION_INVALID

No result from this runner authorizes runtime, portfolio, Core v1/Core v2,
paper/live, sizing, or capital action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# Keep standalone script execution working until the separate packaging migration.
import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
if str(_ArtifactPath(__file__).resolve().parents[1]) not in _artifact_sys.path:
    _artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parents[1]))


SEED = 20260957
N_PERMUTATIONS = 10_000
PRIMARY_WINDOW = 3
PLACEBO_OFFSETS = (5, 10, 15)
MIN_PRIOR_MONTHS = 36
MIN_ERA_MONTHS = 24


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--equity-csv", default="artifacts/campaign57_long_history/VFINX_1D.csv")
    p.add_argument("--bond-csv", default="artifacts/campaign57_long_history/VBMFX_1D.csv")
    p.add_argument("--output-dir", default="artifacts/campaign57_long_history_confirmation")
    return p.parse_args()


def sha256_file(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=hashlib.sha256)


def load_adjusted(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{name}_SOURCE_MISSING:{path}")
    frame = pd.read_csv(path)
    required = {"timestamp", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{name}_MISSING_COLUMNS:{sorted(missing)}")
    out = frame[["timestamp", "close"]].copy()
    out["date"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["date", "close"])
    if (out["close"] <= 0).any():
        raise ValueError(f"{name}_NONPOSITIVE_CLOSE")
    if out["date"].duplicated().any():
        raise ValueError(f"{name}_DUPLICATE_DATE")
    out = out.sort_values("date")
    return out[["date", "close"]].rename(columns={"close": name.lower()})


def build_shared(equity: pd.DataFrame, bond: pd.DataFrame) -> pd.DataFrame:
    data = equity.merge(bond, on="date", how="inner").sort_values("date").reset_index(drop=True)
    if data.empty:
        raise ValueError("NO_SHARED_SESSIONS")
    data["month"] = data["date"].dt.to_period("M")
    return data


def monthly_groups(data: pd.DataFrame) -> dict[pd.Period, pd.DataFrame]:
    return {m: g.reset_index(drop=True) for m, g in data.groupby("month", sort=True)}


def event_for_window(groups: dict[pd.Period, pd.DataFrame], month: pd.Period, window: int, offset: int = 0) -> dict[str, object] | None:
    prior = month - 1
    if prior not in groups or month not in groups:
        return None
    current = groups[month]
    prior_group = groups[prior]
    end_pos = len(current) - 1 - offset
    cutoff_pos = end_pos - window
    if cutoff_pos < 0 or end_pos < 0:
        return None
    anchor = prior_group.iloc[-1]
    cutoff = current.iloc[cutoff_pos]
    end = current.iloc[end_pos]
    eq_signal = float(cutoff["equity"] / anchor["equity"] - 1.0)
    bd_signal = float(cutoff["bond"] / anchor["bond"] - 1.0)
    eq_outcome = float(end["equity"] / cutoff["equity"] - 1.0)
    bd_outcome = float(end["bond"] / cutoff["bond"] - 1.0)
    return {
        "month": str(month),
        "year": int(month.year),
        "signal": eq_signal - bd_signal,
        "outcome": eq_outcome - bd_outcome,
        "anchor_date": pd.Timestamp(anchor["date"]),
        "cutoff_date": pd.Timestamp(cutoff["date"]),
        "end_date": pd.Timestamp(end["date"]),
    }


def build_panel(data: pd.DataFrame, window: int, offset: int = 0) -> pd.DataFrame:
    groups = monthly_groups(data)
    rows = []
    for month in sorted(groups):
        row = event_for_window(groups, month, window, offset)
        if row is not None:
            rows.append(row)
    panel = pd.DataFrame(rows)
    if panel.empty:
        raise ValueError(f"EMPTY_PANEL_WINDOW_{window}_OFFSET_{offset}")
    return panel.sort_values("month").reset_index(drop=True)


def spearman(signal: pd.Series, outcome: pd.Series) -> float:
    result = stats.spearmanr(pd.to_numeric(signal), pd.to_numeric(outcome))
    return float(result.statistic)


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
    return pd.Series(labels, index=signal.index, dtype="object")


def tercile_spread(panel: pd.DataFrame) -> tuple[float, int, int]:
    labels = causal_labels(panel["signal"])
    low = panel.loc[labels == "low", "outcome"]
    high = panel.loc[labels == "high", "outcome"]
    if low.empty or high.empty:
        return np.nan, int(len(low)), int(len(high))
    return float(low.mean() - high.mean()), int(len(low)), int(len(high))


def blocks(panel: pd.DataFrame) -> np.ndarray:
    years = panel["year"].to_numpy(int)
    return (years // 5) * 5


def permutation_p(panel: pd.DataFrame, observed_rho: float) -> float:
    rng = np.random.default_rng(SEED)
    signal = panel["signal"].to_numpy(float)
    outcome = panel["outcome"].to_numpy(float)
    block_ids = blocks(panel)
    count = 0
    for _ in range(N_PERMUTATIONS):
        shuffled = signal.copy()
        for block in np.unique(block_ids):
            idx = np.flatnonzero(block_ids == block)
            shuffled[idx] = rng.permutation(shuffled[idx])
        rho = float(stats.spearmanr(shuffled, outcome).statistic)
        if rho <= observed_rho:
            count += 1
    return float((1 + count) / (N_PERMUTATIONS + 1))


def era_diagnostics(panel: pd.DataFrame) -> dict[str, object]:
    out: dict[str, object] = {}
    panel = panel.copy()
    panel["decade"] = (panel["year"] // 10) * 10
    for decade, group in panel.groupby("decade", sort=True):
        if len(group) < MIN_ERA_MONTHS:
            continue
        out[str(int(decade))] = {"n": int(len(group)), "spearman_rho": spearman(group["signal"], group["outcome"])}
    return out


def leave_one_year_out(panel: pd.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    for year in sorted(panel["year"].unique()):
        if int((panel["year"] == year).sum()) < 6:
            continue
        subset = panel[panel["year"] != year]
        out[str(int(year))] = spearman(subset["signal"], subset["outcome"])
    return out


def top_signal_months(panel: pd.DataFrame) -> list[dict[str, object]]:
    rows = panel.assign(abs_signal=panel["signal"].abs()).sort_values("abs_signal", ascending=False).head(10)
    return rows[["month", "signal", "outcome"]].to_dict(orient="records")


def placebo_rhos(data: pd.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    for offset in PLACEBO_OFFSETS:
        p = build_panel(data, PRIMARY_WINDOW, offset=offset)
        out[f"minus_{offset}_sessions"] = spearman(p["signal"], p["outcome"])
    return out


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    equity_path = Path(args.equity_csv)
    bond_path = Path(args.bond_csv)

    try:
        equity = load_adjusted(equity_path, "equity")
        bond = load_adjusted(bond_path, "bond")
        shared = build_shared(equity, bond)
        panel = build_panel(shared, PRIMARY_WINDOW, offset=0)
    except Exception as exc:
        report = {
            "classification": "HISTORICAL_CONFIRMATION_INVALID",
            "reason": "SOURCE_OR_TIMING_FAILURE",
            "error": f"{type(exc).__name__}: {exc}",
            "boundary": "Campaign #57 research only; no portfolio/runtime authorization.",
        }
        (output_dir / "campaign57_long_history_confirmation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    rho = spearman(panel["signal"], panel["outcome"])
    p_value = permutation_p(panel, rho)
    spread, n_low, n_high = tercile_spread(panel)
    eras = era_diagnostics(panel)
    loo = leave_one_year_out(panel)
    extremes = top_signal_months(panel)
    trimmed = panel.loc[~panel.index.isin(panel["signal"].abs().nlargest(10).index)].copy()
    trimmed_rho = spearman(trimmed["signal"], trimmed["outcome"])
    placebos = placebo_rhos(shared)

    primary_pass = rho < 0 and p_value <= 0.05
    robustness = {
        "tercile_spread_positive": bool(np.isfinite(spread) and spread > 0),
        "all_eligible_era_rhos_negative": bool(eras) and all(float(x["spearman_rho"]) < 0 for x in eras.values()),
        "all_eligible_leave_one_year_out_rhos_negative": bool(loo) and all(float(x) < 0 for x in loo.values()),
        "trimmed_top10_absolute_signal_rho_negative": bool(np.isfinite(trimmed_rho) and trimmed_rho < 0),
        "month_end_rho_more_negative_than_all_placebos": all(rho < float(x) for x in placebos.values()),
    }
    robustness_clean = all(robustness.values())

    if not primary_pass:
        classification = "HISTORICAL_CONFIRMATION_NEGATIVE"
        reason = "PRIMARY_GATE_FAILED"
    elif robustness_clean:
        classification = "HISTORICAL_CONFIRMATION_POSITIVE"
        reason = "PRIMARY_AND_FROZEN_ROBUSTNESS_PASSED"
    else:
        classification = "HISTORICAL_CONFIRMATION_CONDITIONAL"
        reason = "PRIMARY_PASSED_ROBUSTNESS_CONCERN"

    report = {
        "classification": classification,
        "reason": reason,
        "boundary": "Campaign #57 historical confirmation only. No Core v1/Core v2/runtime/portfolio/paper/live/capital action authorized.",
        "design": {
            "primary_window_sessions": PRIMARY_WINDOW,
            "primary_test": "Spearman rho<0 with one-sided within-five-year-block permutation p<=0.05",
            "permutations": N_PERMUTATIONS,
            "seed": SEED,
            "placebo_offsets_sessions_before_month_end": list(PLACEBO_OFFSETS),
            "minimum_prior_months_for_causal_terciles": MIN_PRIOR_MONTHS,
        },
        "source": {
            "equity_csv": args.equity_csv,
            "bond_csv": args.bond_csv,
            "equity_sha256": sha256_file(equity_path),
            "bond_sha256": sha256_file(bond_path),
            "equity_date_min": equity["date"].min().date().isoformat(),
            "equity_date_max": equity["date"].max().date().isoformat(),
            "bond_date_min": bond["date"].min().date().isoformat(),
            "bond_date_max": bond["date"].max().date().isoformat(),
            "shared_sessions": int(len(shared)),
            "valid_months": int(len(panel)),
            "valid_month_start": str(panel.iloc[0]["month"]),
            "valid_month_end": str(panel.iloc[-1]["month"]),
        },
        "primary": {
            "spearman_rho": rho,
            "permutation_p_one_sided": p_value,
            "pass": primary_pass,
        },
        "robustness": {
            "checks": robustness,
            "clean": robustness_clean,
            "causal_low_minus_high_spread": spread,
            "n_low": n_low,
            "n_high": n_high,
            "era_spearman": eras,
            "leave_one_year_out_spearman": loo,
            "trimmed_top10_absolute_signal_spearman": trimmed_rho,
            "placebo_spearman": placebos,
            "top_10_absolute_signal_months": extremes,
        },
    }

    panel.to_csv(output_dir / "campaign57_long_history_panel.csv", index=False)
    (output_dir / "campaign57_long_history_confirmation.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0 if classification == "HISTORICAL_CONFIRMATION_POSITIVE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
