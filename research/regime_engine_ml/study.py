from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from research.core_regime_reuse.adapter import CoreRegimeReader
from research.core_regime_reuse.run import completed_frame
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.crypto_reversal.experiment import HOUR

TARGETS = ['log_variance', 'downside', 'persistence']
MODELS = ['constant', 'simple_linear', 'core_label', 'split_absolute',
          'priority_relative', 'split_relative', 'full_linear', 'boosted']
RAW = ['ema_spread', 'ema_roc', 'atr_pct', 'atr_accel', 'vol_ratio']


def feature_frame(hourly, hours):
    reader = CoreRegimeReader()
    bars = completed_frame(hourly, hours, hourly.index[-1]+HOUR)
    engine = BaselineRegimeEngine()
    # Import exact existing calculations, without changing the engine object or source.
    indicators = pd.DataFrame(engine._compute_indicators(bars))
    out = indicators[['ema_spread', 'ema_roc', 'atr_pct', 'atr_accel']].copy()
    out['core_label'] = [s.label.value for s in reader.history(bars)]
    out['trend'] = np.select([(out.ema_spread > 0) & (out.ema_roc > 0),
                              (out.ema_spread < 0) & (out.ema_roc < 0)], ['UP', 'DOWN'], 'FLAT')
    # The absolute-volatility component exactly retains the baseline priority rules.
    out['absolute_vol'] = np.select([out.atr_pct > .04,
        (out.atr_pct > .025) & (out.atr_accel > .10), out.atr_pct < .012],
        ['HIGH', 'EXPANDING', 'LOW'], 'NORMAL')
    window = 90*24//hours
    past = out.atr_pct.shift(1).rolling(window, min_periods=window)
    q25, q75, q90 = past.quantile(.25), past.quantile(.75), past.quantile(.90)
    out['vol_ratio'] = out.atr_pct / past.median()
    out['relative_vol'] = np.select([out.atr_pct > q90,
        (out.atr_pct > q75) & (out.atr_accel > .10), out.atr_pct < q25],
        ['HIGH', 'EXPANDING', 'LOW'], 'NORMAL')
    out['priority_relative'] = np.where(out.relative_vol == 'NORMAL', out.trend, out.relative_vol)
    out.index = out.index + hours*HOUR  # completed bar information availability
    return out


def build_panel(hourly, hours):
    features = feature_frame(hourly, hours)
    grid = hourly.reindex(pd.date_range(hourly.index[0], hourly.index[-1], freq='h'))
    # At time t, close[t-1] is the most recent completed hourly close.
    closing = grid.close.copy()
    closing.index = closing.index + HOUR
    log_returns = np.log(closing/closing.shift(1))
    future = pd.concat([log_returns.shift(-k) for k in range(1, 25)], axis=1)
    future_prices = pd.concat([closing.shift(-k)/closing-1 for k in range(1, 25)], axis=1)
    labels = pd.DataFrame(index=closing.index)
    labels['log_variance'] = np.log(future.pow(2).sum(axis=1, min_count=24).clip(lower=1e-12))
    labels['downside'] = (future_prices.min(axis=1) <= -.03).astype(float)
    labels.loc[future.isna().any(axis=1), 'downside'] = np.nan
    labels['future_return'] = closing.shift(-24)/closing-1
    # Reject recent gaps causally; future incomplete labels are excluded only from scoring/training.
    recent_complete = grid.close.notna().rolling(max(240, hours*60)).sum() == max(240, hours*60)
    recent_complete.index = recent_complete.index+HOUR
    panel = features.join(labels).join(recent_complete.rename('past_complete'))
    panel = panel.loc[(panel.index.hour == 0) & panel.past_complete.fillna(False)].copy()
    direction = panel.trend.map({'UP':1., 'DOWN':-1., 'FLAT':0.})
    panel['persistence'] = np.where(direction == 0, np.nan, (direction*panel.future_return > 0).astype(float))
    panel.loc[panel.future_return.isna(), 'persistence'] = np.nan
    panel['label_end'] = panel.index+24*HOUR
    return panel.replace([np.inf, -np.inf], np.nan).dropna(subset=RAW)


