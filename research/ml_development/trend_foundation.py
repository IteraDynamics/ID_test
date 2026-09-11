"""Fixed long/cash multi-group trend baseline; exploratory, no model fitting."""
import argparse
import io
import json
import platform
import subprocess
import zipfile
from pathlib import Path
import hashlib

import numpy as np
import pandas as pd
from research.ml_development import portfolio as p

GROUPS={'equity':['SPY','QQQ','IWM','EFA','EEM'],'rates':['IEF','TLT'],
        'gold':['GLD'],'energy':['USO'],'agriculture':['CORN','SOYB','WEAT']}
ASSETS=[a for group in GROUPS.values() for a in group]+['BIL']
SPEC=Path('docs/research/ML_TREND_FOUNDATION_SPEC_20260911.md')


def inputs(etf_root,energy_zip,crop_zip):
    fs,sources=p.inputs(etf_root)
    ref=json.loads(Path('docs/research/evidence/ml_incremental_information_20260910/report.json').read_text())
    if sources!=ref['sources']:raise ValueError('Original nine source identities changed')
    archives={}
    for path,assets in [(energy_zip,['USO']),(crop_zip,['CORN','SOYB','WEAT'])]:
        archives[path.name]=p.sha(path)
        with zipfile.ZipFile(path) as z:
            for asset in assets:
                name=asset+'_1D.csv';raw=z.read(name);mr=z.read(name+'.manifest.json');m=json.loads(mr)
                x=pd.read_csv(io.BytesIO(raw));dates=pd.to_datetime(x.timestamp,utc=True)
                if list(x.columns)!=m['schema'] or list(x.columns)!=['timestamp','open','high','low','close','volume']:raise ValueError('Schema')
                if len(x)!=m['rows'] or dates.duplicated().any() or not dates.is_monotonic_increasing:raise ValueError('Rows/order')
                if dates.iloc[0]!=pd.Timestamp(m['actual_start']) or dates.iloc[-1]!=pd.Timestamp(m['actual_end']):raise ValueError('Manifest dates')
                if m['request']['asset']!=asset or m['request']['auto_adjust'] is not True or m['request']['interval']!='1d':raise ValueError('Adjustment basis')
                x.index=pd.DatetimeIndex(dates);x=x.drop(columns='timestamp').loc['2013-12-02':'2024-12-31'].astype(float)
                if not x.index.equals(fs['SPY'].index):raise ValueError('Calendar mismatch')
                if not np.isfinite(x.to_numpy()).all() or (x[['open','high','low','close']]<=0).any().any() or (x.volume<0).any():raise ValueError('Invalid values')
                tol=1e-10*x.close
                if (x.low>x[['open','close']].min(axis=1)+tol).any() or (x.high+tol<x[['open','close']].max(axis=1)).any() or (x.low>x.high).any():raise ValueError('OHLC range')
                fs[asset]=x;sources.append(dict(asset=asset,csv_sha256=hashlib.sha256(raw).hexdigest(),manifest_sha256=hashlib.sha256(mr).hexdigest(),source_rows=m['rows'],used_rows=len(x)))
    return fs,sources,archives


def risk_limit(risky,cov):
    def full(t):return np.r_[t*risky,1-t*risky.sum()]
    if full(0)@cov@full(0)>.01:raise ValueError('BIL exceeds ceiling')
    lo,hi=0.,1.
    if full(1)@cov@full(1)<=.01:return full(1)
    for _ in range(70):
        mid=(lo+hi)/2
        if full(mid)@cov@full(mid)<=.01:lo=mid
        else:hi=mid
    return full(lo)


def target(closes,s,trend):
    if s<252:raise ValueError('Insufficient warmup')
    returns=closes[s-62:s+1]/closes[s-63:s]-1
    vol=np.maximum(returns.std(axis=0,ddof=1)*np.sqrt(252),.01)
    base=np.zeros(len(ASSETS)-1)
    for group in GROUPS.values():
        idx=[ASSETS.index(a) for a in group];iv=1/vol[idx];base[idx]=.15*iv/iv.sum()
    strength=np.mean([((closes[s,:-1]/closes[s-lag,:-1]-1)>(closes[s,-1]/closes[s-lag,-1]-1)).astype(float) for lag in [63,126,252]],axis=0)
    cov=p.covariance(closes,s)
    w=risk_limit(base*strength if trend else base,cov)
    if w.min()<-1e-12 or abs(w.sum()-1)>1e-12 or w[:-1].max()>.15+1e-12 or w[:-1].sum()>.75+1e-12:raise ValueError('Target limits')
    return w,strength,float(np.sqrt(w@cov@w))


def schedules(fs):
    dates=fs['SPY'].index;closes=np.column_stack([fs[a].close for a in ASSETS])
    months=dates.strftime('%Y-%m');signals=[s for s in range(252,len(dates)-2) if months[s]!=months[s+1] and dates[s].year>=2018]
    schedule={name:{} for name in ['trend','static','hold','bil']};rows=[]
    for s in signals:
        for name in schedule:
            w,strength,vol=target(closes,s,name=='trend')
            if name=='bil':w=np.r_[np.zeros(len(ASSETS)-1),1.];vol=float(np.sqrt(w@p.covariance(closes,s)@w))
            if name=='hold' and s!=signals[0]:continue
            if name=='bil' and s!=signals[0]:continue
            schedule[name][s]=w
            for j,a in enumerate(ASSETS):
                rows.append(dict(signal_date=dates[s],policy=name,asset=a,weight=w[j],trend_fraction=strength[j] if j<len(strength) else np.nan,forecast_volatility=vol))
    return schedule,pd.DataFrame(rows)


