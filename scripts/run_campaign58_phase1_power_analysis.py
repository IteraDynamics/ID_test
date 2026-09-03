"""Campaign #58 Phase 1 (time-series residual census) power analysis — BTC-only proxy, against
real acquired data already committed to this repo.

Authorized 2026-09-03 (CEO authorization, docs/ITERA_CAMPAIGN_BOARD.md correction of that date):
this is the pre-execution power/specification-freeze work the charter's Red Team conditions 1
and 2 require -- bootstrap real data, inject a hypothetical effect, measure whether the frozen
gates would detect it -- not real predictor/outcome computation for an actual Campaign #58
decision. It produces a power percentage against a proxy family, not a candidate ranking, not a
residual-predictability result, and not a trading signal.

Methodology is deliberately the same block-bootstrap, empirical-null, inject_ic approach already
governed for Campaign #53 (`scripts/run_campaign53_power_analysis.py`) -- reused, not reinvented,
per this fund's own convention of not re-deriving a already-proven-sound method from scratch.

DATA HONESTY, stated up front rather than glossed over:

This session's environment has no outbound network access (verified: cftc.gov, deribit.com, and
even generic internet hosts all return a proxy-level 403 CONNECT rejection -- organization
policy, not a transient failure) and this repo's `data/` directory, per its own governed
convention (CLAUDE.md: "Data lives locally on the operator's machines... data/*.csv is
gitignored"), holds only a partial 2026 BTC file, not the multi-year BTC/ETH/SPY/QQQ/GLD history
Campaign #58's time-series track needs.

The ONE piece of real, already-committed, already-governed multi-year data available in this
session is Campaign #48's own canonical anchor inventory
(`artifacts/simple_btc_price_state_predictive_baselines/price_state_anchor_inventory.csv`) --
403 real anchors, 2018-01-08 through 2025-12-?? (168h spacing), 8 real BTC-derived predictor
columns, replay-verified when originally produced. This script uses those real columns as the
power simulation's "candidate" and "target-like" series. It is BTC-ONLY: no ETH, SPY, QQQ, or
GLD data is available in this session, so this result cannot speak to the full BTC/ETH/SPY/QQQ/
GLD scope Campaign #58's charter proposed for Phase 1 -- it is a proxy lower/upper bound on the
BTC leg only, exactly the kind of proxy caveat CLAUDE.md's own cadence-measurement entries
already carry for BTC vs ETH. A future session with real multi-year ETH/SPY/QQQ/GLD access must
re-run this before Phase 1's specification can be considered complete across its full scope.

The "target-like" series is one of Campaign #48's own real predictor columns (see
PROXY_TARGET_COLUMN below), NOT a literal forward-return outcome -- the committed CSV holds
fitted regression summary statistics, not raw per-anchor outcome values, so no real outcome
series exists in this session to inject an effect into. Using a second real predictor column
preserves a genuinely real marginal distribution and autocorrelation structure (unlike a
synthetic draw), which is what the block-bootstrap method needs to be honest about block width --
but it is a stand-in for realistic serial-dependence calibration, not a claim about any specific
real candidate-target relationship. This is stated in the output artifact, not just here.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

FDR_Q = 0.10
CONFIRMATION_TOP_K = 2  # mirrors Campaign #53's ~33% selectivity ratio, restated for a
                         # differently-sized family below (see main())
IC_GRID = (0.02, 0.05, 0.08, 0.12)
CENTRAL_IC = 0.065  # same central assumption as Campaign #53, for comparability across tracks

CANDIDATE_COLUMNS = (
    "return_trailing_24h",
    "return_trailing_72h",
    "return_trailing_168h",
    "realized_volatility_trailing_24h",
    "realized_volatility_trailing_168h",
    "distance_from_mean_trailing_168h",
    "range_position_trailing_168h",
    "drawdown_from_high_trailing_168h",
)
# The strongest, most autocorrelated real family in Campaign #48's own results (all 15 of its
# supported associations were magnitude/volatility, none directional) -- a conservative choice
# for the null/injection "target-like" stand-in, since it is the real column most likely to
# understate rather than overstate how tight a null distribution should be.
PROXY_TARGET_COLUMN = "realized_volatility_trailing_24h"


# ------------------------------------------------------- block bootstrap and effect injection
# (identical to scripts/run_campaign53_power_analysis.py -- reused verbatim, not reimplemented,
# so any future audit of one audits both)


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
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def standardize(x: np.ndarray) -> np.ndarray:
    std = x.std()
    if std == 0:
        raise ValueError("cannot standardize a constant series")
    return (x - x.mean()) / std


def inject_ic(candidate: np.ndarray, independent_noise: np.ndarray, ic: float) -> np.ndarray:
    c = standardize(candidate)
    z = standardize(independent_noise)
    return ic * c + np.sqrt(max(0.0, 1 - ic ** 2)) * z


def benjamini_hochberg(pvalues: np.ndarray, q: float) -> np.ndarray:
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


def draw_independent_pair(candidate: np.ndarray, real_target: np.ndarray, block_size: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    n = len(candidate)
    idx_candidate = block_bootstrap_resample(n, block_size, rng)
    idx_noise = block_bootstrap_resample(n, block_size, rng)
    return candidate[idx_candidate], real_target[idx_noise]


def build_null_reference(candidate: np.ndarray, real_target: np.ndarray, block_size: int, n_null: int, rng: np.random.Generator) -> np.ndarray:
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

            rejected_idx = np.where(rejected)[0]
            ranked = rejected_idx[np.argsort(-np.abs(corrs[rejected_idx]))]
            shortlist = set(ranked[:CONFIRMATION_TOP_K])
            if target_idx not in shortlist:
                continue

            hyp = hypotheses[target_idx]
            confirm_candidate, confirm_noise = draw_independent_pair(hyp["candidate"], hyp["target"], block_size, rng)
            confirm_synthetic = inject_ic(confirm_candidate, confirm_noise, ic)
            confirm_corr = np.corrcoef(confirm_candidate, confirm_synthetic)[0, 1]
            if np.sign(confirm_corr) == np.sign(ic) and abs(confirm_corr) > 0:
                wins[target_idx] += 1

    return {hypotheses[i]["name"]: wins[i] / n_resamples for i in range(n_hyp)}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--anchor-csv", default="artifacts/simple_btc_price_state_predictive_baselines/price_state_anchor_inventory.csv")
    p.add_argument("--n-null", type=int, default=300)
    p.add_argument("--n-power", type=int, default=150)
    p.add_argument("--block-anchors", type=int, default=8, help="Block bootstrap block size, in 168h anchors (~8 anchors ~= 56 days).")
    p.add_argument("--seed", type=int, default=20260903)
    p.add_argument("--out-dir", default="artifacts/campaign58_phase1_power_analysis")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rng = np.random.default_rng(args.seed)

    anchor_path = Path(args.anchor_csv)
    if not anchor_path.exists():
        print(f"FATAL: {anchor_path} not found -- this script requires Campaign #48's committed "
              f"canonical anchor inventory, which is the only real multi-year Itera market data "
              f"available in this session.")
        return 1

    df = pd.read_csv(anchor_path)
    print(f"Loaded {len(df)} real anchors from {anchor_path} (Campaign #48 canonical artifact).")

    target = df[PROXY_TARGET_COLUMN].to_numpy(dtype=float)
    hypotheses: list[dict[str, Any]] = []
    for col in CANDIDATE_COLUMNS:
        if col == PROXY_TARGET_COLUMN:
            continue  # a column cannot proxy-target itself
        candidate = df[col].to_numpy(dtype=float)
        hypotheses.append({"name": col, "candidate": candidate, "target": target})

    print(f"\nProxy-target column: {PROXY_TARGET_COLUMN} (a real Campaign #48 predictor column, "
          f"stand-in for realistic marginal/autocorrelation structure -- NOT a literal forward "
          f"outcome; see module docstring).")
    print(f"{len(hypotheses)} candidate hypotheses (one BTC-only price-state family, real data).")

    print("\nBlock-width sanity check (lag-1 autocorrelation; anchors are already 168h-spaced, so")
    print("substantial residual autocorrelation here would mean even 168h spacing under-spaces")
    print("this family):")
    for hyp in hypotheses:
        print(f"  {hyp['name']}: candidate lag-1 r={lag1_autocorr(hyp['candidate']):.4f}")
    print(f"  {PROXY_TARGET_COLUMN} (proxy target): lag-1 r={lag1_autocorr(target):.4f}")

    block_size = min(args.block_anchors, len(df) - 1)
    print(f"\nBuilding null reference distributions ({args.n_null} resamples each, block size "
          f"{block_size} anchors)...")
    for hyp in hypotheses:
        hyp["null_reference"] = build_null_reference(hyp["candidate"], hyp["target"], block_size, args.n_null, rng)
        print(f"  {hyp['name']}: null |r| median={np.median(hyp['null_reference']):.4f}")

    results: dict[float, dict[str, float]] = {}
    for ic in IC_GRID:
        print(f"\nSimulating power at IC={ic} ({args.n_power} resamples per hypothesis)...")
        results[ic] = simulate_power_for_ic(hypotheses, ic, args.n_power, block_size, rng)
        for name, power in results[ic].items():
            print(f"  {name}: power={power:.3f}")

    central_power = results.get(CENTRAL_IC)
    if central_power is None:
        lower = max(g for g in IC_GRID if g <= CENTRAL_IC)
        upper = min(g for g in IC_GRID if g >= CENTRAL_IC)
        frac = (CENTRAL_IC - lower) / (upper - lower) if upper != lower else 0.0
        central_power = {
            name: results[lower][name] + frac * (results[upper][name] - results[lower][name])
            for name in results[lower]
        }

    avg_central_power = float(np.mean(list(central_power.values())))

    report = {
        "audit": "campaign58_phase1_power_analysis_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_honesty": [
            "This session has no outbound network access (verified 403 at the proxy level for "
            "cftc.gov, deribit.com, and generic internet hosts) and no committed multi-year "
            "ETH/SPY/QQQ/GLD history.",
            "This result uses ONLY Campaign #48's real, committed, already-governed BTC anchor "
            "inventory (403 anchors, 2018-2025, 168h spacing) -- BTC-only, a proxy for the full "
            "BTC/ETH/SPY/QQQ/GLD scope Campaign #58's charter proposed for Phase 1.",
            f"The 'target' series used to calibrate realistic null/injection structure is the "
            f"real column '{PROXY_TARGET_COLUMN}', not a literal forward-return outcome -- no "
            f"raw outcome series exists in this session's committed data.",
            "A future session with real multi-year ETH/SPY/QQQ/GLD access must re-run this "
            "before Phase 1's specification is considered complete across its full proposed "
            "scope. This result bounds the BTC leg only.",
        ],
        "source_artifact": str(anchor_path),
        "n_anchors": len(df),
        "proxy_target_column": PROXY_TARGET_COLUMN,
        "ic_grid": list(IC_GRID),
        "central_ic": CENTRAL_IC,
        "block_size_anchors": block_size,
        "fdr_q": FDR_Q,
        "confirmation_top_k": CONFIRMATION_TOP_K,
        "lag1_autocorr": {
            **{hyp["name"]: lag1_autocorr(hyp["candidate"]) for hyp in hypotheses},
            f"{PROXY_TARGET_COLUMN}__proxy_target": lag1_autocorr(target),
        },
        "null_reference_median_abs_r": {hyp["name"]: float(np.median(hyp["null_reference"])) for hyp in hypotheses},
        "power_by_ic": {str(ic): res for ic, res in results.items()},
        "power_at_central_ic": central_power,
        "average_power_at_central_ic": avg_central_power,
        "passes_50pct_threshold": avg_central_power >= 0.50,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"phase1_power_analysis_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"\n=== Average power at central IC ({CENTRAL_IC}): {avg_central_power:.3f} ===")
    print(f"50% threshold: {'PASS' if avg_central_power >= 0.50 else 'FAIL'}")
    print(f"\nArtifact: {out_path}")
    print("\nBTC-ONLY PROXY -- see 'data_honesty' in the artifact before treating this as final.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
