"""Campaign #57 pre-outcome VTI/BND calendar partition + power preflight.

Research-only. This script deliberately reads ONLY the timestamp column from the
VTI/BND adjusted-price CSVs. It never reads close/returns and therefore cannot
inspect the confirmatory relationship.

Frozen before VTI/BND outcome inspection:
- common valid months split chronologically 50% development, 25% OOS, 25% final holdout;
- sandbox discovery ceiling: Spearman=-0.24861256166873433, tercile spread=0.008477770698736769;
- injected effect haircuts: 25%, 40%, 50%; central gate = 50%;
- 500 outer simulations per effect level;
- 199 within-five-year-block permutations per outer simulation;
- fixed seed 20260957;
- OOS and final holdout each require >=80% estimated joint-gate power at the central effect.

The optimized implementation preserves those frozen choices exactly. It replaces
repeated scipy Spearman calls with equivalent rank-correlation arithmetic and
computes causal terciles incrementally from sorted prior values. This is a pure
runtime optimization; it does not change the null, seed, simulations, permutations,
calendar partitions, effect grid, or pass/fail gate.

Usage:
    python scripts/preflight_campaign57_vti_bnd_partitions.py

Expected inputs:
    artifacts/campaign57_vti_bnd/VTI_1D.csv
    artifacts/campaign57_vti_bnd/BND_1D.csv
"""

from __future__ import annotations

import argparse
import bisect
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

SANDBOX_SPEARMAN = -0.24861256166873433
SANDBOX_SPREAD = 0.008477770698736769
HAIRCUTS = (0.25, 0.40, 0.50)
CENTRAL_HAIRCUT = 0.50
OUTER_SIMS = 500
N_PERMUTATIONS = 199
SEED = 20260957
MIN_PRIOR_MONTHS = 36
POWER_FLOOR = 0.80
PROGRESS_EVERY = 50


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vti-csv", default="artifacts/campaign57_vti_bnd/VTI_1D.csv")
    p.add_argument("--bnd-csv", default="artifacts/campaign57_vti_bnd/BND_1D.csv")
    p.add_argument("--output-dir", default="artifacts/campaign57_vti_bnd_preflight")
    return p.parse_args()


def load_dates_only(path: Path, name: str) -> pd.DatetimeIndex:
    if not path.exists():
        raise FileNotFoundError(f"{name}_SOURCE_MISSING:{path}")
    frame = pd.read_csv(path, usecols=["timestamp"])
    dates = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    dates = dates.dropna().drop_duplicates().sort_values()
    if dates.empty:
        raise ValueError(f"{name}_NO_VALID_DATES")
    return pd.DatetimeIndex(dates)


def valid_common_months(vti_dates: pd.DatetimeIndex, bnd_dates: pd.DatetimeIndex) -> list[pd.Period]:
    common = pd.DatetimeIndex(sorted(set(vti_dates).intersection(set(bnd_dates))))
    if len(common) == 0:
        raise ValueError("NO_COMMON_VTI_BND_SESSIONS")
    frame = pd.DataFrame({"date": common})
    frame["month"] = frame["date"].dt.to_period("M")
    grouped = {m: g for m, g in frame.groupby("month", sort=True)}
    months = sorted(grouped)
    valid: list[pd.Period] = []
    for month in months:
        prior = month - 1
        if prior in grouped and len(grouped[month]) >= 6 and len(grouped[prior]) >= 1:
            valid.append(month)
    return valid


def partition_months(months: list[pd.Period]) -> dict[str, list[pd.Period]]:
    n = len(months)
    if n < 120:
        raise ValueError(f"INSUFFICIENT_COMMON_MONTHS:{n}")
    dev_end = n // 2
    oos_end = dev_end + (n - dev_end) // 2
    return {
        "development": months[:dev_end],
        "oos": months[dev_end:oos_end],
        "holdout": months[oos_end:],
    }


