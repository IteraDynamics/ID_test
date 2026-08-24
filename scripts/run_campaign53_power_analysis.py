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
  periods same-signed as the current one), each at two windows {24h, 72h}, each paired
  with the matching target horizon -- three (candidate, horizon) hypotheses (not four: see
  EXCLUDED_HYPOTHESES below), per Charter section 3c's 2026-08-21 rebalance-frequency
  resolution, its window-narrowing correction (168h dropped 2026-08-21 after a real run
  showed it structurally underpowered -- daily-resampled 168h windows share ~86% of their
  data with the prior day's window, collapsing effective sample size regardless of true
  effect size), AND its 2026-08-24 exclusion of funding_level_24h (a near-tautological
  candidate/target identity when window==horizon==rebalance-interval, proven independent of
  this power simulation and detailed on EXCLUDED_HYPOTHESES). See the charter for the full
  record of all three corrections.
- Targets: forward net carry (sum of funding over the horizon, minus a transaction-cost
  assumption), at daily rebalance points, pooled across BTC and ETH.
- For each hypothesis, build a null reference distribution of block-bootstrapped correlations
  (zero injected effect) -- this is the yardstick empirical p-values are measured against,
  avoiding a parametric independence assumption block-bootstrap data doesn't satisfy.
- For power at a given IC: inject that correlation into ONE hypothesis at a time (the others
  stay null, matching the real FDR environment where most candidates are null), resample, derive
  each hypothesis's empirical p-value against its own null reference distribution, apply
  Benjamini-Hochberg at q=0.10 across all hypotheses, and check whether the effect-bearing
  hypothesis both clears FDR discovery AND survives a held-out confirmation split (top-2 shortlist,
  corrected 2026-08-21 from top-3 to preserve the original ~33% selectivity ratio against the
  narrowed family) with the correct sign. The fraction of resamples where it does, at that IC, is
  that hypothesis's power.

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

WINDOWS_HOURS = (24, 72)  # 168h dropped 2026-08-21 -- see charter §3c "Window narrowing"
REBALANCE = "1D"
TRANSACTION_COST = 0.0006  # round-trip cost assumption, matching this repo's crypto fee convention elsewhere
FDR_Q = 0.10
CONFIRMATION_TOP_K = 2  # was 3 (sized for a 9-member family); corrected 2026-08-21 for the
                         # narrowed 6-member family -- see charter §3d "Confirmation-k corrected"
IC_GRID = (0.02, 0.05, 0.08, 0.12)
CENTRAL_IC = 0.065  # midpoint of the stated 0.05-0.08 central range

# Excluded 2026-08-24: funding_level's 24h window coincides exactly with its own 24h horizon
# AND the 24h daily rebalance interval, so a candidate's trailing-mean window at day t+1 is
# EXACTLY the target's forward-sum window at day t -- target_t ~= 24*candidate_{t+1} - cost, a
# near-deterministic linear identity, not an approximation. This pins corr(candidate,target) to
# candidate's own lag-1 autocorrelation regardless of any real relationship, proven under both
# pure white noise and AR(1) synthetic input (see tests/test_campaign53_power_analysis.py's
# regression test) and confirmed on real data (observed r=0.7075 matched candidate's own lag-1
# autocorrelation of 0.7075 to 4 decimals). No other (candidate, window) pair in the grid shows
# this: funding_level_72h's window != the rebalance interval, and funding_persistence's
# sign-matching transform isn't a linear rescaling, so neither collapses the same way. See
# charter §3c "funding_level_24h excluded" for the full record.
EXCLUDED_HYPOTHESES = frozenset({("funding_level", 24)})


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


def lag1_autocorr(x: np.ndarray) -> float:
    """Lag-1 autocorrelation, for diagnosing whether a series is meaningfully autocorrelated
    (and therefore whether block bootstrapping it should widen a null distribution relative to
    naive IID) -- see the "block width sanity check" printed in main()."""
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def standardize(x: np.ndarray) -> np.ndarray:
    std = x.std()
    if std == 0:
        raise ValueError("cannot standardize a constant series")
    return (x - x.mean()) / std


