from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import traceback
import pandas as pd
import numpy as np
import sklearn
from research.crypto_reversal.experiment import (INPUTS, load_input, SCENARIOS, HOUR,
    policies, schedule, signal_bars, simulate, combine, period_summaries, trade_diagnostics)
from research.core_regime_reuse.adapter import verify_source_lock
from .study import MODELS, build_panel, forecast, score


def filter_orders(orders, predictions):
    """Use last daily forecast available at signal completion, at most 24h old."""
    p = predictions.copy()
    p.index = pd.to_datetime(p.available_at, utc=True)
    p = p.sort_index()
    if not p.index.is_unique:
        raise ValueError('Duplicate forecast times')
    selected = {}
    for entry, meta in orders.items():
        decision = pd.Timestamp(meta['available_at'])
        i = p.index.searchsorted(decision, side='right')-1
        if i < 0 or decision-p.index[i] >= 24*HOUR:
            continue
        row = p.iloc[i]
        if pd.Timestamp(row.fit_at) > p.index[i] or pd.Timestamp(row.latest_training_label_end) >= pd.Timestamp(row.fit_at):
            raise ValueError('Forecast training timing violation')
        if row.prediction <= row.training_mean:
            selected[entry] = meta
    return selected


def practical(frames, predictions, out):
    policy = next(p for p in policies() if p.role=='primary')
    bars = {a:signal_bars(f,4) for a,f in frames.items()}
    summary, diag, trades = [], [], []
    for scenario,(cost,delay) in SCENARIOS.items():
        for model in ['unfiltered']+MODELS:
            runs = {}
            for asset, frame in frames.items():
                orders = schedule(bars[asset],policy,delay)
                if model!='unfiltered':
                    p = predictions[(predictions.asset==asset)&(predictions.timeframe==4)&
                        (predictions.model==model)&(predictions.target=='downside')]
                    orders = filter_orders(orders,p)
                runs[asset] = simulate(frame,orders,24,cost)
                trades.extend(dict(asset=asset,scenario=scenario,model=model,**t) for t in runs[asset].trades)
            runs['MIX']=combine(runs['BTC'],runs['ETH'])
            for asset,run in runs.items():
                summary.extend(dict(asset=asset,scenario=scenario,model=model,**row) for row in period_summaries(run))
                diag.append(dict(asset=asset,scenario=scenario,model=model,**run.diagnostics,
                                 **trade_diagnostics(run.trades,asset=='MIX')))
        print(f'Fixed practical check: {scenario} complete',flush=True)
    pd.DataFrame(summary).to_csv(out/'trading_summary.csv',index=False)
    pd.DataFrame(diag).to_csv(out/'trading_diagnostics.csv',index=False)
    pd.DataFrame(trades).to_csv(out/'trading_trades.csv',index=False)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--output-root',type=Path,default=Path('artifacts'))
    args=p.parse_args()
    out=args.output_root/('regime_engine_ml_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True,exist_ok=False)
    error=None
    try:
        lock=verify_source_lock()
        frames,sources={},{}
        for asset,(filename,_) in INPUTS.items():
            frames[asset],sources[asset]=load_input(args.data_root/filename,asset)
        forecasts=[]
        for asset,frame in frames.items():
            for hours in (1,4):
                panel=build_panel(frame,hours)
                forecasts.append(forecast(panel,asset,hours))
        predictions=pd.concat(forecasts,ignore_index=True)
        predictions.to_csv(out/'predictions.csv',index=False)
        scores=score(predictions)
        scores.to_csv(out/'forecast_scores.csv',index=False)
        practical(frames,predictions,out)
        root=Path(__file__).resolve().parents[2]
        report=dict(status='exploratory chronological replay; previously exposed history, not pristine OOS',
            core_source_lock=lock,sources=sources,models=MODELS,
            versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__),
            git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            study_sha256=hashlib.sha256(Path(__file__).with_name('study.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            horizon_hours=24,forecast_clock='UTC midnight',refits='annual expanding window; strict label_end < fit_at',
            trading_rule='4H primary reversal; daily predicted 3% downside probability <= training prevalence; forecast age <24h',
            selection='No model tuning or automatic promotion. All comparisons reported.')
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(scores[(scores.year=='all')&(scores.target=='log_variance')][['asset','timeframe','model','skill_vs_constant']].to_string(index=False))
    except Exception:
        error=traceback.format_exc()
        (out/'error.txt').write_text(error)
    archive=shutil.make_archive(str(out),'zip',out)
    print(f'SHARE RESULTS ZIP: {archive}',flush=True)
    if error:
        raise SystemExit(error)


if __name__=='__main__':
    main()
