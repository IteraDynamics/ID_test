"""Run this fixed discovery batch; no OOS evaluation or Monte Carlo in phase one."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import zipfile
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .data import SCORE_START, acquire, digest, load_panel, write_json
from .engine import SCENARIOS, InsolventError, simulate
from .metrics import metrics, pareto
from .signals import registry, targets


def git_state() -> dict:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], text=True).strip()
    return {"commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
            "tracked_changes": git("status", "--porcelain", "--untracked-files=no")}


def csv_bytes(frame: pd.DataFrame, index: bool = True) -> bytes:
    return frame.to_csv(index=index, lineterminator="\n", float_format="%.12g").encode("utf-8")


def render_report(summary: pd.DataFrame, output: Path, counts: dict) -> None:
    rows = summary[(summary["scenario"] == "base_2bps") & (summary["status"] == "completed")]
    rows = rows.sort_values(["sharpe_hac20", "cagr"], ascending=False)
    lines = [
        "# Fresh strategy lab — exploratory results",
        "",
        "These are development results, not independent OOS evidence.",
        "All returns use total account equity, including idle cash. Percentages below are net.",
        "The complete search, costs and exposure variants are retained in the CSVs.",
        "No automatic promotion decision is made from the best discovered cell.",
        "",
        f"Completed ledgers: {counts['completed']}; insolvent ledgers: {counts['insolvent']}.",
        "",
        "## Base scenario: 2 bps per dollar traded",
        "",
        "| Candidate | Gross budget | CAGR | Sharpe | HAC Sharpe | Max DD | Calmar | Pareto |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    def number(value: object, percent: bool = False) -> str:
        if pd.isna(value):
            return "NA"
        return f"{float(value):.2%}" if percent else f"{float(value):.2f}"
    for _, row in rows.head(30).iterrows():
        lines.append(
            f"| {row['candidate']} | {row['gross_budget']:.0f}x | "
            f"{number(row['cagr'], True)} | {number(row['sharpe'])} | "
            f"{number(row['sharpe_hac20'])} | {number(row['max_drawdown'], True)} | "
            f"{number(row['calmar'])} | {bool(row['pareto'])} |"
        )
    lines += [
        "", "## What to inspect before advancing", "",
        "- Compare each family with its matching benchmark and its parameter neighbors.",
        "- Require the return/drawdown tradeoff to remain useful under cost and delay stress.",
        "- Check yearly results, best-five-day dependence, exposure and asset P&L concentration.",
        "- Use the return matrix to assess diversification before choosing ensemble weights.",
        "- Freeze a small shortlist only after this review; establish an eligible later sample.",
        "- Block-bootstrap Monte Carlo can stress path risk later; it cannot create OOS evidence.",
        "",
        "Maximum drawdown includes observed opens and closes, not intraday extrema.",
        "HAC Sharpe uses 20 Bartlett lags; it is descriptive, not a significance test or a",
        "multiple-search correction. Gross budgets can drift at fills because share quantities",
        "are fixed at the prior close. The baseline cash/risk-free rate is zero.",
        "Financing/borrow inputs are stated scenarios, not verified broker quotes.",
        "The data are current vendor history, not archived point-in-time observations.",
        "",
        "Files: summary.csv, yearly.csv, net_returns.csv, candidate_correlation.csv,",
        "family_summary.csv, report.json, and ledgers.zip (every simulated ledger).",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run(data_dir: Path, output: Path, reuse_data: bool = False) -> Path:
    if output.exists():
        raise FileExistsError(f"Output exists: {output}")
    output.mkdir(parents=True)
    # Record the planned search before any market results are calculated.
    candidates = registry()
    identity = {
        "status": "running", "stage": "exploratory_development",
        "git": git_state(), "score_start": SCORE_START, "last_scored_year": 2023,
        "excluded_from_this_batch": "2024 onward; prior use prevents assuming pristine OOS",
        "gross_budgets": [1.0, 2.0], "candidates": [c.record() for c in candidates],
        "scenarios": [asdict(s) for s in SCENARIOS],
        "research_candidate_count": sum(not c.benchmark for c in candidates),
        "benchmark_count": sum(c.benchmark for c in candidates),
        "planned_ledgers": len(candidates) * 2 * len(SCENARIOS),
        "python": platform.python_version(),
        "packages": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "yfinance")},
        "source_hashes": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "scope": "simulation only; no runtime/strategy registry or account integration",
        "oos_run": False, "monte_carlo_run": False,
        "selection_adjustment": "none; all rankings explicitly exploratory",
        "annualization": "252 sessions, compounded CAGR; mean and variance annualized by 252",
        "ce_definition": "252*mean(net daily return) - 1.5*252*sample_variance; gamma=3",
        "return_denominator": "total marked account equity; initial normalized NAV 1",
    }
    write_json(output / "identity_before_results.json", identity)
    if not reuse_data:
        acquire(data_dir)
    panel, source = load_panel(data_dir)
    write_json(output / "source_audit.json", source)
    summary_rows, year_rows, return_columns = [], [], {}
    completed = insolvent = replays = 0
    with zipfile.ZipFile(output / "ledgers.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for ci, candidate in enumerate(candidates, 1):
            print(f"[{ci}/{len(candidates)}] {candidate.name}", flush=True)
            target = targets(panel, candidate)
            target_hash = hashlib.sha256(csv_bytes(target)).hexdigest()
            for gross in (1.0, 2.0):
                for scenario in SCENARIOS:
                    key = f"{candidate.name}__g{gross:g}__{scenario.name}"
                    info = {"candidate": candidate.name, "family": candidate.family,
                            "benchmark": candidate.benchmark, "gross_budget": gross,
                            "scenario": scenario.name, "target_sha256": target_hash}
                    try:
                        ledger = simulate(panel, target, candidate.mode, gross, scenario, SCORE_START)
                    except InsolventError as error:
                        summary_rows.append({**info, "status": "insolvent", "failure": str(error)})
                        insolvent += 1
                        continue
                    payload = csv_bytes(ledger)
                    if scenario.name == "base_2bps":
                        replay = simulate(panel, target, candidate.mode, gross, scenario, SCORE_START)
                        if payload != csv_bytes(replay):
                            raise ArithmeticError(f"{key}: deterministic replay mismatch")
                        replays += 1
                    archive.writestr(key + ".csv", payload)
                    summary_rows.append({**info, "status": "completed", **metrics(ledger),
                                         "ledger_sha256": hashlib.sha256(payload).hexdigest()})
                    return_columns[key] = ledger["net_return"]
                    for year, group in ledger.groupby(ledger.index.year):
                        if len(group) >= 2:
                            year_rows.append({**info, "year": int(year), **metrics(group)})
                    completed += 1
    summary = pd.DataFrame(summary_rows)
    summary["pareto"] = False
    valid = summary["status"] == "completed"
    for _, indices in summary[valid].groupby(["scenario", "gross_budget"]).groups.items():
        summary.loc[indices, "pareto"] = pareto(summary.loc[indices])
    summary.to_csv(output / "summary.csv", index=False, lineterminator="\n")
    pd.DataFrame(year_rows).to_csv(output / "yearly.csv", index=False, lineterminator="\n")
    returns = pd.DataFrame(return_columns)
    returns.to_csv(output / "net_returns.csv", lineterminator="\n", float_format="%.12g")
    base_keys = [k for k in returns if k.endswith("__g1__base_2bps")]
    returns[base_keys].corr().to_csv(output / "candidate_correlation.csv", lineterminator="\n")
    base = summary[valid & (summary["scenario"] == "base_2bps") & ~summary["benchmark"]]
    if not base.empty:
        family = base.groupby(["family", "gross_budget"]).agg(
            candidates=("candidate", "size"), median_cagr=("cagr", "median"),
            min_cagr=("cagr", "min"), max_cagr=("cagr", "max"),
            median_sharpe=("sharpe_hac20", "median"),
            median_drawdown=("max_drawdown", "median"),
        )
        family.to_csv(output / "family_summary.csv", lineterminator="\n")
    else:
        (output / "family_summary.csv").write_text("family,gross_budget,candidates\n", encoding="utf-8")
    counts = {"completed": completed, "insolvent": insolvent, "byte_identical_replays": replays}
    render_report(summary, output, counts)
    identity.update(status="completed", counts=counts,
                    outputs={p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()})
    write_json(output / "report.json", identity)
    bundle = output.with_suffix(".zip")
    if bundle.exists():
        raise FileExistsError(f"Bundle already exists: {bundle}")
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path.is_file():
                archive.write(path, arcname=f"{output.name}/{path.name}")
    print(f"\nDone. Share this results bundle:\n{bundle.resolve()}", flush=True)
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reuse-data", action="store_true",
                        help="Verify and reuse the existing fixed-window snapshot without downloading")
    args = parser.parse_args()
    run(args.data_dir, args.output_dir, args.reuse_data)


if __name__ == "__main__":
    main()
