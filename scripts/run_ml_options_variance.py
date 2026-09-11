"""Fixed exploratory variance comparison; operator authorized limited-power run.
No tuning, trade simulation, or confirmation claim. Uses only prepared <=2024 data.
"""
import argparse
import hashlib
import json
import platform
import sklearn
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_panel(path):
    with zipfile.ZipFile(path) as z:
        report=json.loads(z.read('options_variance_preparation.json'))
        for name, expected in report['artifact_sha256'].items():
            if hashlib.sha256(z.read(name)).hexdigest()!=expected:
                raise ValueError('Artifact hash mismatch')
        f=pd.read_csv(z.open('options_variance_anchors.csv'))
    f=f.sort_values('source_date').reset_index(drop=True)
    for c in ['source_date','execution_date','target_end']:
        f[c]=pd.to_datetime(f[c],errors='raise')
    if f.source_date.duplicated().any() or f.target_end.max()>pd.Timestamp('2024-12-31'):
        raise ValueError('Invalid dates or forbidden target coverage')
    if not ((f.source_date<f.execution_date)&(f.execution_date<f.target_end)).all():
        raise ValueError('Invalid timing')
    if (f.execution_date.iloc[1:].to_numpy()<f.target_end.iloc[:-1].to_numpy()).any():
        raise ValueError('Overlapping target intervals')
    if not np.isfinite(f.future_variance_5).all() or (f.future_variance_5<=0).any():
        raise ValueError('QLIKE requires positive finite targets; no silent flooring')
    return f


def features(f):
    a=np.column_stack([np.log(f.rv_5),np.log(f.rv_21),np.log(f.rv_63),f.return_21])
    b=np.column_stack([a,np.log(f.iv_near)])
    c=np.column_stack([b,f[['iv_far','put_call_skew','iv_term_slope',
                            'gamma_strike_concentration','front_gamma_share','log_gamma_z252']]])
    if not np.isfinite(c).all():raise ValueError('Nonfinite features')
    return {'A':a,'B':b,'C':c}


def predict_fold(x,y,train,test,kind):
    model=(make_pipeline(StandardScaler(),Ridge(alpha=10)) if kind=='ridge' else
           GradientBoostingRegressor(n_estimators=200,max_depth=2,learning_rate=.04,
                                     min_samples_leaf=20,loss='squared_error',random_state=20260911))
    log_y=np.log(y[train])
    model.fit(x[train],log_y)
    smear=np.exp(log_y-model.predict(x[train])).mean()
    p=np.exp(model.predict(x[test]))*smear
    if not np.isfinite(p).all() or (p<=0).any():raise ValueError('Invalid predictions')
    return p


def evaluate(f):
    x=features(f);y=f.future_variance_5.to_numpy()
    parts=[];folds=[]
    for year in range(2018,2025):
        train=(f.target_end<pd.Timestamp(year,1,1)).to_numpy()
        test=(f.source_date.dt.year==year).to_numpy()
        if train.sum()<100 or test.sum()<20:raise ValueError('Insufficient fold coverage')
        out=f.loc[test,['source_date','execution_date','target_end','future_variance_5']].copy()
        out['year']=year
        out['rv21']=5*f.loc[test,'rv_21']
        out['iv_near_raw']=5/252*f.loc[test,'iv_near']**2
        for kind in ['ridge','gbm']:
            for group in ['A','B','C']:
                out[kind+'_'+group]=predict_fold(x[group],y,train,test,kind)
        parts.append(out)
        folds.append(dict(year=year,train=int(train.sum()),test=int(test.sum()),
                          latest_training_target=str(f.loc[train,'target_end'].max().date())))
    return pd.concat(parts,ignore_index=True),folds


def summarize(pred):
    models=['rv21','iv_near_raw']+[k+'_'+g for k in ['ridge','gbm'] for g in ['A','B','C']]
    y=pred.future_variance_5.to_numpy()
    losses={m:y/pred[m].to_numpy()-np.log(y/pred[m].to_numpy())-1 for m in models}
    metrics=[dict(model=m,mean_qlike=float(losses[m].mean()),
                  mean_squared_error=float(np.mean((y-pred[m].to_numpy())**2))) for m in models]
    rng=np.random.default_rng(20260911); n=len(pred)
    starts=rng.integers(0,n,(9999,int(np.ceil(n/13))))
    boot=((starts[:,:,None]+np.arange(13))%n).reshape(9999,-1)[:,:n]
    comparisons=[]
    for new,old in [('ridge_C','ridge_B'),('ridge_B','ridge_A'),('gbm_C','gbm_B'),
                    ('gbm_B','gbm_A'),('gbm_C','ridge_C'),('ridge_B','iv_near_raw')]:
        d=losses[old]-losses[new]
        lo,hi=np.quantile(d[boot].mean(axis=1),[.025,.975])
        yearly={str(year):float(d[pred.year.to_numpy()==year].mean()) for year in range(2018,2025)}
        denom=float(losses[old].mean())
        rel=float(d.mean()/denom) if denom>0 else None
        positive=sum(v>0 for v in yearly.values())
        comparisons.append(dict(candidate=new,baseline=old,relative_qlike_improvement=rel,
                                mean_loss_improvement=float(d.mean()),block_95_interval=[float(lo),float(hi)],
                                positive_years=positive,yearly_loss_improvement=yearly,
                                gate_passed=bool(rel is not None and rel>=.05 and lo>0 and positive>=4)))
    return dict(status='EXPLORATORY_OPERATOR_AUTHORIZED_LIMITED_POWER',
                primary_comparison='ridge_C versus ridge_B',primary_gate_passed=comparisons[0]['gate_passed'],
                model_fits=42,evaluation_anchors=len(pred),metrics=metrics,comparisons=comparisons,
                bootstrap=dict(block_length=13,repetitions=9999,seed=20260911),
                limitations=['Discovery-contaminated 2018--2024; no untouched holdout claim',
                             'Operator accepted limited sensitivity to smaller effects',
                             'Synthetic power calibrated only a linear alternative, not GBM',
                             'Missing early crisis features; complete-case inference only',
                             'Source adjustment and vendor IV semantics not independently certified',
                             'Secondary comparisons exploratory and unadjusted for multiplicity',
                             'No portfolio mapping, executable fills, costs, or trading profitability tested'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-zip',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    if a.output_dir.exists():raise ValueError('Refusing overwrite')
    f=load_panel(a.input_zip);pred,folds=evaluate(f);report=summarize(pred)
    report['folds']=folds
    report['environment']={'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'scikit_learn':sklearn.__version__}
    report['input_sha256']=hashlib.sha256(a.input_zip.read_bytes()).hexdigest()
    report['runner_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.output_dir.mkdir(parents=True)
    pred.to_csv(a.output_dir/'options_variance_oos.csv',index=False,lineterminator='\n',float_format='%.17g')
    report['predictions_sha256']=hashlib.sha256((a.output_dir/'options_variance_oos.csv').read_bytes()).hexdigest()
    (a.output_dir/'options_variance_results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
