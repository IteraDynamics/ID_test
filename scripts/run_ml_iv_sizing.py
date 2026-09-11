"""Exploratory SPY/BIL sizing test with pre-2018 risk calibration and costs."""
import argparse, hashlib, json, platform, zipfile
from pathlib import Path
import numpy as np
import pandas as pd


def load_data(options, cash):
    with zipfile.ZipFile(options) as z:
        r=json.loads(z.read('options_variance_preparation.json'))
        for n,h in r['artifact_sha256'].items():
            if hashlib.sha256(z.read(n)).hexdigest()!=h:raise ValueError('Hash mismatch')
        f=pd.read_csv(z.open('options_daily_features.csv'))
    with zipfile.ZipFile(cash) as z:
        m=json.loads(z.read('BIL_1D.csv.manifest.json'))
        if m['request']['auto_adjust'] is not True:raise ValueError('BIL must be adjusted')
        b=pd.read_csv(z.open('BIL_1D.csv'))
    f['date']=pd.to_datetime(f.source_date,utc=True).dt.tz_convert(None).dt.normalize()
    b['date']=pd.to_datetime(b.timestamp,utc=True).dt.tz_convert(None).dt.normalize()
    f=f[(f.date>='2013-12-02')&(f.date<='2024-12-31')].copy()
    if f.date.duplicated().any() or b.date.duplicated().any():raise ValueError('Duplicate dates')
    f=f.merge(b[['date','close']].rename(columns={'close':'bil_close'}),on='date',how='left',validate='one_to_one').sort_values('date').reset_index(drop=True)
    if f[['close','bil_close']].isna().any().any():raise ValueError('Missing cash session; no forward fill')
    if not np.isfinite(f[['close','bil_close']]).all().all() or (f[['close','bil_close']]<=0).any().any():raise ValueError('Invalid price')
    # Rebalance after close t+1, using only features observed at t.
    eligible=f.anchor.astype(bool)&(f.iv_near>0)&(f.rv_21>0)&np.isfinite(f.iv_near)&np.isfinite(f.rv_21)
    for name,vol in [('iv',f.iv_near),('rv',np.sqrt(252*f.rv_21)),('constant',pd.Series(.10,index=f.index))]:
        f[name+'_signal']=(.10/vol).where(eligible).shift(1)
    f['spy_return']=f.close.pct_change(fill_method=None).fillna(0)
    f['bil_return']=f.bil_close.pct_change(fill_method=None).fillna(0)
    return f


def rebalance(stock,cash,target,rate):
    nav=stock+cash;cost=0.
    for _ in range(20):
        wealth=nav-cost
        traded=abs(target*wealth-stock)+abs((1-target)*wealth-cash)
        cost=rate*traded
    wealth=nav-cost
    return target*wealth,(1-target)*wealth,cost,traded


def simulate(f,name,scale,bps):
    stock,cash=0.,1.;records=[]
    for row in f.itertuples(index=False):
        before=stock+cash
        start_weight=stock/before
        stock*=1+row.spy_return;cash*=1+row.bil_return
        signal=getattr(row,name+'_signal');cost=trade=0.
        if np.isfinite(signal):
            stock,cash,cost,trade=rebalance(stock,cash,min(1,max(0,scale*signal)),bps/10000)
        after=stock+cash
        records.append((row.date,after/before-1,start_weight,stock/after,cost/before,trade/before))
    return pd.DataFrame(records,columns=['date','return','start_spy_weight','end_spy_weight','cost_fraction','traded_fraction'])


def calibrate(f,name):
    train=f[f.date<'2018-01-01']
    def vol(k):return float(simulate(train,name,k,0)['return'].std(ddof=1)*np.sqrt(252))
    lo,hi=0.,20.
    if vol(hi)<.10:return hi,vol(hi),False
    for _ in range(30):
        mid=(lo+hi)/2
        if vol(mid)<.10:lo=mid
        else:hi=mid
    return hi,vol(hi),True


def stats(r,cash):
    r=np.asarray(r);e=r-np.asarray(cash)
    nav=np.r_[1.,np.cumprod(1+r)];dd=nav/np.maximum.accumulate(nav)-1
    vol=float(np.std(r,ddof=1)*np.sqrt(252));ev=np.std(e,ddof=1)
    return dict(cagr=float(nav[-1]**(252/len(r))-1),volatility=vol,max_drawdown=float(dd.min()),
                excess_sharpe=float(e.mean()/ev*np.sqrt(252)) if ev>0 else None,
                certainty_equivalent=float(252*(e.mean()-1.5*np.var(r,ddof=1))))


