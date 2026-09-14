"""Audit the supplied fixed longer-history run; no new variant or reserved data."""
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

from research import fresh_crypto_long_history as runner
from research.fresh_discovery.data import sha, write_json
from scripts.review_fresh_crypto_discovery import compare

ROOT = Path(__file__).resolve().parents[1]


def independent_statistics(frame):
    r = frame["return"].to_numpy()
    wealth = np.cumprod(1+r)
    years = (pd.Timestamp(frame.date.iloc[-1])-pd.Timestamp(frame.date.iloc[0])).days/365.25
    deviation = np.std(r, ddof=1)
    cagr = wealth[-1]**(1/years)-1
    drawdown = float(np.min(wealth/np.maximum.accumulate(np.r_[1., wealth])[1:]-1))
    return dict(cagr=cagr, max_drawdown=drawdown,
                cash_excess_sharpe=float(np.mean(r)/deviation*np.sqrt(365)) if deviation>1e-12 else np.nan,
                annual_volatility=deviation*np.sqrt(365),
                calmar=cagr/-drawdown if drawdown < -1e-12 else np.nan)


def audit(archive, out):
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
            if Path(name).name!=name or "\\" in name or name in (".", ".."):
                raise ValueError("Only flat archive filenames are accepted")
            (source/name).write_bytes(z.read(name))
    report = json.loads((source/"report.json").read_text())
    if report["experiment"]!=json.loads(json.dumps(runner.experiment())):
        raise ValueError("Fixed experiment registry differs")
    if report["synthetic_data_used"] is not False or report["reserved_2025_used"] is not False:
        raise ValueError("Expected a pre-2025 market development run")
    if report["model_fits"]!=0 or report["monte_carlo_run"] is not False:
        raise ValueError("Expected an unfitted fixed-rule experiment")
    if set(names)!=set(report["files"]) | {"report.json", "specification.md"}:
        raise ValueError("Incomplete file manifest")
    for name, digest in report["files"].items():
        if Path(name).name!=name or sha(source/name)!=digest:
            raise ValueError(f"Artifact hash mismatch: {name}")
    code_modes = {}
    for name, digest in report["code_sha256"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Invalid code path")
        pinned = subprocess.check_output(["git", "show", f"{report['commit']}:{name}"], cwd=ROOT).replace(b"\r\n", b"\n")
        choices = dict(LF=pinned, CRLF=pinned.replace(b"\n", b"\r\n"))
        matches = [mode for mode, value in choices.items() if hashlib.sha256(value).hexdigest()==digest]
        if not matches or (ROOT/name).read_bytes().replace(b"\r\n", b"\n")!=pinned:
            raise ValueError(f"Pinned/working code mismatch: {name}")
        code_modes[name] = matches[0]
    if sha(source/"specification.md")!=report["code_sha256"][runner.SPEC.relative_to(ROOT).as_posix()]:
        raise ValueError("Archived specification differs")
    frames, _ = runner.load_source(source)
    print("Archive, code, specification and pinned input identities verified", flush=True)
    reproduced = runner.evaluate(frames, replay, dict(synthetic_data_used=False,
                                 purpose="REPLAY_OF_SUPPLIED_FIXED_RUN", source_commit=report["commit"]))
    for key in ("policy_count", "ledger_count", "daily_rows", "model_fits", "independent_buy_hold_checks",
                "first_evaluation_date", "last_evaluation_date", "reserved_2025_used", "monte_carlo_run"):
        if reproduced[key]!=report[key]:
            raise ValueError(f"Run metadata differs: {key}")
    differences = {}
    def read(root, name):
        return pd.read_csv(root/f"{name}.csv", float_precision="round_trip")
    for name in ("features", "target_weights", "mixture_decisions", "daily_ledger", "metrics",
                 "annual_returns", "matched_comparisons", "buy_hold_identities"):
        differences[name] = compare(read(replay, name), read(source, name))
    daily, summary = read(source, "daily_ledger"), read(source, "metrics")
    deletions, annual_pairs = [], []
    independent_count = 0
    for (policy, scenario), frame in daily.groupby(["policy", "scenario"], sort=False):
        if not np.allclose(np.cumprod(1+frame["return"]), frame.nav, atol=2e-11, rtol=2e-10):
            raise ValueError("Independent archived wealth reconstruction failed")
        periods = (("full", frame), ("2018_2019", frame[frame.date<"2020-01-01"]),
                   ("2020_2021", frame[(frame.date>="2020-01-01") & (frame.date<"2022-01-01")]),
                   ("2022_2024", frame[frame.date>="2022-01-01"]),
                   ("2020_2024_carry", frame[frame.date>="2020-01-01"]))
        for period, sub in periods:
            row = summary[(summary.policy==policy) & (summary.scenario==scenario) & (summary.period==period)].iloc[0]
            for key, value in independent_statistics(sub).items():
                if not np.isclose(value, row[key], atol=2e-11, rtol=2e-10, equal_nan=True):
                    raise ValueError(f"Independent statistic failed: {key}")
            independent_count += 1
        if scenario=="base":
            groups = [[str(y)] for y in range(2018,2025)]+[["2018","2022"]]
            for omitted in groups:
                kept = frame[~frame.date.str[:4].isin(omitted)]["return"].to_numpy()
                deviation = np.std(kept, ddof=1)
                deletions.append(dict(policy=policy, omitted_years="+".join(omitted), remaining_days=len(kept),
                                      cash_excess_sharpe=float(np.mean(kept)/deviation*np.sqrt(365)) if deviation>1e-12 else np.nan))
    annual = read(source, "annual_returns")
    for profile in (20,40):
        for treatment in ("exact","band2"):
            name = f"state_rule_vol{profile}_{treatment}"
            for scenario in (s[0] for s in runner.SCENARIOS):
                state = annual[(annual.policy==name) & (annual.scenario==scenario)].set_index("year")
                for family in ("trend","allocation","fixed_blend"):
                    other = annual[(annual.policy==f"{family}_vol{profile}_{treatment}") & (annual.scenario==scenario)].set_index("year")
                    for year in state.index:
                        annual_pairs.append(dict(policy=name, comparator=f"{family}_vol{profile}_{treatment}",
                                                 scenario=scenario, year=int(year),
                                                 state_return=state.loc[year,"total_return"], comparator_return=other.loc[year,"total_return"],
                                                 return_difference=state.loc[year,"total_return"]-other.loc[year,"total_return"]))
    attribution = []
    for profile in (20,40):
        for treatment in ("exact","band2"):
            state_name, trend_name = f"state_rule_vol{profile}_{treatment}", f"trend_vol{profile}_{treatment}"
            def row(policy, scenario):
                return summary[(summary.policy==policy) & (summary.scenario==scenario) & (summary.period=="full")].iloc[0]
            s, t, sg, tg = row(state_name,"base"), row(trend_name,"base"), row(state_name,"frictionless"), row(trend_name,"frictionless")
            attribution.append(dict(policy=state_name, comparator=trend_name,
                                    base_cagr_difference=s.cagr-t.cagr, frictionless_cagr_difference=sg.cagr-tg.cagr,
                                    base_sharpe_difference=s.cash_excess_sharpe-t.cash_excess_sharpe,
                                    frictionless_sharpe_difference=sg.cash_excess_sharpe-tg.cash_excess_sharpe,
                                    annual_turnover_saved=t.annual_one_way_turnover-s.annual_one_way_turnover,
                                    annual_arithmetic_fee_drag_saved=t.annual_arithmetic_execution_drag-s.annual_arithmetic_execution_drag))
    try:
        compare(pd.DataFrame({"return":[.01]}), pd.DataFrame({"return":[.011]}))
    except ValueError:
        pass
    else:
        raise ValueError("Numerical corruption canary failed")
    for name, frame in dict(metrics=summary, annual_returns=annual, matched_comparisons=read(source,"matched_comparisons"),
                            influence_diagnostics=pd.DataFrame(deletions), annual_state_comparisons=pd.DataFrame(annual_pairs),
                            cost_attribution=pd.DataFrame(attribution)).items():
        runner.save(frame, out/f"{name}.csv")
    evidence = dict(status="FIXED_LONG_HISTORY_DEVELOPMENT_AUDITED_NOT_OOS", archive_sha256=sha(archive),
                    source_commit=report["commit"], archive_files_verified=len(report["files"]), code_hash_modes=code_modes,
                    source_environment=report["environment"], reviewer_environment=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__),
                    source_calendar_days=2922, first_evaluation_date=report["first_evaluation_date"], last_evaluation_date=report["last_evaluation_date"],
                    ledgers_replayed=report["ledger_count"], daily_rows=report["daily_rows"],
                    independent_buy_hold_checks=reproduced["independent_buy_hold_checks"], independent_statistic_rows=independent_count,
                    replay_differences=differences, numerical_corruption_canary_passed=True,
                    model_fits=0, new_strategy_variants=0, holdout_evaluations=0, monte_carlo_runs=0,
                    source_vendor_and_acquisition_provenance_verified=False,
                    influence_diagnostic="Saved daily returns with calendar years omitted; no refit, inference or OOS claim")
    write_json(out/"review_audit.json", evidence)
    print("Longer-history audit passed: all ledgers, reported metrics and independent statistics verified", flush=True)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    audit(args.archive, args.output_dir)


if __name__=="__main__":
    main()
