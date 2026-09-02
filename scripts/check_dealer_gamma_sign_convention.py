"""Supplemental pre-registered sign-convention falsification for dealer-gamma sandbox screen.

Consumes the panel written by scripts/screen_dealer_gamma_pressure.py. It does not alter the
primary screen classification. It asks whether simply reversing the call/put sign convention
would produce the same theoretically expected continuation ordering.

For the primary convention, low signed GEX is hypothesized to have greater continuation than
high signed GEX. Reversing call/put signs swaps low/high states. Therefore a robust primary-sign
story should NOT also show positive low-minus-high continuation under the reversed convention.

Research-only; no runtime/portfolio writes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


HORIZONS = (1, 2, 5)
N_PERMUTATIONS = 500
SEED = 20260902


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panel", default="artifacts/dealer_gamma_pressure_screen/dealer_gamma_pressure_panel.csv")
    p.add_argument("--output", default="artifacts/dealer_gamma_pressure_screen/dealer_gamma_sign_convention_check.json")
    p.add_argument("--permutations", type=int, default=N_PERMUTATIONS)
    p.add_argument("--seed", type=int, default=SEED)
    return p.parse_args()


def perm_p(frame: pd.DataFrame, metric: str, observed: float, n_perm: int, rng: np.random.Generator) -> float:
    data = frame[["usable_date", "reverse_signed_state", metric]].dropna().copy()
    data = data[data["reverse_signed_state"].isin({"low", "high"})]
    labels = data["reverse_signed_state"].to_numpy(copy=True)
    years = pd.to_datetime(data["usable_date"]).dt.year.to_numpy()
    values = pd.to_numeric(data[metric], errors="coerce").to_numpy(dtype=float)
    null = np.empty(n_perm, dtype=float)
    for b in range(n_perm):
        shuffled = labels.copy()
        for year in np.unique(years):
            idx = np.flatnonzero(years == year)
            shuffled[idx] = rng.permutation(shuffled[idx])
        null[b] = values[shuffled == "low"].mean() - values[shuffled == "high"].mean()
    return float((1 + np.sum(null >= observed)) / (n_perm + 1))


def main() -> int:
    args = parse_args()
    path = Path(args.panel)
    if not path.exists():
        raise SystemExit(f"PANEL_MISSING:{path}")
    frame = pd.read_csv(path)
    required = {"usable_date", "signed_state"} | {f"continuation_{h}d" for h in HORIZONS}
    missing = required - set(frame.columns)
    if missing:
        raise SystemExit(f"PANEL_MISSING_COLUMNS:{sorted(missing)}")

    # Reversing the sign convention exactly swaps the extreme state labels.
    frame["reverse_signed_state"] = frame["signed_state"].map({"low": "high", "high": "low", "mid": "mid"}).fillna("")
    rng = np.random.default_rng(args.seed)
    results = []
    for h in HORIZONS:
        metric = f"continuation_{h}d"
        low = pd.to_numeric(frame.loc[frame["reverse_signed_state"] == "low", metric], errors="coerce").dropna()
        high = pd.to_numeric(frame.loc[frame["reverse_signed_state"] == "high", metric], errors="coerce").dropna()
        observed = float(low.mean() - high.mean()) if not low.empty and not high.empty else np.nan
        p = perm_p(frame, metric, observed, args.permutations, rng) if np.isfinite(observed) else np.nan
        results.append({
            "horizon_days": h,
            "reverse_low_minus_high_continuation": None if not np.isfinite(observed) else observed,
            "permutation_p_one_sided": None if not np.isfinite(p) else p,
            "n_low": int(len(low)),
            "n_high": int(len(high)),
        })

    contradictory = [r for r in results if r["reverse_low_minus_high_continuation"] is not None and r["reverse_low_minus_high_continuation"] > 0 and r["permutation_p_one_sided"] is not None and r["permutation_p_one_sided"] <= 0.05]
    report = {
        "status": "CONTRADICTS_PRIMARY_SIGN_STORY" if contradictory else "DOES_NOT_CONTRADICT_PRIMARY_SIGN_STORY",
        "convention": "reverse of primary: calls -gamma*OI; puts +gamma*OI",
        "results": results,
        "boundary": "Supplemental sandbox falsification only; does not independently promote or validate the candidate.",
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
