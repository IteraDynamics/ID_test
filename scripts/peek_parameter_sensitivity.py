"""Preliminary read of an in-flight parameter sensitivity run — REPORT ONLY.

`scripts/run_core_v1_parameter_sensitivity.py` writes its scorecard only after
all variants complete, which is several hours. Each variant does, however,
write `nav.csv` the moment it finishes. This reads those files and reports the
same metrics under the same definitions (imported, not reimplemented), plus
per-variant wall times and a projected finish.

Strictly read-only: opens completed `nav.csv` files, writes nothing, holds no
locks, and cannot interfere with a running job. Safe to run repeatedly while
the parent run is still going.

The governance in the parent module applies unchanged and with full force: a
perturbed variant scoring above baseline is NOT a finding and must not be
adopted. Partial results are weaker still, because the variants completed so
far are ordered by the perturbation list, not by anything meaningful -- reading
a trend into the first N rows is reading a trend into an arbitrary ordering.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_core_v1_parameter_sensitivity import (  # noqa: E402
    PERTURBATIONS,
    metrics_from_nav,
)

# Run directories are named "<UTC timestamp>_core-v1-parameter-sensitivity".
RUN_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Summarise a partial parameter sensitivity run.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--out-dir", default="artifacts/core_v1_parameter_sensitivity")
    p.add_argument("--run", default=None, help="Run directory name (default: most recent).")
    return p.parse_args(argv)


def expected_variant_count() -> int:
    return 1 + sum(len(values) for _, _, _, _, values in PERTURBATIONS)


def run_started_utc(run_dir: Path) -> datetime | None:
    stamp = run_dir.name.split("_", 1)[0]
    try:
        return datetime.strptime(stamp, RUN_STAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load_nav(path: Path) -> pd.Series:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    return frame.iloc[:, 0]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.out_dir)
    if not root.exists():
        raise SystemExit(f"No sensitivity artifacts at {root}")

    if args.run:
        run_dir = root / args.run
    else:
        runs = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda d: d.name)
        if not runs:
            raise SystemExit(f"No run directories under {root}")
        run_dir = runs[-1]

    navs = sorted(run_dir.glob("*/nav.csv"), key=lambda p: p.stat().st_mtime)
    if not navs:
        raise SystemExit(f"No completed variants yet in {run_dir}")

    total = expected_variant_count()
    started = run_started_utc(run_dir)

    rows = []
    previous = started
    for path in navs:
        # The variant directory name has "=" replaced by "_" by the parent runner.
        label = path.parent.name
        finished = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        minutes = (finished - previous).total_seconds() / 60.0 if previous else float("nan")
        previous = finished
        row = metrics_from_nav(label, load_nav(path))
        row["minutes"] = round(minutes, 1)
        rows.append(row)

    frame = pd.DataFrame(rows)
    baseline = frame.loc[frame["variant"] == "baseline"]
    if not baseline.empty:
        base = baseline.iloc[0]
        for metric in ("cagr_pct", "sharpe", "calmar", "max_drawdown_pct"):
            frame[f"delta_{metric}"] = (frame[metric] - base[metric]).round(4)

    print(f"Run: {run_dir.name}")
    print(f"Completed: {len(frame)} of {total} variants\n")

    header = (
        f"{'variant':<28}{'CAGR%':>9}{'Sharpe':>9}{'Calmar':>9}"
        f"{'MaxDD%':>9}{'dSharpe':>9}{'min':>8}"
    )
    print(header)
    print("-" * len(header))
    for _, row in frame.iterrows():
        delta = row.get("delta_sharpe")
        print(
            f"{str(row['variant'])[:28]:<28}{row['cagr_pct']:>9.2f}{row['sharpe']:>9.3f}"
            f"{row['calmar']:>9.3f}{row['max_drawdown_pct']:>9.2f}"
            f"{(f'{delta:+.3f}' if delta is not None else '-'):>9}"
            f"{row['minutes']:>8.1f}"
        )
    print("-" * len(header))

    timed = frame["minutes"].dropna()
    if not timed.empty and len(frame) < total:
        median = float(timed.median())
        remaining = total - len(frame)
        print(
            f"\nMedian variant: {median:.1f} min. "
            f"{remaining} remaining -> ~{median * remaining / 60.0:.1f} h "
            f"(projection assumes uniform variant cost)."
        )

    if not baseline.empty and len(frame) > 1:
        perturbed = frame.loc[frame["variant"] != "baseline"]
        print(
            f"\nSharpe so far: {perturbed['sharpe'].min():.3f} .. "
            f"{perturbed['sharpe'].max():.3f} against baseline {base['sharpe']:.3f}"
        )
    else:
        print("\nBaseline not yet complete; deltas unavailable.")

    print(
        "\nPRELIMINARY AND REPORT ONLY. Variants complete in perturbation-list order, "
        "not in any order that carries meaning. Do not adopt a higher-scoring variant, "
        "and do not read the partial set as a result."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
