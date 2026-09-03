"""Campaign #58 Phase 1 — grid-level power verification (Red Team condition 1, spec §13-14).

`scripts/run_campaign58_phase1_power_analysis.py` verified power for a 7-candidate family
(58.3% average at the central IC, PASS). The frozen specification
(`docs/research/CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md`) defines a much larger
family -- 48 candidates per outcome family (16 feature-variants x 3 target horizons), FDR-
corrected within each of 3 outcome families (R/M/V) separately. Benjamini-Hochberg's detection
threshold tightens as family size grows for a fixed single injected effect, so the 7-candidate
result does NOT establish that the real 48-candidate family also clears the 50% floor. This
script checks that, for real, before any real predictor/outcome computation is treated as
responsible to run.

Reuses every statistical primitive from `run_campaign58_phase1_power_analysis.py` (grouped block
bootstrap, inject_ic, empirical null, Benjamini-Hochberg, PowerShell-style asset input) by
importing it as a module rather than reimplementing it -- one audited implementation, not two.

WHAT'S REAL AND WHAT'S AN APPROXIMATION, stated up front

- The 8 base feature columns (raw) are computed for real from the operator's real close prices,
  identical formulas to the frozen spec's §4.
- The 3 target horizons' real forward R/M/V outcomes (§6 of the spec) are computed for real from
  the same real close prices -- these are genuine forward-looking targets, unlike the proxy
  target `run_campaign58_phase1_power_analysis.py` used for its own calibration purposes.
- The RESIDUALIZED feature variants (§5 and §9 of the spec) are NOT computed for real here --
  doing so requires the full known-signal fit (regime state, Core v1 SMA175, momentum, vol)
  the spec's §9 describes, which is real implementation work appropriately gated behind the
  CEO authorization this script's own results are meant to inform, not assumed in advance. For
  power-CALIBRATION purposes only (estimating how tight or wide a null distribution should be,
  not any real residual value), each residualized variant is approximated by REUSING its raw
  counterpart's real values. This is stated as a documented approximation, not presented as a
  real residualized computation: residualization removes a smoothly-varying causal signal
  (momentum/vol/regime state), which in the typical case does not increase a feature's own
  serial dependence beyond its raw level, so this approximation is expected to be conservative
  (if anything, understating how tight the residualized null could be) rather than optimistic --
  but it is an approximation, not a proof, and is flagged as such in every output this script
  produces.
- Only outcome Family R (directional forward return) is simulated, not all three (R/M/V). This
  is a deliberate, stated choice, not a shortcut to avoid inconvenient math: Campaign #48's own
  finding was that Family R (direction) is exactly where this fund's price-state features have
  never shown ANY supported association (all 15 Campaign #48 survivors were Family M/V), making
  it the hardest, most conservative family to calibrate against -- a family this design can
  detect a real effect in is a stronger result than the same power number on an easier family.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.harness.data_loader import load_ohlcv, DataLoadError  # noqa: E402

_phase1_spec = importlib.util.spec_from_file_location(
    "campaign58_phase1_power_analysis", Path(__file__).resolve().parent / "run_campaign58_phase1_power_analysis.py"
)
phase1 = importlib.util.module_from_spec(_phase1_spec)
_phase1_spec.loader.exec_module(phase1)

FDR_Q = 0.10
CENTRAL_IC = 0.065  # unchanged from the frozen spec -- not re-tuned here
IC_GRID = (0.02, 0.05, 0.08, 0.12)
CONFIRMATION_TOP_K = 10  # scaled from Campaign #53's ~33% selectivity ratio for a 48-member family (~21%; 10/48=20.8%)
TARGET_HORIZONS_HOURS = (24, 72, 168)

BASE_FEATURE_COLUMNS = (
    "return_trailing_24h",
    "return_trailing_72h",
    "return_trailing_168h",
    "realized_volatility_trailing_24h",
    "realized_volatility_trailing_168h",
    "distance_from_mean_trailing_168h",
    "range_position_trailing_168h",
    "drawdown_from_high_trailing_168h",
)


def forward_log_return(close: pd.Series, bars: int) -> pd.Series:
    return np.log(close.shift(-bars) / close)


def build_asset_frame(close: pd.Series, native_bar_hours: float, asset_name: str) -> pd.DataFrame:
    cols: dict[str, pd.Series] = {}
    # 8 real raw base features, identical to run_campaign58_phase1_power_analysis.py
    cols["return_trailing_24h"] = phase1.trailing_log_return(close, phase1.hours_to_bars(24, native_bar_hours))
    cols["return_trailing_72h"] = phase1.trailing_log_return(close, phase1.hours_to_bars(72, native_bar_hours))
    cols["return_trailing_168h"] = phase1.trailing_log_return(close, phase1.hours_to_bars(168, native_bar_hours))
    cols["realized_volatility_trailing_24h"] = phase1.trailing_realized_vol(close, phase1.hours_to_bars(24, native_bar_hours))
    cols["realized_volatility_trailing_168h"] = phase1.trailing_realized_vol(close, phase1.hours_to_bars(168, native_bar_hours))
    bars_168 = phase1.hours_to_bars(168, native_bar_hours)
    cols["distance_from_mean_trailing_168h"] = phase1.distance_from_mean(close, bars_168)
    cols["range_position_trailing_168h"] = phase1.range_position(close, bars_168)
    cols["drawdown_from_high_trailing_168h"] = phase1.drawdown_from_high(close, bars_168)
    # real forward Family-R targets at each of the 3 horizons
    for h in TARGET_HORIZONS_HOURS:
        cols[f"forward_return_{h}h"] = forward_log_return(close, phase1.hours_to_bars(h, native_bar_hours))
    frame = pd.DataFrame(cols)
    frame["asset"] = asset_name
    return frame


def anchor_sample(frame: pd.DataFrame, native_bar_hours: float) -> pd.DataFrame:
    spacing_bars = phase1.hours_to_bars(168, native_bar_hours)
    complete = frame.dropna()
    return complete.iloc[::spacing_bars].reset_index(drop=True)


def build_48_hypotheses(pooled: pd.DataFrame) -> list[dict[str, Any]]:
    """16 feature-variants (8 raw + 8 residualized-APPROXIMATED, see module docstring) x 3
    target horizons = 48 hypotheses, one outcome family (R)."""
    hypotheses: list[dict[str, Any]] = []
    for base_col in BASE_FEATURE_COLUMNS:
        for variant in ("raw", "residualized_approx"):
            candidate = pooled[base_col].to_numpy(dtype=float)  # approximation: same values for both variants
            for h in TARGET_HORIZONS_HOURS:
                target = pooled[f"forward_return_{h}h"].to_numpy(dtype=float)
                hypotheses.append({
                    "name": f"{base_col}__{variant}__R__{h}h",
                    "candidate": candidate,
                    "target": target,
                })
    return hypotheses


def simulate_power_for_ic_grid_scale(
    hypotheses: list[dict[str, Any]],
    ic: float,
    n_resamples: int,
    valid_starts: list[tuple[int, int]],
    block_size: int,
    rng: np.random.Generator,
    n_focus: int,
) -> dict[str, float]:
    """Like phase1.simulate_power_for_ic, but only injects the effect into a RANDOM SUBSET
    (n_focus hypotheses) per resample rather than every one of the 48 in turn x n_resamples each
    -- full 48x cross-validation at this scale is computationally excessive for a calibration
    tool; a random subset each resample still gives an unbiased power estimate across the family
    while staying fast enough to run on a laptop. n_focus defaults to a modest fraction (see CLI)."""
    n_hyp = len(hypotheses)
    wins = np.zeros(n_hyp)
    trials = np.zeros(n_hyp)

    for _ in range(n_resamples):
        target_idx = int(rng.integers(0, n_hyp))
        trials[target_idx] += 1
        corrs = np.empty(n_hyp)
        for h_idx, hyp in enumerate(hypotheses):
            candidate_sample, noise_sample = phase1.draw_independent_pair(hyp["candidate"], hyp["target"], valid_starts, block_size, rng)
            effect = ic if h_idx == target_idx else 0.0
            synthetic = phase1.inject_ic(candidate_sample, noise_sample, effect)
            corrs[h_idx] = np.corrcoef(candidate_sample, synthetic)[0, 1]

        pvals = np.array([
            phase1.empirical_pvalue(abs(corrs[h]), hypotheses[h]["null_reference"])
            for h in range(n_hyp)
        ])
        rejected = phase1.benjamini_hochberg(pvals, FDR_Q)
        if not rejected[target_idx]:
            continue

        rejected_idx = np.where(rejected)[0]
        ranked = rejected_idx[np.argsort(-np.abs(corrs[rejected_idx]))]
        shortlist = set(ranked[:CONFIRMATION_TOP_K])
        if target_idx not in shortlist:
            continue

        hyp = hypotheses[target_idx]
        confirm_candidate, confirm_noise = phase1.draw_independent_pair(hyp["candidate"], hyp["target"], valid_starts, block_size, rng)
        confirm_synthetic = phase1.inject_ic(confirm_candidate, confirm_noise, ic)
        confirm_corr = np.corrcoef(confirm_candidate, confirm_synthetic)[0, 1]
        if np.sign(confirm_corr) == np.sign(ic) and abs(confirm_corr) > 0:
            wins[target_idx] += 1

    with np.errstate(invalid="ignore", divide="ignore"):
        power = np.where(trials > 0, wins / np.maximum(trials, 1), np.nan)
    return {hypotheses[i]["name"]: float(power[i]) for i in range(n_hyp)}, trials


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--asset", action="append", type=phase1.parse_asset_arg, required=True,
                    help="NAME,PATH — repeatable, same format as run_campaign58_phase1_power_analysis.py")
    p.add_argument("--n-null", type=int, default=300)
    p.add_argument("--n-power-total", type=int, default=2000,
                    help="Total resamples spread across the 48-hypothesis family (random target each resample) -- NOT per-hypothesis, since 48x the per-hypothesis cost of the base script would be very slow.")
    p.add_argument("--block-anchors", type=int, default=8)
    p.add_argument("--seed", type=int, default=20260903)
    p.add_argument("--out-dir", default="artifacts/campaign58_grid_power_analysis")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rng = np.random.default_rng(args.seed)

    asset_frames: list[pd.DataFrame] = []
    for name, path in args.asset:
        try:
            df = load_ohlcv(path, asset=name)
        except (FileNotFoundError, DataLoadError) as exc:
            print(f"FATAL: could not load {name} from {path}: {exc}")
            return 1
        native_bar_hours = phase1.infer_native_bar_hours(df.index)
        frame = build_asset_frame(df["close"], native_bar_hours, name)
        anchors = anchor_sample(frame, native_bar_hours)
        print(f"{name}: {len(df)} real rows, {len(anchors)} real 168h-equivalent anchors")
        asset_frames.append(anchors)

    pooled = pd.concat(asset_frames, ignore_index=True)
    print(f"\nPooled: {len(pooled)} real anchors across {len(args.asset)} asset(s).")
    print("\nAPPROXIMATION IN EFFECT: residualized-variant columns reuse their raw counterpart's")
    print("real values for null/power calibration only -- see module docstring. Real residualized")
    print("values are not computed by this script.")

    hypotheses = build_48_hypotheses(pooled)
    print(f"\n{len(hypotheses)} hypotheses built (16 feature-variants x 3 horizons, Family R only).")
    if len(hypotheses) != 48:
        print(f"WARNING: expected exactly 48 hypotheses per the frozen spec, got {len(hypotheses)}.")

    group_ids = pooled["asset"].astype("category").cat.codes.to_numpy()
    block_size = args.block_anchors
    valid_starts = phase1.build_valid_starts(group_ids, block_size)
    if not valid_starts:
        print(f"FATAL: no asset has >= {block_size} anchors; reduce --block-anchors.")
        return 1

    print(f"\nBuilding null reference distributions ({args.n_null} resamples each, {len(hypotheses)} hypotheses)...")
    for hyp in hypotheses:
        hyp["null_reference"] = phase1.build_null_reference(hyp["candidate"], hyp["target"], valid_starts, block_size, args.n_null, rng)

    print(f"\nSimulating power at central IC={CENTRAL_IC} ({args.n_power_total} total resamples, "
          f"randomly distributed across {len(hypotheses)} hypotheses)...")
    power_by_hyp, trials = simulate_power_for_ic_grid_scale(hypotheses, CENTRAL_IC, args.n_power_total, valid_starts, block_size, rng, n_focus=1)

    valid_power = [p for p in power_by_hyp.values() if not np.isnan(p)]
    avg_power = float(np.mean(valid_power)) if valid_power else float("nan")
    min_trials = int(trials.min())

    for name, p in sorted(power_by_hyp.items(), key=lambda kv: (np.nan_to_num(kv[1], nan=-1)), reverse=True)[:10]:
        print(f"  {name}: power={p if not np.isnan(p) else 'N/A (0 trials)'}")
    print("  ...")

    report = {
        "audit": "campaign58_grid_power_analysis_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "approximation_notice": (
            "Residualized-variant columns reuse raw-column real values for null/power "
            "calibration only -- not a real residualized computation. Only outcome Family R "
            "simulated. See module docstring for full rationale."
        ),
        "assets": {name: path for name, path in args.asset},
        "n_pooled_anchors": len(pooled),
        "n_hypotheses": len(hypotheses),
        "central_ic": CENTRAL_IC,
        "block_size_anchors": block_size,
        "fdr_q": FDR_Q,
        "confirmation_top_k": CONFIRMATION_TOP_K,
        "n_power_total_resamples": args.n_power_total,
        "min_trials_per_hypothesis": min_trials,
        "power_by_hypothesis": power_by_hyp,
        "average_power_across_family": avg_power,
        "passes_50pct_threshold": (avg_power >= 0.50) if not np.isnan(avg_power) else None,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"grid_power_analysis_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"\n=== Average power across the 48-hypothesis family at central IC ({CENTRAL_IC}): "
          f"{avg_power:.3f} ===" if not np.isnan(avg_power) else "\n=== Average power: N/A (increase --n-power-total) ===")
    print(f"Minimum resamples for any single hypothesis: {min_trials} "
          f"(increase --n-power-total if this is small; each hypothesis needs enough of its own "
          f"draws for its power estimate to be meaningful, not just the family average).")
    print(f"50% threshold: {'PASS' if (not np.isnan(avg_power) and avg_power >= 0.50) else 'FAIL' if not np.isnan(avg_power) else 'INCONCLUSIVE'}")
    print(f"\nArtifact: {out_path}")
    print("\nThis result is used as computed, per the frozen specification's own discipline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
