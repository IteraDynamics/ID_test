"""Campaign #58 Phase 1 (time-series residual census) power analysis — multi-asset, against
real OHLCV data supplied by the operator.

Authorized 2026-09-03 (CEO authorization, docs/ITERA_CAMPAIGN_BOARD.md correction of that date):
this is the pre-execution power/specification-freeze work the charter's Red Team conditions 1
and 2 require -- bootstrap real data, inject a hypothetical effect, measure whether the frozen
gates would detect it -- not real predictor/outcome computation for an actual Campaign #58
decision. It produces a power percentage against a proxy family, not a candidate ranking, not a
residual-predictability result, and not a trading signal.

Methodology is the same block-bootstrap, empirical-null, inject_ic approach already governed for
Campaign #53 (`scripts/run_campaign53_power_analysis.py`) -- reused, not reinvented. One genuine
improvement over that script, made necessary by pooling up to five assets instead of two: the
block bootstrap here never lets a resampled block span an asset boundary (see
`grouped_block_bootstrap_resample` below). Campaign #53's original two-asset version could let a
block straddle the BTC/ETH concatenation point; with five assets pooled that approximation would
be proportionally more common, so it is fixed here rather than carried forward silently.

REVISION HISTORY

v1 (2026-09-03, same-day): BTC-only, using Campaign #48's committed anchor inventory -- this
session's environment had no outbound network access and no multi-asset data. Result: 13.0%
average power at the central IC, FAIL. See
docs/research/CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md.

v2 (this version): generalized to accept real OHLCV CSVs for any number of assets (BTC, ETH,
SPY, QQQ, GLD, or a subset), for the operator to run locally where the full data actually lives.
Computes Campaign #48's own 8 predictor formulas directly from each asset's close prices,
adapted for mixed bar cadence (see "MIXED CADENCE" below), then pools all assets' real
(candidate, target) pairs for the same block-bootstrap power simulation. No BTC-only proxy
artifact is read in this version -- every asset's real close-price history is used directly.

MIXED CADENCE, stated explicitly rather than silently assumed

Campaign #48's predictor windows (24h / 72h / 168h) and anchor spacing (168h) are defined in
hours, which is exact for BTC/ETH's native hourly bars. SPY/QQQ/GLD are ordinarily daily bars,
where "hours" has no literal meaning bar-to-bar. This script infers each asset's OWN native bar
spacing from its own timestamps (median inter-row gap, robust to weekend/holiday gaps in daily
data) and converts every hour-based window into a BAR COUNT for that asset:
`bars = max(1, round(window_hours / native_bar_hours))`. For an hourly asset this reproduces
Campaign #48's original windows exactly (24/72/168 bars). For a daily asset this becomes
1/3/7 bars -- i.e. 1, 3, and 7 TRADING DAYS, not 24/72/168 wall-clock hours. This is a documented
adaptation, not a claim that a SPY "168h" window covers the same wall-clock span as a BTC "168h"
window. Anchor spacing is converted the same way (7 bars for a daily asset, weekly-equivalent to
BTC/ETH's 168h/7-day anchor grid in spirit, not in literal wall-clock hours).

PROXY TARGET, same honesty as v1

The committed governed artifacts hold fitted regression summary statistics, not raw per-anchor
outcome values, and this power simulation is calibration, not a real residual-predictability run
-- so there is still no real "forward outcome" series to inject an effect into. As in v1, one of
the real predictor columns (the trailing realized-volatility family, computed per asset from
that asset's own real close prices) stands in for realistic marginal/autocorrelation structure.
It is a stand-in for calibrating how tight or wide a null distribution should be, not a claim
about any specific real candidate-target relationship.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.harness.data_loader import load_ohlcv, DataLoadError  # noqa: E402

FDR_Q = 0.10
CONFIRMATION_TOP_K = 2
IC_GRID = (0.02, 0.05, 0.08, 0.12)
CENTRAL_IC = 0.065

# Hour-denominated windows, translated per-asset into bar counts (see MIXED CADENCE above).
RETURN_WINDOWS_HOURS = (24, 72, 168)
VOL_WINDOWS_HOURS = (24, 168)
ANCHOR_SPACING_HOURS = 168
PROXY_TARGET_WINDOW_HOURS = 24  # matches PROXY_TARGET_COLUMN's window below


# ------------------------------------------------------- per-asset predictor construction


def infer_native_bar_hours(index: pd.DatetimeIndex) -> float:
    """Median inter-row gap in hours -- robust to weekend/holiday gaps in daily data (a small
    minority of rows), unlike mean, which those gaps would inflate."""
    diffs = index.to_series().diff().dropna()
    if len(diffs) == 0:
        raise ValueError("cannot infer bar spacing from fewer than 2 rows")
    median_seconds = diffs.dt.total_seconds().median()
    return median_seconds / 3600.0


def hours_to_bars(hours: int, native_bar_hours: float) -> int:
    return max(1, round(hours / native_bar_hours))


def trailing_log_return(close: pd.Series, bars: int) -> pd.Series:
    return np.log(close / close.shift(bars))


def trailing_realized_vol(close: pd.Series, bars: int) -> pd.Series:
    log_ret = np.log(close / close.shift(1))
    return log_ret.pow(2).rolling(bars, min_periods=bars).sum().pow(0.5)


def distance_from_mean(close: pd.Series, bars: int) -> pd.Series:
    mean = close.rolling(bars + 1, min_periods=bars + 1).mean()
    return (close / mean) - 1.0


def range_position(close: pd.Series, bars: int) -> pd.Series:
    low = close.rolling(bars + 1, min_periods=bars + 1).min()
    high = close.rolling(bars + 1, min_periods=bars + 1).max()
    span = high - low
    return ((close - low) / span).where(span != 0)


def drawdown_from_high(close: pd.Series, bars: int) -> pd.Series:
    high = close.rolling(bars + 1, min_periods=bars + 1).max()
    return (close / high) - 1.0


def build_asset_predictor_frame(close: pd.Series, native_bar_hours: float, asset_name: str) -> pd.DataFrame:
    """One row per real bar, all 8 Campaign #48-style predictors, computed causally
    (every value at row t uses only rows <= t)."""
    cols: dict[str, pd.Series] = {}
    for h in RETURN_WINDOWS_HOURS:
        bars = hours_to_bars(h, native_bar_hours)
        cols[f"return_trailing_{h}h"] = trailing_log_return(close, bars)
    for h in VOL_WINDOWS_HOURS:
        bars = hours_to_bars(h, native_bar_hours)
        cols[f"realized_volatility_trailing_{h}h"] = trailing_realized_vol(close, bars)
    bars_168 = hours_to_bars(168, native_bar_hours)
    cols["distance_from_mean_trailing_168h"] = distance_from_mean(close, bars_168)
    cols["range_position_trailing_168h"] = range_position(close, bars_168)
    cols["drawdown_from_high_trailing_168h"] = drawdown_from_high(close, bars_168)
    frame = pd.DataFrame(cols)
    frame["asset"] = asset_name
    return frame


def anchor_sample(frame: pd.DataFrame, native_bar_hours: float) -> pd.DataFrame:
    """Sub-sample to a 168h-equivalent anchor grid (per this asset's own bar cadence), matching
    Campaign #48's non-overlapping-anchor discipline instead of using every overlapping row."""
    spacing_bars = hours_to_bars(ANCHOR_SPACING_HOURS, native_bar_hours)
    complete = frame.dropna()
    return complete.iloc[::spacing_bars].reset_index(drop=True)


CANDIDATE_COLUMNS = (
    "return_trailing_24h",
    "return_trailing_72h",
    "return_trailing_168h",
    "realized_volatility_trailing_168h",
    "distance_from_mean_trailing_168h",
    "range_position_trailing_168h",
    "drawdown_from_high_trailing_168h",
)
PROXY_TARGET_COLUMN = "realized_volatility_trailing_24h"


# ------------------------------------------------------- grouped block bootstrap
# (generalizes scripts/run_campaign53_power_analysis.py's block_bootstrap_resample: blocks are
# now drawn so they never span an asset boundary -- see module docstring)


def build_valid_starts(group_ids: np.ndarray, block_size: int) -> list[tuple[int, int]]:
    """(start_index, group_length) for every position where a block of block_size fits entirely
    within one asset's contiguous row range."""
    valid: list[tuple[int, int]] = []
    boundaries = np.flatnonzero(np.diff(group_ids, prepend=group_ids[0] - 1))
    boundaries = np.append(boundaries, len(group_ids))
    start = 0
    for end in boundaries[1:] if len(boundaries) > 1 else [len(group_ids)]:
        group_len = end - start
        for s in range(start, end - block_size + 1):
            valid.append((s, group_len))
        start = end
    return valid


def grouped_block_bootstrap_resample(n: int, valid_starts: list[tuple[int, int]], block_size: int, rng: np.random.Generator) -> np.ndarray:
    if not valid_starts:
        raise ValueError("no asset group is long enough for the requested block_size")
    indices: list[np.ndarray] = []
    total = 0
    starts_only = np.array([s for s, _ in valid_starts])
    while total < n:
        start = int(rng.choice(starts_only))
        indices.append(np.arange(start, start + block_size))
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


def draw_independent_pair(candidate: np.ndarray, real_target: np.ndarray, valid_starts: list[tuple[int, int]], block_size: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    n = len(candidate)
    idx_candidate = grouped_block_bootstrap_resample(n, valid_starts, block_size, rng)
    idx_noise = grouped_block_bootstrap_resample(n, valid_starts, block_size, rng)
    return candidate[idx_candidate], real_target[idx_noise]


def build_null_reference(candidate: np.ndarray, real_target: np.ndarray, valid_starts: list[tuple[int, int]], block_size: int, n_null: int, rng: np.random.Generator) -> np.ndarray:
    correlations = np.empty(n_null)
    for i in range(n_null):
        candidate_sample, noise_sample = draw_independent_pair(candidate, real_target, valid_starts, block_size, rng)
        synthetic = inject_ic(candidate_sample, noise_sample, 0.0)
        correlations[i] = abs(np.corrcoef(candidate_sample, synthetic)[0, 1])
    return correlations


def empirical_pvalue(observed_abs_corr: float, null_reference: np.ndarray) -> float:
    return float((null_reference >= observed_abs_corr).mean())


def simulate_power_for_ic(
    hypotheses: list[dict[str, Any]],
    ic: float,
    n_resamples: int,
    valid_starts: list[tuple[int, int]],
    block_size: int,
    rng: np.random.Generator,
) -> dict[str, float]:
    n_hyp = len(hypotheses)
    wins = np.zeros(n_hyp)

    for target_idx in range(n_hyp):
        for _ in range(n_resamples):
            corrs = np.empty(n_hyp)
            for h_idx, hyp in enumerate(hypotheses):
                candidate_sample, noise_sample = draw_independent_pair(hyp["candidate"], hyp["target"], valid_starts, block_size, rng)
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
            confirm_candidate, confirm_noise = draw_independent_pair(hyp["candidate"], hyp["target"], valid_starts, block_size, rng)
            confirm_synthetic = inject_ic(confirm_candidate, confirm_noise, ic)
            confirm_corr = np.corrcoef(confirm_candidate, confirm_synthetic)[0, 1]
            if np.sign(confirm_corr) == np.sign(ic) and abs(confirm_corr) > 0:
                wins[target_idx] += 1

    return {hypotheses[i]["name"]: wins[i] / n_resamples for i in range(n_hyp)}


# ------------------------------------------------------- CLI


def parse_asset_arg(raw: str) -> tuple[str, str]:
    if "," not in raw:
        raise argparse.ArgumentTypeError(f"--asset expects NAME,PATH, got: {raw!r}")
    name, path = raw.split(",", 1)
    return name.strip(), path.strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example (PowerShell):\n"
            "  python scripts\\run_campaign58_phase1_power_analysis.py `\n"
            "    --asset BTC,data\\btcusd_3600s_2018-01-01_to_2025-12-31.csv `\n"
            "    --asset ETH,data\\ethusd_3600s_2018-01-01_to_2025-12-31.csv `\n"
            "    --asset SPY,data\\spy_daily.csv `\n"
            "    --asset QQQ,data\\qqq_daily.csv `\n"
            "    --asset GLD,data\\gld_daily.csv\n"
        ),
    )
    p.add_argument("--asset", action="append", type=parse_asset_arg, required=True,
                    help="NAME,PATH — repeatable, e.g. --asset BTC,data\\btc.csv. CSV must have "
                         "columns [timestamp, open, high, low, close, volume] (repo standard).")
    p.add_argument("--n-null", type=int, default=300)
    p.add_argument("--n-power", type=int, default=150)
    p.add_argument("--block-anchors", type=int, default=8, help="Block bootstrap block size, in anchors, per asset group.")
    p.add_argument("--seed", type=int, default=20260903)
    p.add_argument("--out-dir", default="artifacts/campaign58_phase1_power_analysis")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rng = np.random.default_rng(args.seed)

    asset_anchor_frames: list[pd.DataFrame] = []
    cadence_report: dict[str, Any] = {}

    for name, path in args.asset:
        try:
            df = load_ohlcv(path, asset=name)
        except (FileNotFoundError, DataLoadError) as exc:
            print(f"FATAL: could not load {name} from {path}: {exc}")
            return 1
        native_bar_hours = infer_native_bar_hours(df.index)
        print(f"{name}: {len(df)} real rows from {path}, inferred native bar spacing "
              f"{native_bar_hours:.2f}h")
        predictor_frame = build_asset_predictor_frame(df["close"], native_bar_hours, name)
        anchors = anchor_sample(predictor_frame, native_bar_hours)
        print(f"  -> {len(anchors)} real 168h-equivalent anchors "
              f"({hours_to_bars(168, native_bar_hours)} bars apart)")
        asset_anchor_frames.append(anchors)
        cadence_report[name] = {
            "rows": len(df),
            "native_bar_hours": native_bar_hours,
            "anchor_bars_apart": hours_to_bars(168, native_bar_hours),
            "n_anchors": len(anchors),
        }

    pooled = pd.concat(asset_anchor_frames, ignore_index=True)
    print(f"\nPooled: {len(pooled)} real anchors across {len(args.asset)} asset(s).")

    group_ids = pooled["asset"].astype("category").cat.codes.to_numpy()
    target = pooled[PROXY_TARGET_COLUMN].to_numpy(dtype=float)

    hypotheses: list[dict[str, Any]] = []
    for col in CANDIDATE_COLUMNS:
        candidate = pooled[col].to_numpy(dtype=float)
        hypotheses.append({"name": col, "candidate": candidate, "target": target})

    print(f"\nProxy-target column: {PROXY_TARGET_COLUMN} (real, per-asset, NOT a literal forward "
          f"outcome -- see module docstring).")
    print(f"{len(hypotheses)} candidate hypotheses, real multi-asset data.")

    print("\nBlock-width sanity check (lag-1 autocorrelation, computed on the pooled series -- "
          "expect some inflation vs. any single asset alone since group boundaries are still "
          "adjacent in the pooled array even though blocks never cross them):")
    for hyp in hypotheses:
        print(f"  {hyp['name']}: candidate lag-1 r={lag1_autocorr(hyp['candidate']):.4f}")
    print(f"  {PROXY_TARGET_COLUMN} (proxy target): lag-1 r={lag1_autocorr(target):.4f}")

    block_size = args.block_anchors
    valid_starts = build_valid_starts(group_ids, block_size)
    if not valid_starts:
        print(f"FATAL: no asset has >= {block_size} anchors; reduce --block-anchors.")
        return 1

    print(f"\nBuilding null reference distributions ({args.n_null} resamples each, block size "
          f"{block_size} anchors, never crossing an asset boundary)...")
    for hyp in hypotheses:
        hyp["null_reference"] = build_null_reference(hyp["candidate"], hyp["target"], valid_starts, block_size, args.n_null, rng)
        print(f"  {hyp['name']}: null |r| median={np.median(hyp['null_reference']):.4f}")

    results: dict[float, dict[str, float]] = {}
    for ic in IC_GRID:
        print(f"\nSimulating power at IC={ic} ({args.n_power} resamples per hypothesis)...")
        results[ic] = simulate_power_for_ic(hypotheses, ic, args.n_power, valid_starts, block_size, rng)
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

    import json
    report = {
        "audit": "campaign58_phase1_power_analysis_v2_multiasset",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "assets": {name: path for name, path in args.asset},
        "cadence": cadence_report,
        "n_pooled_anchors": len(pooled),
        "proxy_target_column": PROXY_TARGET_COLUMN,
        "ic_grid": list(IC_GRID),
        "central_ic": CENTRAL_IC,
        "block_size_anchors": block_size,
        "fdr_q": FDR_Q,
        "confirmation_top_k": CONFIRMATION_TOP_K,
        "lag1_autocorr_pooled": {
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
    out_path = out_dir / f"phase1_power_analysis_multiasset_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"\n=== Average power at central IC ({CENTRAL_IC}): {avg_central_power:.3f} ===")
    print(f"50% threshold: {'PASS' if avg_central_power >= 0.50 else 'FAIL'}")
    print(f"\nArtifact: {out_path}")
    print("\nThis result is used as computed -- per Campaign #58's own frozen discipline, do not")
    print("adjust the design (windows, assets, proxy target, block size) after seeing this number")
    print("and re-run to try to clear 50%. If it fails, report it as a fail.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
