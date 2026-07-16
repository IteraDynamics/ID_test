from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_SCENARIO = "candidate_btc1h_hedges_to_btc4h_gld_qqq"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruct a stitched Core v1 sleeve matrix from completed yearly WFO fold artifacts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--core-wfo-dir",
        default="artifacts/trend_persistence_v0/portfolio_integration/core_wfo",
    )
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO)
    parser.add_argument("--initial-capital", type=float, default=100000.0)
    return parser.parse_args()


def _read_matrix(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    frame = frame.apply(pd.to_numeric, errors="coerce").sort_index().ffill().dropna(how="all")
    if frame.empty:
        raise ValueError(f"Empty sleeve matrix: {path}")
    return frame


def main() -> None:
    args = parse_args()
    scenario_dir = Path(args.core_wfo_dir) / args.scenario
    folds_dir = scenario_dir / "folds"
    if not folds_dir.exists():
        raise FileNotFoundError(f"Missing fold directory: {folds_dir}")

    fold_dirs = sorted(path for path in folds_dir.iterdir() if path.is_dir())
    if not fold_dirs:
        raise FileNotFoundError(f"No completed fold directories found under {folds_dir}")

    running_nav = float(args.initial_capital)
    matrix_parts: list[pd.DataFrame] = []
    nav_parts: list[pd.Series] = []

    for fold_dir in fold_dirs:
        matrix_path = fold_dir / "stitched_sleeve_equity_matrix.csv"
        nav_path = fold_dir / "stitched_fund_nav_from_sleeves.csv"
        if not matrix_path.exists() or not nav_path.exists():
            raise FileNotFoundError(
                f"Fold {fold_dir.name} is missing required outputs: {matrix_path}, {nav_path}"
            )

        matrix = _read_matrix(matrix_path)
        fold_nav = matrix.sum(axis=1).dropna()
        if fold_nav.empty or float(fold_nav.iloc[0]) == 0.0:
            raise ValueError(f"Invalid fold NAV reconstructed from {matrix_path}")

        scale = running_nav / float(fold_nav.iloc[0])
        scaled_matrix = matrix * scale
        scaled_nav = scaled_matrix.sum(axis=1)
        scaled_nav.name = "fund_nav"

        matrix_parts.append(scaled_matrix)
        nav_parts.append(scaled_nav)
        running_nav = float(scaled_nav.iloc[-1])

        print(
            f"Fold {fold_dir.name}: rows={len(scaled_matrix):,} "
            f"scale={scale:.8f} ending_nav={running_nav:,.2f}"
        )

    stitched_matrix = pd.concat(matrix_parts).sort_index()
    stitched_matrix = stitched_matrix[~stitched_matrix.index.duplicated(keep="last")]
    stitched_nav = pd.concat(nav_parts).sort_index()
    stitched_nav = stitched_nav[~stitched_nav.index.duplicated(keep="last")]

    matrix_out = scenario_dir / "stitched_sleeve_equity_matrix.csv"
    nav_out = scenario_dir / "stitched_fund_nav_from_sleeves.csv"
    stitched_matrix.to_csv(matrix_out)
    stitched_nav.to_csv(nav_out, header=True)

    print()
    print("Core v1 sleeve matrix reconstruction complete")
    print(f"Scenario dir: {scenario_dir}")
    print(f"Rows: {len(stitched_matrix):,}")
    print(f"Sleeves: {list(stitched_matrix.columns)}")
    print(f"Final NAV: {float(stitched_nav.iloc[-1]):,.2f}")
    print(f"Matrix: {matrix_out}")
    print(f"NAV: {nav_out}")


if __name__ == "__main__":
    main()
