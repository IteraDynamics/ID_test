"""Common cash-permitted allocation diagnostic; no training or live execution."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
from research.ml_development.breadth_inputs import load_inputs,ASSETS
from research.ml_development.design_audit import MODELS
from scripts.run_ml_etf_risk_screen import rebalance,metrics

ALL_ASSETS=(*ASSETS,'BIL')
POLICIES=[kind+'_'+model for kind in ['raw','risk','rank'] for model in MODELS]+['fine_mlp16','past_mean','zero','passive75','momentum60']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def inputs(root):
    fs,sources=load_inputs(root);p=root/'BIL_1D.csv';mp=Path(str(p)+'.manifest.json');m=json.loads(mp.read_text());d=pd.read_csv(p)
    if list(d.columns)!=m['schema'] or list(d.columns)!=['timestamp','open','high','low','close','volume']:raise ValueError('BIL schema')
    dates=pd.to_datetime(d.pop('timestamp'),utc=True)
    if dates.duplicated().any() or not dates.is_monotonic_increasing or len(d)!=m['rows']:raise ValueError('BIL rows')
    if m['request']['asset']!='BIL' or m['request']['auto_adjust'] is not True or m['request']['interval']!='1d':raise ValueError('BIL basis')
    if dates.iloc[0]!=pd.Timestamp(m['actual_start']) or dates.iloc[-1]!=pd.Timestamp(m['actual_end']):raise ValueError('BIL manifest dates')
    d.index=pd.DatetimeIndex(dates);d=d.loc['2013-12-02':'2024-12-31'].astype(float)
    if not d.index.equals(fs['SPY'].index):raise ValueError('BIL calendar')
    if not np.isfinite(d.to_numpy()).all() or (d[['open','high','low','close']]<=0).any().any() or (d.volume<0).any():raise ValueError('BIL values')
    tol=1e-10*d.close
    if (d.low>d[['open','close']].min(axis=1)+tol).any() or (d.high+tol<d[['open','close']].max(axis=1)).any() or (d.low>d.high).any():raise ValueError('BIL OHLC')
    fs['BIL']=d;sources.append(dict(asset='BIL',csv_sha256=sha(p),manifest_sha256=sha(mp),source_rows=m['rows'],used_rows=len(d)))
    return fs,sources


def top_weights(scores):
    scores=np.asarray(scores,dtype=float)
    if len(scores)!=8 or not np.isfinite(scores).all():raise ValueError('Eight finite scores required')
    cut=np.sort(scores)[-3];above=scores>cut;tied=scores==cut
    w=.25*above.astype(float);w[tied]=.25*(3-above.sum())/tied.sum()
    return w


def covariance(closes,session):
    if session<252:raise ValueError('Covariance support')
    r=closes[session-251:session+1]/closes[session-252:session]-1
    c=np.cov(r,rowvar=False,ddof=1)*252
    return .5*c+.5*np.diag(np.diag(c))


def limit_risk(w,cov):
    def full(s):return np.r_[s*w,1-s*w.sum()]
    def variance(s):v=full(s);return float(v@cov@v)
    if variance(0)>.01+1e-12:raise ValueError('Cash proxy exceeds risk ceiling')
    lo,hi=0.,1.
    if variance(1)<=.01:return full(1)
    for _ in range(70):
        mid=(lo+hi)/2
        if variance(mid)<=.01:lo=mid
        else:hi=mid
    return full(lo)


def schedules(fs,pred):
    dates=fs['SPY'].index;closes=np.column_stack([fs[a].close for a in ALL_ASSETS]);signals=sorted(pred.date.unique())
    out={k:{} for k in POLICIES};audit=[]
    for date in signals[:-1]:
        s=dates.get_loc(date);g=pred[pred.date==date].set_index('asset').loc[list(ASSETS)];cov=covariance(closes,s)
        for policy in POLICIES:
            if policy=='passive75':w=np.r_[np.full(8,.75/8),.25]
            else:
                scores=closes[s,:8]/closes[s-60,:8]-1 if policy=='momentum60' else g[policy].to_numpy()
                w=limit_risk(top_weights(scores),cov)
            assert w.min()>=0 and abs(w.sum()-1)<1e-12 and w[:8].max()<=.25+1e-12
            vol=float(np.sqrt(w@cov@w))
            if policy!='passive75':assert vol<=.10+1e-10
            out[policy][s]=w
            audit.append(dict(signal_date=date,policy=policy,forecast_volatility=vol,**dict(zip(ALL_ASSETS,w))))
    return out,dates.get_loc(signals[-1]),pd.DataFrame(audit)


def ledger(fs,schedule,end_signal,cost,delay):
    dates=fs['SPY'].index;opens=np.column_stack([fs[a].open for a in ALL_ASSETS]);closes=np.column_stack([fs[a].close for a in ALL_ASSETS])
    trades={s+1+delay:w for s,w in schedule.items()};start=min(trades);end=end_signal+1+delay
    if end>=len(dates):raise ValueError('Exit outside data')
    trades[end]=np.zeros(9);h=np.zeros(9);cash=nav=1.;last=opens[start];rows=[]
    for i in range(start,end+1):
        fees=np.zeros(9);turn=np.zeros(9);before=nav
        contribution=h*(opens[i]-last)
        if i in trades:h,cash,fees,turn,before=rebalance(h,cash,opens[i],trades[i],cost)
        contribution+=h*(closes[i]-opens[i])-fees
        values=h*closes[i];new=cash+values.sum();ret=new/nav-1
        if cash<0 or new<=0 or abs(contribution.sum()/nav-ret)>1e-10:raise ValueError('Ledger reconciliation')
        row=dict(date=dates[i],nav=new,return_value=ret,turnover=turn.sum()/before,cost=fees.sum(),
            exposure=values[:8].sum()/new,cash_fraction=(values[8]+cash)/new,bil_fraction=values[8]/new,settlement_cash=cash)
        row.update({a+'_contribution':contribution[j]/nav for j,a in enumerate(ALL_ASSETS)});rows.append(row)
        nav=new;last=closes[i]
    return pd.DataFrame(rows).rename(columns={'return_value':'return'})


def summaries(d):
    rows=[]
    for (scenario,policy),g in d.groupby(['scenario','policy'],sort=True):
        for period,sub in [('all',g),('excluding_2020',g[g.date.dt.year!=2020]),*[(str(y),g[g.date.dt.year==y]) for y in range(2018,2025)]]:
            rows.append(dict(scenario=scenario,policy=policy,period=period,**metrics(sub,period!='excluding_2020')))
    return pd.DataFrame(rows)


def run(root,cached,out):
    if out.exists():raise FileExistsError(out)
    fs,sources=inputs(root);r=json.loads((cached/'report.json').read_text())
    if sources[:8]!=r['sources']:raise ValueError('Forecast source mismatch')
    if sha(cached/'forecasts.csv')!=r['files']['forecasts.csv']:raise ValueError('Forecast hash')
    pred=pd.read_csv(cached/'forecasts.csv',float_precision='round_trip',parse_dates=['date','label_end'])
    if pred.duplicated(['date','asset']).any() or not (pred.groupby('date').size()==8).all():raise ValueError('Forecast inventory')
    sch,end,weights=schedules(fs,pred);out.mkdir(parents=True);weights.to_csv(out/'target_weights.csv',index=False)
    ds=[]
    for scenario,cost,delay in [('cost10',.001,0),('cost25',.0025,0),('delay1',.001,1)]:
        for policy in POLICIES:
            d=ledger(fs,sch[policy],end,cost,delay);d['scenario']=scenario;d['policy']=policy;ds.append(d)
        print(scenario+': 14 reconciled ledgers complete',flush=True)
    daily=pd.concat(ds,ignore_index=True);daily.to_csv(out/'daily_ledger.csv',index=False);summaries(daily).to_csv(out/'economic_metrics.csv',index=False)
    report=dict(status='EXPLORATORY_PORTFOLIO_DIAGNOSTIC',model_fits=0,ledgers=42,sources=sources,reserved_2025_used=False,
        forecast_sha256=sha(cached/'forecasts.csv'),files={p.name:sha(p) for p in out.glob('*.csv')},
        code={str(p):sha(p) for p in [Path(__file__),Path('research/ml_development/breadth_inputs.py'),Path('scripts/run_ml_etf_risk_screen.py')]},
        plan_sha256=sha('docs/research/ML_PORTFOLIO_DIAGNOSTIC_PLAN_20260910.md'),
        limitations='Inspected development years; fixed rank mapping; no significance, promotion, actual brokerage cash yield or realized risk guarantee.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-root',type=Path,required=True);p.add_argument('--cached',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();run(a.input_root,a.cached,a.output_dir)
