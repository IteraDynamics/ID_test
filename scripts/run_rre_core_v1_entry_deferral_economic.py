from __future__ import annotations

if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError:
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from research.core_regime_stability.study import panel_from_hourly
from research.harness.backtest_engine import run_backtest
from research.harness.cross_asset_state import compute_btc_macro_state, inject_btc_macro_state
from research.harness.metrics import compute_metrics
from research.harness.resampler import align_equity_curves
from research.rre_deferral_strategy import RREDeferralStrategy
from research.rre_entry_deferral import ELIGIBLE_SLEEVES, training_q80
from research.rre_frozen_instability import FrozenInstabilityModel
from runtime.core_v1.allocation import SELECTED_CORE_V1_SCENARIO, SELECTED_CORE_V1_SLEEVES, validate_selected_allocation
from scripts.run_campaign52_governed_equivalence import SOURCE_SHA256, sha256_file
from scripts.run_core_v1_sleeve_contribution_audit import load_data, make_execution_configs, sleeve_df, strategy_for
from scripts.run_multi_strategy_fund import SleeveSpec, _build_sleeves
from scripts.run_multi_strategy_walkforward import _build_folds

EXPECTED_SCENARIO = "candidate_btc1h_hedges_to_btc4h_gld_qqq"
BASE_COST = dict(fee=.0006, equity_fee=.0001, base_slippage=3.0, slippage_vol_factor=50.0)
STRESS_COST = dict(fee=.0012, equity_fee=.0002, base_slippage=6.0, slippage_vol_factor=100.0)
RRE_SOURCE_SHA256 = {
    "btc_data": SOURCE_SHA256["btc_data"],
    "eth_data": SOURCE_SHA256["eth_data"],
    "spy_data": "5c7461eb6fc265e1f53b7e68e51e4386e28720cb6095da14556feae0f6abc911",
    "qqq_data": "7f3c42c05390a86bf8d9f1e3f4990eddc9163ab46ad8855a87120ecf08504cde",
    "bil_data": "174f541610e8f34246837ada83c9346c20d5df5805af5349cf6ec043d8265022",
    "gld_data": "1942a0e13c92487a72bb5c1e6f13b0317ab7f99cb3f798d9d0d279df91630477",
}


class RREEconomicError(RuntimeError):
    pass


