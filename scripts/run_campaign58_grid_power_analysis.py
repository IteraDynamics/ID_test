"""Campaign #58 Phase 1 -- grid-level power verification (Red Team condition 1, spec Sec13-14).

`scripts/run_campaign58_phase1_power_analysis.py` verified power for a 7-candidate,
Family-R-only family (58.3% average at the central IC, PASS). The frozen specification
(`docs/research/CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md`) defines a much larger
design -- 48 candidates per outcome family (16 feature-variants x 3 target horizons), FDR-
corrected within each of 3 outcome families (R/M/V) separately, 144 candidates total.
Benjamini-Hochberg's detection threshold tightens as family size grows for a fixed single
injected effect, so the 7-candidate result does NOT establish that the real 48-per-family design
also clears the 50% floor. This script checks that, for real, before any real predictor/outcome
computation is treated as responsible to run.

Reuses every statistical primitive from `run_campaign58_phase1_power_analysis.py` (grouped block
bootstrap, inject_ic, empirical null, Benjamini-Hochberg, PowerShell-style asset input) by
importing it as a module rather than reimplementing it -- one audited implementation, not two.

CORRECTION, independent Red Team review of the frozen specification: the first version of this
script simulated outcome Family R only, reasoning that Campaign #48's own finding (zero
supported directional associations, all 15 survivors in Family M/V) made R the "hardest, most
conservative" family. The review found this conflates whether a true effect EXISTS (irrelevant to
injected-IC power calibration, which assumes a true effect and asks whether it would be detected)
with how AUTOCORRELATED a series is (what actually drives this block-bootstrap methodology's
power -- directly evidenced by this fund's own data, where `realized_volatility_trailing_168h`'s
uniquely weak 19.7% power traces to its outlier-high 0.78 lag-1 autocorrelation, not to any claim
about whether volatility clustering is "real"). If forward volatility/magnitude targets are as
persistent as this fund's own price-state features already measured are (plausible -- volatility
clustering is well documented), Family M/V power could be LOWER than Family R's, meaning an
R-only result could OVERSTATE the true 144-candidate grid's power rather than lower-bound it.
This version simulates all three outcome families.

WHAT'S REAL AND WHAT'S AN APPROXIMATION, stated up front

- The 8 base feature columns (raw) are computed for real from the operator's real close prices,
  identical formulas to the frozen spec's Sec4.
- The 3 target horizons' real forward R/M/V outcomes (Sec6 of the spec) are computed for real
  from the same real close prices -- these are genuine forward-looking targets, unlike the proxy
  target `run_campaign58_phase1_power_analysis.py` used for its own calibration purposes.
- The RESIDUALIZED feature variants (Sec5 and Sec9 of the spec) are NOT computed for real here --
  doing so requires the full known-signal fit (regime state, Core v1 SMA175, momentum, vol) the
  spec's Sec9 describes, which is real implementation work appropriately gated behind the CEO
  authorization this script's own results are meant to inform, not assumed in advance. For
  power-CALIBRATION purposes only (estimating how tight or wide a null distribution should be,
  not any real residual value), each residualized variant is approximated by REUSING its raw
  counterpart's real values -- expected to be conservative (residualization typically does not
  INCREASE a feature's own serial dependence), but an approximation, not a proof.
- All three outcome families (R, M, V) are simulated, at the true 48-candidates-per-family scale
  (144 total), matching the frozen specification exactly.
- This script does NOT fit any of the 6 real models from spec Sec8 -- it tests the same
  correlation-style injected-effect detectability `run_campaign58_phase1_power_analysis.py`
  already uses, which is the appropriate level of fidelity for a PRE-EXECUTION power calibration
  (matching Campaign #53's own precedent) and does not need to replicate Sec12's full decision
  machinery to answer the narrower question "would the FDR gate detect a real effect of this
  size at this family size."

TRIAL-ADEQUACY GUARD, independent Red Team review condition 9

The first version's own smoke test produced hypotheses with 0 trials and degenerate 0.0/1.0
per-hypothesis power estimates at a low --n-power-total. This version REFUSES to report a clean
PASS/FAIL headline if any hypothesis's trial count falls below --min-trials-per-hypothesis
(default 20) -- it reports which hypotheses are under-sampled and by how much, and instructs the
operator to increase --n-power-total, rather than silently averaging over unreliable estimates.
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
CONFIRMATION_TOP_K = 10  # scaled from Campaign #53's ~33% selectivity ratio for a 48-member family (~21%; 10/48=20.8%)
TARGET_HORIZONS_HOURS = (24, 72, 168)
OUTCOME_FAMILIES = ("R", "M", "V")

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


def forward_return(close: pd.Series, bars: int) -> pd.Series:
    """Family R -- forward_return_h = ln(C_{t+h} / C_t)."""
    return np.log(close.shift(-bars) / close)


def forward_absolute_return(forward_ret: pd.Series) -> pd.Series:
    """Family M -- forward_absolute_return_h = abs(forward_return_h)."""
    return forward_ret.abs()


def forward_realized_volatility(close: pd.Series, bars: int) -> pd.Series:
    """Family V -- forward_realized_volatility_h = sqrt(sum(r_u^2)) over the h forward bars."""
    log_ret = np.log(close / close.shift(1))
    forward_sq_sum = log_ret.pow(2).shift(-bars).rolling(bars, min_periods=bars).sum()
    # rolling window here is over the PAST bars-1..0 with shift(-bars) already moving the origin
    # forward by `bars`; equivalent construction to phase1.trailing_realized_vol but pointed at
    # the future window (t, t+h] rather than the trailing window [t-h, t).
    return forward_sq_sum.pow(0.5)


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
    # real forward R/M/V targets at each of the 3 horizons
    for h in TARGET_HORIZONS_HOURS:
        bars_h = phase1.hours_to_bars(h, native_bar_hours)
        fwd_r = forward_return(close, bars_h)
        cols[f"target_R_{h}h"] = fwd_r
        cols[f"target_M_{h}h"] = forward_absolute_return(fwd_r)
        cols[f"target_V_{h}h"] = forward_realized_volatility(close, bars_h)
    frame = pd.DataFrame(cols)
    frame["asset"] = asset_name
    return frame


def anchor_sample(frame: pd.DataFrame, native_bar_hours: float) -> pd.DataFrame:
    spacing_bars = phase1.hours_to_bars(168, native_bar_hours)
    complete = frame.dropna()
    return complete.iloc[::spacing_bars].reset_index(drop=True)


def build_144_hypotheses(pooled: pd.DataFrame) -> list[dict[str, Any]]:
    """16 feature-variants (8 raw + 8 residualized-APPROXIMATED, see module docstring) x 3
    target horizons x 3 outcome families (R, M, V) = 144 hypotheses, matching the frozen spec's
    true grid exactly."""
    hypotheses: list[dict[str, Any]] = []
    for base_col in BASE_FEATURE_COLUMNS:
        for variant in ("raw", "residualized_approx"):
            candidate = pooled[base_col].to_numpy(dtype=float)  # approximation: same values for both variants
            for family in OUTCOME_FAMILIES:
                for h in TARGET_HORIZONS_HOURS:
                    target = pooled[f"target_{family}_{h}h"].to_numpy(dtype=float)
                    hypotheses.append({
                        "name": f"{base_col}__{variant}__{family}__{h}h",
                        "family": family,
                        "candidate": candidate,
                        "target": target,
                    })
    return hypotheses


def simulate_power_random_target(
    hypotheses: list[dict[str, Any]],
    ic: float,
    n_resamples: int,
    valid_starts: list[tuple[int, int]],
    block_size: int,
    rng: np.random.Generator,
    confirmation_top_k: int,
) -> tuple[dict[str, float], np.ndarray]:
    """Like phase1.simulate_power_for_ic, but injects the effect into a RANDOM hypothesis each
    resample (drawn only from within that hypothesis's own outcome family, matching how BH-FDR
    is applied per-family in the frozen spec) rather than looping every hypothesis in turn --
    full per-hypothesis x per-resample coverage at 144 hypotheses is too slow for a laptop
    calibration run; random-target sampling still gives an unbiased per-hypothesis power
    estimate given enough total resamples (see the trial-adequacy guard in main())."""
    n_hyp = len(hypotheses)
    families = np.array([h["family"] for h in hypotheses])
    family_indices = {fam: np.where(families == fam)[0] for fam in OUTCOME_FAMILIES}

    wins = np.zeros(n_hyp)
    trials = np.zeros(n_hyp)

    for _ in range(n_resamples):
        target_idx = int(rng.integers(0, n_hyp))
        target_family = hypotheses[target_idx]["family"]
        family_idx = family_indices[target_family]
        trials[target_idx] += 1

        corrs_family = np.empty(len(family_idx))
        for pos, h_idx in enumerate(family_idx):
            hyp = hypotheses[h_idx]
            candidate_sample, noise_sample = phase1.draw_independent_pair(hyp["candidate"], hyp["target"], valid_starts, block_size, rng)
            effect = ic if h_idx == target_idx else 0.0
            synthetic = phase1.inject_ic(candidate_sample, noise_sample, effect)
            corrs_family[pos] = np.corrcoef(candidate_sample, synthetic)[0, 1]

        pvals = np.array([
            phase1.empirical_pvalue(abs(corrs_family[pos]), hypotheses[family_idx[pos]]["null_reference"])
            for pos in range(len(family_idx))
        ])
        rejected = phase1.benjamini_hochberg(pvals, FDR_Q)
        target_pos = int(np.where(family_idx == target_idx)[0][0])
        if not rejected[target_pos]:
            continue

        rejected_pos = np.where(rejected)[0]
        ranked = rejected_pos[np.argsort(-np.abs(corrs_family[rejected_pos]))]
        shortlist = set(ranked[:confirmation_top_k])
        if target_pos not in shortlist:
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
    p.add_argument("--n-power-total", type=int, default=8000,
                    help="Total resamples spread across the 144-hypothesis grid (random target each resample, within its own outcome family). ~55 trials/hypothesis on average at the default.")
    p.add_argument("--min-trials-per-hypothesis", type=int, default=20,
                    help="Refuse a clean PASS/FAIL headline if any hypothesis falls below this many trials — increase --n-power-total instead of trusting an under-sampled estimate.")
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
    print("real values for null/power calibration only — see module docstring. Real residualized")
    print("values are not computed by this script.")

    hypotheses = build_144_hypotheses(pooled)
    print(f"\n{len(hypotheses)} hypotheses built (16 feature-variants x 3 horizons x 3 outcome "
          f"families R/M/V — the frozen spec's true grid).")
    if len(hypotheses) != 144:
        print(f"WARNING: expected exactly 144 hypotheses per the frozen spec, got {len(hypotheses)}.")

    group_ids = pooled["asset"].astype("category").cat.codes.to_numpy()
    block_size = args.block_anchors
    valid_starts = phase1.build_valid_starts(group_ids, block_size)
    if not valid_starts:
        print(f"FATAL: no asset has >= {block_size} anchors; reduce --block-anchors.")
        return 1

    print(f"\nBuilding null reference distributions ({args.n_null} resamples each, "
          f"{len(hypotheses)} hypotheses)...")
    for hyp in hypotheses:
        hyp["null_reference"] = phase1.build_null_reference(hyp["candidate"], hyp["target"], valid_starts, block_size, args.n_null, rng)

    print(f"\nSimulating power at central IC={CENTRAL_IC} ({args.n_power_total} total resamples, "
          f"randomly distributed across {len(hypotheses)} hypotheses within their own outcome "
          f"family)...")
    power_by_hyp, trials = simulate_power_random_target(
        hypotheses, CENTRAL_IC, args.n_power_total, valid_starts, block_size, rng, CONFIRMATION_TOP_K
    )

    min_trials = int(trials.min())
    under_sampled = [hypotheses[i]["name"] for i in range(len(hypotheses)) if trials[i] < args.min_trials_per_hypothesis]

    families_report: dict[str, Any] = {}
    for fam in OUTCOME_FAMILIES:
        fam_powers = [power_by_hyp[h["name"]] for h in hypotheses if h["family"] == fam and not np.isnan(power_by_hyp[h["name"]])]
        families_report[fam] = {
            "n_hypotheses": sum(1 for h in hypotheses if h["family"] == fam),
            "n_with_valid_estimate": len(fam_powers),
            "average_power": float(np.mean(fam_powers)) if fam_powers else None,
        }
        avg_str = f"{families_report[fam]['average_power']:.3f}" if families_report[fam]["average_power"] is not None else "N/A"
        print(f"  Family {fam}: average power = {avg_str} ({families_report[fam]['n_with_valid_estimate']}/{families_report[fam]['n_hypotheses']} hypotheses with a valid estimate)")

    valid_power = [p for p in power_by_hyp.values() if not np.isnan(p)]
    avg_power = float(np.mean(valid_power)) if valid_power else float("nan")

    report = {
        "audit": "campaign58_grid_power_analysis_v2_all_families",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "approximation_notice": (
            "Residualized-variant columns reuse raw-column real values for null/power "
            "calibration only — not a real residualized computation. See module docstring."
        ),
        "assets": {name: path for name, path in args.asset},
        "n_pooled_anchors": len(pooled),
        "n_hypotheses": len(hypotheses),
        "central_ic": CENTRAL_IC,
        "block_size_anchors": block_size,
        "fdr_q": FDR_Q,
        "confirmation_top_k": CONFIRMATION_TOP_K,
        "n_power_total_resamples": args.n_power_total,
        "min_trials_per_hypothesis_observed": min_trials,
        "min_trials_per_hypothesis_required": args.min_trials_per_hypothesis,
        "under_sampled_hypotheses": under_sampled,
        "power_by_family": families_report,
        "power_by_hypothesis": power_by_hyp,
        "average_power_across_family": avg_power,
        "trial_adequacy_met": len(under_sampled) == 0,
        "passes_50pct_threshold": (avg_power >= 0.50) if (not np.isnan(avg_power) and len(under_sampled) == 0) else None,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"grid_power_analysis_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"\n=== Overall average power across all {len(hypotheses)} hypotheses at central IC "
          f"({CENTRAL_IC}): {avg_power:.3f} ===" if not np.isnan(avg_power) else "\n=== Average power: N/A ===")

    if under_sampled:
        print(f"\nTRIAL-ADEQUACY GUARD TRIPPED: {len(under_sampled)} of {len(hypotheses)} "
              f"hypotheses received fewer than {args.min_trials_per_hypothesis} trials "
              f"(minimum observed: {min_trials}). PASS/FAIL is NOT reported — increase "
              f"--n-power-total and re-run before treating any number here as informative.")
    else:
        print(f"Minimum trials for any hypothesis: {min_trials} (adequate, >= "
              f"{args.min_trials_per_hypothesis}).")
        print(f"50% threshold: {'PASS' if avg_power >= 0.50 else 'FAIL'}")

    print(f"\nArtifact: {out_path}")
    print("\nThis result is used as computed, per the frozen specification's own discipline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