def train_mask(panel, cutoff, target):
    return (panel.index < cutoff) & (panel.label_end < cutoff) & panel[target].notna()


def matrix(panel, model):
    if model == 'simple_linear':
        return panel[['ema_spread', 'atr_pct']]
    categorical = {'core_label':['core_label'], 'split_absolute':['trend','absolute_vol'],
                   'priority_relative':['priority_relative'], 'split_relative':['trend','relative_vol']}
    if model in categorical:
        # Fixed vocabularies avoid deriving feature schemas from the evaluation period.
        vocab = {'core_label':['TREND_UP','TREND_DOWN','RANGE','VOL_COMPRESSION','VOL_EXPANSION','HIGH_VOL','UNKNOWN'],
                 'trend':['UP','DOWN','FLAT'], 'absolute_vol':['HIGH','EXPANDING','LOW','NORMAL'],
                 'relative_vol':['HIGH','EXPANDING','LOW','NORMAL'],
                 'priority_relative':['HIGH','EXPANDING','LOW','UP','DOWN','FLAT']}
        return pd.DataFrame({f'{col}_{value}':(panel[col]==value).astype(float)
                             for col in categorical[model] for value in vocab[col]}, index=panel.index)
    return panel[RAW]


def predict_fold(train, test, model, target):
    y = train[target]
    if model == 'constant':
        pred = np.full(len(test), y.mean())
    else:
        x, xt = matrix(train, model), matrix(test, model)
        if model == 'boosted':
            estimator = HistGradientBoostingRegressor(max_iter=80, max_leaf_nodes=7,
                min_samples_leaf=50, l2_regularization=10., learning_rate=.05,
                early_stopping=False, random_state=1729)
        else:
            estimator = make_pipeline(StandardScaler(), Ridge(alpha=10.))
        with threadpool_limits(limits=1):
            estimator.fit(x, y)
            pred = estimator.predict(xt)
    return np.clip(pred, 0., 1.) if target != 'log_variance' else pred


def forecast(panel, asset, hours, years=range(2020, 2026)):
    rows = []
    for year in years:
        cutoff = pd.Timestamp(f'{year}-01-01', tz='UTC')
        finish = pd.Timestamp(f'{year+1}-01-01', tz='UTC')
        test = panel.loc[(panel.index >= cutoff) & (panel.index < finish)]
        if test.empty:
            continue
        for target in TARGETS:
            train = panel.loc[train_mask(panel, cutoff, target)]
            if len(train) < 250:
                raise ValueError(f'Too few matured training rows: {asset}/{hours}/{year}/{target}')
            assert train.label_end.max() < cutoff
            for model in MODELS:
                pred = predict_fold(train, test, model, target)
                rows.extend(dict(asset=asset, timeframe=hours, model=model, target=target,
                    available_at=str(t), label_end=str(test.loc[t,'label_end']), actual=test.loc[t,target],
                    prediction=float(p), training_mean=float(train[target].mean()),
                    fit_at=str(cutoff), latest_training_label_end=str(train.label_end.max()), training_rows=len(train))
                    for t,p in zip(test.index,pred))
        print(f'{asset} {hours}H: {year} predictions complete', flush=True)
    return pd.DataFrame(rows)


def score(predictions):
    rows = []
    for keys, g in predictions.groupby(['asset','timeframe','target','model']):
        asset, timeframe, target, model = keys
        g = g.dropna(subset=['actual'])
        for year in ['all']+list(range(2020,2026)):
            s = g if year == 'all' else g.loc[pd.to_datetime(g.available_at).dt.year==year]
            if s.empty:
                continue
            loss = float(np.mean((s.prediction-s.actual)**2))
            baseline = float(np.mean((s.training_mean-s.actual)**2))
            rows.append(dict(asset=asset,timeframe=timeframe,target=target,model=model,year=year,
                observations=len(s),loss=loss,constant_loss=baseline,
                skill_vs_constant=1-loss/baseline if baseline>0 else None,
                mean_prediction=float(s.prediction.mean()),mean_actual=float(s.actual.mean()),
                metric='log_variance_MSE' if target=='log_variance' else 'Brier'))
    return pd.DataFrame(rows)
