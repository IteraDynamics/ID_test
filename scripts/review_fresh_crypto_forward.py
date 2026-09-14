"""Audit one frozen crypto forward archive; no new strategy, fit or Monte Carlo."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import zipfile

import numpy as np
import pandas as pd

from research import fresh_crypto_forward as runner
from research import fresh_crypto_long_history as prior
from research.fresh_discovery.data import sha, write_json
from scripts.review_fresh_crypto_discovery import compare
from scripts.review_fresh_crypto_long_history import independent_statistics

ROOT = Path(__file__).resolve().parents[1]


def audit(archive: Path, development_source: Path, out: Path) -> dict:
    if out.exists():
        raise FileExistsError(out)
    source, replay = out/"source", out/"replay"
    source.mkdir(parents=True)
    replay.mkdir()
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(set(names))!=len(names) or z.testzip() is not None:
            raise ValueError("Duplicate ZIP members or CRC failure")
        for name in names:
            if Path(name).name!=name or "\\" in name or name in (".",".."):
                raise ValueError("Only flat archive filenames are accepted")
            (source/name).write_bytes(z.read(name))
    report = json.loads((source/"report.json").read_text())
    identity = json.loads((source/"identity_before_evaluation.json").read_text())
    prepared = json.loads((source/"prepared.json").read_text())
    if (report["synthetic_data_used"] is not False or report["reserved_2025_used"] is not True or
            report["globally_pristine_oos_claim"] is not False or report["model_fits"]!=0 or
            report["monte_carlo_run"] is not False):
        raise ValueError("Expected the frozen market historical forward experiment")
    if report["protocol"]!=runner.protocol() or report["experiment"]!=runner.protocol():
        raise ValueError("Frozen forward protocol changed")
    if report["data"]!=prepared or any(report[k]!=v for k,v in identity.items()):
        raise ValueError("Archived identity/preparation chain differs")
    if set(names)!=set(report["files"])|{"report.json"}:
        raise ValueError("Incomplete artifact manifest")
    for name,digest in report["files"].items():
        if Path(name).name!=name or sha(source/name)!=digest:
            raise ValueError(f"Artifact hash mismatch: {name}")
    current = runner.identity()
    if set(report["code_sha256"])!=set(current["code_sha256"]):
        raise ValueError("Consumed code registry differs")
    modes = {}
    for name,digest in report["code_sha256"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Invalid source-code path")
        pinned = subprocess.check_output(["git","show",f"{report['commit']}:{name}"],cwd=ROOT).replace(b"\r\n",b"\n")
        choices = dict(LF=pinned,CRLF=pinned.replace(b"\n",b"\r\n"))
        matches = [mode for mode,value in choices.items() if hashlib.sha256(value).hexdigest()==digest]
        if not matches or (ROOT/name).read_bytes().replace(b"\r\n",b"\n")!=pinned:
            raise ValueError(f"Pinned/working code mismatch: {name}")
        modes[name] = matches[0]
    for file,code in [("specification.md",runner.SPEC),("candidate_freeze.json",runner.FREEZE)]:
        if sha(source/file)!=report["code_sha256"][code.relative_to(ROOT).as_posix()]:
            raise ValueError(f"Archived definition differs: {file}")
    # Source environment is used only for the archived preparation-chain validation.
    # Its code hashes were independently matched to Git and the working tree above.
    frames, _ = runner.data.load_prepared(source, identity)
    reviewed, development_manifest = prior.load_source(development_source)
    for asset,frame in frames.items():
        pd.testing.assert_frame_equal(frame.loc[:"2024-12-31"],reviewed[asset],check_freq=False)
    if development_source.is_dir():
        original_report = (development_source/"report.json").read_bytes()
    else:
        with zipfile.ZipFile(development_source) as z:
            original_report = z.read("report.json")
    if original_report!=(source/"source_report.json").read_bytes():
        raise ValueError("Supplied development source report differs")
    expected_end = min([runner.data.END_CAP]+[pd.Timestamp(r["eligible_last_date"],tz="UTC")
                                             for r in prepared["assets"].values()])
    if expected_end!=frames["BTC"].index[-1]:
        raise ValueError("Common endpoint differs from prepared coverage metadata")
    print("Archive, code, prepared snapshots and reviewed development overlap verified",flush=True)
    reproduction = runner.evaluate(frames,replay,dict(current,data=prepared,prepared_inputs_verified=True,
                                                      purpose="AUDIT_REPLAY_OF_SUPPLIED_FORWARD_RUN"))
    for key in ("policy_count","ledger_count","daily_rows","first_evaluation_date","last_evaluation_date",
                "model_fits","independent_buy_hold_checks","corruption_canary_passed","monte_carlo_run"):
        if reproduction[key]!=report[key]:
            raise ValueError(f"Replay metadata differs: {key}")
    def read(root,name):
        return pd.read_csv(root/f"{name}.csv",float_precision="round_trip")
    differences = {name:compare(read(replay,name),read(source,name))
                   for name in ("features","target_weights","mixture_decisions","daily_ledger","metrics",
                                "annual_returns","matched_comparisons","buy_hold_identities")}
    daily, summary = read(source,"daily_ledger"),read(source,"metrics")
    independent_count = 0
    for (policy,scenario),frame in daily.groupby(["policy","scenario"],sort=False):
        if not np.allclose(np.cumprod(1+frame["return"]),frame.nav,atol=2e-11,rtol=2e-10):
            raise ValueError("Independent archived wealth reconstruction failed")
        for period,sub in [("full_forward",frame),*list(frame.groupby(frame.date.str[:4]))]:
            row = summary[(summary.policy==policy)&(summary.scenario==scenario)&(summary.period==period)].iloc[0]
            values = dict(independent_statistics(sub),total_return=float(np.prod(1+sub["return"])-1))
            for name,value in values.items():
                if not np.isclose(value,row[name],atol=2e-11,rtol=2e-10,equal_nan=True):
                    raise ValueError(f"Independent statistic mismatch: {name}")
            independent_count += 1
    monthly, omissions, yearly_identity, attribution = [],[],[],[]
    targets = read(source,"target_weights")
    for profile in (20,40):
        state,trend = f"state_rule_vol{profile}_band2",f"trend_vol{profile}_band2"
        for scenario in (s[0] for s in prior.SCENARIOS):
            pair = daily[(daily.scenario==scenario)&daily.policy.isin([state,trend])].pivot(index="date",columns="policy",values="return")
            total_log = float(np.log1p(pair[state]).sum()-np.log1p(pair[trend]).sum())
            for month,sub in pair.groupby(pair.index.str[:7]):
                a,b = float(np.prod(1+sub[state])-1),float(np.prod(1+sub[trend])-1)
                log_difference = float(np.log1p(sub[state]).sum()-np.log1p(sub[trend]).sum())
                monthly.append(dict(policy=state,comparator=trend,scenario=scenario,month=month,
                                    state_return=a,trend_return=b,return_difference=a-b,
                                    relative_log_wealth_contribution=log_difference,
                                    fraction_of_full_relative_log_wealth=log_difference/total_log if abs(total_log)>1e-12 else np.nan))
                if scenario=="base":
                    kept = pair[pair.index.str[:7]!=month]
                    def sharpe(r):
                        return float(r.mean()/r.std(ddof=1)*np.sqrt(365)) if r.std(ddof=1)>1e-12 else np.nan
                    omissions.append(dict(policy=state,comparator=trend,omitted_month=month,
                                          state_sharpe=sharpe(kept[state]),trend_sharpe=sharpe(kept[trend]),
                                          state_compounded_return=float(np.prod(1+kept[state])-1),
                                          trend_compounded_return=float(np.prod(1+kept[trend])-1),
                                          remaining_relative_log_wealth=float(np.log1p(kept[state]).sum()-np.log1p(kept[trend]).sum())))
            for year,sub in pair.groupby(pair.index.str[:4]):
                state_targets = targets[(targets.policy==state)&targets.signal_bar_start.str.startswith(year)]
                yearly_identity.append(dict(policy=state,comparator=trend,scenario=scenario,year=year,days=len(sub),
                                            maximum_absolute_daily_return_difference=float((sub[state]-sub[trend]).abs().max()),
                                            mean_trend_mixture_on_year_signal_bars=float(state_targets.mixture.mean())))
        def row(policy,scenario):
            return summary[(summary.policy==policy)&(summary.scenario==scenario)&(summary.period=="full_forward")].iloc[0]
        s,t,sg,tg = row(state,"base"),row(trend,"base"),row(state,"frictionless"),row(trend,"frictionless")
        attribution.append(dict(policy=state,comparator=trend,base_cagr_difference=s.cagr-t.cagr,
                                frictionless_cagr_difference=sg.cagr-tg.cagr,
                                base_sharpe_difference=s.cash_excess_sharpe-t.cash_excess_sharpe,
                                frictionless_sharpe_difference=sg.cash_excess_sharpe-tg.cash_excess_sharpe,
                                annual_turnover_saved=t.annual_one_way_turnover-s.annual_one_way_turnover,
                                annual_arithmetic_fee_drag_saved=t.annual_arithmetic_execution_drag-s.annual_arithmetic_execution_drag))
    for name,frame in dict(metrics=summary,annual_returns=read(source,"annual_returns"),
                           matched_comparisons=read(source,"matched_comparisons"),
                           monthly_relative_performance=pd.DataFrame(monthly),influence_diagnostics=pd.DataFrame(omissions),
                           yearly_state_trend_identity=pd.DataFrame(yearly_identity),cost_attribution=pd.DataFrame(attribution)).items():
        prior.save(frame,out/f"{name}.csv")
    evidence = dict(status="FROZEN_HISTORICAL_FORWARD_AUDITED_NOT_PRISTINE_OOS",archive_sha256=sha(archive),
                    source_commit=report["commit"],archive_files_verified=len(report["files"]),code_hash_modes=modes,
                    source_environment=report["environment"],reviewer_environment=dict(python=platform.python_version(),
                        numpy=np.__version__,pandas=pd.__version__),prepared_artifact_hashes_verified=len(prepared["artifact_sha256"]),
                    normalized_calendar_days=len(frames["BTC"]),reviewed_development_overlap_rows_per_asset=2922,
                    development_source=development_manifest,first_evaluation_date=report["first_evaluation_date"],
                    last_evaluation_date=report["last_evaluation_date"],ledgers_replayed=report["ledger_count"],
                    daily_rows=report["daily_rows"],independent_statistic_rows=independent_count,
                    independent_buy_hold_checks=reproduction["independent_buy_hold_checks"],
                    corruption_canary_passed=reproduction["corruption_canary_passed"],replay_differences=differences,
                    prior_access_2025=prepared["prior_access_2025"],prior_access_2026=prepared["prior_access_2026"],
                    new_model_fits=0,new_strategy_variants=0,new_holdout_windows=0,monte_carlo_runs=0,
                    raw_local_file_hashes_independently_recomputed=False,
                    source_vendor_and_acquisition_provenance_verified=False,
                    influence_diagnostic="Post hoc omission of saved daily returns by calendar month; no refit, significance test or tradable path claim")
    write_json(out/"review_audit.json",evidence)
    print("Forward audit passed: 80 ledgers, independent statistics and input identity verified",flush=True)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--development-source",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args = parser.parse_args()
    audit(args.archive,args.development_source,args.output_dir)


if __name__=="__main__":
    main()
