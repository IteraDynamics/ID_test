from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer

from research.regime_state_compression.study import CompressionModel
from research.multidimensional_regimes.study import TARGETS, panel_from_hourly

PCS = [f'pc{i}' for i in range(1, 5)]
TRAJECTORY = ['speed','accel_mag','center_distance','radial_velocity','radial_alignment','core_centroid_distance','alternate_centroid_distance','centroid_margin','margin_velocity']
HORIZONS = (1, 3, 7)


def _safe_cos(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    den = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
    out = np.zeros(len(a), dtype=float)
    ok = den > 1e-12
    out[ok] = np.sum(a[ok] * b[ok], axis=1) / den[ok]
    return out


class TrajectoryModel:
    def fit(self, train: pd.DataFrame) -> 'TrajectoryModel':
        self.compression = CompressionModel().fit(train)
        z = self.compression.transform(train)[PCS].to_numpy()
        self.center = z.mean(axis=0)
        self.core_centers = {}
        temp = train.copy()
        temp[PCS] = z
        for label, g in temp.groupby('core_label'):
            self.core_centers[str(label)] = g[PCS].to_numpy().mean(axis=0)
        if len(self.core_centers) < 2:
            raise ValueError('Need at least two Core labels for centroid geometry')
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = self.compression.transform(frame)
        z = out[PCS].to_numpy()
        v = np.vstack([np.full((1,4), np.nan), np.diff(z, axis=0)])
        a = np.vstack([np.full((1,4), np.nan), np.diff(v, axis=0)])
        radial = z - self.center
        out['speed'] = np.linalg.norm(v, axis=1)
        out['accel_mag'] = np.linalg.norm(a, axis=1)
        out['center_distance'] = np.linalg.norm(radial, axis=1)
        out['radial_velocity'] = out['center_distance'].diff()
        out['radial_alignment'] = _safe_cos(np.nan_to_num(v), radial)
        current_d, alt_d = [], []
        for label, point in zip(out.core_label.astype(str), z):
            if label not in self.core_centers:
                current_d.append(np.nan)
                ds = [np.linalg.norm(point-c) for c in self.core_centers.values()]
                alt_d.append(min(ds) if ds else np.nan)
                continue
            current = np.linalg.norm(point-self.core_centers[label])
            others = [np.linalg.norm(point-c) for k,c in self.core_centers.items() if k != label]
            current_d.append(current)
            alt_d.append(min(others))
        out['core_centroid_distance'] = current_d
        out['alternate_centroid_distance'] = alt_d
        out['centroid_margin'] = out.core_centroid_distance - out.alternate_centroid_distance
        out['margin_velocity'] = out.centroid_margin.diff()
        return out


def add_forward_events(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    labels = out.core_label.astype(str)
    for h in HORIZONS:
        future = pd.concat([labels.shift(-i) for i in range(1,h+1)], axis=1)
        out[f'core_transition_{h}d'] = future.ne(labels, axis=0).any(axis=1).astype(float)
        out.loc[future.isna().any(axis=1), f'core_transition_{h}d'] = np.nan
    # Expansion is deliberately relative, not tuned: forward log variance > current/trailing log ATR proxy.
    if 'log_variance' in out and 'log_atr' in out:
        out['vol_expansion'] = (out.log_variance > 2.0*out.log_atr).astype(float)
        out.loc[out.log_variance.isna(), 'vol_expansion'] = np.nan
    return out


def _ridge(train, test, cols, target):
    m = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    m.fit(train[cols], train[target])
    return m.predict(test[cols])


def _core_plus(train, test, cols, target):
    pre = ColumnTransformer([('core', OneHotEncoder(handle_unknown='ignore'), ['core_label']), ('x', StandardScaler(), cols)])
    m = make_pipeline(pre, Ridge(alpha=10.0))
    m.fit(train[['core_label',*cols]], train[target])
    return m.predict(test[['core_label',*cols]])


def _binary_score(train, test, cols, target, include_core=False):
    tr = train.dropna(subset=[target,*cols]).copy()
    te = test.dropna(subset=[target,*cols]).copy()
    if tr[target].nunique() < 2 or te.empty:
        return None
    if include_core:
        pre = ColumnTransformer([('core', OneHotEncoder(handle_unknown='ignore'), ['core_label']), ('x', StandardScaler(), cols)])
        m = make_pipeline(pre, LogisticRegression(C=.1, max_iter=2000, random_state=1729))
        m.fit(tr[['core_label',*cols]], tr[target].astype(int))
        p = m.predict_proba(te[['core_label',*cols]])[:,1]
    else:
        m = make_pipeline(StandardScaler(), LogisticRegression(C=.1, max_iter=2000, random_state=1729))
        m.fit(tr[cols], tr[target].astype(int)); p = m.predict_proba(te[cols])[:,1]
    y = te[target].to_numpy()
    prior = tr[target].mean(); base = np.mean((y-prior)**2); loss=np.mean((y-p)**2)
    return dict(observations=len(te), events=int(y.sum()), brier=loss, constant_brier=base, skill_vs_constant=1-loss/base if base else None)


def evaluate(panel: pd.DataFrame, asset: str, hours: int, years=range(2020,2026)) -> dict:
    outputs={k:[] for k in ['scores','events','lead_lag','fits']}
    for year in years:
        cutoff=pd.Timestamp(f'{year}-01-01',tz='UTC'); end=pd.Timestamp(f'{year+1}-01-01',tz='UTC')
        fitting=panel.loc[(panel.index<cutoff)&(panel.label_end<cutoff)]
        test=panel.loc[(panel.index>=cutoff)&(panel.index<end)]
        model=TrajectoryModel().fit(fitting)
        train=add_forward_events(model.transform(fitting)); test=add_forward_events(model.transform(test))
        keys=dict(asset=asset,timeframe=hours,year=year)
        outputs['fits'].append(dict(**keys,fit_at=str(cutoff),training_rows=len(train),latest_training_label_end=str(train.label_end.max()),center=model.center.tolist(),core_centers={k:v.tolist() for k,v in model.core_centers.items()}))
        # Continuous risk targets.
        for target in ('log_variance','downside'):
            tr=train.dropna(subset=[target,*PCS,*TRAJECTORY]); te=test.dropna(subset=[target,*PCS,*TRAJECTORY])
            y=te[target].to_numpy(); prior=tr[target].mean(); base=np.mean((y-prior)**2)
            reps={
                'pca4': _ridge(tr,te,PCS,target),
                'trajectory': _ridge(tr,te,TRAJECTORY,target),
                'pca4_plus_trajectory': _ridge(tr,te,PCS+TRAJECTORY,target),
                'core_plus_trajectory': _core_plus(tr,te,TRAJECTORY,target),
                'core_plus_pca4_plus_trajectory': _core_plus(tr,te,PCS+TRAJECTORY,target),
            }
            core=_core_plus(tr,te,[],target); core_loss=np.mean((y-core)**2)
            for name,pred in {'core_label':core,**reps}.items():
                if target=='downside': pred=np.clip(pred,0,1)
                loss=np.mean((y-pred)**2)
                outputs['scores'].append(dict(**keys,representation=name,target=target,observations=len(te),mse=float(loss),constant_mse=float(base),skill_vs_constant=float(1-loss/base),skill_vs_core=float(1-loss/core_loss) if core_loss else None))
        # Transition and expansion classification.
        for target in [f'core_transition_{h}d' for h in HORIZONS]+(['vol_expansion'] if 'vol_expansion' in train else []):
            for name,cols,core in [('pca4',PCS,False),('trajectory',TRAJECTORY,False),('pca4_plus_trajectory',PCS+TRAJECTORY,False),('core_plus_trajectory',TRAJECTORY,True),('core_plus_pca4_plus_trajectory',PCS+TRAJECTORY,True)]:
                score=_binary_score(train,test,cols,target,core)
                if score: outputs['events'].append(dict(**keys,representation=name,target=target,**score))
        # Descriptive pre-transition windows: no tuned thresholds.
        labels=test.core_label.astype(str)
        next_change=labels.ne(labels.shift(-1))
        for lead in (1,2,3,5,7):
            pre=next_change.shift(-lead).fillna(False)
            for col in TRAJECTORY:
                a=test.loc[pre,col].dropna(); b=test.loc[~pre,col].dropna()
                outputs['lead_lag'].append(dict(**keys,lead_days=lead,feature=col,pre_transition_n=len(a),control_n=len(b),pre_transition_mean=float(a.mean()) if len(a) else None,control_mean=float(b.mean()) if len(b) else None,standardized_difference=float((a.mean()-b.mean())/b.std(ddof=0)) if len(a) and b.std(ddof=0)>0 else None))
        print(f'{asset} {hours}H {year}: latent trajectory study complete',flush=True)
    return outputs

__all__=['evaluate','panel_from_hourly','TrajectoryModel','PCS','TRAJECTORY','HORIZONS']
