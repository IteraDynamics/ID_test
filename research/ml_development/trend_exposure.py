"""Fixed exposure/financing map for the retained trend foundation."""
import argparse,json,platform,subprocess
from pathlib import Path
import numpy as np
import pandas as pd
from research.ml_development import trend_foundation as t

SPEC=Path('docs/research/ML_TREND_EXPOSURE_SPEC_20260911.md')
LADDER=[('1x',1.,False),('1.5x',1.5,False),('2x',2.,False),('2.5x',2.5,False),('3x',3.,False),('4x',4.,False),('2x_cashcap',2.,True)]


def scaled(w,k,cap=False):
    risky=w[:-1]*k
    if cap and risky.sum()>1:risky=risky/risky.sum()
    return np.r_[risky,max(0.,1-risky.sum())]


def trade(h,cash,prices,w,cost):
    values=h*prices;before=float(cash+values.sum())
    if before<=0 or cost*w.sum()>=1:raise ValueError('Insolvent/nonmonotone fee equation')
    lo,hi=0.,before
    for _ in range(80):
        mid=(lo+hi)/2
        if mid+cost*np.abs(w*mid-values).sum()>before:hi=mid
        else:lo=mid
    equity=(lo+hi)/2;new_values=w*equity;fees=cost*np.abs(new_values-values)
    newcash=cash-(new_values-values).sum()-fees.sum()
    if abs(newcash+new_values.sum()-equity)>1e-10:raise ValueError('Trade accounting')
    return new_values/prices,float(newcash),fees,float(np.abs(new_values-values).sum()/before)


def stressed_prices(opens,closes,start):
    o=opens.copy();c=closes.copy()
    for i in range(start,len(o)):
        if i>start:
            gap=opens[i,:-1]/closes[i-1,:-1]-1
            o[i,:-1]=c[i-1,:-1]*(1+2*gap)
        intra=closes[i,:-1]/opens[i,:-1]-1
        c[i,:-1]=o[i,:-1]*(1+2*intra)
    if (o<=0).any() or (c<=0).any():raise ValueError('Invalid doubled-return stress')
    return o,c


def simulate(fs,schedule,k,cap,cost,rate,delay=0,stress=False):
    dates=fs['SPY'].index;o=np.column_stack([fs[a].open for a in t.ASSETS]);c=np.column_stack([fs[a].close for a in t.ASSETS])
    start=min(schedule)+1;end=len(dates)-1
    if stress:o,c=stressed_prices(o,c,start)
    orders={s+1+delay:scaled(w,k,cap) for s,w in schedule.items()}
    h=np.zeros(len(t.ASSETS));cash=nav=1.;last=o[start];stopped=False;rows=[]
    for i in range(start,end+1):
        prior=nav;days=(dates[i]-dates[i-1]).days if i>start else 0
        interest=max(0.,-cash)*rate*days/365;cash-=interest
        contribution=h*(o[i]-last);open_values=h*o[i];open_equity=cash+open_values.sum()
        if open_equity<=0:raise ValueError('Ruin before open liquidation')
        breach=not stopped and open_values.sum()>0 and open_equity/open_values.sum()<.30
        fees=np.zeros(len(h));turn=0.;w=None
        if breach:stopped=True;w=np.zeros(len(h))
        elif i==end:w=np.zeros(len(h))
        elif not stopped:w=orders.get(i)
        if w is not None:h,cash,fees,turn=trade(h,cash,o[i],w,cost)
        contribution+=h*(c[i]-o[i])-fees;values=h*c[i];new=cash+values.sum()
        if new<=0:raise ValueError('Ruin at close')
        ret=new/prior-1
        if abs((contribution.sum()-interest)/prior-ret)>1e-10:raise ValueError('Ledger reconciliation')
        row=dict(date=dates[i],nav=new,return_value=ret,interest=interest,cost=fees.sum(),turnover=turn,
                 exposure=values[:-1].sum()/new,cash_fraction=(values[-1]+max(cash,0))/new,
                 debt=max(-cash,0),gross=values.sum()/new,margin_breach=breach,stopped=stopped,
                 open_gross=open_values.sum()/open_equity,open_exposure=open_values[:-1].sum()/open_equity)
        row.update({a+'_contribution':contribution[j]/prior for j,a in enumerate(t.ASSETS)})
        rows.append(row);nav=new;last=c[i]
    return pd.DataFrame(rows).rename(columns={'return_value':'return'})


