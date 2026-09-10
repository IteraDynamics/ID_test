"""Fixed incremental-information probe; no model or allocation search."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from research.ml_development import breadth as b
from research.ml_development import portfolio as p

MODELS=['ridge100','gbm2']
DYNAMIC=b.SUMMARY[:8]
VARIANTS=['mean',*[kind+'_'+m for m in MODELS for kind in ['raw','cal','static']]]
POLICIES=VARIANTS+['equal','bil','mean_ungated']
SPEC=Path('docs/research/ML_INCREMENTAL_INFORMATION_20260910.md')


def panel(fs):
    q=b.build_panel({a:fs[a] for a in b.ASSETS})
    bil=fs['BIL'].open.shift(-6)/fs['BIL'].open.shift(-1)-1
    q['bil_target']=q.date.map(bil)
    q['target']=q.target-q.bil_target
    if not np.isfinite(q.target).all():raise ValueError('Missing excess target')
    return q


def residual_fit(name,train,val):
    if not train.label_end.max()<val.date.min():raise ValueError('Overlapping train/validation')
    means=train.groupby('asset').target.mean()
    y=train.target-train.asset.map(means)
    model=b.estimator(name)
    with threadpool_limits(limits=1):
        model.fit(train[b.SUMMARY],100*y)
        residual=model.predict(val[b.SUMMARY])/100
        frozen=val[b.SUMMARY].copy()
        typical=train.groupby('asset')[DYNAMIC].mean()
        for c in DYNAMIC:frozen[c]=val.asset.map(typical[c]).to_numpy()
        static=model.predict(frozen)/100
    if not np.isfinite(residual).all() or not np.isfinite(static).all():raise ValueError('Nonfinite forecast')
    return val.asset.map(means).to_numpy(),residual,static


def slope(pred,truth):
    pred=np.asarray(pred);truth=np.asarray(truth);den=float(pred@pred)
    if not np.isfinite(pred).all() or not np.isfinite(truth).all():raise ValueError('Calibration values')
    return float(np.clip(pred@truth/den,0,1)) if den>0 else 0.


def gated(scores,cost):
    scores=np.asarray(scores,dtype=float)
    if scores.shape!=(8,) or not np.isfinite(scores).all() or cost<0:raise ValueError('Scores/cost')
    ok=scores>4*cost;count=int(ok.sum())
    if count<=3:return .25*ok.astype(float)
    cut=np.sort(scores[ok])[-3];above=scores>cut;ties=scores==cut
    w=.25*above.astype(float);w[ties]=.25*(3-above.sum())/ties.sum()
    return w


def forecasts(q,out):
    records=[];fits=[];calibrations=[]
    for year in range(2018,2025):
        tr,va=b.split(q,year);f=va[['date','asset','label_end','target','bil_target']].copy()
        f['mean']=va.asset.map(tr.groupby('asset').target.mean())
        for model in MODELS:
            ips=[];its=[]
            for iy in [year-2,year-1]:
                it,iv=b.inner_split(q,iy,year);mean,res,_=residual_fit(model,it,iv)
                ips.extend(res);its.extend(iv.target.to_numpy()-mean)
                fits.append(dict(year=year,model=model,stage='inner',validation_year=iy,rows=len(it),last_training_outcome=str(it.label_end.max()),first_validation_signal=str(iv.date.min()),last_validation_outcome=str(iv.label_end.max()),outer_first_signal=str(va.date.min())))
            alpha=slope(ips,its);mean,res,static=residual_fit(model,tr,va)
            f['raw_'+model]=mean+res;f['cal_'+model]=mean+alpha*res;f['static_'+model]=mean+alpha*static
            calibrations.append(dict(year=year,model=model,slope=alpha,inner_rows=len(ips)))
            fits.append(dict(year=year,model=model,stage='outer',validation_year=year,rows=len(tr),last_training_outcome=str(tr.label_end.max()),first_validation_signal=str(va.date.min()),last_validation_outcome=str(va.label_end.max()),outer_first_signal=str(va.date.min())))
        records.append(f);pd.concat(records).to_csv(out/'forecasts.csv',index=False)
        pd.DataFrame(fits).to_csv(out/'fits.csv',index=False);pd.DataFrame(calibrations).to_csv(out/'calibration.csv',index=False)
        print(f'{year}: six fixed fits complete',flush=True)
    return pd.concat(records,ignore_index=True)


def forecast_metrics(f):
    rows=[]
    for scope,g in [('all',f),('excluding_2020',f[f.date.dt.year!=2020]),*[(str(y),f[f.date.dt.year==y]) for y in range(2018,2025)]]:
        for asset in ['pooled',*b.ASSETS]:
            sub=g if asset=='pooled' else g[g.asset==asset]
            for variant in VARIANTS:
                x=sub[variant]-sub['mean'];y=sub.target-sub['mean']
                rows.append(dict(scope=scope,asset=asset,variant=variant,rows=len(sub),mse=float(((sub[variant]-sub.target)**2).mean()),residual_correlation=float(x.corr(y)) if x.std()>1e-15 and y.std()>0 else None))
    return pd.DataFrame(rows)


def schedules(fs,f,cost):
    dates=fs['SPY'].index;closes=np.column_stack([fs[a].close for a in p.ALL_ASSETS]);signals=sorted(f.date.unique());sch={name:{} for name in POLICIES};audit=[]
    for date in signals[:-1]:
        s=dates.get_loc(date);g=f[f.date==date].set_index('asset').loc[list(b.ASSETS)];cov=p.covariance(closes,s)
        for name in POLICIES:
            if name=='bil':risky=np.zeros(8)
            elif name=='equal':risky=np.full(8,.75/8)
            elif name=='mean_ungated':risky=p.top_weights(g['mean'].to_numpy())
            else:risky=gated(g[name].to_numpy(),cost)
            w=p.limit_risk(risky,cov);sch[name][s]=w
            audit.append(dict(date=date,policy=name,qualifying_assets=int((risky>0).sum()),forecast_volatility=float(np.sqrt(w@cov@w)),**dict(zip(p.ALL_ASSETS,w))))
    return sch,dates.get_loc(signals[-1]),pd.DataFrame(audit)


def judge(fm,em):
    result={}
    for model in MODELS:
        name='cal_'+model;z=fm[fm.asset=='pooled'].pivot(index='scope',columns='variant',values='mse')
        predictive=all(z.loc[t,name]<min(z.loc[t,'mean'],z.loc[t,'static_'+model]) for t in ['all','excluding_2020'])
        years=[str(y) for y in range(2018,2025)]
        wins=int((z.loc[years,name]<z.loc[years,'mean']).sum());predictive &= wins>=4
        economic=True
        for scenario in ['cost10','cost25','delay1']:
            e=em[em.scenario==scenario].pivot(index='period',columns='policy',values='ce')
            economic &= all(e.loc[t,name]>max(e.loc[t,'mean'],e.loc[t,'equal']) for t in ['all','excluding_2020'])
        e=em[em.scenario=='cost10'].pivot(index='period',columns='policy',values='ce');ewins=int((e.loc[years,name]>e.loc[years,'mean']).sum());economic &= ewins>=4
        result[model]=dict(predictive_consistency=bool(predictive),economic_consistency=bool(economic),mse_lift_years=wins,ce_lift_years=ewins,both=bool(predictive and economic))
    return result


def run(root,out):
    if out.exists():raise FileExistsError(out)
    fs,sources=p.inputs(root);q=panel(fs);out.mkdir(parents=True)
    f=forecasts(q,out);fm=forecast_metrics(f);fm.to_csv(out/'forecast_metrics.csv',index=False)
    days=[];weights=[]
    for scenario,cost,delay in [('cost10',.001,0),('cost25',.0025,0),('delay1',.001,1)]:
        sch,end,w=schedules(fs,f,cost);w['scenario']=scenario;weights.append(w)
        for name in POLICIES:
            d=p.ledger(fs,sch[name],end,cost,delay);d['policy']=name;d['scenario']=scenario;days.append(d)
        print(scenario+': ten reconciled ledgers complete',flush=True)
    d=pd.concat(days,ignore_index=True);d.to_csv(out/'daily_ledger.csv',index=False);pd.concat(weights,ignore_index=True).to_csv(out/'target_weights.csv',index=False)
    em=p.summaries(d);em.to_csv(out/'economic_metrics.csv',index=False)
    report=dict(status='EXPLORATORY_INCREMENTAL_INFORMATION',optimizer_fits=42,ledgers=30,sources=sources,consistency=judge(fm,em),reserved_2025_used=False,
        files={x.name:p.sha(x) for x in out.glob('*.csv')},spec_sha256=p.sha(SPEC),code={str(x):p.sha(x) for x in [Path(__file__),Path(b.__file__),Path(p.__file__),Path('research/ml_development/breadth_inputs.py'),Path('scripts/run_ml_etf_risk_screen.py')]},limitations='Inspected development data; no significance, confirmation, promotion, or proof of optimal allocation.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['consistency']),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--input-root',type=Path,required=True);a.add_argument('--output-dir',type=Path,required=True);x=a.parse_args();run(x.input_root,x.output_dir)
