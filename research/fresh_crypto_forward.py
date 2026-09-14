"""Frozen 2025+ historical forward validation of fixed crypto rules; no model search."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from research import fresh_crypto_long_history as prior
from research import fresh_crypto_forward_data as data
from research.fresh_crypto_ml.features import Panel
from research.fresh_crypto_ml.portfolio import simulate
from research.fresh_discovery.data import sha, write_json

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT/"docs/research/FRESH_CRYPTO_FORWARD_20260914.md"
FREEZE = ROOT/"docs/research/evidence/fresh_crypto_long_history_20260914/market_review/candidate_freeze.json"
FREEZE_SHA256 = "b8676a153882587c55b8bbeb76d59022490e12c960920473d0f7d087f4585230"
CANDIDATES = ("state_rule_vol20_band2", "state_rule_vol40_band2")
NEW_FILES = ["research/fresh_crypto_forward.py", "research/fresh_crypto_forward_data.py",
             "scripts/local/run_fresh_crypto_forward.ps1", "tests/test_fresh_crypto_forward.py",
             SPEC.relative_to(ROOT).as_posix(), FREEZE.relative_to(ROOT).as_posix()]


def protocol() -> dict:
    return json.loads(json.dumps(dict(version=1, candidates=list(CANDIDATES), primary_candidate=CANDIDATES[0],
                higher_risk_alternative=CANDIDATES[1], compare_all_original_20_policies=True,
                unchanged_strategy=prior.experiment(), first_evaluation_date="2025-01-01",
                development_dates_in_unchanged_strategy_are_not_forward_dates=True,
                end_rule="minimum_specified_file_last_daily_date_capped_at_2026-08-26",
                minimum_end_date="2025-12-31", initial_inventory="fresh_cash_1_for_every_policy",
                first_signal="2024-12-30", first_base_fill="2025-01-01", first_delayed_fill="2025-01-02",
                weekly_state="inherited_from_original_2018_schedule_no_extra_January_1_state_decision",
                period_boundary="no_2026_inventory_reset", final_exit="common_last_day_open_with_fees",
                report_periods=["full_forward", "2025", "2026_if_present"],
                role_of_2026="partial_historical_extension_prior_access_unresolved_unless_operator_classifies",
                selection_rule="report_both_risk_profiles_no_forward_parameter_selection",
                model_fits=0, monte_carlo_run=False, globally_pristine_oos_claim=False)))


def verify_frozen_strategy() -> None:
    content = FREEZE.read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(content).hexdigest()!=FREEZE_SHA256:
        raise ValueError("Candidate freeze changed")
    freeze = json.loads(content)
    if freeze["strategy_definition"]!=json.loads(json.dumps(prior.experiment())):
        raise ValueError("Original strategy registry changed")
    for name, digest in freeze["source_code_sha256"].items():
        normalized = (ROOT/name).read_bytes().replace(b"\r\n", b"\n")
        if digest not in {hashlib.sha256(v).hexdigest() for v in (normalized, normalized.replace(b"\n",b"\r\n"))}:
            raise ValueError(f"Frozen strategy dependency changed: {name}")


def identity() -> dict:
    import subprocess
    verify_frozen_strategy()
    result = prior.identity()
    if subprocess.check_output(["git","status","--porcelain","--",*NEW_FILES],cwd=ROOT,text=True).strip():
        raise ValueError("Commit consumed forward code/specification before a market run")
    result["code_sha256"].update({name:sha(ROOT/name) for name in NEW_FILES})
    result["protocol"] = protocol()
    return result


def make_schedules(panel: Panel):
    """Continue causal weekly state choices, but begin all holdings from cash in 2025."""
    first = panel.dates.get_loc(data.FORWARD_START)-2
    if first<365 or first+3>=len(panel.dates):
        raise ValueError("Insufficient forward warm-up or evaluation calendar")
    original, targets, decisions = prior.make_schedules(panel)
    schedules, rows = {}, []
    for policy in prior.policies():
        if policy.role=="benchmark":
            # The original benchmark's only order was in 2018. Enter the same weights now.
            weights, coefficient = original[policy.name][min(original[policy.name])]
            schedule = {first:(weights.copy(), coefficient)}
            rows.append(dict(policy=policy.name, signal_index=first, signal_bar_start=str(panel.dates[first]),
                             feature_available=str(panel.dates[first]+pd.Timedelta(days=1)),
                             base_fill_time=str(data.FORWARD_START), BTC=weights[0], ETH=weights[1],
                             USD=1-weights.sum(), mixture=coefficient))
        else:
            schedule = {t:value for t,value in original[policy.name].items() if t>=first}
        schedules[policy.name] = schedule
    targets = pd.concat([targets[(targets.signal_index>=first) & ~targets.policy.isin(
        [p.name for p in prior.policies() if p.role=="benchmark"])], pd.DataFrame(rows)],ignore_index=True)
    # Include each active policy's most recent pre-entry state decision for auditability.
    kept = []
    for _, frame in decisions.groupby("policy",sort=False):
        previous = frame[frame.signal_index<first].tail(1)
        kept.append(pd.concat([previous,frame[frame.signal_index>=first]]))
    decisions = pd.concat(kept,ignore_index=True)
    decisions["carried_before_initial_entry"] = decisions.signal_index<first
    return schedules, targets, decisions, first


def verify_ledger(ledger, panel, policy, cost_bps, delay, first):
    def check(a, b, message):
        if not np.allclose(a,b,atol=2e-11,rtol=2e-10):
            raise ValueError(message)
    check(np.cumprod(1+ledger["return"]),ledger.nav,"Independent wealth reconstruction failed")
    check(ledger.BTC_pnl+ledger.ETH_pnl,ledger["return"],"Independent asset P&L identity failed")
    check(ledger.BTC_weight+ledger.ETH_weight+ledger.USD_weight,1.,"Full-equity weights failed")
    if ledger.date.iloc[0]!="2025-01-01" or ledger.risky_exposure.iloc[-1]!=0 or not ledger.terminal_liquidation.iloc[-1]:
        raise ValueError("Forward entry/terminal boundary failed")
    fills = ledger[ledger.executed & ~ledger.terminal_liquidation]
    if policy.family!="usd_cash" and (fills.empty or fills.date.iloc[0]!=str(panel.dates[first+2+delay].date())):
        raise ValueError("Incorrect first fill date")
    if delay and (ledger.iloc[:delay].risky_exposure.ne(0).any() or ledger.iloc[:delay]["return"].ne(0).any()):
        raise ValueError("Delayed entry must remain in cash")
    if policy.family in ("btc_buy_hold","eth_buy_hold","mix_buy_hold"):
        weights = np.array(dict(btc_buy_hold=[1.,0.],eth_buy_hold=[0.,1.],mix_buy_hold=[.5,.5])[policy.family])
        rate = cost_bps/10_000
        expected = float(weights @ (panel.opens[-1]/panel.opens[first+2+delay]))*(1-rate)/(1+rate)
        check(ledger.nav.iloc[-1],expected,"Independent buy-and-hold fee/price identity failed")
        return dict(expected_nav=expected,reported_nav=float(ledger.nav.iloc[-1]),residual=float(ledger.nav.iloc[-1]-expected))
    return None


def evaluate(frames: dict, out: Path, run_identity: dict) -> dict:
    synthetic = run_identity.get("synthetic_data_used")
    if not isinstance(synthetic,bool):
        raise ValueError("Explicit synthetic_data_used boolean is required")
    end = frames["BTC"].index[-1]
    for frame in frames.values():
        data.validate_daily(frame,end)
    if end<data.FORWARD_START+pd.Timedelta(days=30) or end>data.END_CAP or (not synthetic and end<data.MIN_END):
        raise ValueError("Forward evaluation outside frozen calendar bounds")
    if not synthetic:
        if run_identity.get("prepared_inputs_verified") is not True or run_identity.get("protocol")!=protocol():
            raise ValueError("Market evaluation requires the verified prepared input protocol")
        if run_identity["data"]["last_evaluation_date"]!=str(end.date()):
            raise ValueError("Prepared common endpoint changed")
    if (out/"identity_before_evaluation.json").exists() or (out/"report.json").exists():
        raise FileExistsError("Use a new run; evaluation cannot overwrite or resume an existing result")
    status = "SYNTHETIC_MECHANICS_ONLY" if synthetic else "LOCKED_HISTORICAL_FORWARD_VALIDATION_NOT_PRISTINE_OOS"
    record = dict(run_identity,status=status,experiment=protocol(),model_fits=0,monte_carlo_run=False,
                  reserved_2025_used=not synthetic,globally_pristine_oos_claim=False)
    write_json(out/"identity_before_evaluation.json",record)
    print(status,flush=True)
    panel = Panel(frames)
    schedules, targets, decisions, first = make_schedules(panel)
    other, other_targets, other_decisions, other_first = make_schedules(panel)
    if (first!=other_first or prior.csv(targets)!=prior.csv(other_targets) or
            prior.csv(decisions)!=prior.csv(other_decisions)):
        raise ValueError("Forward schedule replay failed")
    prior.save(panel.frame().query("signal_index >= @first"),out/"features.csv")
    prior.save(targets,out/"target_weights.csv")
    prior.save(decisions,out/"mixture_decisions.csv")
    ledgers, summaries, annual, identities = [], [], [], []
    for scenario,cost,delay in prior.SCENARIOS:
        for policy in prior.policies():
            ledger = simulate(panel,schedules[policy.name],policy,cost,delay,first)
            replay = simulate(panel,other[policy.name],policy,cost,delay,first)
            if prior.csv(ledger)!=prior.csv(replay):
                raise ValueError(f"Ledger replay failed: {scenario}/{policy.name}")
            proof = verify_ledger(ledger,panel,policy,cost,delay,first)
            if proof is not None:
                identities.append(dict(policy=policy.name,scenario=scenario,**proof))
            ledger["policy"],ledger["scenario"] = policy.name,scenario
            ledgers.append(ledger)
            periods = [("full_forward",ledger),*[(str(year),sub) for year,sub in ledger.groupby(ledger.date.str[:4])]]
            for period,sub in periods:
                if len(sub)>1:
                    summaries.append(dict(policy=policy.name,family=policy.family,profile=policy.target,band=policy.band,
                                          role="candidate" if policy.name in CANDIDATES else "comparator",
                                          scenario=scenario,period=period,first_date=sub.date.iloc[0],last_date=sub.date.iloc[-1],
                                          days=len(sub),total_return=float((1+sub["return"]).prod()-1),
                                          executed_rebalances=int(sub.executed.sum()),
                                          skipped_rebalances=int((sub.execution_reason=="inside_band").sum()),**prior.metrics(sub)))
                if period!="full_forward":
                    annual.append(dict(policy=policy.name,scenario=scenario,year=int(period),days=len(sub),
                                       total_return=float((1+sub["return"]).prod()-1)))
        print(f"{scenario}: 20 forward ledgers reconciled and replayed exactly",flush=True)
    daily,summary = pd.concat(ledgers,ignore_index=True),pd.DataFrame(summaries)
    prior.save(daily,out/"daily_ledger.csv")
    prior.save(summary,out/"metrics.csv")
    prior.save(pd.DataFrame(annual),out/"annual_returns.csv")
    prior.save(pd.DataFrame(identities),out/"buy_hold_identities.csv")
    pairs = []
    for row in summary[summary.role=="candidate"].itertuples():
        controls = summary[(summary.scenario==row.scenario)&(summary.period==row.period)&(
            ((summary.profile==row.profile)&(summary.band==row.band)&summary.family.isin(("trend","allocation","fixed_blend"))) |
            summary.family.isin(("btc_buy_hold","eth_buy_hold","mix_buy_hold","usd_cash")))]
        for control in controls.itertuples():
            pairs.append(dict(policy=row.policy,comparator=control.policy,scenario=row.scenario,period=row.period,
                              matched_risk_setting=control.family in prior.FAMILIES,
                              cagr_difference=row.cagr-control.cagr,sharpe_difference=row.cash_excess_sharpe-control.cash_excess_sharpe,
                              drawdown_difference=row.max_drawdown-control.max_drawdown,
                              volatility_difference=row.annual_volatility-control.annual_volatility))
    prior.save(pd.DataFrame(pairs),out/"matched_comparisons.csv")
    # Runtime canary confirms the independent checker can reject a changed return.
    canary = daily[(daily.policy=="btc_buy_hold")&(daily.scenario=="base")].copy()
    canary.loc[canary.index[0],"return"] += .001
    try:
        verify_ledger(canary,panel,next(p for p in prior.policies() if p.family=="btc_buy_hold"),30.,0,first)
    except ValueError as exc:
        if "wealth reconstruction" not in str(exc):
            raise
    else:
        raise ValueError("Corruption canary failed")
    base = summary[(summary.scenario=="base")&(summary.period=="full_forward")]
    lines = [f"# {status}","","Frozen fixed rules; 20 policies, four scenarios; no ML fit or parameter search.",
             f"Calendar: 2025-01-01 through {end.date()}; each portfolio starts from cash.",
             "Weekly state decisions continue from the original schedule; 2026 inventory carries over.",
             "Base 30 bps one way; stress 75 bps; separate extra-day delay; unlevered spot; cash yield zero.",
             "2025 was inspected in earlier repo research; 2026 prior access is recorded in prepared.json.",
             "This is historical forward validation, not globally untouched OOS or prospective trading.","",
             "| Policy | Total return | CAGR | Sharpe | Max DD |","|---|---:|---:|---:|---:|"]
    for row in base.itertuples():
        lines.append(f"| {row.policy} | {row.total_return:.2%} | {row.cagr:.2%} | {row.cash_excess_sharpe:.3f} | {row.max_drawdown:.2%} |")
    lines += ["","Annual and partial-year totals are in annual_returns.csv. Annualized short-period figures are not forecasts.",
              "Full period and year slices use the same continuous ledger; slices do not charge fictitious year-end exits.",
              "All holdings liquidate at the common final open, with fees. Daily marks omit intraday drawdowns.",
              "Raw-file hashes and overlap checks establish reproducibility, not vendor or venue provenance.",
              "Compare both frozen candidates against matched controls under all scenarios; no automatic promotion gate."]
    (out/"README.md").write_text("\n".join(lines)+"\n",encoding="utf-8",newline="\n")
    report = dict(record,policy_count=20,ledger_count=len(ledgers),daily_rows=len(daily),
                  first_evaluation_date="2025-01-01",last_evaluation_date=str(end.date()),
                  exact_replay_passed=True,independent_buy_hold_checks=len(identities),corruption_canary_passed=True,
                  maximum_accounting_residual=float(daily.accounting_residual.abs().max()),
                  files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!="report.json"})
    write_json(out/"report.json",report)
    print(base[["policy","cagr","cash_excess_sharpe","max_drawdown"]].to_string(index=False),flush=True)
    return report


def bundle(out: Path) -> Path:
    path = Path(str(out)+".zip")
    if path.exists():
        raise FileExistsError(path)
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for file in sorted(out.iterdir()):
            if file.is_file():
                archive.write(file,file.name)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare",action="store_true")
    mode.add_argument("--evaluate-prepared",action="store_true")
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--source-run",type=Path)
    parser.add_argument("--data-root",type=Path,default=ROOT.parent/"ID_test"/"data")
    parser.add_argument("--btc-csv",type=Path)
    parser.add_argument("--eth-csv",type=Path)
    parser.add_argument("--prior-access-2026",choices=("unknown","already_inspected","not_known_inspected"),default="unknown")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if args.prepare:
        if out.exists() or Path(str(out)+".zip").exists():
            parser.error("Use a new output directory; never overwrite an existing run")
        out.mkdir(parents=True)
        try:
            run_identity = identity()
            (out/"specification.md").write_bytes(SPEC.read_bytes())
            (out/"candidate_freeze.json").write_bytes(FREEZE.read_bytes())
            source = data.resolve_source(args.source_run,ROOT)
            paths = {a:getattr(args,f"{a.lower()}_csv") or args.data_root/name for a,name in data.FILENAMES.items()}
            prepared = data.snapshot(source,paths,out,run_identity,args.prior_access_2026)
        except (OSError,ValueError,KeyError,zipfile.BadZipFile) as exc:
            write_json(out/"data_check_error.json",dict(status="PREPARATION_FAILED_NO_STRATEGY_EVALUATION",error=str(exc)))
            print(f"SHARE DATA CHECK ZIP: {bundle(out)}",flush=True)
            parser.exit(2,f"Data preparation failed: {exc}\n")
        print(f"Prepared local snapshot: {prepared['first_evaluation_date']} through {prepared['last_evaluation_date']}; downloads 0",flush=True)
        print(f"2026 prior access: {prepared['prior_access_2026']}; no strategy evaluated during preparation.",flush=True)
    else:
        try:
            if not out.is_dir() or Path(str(out)+".zip").exists():
                raise ValueError("Supply a fresh prepared directory, without an existing results ZIP")
            current = identity()
            frames,prepared = data.load_prepared(out,current)
            evaluate(frames,out,dict(current,data=prepared,prepared_inputs_verified=True))
            print(f"\nSHARE FORWARD RESULTS ZIP: {bundle(out)}",flush=True)
        except (OSError,ValueError,KeyError) as exc:
            parser.exit(2,f"Forward evaluation stopped: {exc}. Partial output: {out}\n")


if __name__=="__main__":
    main()
