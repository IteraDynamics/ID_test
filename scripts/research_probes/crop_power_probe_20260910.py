"""Known-signal planning only: no learned model, no cost gate, no predictive result."""
import json
from pathlib import Path
import numpy as np,pandas as pd
p=Path('artifacts/ml_crop_feasibility_20260910');a=['CORN','WEAT','SOYB'];fs={x:pd.read_csv(p/f'{x}_1D.csv',index_col='timestamp',parse_dates=True) for x in a};bil=pd.read_csv('artifacts/ml_energy_feasibility_20260910/BIL_1D.csv',index_col='timestamp',parse_dates=True)
cal=bil.index
for f in fs.values():cal=cal.intersection(f.index)
rs=json.loads((p/'all_formats_index.json').read_text());ds=sorted({r['release_date'] for r in rs if '2018-01-01'<=r['release_date']<='2024-12-31'});monthly={}
for d in ds:monthly.setdefault(d[:7],d)
y=[];dates=[]
for d in monthly.values():
 i=cal.searchsorted(pd.Timestamp(d,tz='UTC'),side='right')+1;j=i+21
 if j>=len(cal):continue
 if any(f.loc[cal[[i,j]],'volume'].min()<=0 for f in fs.values()):continue
 cash=bil.loc[cal[j],'open']/bil.loc[cal[i],'open']-1
 y.append([f.loc[cal[j],'open']/f.loc[cal[i],'open']-1-cash for f in fs.values()]);dates.append(d)
y=np.array(y);y=(y-y.mean(0))/y.std(0);n=len(y);rng=np.random.default_rng(29010);B=2000;out=[]
for block in [3,6]:
 starts=rng.integers(0,n,(B,(n+block-1)//block));idx=((starts[:,:,None]+np.arange(block))%n).reshape(B,-1)[:,:n];noise=y[idx];noise-=noise.mean(1,keepdims=True);noise/=noise.std(1,keepdims=True)
 for share in [0.,.5,1.]:
  z=(1-share)**.5*rng.normal(size=(B,n,3))+share**.5*rng.normal(size=(B,n,1));x=np.zeros_like(z);x[:,0]=z[:,0]
  for t in range(1,n):x[:,t]=.5*x[:,t-1]+.75**.5*z[:,t]
  x-=x.mean(1,keepdims=True);x/=x.std(1,keepdims=True)
  null=(x*noise).mean((1,2));cut=np.quantile(abs(null[:1000]),.95)
  for effect in [0.,.1,.15,.2]:
   target=effect*x+(1-effect**2)**.5*noise;score=(x*target).mean((1,2));power=float((abs(score[1000:])>cut).mean());out.append(dict(block_months=block,shared_predictor_fraction=share,injected_standardized_effect=effect,rejection_fraction=power))
r=dict(status='KNOWN_SIGNAL_PLANNING_SIMULATION_NOT_MODEL_POWER',events=n,first=dates[0],last=dates[-1],seed=29010,simulations_per_scenario=B,results=out,limitations=['First listed release per calendar month used for planning; corrections not resolved.','Block-resampled full cross-asset return vectors preserve within-block dependence, not all regimes.','Synthetic AR(1)=0.5 predictor; signal known without estimation. Actual WASDE feature persistence and train/test model power remain unknown.','Injected standardized effect is not an observed correlation or net trading edge. No cost or portfolio rule is evaluated.','Threshold uses 1000 null draws; rejection estimated on disjoint 1000 draws.'])
(p/'power_planning.json').write_text(json.dumps(r,indent=2));print('events',n);print(out)
