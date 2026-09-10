"""Bounded learning-design audit; see ML_DESIGN_AUDIT_20260910.md."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from research.ml_development import breadth as b

MODELS=['ridge100','gbm2','mlp16']

def risk(p):return np.maximum(.005,p.rv60.to_numpy()*np.sqrt(5/252))

def transformed(p,objective):
    p=p.copy()
    if objective=='risk':p['target']=.01*p.target/risk(p)
    elif objective=='rank':
        if not (p.groupby('date').size()==8).all():raise ValueError('Rank requires eight assets')
        p['target']=.02*((p.groupby('date').target.rank(method='average')-1)/7-.5)
    else:raise ValueError(objective)
    return p


def fine_fit(train,val):
    sub,stop=b.stopping_split(train);cols=b.SUMMARY
    scaler=StandardScaler().fit(sub[cols]);x=scaler.transform(sub[cols]);y=100*sub.target.to_numpy()
    sx=scaler.transform(stop[cols]);sy=100*stop.target.to_numpy()
    net=clone(b.estimator('mlp16').steps[-1][1]).set_params(shuffle=True)
    best=float('inf');be=0;curve=[]
    with threadpool_limits(limits=1):
        for epoch in range(1,201):
            net.partial_fit(x,y);loss=float(np.mean((net.predict(sx)-sy)**2))/10000
            curve.append(dict(epoch=epoch,training_mse=float(np.mean((net.predict(x)-y)**2))/10000,stopping_mse=loss))
            if loss<best-1e-10:best=loss;be=epoch
            if epoch-be>=25:break
        scaler=StandardScaler().fit(train[cols]);x=scaler.transform(train[cols]);y=100*train.target.to_numpy()
        net=clone(b.estimator('mlp16').steps[-1][1]).set_params(shuffle=True)
        for _ in range(be):net.partial_fit(x,y)
        pred=net.predict(scaler.transform(val[cols]))/100
    if not np.isfinite(pred).all():raise ValueError('Nonfinite fine forecast')
    return pred,dict(selected_epoch=be,epochs_examined=epoch,optimizer_fits=2,training_curve=json.dumps(curve),
        stopping_fit_last_outcome=str(sub.label_end.max()),stopping_first_signal=str(stop.date.min()),
        stopping_last_outcome=str(stop.label_end.max()),first_validation_signal=str(val.date.min()))


def synthetic():
    rng=np.random.default_rng(123);dates=pd.bdate_range('2010-01-01',periods=806,tz='UTC');rows=[]
    for i in range(800):
        for a in b.ASSETS:
            r={c:rng.normal() for c in b.SUMMARY if c not in b.ASSETS}
            r.update({x:float(x==a) for x in b.ASSETS})
            truth=.01*(r['ret5']+.5*r['ret20'])
            r.update(date=dates[i],label_end=dates[i+6],weekly=i%5==4,asset=a,truth=truth,target=truth+rng.normal(0,.001));rows.append(r)
    p=pd.DataFrame(rows);boundary=dates[600];train=p[p.label_end<boundary].copy();val=p[(p.date>=boundary)&p.weekly]
    perm=train.copy();perm['target']=np.random.default_rng(321).permutation(perm.target.to_numpy())
    result=[]
    for condition,t in [('signal',train),('shuffled',perm)]:
        for model in MODELS:
            pred,info=b.fit(model,t,val);mse=float(np.mean((pred-val.target.to_numpy())**2));skill=1-mse/float((val.target**2).mean())
            result.append(dict(condition=condition,model=model,mse=mse,skill=skill,passed=bool(skill>.5 if condition=='signal' else skill<.1),optimizer_fits=info['optimizer_fits']))
    return result


def evaluate(f):
    variants=[kind+'_'+model for kind in ['raw','risk','rank'] for model in MODELS]+['fine_mlp16','past_mean','zero']
    results=[];ics=[]
    for name in variants:
        for date,g in f.groupby('date'):
            ic=g[name].rank().corr(g.target.rank()) if g[name].nunique()>1 else 0.
            ics.append(dict(date=date,variant=name,rank_ic=ic))
        for scope,g in [('all',f),('excluding_2020',f[f.date.dt.year!=2020]),*[(str(y),f[f.date.dt.year==y]) for y in range(2018,2025)]]:
            dates=set(g.date)
            subset=[x['rank_ic'] for x in ics if x['variant']==name and x['date'] in dates]
            mse=float(((g[name]-g.target)**2).mean()) if not name.startswith('rank_') else None
            results.append(dict(scope=scope,variant=name,rows=len(g),rank_ic=float(np.mean(subset)),mse=mse,
                skill_vs_past_mean=1-mse/float(((g.past_mean-g.target)**2).mean()) if mse is not None else None,
                normalized_mse=float((((g[name]-g.target)/g.risk_scale)**2).mean()) if mse is not None else None))
    return pd.DataFrame(results),pd.DataFrame(ics)


def main(root,cached,out):
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    syn=synthetic();(out/'synthetic.json').write_text(json.dumps(syn,indent=2)+'\n')
    if not all(x['passed'] for x in syn):raise ValueError('Synthetic recovery failed; no real fits authorized until diagnosis')
    frames,sources=b.load_inputs(root);p=b.build_panel(frames)
    report=json.loads((cached/'report.json').read_text())
    if sources!=report['sources']:raise ValueError('Source snapshot differs')
    for name,h in report['artifacts'].items():
        if hashlib.sha256((cached/name).read_bytes()).hexdigest()!=h:raise ValueError('Cached hash '+name)
    old=pd.read_csv(cached/'forecasts.csv',float_precision='round_trip',parse_dates=['date','label_end'])
    outputs=[];fits=[];audit=[]
    for year in range(2018,2025):
        train,val=b.split(p,year);f=val[['date','asset','label_end','target','rv60']].copy();f['risk_scale']=risk(val)
        q=old[old.date.dt.year==year].set_index(['date','asset']).reindex(pd.MultiIndex.from_frame(f[['date','asset']]))
        np.testing.assert_allclose(q.target.to_numpy(),f.target.to_numpy(),rtol=0,atol=1e-15)
        f['past_mean']=q.past_mean.to_numpy();f['zero']=0.
        for model in MODELS:f['raw_'+model]=q[model].to_numpy()
        cuts=np.quantile(train.rv60,[1/3,2/3]);f['volatility_bucket']=np.searchsorted(cuts,f.rv60)
        for objective in ['risk','rank']:
            for model in MODELS:
                pred,info=b.fit(model,transformed(train,objective),transformed(val,objective))
                if objective=='risk':pred=pred/.01*f.risk_scale.to_numpy()
                f[objective+'_'+model]=pred;info.update(year=year,objective=objective,model=model);fits.append(info)
        f['fine_mlp16'],info=fine_fit(train,val);info.update(year=year,objective='fine_raw',model='mlp16');fits.append(info)
        outputs.append(f);pd.concat(outputs).to_csv(out/'forecasts.csv',index=False);pd.DataFrame(fits).to_csv(out/'fits.csv',index=False)
        print(f'{year}: controlled objectives and stopping-resolution fits complete',flush=True)
    f=pd.concat(outputs);m,ic=evaluate(f);m.to_csv(out/'metrics.csv',index=False);ic.to_csv(out/'rank_ic.csv',index=False)
    for key,g in f.groupby([f.date.dt.year,'asset','volatility_bucket']):
        for model in MODELS:
            for objective in ['raw','risk','rank']:
                name=objective+'_'+model
                audit.append(dict(year=int(key[0]),asset=key[1],volatility_bucket=int(key[2]),variant=name,rows=len(g),
                    squared_error_sum=float(((g[name]-g.target)**2).sum()) if objective!='rank' else None))
    pd.DataFrame(audit).to_csv(out/'error_contributions.csv',index=False)
    d=dict(status='DEVELOPMENT_DESIGN_DIAGNOSTIC',real_optimizer_fits=sum(x['optimizer_fits'] for x in fits),synthetic_optimizer_fits=sum(x['optimizer_fits'] for x in syn),sources=sources,
        reserved_2025_used=False,files={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in out.iterdir()},
        code={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [Path(__file__),Path(b.__file__),Path('research/ml_development/breadth_inputs.py')]},
        spec_sha256=hashlib.sha256(Path('docs/research/ML_DESIGN_AUDIT_20260910.md').read_bytes()).hexdigest())
    (out/'report.json').write_text(json.dumps(d,indent=2)+'\n')

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--input-root',type=Path,required=True);a.add_argument('--cached',type=Path,required=True);a.add_argument('--output-dir',type=Path,required=True);x=a.parse_args();main(x.input_root,x.cached,x.output_dir)
