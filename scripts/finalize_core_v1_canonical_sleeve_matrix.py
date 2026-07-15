from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_core_v1_candidate_wfo import years


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize canonical Core v1 sleeve matrices from completed exporter fold captures.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        default="candidate_btc1h_hedges_to_btc4h_gld_qqq",
    )
    parser.add_argument(
        "--core-wfo-dir",
        default="artifacts/trend_persistence_v0/portfolio_integration/core_wfo",
    )
    parser.add_argument("--oos-start", default="2020-01-01")
    parser.add_argument("--oos-end", default="2025-12-31")
    parser.add_argument("--initial-capital", type=float, default=100000.0)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    return parser.parse_args()


def read_series(path: Path) -> pd.Series:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    series = pd.to_numeric(frame.iloc[:, 0], errors="coerce").dropna().sort_index()
    series.index = pd.to_datetime(series.index).tz_localize(None)
    return series


def read_matrix(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    return frame.apply(pd.to_numeric, errors="coerce").sort_index().dropna(how="any")


def main() -> None:
    args = parse_args()
    scenario_dir = Path(args.core_wfo_dir) / args.scenario
    folds_dir = scenario_dir / "folds"
    if not folds_dir.exists():
        raise FileNotFoundError(f"Missing folds directory: {folds_dir}")

    running_nav = float(args.initial_capital)
    matrix_parts: list[pd.DataFrame] = []
    nav_parts: list[pd.Series] = []
    audit_rows: list[dict[str, float | int | str]] = []

    for year, start_raw, end_raw in years(args.oos_start, args.oos_end):
        fold_dir = folds_dir / year
        capture_path = fold_dir / "canonical_full_sleeve_equity_matrix.csv"
        fold_nav_path = fold_dir / "stitched_fund_nav_from_sleeves.csv"
        if not capture_path.exists() or not fold_nav_path.exists():
            raise FileNotFoundError(
                f"Fold {year} missing exporter artifacts: {capture_path}, {fold_nav_path}"
            )

        start = pd.Timestamp(start_raw)
        end = pd.Timestamp(end_raw)
        raw_matrix = read_matrix(capture_path).loc[start:end]
        fold_nav = read_series(fold_nav_path).loc[start:end]
        common = raw_matrix.index.intersection(fold_nav.index)
        raw_matrix = raw_matrix.loc[common]
        fold_nav = fold_nav.loc[common]
        if raw_matrix.empty or fold_nav.empty:
            raise RuntimeError(f"Fold {year} has no overlapping OOS rows")

        # The exporter capture occurs before run_audit applies its fund-level fold
        # normalization. Normalize the entire captured sleeve matrix by the same
        # scalar so its row sum exactly matches the saved fold fund NAV.
        raw_sum = raw_matrix.sum(axis=1)
        capture_to_fold_scale = float(fold_nav.iloc[0]) / float(raw_sum.iloc[0])
        fold_matrix = raw_matrix * capture_to_fold_scale
        fold_delta = float((fold_matrix.sum(axis=1) - fold_nav).abs().max())
        if fold_delta > args.tolerance:
            raise RuntimeError(
                f"Fold {year} normalized matrix does not reconcile to fund NAV; "
                f"max delta={fold_delta}"
            )

        # Match run_core_v1_candidate_wfo.py: compound each independently run
        # annual fold from the previous stitched ending NAV.
        stitch_scale = running_nav / float(fold_nav.iloc[0])
        stitched_fold_matrix = fold_matrix * stitch_scale
        stitched_fold_nav = fold_nav * stitch_scale
        matrix_parts.append(stitched_fold_matrix)
        nav_parts.append(stitched_fold_nav)
        running_nav = float(stitched_fold_nav.iloc[-1])

        audit_rows.append(
            {
                "year": year,
                "rows": len(fold_matrix),
                "capture_to_fold_scale": capture_to_fold_scale,
                "stitch_scale": stitch_scale,
                "fold_reconciliation_delta": fold_delta,
                "ending_nav": running_nav,
            }
        )
        print(
            f"Fold {year}: rows={len(fold_matrix):,} "
            f"capture_scale={capture_to_fold_scale:.8f} "
            f"stitch_scale={stitch_scale:.8f} ending_nav={running_nav:,.2f}"
        )

    stitched_matrix = pd.concat(matrix_parts).sort_index()
    stitched_matrix = stitched_matrix[~stitched_matrix.index.duplicated(keep="last")]
    stitched_nav = pd.concat(nav_parts).sort_index()
    stitched_nav = stitched_nav[~stitched_nav.index.duplicated(keep="last")]

    final_delta = float((stitched_matrix.sum(axis=1) - stitched_nav).abs().max())
    if final_delta > args.tolerance:
        raise RuntimeError(f"Stitched matrix does not reconcile; max delta={final_delta}")

    canonical_path = scenario_dir / "stitched_oos_nav.csv"
    if canonical_path.exists():
        canonical = read_series(canonical_path)
        common = canonical.index.intersection(stitched_nav.index)
        canonical_delta = float((canonical.loc[common] - stitched_nav.loc[common]).abs().max())
        canonical_end_delta = float(canonical.iloc[-1] - stitched_nav.iloc[-1])
        if len(canonical) != len(stitched_nav) or canonical_delta > args.tolerance:
            raise RuntimeError(
                "Finalized sleeve matrix does not reproduce canonical stitched_oos_nav.csv; "
                f"canonical_rows={len(canonical)} matrix_rows={len(stitched_nav)} "
                f"max_common_delta={canonical_delta} end_delta={canonical_end_delta}"
            )
    else:
        canonical_delta = float("nan")

    matrix_path = scenario_dir / "stitched_sleeve_equity_matrix.csv"
    nav_path = scenario_dir / "stitched_fund_nav_from_sleeves.csv"
    audit_path = scenario_dir / "canonical_sleeve_matrix_stitch_audit.csv"
    stitched_matrix.to_csv(matrix_path)
    stitched_nav.rename("fund_nav").to_csv(nav_path, header=True)
    pd.DataFrame(audit_rows).to_csv(audit_path, index=False)

    print()
    print("Canonical Core v1 sleeve matrix finalization complete")
    print(f"Rows: {len(stitched_matrix):,}")
    print(f"Final NAV: {float(stitched_nav.iloc[-1]):,.2f}")
    print(f"Matrix reconciliation delta: {final_delta:.12f}")
    print(f"Canonical NAV delta: {canonical_delta:.12f}")
    print(f"Matrix: {matrix_path}")
    print(f"NAV: {nav_path}")
    print(f"Audit: {audit_path}")


if __name__ == "__main__":
    main()
