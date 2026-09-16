from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from research.regime_engine_ml.study import build_panel, train_mask, predict_fold
from research.crypto_reversal.experiment import HOUR

MODELS = ['recent24_raw','ewma_raw','recent24_calibrated','ewma_calibrated',
          'full_linear','boosted']
DAILY_RISK = .40/np.sqrt(365.)


def add_benchmarks(hourly, panel):
    grid = hourly.reindex(pd.date_range(hourly.index[0],hourly.index[-1],freq='h'))
    r = np.log(grid.close/grid.close.shift(1))
    rv = r.pow(2).rolling(24,min_periods=24).sum().clip(lower=1e-12)
    ewma = (24*r.pow(2).ewm(halflife=24,adjust=False,min_periods=240).mean()).clip(lower=1e-12)
    predictors = pd.DataFrame({'recent24':np.log(rv),'ewma':np.log(ewma)})
    predictors.index += HOUR
    return panel.join(predictors).dropna(subset=['recent24','ewma'])


def annual_forecasts(hourly,asset,hours):
    panel = add_benchmarks(hourly,build_panel(hourly,hours))
    rows=[]
    for year in range(2020,2026):
        cutoff=pd.Timestamp(f'{year}-01-01',tz='UTC')
        train=panel.loc[train_mask(panel,cutoff,'log_variance')]
        test=panel.loc[(panel.index>=cutoff)&(panel.index<pd.Timestamp(f'{year+1}-01-01',tz='UTC'))]
        if len(train)<250 or test.empty:
            raise ValueError('Insufficient annual training/evaluation population')
        for model in MODELS:
            if model.endswith('_raw'):
                prediction=test[model.removesuffix('_raw')].to_numpy()
            elif model.endswith('_calibrated'):
                col=model.removesuffix('_calibrated')
                estimator=make_pipeline(StandardScaler(),Ridge(alpha=10.))
                estimator.fit(train[[col]],train.log_variance)
                prediction=estimator.predict(test[[col]])
            else:
                prediction=predict_fold(train,test,model,'log_variance')
            rows.extend(dict(asset=asset,timeframe=hours,model=model,available_at=str(t),
                prediction=float(p),actual=test.loc[t,'log_variance'],fit_at=str(cutoff),
                latest_training_label_end=str(train.label_end.max()),training_rows=len(train))
                for t,p in zip(test.index,prediction))
        print(f'{asset} {hours}H {year}: volatility forecasts complete',flush=True)
    return pd.DataFrame(rows)


def scores(predictions):
    rows=[]
    for keys,g in predictions.groupby(['asset','timeframe','model']):
        for year in ['all']+list(range(2020,2026)):
            s=g if year=='all' else g.loc[pd.to_datetime(g.available_at).dt.year==year]
            s=s.dropna(subset=['actual'])
            if s.empty:continue
            err=s.actual-s.prediction
            rows.append(dict(asset=keys[0],timeframe=keys[1],model=keys[2],year=year,
                observations=len(s),log_variance_mse=float(np.mean(err**2)),
                variance_qlike=float(np.mean(np.exp(err)-err-1))))
    return pd.DataFrame(rows)


def size_at(predictions,decision):
    i=predictions.index.searchsorted(decision,side='right')-1
    if i<0 or decision-predictions.index[i]>=24*HOUR:
        return 0.,None
    row=predictions.iloc[i]
    if pd.Timestamp(row.fit_at)>predictions.index[i] or pd.Timestamp(row.latest_training_label_end)>=pd.Timestamp(row.fit_at):
        raise ValueError('Training timing violation')
    if not np.isfinite(row.prediction):raise ValueError('Invalid variance prediction')
    # Square root of exp(predicted log variance); not claimed unbiased expected volatility.
    weight=float(np.clip(DAILY_RISK/np.exp(row.prediction/2),0.,1.))
    return weight,str(predictions.index[i])
