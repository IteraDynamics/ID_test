"""Audit the fixed operator ML run; reproduce existing fits, never search or use OOS.

Run from the repository root with python -m scripts.review_fresh_crypto_ml
--archive PATH --output-dir NEW_DIRECTORY. Outputs are audit evidence, not new trials.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from research.fresh_crypto.data import normalize
from research.fresh_crypto.engine import SCENARIOS, metrics
from research.fresh_crypto_ml.design import EXPECTED_INPUTS, FEATURES, policies, registry
from research.fresh_crypto_ml.features import Panel
from research.fresh_crypto_ml.labels import make_labels
from research.fresh_crypto_ml.models import first_signal, walk_forward
from research.fresh_crypto_ml.portfolio import make_schedules, simulate
from research.fresh_crypto_ml.run import save
from research.fresh_discovery.data import sha, write_json
from scripts.review_fresh_crypto_discovery import compare

ROOT = Path(__file__).resolve().parents[1]


def close(a, b, message):
    if not np.allclose(a, b, atol=2e-11, rtol=2e-10, equal_nan=True):
        raise ValueError(message)


def training_audit(fits, labels, features, predictions):
    """Reconstruct the *archived* training bytes and check all availability boundaries."""
    x = features.set_index("signal_index")
    for fit in fits:
        cutoff = pd.Timestamp(fit["fit_time"])
        train = labels[(labels.profile==fit["profile"]) &
                       (pd.to_datetime(labels.label_available, utc=True)<cutoff) &
                       (pd.to_datetime(labels.feature_available, utc=True)<cutoff)]
        indices = train.signal_index.to_numpy(dtype=int)
        packed = np.c_[indices, x.loc[indices, list(FEATURES)].to_numpy(), train.target.to_numpy()]
        digest = hashlib.sha256(packed.astype("<f8").tobytes()).hexdigest()
        if len(train)!=fit["training_rows"] or digest!=fit["training_sha256"]:
            raise ValueError(f"Archived training-set identity failed: {fit['fit_id']}")
        latest = pd.to_datetime(train.label_available, utc=True).max()
        if latest>=cutoff or latest!=pd.Timestamp(fit["latest_label_available"]):
            raise ValueError("Label maturity failed")
        predicted = predictions[predictions.fit_id==fit["fit_id"]]
        if predicted.empty or not (pd.to_datetime(predicted.fit_time, utc=True)==cutoff).all():
            raise ValueError("Prediction model identity failed")
        available = pd.to_datetime(predicted.feature_available, utc=True)
        fill = pd.to_datetime(predicted.base_fill_time, utc=True)
        if not ((available>=cutoff) & (fill>available)).all():
            raise ValueError("Prediction availability failed")
    return len(fits)


def audit(archive, out):
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    source = out/"source"
    source.mkdir()
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(set(names))!=len(names) or z.testzip() is not None:
            raise ValueError("Duplicate ZIP members or CRC failure")
        for name in names:
            if Path(name).name!=name or "\\" in name or name in (".", ".."):
                raise ValueError("Only flat archive paths are accepted")
            (source/name).write_bytes(z.read(name))
    report = json.loads((source/"report.json").read_text())
    if report["synthetic_data_used"] is not False or report["reserved_2025_used"] is not False:
        raise ValueError("Expected the pre-2025 market development run")
    if report["experiment"]!=json.loads(json.dumps(registry())) or report["scenarios"]!=[list(s) for s in SCENARIOS]:
        raise ValueError("Fixed experiment registry differs")
    if set(names)!=set(report["files"]) | {"report.json", "specification.md"}:
        raise ValueError("Archive file manifest is incomplete")
    for name, digest in report["files"].items():
        if Path(name).name!=name or sha(source/name)!=digest:
            raise ValueError(f"Artifact hash mismatch: {name}")
    modes = {}
    for name, digest in report["code_sha256"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Invalid code path")
        pinned = subprocess.check_output(["git", "show", f"{report['commit']}:{name}"], cwd=ROOT).replace(b"\r\n", b"\n")
        choices = {"LF": pinned, "CRLF": pinned.replace(b"\n", b"\r\n")}
        matches = [mode for mode, value in choices.items() if hashlib.sha256(value).hexdigest()==digest]
        if not matches or (ROOT/name).read_bytes().replace(b"\r\n", b"\n")!=pinned:
            raise ValueError(f"Pinned/working code mismatch: {name}")
        modes[name] = matches[0]
    if sha(source/"specification.md")!=report["code_sha256"]["docs/research/FRESH_CRYPTO_ML_ALLOCATION_20260914.md"]:
        raise ValueError("Archived specification differs")
    for name, digest in EXPECTED_INPUTS.items():
        if sha(source/name)!=digest:
            raise ValueError("Reviewed input snapshot differs")
    frames = {a: normalize(pd.read_csv(source/f"{a}-USD.csv", float_precision="round_trip"))[0]
              for a in ("BTC", "ETH")}
    expected_dates = pd.date_range("2017-01-01", "2024-12-31", tz="UTC")
    if any(not f.index.equals(expected_dates) for f in frames.values()):
        raise ValueError("Source calendar differs")
    def read(name):
        return pd.read_csv(source/f"{name}.csv", float_precision="round_trip")
    panel = Panel(frames)
    first = first_signal(panel)
    features, labels, predictions = read("features"), read("labels"), read("predictions")
    feature_deltas = compare(panel.frame(), features)
    regenerated_labels = make_labels(panel)
    label_deltas = compare(regenerated_labels, labels)
    fit_records = json.loads((source/"fit_records.json").read_text())["fits"]
    fit_count = training_audit(fit_records, labels, features, predictions)
    print("Archive/code/input hashes, causal features, labels and archived training sets verified", flush=True)
    replay_predictions, replay_fits = walk_forward(panel, regenerated_labels, first)
    prediction_deltas = compare(replay_predictions, predictions)
    # Metadata and preprocessing are compared separately from binary training hashes;
    # the archived training hashes were already reconstructed from exact saved floats.
    def check_details(left, right):
        if isinstance(left, dict):
            if set(left)!=set(right):
                raise ValueError("Fit record keys differ")
            for key in left:
                if key!="training_sha256":
                    check_details(left[key], right[key])
        elif isinstance(left, list):
            if len(left)!=len(right):
                raise ValueError("Fit record lengths differ")
            for a, b in zip(left, right):
                check_details(a, b)
        elif isinstance(left, (float, int)):
            close(left, right, "Fit parameters differ")
        elif left!=right:
            raise ValueError("Fit metadata differs")
    check_details(replay_fits, fit_records)
    schedules, targets, decisions = make_schedules(panel, replay_predictions, first)
    target_deltas = compare(targets, read("target_weights"))
    compare(decisions, read("mixture_decisions"))
    daily, summary, annual = read("daily_ledger"), read("metrics"), read("annual_returns")
    deltas, identities, deletions = {}, [], []
    group_count = 0
    for scenario, cost, delay in SCENARIOS:
        for policy in policies():
            saved = daily[(daily.scenario==scenario) & (daily.policy==policy.name)].reset_index(drop=True)
            replay = simulate(panel, schedules[policy.name], policy, cost, delay, first)
            for key, value in compare(replay, saved[replay.columns]).items():
                deltas[key] = max(value, deltas.get(key, 0.))
            group_count += 1
            wealth = np.cumprod(1+saved["return"].to_numpy())
            close(wealth, saved.nav, "Independent wealth identity failed")
            close(saved.BTC_pnl+saved.ETH_pnl, saved["return"], "Independent asset P&L failed")
            close(saved.BTC_weight+saved.ETH_weight+saved.USD_weight, 1., "Full-equity weights failed")
            if not saved.iloc[-1].terminal_liquidation or saved.iloc[-1].risky_exposure!=0.:
                raise ValueError("Terminal liquidation failed")
            peak = np.maximum.accumulate(np.r_[1., wealth])[1:]
            years = (pd.Timestamp(saved.date.iloc[-1])-pd.Timestamp(saved.date.iloc[0])).days/365.25
            full = summary[(summary.scenario==scenario) & (summary.policy==policy.name) & (summary.period=="full")].iloc[0]
            close(full.cagr, wealth[-1]**(1/years)-1, "Independent CAGR failed")
            close(full.max_drawdown, (wealth/peak-1).min(), "Independent drawdown failed")
            for period, sub in (("full", saved), ("2020_2021", saved[saved.date<"2022-01-01"]),
                                ("2022_2024", saved[saved.date>="2022-01-01"])):
                row = summary[(summary.scenario==scenario) & (summary.policy==policy.name) & (summary.period==period)].iloc[0]
                for key, value in metrics(sub).items():
                    close(value, row[key], f"Reported metric differs: {key}")
            for year, sub in saved.groupby(saved.date.str[:4]):
                row = annual[(annual.policy==policy.name) & (annual.scenario==scenario) & (annual.year==int(year))].iloc[0]
                close(row.total_return, (1+sub["return"]).prod()-1, "Annual return differs")
                if scenario=="base":
                    kept = saved[saved.date.str[:4]!=year]["return"].to_numpy()
                    sd = kept.std(ddof=1)
                    deletions.append(dict(policy=policy.name, excluded_year=int(year), remaining_days=len(kept),
                                          cash_excess_sharpe=float(kept.mean()/sd*np.sqrt(365)) if sd>1e-12 else np.nan))
            if policy.family in ("btc_buy_hold", "eth_buy_hold", "mix_buy_hold"):
                w = np.array(dict(btc_buy_hold=[1.,0.], eth_buy_hold=[0.,1.], mix_buy_hold=[.5,.5])[policy.family])
                rate = cost/10_000
                expected = float(w @ (panel.opens[-1]/panel.opens[first+2+delay]))*(1-rate)/(1+rate)
                close(saved.nav.iloc[-1], expected, "Independent buy-and-hold price/fee identity failed")
                identities.append(dict(policy=policy.name, scenario=scenario, expected_nav=expected,
                                       reported_nav=float(saved.nav.iloc[-1]), residual=float(saved.nav.iloc[-1]-expected)))
        print(f"Verified {scenario}: 32 ledgers, metrics, annual returns and benchmark identities", flush=True)
    if (group_count, len(daily), fit_count)!=(128, 233856, 120):
        raise ValueError("Incomplete fixed experiment")
    scored = predictions.merge(labels[["profile", "signal_index", "target"]], on=["profile", "signal_index"])
    compare(scored, read("scored_predictions"))
    diagnostics, forecast_value = [], []
    for (profile, model), group in scored.groupby(["profile", "model"]):
        error = group.predicted_relative_log_return-group.target
        diagnostics.append(dict(profile=profile, model=model, scored_decisions=len(group),
                                rmse=float(np.sqrt(np.mean(error**2))), mae=float(np.abs(error).mean()),
                                mean_predicted=float(group.predicted_relative_log_return.mean()), mean_actual=float(group.target.mean()),
                                sign_accuracy=float(((group.predicted_relative_log_return>0)==(group.target>0)).mean())))
    diagnostics = pd.DataFrame(diagnostics)
    compare(diagnostics, read("prediction_diagnostics"))
    for row in diagnostics.itertuples():
        baseline = diagnostics[(diagnostics.profile==row.profile) & (diagnostics.model=="constant")].iloc[0]
        forecast_value.append(dict(profile=row.profile, model=row.model, rmse=row.rmse, mae=row.mae,
                                   relative_rmse=row.rmse/baseline.rmse,
                                   mse_skill_vs_constant=1-(row.rmse/baseline.rmse)**2))
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
    comparisons = pd.DataFrame(comparisons)
    compare(comparisons, read("matched_control_comparisons"))
    # A timing error and an economic error must each trip the audit.
    corrupted = [dict(fit_records[0], fit_time="2019-01-01 00:00:00+00:00")]
    canaries = [lambda: training_audit(corrupted, labels, features, predictions),
                lambda: compare(pd.DataFrame({"return":[.01]}), pd.DataFrame({"return":[.011]}))]
    for canary in canaries:
        try:
            canary()
        except ValueError:
            pass
        else:
            raise ValueError("Corruption canary did not fail")
    for name, frame in dict(leave_one_year_out=pd.DataFrame(deletions), buy_hold_identities=pd.DataFrame(identities),
                            forecast_value=pd.DataFrame(forecast_value), metrics=summary, annual_returns=annual,
                            matched_control_comparisons=comparisons).items():
        save(frame, out/f"{name}.csv")
    evidence = dict(status="FIXED_ML_DEVELOPMENT_RUN_AUDITED_NOT_FINAL_OOS", archive_sha256=sha(archive),
                    source_commit=report["commit"], archive_files_verified=len(report["files"]), code_hash_modes=modes,
                    normalized_inputs_verified=True, calendar_days=2922,
                    original_vendor_and_acquisition_provenance_independently_verified=False,
                    source_environment=report["environment"], reviewer_environment=dict(python=platform.python_version(),
                        **{p:importlib.metadata.version(p) for p in ("numpy", "pandas", "scikit-learn", "scipy", "threadpoolctl")}),
                    archived_training_sets_verified=fit_count, existing_learned_fits_reproduced=80,
                    learned_fit_executions_including_replay=160, constant_estimate_executions_including_replay=80,
                    regenerated_training_hash_matches=sum(a["training_sha256"]==b["training_sha256"] for a,b in zip(replay_fits,fit_records)),
                    feature_replay_differences=feature_deltas, label_replay_differences=label_deltas,
                    prediction_replay_differences=prediction_deltas, target_replay_differences=target_deltas,
                    maximum_ledger_replay_differences=deltas, ledgers_replayed=group_count, daily_rows=len(daily),
                    independent_buy_hold_checks=len(identities), metrics_and_diagnostics_reconstructed=True,
                    corruption_canaries_passed=2, new_strategy_variants=0, holdout_evaluations=0,
                    monte_carlo_runs=0, deletion_diagnostic="Omit one year's saved daily returns; no refit, significance test or OOS claim")
    write_json(out/"review_audit.json", evidence)
    print("Fixed ML run audit passed; no new configuration or reserved history evaluated", flush=True)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    audit(args.archive, args.output_dir)


if __name__=="__main__":
    main()
