from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression,Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from research.core_regime_stability.study import episode_age,transition_target
from research.latent_state_trajectories.study import TrajectoryModel,PCS,TRAJECTORY
from research.multidimensional_regimes.study import panel_from_hourly
from research.crypto_reversal.experiment import HOUR

HORIZONS=(1,3,5,7,14); STABILITY_HORIZON=7
OUTCOMES=('log_return','log_variance','downside_semivariance','max_adverse_excursion','max_favorable_excursion','absolute_return','path_efficiency','sign_persistence')
STAB_COLS=PCS+TRAJECTORY+['episode_age']

def add_forward_outcomes(panel,hourly):
 grid=hourly.reindex(pd.date_range(hourly.index[0],hourly.index[-1],freq='h'));close=grid.close.copy();close.index+=HOUR
 daily=close.reindex(panel.index)
 out=panel.copy()
 for h in HORIZONS:
  rs=pd.concat([np.log(daily.shift(-k)/daily.shift(-(k-1))) for k in range(1,h+1)],axis=1);rel=pd.concat([daily.shift(-k)/daily-1 for k in range(1,h+1)],axis=1);complete=rs.notna().all(axis=1)
  endpoint=rs.sum(axis=1,min_count=h);path=rs.abs().sum(axis=1,min_count=h);same=((np.sign(rs).eq(np.sign(endpoint),axis=0)) & rs.ne(0)).sum(axis=1);nonzero=rs.ne(0).sum(axis=1)
  vals={'log_return':endpoint,'log_variance':np.log(rs.pow(2).sum(axis=1,min_count=h).clip(lower=1e-12)),'downside_semivariance':rs.clip(upper=0).pow(2).sum(axis=1,min_count=h),'max_adverse_excursion':rel.min(axis=1),'max_favorable_excursion':rel.max(axis=1),'absolute_return':endpoint.abs(),'path_efficiency':endpoint.abs()/path.replace(0,np.nan),'sign_persistence':same/nonzero.replace(0,np.nan)}
  for name,s in vals.items():out[f'{name}_{h}d']=s.where(complete)
  out[f'outcome_end_{h}d']=out.index+h*24*HOUR
 return out

def _stability_model(train):
 tr=train.copy();tr['episode_age']=episode_age(tr.core_label);tr['transition_7d']=transition_target(tr.core_label,7);tr=tr.dropna(subset=['transition_7d',*STAB_COLS]);
 if len(tr)<250 or tr.transition_7d.nunique()<2:raise ValueError('Insufficient stability training data')
 pre=ColumnTransformer([('core',OneHotEncoder(handle_unknown='ignore'),['core_label']),('x',StandardScaler(),STAB_COLS)])
 m=make_pipeline(pre,LogisticRegression(C=.1,max_iter=3000,random_state=1729));m.fit(tr[['core_label',*STAB_COLS]],tr.transition_7d.astype(int));return m

def _predict_stability(model,frame,ages):
 x=frame.copy();x['episode_age']=ages.reindex(x.index);return pd.Series(model.predict_proba(x[['core_label',*STAB_COLS]])[:,1],index=x.index)

def _ridge(train,test,target,cols,core=True):
 tr=train.dropna(subset=[target,*cols]);te=test.dropna(subset=[target,*cols]);
 if len(tr)<250 or te.empty:return None
 if core:
  pre=ColumnTransformer([('core',OneHotEncoder(handle_unknown='ignore'),['core_label']),('x',StandardScaler(),cols)]);m=make_pipeline(pre,Ridge(alpha=10.));m.fit(tr[['core_label',*cols]],tr[target]);p=m.predict(te[['core_label',*cols]])
 else:
  m=make_pipeline(StandardScaler(),Ridge(alpha=10.));m.fit(tr[cols],tr[target]);p=m.predict(te[cols])
 return te.index,p

