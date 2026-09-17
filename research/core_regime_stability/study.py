from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from research.latent_state_trajectories.study import TrajectoryModel,PCS,TRAJECTORY
from research.multidimensional_regimes.study import panel_from_hourly

HORIZONS=(1,2,3,5,7,10,14)
AGE=['episode_age']

def episode_age(labels: pd.Series)->pd.Series:
 v=labels.astype(str).to_numpy(); out=np.ones(len(v),dtype=float)
 for i in range(1,len(v)): out[i]=out[i-1]+1 if v[i]==v[i-1] else 1
 return pd.Series(out,index=labels.index)

def transition_target(labels: pd.Series,h:int)->pd.Series:
 v=labels.astype(str).to_numpy(); out=np.full(len(v),np.nan)
 for i in range(len(v)):
  if i+h>=len(v): continue
  out[i]=float(any(v[j]!=v[i] for j in range(i+1,i+h+1)))
 return pd.Series(out,index=labels.index)

def _fit_predict(train,test,cols,target,core=False):
 tr=train.dropna(subset=[target,*cols]).copy();te=test.dropna(subset=[target,*cols]).copy()
 if tr[target].nunique()<2 or te.empty:return None
 if core:
  pre=ColumnTransformer([('core',OneHotEncoder(handle_unknown='ignore'),['core_label']),('x',StandardScaler(),cols)])
  model=make_pipeline(pre,LogisticRegression(C=.1,max_iter=3000,random_state=1729));xtr=tr[['core_label',*cols]];xte=te[['core_label',*cols]]
 else:
  model=make_pipeline(StandardScaler(),LogisticRegression(C=.1,max_iter=3000,random_state=1729));xtr=tr[cols];xte=te[cols]
 model.fit(xtr,tr[target].astype(int));p=model.predict_proba(xte)[:,list(model.classes_).index(1)];y=te[target].astype(int).to_numpy();base=float(tr[target].mean());loss=brier_score_loss(y,p);constant=float(np.mean((y-base)**2));auc=float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None
 return te.index,p,dict(observations=len(te),events=int(y.sum()),event_rate=float(y.mean()),brier=loss,constant_brier=constant,skill_vs_constant=1-loss/constant if constant else None,auc=auc)

def evaluate(panel,asset,hours,years=range(2020,2026)):
 out={k:[] for k in ['scores','calibration','by_core','lead_profile','fits']}
 for year in years:
  cutoff=pd.Timestamp(f'{year}-01-01',tz='UTC');end=pd.Timestamp(f'{year+1}-01-01',tz='UTC');fitting=panel.loc[(panel.index<cutoff)&(panel.label_end<cutoff)];raw=panel.loc[(panel.index>=cutoff)&(panel.index<end)]
  if raw.empty:raise ValueError(f'No evaluation rows {asset}/{hours}/{year}')
  tm=TrajectoryModel().fit(fitting);train=tm.transform(fitting);test=tm.transform(raw);train['episode_age']=episode_age(train.core_label);test['episode_age']=episode_age(test.core_label)
  if not train.label_end.max()<cutoff:raise ValueError('Training maturity violation')
  keys=dict(asset=asset,timeframe=hours,year=year);out['fits'].append(dict(**keys,fit_at=str(cutoff),training_rows=len(train),latest_training_label_end=str(train.label_end.max())))
  for h in HORIZONS:
   target=f'transition_{h}d';train[target]=transition_target(train.core_label,h);test[target]=transition_target(test.core_label,h)
   reps=[('episode_age',AGE,False),('pca4',PCS,False),('trajectory',TRAJECTORY,False),('core',[],True),('core_plus_episode_age',AGE,True),('core_plus_pca4',PCS,True),('core_plus_trajectory',TRAJECTORY,True),('core_plus_pca4_plus_trajectory',PCS+TRAJECTORY,True),('core_plus_pca4_plus_trajectory_plus_age',PCS+TRAJECTORY+AGE,True)]
   predictions={}
   for name,cols,core in reps:
    result=_fit_predict(train,test,cols,target,core)
    if not result:continue
    idx,p,score=result;predictions[name]=(idx,p);out['scores'].append(dict(**keys,horizon_days=h,representation=name,**score))
   if 'core' in predictions:
    ci,cp=predictions['core'];cy=test.loc[ci,target].astype(int).to_numpy();core_loss=brier_score_loss(cy,cp)
    for row in out['scores']:
     if all(row[k]==keys[k] for k in keys) and row['horizon_days']==h:
      idx,p=predictions[row['representation']];y=test.loc[idx,target].astype(int).to_numpy();row['skill_vs_core']=1-brier_score_loss(y,p)/core_loss if core_loss else None
   best='core_plus_pca4_plus_trajectory_plus_age'
   if best in predictions:
    idx,p=predictions[best];sc=pd.DataFrame({'p':p,'y':test.loc[idx,target].astype(int),'core':test.loc[idx,'core_label'].astype(str)},index=idx);rank=sc.p.rank(method='first');sc['decile']=pd.qcut(rank,10,labels=False,duplicates='drop')+1
    for d,g in sc.groupby('decile'):out['calibration'].append(dict(**keys,horizon_days=h,decile=int(d),mean_predicted=float(g.p.mean()),observed_rate=float(g.y.mean()),n=len(g)))
    for label,g in sc.groupby('core'):out['by_core'].append(dict(**keys,horizon_days=h,core_label=label,n=len(g),events=int(g.y.sum()),event_rate=float(g.y.mean()),mean_predicted=float(g.p.mean()),auc=float(roc_auc_score(g.y,g.p)) if g.y.nunique()==2 else None))
  # frozen lead profile uses the 7d stability model score if available
  if 'transition_7d' in test and 'core_plus_pca4_plus_trajectory_plus_age' in predictions:
   idx,p=predictions['core_plus_pca4_plus_trajectory_plus_age'];ps=pd.Series(p,index=idx);labels=test.core_label.astype(str);changes=np.flatnonzero(labels.to_numpy()[1:]!=labels.to_numpy()[:-1])+1
   for lead in HORIZONS:
    vals=[float(ps.loc[test.index[c-lead]]) for c in changes if c-lead>=0 and test.index[c-lead] in ps.index]
    if vals:out['lead_profile'].append(dict(**keys,model_horizon_days=7,lead_days=lead,n=len(vals),mean_instability=float(np.mean(vals)),median_instability=float(np.median(vals))))
  print(f'{asset} {hours}H {year}: stability complete',flush=True)
 return out

__all__=['evaluate','panel_from_hourly','episode_age','transition_target','HORIZONS']
