"""Campaign #57 long-history historical-confirmation preflight.

Research-only and PRE-OUTCOME. This script reads ONLY the timestamp column from
VFINX/VBMFX adjusted-price CSVs. It never reads close/returns and therefore
cannot inspect the Campaign #57 confirmation relationship.

Frozen by Campaign #57 Validation Architecture Amendment 2:
- proposed long-history pair: VFINX / VBMFX;
- primary historical-confirmation statistic: Spearman rank correlation;
- expected direction: negative;
- null: signal shuffled within five-year calendar blocks;
- one-sided p <= 0.05;
- sandbox Spearman ceiling = -0.24861256166873433;
- effect haircuts = 25%, 40%, 50%; central gate = 50%;
- 500 outer simulations per haircut;
- 199 permutations per simulation;
- fixed seed = 20260957;
- power floor = 80% at central haircut.

Usage:
    python scripts/preflight_campaign57_long_history_confirmation.py

Expected inputs:
    artifacts/campaign57_long_history/VFINX_1D.csv
    artifacts/campaign57_long_history/VBMFX_1D.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


SANDBOX_SPEARMAN = -0.24861256166873433
HAIRCUTS = (0.25, 0.40, 0.50)
CENTRAL_HAIRCUT = 0.50
OUTER_SIMS = 500
N_PERMUTATIONS = 199
SEED = 20260957
POWER_FLOOR = 0.80
MIN_VALID_MONTHS = 120


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--equity-csv", default="artifacts/campaign57_long_history/VFINX_1D.csv")
    p.add_argument("--bond-csv", default="artifacts/campaign57_long_history/VBMFX_1D.csv")
    p.add_argument("--output-dir", default="artifacts/campaign57_long_history_preflight")
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


def valid_common_months(equity_dates: pd.DatetimeIndex, bond_dates: pd.DatetimeIndex) -> list[pd.Period]:
    common = pd.DatetimeIndex(sorted(set(equity_dates).intersection(set(bond_dates))))
    if len(common) == 0:
        raise ValueError("NO_COMMON_SESSIONS")
    frame = pd.DataFrame({"date": common})
    frame["month"] = frame["date"].dt.to_period("M")
    grouped = {m: g for m, g in frame.groupby("month", sort=True)}
    months = sorted(grouped)
    valid: list[pd.Period] = []
    for month in months:
        prior = month - 1
        if prior in grouped and len(grouped[month]) >= 6 and len(grouped[prior]) >= 1:
            valid.append(month)
    if len(valid) < MIN_VALID_MONTHS:
        raise ValueError(f"INSUFFICIENT_COMMON_MONTHS:{len(valid)}")
    return valid


def rankdata(a: np.ndarray) -> np.ndarray:
    # Synthetic generator is continuous, so ties should be absent. Keep average-rank
    # behavior for safety and mathematical equivalence to Spearman.
    return stats.rankdata(a, method="average")


def spearman_fast(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return np.nan
    rx = rankdata(x)
    ry = rankdata(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = np.sqrt(np.dot(rx, rx) * np.dot(ry, ry))
    if denom <= 0:
        return np.nan
    return float(np.dot(rx, ry) / denom)


def five_year_blocks(months: list[pd.Period]) -> np.ndarray:
    years = np.array([m.year for m in months], dtype=int)
    return (years // 5) * 5


def permute_within_blocks(values: np.ndarray, blocks: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = values.copy()
    for block in np.unique(blocks):
        idx = np.flatnonzero(blocks == block)
        out[idx] = rng.permutation(out[idx])
    return out


def permutation_pvalue(signal: np.ndarray, outcome: np.ndarray, blocks: np.ndarray, rng: np.random.Generator) -> float:
    observed = spearman_fast(signal, outcome)
    if not np.isfinite(observed):
        return np.nan
    count = 0
    valid = 0
    for _ in range(N_PERMUTATIONS):
        shuffled = permute_within_blocks(signal, blocks, rng)
        rho = spearman_fast(shuffled, outcome)
        if np.isfinite(rho):
            valid += 1
            if rho <= observed:
                count += 1
    if valid == 0:
        return np.nan
    return float((1 + count) / (1 + valid))


def target_pearson_from_spearman(target_spearman: float) -> float:
    # Bivariate-normal relationship: rho_s = 6/pi * asin(rho_p/2).
    return float(2.0 * np.sin(np.pi * target_spearman / 6.0))


def estimate_power(months: list[pd.Period], haircut: float, seed: int) -> dict[str, float | int]:
    target_s = SANDBOX_SPEARMAN * haircut
    target_p = target_pearson_from_spearman(target_s)
    blocks = five_year_blocks(months)
    rng = np.random.default_rng(seed)
    passed = 0

    # Construct standardized bivariate normal with desired Pearson correlation.
    noise_scale = float(np.sqrt(max(1.0 - target_p * target_p, 0.0)))

    print(f"Power haircut {haircut:.0%}: {OUTER_SIMS} simulations", flush=True)
    for i in range(1, OUTER_SIMS + 1):
        signal = rng.normal(0.0, 1.0, size=len(months))
        eps = rng.normal(0.0, 1.0, size=len(months))
        outcome = target_p * signal + noise_scale * eps
        rho = spearman_fast(signal, outcome)
        if np.isfinite(rho) and rho < 0:
            p = permutation_pvalue(signal, outcome, blocks, rng)
            if np.isfinite(p) and p <= 0.05:
                passed += 1
        if i % 50 == 0 or i == OUTER_SIMS:
            print(f"  {i}/{OUTER_SIMS} | pass {passed}/{i} ({passed / i:.1%})", flush=True)

    return {
        "haircut": haircut,
        "target_spearman": target_s,
        "target_pearson_gaussian": target_p,
        "outer_simulations": OUTER_SIMS,
        "permutations_per_simulation": N_PERMUTATIONS,
        "power": passed / OUTER_SIMS,
    }


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        equity_dates = load_dates_only(Path(args.equity_csv), "VFINX")
        bond_dates = load_dates_only(Path(args.bond_csv), "VBMFX")
        months = valid_common_months(equity_dates, bond_dates)
    except Exception as exc:
        report = {
            "status": "NOT_READY",
            "reason": "SOURCE_OR_CALENDAR_FAILURE",
            "error": f"{type(exc).__name__}: {exc}",
            "outcomes_inspected": False,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        (out_dir / "campaign57_long_history_preflight.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return 2

    print(
        f"Shared valid months: {len(months)} | {months[0]} -> {months[-1]}",
        flush=True,
    )

    power_results = [
        estimate_power(months, haircut, SEED + int(haircut * 1000))
        for haircut in HAIRCUTS
    ]
    central = next(x for x in power_results if abs(float(x["haircut"]) - CENTRAL_HAIRCUT) < 1e-12)
    central_power = float(central["power"])
    status = "POWER_PASS" if central_power >= POWER_FLOOR else "POWER_FAIL"

    report = {
        "status": status,
        "outcomes_inspected": False,
        "source": {
            "equity_csv": args.equity_csv,
            "bond_csv": args.bond_csv,
            "equity_date_min": equity_dates.min().date().isoformat(),
            "equity_date_max": equity_dates.max().date().isoformat(),
            "bond_date_min": bond_dates.min().date().isoformat(),
            "bond_date_max": bond_dates.max().date().isoformat(),
            "shared_valid_months": len(months),
            "valid_month_start": str(months[0]),
            "valid_month_end": str(months[-1]),
        },
        "power_design": {
            "primary_test": "Spearman rho<0 with one-sided within-five-year-block permutation p<=0.05",
            "sandbox_spearman_ceiling": SANDBOX_SPEARMAN,
            "haircuts": list(HAIRCUTS),
            "central_haircut": CENTRAL_HAIRCUT,
            "outer_simulations": OUTER_SIMS,
            "permutations_per_simulation": N_PERMUTATIONS,
            "seed": SEED,
            "power_floor": POWER_FLOOR,
        },
        "power_results": power_results,
        "central_gate": {
            "power": central_power,
            "pass": central_power >= POWER_FLOOR,
        },
        "boundary": (
            "Timestamp-only long-history feasibility/power preflight. No close, return, signal, "
            "or outcome column is read. POWER_PASS authorizes only the next recorded Campaign #57 "
            "historical-confirmation transition, not portfolio/runtime action."
        ),
    }

    (out_dir / "campaign57_long_history_preflight.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if status == "POWER_PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