def parse_args():
    p=argparse.ArgumentParser(description="Offline governed Core v1 vs frozen RRE entry-deferral experiment.")
    p.add_argument("--btc-data",default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--eth-data",default="data/ethusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--spy-data",default="data/SPY_1D.csv");p.add_argument("--qqq-data",default="data/QQQ_1D.csv")
    p.add_argument("--bil-data",default="data/BIL_1D.csv");p.add_argument("--gld-data",default="data/GLD_1D.csv")
    p.add_argument("--data-start",default="2018-01-01");p.add_argument("--oos-start",default="2020-01-01");p.add_argument("--oos-end",default="2025-12-31")
    p.add_argument("--capital",type=float,default=100000.0);p.add_argument("--rebalance-threshold",type=float,default=.02)
    p.add_argument("--cooldown",type=int,default=2);p.add_argument("--mr-cooldown",type=int,default=12)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--out-dir",default="artifacts/rre_core_v1_entry_deferral")
    p.add_argument("--cost-case",choices=("base","stress"),default="base")
    return p.parse_args()


def verify(args):
    validate_selected_allocation()
    if SELECTED_CORE_V1_SCENARIO != EXPECTED_SCENARIO: raise RREEconomicError("CORE_SCENARIO_DRIFT")
    active={s.label:s.weight for s in SELECTED_CORE_V1_SLEEVES}
    expected={"BTC_4H_trend":.15,"ETH_1H_trend":.10,"ETH_4H_trend":.10,"SPY_1D_equity":.175,"QQQ_1D_equity":.275,"GLD_1D_gold":.20}
    if active != expected: raise RREEconomicError(f"CORE_ALLOCATION_DRIFT:{active}")
    hashes={}
    for key,expected_hash in RRE_SOURCE_SHA256.items():
        actual=sha256_file(Path(getattr(args,key)))
        if actual != expected_hash: raise RREEconomicError(f"SOURCE_SHA256_MISMATCH:{key}:{actual}")
        hashes[key]=actual
    return hashes


def ns_for(args,cost):
    return SimpleNamespace(
        btc_data=args.btc_data,eth_data=args.eth_data,spy_data=args.spy_data,qqq_data=args.qqq_data,bil_data=args.bil_data,gld_data=args.gld_data,
        data_start=args.data_start,capital=args.capital,trend_weight=.40,equity_weight=.35,gold_weight=.15,hedge_weight=.10,mr_weight=0.,
        fee=cost["fee"],equity_fee=cost["equity_fee"],base_slippage=cost["base_slippage"],slippage_vol_factor=cost["slippage_vol_factor"],
        cooldown=args.cooldown,mr_cooldown=args.mr_cooldown,rebalance_threshold=args.rebalance_threshold,
    )


def selected_specs(run_args):
    base={s.label:s for s in _build_sleeves(run_args)}
    out=[]
    for chosen in SELECTED_CORE_V1_SLEEVES:
        if chosen.label not in base: raise RREEconomicError(f"MISSING_BASE_SLEEVE:{chosen.label}")
        s=base[chosen.label]
        out.append(SleeveSpec(
            label=s.label,
            family=s.family,
            asset=s.asset,
            timeframe=s.timeframe,
            strategy=s.strategy,
            capital=run_args.capital*chosen.weight,
        ))
    return out


def prepare_df(raw_window,spec,btc_state_window,spy_window,btc_para_window):
    df=sleeve_df(raw_window,spec)
    if spec.family=="trend": df=inject_btc_macro_state(df,btc_state_window)
    if spec.family in ("trend","hedge"):
        df=df.copy();df["spy_above_sma175"]=spy_window.reindex(df.index,method="ffill")
    if spec.family=="equity":
        df=df.copy();df["btc_in_parabolic"]=btc_para_window.reindex(df.index,method="ffill")
    return df


def metric(eq):
    m=compute_metrics(eq.dropna(),[],initial_capital=float(eq.iloc[0]))
    return dict(cagr_pct=float(m.cagr_pct),total_return_pct=float(m.total_return_pct),max_drawdown_pct=float(m.max_drawdown_pct),sharpe=float(m.sharpe),calmar=float(m.calmar),final_equity=float(m.final_equity))


def same_result(a,b,label):
    if not a.equity_curve.index.equals(b.equity_curve.index) or not np.array_equal(a.equity_curve.to_numpy(),b.equity_curve.to_numpy(),equal_nan=True):
        raise RREEconomicError(f"EXPERIMENTAL_REPLAY_EQUITY_MISMATCH:{label}")
    if not np.array_equal(a.position_series.to_numpy(),b.position_series.to_numpy(),equal_nan=True):
        raise RREEconomicError(f"EXPERIMENTAL_REPLAY_POSITION_MISMATCH:{label}")
    ta=[(t.timestamp,t.direction,t.notional_usd,t.fee_usd,t.new_exposure) for t in a.trades]
    tb=[(t.timestamp,t.direction,t.notional_usd,t.fee_usd,t.new_exposure) for t in b.trades]
    if ta!=tb: raise RREEconomicError(f"EXPERIMENTAL_REPLAY_TRADE_MISMATCH:{label}")


def run_fold(payload):
    args_dict,year,cost_case,panels=payload
    args=SimpleNamespace(**args_dict); cost=BASE_COST if cost_case=="base" else STRESS_COST; ra=ns_for(args,cost)
    raw=load_data(ra); specs=selected_specs(ra); folds=_build_folds(args.data_start,args.oos_start,args.oos_end)
    fold=next(f for f in folds if str(f.label)==str(year))
    raw_window={a:d.loc[fold.is_start:fold.oos_end] for a,d in raw.items()}
    btc_state=compute_btc_macro_state(raw["BTC"]);btc_state_window=btc_state.loc[fold.is_start:fold.oos_end]
    spy_close=raw["SPY"]["close"];spy=(spy_close>spy_close.rolling(175).mean()).rename("spy_above_sma175");spy_window=spy.loc[fold.is_start:fold.oos_end]
    para=btc_state["btc_parabolic_hard"].rename("btc_in_parabolic");para_window=para.loc[fold.is_start:fold.oos_end]
    bil=pd.read_csv(args.bil_data,index_col=0,parse_dates=True);bil_ret=pd.to_numeric(bil["close"],errors="raise").pct_change().fillna(0.0)
    base_cfg,mr_cfg,equity_cfg=make_execution_configs(ra)

    score_cache={}
    for spec in specs:
        if spec.label not in ELIGIBLE_SLEEVES: continue
        hours=4 if spec.timeframe.upper()=="4H" else 1
        key=(spec.asset,hours)
        if key in score_cache: continue
        panel=panels[(spec.asset,hours)]
        cutoff=pd.Timestamp(f"{year}-01-01",tz="UTC");end=pd.Timestamp(f"{int(year)+1}-01-01",tz="UTC")
        model=FrozenInstabilityModel.fit(panel,cutoff)
        test=panel.loc[(panel.index>=cutoff)&(panel.index<end)]
        scores=model.transform_and_score(test).sort_index()
        q80=training_q80(model.training_probabilities)
        score_cache[key]=(scores,q80,str(model.latest_training_label_end))

    control_curves={};experimental_curves={};diagnostics=[];audit=[]
    for spec in specs:
        df=prepare_df(raw_window,spec,btc_state_window,spy_window,para_window)
        cfg=equity_cfg if spec.family in ("equity","gold") else mr_cfg if spec.family=="mr" else base_cfg
        cash_yield=bil_ret.loc[fold.is_start:fold.oos_end] if spec.family in ("equity","gold") else None
        canonical_strategy=strategy_for(spec)
        control=run_backtest(df=df,strategy_module=canonical_strategy,initial_capital=spec.capital,exec_config=cfg,asset=spec.asset,rebalance_threshold=args.rebalance_threshold,cash_yield_series=cash_yield)
        control_curves[spec.label]=control.equity_curve
        if spec.label in ELIGIBLE_SLEEVES:
            hours=4 if spec.timeframe.upper()=="4H" else 1;scores,q80,latest=score_cache[(spec.asset,hours)]
            w1=RREDeferralStrategy(canonical_strategy,spec.label,scores,q80)
            exp1=run_backtest(df=df,strategy_module=w1,initial_capital=spec.capital,exec_config=cfg,asset=spec.asset,rebalance_threshold=args.rebalance_threshold,cash_yield_series=cash_yield)
            w2=RREDeferralStrategy(canonical_strategy,spec.label,scores,q80)
            exp2=run_backtest(df=df,strategy_module=w2,initial_capital=spec.capital,exec_config=cfg,asset=spec.asset,rebalance_threshold=args.rebalance_threshold,cash_yield_series=cash_yield)
            same_result(exp1,exp2,f"{year}:{spec.label}")
            experimental_curves[spec.label]=exp1.equity_curve
            for row in w1.audit: audit.append({**row,"fold":str(year),"cost_case":cost_case,"latest_training_label_end":latest})
            c=control.equity_curve.loc[fold.oos_start:fold.oos_end].dropna();e=exp1.equity_curve.loc[fold.oos_start:fold.oos_end].dropna()
            cm,em=metric(c),metric(e)
            diagnostics.append(dict(fold=str(year),sleeve=spec.label,cost_case=cost_case,control_sharpe=cm["sharpe"],experimental_sharpe=em["sharpe"],paired_sharpe_diff=em["sharpe"]-cm["sharpe"],control_return_pct=cm["total_return_pct"],experimental_return_pct=em["total_return_pct"],q80=q80,deferred=sum(1 for x in w1.audit if x["deferred"]),eligible=len(w1.audit)))
        else:
            experimental_curves[spec.label]=control.equity_curve

    cfund=align_equity_curves(control_curves,base_freq="1h").sum(axis=1).loc[fold.oos_start:fold.oos_end].dropna()
    efund=align_equity_curves(experimental_curves,base_freq="1h").sum(axis=1).loc[fold.oos_start:fold.oos_end].dropna()
    cfm,efm=metric(cfund),metric(efund)
    return dict(
        year=str(year),control_nav=cfund,experimental_nav=efund,diagnostics=diagnostics,audit=audit,
        control_fund_sharpe=cfm["sharpe"],experimental_fund_sharpe=efm["sharpe"],
        paired_fund_sharpe_diff=efm["sharpe"]-cfm["sharpe"],
    )


def stitch(results,key,capital):
    running=float(capital);parts=[]
    for r in sorted(results,key=lambda x:x["year"]):
        s=r[key];scaled=s*(running/float(s.iloc[0]));parts.append(scaled);running=float(scaled.iloc[-1])
    out=pd.concat(parts).sort_index();return out[~out.index.duplicated(keep="last")]


def evaluate_case(results,args,cost_case,out):
    c=stitch(results,"control_nav",args.capital);e=stitch(results,"experimental_nav",args.capital)
    cm,em=metric(c),metric(e)
    diag=pd.DataFrame([x for r in results for x in r["diagnostics"]]); audit=pd.DataFrame([x for r in results for x in r["audit"]])
    out.mkdir(parents=True,exist_ok=True);c.rename("control_nav").to_csv(out/"control_nav.csv");e.rename("experimental_nav").to_csv(out/"experimental_nav.csv")
    diag.to_csv(out/"sleeve_fold_diagnostics.csv",index=False);audit.to_csv(out/"intervention_audit.csv",index=False)
    by=diag.groupby("sleeve").paired_sharpe_diff.mean().to_dict() if len(diag) else {}
    n_defined=len(diag);required=int(np.ceil((2*n_defined)/3));wins=int((diag.paired_sharpe_diff>0).sum()) if len(diag) else 0
    deferred=int(audit.deferred.sum()) if len(audit) else 0
    per_sleeve_deferred=audit.loc[audit.deferred].groupby("sleeve").size().to_dict() if len(audit) else {}
    annual_fund_diffs=[float(r["paired_fund_sharpe_diff"]) for r in sorted(results,key=lambda x:x["year"])]
    mean_paired_fund_sharpe_diff=float(np.mean(annual_fund_diffs)) if annual_fund_diffs else float("nan")
    dd_ok=em["max_drawdown_pct"] >= cm["max_drawdown_pct"]-0.10*abs(cm["max_drawdown_pct"])
    gates=dict(
        positive_mean_paired_fund_sharpe_diff=mean_paired_fund_sharpe_diff>0,
        cross_fold_consistency=wins>=required,
        each_sleeve_positive=all(by.get(s,float("-inf"))>0 for s in sorted(ELIGIBLE_SLEEVES)),
        drawdown_within_allowance=bool(dd_ok),
        intervention_count=deferred>=20 and all(per_sleeve_deferred.get(s,0)>=3 for s in ELIGIBLE_SLEEVES),
    )
    summary=dict(cost_case=cost_case,control=cm,experimental=em,stitched_fund_sharpe_diff=em["sharpe"]-cm["sharpe"],mean_paired_fund_sharpe_diff=mean_paired_fund_sharpe_diff,annual_paired_fund_sharpe_diffs=annual_fund_diffs,defined_diagnostics=n_defined,required_positive_diagnostics=required,positive_diagnostics=wins,mean_sleeve_fold_sharpe_diff=float(diag.paired_sharpe_diff.mean()),mean_by_sleeve=by,deferred_events=deferred,deferred_by_sleeve=per_sleeve_deferred,base_evaluable_gates=gates,base_gate_pass=all(gates.values()))
    (out/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
    return summary


def run_case(args,cost_case):
    folds=_build_folds(args.data_start,args.oos_start,args.oos_end);years=[str(f.label) for f in folds]
    # Runtime optimization only: construct immutable daily RRE panels once in the
    # parent process instead of rebuilding the same panels in every annual worker.
    ra=ns_for(args,BASE_COST if cost_case=="base" else STRESS_COST)
    raw_for_panels=load_data(ra)
    panels={
        ("BTC",4):panel_from_hourly(raw_for_panels["BTC"],4),
        ("ETH",1):panel_from_hourly(raw_for_panels["ETH"],1),
        ("ETH",4):panel_from_hourly(raw_for_panels["ETH"],4),
    }
    payload=[(vars(args),y,cost_case,panels) for y in years];workers=max(1,min(args.workers,len(payload)))
    results=[]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs={ex.submit(run_fold,p):p[1] for p in payload}
        for fut in as_completed(futs):
            y=futs[fut];r=fut.result();results.append(r);print(f"{cost_case} fold {y} complete",flush=True)
    return results


def main():
    args=parse_args();sources=verify(args);out=Path(args.out_dir)
    cost_case=args.cost_case
    results=run_case(args,cost_case);summary=evaluate_case(results,args,cost_case,out/cost_case)
    manifest=dict(status="PASS",observation_only=True,scenario=SELECTED_CORE_V1_SCENARIO,source_sha256=sources,cost_case=cost_case,workers=args.workers,runtime_modified=False,strategy_source_modified=False,allocation_modified=False,core_labels_modified=False,summary=summary)
    (out/f"{cost_case}_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(summary,indent=2,sort_keys=True))
    if cost_case=="base":
        print("BASE_GATE_PASS="+str(summary["base_gate_pass"]).lower())
        print("Run stress only if BASE_GATE_PASS=true.")


if __name__=="__main__":
    main()
