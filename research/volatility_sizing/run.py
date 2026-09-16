import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import platform
import shutil
import subprocess
import traceback
import numpy as np
import pandas as pd
import sklearn
from research.core_regime_reuse.adapter import verify_source_lock
from research.crypto_reversal.experiment import (INPUTS,SCENARIOS,load_input,policies,
    signal_bars,schedule,simulate,combine,period_summaries)
from .study import MODELS,annual_forecasts,scores,size_at
from .replay import replay


def practical(frames,predictions,out):
    policy=next(p for p in policies() if p.role=='primary')
    bars={a:signal_bars(f,4) for a,f in frames.items()}
    summary=[];diagnostics=[];trades=[];fills=[];weights_log=[]
    (out/'daily').mkdir()
    for scenario,(cost,delay) in SCENARIOS.items():
        originals={a:simulate(f,schedule(bars[a],policy,delay),24,cost) for a,f in frames.items()}
        for model in ['fixed_full','fixed_half']+MODELS:
            runs={}
            for asset,frame in frames.items():
                p=predictions[(predictions.asset==asset)&(predictions.timeframe==4)&(predictions.model==model)].copy()
                p.index=pd.to_datetime(p.available_at,utc=True)
                p=p.sort_index()
                if not p.index.is_unique:raise ValueError('Duplicate forecasts')
                weights={}
                for t in originals[asset].trades:
                    entry=pd.Timestamp(t['entry_time']);decision=pd.Timestamp(t['available_at'])
                    if model=='fixed_full':w,forecast_at=1.,None
                    elif model=='fixed_half':w,forecast_at=.5,None
                    else:w,forecast_at=size_at(p,decision)
                    weights[entry]=w
                    weights_log.append(dict(scenario=scenario,asset=asset,model=model,
                        entry_time=str(entry),decision_at=str(decision),forecast_at=forecast_at,weight=w))
                run=replay(frame,originals[asset],weights,cost)
                if model=='fixed_full':
                    np.testing.assert_allclose(run.curve,originals[asset].curve,rtol=1e-10,atol=1e-10)
                runs[asset]=run
                trades.extend(dict(scenario=scenario,asset=asset,model=model,**t) for t in run.trades)
                fills.extend(dict(scenario=scenario,asset=asset,model=model,**t) for t in run.fills)
            runs['MIX']=combine(runs['BTC'],runs['ETH'])
            for asset,run in runs.items():
                summary.extend(dict(scenario=scenario,asset=asset,model=model,**r) for r in period_summaries(run))
                diagnostics.append(dict(scenario=scenario,asset=asset,model=model,**run.diagnostics))
                run.curve.loc[run.curve.index.hour==0,['nav','exposure']].to_csv(
                    out/'daily'/f'{scenario}__{model}__{asset}.csv',index_label='valuation_time')
        print(f'Sizing replay: {scenario} complete',flush=True)
    for name,rows in [('sizing_summary',summary),('sizing_diagnostics',diagnostics),('sizing_trades',trades),
                       ('sizing_fills',fills),('entry_weights',weights_log)]:
        pd.DataFrame(rows).to_csv(out/f'{name}.csv',index=False)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-root',type=Path,required=True)
    parser.add_argument('--output-root',type=Path,default=Path('artifacts'))
    args=parser.parse_args()
    out=args.output_root/('volatility_sizing_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True,exist_ok=False);error=None
    try:
        lock=verify_source_lock();frames={};sources={}
        for asset,(filename,_) in INPUTS.items():
            frames[asset],sources[asset]=load_input(args.data_root/filename,asset)
        predictions=pd.concat([annual_forecasts(f,a,h) for a,f in frames.items() for h in (1,4)],ignore_index=True)
        predictions.to_csv(out/'forecasts.csv',index=False)
        scores(predictions).to_csv(out/'forecast_scores.csv',index=False)
        practical(frames,predictions,out)
        root=Path(__file__).resolve().parents[2]
        report=dict(state='chronological development replay; previously exposed history',source_lock=lock,sources=sources,
            models=MODELS,git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            versions=dict(python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,sklearn=sklearn.__version__),
            sizing='min(1, (0.40/sqrt(365))/sqrt(exp(predicted log variance))); fixed at entry; no leverage or rebalancing',
            opportunity_set='Original primary reversal executed trade slots; no new entries after a zero-sized slot',
            controls=['fixed_full','fixed_half'],cash_yield=0,fit='Annual; label_end strictly before fit_at')
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        s=pd.read_csv(out/'sizing_summary.csv')
        print(s[(s.scenario=='base')&(s.asset=='MIX')&(s.period=='full')][['model','cagr','zero_cash_sharpe','max_drawdown','mean_exposure']].to_string(index=False))
    except Exception:
        error=traceback.format_exc();(out/'error.txt').write_text(error)
    archive=shutil.make_archive(str(out),'zip',out)
    print(f'SHARE RESULTS ZIP: {archive}',flush=True)
    if error:raise SystemExit(error)


if __name__=='__main__':main()
