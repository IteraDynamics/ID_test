"""Run the bounded development comparison described in ML_DEVELOPMENT_PROGRAM_20260910.md."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import warnings
import platform
import sklearn
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from threadpoolctl import threadpool_limits
from scripts.run_ml_etf_risk_screen import load_inputs, features, weekly_sessions, ASSETS

SUMMARY = ['ret5','ret20','ret60','trend','rv20','rv60','dd60','negative20',*ASSETS]
SEQUENCE = [f'{kind}_{lag}' for kind in ['return','volume'] for lag in range(19,-1,-1)]+list(ASSETS)
CANDIDATES = ['ridge1','ridge100','gbm2','gbm3','mlp16','mlp32','sequence16','sequence32']


def build_panel(frames):
    rows=[]
    for a,d in frames.items():
        f=features(d)
        r=d.close.pct_change(fill_method=None)
        v=d.volume/d.volume.rolling(60).mean()-1
        for lag in range(20):
            f[f'return_{lag}']=r.shift(lag)
            f[f'volume_{lag}']=v.shift(lag)
        for b in ASSETS: f[b]=float(a==b)
        f['target']=d.open.shift(-6)/d.open.shift(-1)-1
        f['label_end']=pd.Series(d.index,index=d.index).shift(-6)
        f['date']=d.index;f['asset']=a
        f['weekly']=np.isin(np.arange(len(d)),weekly_sessions(d.index))
        rows.append(f)
    return pd.concat(rows,ignore_index=True).dropna(subset=list(set(SUMMARY+SEQUENCE))+['target','label_end']).sort_values(['date','asset']).reset_index(drop=True)


def split(p,year):
    val=p.loc[p.weekly & (p.date.dt.year==year)]
    if val.empty: raise ValueError(f'No weekly validation in {year}')
    train=p.loc[p.label_end<val.date.min()]
    if train.date.nunique()<252: raise ValueError(f'Insufficient training dates in {year}')
    assert train.label_end.max()<val.date.min()
    return train,val


def inner_split(p,year,outer_year):
    train,val=split(p,year)
    _,outer=split(p,outer_year)
    val=val.loc[val.label_end<outer.date.min()]
    if val.empty:raise ValueError("Empty inner validation after outer-boundary purge")
    return train,val


def estimator(name):
    if name.startswith('ridge'): return make_pipeline(StandardScaler(),Ridge(alpha=float(name[5:])))
    if name.startswith('gbm'):
        return HistGradientBoostingRegressor(max_depth=int(name[-1]),max_iter=100,learning_rate=.05,
              min_samples_leaf=100,l2_regularization=10,early_stopping=False,random_state=17)
    width=(16,) if name.endswith('16') else (32,16)
    return make_pipeline(StandardScaler(),MLPRegressor(hidden_layer_sizes=width,activation='relu',
          solver='adam',alpha=.1,learning_rate_init=.001,max_iter=150,batch_size=128,
          shuffle=False,early_stopping=False,random_state=17))


def fit(name,train,val):
    columns=SEQUENCE if name.startswith('sequence') else SUMMARY
    with threadpool_limits(limits=1),warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        model=estimator(name)
        model.fit(train[columns],100*train.target)
        prediction=model.predict(val[columns])/100
        fitted=model.predict(train[columns])/100
    if not np.isfinite(prediction).all(): raise ValueError('Nonfinite prediction')
    return prediction,{'training_mse':float(np.mean((fitted-train.target.to_numpy())**2)),
      'validation_mse':float(np.mean((prediction-val.target.to_numpy())**2)),
      'validation_rows':len(val),'training_rows':len(train),'training_dates':train.date.nunique(),
      'last_training_outcome':str(train.label_end.max()),'first_validation_signal':str(val.date.min()),
      'warnings':' | '.join(str(w.message) for w in caught)}


def select(scores):
    # Predeclared row-weighted inner MSE, deterministic candidate-name tie break.
    totals={name:sum(s['validation_mse']*s['validation_rows'] for s in scores if s['candidate']==name)
        /sum(s['validation_rows'] for s in scores if s['candidate']==name) for name in CANDIDATES}
    return min(totals,key=lambda name:(totals[name],name)),totals


def evaluate(pred):
    rows=[]
    for year in ['all',*sorted(pred.date.dt.year.unique())]:
        y=pred if year=='all' else pred.loc[pred.date.dt.year==year]
        for asset in ['pooled',*ASSETS]:
            s=y if asset=='pooled' else y.loc[y.asset==asset]
            for name in [*CANDIDATES,'selected','zero','past_mean']:
                e=s[name]-s.target
                rows.append({'year':str(year),'asset':asset,'model':name,'rows':len(s),
                  'dates':s.date.nunique(),'mse':float((e**2).mean()),'mae':float(e.abs().mean()),
                  'correlation':float(s[name].corr(s.target)) if s[name].std()>0 and s.target.std()>0 else None})
    return pd.DataFrame(rows)


def run(root,output,smoke=False):
    if output.exists():raise FileExistsError(output)
    frames,sources=load_inputs(root);p=build_panel(frames)
    scores=[];selections=[];predictions=[]
    years=[2018] if smoke else range(2018,2025)
    for year in years:
        inner=[]
        for iv in [year-2,year-1]:
            train,val=inner_split(p,iv,year)
            for name in CANDIDATES:
                _,s=fit(name,train,val)
                s.update(candidate=name,outer_year=year,validation_year=iv,stage='inner')
                inner.append(s);scores.append(s)
        chosen,totals=select(inner)
        selections.append({'outer_year':year,'candidate':chosen,'inner_mse':totals})
        train,val=split(p,year)
        out=val[['date','asset','target','label_end']].copy()
        out['zero']=0.;out['past_mean']=out.asset.map(train.groupby('asset').target.mean())
        for name in CANDIDATES:
            out[name],s=fit(name,train,val)
            s.update(candidate=name,outer_year=year,validation_year=year,stage='outer')
            scores.append(s)
        out['selected']=out[chosen];out['selected_candidate']=chosen
        predictions.append(out)
        print(f'{year}: inner-selected {chosen}; 24 fits complete',flush=True)
    output.mkdir(parents=True)
    pred=pd.concat(predictions,ignore_index=True)
    artifacts={'forecasts':pred,'fit_diagnostics':pd.DataFrame(scores),'forecast_metrics':evaluate(pred)}
    hashes={}
    for name,data in artifacts.items():
        path=output/(name+'.csv');data.to_csv(path,index=False,lineterminator='\n')
        hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    report={'status':'DEVELOPMENT_DIAGNOSTIC_ONLY','smoke':smoke,'fits':len(scores),'sources':sources,
      'selections':selections,'artifacts':hashes,'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'limitations':'Previously inspected data. Outer results are diagnostic, not confirmation. No allocation or economic claim.',
      'environment':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__},
      'spec_sha256':hashlib.sha256((Path(__file__).resolve().parents[2]/'docs/research/ML_DEVELOPMENT_PROGRAM_20260910.md').read_bytes()).hexdigest(),
      'dependency_runner_sha256':hashlib.sha256((Path(__file__).resolve().parents[2]/'scripts/run_ml_etf_risk_screen.py').read_bytes()).hexdigest(),
      'reserved_2025_used':False}
    (output/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--smoke',action='store_true',help='Only 2018 outer block; 24 fits, counts against main budget.')
    args=parser.parse_args();run(args.input_root,args.output_dir,args.smoke)
