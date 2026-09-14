"""CLI for a reproducible exploratory screen; deliberately no OOS/MC command yet."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import zipfile
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .accounting import SCENARIOS, simulate
from .data import ASSETS, EVALUATION_START, download_snapshot, load_snapshot, sha, write_json
from .metrics import pareto_flags, summarize
from .strategies import WARMUP, make_schedules, registry

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/research/FRESH_STRATEGY_DISCOVERY_20260914.md"


def save_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n", float_format="%.12g")


def first_signal(frames: dict[str, pd.DataFrame]) -> int:
    dates = frames["SPY"].index
    first_execution = int(dates.searchsorted(pd.Timestamp(EVALUATION_START)))
    result = first_execution - 1
    if result < WARMUP or first_execution >= len(dates) - 2:
        raise ValueError("Insufficient warmup/evaluation history")
    return result


def mechanics_canary() -> dict:
    """A deliberately invalid self-financing state must fail on every real run."""
    from .accounting import rebalance
    try:
        rebalance(np.array([2.0]), -3.0, np.array([1.0]), .001)
    except ValueError:
        return {"insolvent_accounting_rejected": True}
    raise RuntimeError("Accounting rejection canary failed")


def is_synthetic_identity(value: dict) -> bool:
    """Read explicit labels, never the occurrence of 'synthetic' in JSON keys."""
    if "synthetic_data_used" in value:
        flag = value["synthetic_data_used"]
        if not isinstance(flag, bool):
            raise ValueError("synthetic_data_used must be a boolean")
        return flag
    labels = (value.get("status", ""), value.get("status_label", ""),
              value.get("data", {}).get("status", ""))
    return any(isinstance(label, str) and label.upper().startswith("SYNTHETIC") for label in labels)


def run_screen(frames: dict[str, pd.DataFrame], out: Path, identity: dict) -> dict:
    """Also used by synthetic integration tests; they must label their identity."""
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite run: {out}")
    out.mkdir(parents=True)
    first = first_signal(frames)
    synthetic = is_synthetic_identity(identity)
    identity = dict(identity, status="SYNTHETIC_MECHANICS_ONLY" if synthetic else "EXPLORATORY_SCREEN_NOT_OOS",
                    synthetic_data_used=synthetic,
                    candidate_registry=registry(), scenarios=[asdict(s) for s in SCENARIOS],
                    canary=mechanics_canary(), reserved_2025_used=False,
                    monte_carlo_run=False, fitted_models=0)
    write_json(out / "identity_before_evaluation.json", identity)
    specifications, schedules, targets = make_schedules(frames, first)
    save_csv(targets, out / "target_weights.csv")
    ledgers, attribution = [], []
    for scenario in SCENARIOS:
        for policy in specifications:
            full = simulate(frames, schedules[policy.name], scenario, first)
            if scenario.name == "base":
                for asset in ASSETS:
                    attribution.append(dict(policy=policy.name, asset=asset,
                                            sum_arithmetic_pnl_contributions=float(full[f"{asset}_pnl"].sum()),
                                            mean_weight=float(full[f"{asset}_weight"].mean()),
                                            max_abs_weight=float(full[f"{asset}_weight"].abs().max())))
            ledger = full.drop(columns=[f"{a}_{kind}" for a in ASSETS for kind in ("weight", "pnl")])
            ledger["scenario"], ledger["policy"] = scenario.name, policy.name
            ledgers.append(ledger)
        print(f"{scenario.name}: {len(specifications)} portfolio ledgers reconciled", flush=True)
    daily = pd.concat(ledgers, ignore_index=True)
    save_csv(daily, out / "daily_ledger.csv")
    save_csv(pd.DataFrame(attribution), out / "asset_attribution_base.csv")
    summary, annual, exclusions = summarize(daily)
    summary = pareto_flags(summary)
    roles = {p.name: p.role for p in specifications}
    families = {p.name: p.family for p in specifications}
    summary["role"] = summary.policy.map(roles)
    summary["family"] = summary.policy.map(families)
    save_csv(summary, out / "metrics.csv")
    save_csv(annual, out / "annual_returns.csv")
    save_csv(exclusions, out / "leave_one_year_out.csv")
    base = daily[daily.scenario == "base"].pivot(index="date", columns="policy", values="return")
    correlations = base.corr().rename_axis("policy").reset_index()
    save_csv(correlations, out / "base_return_correlations.csv")
    # All these policy comparisons are exploratory; retain the full return matrix.
    robustness = summary[summary.period == "full"].groupby("policy").agg(
        minimum_scenario_cagr=("cagr", "min"), minimum_scenario_sharpe=("excess_sharpe", "min"),
        worst_scenario_drawdown=("max_drawdown", "min"))
    robustness["worst_year_deletion_sharpe"] = exclusions.groupby("policy").excess_sharpe.min()
    save_csv(robustness.reset_index(), out / "robustness.csv")
    full_base = summary[(summary.scenario == "base") & (summary.period == "full")]
    leaders = full_base[full_base.role == "candidate"].sort_values("excess_sharpe", ascending=False).head(5)
    make_plot(daily, leaders.policy.tolist(), out, synthetic=synthetic)
    label = "SYNTHETIC MECHANICS TEST — NOT MARKET RESULTS" if synthetic else "Fresh strategy discovery — exploratory results"
    lines = ["# " + label, "",
             "This is a development screen, not OOS evidence or a promotion decision.", "",
             "Base case: 5 bps one way, 1% annual short borrow, lagged BIL yield + 1.5% debit financing.",
             "Signals use completed closes and fill at the next session open. Final exit costs are included.",
             "Returns use total initial equity, including cash/collateral, with daily mark-to-market.", "",
             "## Top five candidates by base excess Sharpe (selected for display only)", "",
             "| Policy | CAGR | Excess Sharpe | Max DD | Calmar |", "|---|---:|---:|---:|---:|"]
    for row in leaders.itertuples():
        lines.append(f"| {row.policy} | {row.cagr:.2%} | {row.excess_sharpe:.2f} | {row.max_drawdown:.2%} | {row.calmar:.2f} |")
    lines.extend(["", "All variants and controls: metrics.csv. Read both historical eras, annual returns,",
                  "cost/delay scenarios, exposure, attribution and year-deletion diagnostics before shortlisting.",
                  "The 2008 row is partial. Historical ETF selection and revised adjusted prices limit inference.",
                  "Borrow availability, broker margin, capacity, taxes and opening-auction fills are not verified.",
                  "Asset attribution sums daily arithmetic contributions; it is not compounded wealth attribution.",
                  "", "The screen ranks no single winner automatically. Freeze any proposed candidate before OOS/MC."])
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    report = dict(**identity, policies=len(specifications),
                  candidates=sum(p.role == "candidate" for p in specifications),
                  ledgers=len(ledgers), daily_rows=len(daily),
                  evaluation_first_date=str(daily.date.min()), evaluation_last_date=str(daily.date.max()),
                  max_accounting_residual=float(daily.accounting_residual.abs().max()),
                  files={p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    write_json(out / "report.json", report)
    print("\n" + label + "\nBase-case candidates (exploratory):", flush=True)
    print(leaders[["policy", "cagr", "excess_sharpe", "max_drawdown", "calmar"]].to_string(index=False), flush=True)
    return report


def make_plot(daily: pd.DataFrame, names: list[str], out: Path, *, synthetic: bool = False) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1]}, constrained_layout=True)
    for name in names + ["spy_buy_hold", "bil_buy_hold"]:
        frame = daily[(daily.scenario == "base") & (daily.policy == name)]
        nav = frame.nav.to_numpy()
        dates = pd.to_datetime(frame.date)
        axes[0].plot(dates, nav, label=name, linewidth=1.2)
        peak = np.maximum.accumulate(np.r_[1.0, nav])[1:]
        axes[1].plot(dates, nav / peak - 1, linewidth=1.0)
    title = ("SYNTHETIC MECHANICS TEST — NOT MARKET PERFORMANCE" if synthetic else
             "Exploratory top five by base excess Sharpe; display selection uses the full sample")
    axes[0].set(yscale="log", ylabel="Equity multiple (log scale)", title=title)
    axes[1].set(ylabel="Drawdown", xlabel="Session")
    for ax in axes:
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=7, loc="upper left", ncol=2)
    fig.savefig(out / "equity_drawdown.png", dpi=150)
    plt.close(fig)


def identity(data_identity: dict) -> dict:
    paths = sorted((ROOT / "research/fresh_discovery").glob("*.py")) + [
        SPEC, ROOT / "uv.lock", ROOT / "tests/test_fresh_strategy_discovery.py",
        ROOT / "scripts/local/run_fresh_strategy_discovery.ps1"]
    code = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *code], cwd=ROOT, text=True)
    if dirty.strip():
        raise ValueError("Research code/spec is modified; commit it before recording real results")
    return dict(data=data_identity, code_sha256=code, commit=head,
                environment=dict(python=platform.python_version(),
                                 **{name: importlib.metadata.version(name)
                                    for name in ("numpy", "pandas", "yfinance", "matplotlib")}))


def bundle(out: Path, data_root: Path) -> Path:
    archive = out.with_suffix(".zip")
    if archive.exists():
        raise FileExistsError(archive)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(out.iterdir()):
            if path.is_file():
                z.write(path, "results/" + path.name)
        inputs = [data_root / "snapshot.json"]
        inputs.extend(data_root / f"{a}.{suffix}" for a in ASSETS for suffix in ("csv", "json"))
        for path in sorted(inputs):
            z.write(path, "inputs/" + path.name)
        z.write(SPEC, "specification.md")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--download", action="store_true", help="Create/resume an immutable pre-2025 data snapshot")
    args = parser.parse_args()
    if not args.download and args.output_dir is None:
        parser.error("Supply --download and/or --output-dir")
    if args.download:
        download_snapshot(args.data_root)
    if args.output_dir is not None:
        frames, data_identity = load_snapshot(args.data_root)
        run_screen(frames, args.output_dir, identity(data_identity))
        archive = bundle(args.output_dir, args.data_root)
        print(f"\nSHARE THIS FILE: {archive.resolve()}", flush=True)


if __name__ == "__main__":
    main()