def run(options,cash):
    f=load_data(options,cash);test=f.date>='2018-01-01'
    calibration={};frames=[];metrics=[]
    for name in ['constant','rv','iv']:
        scale,vol,attainable=calibrate(f,name)
        calibration[name]=dict(scale=scale,training_volatility=vol,target_attained=attainable)
        for cost in [1,5,10]:
            # Warm positions through training; costs charged in both periods.
            a=simulate(f,name,scale,cost).loc[test].copy();a['strategy']=name;a['cost_bps']=cost
            frames.append(a)
            s=stats(a['return'],f.loc[test,'bil_return'])
            s.update(strategy=name,cost_bps=cost,annual_traded_fraction=float(a.traded_fraction.mean()*252),
                     average_spy_weight=float(a.start_spy_weight.mean()),annual_cost_fraction=float(a.cost_fraction.mean()*252))
            metrics.append(s)
    daily=pd.concat(frames,ignore_index=True)
    rng=np.random.default_rng(20260911);n=int(test.sum())
    starts=rng.integers(0,n,(9999,int(np.ceil(n/65))))
    boot=((starts[:,:,None]+np.arange(65))%n).reshape(9999,-1)[:,:n]
    comparisons=[]
    for old in ['rv','constant']:
        for cost in [5,10]:
            new=daily[(daily.strategy=='iv')&(daily.cost_bps==cost)]
            baseline=daily[(daily.strategy==old)&(daily.cost_bps==cost)]
            a=new['return'].to_numpy();b=baseline['return'].to_numpy()
            delta=252*((a.mean()-b.mean())-1.5*(a.var(ddof=1)-b.var(ddof=1)))
            ba,bb=a[boot],b[boot]
            draws=252*((ba.mean(axis=1)-bb.mean(axis=1))-1.5*(ba.var(axis=1,ddof=1)-bb.var(axis=1,ddof=1)))
            interval=np.quantile(draws,[.025,.975])
            years={str(y):float(252*((a[new.date.dt.year==y].mean()-b[new.date.dt.year==y].mean())-1.5*(a[new.date.dt.year==y].var(ddof=1)-b[new.date.dt.year==y].var(ddof=1)))) for y in range(2018,2025)}
            ma=next(m for m in metrics if m['strategy']=='iv' and m['cost_bps']==cost)
            mb=next(m for m in metrics if m['strategy']==old and m['cost_bps']==cost)
            passed=delta>=.005 and interval[0]>0 and sum(v>0 for v in years.values())>=4 and ma['volatility']<=1.1*mb['volatility'] and ma['max_drawdown']>=mb['max_drawdown']-.02
            comparisons.append(dict(baseline=old,cost_bps=cost,annual_ce_improvement=float(delta),block95_interval=interval.tolist(),yearly_ce_improvement=years,gate_passed=bool(passed)))
    return daily,dict(status='EXPLORATORY_SIZING_TEST',calibration=calibration,metrics=metrics,comparisons=comparisons,
                       primary_gate_passed=bool(all(c['gate_passed'] for c in comparisons if c['cost_bps']==5) and all(c['annual_ce_improvement']>0 for c in comparisons if c['cost_bps']==10)),
                       assumptions=['SPY supplied close is treated as adjusted total-return proxy; not independently certified',
                                    'BIL source manifest specifies auto_adjust true',
                                    'Hypothetical next-session closing fills; costs are scenarios not measured broker estimates',
                                    'Fractional shares; no taxes, leverage, or terminal liquidation',
                                    'Common rebalance eligibility requires IV and RV; missing signal means hold all strategies',
                                    'Initial BIL acquisition before training omitted equally; warm positions at evaluation start',
                                    'No cost-free daily weight reset; weights drift between rebalances'],
                       limitations=['Discovery-contaminated; economic sensitivity not power-calibrated',
                                    'Prior permission for limited-power exploration retained; no confirmation claim',
                                    'In-sample risk calibration does not ensure equal out-of-sample risk',
                                    'No Core/runtime/portfolio changes'],
                       input_hashes={str(p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in [options,cash]},
                       environment=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--options-zip',type=Path,required=True);p.add_argument('--cash-zip',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    if a.output_dir.exists():raise ValueError('Refusing overwrite')
    d,r=run(a.options_zip,a.cash_zip);a.output_dir.mkdir(parents=True)
    d.to_csv(a.output_dir/'iv_sizing_daily.csv',index=False,float_format='%.17g',lineterminator='\n')
    r['daily_sha256']=hashlib.sha256((a.output_dir/'iv_sizing_daily.csv').read_bytes()).hexdigest()
    r['runner_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (a.output_dir/'iv_sizing_report.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
    print(json.dumps(r,indent=2))