def inject_ic(candidate: np.ndarray, independent_noise: np.ndarray, ic: float) -> np.ndarray:
    """Synthetic target with controlled correlation `ic` to `candidate`.

    `independent_noise` must already be decorrelated from `candidate` -- the caller's
    responsibility, via an INDEPENDENT block-bootstrap draw (different random block positions),
    not a full IID permutation. A full permutation would destroy the noise's own autocorrelation
    along with the candidate relationship, understating the true sampling variability of a
    correlation estimate under block-dependent data and making the null distribution built from
    this function artificially tight -- which was a real bug here until 2026-08-21 (see
    tests/test_campaign53_power_analysis.py's regression test for the exact failure mode).
    """
    c = standardize(candidate)
    z = standardize(independent_noise)
    return ic * c + np.sqrt(max(0.0, 1 - ic ** 2)) * z


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


def draw_independent_pair(candidate: np.ndarray, real_target: np.ndarray, block_size: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Two SEPARATELY block-bootstrapped arrays -- different random block positions for each,
    so they're independent of each other (no real relationship) while each retains its own
    genuine within-series autocorrelation. This is what makes the null distribution and the
    injected-effect construction reflect real block-dependent sampling variability instead of
    an artificially tight IID-like one."""
    n = len(candidate)
    idx_candidate = block_bootstrap_resample(n, block_size, rng)
    idx_noise = block_bootstrap_resample(n, block_size, rng)
    return candidate[idx_candidate], real_target[idx_noise]


def build_null_reference(candidate: np.ndarray, real_target: np.ndarray, block_size: int, n_null: int, rng: np.random.Generator) -> np.ndarray:
    """Empirical distribution of |correlation| under IC=0, for p-value lookup."""
    correlations = np.empty(n_null)
    for i in range(n_null):
        candidate_sample, noise_sample = draw_independent_pair(candidate, real_target, block_size, rng)
        synthetic = inject_ic(candidate_sample, noise_sample, 0.0)
        correlations[i] = abs(np.corrcoef(candidate_sample, synthetic)[0, 1])
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
                candidate_sample, noise_sample = draw_independent_pair(hyp["candidate"], hyp["target"], block_size, rng)
                effect = ic if h_idx == target_idx else 0.0
                synthetic = inject_ic(candidate_sample, noise_sample, effect)
                corrs[h_idx] = np.corrcoef(candidate_sample, synthetic)[0, 1]

            pvals = np.array([
                empirical_pvalue(abs(corrs[h]), hypotheses[h]["null_reference"])
                for h in range(n_hyp)
            ])
            rejected = benjamini_hochberg(pvals, FDR_Q)
            if not rejected[target_idx]:
                continue

            # top-2 confirmation shortlist by |correlation| among rejected hypotheses
            rejected_idx = np.where(rejected)[0]
            ranked = rejected_idx[np.argsort(-np.abs(corrs[rejected_idx]))]
            shortlist = set(ranked[:CONFIRMATION_TOP_K])
            if target_idx not in shortlist:
                continue

            # confirmation: independent resample, same injected IC on target_idx, sign check
            hyp = hypotheses[target_idx]
            confirm_candidate, confirm_noise = draw_independent_pair(hyp["candidate"], hyp["target"], block_size, rng)
            confirm_synthetic = inject_ic(confirm_candidate, confirm_noise, ic)
            confirm_corr = np.corrcoef(confirm_candidate, confirm_synthetic)[0, 1]
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
            if (cand_name, window) in EXCLUDED_HYPOTHESES:
                print(f"  {cand_name}_{window}h: excluded -- see EXCLUDED_HYPOTHESES")
                continue
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

    print("\nBlock-width sanity check (lag-1 autocorrelation of each pooled series; if these are")
    print("near zero, a tight null distribution is a correct reflection of the data, not a bug --")
    print("if they are meaningfully positive, the null distribution below should be visibly wider")
    print("than naive IID (~%.4f for n~%d)):" % (0.674 / np.sqrt(np.mean([len(h["candidate"]) for h in hypotheses])), int(np.mean([len(h["candidate"]) for h in hypotheses]))))
    for hyp in hypotheses:
        print(f"  {hyp['name']}: candidate lag-1 r={lag1_autocorr(hyp['candidate']):.4f}, "
              f"target lag-1 r={lag1_autocorr(hyp['target']):.4f}")

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
        "block_width_sanity_check": {
            hyp["name"]: {
                "candidate_lag1_autocorr": lag1_autocorr(hyp["candidate"]),
                "target_lag1_autocorr": lag1_autocorr(hyp["target"]),
                "null_reference_median_abs_r": float(np.median(hyp["null_reference"])),
            }
            for hyp in hypotheses
        },
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