def evaluate(hourly,asset,hours,years=range(2020,2026)):
 base=add_forward_outcomes(panel_from_hourly(hourly,hours),hourly);all_age=episode_age(base.core_label);out={k:[] for k in ['scores','bins','correlations','fits']}
 for year in years:
  cutoff=pd.Timestamp(f'{year}-01-01',tz='UTC');finish=pd.Timestamp(f'{year+1}-01-01',tz='UTC');fit_base=base.loc[(base.index<cutoff)&(base.label_end<cutoff)];eval_base=base.loc[(base.index>=cutoff)&(base.index<finish)]
  tm=TrajectoryModel().fit(fit_base);train=tm.transform(fit_base);test=tm.transform(eval_base);train['episode_age']=all_age.reindex(train.index);test['episode_age']=all_age.reindex(test.index)
  # Frozen 7d instability model is fit only on pre-cutoff observations. Evaluation probabilities are strictly OOS.
  sm=_stability_model(train);test['instability_7d']=_predict_stability(sm,test,test.episode_age)
  # Causal annual OOF stability probabilities for supervised behavior-model training; no in-sample stacked probabilities.
  train['instability_7d']=np.nan
  first=max(int(base.index.min().year)+1,2019)
  for oy in range(first,year):
   oc=pd.Timestamp(f'{oy}-01-01',tz='UTC');oe=pd.Timestamp(f'{oy+1}-01-01',tz='UTC');hist=base.loc[(base.index<oc)&(base.label_end<oc)];blk=base.loc[(base.index>=oc)&(base.index<oe)]
   if len(hist)<250 or blk.empty:continue
   otm=TrajectoryModel().fit(hist);oh=otm.transform(hist);ob=otm.transform(blk);oh['episode_age']=all_age.reindex(oh.index);ob['episode_age']=all_age.reindex(ob.index)
   try: osm=_stability_model(oh)
   except ValueError: continue
   common=train.index.intersection(ob.index);train.loc[common,'instability_7d']=_predict_stability(osm,ob,ob.episode_age).reindex(common)
  keys=dict(asset=asset,timeframe=hours,year=year);out['fits'].append(dict(**keys,training_rows=len(train),oof_instability_rows=int(train.instability_7d.notna().sum()),fit_at=str(cutoff),latest_training_label_end=str(train.label_end.max())))
  # Training-distribution within-Core quintile cut points; evaluation is never re-ranked.
  for label,gte in test.groupby('core_label'):
   gtr=train.loc[train.core_label==label,'instability_7d'].dropna()
   if len(gtr)<50:continue
   cuts=np.unique(gtr.quantile([.2,.4,.6,.8]).to_numpy());
   if len(cuts)!=4:continue
   b=np.digitize(gte.instability_7d.to_numpy(),cuts,right=True)+1
   for h in HORIZONS:
    for target in OUTCOMES:
     col=f'{target}_{h}d';valid=gte[col].notna()&gte.instability_7d.notna()
     if valid.sum()>=5:
      rho,pv=spearmanr(gte.loc[valid,'instability_7d'],gte.loc[valid,col]);out['correlations'].append(dict(**keys,core_label=str(label),horizon_days=h,target=target,n=int(valid.sum()),spearman=float(rho),pvalue=float(pv)))
     for q in range(1,6):
      v=gte.loc[(b==q)&gte[col].notna(),col]
      if len(v):out['bins'].append(dict(**keys,core_label=str(label),horizon_days=h,target=target,instability_quintile=q,n=len(v),mean=float(v.mean()),median=float(v.median()),q10=float(v.quantile(.1)),q90=float(v.quantile(.9))))
  for h in HORIZONS:
   for target in OUTCOMES:
    col=f'{target}_{h}d';mature=train[f'outcome_end_{h}d']<cutoff;tr=train.loc[mature].copy();te=test.copy();reps=[('core',[],True),('core_plus_pca4',PCS,True),('core_plus_instability',['instability_7d'],True),('core_plus_pca4_plus_instability',PCS+['instability_7d'],True)];pred={}
    for name,cols,core in reps:
     r=_ridge(tr,te,col,cols,core)
     if r:pred[name]=r
    if 'core' not in pred:continue
    bi,bp=pred['core'];by=te.loc[bi,col].to_numpy();bl=float(np.mean((bp-by)**2))
    for name,(idx,p) in pred.items():
     y=te.loc[idx,col].to_numpy();loss=float(np.mean((p-y)**2));out['scores'].append(dict(**keys,horizon_days=h,target=target,representation=name,n=len(idx),mse=loss,core_mse=bl,skill_vs_core=1-loss/bl if bl else None))
  print(f'{asset} {hours}H {year}: conditional behavior complete',flush=True)
 return out

__all__=['evaluate','add_forward_outcomes','HORIZONS','OUTCOMES','STABILITY_HORIZON']
