"""Offline ML allocation experiment; operator-local development, not final OOS."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from research.fresh_crypto.engine import SCENARIOS, metrics
from research.fresh_discovery.data import sha, write_json
from .data import load_source
from .design import FEATURES, policies, registry
from .features import Panel
from .labels import make_labels
from .models import eligible_labels, first_signal, walk_forward
from .portfolio import make_schedules, simulate

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT/"docs/research/FRESH_CRYPTO_ML_ALLOCATION_20260914.md"


def csv(frame):
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.17g")


def save(frame, path):
    path.write_text(csv(frame), encoding="utf-8", newline="\n")


def identity():
    paths = sorted((ROOT/"research/fresh_crypto_ml").glob("*.py")) + [
        ROOT/"research/fresh_crypto/data.py", ROOT/"research/fresh_crypto/engine.py",
        ROOT/"research/fresh_discovery/accounting.py", ROOT/"research/fresh_discovery/data.py",
        ROOT/"scripts/local/run_fresh_crypto_ml.ps1", ROOT/"tests/test_fresh_crypto_ml.py",
        ROOT/"uv.lock", ROOT/"pyproject.toml", SPEC]
    names = [p.relative_to(ROOT).as_posix() for p in paths]
    status = subprocess.check_output(["git", "status", "--porcelain", "--", *names], cwd=ROOT, text=True)
    if status.strip():
        raise ValueError("Commit research code/spec before recording a market ML run")
    return dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                code_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in paths}, synthetic_data_used=False,
                environment=dict(python=platform.python_version(), **{p: importlib.metadata.version(p)
                    for p in ("numpy", "pandas", "scikit-learn", "scipy", "threadpoolctl")}))


def evaluate(frames, out, run_identity):
    if not isinstance(run_identity.get("synthetic_data_used"), bool):
        raise ValueError("Explicit synthetic_data_used boolean is required")
    status = "SYNTHETIC_MECHANICS_ONLY" if run_identity["synthetic_data_used"] else "ML_DEVELOPMENT_WALK_FORWARD_NOT_FINAL_OOS"
    print(status, flush=True)
    run_identity = dict(run_identity, status=status, experiment=registry(), scenarios=SCENARIOS,
                        cash_yield=0., reserved_2025_used=False, monte_carlo_run=False)
    write_json(out/"identity_before_evaluation.json", run_identity)
    panel = Panel(frames)
    first = first_signal(panel)
    save(panel.frame(), out/"features.csv")
    labels = make_labels(panel)
    if csv(labels)!=csv(make_labels(panel)):
        raise ValueError("Counterfactual label replay failed")
    save(labels, out/"labels.csv")
    # Immature labels must be rejected on every run.
    try:
        eligible_labels(labels, panel.dates[365])
    except ValueError:
        pass
    else:
        raise ValueError("Immature-label rejection canary failed")
    print(f"{len(labels)} counterfactual labels verified; fitting chronological models", flush=True)
    predictions, fits = walk_forward(panel, labels, first)
    save(predictions, out/"predictions.csv")
    write_json(out/"fit_records.json", dict(fits=fits))
    schedules, targets, decisions = make_schedules(panel, predictions, first)
    replay_schedules, replay_targets, replay_decisions = make_schedules(panel, predictions, first)
    if csv(targets)!=csv(replay_targets) or csv(decisions)!=csv(replay_decisions):
        raise ValueError("Allocation decision replay failed")
    save(targets, out/"target_weights.csv")
    save(decisions, out/"mixture_decisions.csv")
    diagnostics = []
    scored = predictions.merge(labels[["profile", "signal_index", "target"]], on=["profile", "signal_index"], how="inner")
    save(scored, out/"scored_predictions.csv")
    for (profile, model), group in scored.groupby(["profile", "model"]):
        error = group.predicted_relative_log_return-group.target
        diagnostics.append(dict(profile=profile, model=model, scored_decisions=len(group),
                                rmse=float(np.sqrt(np.mean(error**2))), mae=float(np.abs(error).mean()),
                                mean_predicted=float(group.predicted_relative_log_return.mean()),
                                mean_actual=float(group.target.mean()),
                                sign_accuracy=float(((group.predicted_relative_log_return>0)==(group.target>0)).mean())))
    save(pd.DataFrame(diagnostics), out/"prediction_diagnostics.csv")
    ledgers, summaries, annual = [], [], []
    for scenario, cost, delay in SCENARIOS:
        for policy in policies():
            ledger = simulate(panel, schedules[policy.name], policy, cost, delay, first)
            replay = simulate(panel, replay_schedules[policy.name], policy, cost, delay, first)
            if csv(ledger)!=csv(replay):
                raise ValueError(f"Ledger replay failed: {scenario}/{policy.name}")
            ledger["policy"], ledger["scenario"] = policy.name, scenario
            ledgers.append(ledger)
            for period, sub in (("full", ledger), ("2020_2021", ledger[ledger.date<"2022-01-01"]),
                                ("2022_2024", ledger[ledger.date>="2022-01-01"])):
                if len(sub)>=30:
                    summaries.append(dict(policy=policy.name, family=policy.family, profile=policy.target,
                                          band=policy.band, role=policy.role, period=period, scenario=scenario,
                                          first_date=sub.date.iloc[0], last_date=sub.date.iloc[-1],
                                          executed_rebalances=int(sub.executed.sum()),
                                          skipped_rebalances=int((sub.execution_reason=="inside_band").sum()), **metrics(sub)))
            for year, sub in ledger.groupby(ledger.date.str[:4]):
                annual.append(dict(policy=policy.name, scenario=scenario, year=int(year), days=len(sub),
                                   total_return=float((1+sub["return"]).prod()-1)))
        print(f"{scenario}: all {len(policies())} continuous portfolios reconciled and replayed", flush=True)
    daily, summary = pd.concat(ledgers, ignore_index=True), pd.DataFrame(summaries)
    save(daily, out/"daily_ledger.csv")
    save(summary, out/"metrics.csv")
    save(pd.DataFrame(annual), out/"annual_returns.csv")
    comparisons = []
    for row in summary[summary.role=="candidate"].itertuples():
        for family in ("trend", "allocation", "fixed_blend", "state_rule", "constant"):
            control = summary[(summary.family==family) & (summary.profile==row.profile) & (summary.band==row.band)
                              & (summary.scenario==row.scenario) & (summary.period==row.period)].iloc[0]
            comparisons.append(dict(policy=row.policy, control=control.policy, scenario=row.scenario, period=row.period,
                                    cagr_difference=row.cagr-control.cagr,
                                    sharpe_difference=row.cash_excess_sharpe-control.cash_excess_sharpe,
                                    drawdown_difference=row.max_drawdown-control.max_drawdown,
                                    volatility_difference=row.annual_volatility-control.annual_volatility))
    save(pd.DataFrame(comparisons), out/"matched_control_comparisons.csv")
    base = summary[(summary.scenario=="base") & (summary.period=="full")]
    lines = [f"# {status}", "", "2020-2024 is already-inspected development history, not final OOS evidence.",
             "Two learned models, constant predictor, fixed blends, rule control and spot benchmarks.",
             "Base costs 30 bps one way; stress 75 bps; separate extra-day delay stress.",
             "USD cash yield zero. No leverage. All portfolios share the same evaluation window.", "",
             "| Policy | CAGR | Cash-excess Sharpe | Max DD | Turnover/year |",
             "|---|---:|---:|---:|---:|"]
    for row in base.itertuples():
        lines.append(f"| {row.policy} | {row.cagr:.2%} | {row.cash_excess_sharpe:.3f} | {row.max_drawdown:.2%} | {row.annual_one_way_turnover:.2f} |")
    lines += ["", "The allocation endpoints are causal fixed rules; learned mixtures update weekly.",
              "A model fit uses only labels exiting strictly before its feature-availability cutoff.",
              "Feature clipping/scaling is fitted on that training set. No random validation or early stopping.",
              "All stress ledgers reuse base-trained predictions; no scenario-specific tuning.",
              "The 2% band measures total absolute risky-weight deviation at the candidate execution open.",
              "Risk reductions and full exits override the band; all final exits include costs.",
              "Skipped-trade positions drift; the band does not enforce an intraday volatility guarantee.",
              "Label experiments start from unit cash and liquidate after 14 days. Actual portfolios never reset.",
              "The forecast hurdle is a fixed turnover-sensitive margin, not calibrated confidence.",
              "Compare both ML models with every matched control, and compare band/exact execution separately.",
              "Inspect annual returns, realized risk, costs and prediction diagnostics before a research decision.",
              "No automatic winner, OOS promotion, Monte Carlo conclusion, capacity or venue-access claim."]
    (out/"README.md").write_text("\n".join(lines)+"\n", encoding="utf-8", newline="\n")
    distinct_learned = sum(f["model"]!="constant" for f in fits)
    report = dict(**run_identity, policy_count=len(policies()), ledger_count=len(ledgers), daily_rows=len(daily),
                  distinct_learned_fits=distinct_learned, learned_fit_executions_including_replay=2*distinct_learned,
                  constant_estimates=sum(f["model"]=="constant" for f in fits),
                  exact_replay_passed=True, immature_label_canary_passed=True,
                  first_evaluation_date=str(daily.date.min()), last_evaluation_date=str(daily.date.max()),
                  maximum_accounting_residual=float(daily.accounting_residual.abs().max()),
                  files={p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!="report.json"})
    write_json(out/"report.json", report)
    print(f"{status}: base-case table", flush=True)
    print(base[["policy", "cagr", "cash_excess_sharpe", "max_drawdown"]].to_string(index=False), flush=True)
    return report


def bundle(out):
    archive_path = out.with_suffix(".zip")
    if archive_path.exists():
        raise FileExistsError(archive_path)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(out.iterdir()):
            if path.is_file():
                archive.write(path, path.name)
        archive.write(SPEC, "specification.md")
    return archive_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.with_suffix(".zip").exists():
        parser.error("Use a new output directory; existing runs are immutable")
    run_identity = identity()
    args.output_dir.mkdir(parents=True)
    frames, source = load_source(args.source_run, args.output_dir)
    evaluate(frames, args.output_dir, dict(run_identity, data=source))
    archive = bundle(args.output_dir)
    print(f"\nSHARE ML RESULTS ZIP: {archive.resolve()}", flush=True)


if __name__=="__main__":
    main()
