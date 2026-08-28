"""Core v1 frozen-parameter sensitivity pass — REPORT ONLY.

Core v1's canonical parameters were selected by an iterative, pre-governance
process (trend_following v1-v11 including a cap grid, equity_sma175 v1-v3 with
episode-motivated amendments, and an allocation scenario comparison). The
resulting backtest is therefore the maximum of a substantial implicit search,
as recorded in `docs/research/CORE_V1_LIVE_EXPECTATION_AND_DEGRADATION_BAND.md`.

This pass asks one question: **does that result sit on a knife edge?** A
strategy whose performance collapses under a small parameter perturbation is
fitted to its sample. A strategy whose performance degrades smoothly and
survives nearby values is expressing a real effect, whatever its selection
history.

THIS SCRIPT IS REPORT-ONLY AND MUST REMAIN SO.

The output is evidence about fragility, not a search for better parameters.
Selecting a perturbed variant because it scored higher would repeat exactly
the process that created the problem, on the same data, and would invalidate
both the live record and the degradation band. Under
`docs/ITERA_DESTINATION_CHARTER.md` the canonical parameters may change only
through full governance, and a higher number in this table is not a finding.

Method: one-at-a-time perturbation of the frozen strategy constants. Each
variant reruns the full canonical walk-forward via the existing fold machinery
in `scripts/export_core_v1_canonical_sleeve_matrix.py`, with the constants
patched in the fold subprocess. Everything else -- weights, costs, calendars,
data -- is held identical to canonical.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.export_core_v1_canonical_sleeve_matrix import _read_series  # noqa: E402
from scripts.run_core_v1_candidate_wfo import SCENARIOS, years  # noqa: E402

CANONICAL_SCENARIO = "candidate_btc1h_hedges_to_btc4h_gld_qqq"

# (label, module, constant, canonical value, perturbed values)
# Chosen for genuine overfitting risk: values with no a priori justification,
# or introduced in response to specific historical episodes.
PERTURBATIONS: list[tuple[str, str, str, Any, list[Any]]] = [
    ("equity_sma_period", "research.strategies.equity_sma175_v3", "SMA_PERIOD", 175, [150, 200]),
    ("equity_fast_sma", "research.strategies.equity_sma175_v3", "FAST_SMA_PERIOD", 50, [40, 60]),
    ("equity_derisk_exposure", "research.strategies.equity_sma175_v3", "DERISKED_EXPOSURE", 0.50, [0.40, 0.60]),
    ("equity_entry_buffer", "research.strategies.equity_sma175_v3", "ENTRY_BUFFER", 0.005, [0.0025, 0.0100]),
    ("gold_sma_period", "research.strategies.gold_sma_v1", "SMA_PERIOD", 200, [175, 225]),
    ("v11_soft_threshold", "research.strategies.trend_following_v11", "SOFT_THRESHOLD", 0.60, [0.45, 0.75]),
    ("v11_hard_threshold", "research.strategies.trend_following_v11", "HARD_THRESHOLD", 1.00, [0.85, 1.15]),
    ("v11_soft_entry_cap", "research.strategies.trend_following_v11", "SOFT_ENTRY_CAP", 0.40, [0.30, 0.50]),
    ("v11_para_sma_days", "research.strategies.trend_following_v11", "PARA_SMA_DAYS", 365, [300, 430]),
    ("v9_sma_days", "research.strategies.trend_following_v9", "SMA_DAYS", 175, [150, 200]),
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Report-only sensitivity of Core v1 to its frozen parameters.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
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
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--out-dir", default="artifacts/core_v1_parameter_sensitivity")
    p.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Run only these perturbation labels (default: all). Baseline always runs.",
    )
    return p.parse_args(argv)


def fold_script(
    args: argparse.Namespace,
    variant_dir: Path,
    year: str,
    start: str,
    end: str,
    patch: tuple[str, str, Any] | None,
) -> Path:
    """Write the per-fold subprocess, optionally patching one strategy constant."""
    fold_dir = variant_dir / "folds" / year
    fold_dir.mkdir(parents=True, exist_ok=True)
    capture = fold_dir / "canonical_full_sleeve_equity_matrix.csv"
    weights = SCENARIOS[CANONICAL_SCENARIO]

    patch_lines = ""
    if patch is not None:
        module, constant, value = patch
        patch_lines = (
            f"import importlib\n"
            f"_m = importlib.import_module({module!r})\n"
            f"setattr(_m, {constant!r}, {value!r})\n"
        )

    script = fold_dir / "run_fold_sensitivity.py"
    script.write_text(
        f'''
from argparse import Namespace
from pathlib import Path
import sys

sys.path.insert(0, r"{REPO_ROOT}")

{patch_lines}
import scripts.run_core_v1_sleeve_contribution_audit as audit
from scripts.run_multi_strategy_fund import _build_sleeves as base_build

WEIGHTS = {weights!r}
CAPTURE_PATH = Path(r"{capture}")


def custom_build_sleeves(args):
    specs = base_build(args)
    out = []
    for spec in specs:
        spec.capital = args.capital * WEIGHTS.get(spec.label, 0.0)
        if spec.capital > 0:
            out.append(spec)
    return out


_original_align = audit.align_equity_curves
_count = 0


def capture_first(curves, base_freq="1h"):
    global _count
    aligned = _original_align(curves, base_freq=base_freq)
    _count += 1
    if _count == 1:
        CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        aligned.to_csv(CAPTURE_PATH)
    return aligned


audit._build_sleeves = custom_build_sleeves
audit.align_equity_curves = capture_first

args = Namespace(
    btc_data=r"{args.btc_data}", eth_data=r"{args.eth_data}",
    spy_data=r"{args.spy_data}", qqq_data=r"{args.qqq_data}",
    bil_data=r"{args.bil_data}", gld_data=r"{args.gld_data}",
    capital=100000.0, trend_weight=0.40, equity_weight=0.35,
    gold_weight=0.15, hedge_weight=0.10, mr_weight=0.00,
    data_start="{args.data_start}", oos_start="{start}", oos_end="{end}",
    fee={args.fee}, equity_fee={args.equity_fee},
    base_slippage={args.base_slippage},
    slippage_vol_factor={args.slippage_vol_factor},
    cooldown=2, mr_cooldown=12, rebalance_threshold=0.02,
    out_dir=r"{fold_dir}",
)

audit.run_audit(args)
''',
        encoding="utf-8",
    )
    return script


def metrics_from_nav(label: str, nav: pd.Series) -> dict[str, Any]:
    """Scorecard metrics for one chained variant NAV.

    Factored out so that a partial run can be summarised from the per-variant
    ``nav.csv`` files alone (see ``scripts/peek_parameter_sensitivity.py``)
    under exactly these definitions, rather than a second implementation that
    could drift from the final table.
    """
    total_return = float(nav.iloc[-1]) / 100000.0 - 1.0
    elapsed_days = max((nav.index[-1] - nav.index[0]).days, 1)
    cagr = (float(nav.iloc[-1]) / 100000.0) ** (365.25 / elapsed_days) - 1.0
    peak = nav.cummax()
    max_dd = float((nav / peak - 1.0).min())
    daily = nav.resample("D").last().dropna()
    rets = daily.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * (365.25 ** 0.5)) if rets.std() > 0 else float("nan")
    calmar = cagr / abs(max_dd) if max_dd < 0 else float("nan")

    return {
        "variant": label,
        "final_nav": round(float(nav.iloc[-1]), 2),
        "total_return_pct": round(total_return * 100, 4),
        "cagr_pct": round(cagr * 100, 4),
        "sharpe": round(sharpe, 4),
        "calmar": round(calmar, 4),
        "max_drawdown_pct": round(max_dd * 100, 4),
    }


def run_variant(
    args: argparse.Namespace,
    out_dir: Path,
    label: str,
    patch: tuple[str, str, Any] | None,
) -> dict[str, Any]:
    variant_dir = out_dir / label
    folds = years(args.oos_start, args.oos_end)

    def one(year: str, start: str, end: str) -> str:
        script = fold_script(args, variant_dir, year, start, end, patch)
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        (script.parent / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
        if proc.returncode:
            raise RuntimeError(f"{label} fold {year} failed; see {script.parent / 'stderr.txt'}")
        return year

    workers = max(1, min(args.workers, len(folds)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, y, s, e) for y, s, e in folds]
        for future in as_completed(futures):
            future.result()

    # Chain the fold NAVs exactly as the canonical export does.
    running = 100000.0
    navs: list[pd.Series] = []
    for year, _, _ in folds:
        nav = _read_series(variant_dir / "folds" / year / "stitched_fund_nav_from_sleeves.csv")
        scale = running / float(nav.iloc[0])
        scaled = nav * scale
        navs.append(scaled)
        running = float(scaled.iloc[-1])

    nav = pd.concat(navs).sort_index()
    nav = nav[~nav.index.duplicated(keep="last")]
    nav.to_csv(variant_dir / "nav.csv", header=True)

    return metrics_from_nav(label, nav)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir) / f"{timestamp}_core-v1-parameter-sensitivity"
    out_dir.mkdir(parents=True, exist_ok=False)

    selected = PERTURBATIONS
    if args.only:
        selected = [p for p in PERTURBATIONS if p[0] in set(args.only)]
        if not selected:
            raise SystemExit(f"No perturbations matched {args.only}")

    jobs: list[tuple[str, tuple[str, str, Any] | None]] = [("baseline", None)]
    for label, module, constant, canonical, values in selected:
        for value in values:
            jobs.append((f"{label}={value}", (module, constant, value)))

    print(f"Core v1 parameter sensitivity — REPORT ONLY")
    print(f"{len(jobs)} variants (baseline + {len(jobs)-1} perturbations), "
          f"{len(years(args.oos_start, args.oos_end))} folds each\n")

    rows: list[dict[str, Any]] = []
    for index, (label, patch) in enumerate(jobs, start=1):
        print(f"[{index}/{len(jobs)}] {label}")
        rows.append(run_variant(args, out_dir, label.replace("=", "_"), patch))
        rows[-1]["variant"] = label

    frame = pd.DataFrame(rows)
    base = frame.loc[frame["variant"] == "baseline"].iloc[0]
    for metric in ("cagr_pct", "sharpe", "calmar", "max_drawdown_pct"):
        frame[f"delta_{metric}"] = (frame[metric] - base[metric]).round(4)
    frame.to_csv(out_dir / "sensitivity_scorecard.csv", index=False)

    perturbed = frame.loc[frame["variant"] != "baseline"]
    summary = {
        "audit": "core_v1_parameter_sensitivity_v1",
        "report_only": True,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline": {
            "cagr_pct": float(base["cagr_pct"]),
            "sharpe": float(base["sharpe"]),
            "calmar": float(base["calmar"]),
            "max_drawdown_pct": float(base["max_drawdown_pct"]),
        },
        "variants": len(perturbed),
        "sharpe_range": [float(perturbed["sharpe"].min()), float(perturbed["sharpe"].max())],
        "cagr_range_pct": [float(perturbed["cagr_pct"].min()), float(perturbed["cagr_pct"].max())],
        "max_drawdown_range_pct": [
            float(perturbed["max_drawdown_pct"].min()),
            float(perturbed["max_drawdown_pct"].max()),
        ],
        "worst_sharpe_variant": str(perturbed.loc[perturbed["sharpe"].idxmin(), "variant"]),
        "baseline_is_best_sharpe": bool(base["sharpe"] >= perturbed["sharpe"].max()),
        "note": (
            "Report only. A perturbed variant scoring higher is not a finding and must not be "
            "adopted; doing so would repeat the selection process that produced the original "
            "overfitting concern, on the same data."
        ),
    }
    (out_dir / "sensitivity_report.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print("\n" + "=" * 78)
    header = f"{'variant':<28}{'CAGR%':>9}{'Sharpe':>9}{'Calmar':>9}{'MaxDD%':>9}{'dSharpe':>9}"
    print(header)
    print("-" * len(header))
    for _, row in frame.iterrows():
        print(
            f"{row['variant']:<28}{row['cagr_pct']:>9.2f}{row['sharpe']:>9.3f}"
            f"{row['calmar']:>9.3f}{row['max_drawdown_pct']:>9.2f}{row['delta_sharpe']:>9.3f}"
        )
    print("=" * 78)
    print(f"\nSharpe across perturbations: {summary['sharpe_range'][0]:.3f} .. "
          f"{summary['sharpe_range'][1]:.3f}  (baseline {base['sharpe']:.3f})")
    print(f"Worst variant: {summary['worst_sharpe_variant']}")
    print(f"\nArtifacts: {out_dir}")
    print("\nREPORT ONLY — do not adopt a higher-scoring variant. See module docstring.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
