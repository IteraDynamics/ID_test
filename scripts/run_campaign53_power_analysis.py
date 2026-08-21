"""Campaign #53 Amendment 1 power analysis — statistical family (funding level, funding
persistence), against real acquired Deribit data.

Authorized 2026-08-21 (docs/ITERA_CAMPAIGN_BOARD.md correction): this is Amendment 1's required
methodology calibration -- bootstrap real data, inject a hypothetical effect, measure whether the
frozen gates (FDR q=0.10, top-3 confirmation) would detect it -- not real predictor/outcome
computation for an actual decision. It produces a power percentage, not a candidate ranking or a
trading signal.

Two things this script is honest about rather than glossing over, per the charter's own
2026-08-21 corrections:

1. The effect-size grid (IC = 0.02/0.05/0.08/0.12) is a reasoned estimate, not literature-cited
   -- this environment has no live internet access to pull real published carry-strategy figures.
   Replace with real citations before treating any result here as final.
2. Real CDE confirmation data does not exist yet (only Deribit discovery data does). This
   approximates confirmation with a held-out chronological split of the SAME Deribit series --
   not genuine cross-venue confirmation. Every report this script writes says so explicitly.

Method (non-parametric, bootstrap-based, no distributional assumptions):

- Candidates: funding level (trailing mean) and funding persistence (fraction of trailing
  periods same-signed as the current one), each at three windows {24h, 72h, 168h}, each paired
  with the matching target horizon -- six (candidate, horizon) hypotheses total, per
  Charter section 3c's 2026-08-21 rebalance-frequency resolution.
- Targets: forward net carry (sum of funding over the horizon, minus a transaction-cost
  assumption), at daily rebalance points, pooled across BTC and ETH.
- For each hypothesis, build a null reference distribution of block-bootstrapped correlations
  (zero injected effect) -- this is the yardstick empirical p-values are measured against,
  avoiding a parametric independence assumption block-bootstrap data doesn't satisfy.
- For power at a given IC: inject that correlation into ONE hypothesis at a time (the other five
  stay null, matching the real FDR environment where most candidates are null), resample, derive
  each hypothesis's empirical p-value against its own null reference distribution, apply
  Benjamini-Hochberg at q=0.10 across all six, and check whether the effect-bearing hypothesis
  both clears FDR discovery AND survives a held-out confirmation split with the correct sign.
  The fraction of resamples where it does, at that IC, is that hypothesis's power.

Observation/simulation only. Reads acquired data; computes no real candidate ranking, makes no
economic claim, and produces no trading signal.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

WINDOWS_HOURS = (24, 72, 168)
REBALANCE = "1D"
TRANSACTION_COST = 0.0006  # round-trip cost assumption, matching this repo's crypto fee convention elsewhere
FDR_Q = 0.10
CONFIRMATION_TOP_K = 3
IC_GRID = (0.02, 0.05, 0.08, 0.12)
CENTRAL_IC = 0.065  # midpoint of the stated 0.05-0.08 central range


# ------------------------------------------------------- data loading and candidate construction


def load_funding_series(path: str | Path) -> pd.Series:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    series = df["funding_rate_8h"].astype(float)
    series.index = pd.DatetimeIndex(series.index).tz_localize(None) if series.index.tz is None else series.index.tz_convert(None)
    return series


def hourly_reindex(series: pd.Series) -> pd.Series:
    """Fill to a regular hourly grid (ffill across any small real gaps) so trailing-window
    arithmetic is well-defined; does not fabricate values beyond the series' own observed range."""
    full_index = pd.date_range(series.index.min(), series.index.max(), freq="1h")
    return series.reindex(full_index).ffill()


def funding_level(hourly: pd.Series, window_hours: int) -> pd.Series:
    return hourly.rolling(window_hours, min_periods=window_hours).mean()


def funding_persistence(hourly: pd.Series, window_hours: int) -> pd.Series:
    sign = np.sign(hourly)
    current_sign = sign
    same_sign = (sign.rolling(window_hours, min_periods=window_hours)
                 .apply(lambda w: np.mean(w == w[-1]), raw=True))
    return same_sign


def forward_net_carry(hourly: pd.Series, horizon_hours: int, cost: float) -> pd.Series:
    """Forward sum of funding over the horizon starting the NEXT hour (not including the
    current one, matching the frozen research path's own no-lookahead convention), minus cost."""
    forward_sum = hourly.shift(-1).rolling(horizon_hours, min_periods=horizon_hours).sum().shift(-(horizon_hours - 1))
    return forward_sum - cost


def build_hypothesis_frame(hourly: pd.Series, candidate_fn, window_hours: int, rebalance: str) -> pd.DataFrame:
    candidate = candidate_fn(hourly, window_hours)
    target = forward_net_carry(hourly, window_hours, TRANSACTION_COST)
    frame = pd.DataFrame({"candidate": candidate, "target": target}).dropna()
    rebalanced = frame.resample(rebalance).first().dropna()
    return rebalanced