def ledger(fs,schedule,cost,delay):
    dates=fs['SPY'].index;opens=np.column_stack([fs[a].open for a in ASSETS]);closes=np.column_stack([fs[a].close for a in ASSETS])
    orders={s+1+delay:w for s,w in schedule.items()};start=min(orders);end=len(dates)-1
    orders[end]=np.zeros(len(ASSETS));h=np.zeros(len(ASSETS));cash=nav=1.;last=opens[start];rows=[]
    # All scenarios start valuation on the primary first execution date. Delayed
    # scenarios hold settlement cash until their first fill.
    for i in range(min(schedule)+1,end+1):
        fees=np.zeros(len(ASSETS));traded=np.zeros(len(ASSETS));before=cash+(h*opens[i]).sum()
        contribution=h*(opens[i]-last)
        if i in orders:h,cash,fees,traded,before=p.rebalance(h,cash,opens[i],orders[i],cost)
        contribution+=h*(closes[i]-opens[i])-fees
        values=h*closes[i];new=cash+values.sum();ret=new/nav-1
        if cash<-1e-12 or new<=0 or abs(contribution.sum()/nav-ret)>1e-10:raise ValueError('Accounting')
        row=dict(date=dates[i],nav=new,return_value=ret,cost=fees.sum(),turnover=traded.sum()/before,
                 exposure=values[:-1].sum()/new,cash_fraction=(cash+values[-1])/new)
        for j,a in enumerate(ASSETS):row[a+'_contribution']=contribution[j]/nav;row[a+'_weight']=values[j]/new
        rows.append(row);nav=new;last=closes[i]
    if np.abs(h).sum()>1e-12:raise ValueError('Terminal position')
    return pd.DataFrame(rows).rename(columns={'return_value':'return'})


def run(etf_root,energy_zip,crop_zip,out):
    if out.exists():raise FileExistsError(out)
    fs,sources,archives=inputs(etf_root,energy_zip,crop_zip);out.mkdir(parents=True)
    identity=dict(status='EXPLORATORY_TREND_BASELINE',model_fits=0,sources=sources,archives=archives,spec_sha256=p.sha(SPEC),
                  code={str(x):p.sha(x) for x in [Path(__file__),Path(p.__file__),Path('research/ml_development/breadth_inputs.py'),Path('scripts/run_ml_etf_risk_screen.py')]},
                  environment=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__),
                  parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),reserved_2025_used=False)
    (out/'identity_before_evaluation.json').write_text(json.dumps(identity,indent=2)+'\n')
    sch,w=schedules(fs);w.to_csv(out/'target_weights.csv',index=False);days=[]
    for scenario,cost,delay in [('gross',0.,0),('cost5',.0005,0),('cost10',.001,0),('cost25',.0025,0),('delay1',.001,1)]:
        for name,s in sch.items():
            d=ledger(fs,s,cost,delay);d['scenario']=scenario;d['policy']=name;days.append(d)
        print(scenario+': four ledgers reconciled',flush=True)
    d=pd.concat(days,ignore_index=True);d.to_csv(out/'daily_ledger.csv',index=False)
    em=p.summaries(d);em.to_csv(out/'economic_metrics.csv',index=False)
    diagnostics=[]
    for scenario,g in d.groupby('scenario'):
        t=g[g.policy=='trend'].set_index('date');s=g[g.policy=='static'].set_index('date');bil=g[g.policy=='bil'].set_index('date')
        alpha=float(t.exposure.mean()/s.exposure.mean())
        if not 0<=alpha<=1:raise ValueError('Exposure diagnostic requires convex blend')
        # Explicitly ex-post moment attribution, with no claimed executable ledger.
        blend=alpha*s['return']+(1-alpha)*bil['return']
        nav=np.r_[1.,(1+blend).cumprod().to_numpy()]
        diagnostics.append(dict(scenario=scenario,status='EX_POST_NONINVESTABLE_ATTRIBUTION',static_fraction=alpha,
                                ce=252*blend.mean()-1.5*252*blend.var(ddof=1),annualized_volatility=blend.std(ddof=1)*np.sqrt(252),
                                cagr=nav[-1]**(252/len(blend))-1,maximum_drawdown=(nav/np.maximum.accumulate(nav)-1).min()))
    pd.DataFrame(diagnostics).to_csv(out/'exposure_diagnostic.csv',index=False)
    report=dict(**identity,ledgers=20,signal_dates=sch['trend'].__len__(),first_signal=str(fs['SPY'].index[min(sch['trend'])]),last_exit=str(d.date.max()),
                files={x.name:p.sha(x) for x in out.glob('*.csv')},limitations='Repeatedly inspected development history; long/cash adaptation, no currency or short futures sleeve; vendor adjusted prices; cost approximations; no ML or fresh holdout claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    a=argparse.ArgumentParser()
    for name in ['etf-root','energy-zip','crop-zip','output-dir']:a.add_argument('--'+name,type=Path,required=True)
    x=a.parse_args();run(x.etf_root,x.energy_zip,x.crop_zip,x.output_dir)
