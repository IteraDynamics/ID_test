from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

from scripts.run_core_v1_candidate_wfo import SCENARIOS, years


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Rerun canonical Core v1 folds and export an exact stitched sleeve matrix.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--scenario", default="candidate_btc1h_hedges_to_btc4h_gld_qqq", choices=sorted(SCENARIOS))
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--btc-data", default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--eth-data", default="data/ethusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--gld-data", default="data/GLD_1D.csv")
    p.add_argument("--data-start", default="2019-01-01")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--equity-fee", type=float, default=0.0001)
    p.add_argument("--base-slippage", type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--out-dir", default="artifacts/trend_persistence_v0/portfolio_integration/core_wfo")
    return p.parse_args()


def _read_series(path: Path) -> pd.Series:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    series = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().sort_index()
    series.index = pd.to_datetime(series.index).tz_localize(None)
    return series


def _read_matrix(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.apply(pd.to_numeric, errors="coerce").sort_index().dropna(how="any")


def run_fold(args: argparse.Namespace, year: str, start: str, end: str) -> tuple[str, Path]:
    weights = SCENARIOS[args.scenario]
    fold_dir = Path(args.out_dir) / args.scenario / "folds" / year
    fold_dir.mkdir(parents=True, exist_ok=True)
    patch = fold_dir / "run_fold_matrix_export.py"
    matrix_capture = fold_dir / "canonical_full_sleeve_equity_matrix.csv"

    patch.write_text(
        f'''
from argparse import Namespace
from pathlib import Path
import sys

sys.path.insert(0, r"{REPO_ROOT}")

import scripts.run_core_v1_sleeve_contribution_audit as audit
from scripts.run_multi_strategy_fund import _build_sleeves as base_build

WEIGHTS = {weights!r}
CAPTURE_PATH = Path(r"{matrix_capture}")


def custom_build_sleeves(args):
    specs = base_build(args)
    labels = {{s.label for s in specs}}
    missing = set(WEIGHTS) - labels
    if missing:
        raise ValueError(f"Missing sleeve labels: {{sorted(missing)}}")
    if abs(sum(WEIGHTS.values()) - 1.0) > 1e-9:
        raise ValueError("Scenario weights do not sum to 1.0")
    out = []
    for spec in specs:
        spec.capital = args.capital * WEIGHTS.get(spec.label, 0.0)
        if spec.capital > 0:
            out.append(spec)
    return out


_original_align = audit.align_equity_curves
_capture_count = 0


def capture_first_alignment(curves, base_freq="1h"):
    global _capture_count
    aligned = _original_align(curves, base_freq=base_freq)
    _capture_count += 1
    if _capture_count == 1:
        CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        aligned.to_csv(CAPTURE_PATH)
    return aligned


audit._build_sleeves = custom_build_sleeves
audit.align_equity_curves = capture_first_alignment

args = Namespace(
    btc_data=r"{args.btc_data}",
    eth_data=r"{args.eth_data}",
    spy_data=r"{args.spy_data}",
    qqq_data=r"{args.qqq_data}",
    bil_data=r"{args.bil_data}",
    gld_data=r"{args.gld_data}",
    capital=100000.0,
    trend_weight=0.40,
    equity_weight=0.35,
    gold_weight=0.15,
    hedge_weight=0.10,
    mr_weight=0.00,
    data_start="{args.data_start}",
    oos_start="{start}",
    oos_end="{end}",
    fee={args.fee},
    equity_fee={args.equity_fee},
    base_slippage={args.base_slippage},
    slippage_vol_factor={args.slippage_vol_factor},
    cooldown=2,
    mr_cooldown=12,
    rebalance_threshold=0.02,
    out_dir=r"{fold_dir}",
)

audit.run_audit(args)
''',
        encoding="utf-8",
    )

    proc = subprocess.run([sys.executable, str(patch)], capture_output=True, text=True)
    (fold_dir / "matrix_export_stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (fold_dir / "matrix_export_stderr.txt").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"Fold {year} failed; see {fold_dir / 'matrix_export_stderr.txt'}")
    if not matrix_capture.exists():
        raise FileNotFoundError(f"Fold {year} did not produce {matrix_capture}")
    return year, fold_dir


def reconcile_fold_matrix(
    matrix: pd.DataFrame,
    fold_nav: pd.Series,
    year: str,
    *,
    tolerance: float = 1e-6,
) -> pd.DataFrame:
    """Rebase a captured sleeve matrix onto the fund NAV's basis and verify it.

    The captured matrix is the *unscaled* alignment produced inside
    ``run_core_v1_sleeve_contribution_audit`` (sleeves start at their allocated
    capital and include the pre-OOS warm-up). The fund NAV written alongside it
    has already been rebased to starting capital. Differencing the two directly
    compares different units and fails by a constant factor even when the data
    is perfectly sound.

    Rebasing first does not weaken the guard. The sleeve set, index, and
    composition must still agree exactly: any real divergence makes the
    matrix-to-NAV ratio non-constant, which this check rejects. Only a single
    global scale factor is forgiven.
    """
    totals = matrix.sum(axis=1)
    if totals.empty:
        raise RuntimeError(f"Fold {year} matrix has no rows in common with fund NAV")
    first_total = float(totals.iloc[0])
    if not np.isfinite(first_total) or first_total <= 0:
        raise RuntimeError(f"Fold {year} matrix sum is non-positive at the first common timestamp")

    rebase = float(fold_nav.iloc[0]) / first_total
    rebased = matrix * rebase
    delta = (rebased.sum(axis=1) - fold_nav).abs().max()
    if delta > tolerance:
        ratio = fold_nav / totals
        raise RuntimeError(
            f"Fold {year} matrix does not reconcile to fund NAV after rebasing; "
            f"max delta={delta} (rebase factor {rebase:.12f}, "
            f"ratio spread {float(ratio.max() - ratio.min()):.3e}). "
            "A non-constant ratio means the sleeve set, index, or composition "
            "genuinely differs — do not widen this tolerance."
        )
    return rebased


def main() -> None:
    args = parse_args()
    folds = years(args.oos_start, args.oos_end)
    workers = max(1, min(args.workers, len(folds)))
    print(f"Exporting canonical Core sleeve matrices: {len(folds)} folds with {workers} workers")

    completed: list[tuple[str, Path]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_fold, args, year, start, end) for year, start, end in folds]
        for future in as_completed(futures):
            year, fold_dir = future.result()
            print(f"Fold {year} complete")
            completed.append((year, fold_dir))

    running_nav = 100000.0
    matrix_parts: list[pd.DataFrame] = []
    nav_parts: list[pd.Series] = []

    for year, fold_dir in sorted(completed):
        start = pd.Timestamp(f"{year}-01-01") if int(year) > pd.Timestamp(args.oos_start).year else pd.Timestamp(args.oos_start)
        end = pd.Timestamp(f"{year}-12-31") if int(year) < pd.Timestamp(args.oos_end).year else pd.Timestamp(args.oos_end)
        full_matrix = _read_matrix(fold_dir / "canonical_full_sleeve_equity_matrix.csv")
        matrix = full_matrix.loc[start:end].dropna(how="any")
        fold_nav = _read_series(fold_dir / "stitched_fund_nav_from_sleeves.csv")
        common = matrix.index.intersection(fold_nav.index)
        matrix = matrix.loc[common]
        fold_nav = fold_nav.loc[common]
        matrix = reconcile_fold_matrix(matrix, fold_nav, year)
        scale = running_nav / float(fold_nav.iloc[0])
        scaled_matrix = matrix * scale
        scaled_nav = fold_nav * scale
        matrix_parts.append(scaled_matrix)
        nav_parts.append(scaled_nav)
        running_nav = float(scaled_nav.iloc[-1])
        print(f"Fold {year}: rows={len(matrix):,} scale={scale:.8f} ending_nav={running_nav:,.2f}")

    scenario_dir = Path(args.out_dir) / args.scenario
    stitched_matrix = pd.concat(matrix_parts).sort_index()
    stitched_matrix = stitched_matrix[~stitched_matrix.index.duplicated(keep="last")]
    stitched_nav = pd.concat(nav_parts).sort_index()
    stitched_nav = stitched_nav[~stitched_nav.index.duplicated(keep="last")]
    final_delta = (stitched_matrix.sum(axis=1) - stitched_nav).abs().max()
    if final_delta > 1e-6:
        raise RuntimeError(f"Stitched matrix does not reconcile; max delta={final_delta}")

    matrix_path = scenario_dir / "stitched_sleeve_equity_matrix.csv"
    nav_path = scenario_dir / "stitched_fund_nav_from_sleeves.csv"
    stitched_matrix.to_csv(matrix_path)
    stitched_nav.rename("fund_nav").to_csv(nav_path, header=True)

    print()
    print("Canonical Core v1 sleeve matrix export complete")
    print(f"Rows: {len(stitched_matrix):,}")
    print(f"Final NAV: {float(stitched_nav.iloc[-1]):,.2f}")
    print(f"Max reconciliation delta: {final_delta:.12f}")
    print(f"Matrix: {matrix_path}")
    print(f"NAV: {nav_path}")


if __name__ == "__main__":
    main()
