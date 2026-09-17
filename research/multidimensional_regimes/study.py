from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from research.regime_engine_ml.study import build_panel
from research.crypto_reversal.experiment import HOUR

FEATURES = ['strength', 'momentum', 'log_atr', 'atr_accel', 'efficiency']
TARGETS = ['future_return', 'log_variance', 'downside', 'future_efficiency']
STATES = ['core_label', 'rule_joint', 'learned', 'volatility']
MIN_SUPPORT = 20


def panel_from_hourly(hourly: pd.DataFrame, hours: int) -> pd.DataFrame:
    panel = build_panel(hourly, hours)
    close = hourly.close.reindex(pd.date_range(hourly.index[0], hourly.index[-1], freq='h'))
    close.index += HOUR
    r = np.log(close / close.shift(1))
    path = r.abs().rolling(24, min_periods=24).sum()
    efficiency = (np.log(close / close.shift(24)).abs() / path.replace(0, np.nan)).clip(0, 1)
    efficiency.loc[path == 0] = 0.
    future = pd.concat([r.shift(-k) for k in range(1, 25)], axis=1)
    future_path = future.abs().sum(axis=1, min_count=24)
    future_efficiency = (future.sum(axis=1, min_count=24).abs() / future_path.replace(0, np.nan)).clip(0, 1)
    future_efficiency.loc[future_path == 0] = 0.
    panel['strength'] = panel.ema_spread / panel.atr_pct
    panel['momentum'] = panel.ema_roc / panel.atr_pct
    panel['log_atr'] = np.log(panel.atr_pct)
    panel['efficiency'] = efficiency.reindex(panel.index)
    panel['future_efficiency'] = future_efficiency.reindex(panel.index)
    # All outcome comparisons use the same complete future window. State rows
    # remain present even when future observations are missing.
    panel.loc[panel.future_efficiency.isna(), TARGETS] = np.nan
    return panel.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURES)


class StateModel:
    """Fixed rule axes plus one six-cluster, training-only alternative."""

    def fit(self, train: pd.DataFrame) -> 'StateModel':
        if len(train) < 250 or not np.isfinite(train[FEATURES].to_numpy()).all():
            raise ValueError('Need 250 finite training snapshots')
        self.vol_cutoffs = train.log_atr.quantile([1/3, 2/3]).to_numpy()
        self.lower = train[FEATURES].quantile(.01)
        self.upper = train[FEATURES].quantile(.99)
        self.scaler = StandardScaler().fit(train[FEATURES].clip(self.lower, self.upper, axis=1))
        x = self.scaler.transform(train[FEATURES].clip(self.lower, self.upper, axis=1))
        with threadpool_limits(limits=1):
            self.cluster = KMeans(n_clusters=6, n_init=10, random_state=1729).fit(x)
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not np.isfinite(frame[FEATURES].to_numpy()).all():
            raise ValueError('Nonfinite state features')
        out = frame.copy()
        out['direction'] = np.select([(out.strength > .25) & (out.momentum > 0),
                                      (out.strength < -.25) & (out.momentum < 0)], ['UP', 'DOWN'], 'NEUTRAL')
        out['volatility'] = np.select([out.log_atr < self.vol_cutoffs[0],
                                       out.log_atr > self.vol_cutoffs[1]], ['LOW', 'HIGH'], 'NORMAL')
        out['vol_change'] = np.select([out.atr_accel > .10, out.atr_accel < -.10], ['RISING', 'FALLING'], 'STABLE')
        out['path_structure'] = np.select([out.efficiency < .30, out.efficiency >= .60], ['CHOPPY', 'PERSISTENT'], 'MIXED')
        axes = ['direction', 'volatility', 'vol_change', 'path_structure']
        out['rule_joint'] = out[axes].agg('|'.join, axis=1)
        x = self.scaler.transform(frame[FEATURES].clip(self.lower, self.upper, axis=1))
        with threadpool_limits(limits=1):
            out['learned'] = ['K'+str(i) for i in self.cluster.predict(x)]
        return out

    def metadata(self) -> dict:
        return dict(vol_cutoffs=self.vol_cutoffs.tolist(), clip_low=self.lower.to_dict(),
                    clip_high=self.upper.to_dict(), scaler_mean=self.scaler.mean_.tolist(),
                    scaler_scale=self.scaler.scale_.tolist(),
                    cluster_centers_scaled=self.cluster.cluster_centers_.tolist())


def state_forecast(train: pd.DataFrame, test: pd.DataFrame, state: str, target: str) -> np.ndarray:
    """Same shrinkage decoder for every partition, with explicit sparse fallback."""
    means = train.groupby(state)[target].agg(['count', 'sum'])
    prior = float(train[target].mean())
    estimate = (means['sum'] + MIN_SUPPORT*prior)/(means['count']+MIN_SUPPORT)
    estimate.loc[means['count'] < MIN_SUPPORT] = prior
    return test[state].map(estimate).fillna(prior).to_numpy()