# ------------------------------------------------------- block bootstrap and effect injection


def block_bootstrap_resample(n: int, block_size: int, rng: np.random.Generator) -> np.ndarray:
    if block_size < 1 or block_size > n:
        raise ValueError(f"block_size must be in [1, {n}], got {block_size}")
    indices: list[np.ndarray] = []
    total = 0
    while total < n:
        start = int(rng.integers(0, n - block_size + 1))
        block = np.arange(start, start + block_size)
        indices.append(block)
        total += block_size
    return np.concatenate(indices)[:n]


def standardize(x: np.ndarray) -> np.ndarray:
    std = x.std()
    if std == 0:
        raise ValueError("cannot standardize a constant series")
    return (x - x.mean()) / std


def inject_ic(candidate: np.ndarray, real_target: np.ndarray, ic: float, rng: np.random.Generator) -> np.ndarray:
    """Synthetic target with controlled correlation `ic` to `candidate`, built from real target
    noise (block-bootstrapped separately from candidate to destroy any real relationship first)
    so the injected effect is the ONLY relationship present, at a known strength."""
    n = len(candidate)
    shuffled_noise = real_target[rng.permutation(n)]  # destroys real candidate-target relationship
    c = standardize(candidate)
    z = standardize(shuffled_noise)
    synthetic = ic * c + np.sqrt(max(0.0, 1 - ic ** 2)) * z
    return synthetic


# ------------------------------------------------------- FDR


def benjamini_hochberg(pvalues: np.ndarray, q: float) -> np.ndarray:
    """Returns a boolean array of which hypotheses are rejected (declared significant) at FDR q."""
    n = len(pvalues)
    order = np.argsort(pvalues)
    sorted_p = pvalues[order]
    thresholds = (np.arange(1, n + 1) / n) * q
    passing = sorted_p <= thresholds
    if not passing.any():
        return np.zeros(n, dtype=bool)
    max_i = np.max(np.where(passing)[0])
    reject_sorted = np.zeros(n, dtype=bool)
    reject_sorted[: max_i + 1] = True
    reject = np.zeros(n, dtype=bool)
    reject[order] = reject_sorted
    return reject


# ------------------------------------------------------- power simulation


def build_null_reference(candidate: np.ndarray, real_target: np.ndarray, block_size: int, n_null: int, rng: np.random.Generator) -> np.ndarray:
    """Empirical distribution of |correlation| under IC=0, for p-value lookup."""
    n = len(candidate)
    correlations = np.empty(n_null)
    for i in range(n_null):
        idx = block_bootstrap_resample(n, block_size, rng)
        synthetic = inject_ic(candidate[idx], real_target[idx], 0.0, rng)
        correlations[i] = abs(np.corrcoef(candidate[idx], synthetic)[0, 1])
    return correlations


def empirical_pvalue(observed_abs_corr: float, null_reference: np.ndarray) -> float:
    return float((null_reference >= observed_abs_corr).mean())


