import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from research.regime_engine_ml.study import RAW,build_panel,train_mask
from research.volatility_sizing.study import add_benchmarks,scores

FEATURES={'volatility':['recent24','ewma'],'augmented':RAW+['recent24','ewma']}
MODELS=['ewma_raw','ewma_calibrated','linear_volatility','boosted_volatility',
        'linear_augmented','boosted_augmented']


def columns(model):
    return ['ewma'] if model=='ewma_calibrated' else FEATURES[model.split('_',1)[1]]


def predict(train,test,model):
    if model=='ewma_raw':return test.ewma.to_numpy()
    cols=columns(model)
    estimator=(HistGradientBoostingRegressor(max_iter=80,max_leaf_nodes=7,min_samples_leaf=50,
        l2_regularization=10.,learning_rate=.05,early_stopping=False,random_state=1729)
        if model.startswith('boosted') else make_pipeline(StandardScaler(),Ridge(alpha=10.)))
    with threadpool_limits(limits=1):
        estimator.fit(train[cols],train.log_variance)
        return estimator.predict(test[cols])


def annual(panel,asset,hours,years=range(2020,2026)):
    rows=[]
    for year in years:
        cutoff=pd.Timestamp(f'{year}-01-01',tz='UTC')
        train=panel.loc[train_mask(panel,cutoff,'log_variance')]
        test=panel.loc[(panel.index>=cutoff)&(panel.index<pd.Timestamp(f'{year+1}-01-01',tz='UTC'))]
        if len(train)<250 or test.empty:raise ValueError('Insufficient annual population')
        for model in MODELS:
            pred=predict(train,test,model)
            rows.extend(dict(asset=asset,timeframe=hours,model=model,available_at=str(t),
                prediction=float(p),actual=test.loc[t,'log_variance'],label_end=str(test.loc[t,'label_end']),
                fit_at=str(cutoff),latest_training_label_end=str(train.label_end.max()),training_rows=len(train))
                for t,p in zip(test.index,pred))
        print(f'{asset} {hours}H {year}: matched-input forecasts complete',flush=True)
    return pd.DataFrame(rows)


def compare(score_frame):
    rows=[]
    pairs=[('boosted_volatility','linear_volatility'),('boosted_augmented','linear_augmented'),
           ('linear_augmented','linear_volatility'),('boosted_augmented','boosted_volatility'),
           ('boosted_augmented','ewma_calibrated')]
    for keys,g in score_frame.groupby(['asset','timeframe','year']):
        g=g.set_index('model')
        for candidate,benchmark in pairs:
            for loss in ['log_variance_mse','variance_qlike']:
                c=float(g.loc[candidate,loss]);b=float(g.loc[benchmark,loss])
                rows.append(dict(asset=keys[0],timeframe=keys[1],year=keys[2],candidate=candidate,
                    benchmark=benchmark,metric=loss,candidate_loss=c,benchmark_loss=b,
                    relative_improvement=1-c/b if b>0 else np.nan))
    return pd.DataFrame(rows)