def recovery(nav,dates):
    peak=1.;peak_date=dates.iloc[0];longest=0;recovered=[];under=False
    for value,date in zip(nav,dates):
        if value>=peak-1e-12:
            if under:
                duration=(date-peak_date).days;recovered.append(duration);longest=max(longest,duration)
            peak=max(peak,value);peak_date=date;under=False
        else:
            under=True;longest=max(longest,(date-peak_date).days)
    return dict(longest_underwater_calendar_days=longest,
                longest_recovered_episode_days=max(recovered,default=0),
                terminal_unrecovered_days=(dates.iloc[-1]-peak_date).days if under else 0)


def summarize(d):
    rows=[]
    for (scenario,level),g in d.groupby(['scenario','level']):
        m=t.p.metrics(g)
        m.update(recovery(g.nav,g.date))
        m.update(scenario=scenario,level=level,financing_per_initial_dollar=float(g.interest.sum()),
                 fees_per_initial_dollar=float(g.cost.sum()),max_gross=float(max(g.gross.max(),g.open_gross.max())),
                 average_debt_to_equity=float((g.debt/g.nav).mean()),margin_breaches=int(g.margin_breach.sum()),
                 first_breach=str(g.loc[g.margin_breach,'date'].min()) if g.margin_breach.any() else None)
        m['gap10_equity_loss']=.10*float(max(g.exposure.max(),g.open_exposure.max()));m['gap20_equity_loss']=.20*float(max(g.exposure.max(),g.open_exposure.max()))
        rows.append(m)
    return pd.DataFrame(rows)


def run(root,energy,crop,out):
    if out.exists():raise FileExistsError(out)
    fs,sources,archives=t.inputs(root,energy,crop);ref=json.loads(Path('docs/research/evidence/ml_trend_foundation_20260911/report.json').read_text())
    if sources!=ref['sources'] or archives!=ref['archives']:raise ValueError('Input identity')
    sch,_=t.schedules(fs);schedule=sch['trend'];out.mkdir(parents=True)
    identity=dict(spec_sha256=t.p.sha(SPEC),sources=sources,archives=archives,
                  code={str(x):t.p.sha(x) for x in [Path(__file__),Path(t.__file__),Path(t.p.__file__),Path('scripts/run_ml_etf_risk_screen.py')]},
                  environment=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__),
                  parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    (out/'identity_before_evaluation.json').write_text(json.dumps(identity,indent=2)+'\n')
    paths=[]
    for scenario,cost,rate,delay,stress in [('primary8',.001,.08,0,False),('funding4',.001,.04,0,False),('funding12',.001,.12,0,False),('cost25',.0025,.08,0,False),('delay1',.001,.08,1,False),('double_moves',.001,.08,0,True)]:
        for label,k,cap in LADDER:
            d=simulate(fs,schedule,k,cap,cost,rate,delay,stress);d['scenario']=scenario;d['level']=label;paths.append(d)
        print(scenario+': seven paths reconciled',flush=True)
    d=pd.concat(paths,ignore_index=True);d.to_csv(out/'daily_ledger.csv',index=False)
    summary=summarize(d);summary.to_csv(out/'summary.csv',index=False)
    periods=[]
    for (scenario,level),g in d.groupby(['scenario','level']):
        for name,x in [('excluding_2020',g[g.date.dt.year!=2020]),*[(str(y),g[g.date.dt.year==y]) for y in range(2018,2025)]]:
            periods.append(dict(scenario=scenario,level=level,period=name,**t.p.metrics(x,name!='excluding_2020')))
    pd.DataFrame(periods).to_csv(out/'period_metrics.csv',index=False)
    base=t.ledger(fs,schedule,.001,0);one=d[(d.scenario=='primary8')&(d.level=='1x')]
    parity=float(np.max(np.abs(base.nav.to_numpy()-one.nav.to_numpy())))
    if parity>1e-10:raise ValueError('Baseline parity')
    report=dict(**identity,status='EXPLORATORY_EXPOSURE_MAP',model_fits=0,paths=42,baseline_nav_max_delta=parity,reserved_2025_used=False,
                files={x.name:t.p.sha(x) for x in out.glob('*.csv')},
                limitations='Fixed hypothetical financing, daily-open30% margin stop; no verified broker terms. Previously inspected history. Double-move replay is synthetic with frozen historical signals; gaps are instantaneous diagnostics, not probabilities or maximum-loss estimates.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    a=argparse.ArgumentParser()
    for name in ['etf-root','energy-zip','crop-zip','output-dir']:a.add_argument('--'+name,type=Path,required=True)
    x=a.parse_args();run(x.etf_root,x.energy_zip,x.crop_zip,x.output_dir)