def simulate_power_for_ic(
    hypotheses: list[dict[str, Any]],
    ic: float,
    n_resamples: int,
    block_size: int,
    rng: np.random.Generator,
) -> dict[str, float]:
    """One `hypotheses[i]` gets the true injected IC per resample, in turn; the rest stay null.
    Returns {hypothesis_name: power_fraction}."""
    n_hyp = len(hypotheses)
    wins = np.zeros(n_hyp)

    for target_idx in range(n_hyp):
        for _ in range(n_resamples):
            corrs = np.empty(n_hyp)
            for h_idx, hyp in enumerate(hypotheses):
                candidate = hyp["candidate"]
                real_target = hyp["target"]
                n = len(candidate)
                idx = block_bootstrap_resample(n, block_size, rng)
                effect = ic if h_idx == target_idx else 0.0
                synthetic = inject_ic(candidate[idx], real_target[idx], effect, rng)
                corrs[h_idx] = np.corrcoef(candidate[idx], synthetic)[0, 1]

            pvals = np.array([
                empirical_pvalue(abs(corrs[h]), hypotheses[h]["null_reference"])
                for h in range(n_hyp)
            ])
            rejected = benjamini_hochberg(pvals, FDR_Q)
            if not rejected[target_idx]:
                continue

            # top-3 confirmation shortlist by |correlation| among rejected hypotheses
            rejected_idx = np.where(rejected)[0]
            ranked = rejected_idx[np.argsort(-np.abs(corrs[rejected_idx]))]
            shortlist = set(ranked[:CONFIRMATION_TOP_K])
            if target_idx not in shortlist:
                continue

            # confirmation: independent resample, same injected IC on target_idx, sign check
            hyp = hypotheses[target_idx]
            candidate = hyp["candidate"]
            real_target = hyp["target"]
            n = len(candidate)
            confirm_idx = block_bootstrap_resample(n, block_size, rng)
            confirm_synthetic = inject_ic(candidate[confirm_idx], real_target[confirm_idx], ic, rng)
            confirm_corr = np.corrcoef(candidate[confirm_idx], confirm_synthetic)[0, 1]
            if np.sign(confirm_corr) == np.sign(ic) and abs(confirm_corr) > 0:
                wins[target_idx] += 1

    return {hypotheses[i]["name"]: wins[i] / n_resamples for i in range(n_hyp)}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--btc-funding-csv", required=True)
    p.add_argument("--eth-funding-csv", required=True)
    p.add_argument("--n-null", type=int, default=300, help="Null reference resamples per hypothesis.")
    p.add_argument("--n-power", type=int, default=150, help="Power resamples per (hypothesis, IC grid point).")
    p.add_argument("--block-days", type=int, default=30, help="Block bootstrap block size, in rebalance periods (days).")
    p.add_argument("--seed", type=int, default=20260821)
    p.add_argument("--out-dir", default="artifacts/campaign53_power_analysis")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rng = np.random.default_rng(args.seed)

    print("Loading and pooling BTC/ETH funding series...")
    btc = hourly_reindex(load_funding_series(args.btc_funding_csv))
    eth = hourly_reindex(load_funding_series(args.eth_funding_csv))

    candidate_fns = {"funding_level": funding_level, "funding_persistence": funding_persistence}
    hypotheses: list[dict[str, Any]] = []
    for cand_name, cand_fn in candidate_fns.items():
        for window in WINDOWS_HOURS:
            btc_frame = build_hypothesis_frame(btc, cand_fn, window, REBALANCE)
            eth_frame = build_hypothesis_frame(eth, cand_fn, window, REBALANCE)
            pooled = pd.concat([btc_frame, eth_frame], ignore_index=True)
            name = f"{cand_name}_{window}h"
            print(f"  {name}: {len(pooled)} pooled (candidate, target) observations")
            hypotheses.append({
                "name": name,
                "candidate": pooled["candidate"].to_numpy(),
                "target": pooled["target"].to_numpy(),
            })

    block_size = min(args.block_days, min(len(h["candidate"]) for h in hypotheses) - 1)
    print(f"\nBuilding null reference distributions ({args.n_null} resamples each, block size {block_size})...")
    for hyp in hypotheses:
        hyp["null_reference"] = build_null_reference(hyp["candidate"], hyp["target"], block_size, args.n_null, rng)
        print(f"  {hyp['name']}: null |r| median={np.median(hyp['null_reference']):.4f}")

    results: dict[float, dict[str, float]] = {}
    for ic in IC_GRID:
        print(f"\nSimulating power at IC={ic} ({args.n_power} resamples per hypothesis)...")
        results[ic] = simulate_power_for_ic(hypotheses, ic, args.n_power, block_size, rng)
        for name, power in results[ic].items():
            print(f"  {name}: power={power:.3f}")

    central_power = {}
    if CENTRAL_IC in IC_GRID:
        central_power = results[CENTRAL_IC]
    else:
        print(f"\nCentral IC {CENTRAL_IC} not in grid {IC_GRID}; interpolating from nearest grid points for the headline figure.")
        lower = max(g for g in IC_GRID if g <= CENTRAL_IC)
        upper = min(g for g in IC_GRID if g >= CENTRAL_IC)
        if lower == upper:
            central_power = results[lower]
        else:
            frac = (CENTRAL_IC - lower) / (upper - lower)
            central_power = {
                name: results[lower][name] + frac * (results[upper][name] - results[lower][name])
                for name in results[lower]
            }

    avg_central_power = float(np.mean(list(central_power.values())))

    report = {
        "audit": "campaign53_power_analysis_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "caveats": [
            "Effect-size grid is a reasoned estimate, not literature-cited (no live internet access).",
            "Confirmation is approximated with a held-out resample of the SAME Deribit series, not real CDE data.",
        ],
        "ic_grid": list(IC_GRID),
        "central_ic": CENTRAL_IC,
        "rebalance": REBALANCE,
        "block_size_days": block_size,
        "fdr_q": FDR_Q,
        "confirmation_top_k": CONFIRMATION_TOP_K,
        "power_by_ic": {str(ic): res for ic, res in results.items()},
        "power_at_central_ic": central_power,
        "average_power_at_central_ic": avg_central_power,
        "passes_50pct_threshold": avg_central_power >= 0.50,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"power_analysis_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"\n=== Average power at central IC ({CENTRAL_IC}): {avg_central_power:.3f} ===")
    print(f"50% threshold: {'PASS' if avg_central_power >= 0.50 else 'FAIL'}")
    print(f"\nArtifacts: {out_path}")
    print("\nReminder: effect-size grid is uncited, and confirmation is simulated against a split")
    print("of Deribit data, not real CDE data. Treat this as a first-pass estimate, not final.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
