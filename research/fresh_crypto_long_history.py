"""Unchanged fixed crypto rules over longer development history; no model fitting."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import subprocess
import zipfile

import numpy as np
import pandas as pd

from research.fresh_crypto.data import WARMUP, normalize
from research.fresh_crypto.engine import SCENARIOS, metrics
from research.fresh_crypto_ml.design import EXPECTED_INPUTS, FEATURES, policies as prior_policies
from research.fresh_crypto_ml.features import Panel
from research.fresh_crypto_ml.portfolio import simulate
from research.fresh_discovery.data import sha, write_json

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT/"docs/research/FRESH_CRYPTO_LONG_HISTORY_20260914.md"
SOURCE_RUNS = ("fresh_crypto_ml_20260914_134645_379", "fresh_crypto_20260914_110447_621")
FAMILIES = ("trend", "allocation", "fixed_blend", "state_rule")


def csv(frame):
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.17g")


def save(frame, path):
    path.write_text(csv(frame), encoding="utf-8", newline="\n")


def resolve_source(source: Path | None, root: Path = ROOT) -> Path:
    bases = [source] if source is not None else [root/"artifacts"/name for name in SOURCE_RUNS]
    checked = []
    for base in bases:
        candidates = [base] if base.suffix.lower()==".zip" else [base, Path(str(base)+".zip")]
        for path in candidates:
            checked.append(str(path.absolute()))
            if path.is_file() or path.is_dir():
                return path.resolve()
    raise FileNotFoundError("Prior results not found. Checked: " + "; ".join(checked) +
                            ". Supply -SourceRun with your completed crypto or ML results directory/ZIP; "
                            "this is not the raw data folder. Git does not restore local artifacts.")


def load_source(source: Path, out: Path | None = None):
    names = ["report.json", *EXPECTED_INPUTS]
    if source.is_dir():
        content = {name: (source/name).read_bytes() for name in names}
        source_hash = dict(source_report_sha256=sha(source/"report.json"))
    else:
        with zipfile.ZipFile(source) as archive:
            members = archive.namelist()
            if len(set(members))!=len(members) or archive.testzip() is not None:
                raise ValueError("Duplicate ZIP members or corrupt source archive")
            content = {name: archive.read(name) for name in names}
        source_hash = dict(source_archive_sha256=sha(source))
    report = json.loads(content["report.json"])
    if report.get("synthetic_data_used") is not False or report.get("reserved_2025_used") is not False:
        raise ValueError("Expected a pre-2025 market-development source")
    frames = {}
    for name, digest in EXPECTED_INPUTS.items():
        if hashlib.sha256(content[name]).hexdigest()!=digest or report.get("files", {}).get(name)!=digest:
            raise ValueError(f"Input differs from the reviewed BTC/ETH snapshot: {name}")
        asset = name.split("-")[0]
        frames[asset], _ = normalize(pd.read_csv(io.BytesIO(content[name]), float_precision="round_trip"))
        if not frames[asset].index.equals(pd.date_range("2017-01-01", "2024-12-31", tz="UTC")):
            raise ValueError("Expected the complete 2017-2024 calendar")
    manifest = dict(source_path=str(source.resolve()), source_commit=report.get("commit"), **source_hash,
                    normalized_input_sha256=EXPECTED_INPUTS, downloads=0,
                    original_vendor_provenance="operator_local_unverified",
                    price_window="2017-01-01 through 2024-12-31")
    if out is not None:
        for name in EXPECTED_INPUTS:
            (out/name).write_bytes(content[name])
        (out/"source_report.json").write_bytes(content["report.json"])
        write_json(out/"input_manifest.json", manifest)
    return frames, manifest


def policies():
    return [replace(p, role="candidate" if p.family in ("fixed_blend", "state_rule") else p.role)
            for p in prior_policies() if p.family in FAMILIES or p.role=="benchmark"]


def state_mixture(agreement, volatility_ratio):
    return float(agreement<2/3 or volatility_ratio>1.25)


def make_schedules(panel, first=WARMUP):
    if first<WARMUP or first+3>=len(panel.dates):
        raise ValueError("Insufficient warm-up or evaluation history")
    schedules, rows, decisions = {}, [], []
    for policy in policies():
        schedule, mixture = {}, .5
        for t in range(first, len(panel.dates)-3):
            if policy.role=="benchmark":
                if t>first:
                    continue
                target = np.array(dict(btc_buy_hold=[1.,0.], eth_buy_hold=[0.,1.],
                                       mix_buy_hold=[.5,.5], usd_cash=[0.,0.])[policy.family])
                coefficient = np.nan
            else:
                agreement = panel.x[t, FEATURES.index("trend_agreement")]
                ratio = panel.x[t, FEATURES.index("volatility_ratio")]
                due = t==first or panel.dates[t+2].weekday()==0
                if policy.family=="state_rule":
                    if due:
                        mixture = state_mixture(agreement, ratio)
                else:
                    mixture = {"trend":1., "allocation":0., "fixed_blend":.5}[policy.family]
                if due:
                    decisions.append(dict(policy=policy.name, signal_index=t, signal_bar_start=str(panel.dates[t]),
                                          feature_available=str(panel.dates[t]+pd.Timedelta(days=1)),
                                          base_fill_time=str(panel.dates[t]+pd.Timedelta(days=2)), mixture=mixture,
                                          trend_agreement=float(agreement), volatility_ratio=float(ratio)))
                target = mixture*panel.trend[policy.target][t]+(1-mixture)*panel.allocation[policy.target][t]
                coefficient = mixture
                if np.sqrt(max(0., target @ panel.cov[t] @ target))>policy.target+1e-10:
                    raise ValueError("Mixture exceeds target formation risk budget")
            schedule[t] = (target, coefficient)
            rows.append(dict(policy=policy.name, signal_index=t, signal_bar_start=str(panel.dates[t]),
                             feature_available=str(panel.dates[t]+pd.Timedelta(days=1)),
                             base_fill_time=str(panel.dates[t]+pd.Timedelta(days=2)),
                             BTC=target[0], ETH=target[1], USD=1-target.sum(), mixture=coefficient))
        schedules[policy.name] = schedule
    return schedules, pd.DataFrame(rows), pd.DataFrame(decisions)


def experiment():
    return dict(policies=[asdict(p) for p in policies()], scenarios=SCENARIOS,
                first_signal="2018-01-01", first_evaluation_date="2018-01-03", last_evaluation_date="2024-12-31",
                state_rule=dict(agreement_below=2/3, volatility_ratio_above=1.25),
                state_decisions="initial_signal_then_Monday_base_fills", fixed_blend_coefficient=.5,
                band_total_absolute_risky_weight_deviation=.02, cash_yield=0., leverage=False,
                model_fits=0, parameter_search=False, subperiod_inventory="carried_from_continuous_full_run")


def identity():
    names = ["research/fresh_crypto_long_history.py", "research/fresh_crypto/data.py", "research/fresh_crypto/engine.py",
             "research/fresh_crypto_ml/design.py", "research/fresh_crypto_ml/features.py",
             "research/fresh_crypto_ml/portfolio.py", "research/fresh_crypto_ml/models.py",
             "research/fresh_discovery/accounting.py", "research/fresh_discovery/data.py",
             "scripts/local/run_fresh_crypto_long_history.ps1", "tests/test_fresh_crypto_long_history.py",
             "docs/research/FRESH_CRYPTO_LONG_HISTORY_20260914.md", "pyproject.toml", "uv.lock"]
    if subprocess.check_output(["git", "status", "--porcelain", "--", *names], cwd=ROOT, text=True).strip():
        raise ValueError("Commit consumed research code/spec before recording a market run")
    return dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                code_sha256={name:sha(ROOT/name) for name in names}, synthetic_data_used=False,
                environment=dict(python=platform.python_version(), **{p:importlib.metadata.version(p)
                    for p in ("numpy", "pandas", "scikit-learn", "scipy", "threadpoolctl")}))


def verify_ledger(ledger, panel, policy, cost_bps, delay):
    def check(a, b, message):
        if not np.allclose(a, b, atol=2e-11, rtol=2e-10):
            raise ValueError(message)
    check(np.cumprod(1+ledger["return"].to_numpy()), ledger.nav, "Independent wealth reconstruction failed")
    check(ledger.BTC_pnl+ledger.ETH_pnl, ledger["return"], "Independent asset P&L identity failed")
    check(ledger.BTC_weight+ledger.ETH_weight+ledger.USD_weight, 1., "Full-equity weights failed")
    if ledger.risky_exposure.iloc[-1]!=0 or not ledger.terminal_liquidation.iloc[-1]:
        raise ValueError("Final liquidation failed")
    if policy.family in ("btc_buy_hold", "eth_buy_hold", "mix_buy_hold"):
        weights = np.array(dict(btc_buy_hold=[1.,0.], eth_buy_hold=[0.,1.], mix_buy_hold=[.5,.5])[policy.family])
        rate = cost_bps/10_000
        expected = float(weights @ (panel.opens[-1]/panel.opens[WARMUP+2+delay]))*(1-rate)/(1+rate)
        check(ledger.nav.iloc[-1], expected, "Independent buy-and-hold fee/price identity failed")
        return dict(expected_nav=expected, reported_nav=float(ledger.nav.iloc[-1]),
                    residual=float(ledger.nav.iloc[-1]-expected))
    return None


def evaluate(frames, out, run_identity):
    if not isinstance(run_identity.get("synthetic_data_used"), bool):
        raise ValueError("Explicit synthetic_data_used boolean is required")
    synthetic = run_identity["synthetic_data_used"]
    dates = frames["BTC"].index
    if (dates[-1]>=pd.Timestamp("2025-01-01", tz="UTC") or
            not dates.equals(pd.date_range(pd.Timestamp("2017-01-01", tz="UTC"), dates[-1])) or
            not dates.equals(frames["ETH"].index)):
        raise ValueError("Expected aligned complete pre-2025 daily calendars starting in 2017")
    if not synthetic and dates[-1]!=pd.Timestamp("2024-12-31", tz="UTC"):
        raise ValueError("Market evaluation requires the full reviewed snapshot")
    status = "SYNTHETIC_MECHANICS_ONLY" if synthetic else "FIXED_RULE_LONG_HISTORY_DEVELOPMENT_NOT_OOS"
    print(status, flush=True)
    record = dict(run_identity, status=status, experiment=experiment(), model_fits=0,
                  reserved_2025_used=False, monte_carlo_run=False)
    write_json(out/"identity_before_evaluation.json", record)
    panel = Panel(frames)
    orders, targets, decisions = make_schedules(panel)
    other_orders, other_targets, other_decisions = make_schedules(panel)
    if csv(targets)!=csv(other_targets) or csv(decisions)!=csv(other_decisions):
        raise ValueError("Fixed-rule schedule replay failed")
    save(panel.frame(), out/"features.csv")
    save(targets, out/"target_weights.csv")
    save(decisions, out/"mixture_decisions.csv")
    ledgers, summaries, annual, identities = [], [], [], []
    for scenario, cost, delay in SCENARIOS:
        for policy in policies():
            ledger = simulate(panel, orders[policy.name], policy, cost, delay, WARMUP)
            replay = simulate(panel, other_orders[policy.name], policy, cost, delay, WARMUP)
            if csv(ledger)!=csv(replay):
                raise ValueError(f"Ledger replay failed: {scenario}/{policy.name}")
            proof = verify_ledger(ledger, panel, policy, cost, delay)
            if proof is not None:
                identities.append(dict(policy=policy.name, scenario=scenario, **proof))
            ledger["policy"], ledger["scenario"] = policy.name, scenario
            ledgers.append(ledger)
            periods = (("full", ledger), ("2018_2019", ledger[ledger.date<"2020-01-01"]),
                       ("2020_2021", ledger[(ledger.date>="2020-01-01") & (ledger.date<"2022-01-01")]),
                       ("2022_2024", ledger[ledger.date>="2022-01-01"]),
                       ("2020_2024_carry", ledger[ledger.date>="2020-01-01"]))
            for period, sub in periods:
                if len(sub)>=30:
                    summaries.append(dict(policy=policy.name, family=policy.family, profile=policy.target,
                                          band=policy.band, role=policy.role, scenario=scenario, period=period,
                                          first_date=sub.date.iloc[0], last_date=sub.date.iloc[-1],
                                          executed_rebalances=int(sub.executed.sum()),
                                          skipped_rebalances=int((sub.execution_reason=="inside_band").sum()), **metrics(sub)))
            for year, sub in ledger.groupby(ledger.date.str[:4]):
                annual.append(dict(policy=policy.name, scenario=scenario, year=int(year), days=len(sub),
                                   total_return=float((1+sub["return"]).prod()-1)))
        print(f"{scenario}: 20 ledgers reconciled and replayed exactly", flush=True)
    daily, summary = pd.concat(ledgers, ignore_index=True), pd.DataFrame(summaries)
    save(daily, out/"daily_ledger.csv")
    save(summary, out/"metrics.csv")
    save(pd.DataFrame(annual), out/"annual_returns.csv")
    save(pd.DataFrame(identities), out/"buy_hold_identities.csv")
    comparisons = []
    for row in summary[summary.role=="candidate"].itertuples():
        for family in FAMILIES:
            if family==row.family:
                continue
            control = summary[(summary.family==family) & (summary.profile==row.profile) & (summary.band==row.band)
                              & (summary.scenario==row.scenario) & (summary.period==row.period)].iloc[0]
            comparisons.append(dict(policy=row.policy, comparator=control.policy, scenario=row.scenario, period=row.period,
                                    cagr_difference=row.cagr-control.cagr,
                                    sharpe_difference=row.cash_excess_sharpe-control.cash_excess_sharpe,
                                    drawdown_difference=row.max_drawdown-control.max_drawdown,
                                    volatility_difference=row.annual_volatility-control.annual_volatility))
    save(pd.DataFrame(comparisons), out/"matched_comparisons.csv")
    base = summary[(summary.scenario=="base") & (summary.period=="full")]
    lines = [f"# {status}", "", "Unchanged fixed rules; longer development history; zero ML fits.",
             f"Continuous evaluation: {daily.date.min()} through {daily.date.max()}.",
             "Base costs 30 bps one way; stress 75 bps; separate extra-day execution stress.",
             "USD cash yield zero; unlevered spot. All portfolios share the same dates.", "",
             "| Policy | CAGR | Cash-excess Sharpe | Max DD | Turnover/year |",
             "|---|---:|---:|---:|---:|"]
    for row in base.itertuples():
        lines.append(f"| {row.policy} | {row.cagr:.2%} | {row.cash_excess_sharpe:.3f} | {row.max_drawdown:.2%} | {row.annual_one_way_turnover:.2f} |")
    lines += ["", "First signal 2018-01-01; available 2018-01-02; base entry 2018-01-03.",
              "State choices update weekly; expert weights and volatility estimates update daily.",
              "Subperiod metrics slice the continuous inventory path without resetting positions.",
              "The 2020_2024_carry slice is not the earlier ML experiment's fresh cash restart.",
              "Assess 2018 and 2022 protection, 2019/recovery participation, costs and yearly concentration.",
              "Skipped trades allow drift. Neither risk setting guarantees an intraday realized-volatility limit.",
              "Opening-price proxies do not establish venue capacity; source-vendor provenance remains unverified.",
              "No parameter search, automatic winner, OOS evaluation or Monte Carlo conclusion."]
    (out/"README.md").write_text("\n".join(lines)+"\n", encoding="utf-8", newline="\n")
    report = dict(**record, policy_count=len(policies()), ledger_count=len(ledgers), daily_rows=len(daily),
                  first_evaluation_date=str(daily.date.min()), last_evaluation_date=str(daily.date.max()),
                  exact_replay_passed=True, independent_buy_hold_checks=len(identities),
                  maximum_accounting_residual=float(daily.accounting_residual.abs().max()),
                  files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!="report.json"})
    write_json(out/"report.json", report)
    print(f"{status}: base-case table", flush=True)
    print(base[["policy", "cagr", "cash_excess_sharpe", "max_drawdown"]].to_string(index=False), flush=True)
    return report


def bundle(out):
    path = out.with_suffix(".zip")
    if path.exists():
        raise FileExistsError(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file in sorted(out.iterdir()):
            if file.is_file():
                archive.write(file, file.name)
        archive.write(SPEC, "specification.md")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check-data", action="store_true")
    args = parser.parse_args()
    try:
        source = resolve_source(args.source_run)
        if args.check_data:
            frames, _ = load_source(source)
            print(f"Source verified: {source}; BTC {len(frames['BTC'])} rows, ETH {len(frames['ETH'])} rows; downloads 0")
            return
        if args.output_dir is None:
            parser.error("--output-dir is required unless checking data")
        if args.output_dir.exists() or args.output_dir.with_suffix(".zip").exists():
            parser.error("Use a new output directory; existing runs are immutable")
        run_identity = identity()
        args.output_dir.mkdir(parents=True)
        frames, manifest = load_source(source, args.output_dir)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    print(f"Reusing crypto inputs from: {source}", flush=True)
    evaluate(frames, args.output_dir, dict(run_identity, data=manifest))
    print(f"\nSHARE LONG-HISTORY RESULTS ZIP: {bundle(args.output_dir).resolve()}", flush=True)


if __name__=="__main__":
    main()
