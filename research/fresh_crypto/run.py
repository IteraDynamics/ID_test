"""Local-first BTC/ETH discovery. No OOS, model fitting, or automatic promotion."""
from __future__ import annotations

import argparse
import importlib.metadata
import platform
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from research.fresh_discovery.data import sha, write_json
from .data import load_inputs
from .engine import SCENARIOS, metrics, policies, registry, schedules, simulate

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/research/FRESH_CRYPTO_DISCOVERY_20260914.md"


def csv(frame):
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.17g")


def identity():
    paths = sorted((ROOT / "research/fresh_crypto").glob("*.py")) + [
        ROOT / "research/fresh_discovery/accounting.py", ROOT / "research/fresh_discovery/data.py",
        ROOT / "tests/test_fresh_crypto_discovery.py", ROOT / "scripts/local/run_fresh_crypto_discovery.ps1",
        ROOT / "uv.lock", ROOT / "pyproject.toml", SPEC]
    relative = [p.relative_to(ROOT).as_posix() for p in paths]
    state = subprocess.check_output(["git", "status", "--porcelain", "--", *relative], cwd=ROOT, text=True)
    if state.strip():
        raise ValueError("Commit the research code/spec before recording a market run")
    return dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                code_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in paths},
                environment=dict(python=platform.python_version(), **{p: importlib.metadata.version(p)
                                 for p in ("numpy", "pandas")}),
                synthetic_data_used=False)


def evaluate(frames, out, run_identity):
    if not isinstance(run_identity.get("synthetic_data_used"), bool):
        raise ValueError("An explicit synthetic_data_used boolean is required")
    synthetic = run_identity["synthetic_data_used"]
    label = "SYNTHETIC_MECHANICS_ONLY" if synthetic else "EXPLORATORY_CRYPTO_SCREEN_NOT_OOS"
    run_identity = dict(run_identity, status=label, candidate_registry=registry(), scenarios=SCENARIOS,
                        cash_yield=0., annualization_days=365, reserved_2025_used=False,
                        monte_carlo_run=False, full_day_signal_latency=True)
    write_json(out / "identity_before_evaluation.json", run_identity)
    # A rejection canary must fire on every run, independently of synthetic tests.
    from .engine import size
    try:
        size(np.array([1., 1.]), np.eye(2), None)
    except ValueError:
        pass
    else:
        raise RuntimeError("Invalid leverage rejection canary failed")
    orders, targets = schedules(frames)
    replay_orders, replay_targets = schedules(frames)
    if csv(targets) != csv(replay_targets):
        raise RuntimeError("Target generation replay mismatch")
    (out / "target_weights.csv").write_text(csv(targets), encoding="utf-8", newline="\n")
    ledgers, summaries, annual = [], [], []
    for scenario, bps, delay in SCENARIOS:
        for policy in policies():
            ledger = simulate(frames, orders[policy.name], bps, delay)
            replay = simulate(frames, replay_orders[policy.name], bps, delay)
            if csv(ledger) != csv(replay):
                raise RuntimeError(f"Replay mismatch: {scenario}/{policy.name}")
            ledger["scenario"], ledger["policy"] = scenario, policy.name
            ledgers.append(ledger)
            for period, sub in (("full", ledger),
                                ("through_2020", ledger[ledger.date < "2021-01-01"]),
                                ("2021_2024", ledger[ledger.date >= "2021-01-01"])):
                if len(sub) >= 180:
                    summaries.append(dict(policy=policy.name, family=policy.family, role=policy.role,
                                          scenario=scenario, period=period, observations=len(sub),
                                          first_date=sub.date.iloc[0], last_date=sub.date.iloc[-1], **metrics(sub)))
            for year, sub in ledger.groupby(ledger.date.str[:4]):
                annual.append(dict(policy=policy.name, scenario=scenario, year=int(year),
                                   observations=len(sub), total_return=float((1+sub["return"]).prod()-1)))
        print(f"{scenario}: 16 ledgers reconciled and replayed exactly", flush=True)
    daily = pd.concat(ledgers, ignore_index=True)
    summary = pd.DataFrame(summaries)
    summary["pareto_cagr_sharpe_drawdown"] = False
    for _, group in summary.groupby(["scenario", "period"]):
        points = group[["cagr", "cash_excess_sharpe", "max_drawdown"]].to_numpy()
        for j, idx in enumerate(group.index):
            if np.isfinite(points[j]).all():
                dominates = (points >= points[j]).all(axis=1) & (points > points[j]).any(axis=1)
                summary.loc[idx, "pareto_cagr_sharpe_drawdown"] = not dominates.any()
    (out / "daily_ledger.csv").write_text(csv(daily), encoding="utf-8", newline="\n")
    (out / "metrics.csv").write_text(csv(summary), encoding="utf-8", newline="\n")
    (out / "annual_returns.csv").write_text(csv(pd.DataFrame(annual)), encoding="utf-8", newline="\n")
    correlations = daily[daily.scenario == "base"].pivot(index="date", columns="policy", values="return").corr()
    correlations.to_csv(out / "base_return_correlations.csv", lineterminator="\n", float_format="%.17g")
    comparisons = []
    for row in summary[summary.role == "candidate"].itertuples():
        suffix = row.policy.rsplit("_", 1)[1]
        control = summary[(summary.policy == f"equal_weight_{suffix}") &
                          (summary.scenario == row.scenario) & (summary.period == row.period)].iloc[0]
        comparisons.append(dict(policy=row.policy, control=control.policy, period=row.period, scenario=row.scenario,
                                cagr_difference=row.cagr-control.cagr,
                                sharpe_difference=row.cash_excess_sharpe-control.cash_excess_sharpe,
                                drawdown_difference=row.max_drawdown-control.max_drawdown,
                                volatility_difference=row.annual_volatility-control.annual_volatility))
    (out / "matched_control_comparisons.csv").write_text(csv(pd.DataFrame(comparisons)), encoding="utf-8", newline="\n")
    base = summary[(summary.scenario == "base") & (summary.period == "full")]
    lines = [f"# {label}", "", "Nine candidates, three allocation controls, four benchmarks; four scenarios.",
             "All results are exploratory. No model fits, OOS evaluation, or Monte Carlo promotion.", "",
             "Base: 30 bps one way. Stress: 75 bps. These are assumptions, not verified fee tiers.",
             "USD cash earns zero; spot only, no leverage, staking, lending, funding or short sales.",
             "Signal bar close is available next UTC midnight; execution is one further day later.",
             "Final exit is the 2024-12-31 open. Drawdown uses daily marks, not intraday extremes.", "",
             "| Policy | CAGR | Cash-excess Sharpe | Max DD | Realized vol |", "|---|---:|---:|---:|---:|"]
    for row in base.itertuples():
        lines.append(f"| {row.policy} | {row.cagr:.2%} | {row.cash_excess_sharpe:.2f} | {row.max_drawdown:.2%} | {row.annual_volatility:.2%} |")
    lines.extend(["", "Compare candidates with the same-profile equal-weight control AND all buy-and-hold benchmarks.",
                  "Matching the sizing rule does not ensure identical realized volatility. Inspect exposure and turnover.",
                  "Raw cash-excess crypto Sharpe is not directly comparable to the earlier BIL-excess ETF screen.",
                  "Annual returns, early/late periods, costs, delayed fills and every trial are retained.",
                  "BTC/ETH were selected today: this conditional survivor-universe study cannot establish broad crypto alpha.",
                  "Daily candles do not validate executable size, opening fills, venue custody or taxes.",
                  "No historical crypto price results were used here to choose parameters.",
                  "A promising outcome requires a separately frozen confirmation design. This ZIP is not a deployment decision."])
    (out / "README.md").write_text("\n".join(lines)+"\n", encoding="utf-8", newline="\n")
    report = dict(**run_identity, evaluation_first_date=str(daily.date.min()), evaluation_last_date=str(daily.date.max()),
                  policy_count=16, candidate_count=9, ledger_count=64, exact_replay_passed=True,
                  daily_rows=len(daily), maximum_accounting_residual=float(daily.accounting_residual.abs().max()),
                  files={p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "report.json"})
    write_json(out / "report.json", report)
    print(base[["policy", "cagr", "cash_excess_sharpe", "max_drawdown"]].to_string(index=False), flush=True)
    return report


