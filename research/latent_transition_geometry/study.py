from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from research.latent_state_trajectories.study import TrajectoryModel, PCS, TRAJECTORY
from research.multidimensional_regimes.study import panel_from_hourly

HORIZONS=(1,2,3,5,7,10,14)
MIN_TRAIN_EVENTS=20
MIN_EVAL_EVENTS=5


def first_destination(labels: pd.Series, horizon: int) -> pd.Series:
    values=labels.astype(str).to_numpy(); result=np.empty(len(values),dtype=object)
    for i,current in enumerate(values):
        destination='NO_TRANSITION'
        complete=i+horizon < len(values)
        if not complete:
            result[i]=None; continue
        for j in range(i+1,i+horizon+1):
            if values[j] != current:
                destination=values[j]; break
        result[i]=destination
    return pd.Series(result,index=labels.index,dtype='object')


def _multiclass(train,test,cols,target,include_core=False):
    tr=train.dropna(subset=[target,*cols]).copy(); te=test.dropna(subset=[target,*cols]).copy()
    classes=sorted(tr[target].astype(str).unique())
    if len(classes)<2 or te.empty: return None
    if include_core:
        pre=ColumnTransformer([('core',OneHotEncoder(handle_unknown='ignore'),['core_label']),('x',StandardScaler(),cols)])
        model=make_pipeline(pre,LogisticRegression(C=.1,max_iter=3000,random_state=1729))
        xtr=tr[['core_label',*cols]]; xte=te[['core_label',*cols]]
    else:
        model=make_pipeline(StandardScaler(),LogisticRegression(C=.1,max_iter=3000,random_state=1729))
        xtr=tr[cols]; xte=te[cols]
    model.fit(xtr,tr[target].astype(str)); prob=model.predict_proba(xte); fitted=list(model.classes_)
    y=te[target].astype(str).to_numpy(); all_classes=sorted(set(classes)|set(y)); pi=tr[target].astype(str).value_counts(normalize=True)
    loss=[]; base=[]
    for row,label in zip(prob,y):
        pm={c:row[fitted.index(c)] if c in fitted else 0.0 for c in all_classes}
        loss.append(sum((pm[c]-(1.0 if c==label else 0.0))**2 for c in all_classes))
        base.append(sum((float(pi.get(c,0.0))-(1.0 if c==label else 0.0))**2 for c in all_classes))
    loss=float(np.mean(loss)); base=float(np.mean(base))
    return dict(observations=len(te),classes=len(all_classes),multiclass_brier=loss,constant_brier=base,skill_vs_constant=1-loss/base if base else None)


def _pair_geometry(test: pd.DataFrame, model: TrajectoryModel, keys: dict) -> list[dict]:
    rows=[]; labels=test.core_label.astype(str); z=test[PCS].to_numpy(); idx=test.index
    changes=np.flatnonzero(labels.to_numpy()[1:] != labels.to_numpy()[:-1])+1
    for change in changes:
        source=labels.iloc[change-1]; dest=labels.iloc[change]
        if source not in model.core_centers or dest not in model.core_centers: continue
        dc=model.core_centers[dest]; sc=model.core_centers[source]
        for lead in HORIZONS:
            pos=change-lead
            if pos<1: continue
            point=z[pos]; prev=z[pos-1]; velocity=point-prev
            to_dest=dc-point; nd=np.linalg.norm(to_dest); nv=np.linalg.norm(velocity)
            alignment=float(np.dot(velocity,to_dest)/(nv*nd)) if nv>1e-12 and nd>1e-12 else 0.0
            prev_dest=float(np.linalg.norm(prev-dc)); dest_dist=float(np.linalg.norm(point-dc)); source_dist=float(np.linalg.norm(point-sc))
            rows.append(dict(**keys,source=source,destination=dest,lead_days=lead,event_at=str(idx[change]),distance_destination=dest_dist,distance_source=source_dist,destination_margin=dest_dist-source_dist,destination_distance_change=dest_dist-prev_dest,alignment_toward_destination=alignment,speed=float(test.iloc[pos].speed),accel_mag=float(test.iloc[pos].accel_mag)))
    return rows


def evaluate(panel: pd.DataFrame, asset: str, hours: int, years=range(2020,2026)) -> dict:
    outputs={k:[] for k in ['scores','pair_counts','pair_geometry','fits']}
    for year in years:
        cutoff=pd.Timestamp(f'{year}-01-01',tz='UTC'); end=pd.Timestamp(f'{year+1}-01-01',tz='UTC')
        fitting=panel.loc[(panel.index<cutoff)&(panel.label_end<cutoff)]; raw_test=panel.loc[(panel.index>=cutoff)&(panel.index<end)]
        if raw_test.empty: raise ValueError(f'No evaluation rows for {asset}/{hours}/{year}')
        model=TrajectoryModel().fit(fitting); train=model.transform(fitting); test=model.transform(raw_test)
        if not train.label_end.max()<cutoff: raise ValueError('Training maturity boundary violation')
        keys=dict(asset=asset,timeframe=hours,year=year)
        outputs['fits'].append(dict(**keys,fit_at=str(cutoff),training_rows=len(train),latest_training_label_end=str(train.label_end.max()),core_centers={k:v.tolist() for k,v in model.core_centers.items()}))
        for h in HORIZONS:
            target=f'destination_{h}d'; train[target]=first_destination(train.core_label,h); test[target]=first_destination(test.core_label,h)
            reps=[('pca4',PCS,False),('trajectory',TRAJECTORY,False),('core_plus_pca4',PCS,True),('core_plus_trajectory',TRAJECTORY,True),('pca4_plus_trajectory',PCS+TRAJECTORY,False),('core_plus_pca4_plus_trajectory',PCS+TRAJECTORY,True)]
            for name,cols,core in reps:
                score=_multiclass(train,test,cols,target,core)
                if score: outputs['scores'].append(dict(**keys,horizon_days=h,representation=name,**score))
            tr_pairs=train.loc[train[target].notna() & train[target].ne('NO_TRANSITION')].groupby(['core_label',target]).size()
            te_pairs=test.loc[test[target].notna() & test[target].ne('NO_TRANSITION')].groupby(['core_label',target]).size()
            pairs=set(tr_pairs.index)|set(te_pairs.index)
            for source,dest in sorted(pairs):
                nt=int(tr_pairs.get((source,dest),0)); ne=int(te_pairs.get((source,dest),0))
                outputs['pair_counts'].append(dict(**keys,horizon_days=h,source=source,destination=dest,training_events=nt,evaluation_events=ne,supported=nt>=MIN_TRAIN_EVENTS and ne>=MIN_EVAL_EVENTS))
        outputs['pair_geometry'].extend(_pair_geometry(test,model,keys))
        print(f'{asset} {hours}H {year}: transition geometry complete',flush=True)
    return outputs

__all__=['evaluate','panel_from_hourly','first_destination','HORIZONS','MIN_TRAIN_EVENTS','MIN_EVAL_EVENTS']
