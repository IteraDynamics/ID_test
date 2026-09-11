"""Read-only forensic checks of existing evidence; no fitting or strategy search."""
import argparse, hashlib, io, json, zipfile
from pathlib import Path
import numpy as np
import pandas as pd


def audit(root, incremental_zip, options_zip):
    def digest(b): return hashlib.sha256(b).hexdigest()
    result={'status':'EXISTING_EVIDENCE_AUDIT','new_model_fits':0,'new_strategy_backtests':0}
    with zipfile.ZipFile(incremental_zip) as z:
        report=json.loads(z.read('results/report.json'))
        for name,h in report['files'].items():
            assert digest(z.read('results/'+name))==h,name
        f=pd.read_csv(z.open('results/forecasts.csv'),float_precision='round_trip')
        saved=pd.read_csv(z.open('results/forecast_metrics.csv'),float_precision='round_trip')
        led=pd.read_csv(z.open('results/daily_ledger.csv'),float_precision='round_trip')
        econ=pd.read_csv(z.open('results/economic_metrics.csv'),float_precision='round_trip')
        fits=pd.read_csv(z.open('results/fits.csv'))
    result['incremental_artifact_hashes_verified']=len(report['files'])
    f['date']=pd.to_datetime(f.date,utc=True)
    values=[];max_delta=0.
    names=['mean','raw_ridge100','cal_ridge100','static_ridge100','raw_gbm2','cal_gbm2','static_gbm2']
    for scope,sub in [('all',f),('excluding_2020',f[f.date.dt.year!=2020])]:
        base=np.mean((sub['mean']-sub.target)**2)
        for name in names:
            mse=float(np.mean((sub[name]-sub.target)**2))
            old=float(saved[(saved.scope==scope)&(saved.asset=='pooled')&(saved.variant==name)].mse.iloc[0])
            max_delta=max(max_delta,abs(mse-old))
            values.append(dict(scope=scope,forecast=name,mse=mse,skill_vs_mean=1-mse/base))
    assert max_delta<1e-14
    result['forecast_metrics']=values;result['max_mse_recompute_delta']=max_delta
    for row in fits.itertuples():
        assert pd.Timestamp(row.last_training_outcome)<pd.Timestamp(row.first_validation_signal)
        if row.stage=='inner':assert pd.Timestamp(row.last_validation_outcome)<pd.Timestamp(row.outer_first_signal)
    result['fit_boundaries_verified']=len(fits)
    errors=[]
    for (scenario,policy),g in led.groupby(['scenario','policy']):
        rr=g['return'].to_numpy();nav=np.cumprod(1+rr)
        assert np.max(abs(nav-g.nav.to_numpy()))<1e-10
        ce=float(252*(rr.mean()-1.5*np.var(rr,ddof=1)))
        old=float(econ[(econ.scenario==scenario)&(econ.policy==policy)&(econ.period=='all')].ce.iloc[0])
        errors.append(abs(ce-old))
    assert max(errors)<1e-12
    result['ledgers_nav_and_ce_reconciled']=len(errors)
    result['max_ce_recompute_delta']=max(errors)
    with zipfile.ZipFile(options_zip) as z:
        daily=pd.read_csv(z.open('options_daily_features.csv'))
    dates=pd.DatetimeIndex(pd.to_datetime(daily.source_date,utc=True))
    signals=pd.DatetimeIndex(sorted(f.date.unique()))
    positions=dates.get_indexer(signals)
    assert (positions>=0).all(), 'Missing supplied calendar date'
    gaps=np.diff(positions)
    assert (gaps>0).all()
    result['etf_sessions_between_weekly_rebalances']={str(int(n)):int((gaps==n).sum()) for n in sorted(set(gaps))}
    result['five_session_label_vs_next_rebalance_mismatches']=int((gaps!=5).sum())
    result['weekly_transition_count']=len(gaps)
    r=json.loads((root/'docs/research/ML_OPTIONS_VARIANCE_RESULTS_20260911.json').read_text())
    raw=(root/'docs/research/ML_OPTIONS_VARIANCE_OOS_20260911.csv').read_bytes()
    assert digest(raw)==r['predictions_sha256']
    pred=pd.read_csv(io.BytesIO(raw),float_precision='round_trip')
    delta=[]
    for m in r['metrics']:
        ratio=pred.future_variance_5/pred[m['model']]
        delta.append(abs(float((ratio-np.log(ratio)-1).mean())-m['mean_qlike']))
    assert max(delta)<1e-12
    result['options_prediction_hash_verified']=True;result['max_qlike_recompute_delta']=max(delta)
    old=json.loads((root/'docs/research/evidence/ml_lab_013_closeout_20260909.json').read_text())
    result['lab013_primary_all_period']=[x for x in old['period_model_summary'] if x['memory_scheme']=='trailing_3y' and x['period']=='all' and x['model'] in ['price_ridge','low_vol_60d']]
    result['inputs']={p.name:digest(p.read_bytes()) for p in [incremental_zip,options_zip]}
    result['scope_limits']=['No raw options-chain or complete acquisition re-audit','No independent refit of old models','Calendar diagnostic uses supplied SPY sessions, not independent exchange calendar','No claim of full repository or production-system audit']
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--repo',type=Path,default=Path('.'));a.add_argument('--incremental-zip',type=Path,required=True);a.add_argument('--options-zip',type=Path,required=True);a.add_argument('--output',type=Path,required=True);x=a.parse_args()
    r=audit(x.repo,x.incremental_zip,x.options_zip)
    x.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in r.items() if k not in ['forecast_metrics','lab013_primary_all_period','inputs']},indent=2))