def _sorted_quantile(sorted_values: list[float], q: float) -> float:
    """Match numpy's default linear quantile on an already sorted list."""
    n = len(sorted_values)
    if n == 0:
        return np.nan
    pos = (n - 1) * q
    lo = int(np.floor(pos))
    hi = int(np.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])
    w = pos - lo
    return float(sorted_values[lo] * (1.0 - w) + sorted_values[hi] * w)


def causal_labels_for_idx(signal: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Exact causal labels for tested indices only, using all prior observations."""
    if len(idx) == 0:
        return np.empty(0, dtype=object)
    order = np.argsort(idx)
    sorted_idx = idx[order]
    out_sorted = np.full(len(sorted_idx), "", dtype=object)
    prior_sorted: list[float] = []
    next_test = 0
    max_i = int(sorted_idx[-1])
    test_positions = {int(v): j for j, v in enumerate(sorted_idx)}
    for i in range(max_i + 1):
        if i in test_positions:
            j = test_positions[i]
            value = signal[i]
            if len(prior_sorted) >= MIN_PRIOR_MONTHS and np.isfinite(value):
                q1 = _sorted_quantile(prior_sorted, 1.0 / 3.0)
                q2 = _sorted_quantile(prior_sorted, 2.0 / 3.0)
                out_sorted[j] = "low" if value <= q1 else ("high" if value >= q2 else "mid")
        value = signal[i]
        if np.isfinite(value):
            bisect.insort(prior_sorted, float(value))
    out = np.empty(len(idx), dtype=object)
    out[order] = out_sorted
    return out


def _rank_corr(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return np.nan
    rx = stats.rankdata(x, method="average")
    ry = stats.rankdata(y, method="average")
    sx = float(np.std(rx))
    sy = float(np.std(ry))
    if sx == 0.0 or sy == 0.0:
        return np.nan
    return float(np.corrcoef(rx, ry)[0, 1])


def spearman(signal: np.ndarray, outcome: np.ndarray, idx: np.ndarray) -> float:
    return _rank_corr(signal[idx], outcome[idx])


def spread(signal: np.ndarray, outcome: np.ndarray, idx: np.ndarray) -> float:
    labels = causal_labels_for_idx(signal, idx)
    test_outcome = outcome[idx]
    low = test_outcome[labels == "low"]
    high = test_outcome[labels == "high"]
    if len(low) == 0 or len(high) == 0:
        return np.nan
    return float(np.mean(low) - np.mean(high))


def five_year_blocks(months: list[pd.Period]) -> np.ndarray:
    years = np.array([m.year for m in months], dtype=int)
    return (years // 5) * 5


def shuffled_test_signal(signal: np.ndarray, test_idx: np.ndarray, blocks: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = signal.copy()
    test_blocks = blocks[test_idx]
    for block in np.unique(test_blocks):
        idx = test_idx[test_blocks == block]
        out[idx] = rng.permutation(out[idx])
    return out


def permutation_pvalues(signal: np.ndarray, outcome: np.ndarray, test_idx: np.ndarray, blocks: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    obs_rho = spearman(signal, outcome, test_idx)
    obs_spread = spread(signal, outcome, test_idx)
    if not np.isfinite(obs_rho) or not np.isfinite(obs_spread):
        return np.nan, np.nan

    # Outcome ranks are constant throughout the permutation test.
    out_ranks = stats.rankdata(outcome[test_idx], method="average")
    out_ranks_centered = out_ranks - out_ranks.mean()
    out_norm = float(np.sqrt(np.dot(out_ranks_centered, out_ranks_centered)))

    null_rho = np.empty(N_PERMUTATIONS, dtype=float)
    null_spread = np.empty(N_PERMUTATIONS, dtype=float)
    for i in range(N_PERMUTATIONS):
        shuffled = shuffled_test_signal(signal, test_idx, blocks, rng)
        sig_ranks = stats.rankdata(shuffled[test_idx], method="average")
        sig_centered = sig_ranks - sig_ranks.mean()
        sig_norm = float(np.sqrt(np.dot(sig_centered, sig_centered)))
        null_rho[i] = np.nan if sig_norm == 0.0 or out_norm == 0.0 else float(
            np.dot(sig_centered, out_ranks_centered) / (sig_norm * out_norm)
        )
        null_spread[i] = spread(shuffled, outcome, test_idx)

    valid_rho = null_rho[np.isfinite(null_rho)]
    valid_spread = null_spread[np.isfinite(null_spread)]
    p_rho = np.nan if len(valid_rho) == 0 else float((1 + np.sum(valid_rho <= obs_rho)) / (1 + len(valid_rho)))
    p_spread = np.nan if len(valid_spread) == 0 else float((1 + np.sum(valid_spread >= obs_spread)) / (1 + len(valid_spread)))
    return p_rho, p_spread


def leave_one_year_out_negative(signal: np.ndarray, outcome: np.ndarray, test_idx: np.ndarray, months: list[pd.Period]) -> bool:
    years = np.array([m.year for m in months], dtype=int)
    test_years = years[test_idx]
    checked = 0
    for year in np.unique(test_years):
        if int(np.sum(test_years == year)) < 6:
            continue
        idx = test_idx[test_years != year]
        rho = spearman(signal, outcome, idx)
        if not np.isfinite(rho) or rho >= 0:
            return False
        checked += 1
    return checked > 0


def passes_joint_gate(signal: np.ndarray, outcome: np.ndarray, test_idx: np.ndarray, months: list[pd.Period], blocks: np.ndarray, rng: np.random.Generator) -> bool:
    rho = spearman(signal, outcome, test_idx)
    spr = spread(signal, outcome, test_idx)
    if not np.isfinite(rho) or rho >= 0 or not np.isfinite(spr) or spr <= 0:
        return False
    p_rho, p_spread = permutation_pvalues(signal, outcome, test_idx, blocks, rng)
    if not np.isfinite(p_rho) or p_rho > 0.05 or not np.isfinite(p_spread) or p_spread > 0.05:
        return False
    return leave_one_year_out_negative(signal, outcome, test_idx, months)


def gaussian_params(haircut: float) -> tuple[float, float, float, float]:
    target_spearman = SANDBOX_SPEARMAN * haircut
    target_spread = SANDBOX_SPREAD * haircut
    target_pearson = float(2.0 * np.sin(np.pi * target_spearman / 6.0))
    q = stats.norm.ppf(2 / 3)
    mu_upper = stats.norm.pdf(q) / (1 - stats.norm.cdf(q))
    x_low_minus_high = -2.0 * mu_upper
    beta = target_spread / x_low_minus_high
    r_abs = max(abs(target_pearson), 1e-6)
    sigma_eps = abs(beta) * np.sqrt(max(1.0 / (r_abs * r_abs) - 1.0, 0.0))
    return target_spearman, target_spread, beta, sigma_eps


def estimate_power(months: list[pd.Period], partitions: dict[str, list[pd.Period]], haircut: float, seed: int) -> dict[str, float | int]:
    month_to_idx = {m: i for i, m in enumerate(months)}
    oos_idx = np.array([month_to_idx[m] for m in partitions["oos"]], dtype=int)
    holdout_idx = np.array([month_to_idx[m] for m in partitions["holdout"]], dtype=int)
    blocks = five_year_blocks(months)
    target_s, target_spread, beta, sigma_eps = gaussian_params(haircut)
    rng = np.random.default_rng(seed)
    oos_pass = 0
    holdout_pass = 0

    print(f"Power haircut {haircut:.0%}: {OUTER_SIMS} simulations", flush=True)
    for sim in range(1, OUTER_SIMS + 1):
        signal = rng.normal(0.0, 1.0, size=len(months))
        outcome = beta * signal + rng.normal(0.0, sigma_eps, size=len(months))
        if passes_joint_gate(signal, outcome, oos_idx, months, blocks, rng):
            oos_pass += 1
        if passes_joint_gate(signal, outcome, holdout_idx, months, blocks, rng):
            holdout_pass += 1
        if sim % PROGRESS_EVERY == 0 or sim == OUTER_SIMS:
            print(
                f"  {sim}/{OUTER_SIMS} | OOS pass {oos_pass}/{sim} ({oos_pass/sim:.1%}) | "
                f"holdout pass {holdout_pass}/{sim} ({holdout_pass/sim:.1%})",
                flush=True,
            )

    return {
        "haircut": haircut,
        "target_spearman": target_s,
        "target_low_minus_high_spread": target_spread,
        "outer_simulations": OUTER_SIMS,
        "permutations_per_simulation": N_PERMUTATIONS,
        "oos_power": oos_pass / OUTER_SIMS,
        "holdout_power": holdout_pass / OUTER_SIMS,
    }


def period_range(items: list[pd.Period]) -> dict[str, object]:
    return {"months": len(items), "start": str(items[0]) if items else None, "end": str(items[-1]) if items else None}


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        vti_dates = load_dates_only(Path(args.vti_csv), "VTI")
        bnd_dates = load_dates_only(Path(args.bnd_csv), "BND")
        months = valid_common_months(vti_dates, bnd_dates)
        partitions = partition_months(months)
    except Exception as exc:
        report = {"status": "NOT_READY", "reason": "SOURCE_OR_CALENDAR_FAILURE", "error": f"{type(exc).__name__}: {exc}", "outcomes_inspected": False}
        print(json.dumps(report, indent=2, sort_keys=True))
        (out_dir / "campaign57_preflight.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 2

    print(f"Shared valid months: {len(months)}", flush=True)
    for name, items in partitions.items():
        r = period_range(items)
        print(f"  {name}: {r['months']} months | {r['start']} -> {r['end']}", flush=True)

    power = [estimate_power(months, partitions, h, SEED + int(h * 1000)) for h in HAIRCUTS]
    central = next(x for x in power if abs(float(x["haircut"]) - CENTRAL_HAIRCUT) < 1e-12)
    oos_ok = float(central["oos_power"]) >= POWER_FLOOR
    holdout_ok = float(central["holdout_power"]) >= POWER_FLOOR
    status = "POWER_PASS" if oos_ok and holdout_ok else "POWER_FAIL"

    report = {
        "status": status,
        "outcomes_inspected": False,
        "source": {
            "vti_csv": args.vti_csv,
            "bnd_csv": args.bnd_csv,
            "vti_date_min": vti_dates.min().date().isoformat(),
            "vti_date_max": vti_dates.max().date().isoformat(),
            "bnd_date_min": bnd_dates.min().date().isoformat(),
            "bnd_date_max": bnd_dates.max().date().isoformat(),
            "shared_valid_months": len(months),
        },
        "partition_rule": "chronological 50% development / 25% OOS / 25% sealed final holdout by valid common-month sequence",
        "partitions": {name: period_range(items) for name, items in partitions.items()},
        "power_design": {
            "sandbox_spearman_ceiling": SANDBOX_SPEARMAN,
            "sandbox_spread_ceiling": SANDBOX_SPREAD,
            "haircuts": list(HAIRCUTS),
            "central_haircut": CENTRAL_HAIRCUT,
            "outer_simulations": OUTER_SIMS,
            "permutations_per_simulation": N_PERMUTATIONS,
            "seed": SEED,
            "power_floor_each_oos_and_holdout": POWER_FLOOR,
            "joint_gate_includes": [
                "Spearman<0 and one-sided block-permutation p<=0.05",
                "causal-tercile low-minus-high spread>0 and one-sided block-permutation p<=0.05",
                "every eligible leave-one-year-out Spearman<0",
            ],
            "runtime_optimization_only": True,
        },
        "power_results": power,
        "central_gate": {"oos_power": central["oos_power"], "holdout_power": central["holdout_power"], "oos_pass": oos_ok, "holdout_pass": holdout_ok},
        "boundary": "Pre-outcome calendar/power preflight only. VTI/BND close/returns are not read. POWER_PASS does not itself authorize confirmation outcome inspection.",
    }
    (out_dir / "campaign57_preflight.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if status == "POWER_PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