def bundle(out):
    path = out.with_suffix(".zip")
    if path.exists():
        raise FileExistsError(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in sorted(out.iterdir()):
            if item.is_file():
                archive.write(item, item.name)
        archive.write(SPEC, "specification.md")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--btc-csv", type=Path)
    parser.add_argument("--eth-csv", type=Path)
    parser.add_argument("--source-label", default="operator_local_unverified")
    parser.add_argument("--download-missing", action="store_true", help="Explicitly permit Coinbase BTC/ETH downloads")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.with_suffix(".zip").exists():
        parser.error("Output path already exists; use a new run directory")
    run_identity = identity()
    args.output_dir.mkdir(parents=True)
    try:
        frames, records = load_inputs(args.data_root, dict(BTC=args.btc_csv, ETH=args.eth_csv), args.output_dir,
                                      args.download_missing, args.source_label)
    except (ValueError, OSError, TypeError) as exc:
        write_json(args.output_dir / "DATA_CHECK_FAILED.json", dict(status="DATA_CHECK_FAILED_NO_BACKTEST", error=str(exc)))
        archive = bundle(args.output_dir)
        print(f"Data check failed: {exc}\nSHARE DATA CHECK ZIP: {archive.resolve()}", flush=True)
        raise SystemExit(2) from exc
    evaluate(frames, args.output_dir, dict(run_identity, data=records))
    archive = bundle(args.output_dir)
    print(f"\nSHARE RESULTS ZIP: {archive.resolve()}", flush=True)


if __name__ == "__main__":
    main()