def transition_rows(frame: pd.DataFrame, state: str) -> list[dict]:
    previous = frame[state].shift(1)
    contiguous = frame.index.to_series().diff() == 24*HOUR
    pairs = pd.DataFrame({'from_state': previous[contiguous], 'to_state': frame.loc[contiguous, state]})
    rows = []
    for (a, b), n in pairs.groupby(['from_state', 'to_state']).size().items():
        total = int((pairs.from_state == a).sum())
        rows.append(dict(from_state=a, to_state=b, transitions=int(n), probability=n/total))
    return rows


def evaluate(panel: pd.DataFrame, asset: str, hours: int, years=range(2020, 2026)) -> dict:
    outputs = {k: [] for k in ['states', 'occupancy', 'transitions', 'episodes', 'outcomes', 'scores', 'forecasts', 'fits']}
    for year in years:
        cutoff = pd.Timestamp(f'{year}-01-01', tz='UTC')
        # Unsupervised fitting still uses only pre-cutoff features; same conservative
        # one-day maturity boundary for state fitting and supervised outcome decoding.
        fitting = panel.loc[(panel.index < cutoff) & (panel.label_end < cutoff)]
        test = panel.loc[(panel.index >= cutoff) & (panel.index < pd.Timestamp(f'{year+1}-01-01', tz='UTC'))]
        if test.empty:
            raise ValueError(f'No evaluation rows for {asset}/{hours}/{year}')
        model = StateModel().fit(fitting)
        train, test = model.transform(fitting), model.transform(test)
        keys = dict(asset=asset, timeframe=hours, year=year)
        outputs['fits'].append(dict(**keys, fit_at=str(cutoff), latest_training_label_end=str(train.label_end.max()),
                                   training_rows=len(train), **model.metadata()))
        for t, row in test.iterrows():
            outputs['states'].append(dict(**keys, available_at=str(t), **{k: row[k] for k in
                FEATURES + STATES + ['direction', 'vol_change', 'path_structure']}))
        for state in STATES:
            counts = train[state].value_counts()
            outputs['transitions'].extend(dict(**keys, representation=state, **r) for r in transition_rows(test, state))
            for label, group in test.groupby(state):
                n_train = int(counts.get(label, 0))
                outputs['occupancy'].append(dict(**keys, representation=state, state=label,
                    training_count=n_train, evaluation_count=len(group), fraction=len(group)/len(test),
                    sparse_training=n_train < MIN_SUPPORT))
                # Representative snapshot nearest the training state's feature median;
                # selection never examines future return or drawdown.
                center = train.loc[train[state] == label, FEATURES].median() if n_train else train[FEATURES].median()
                distance = ((group[FEATURES]-center)/model.scaler.scale_).pow(2).sum(axis=1)
                chosen = distance.idxmin()
                outputs['episodes'].append(dict(**keys, representation=state, state=label,
                    representative_at=str(chosen), training_count=n_train,
                    **{k: group.loc[chosen, k] for k in FEATURES}))
                for target in TARGETS:
                    values = group[target].dropna()
                    outputs['outcomes'].append(dict(**keys, representation=state, state=label, target=target,
                        observations=len(values), mean=values.mean(), median=values.median(),
                        q10=values.quantile(.1), q90=values.quantile(.9)))
        for target in TARGETS:
            tr = train.dropna(subset=[target])
            if len(tr) < 250:
                raise ValueError('Insufficient matured outcomes')
            valid = test[target].notna()
            prior = float(tr[target].mean())
            predictions = {'constant': np.full(len(test), prior)}
            for state in STATES:
                predictions[state] = state_forecast(tr, test, state, target)
            for name, columns in [('simple_continuous', ['strength', 'log_atr']), ('all_continuous', FEATURES)]:
                estimator = make_pipeline(StandardScaler(), Ridge(alpha=10.))
                estimator.fit(tr[columns], tr[target])
                predictions[name] = estimator.predict(test[columns])
            for name, pred in predictions.items():
                if target in ('downside', 'future_efficiency'):
                    pred = np.clip(pred, 0, 1)
                loss = float(np.mean((pred[valid]-test.loc[valid, target].to_numpy())**2)) if valid.any() else None
                base = float(np.mean((prior-test.loc[valid, target])**2)) if valid.any() else None
                outputs['scores'].append(dict(**keys, representation=name, target=target,
                    observations=int(valid.sum()), mse=loss, constant_mse=base,
                    skill_vs_constant=1-loss/base if base and loss is not None else None))
                for i, (t, row) in enumerate(test.iterrows()):
                    outputs['forecasts'].append(dict(**keys, representation=name, target=target,
                        available_at=str(t), label_end=str(row.label_end), actual=row[target], prediction=float(pred[i]),
                        fit_at=str(cutoff), latest_training_label_end=str(tr.label_end.max())))
        print(f'{asset} {hours}H {year}: state study complete', flush=True)
    return outputs
