from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

from research.crypto_reversal.experiment import HOUR
from research.multidimensional_regimes.study import (
    FEATURES,
    TARGETS,
    MIN_SUPPORT,
    panel_from_hourly,
    state_forecast,
)

KS = (2, 3, 4, 6, 8, 10, 12)


def transition_summary(frame: pd.DataFrame, state: str) -> dict:
    previous = frame[state].shift(1)
    contiguous = frame.index.to_series().diff() == 24 * HOUR
    pairs = pd.DataFrame({'from_state': previous[contiguous], 'to_state': frame.loc[contiguous, state]}).dropna()
    if pairs.empty:
        return dict(transitions=0, self_probability=None)
    return dict(
        transitions=len(pairs),
        self_probability=float((pairs.from_state == pairs.to_state).mean()),
    )


def episode_lengths(frame: pd.DataFrame, state: str) -> list[int]:
    values = frame[state].astype(str)
    contiguous = frame.index.to_series().diff().eq(24 * HOUR)
    group_start = (~contiguous) | values.ne(values.shift(1))
    ids = group_start.cumsum()
    return [int(v) for v in frame.groupby(ids).size().to_list()]


class CompressionModel:
    def fit(self, train: pd.DataFrame) -> 'CompressionModel':
        if len(train) < 250 or not np.isfinite(train[FEATURES].to_numpy()).all():
            raise ValueError('Need 250 finite training snapshots')
        self.lower = train[FEATURES].quantile(.01)
        self.upper = train[FEATURES].quantile(.99)
        clipped = train[FEATURES].clip(self.lower, self.upper, axis=1)
        self.scaler = StandardScaler().fit(clipped)
        x = self.scaler.transform(clipped)
        with threadpool_limits(limits=1):
            self.pca = PCA(n_components=len(FEATURES), svd_solver='full').fit(x)
        z = self.pca.transform(x)
        self.clusters = {}
        with threadpool_limits(limits=1):
            for k in KS:
                self.clusters[k] = KMeans(n_clusters=k, n_init=10, random_state=1729).fit(z)
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not np.isfinite(frame[FEATURES].to_numpy()).all():
            raise ValueError('Nonfinite state features')
        out = frame.copy()
        clipped = frame[FEATURES].clip(self.lower, self.upper, axis=1)
        z = self.pca.transform(self.scaler.transform(clipped))
        for i in range(len(FEATURES)):
            out[f'pc{i+1}'] = z[:, i]
        with threadpool_limits(limits=1):
            for k, model in self.clusters.items():
                out[f'k{k}'] = [f'K{k}_{i}' for i in model.predict(z)]
        return out

    def metadata(self) -> dict:
        return dict(
            clip_low=self.lower.to_dict(),
            clip_high=self.upper.to_dict(),
            scaler_mean=self.scaler.mean_.tolist(),
            scaler_scale=self.scaler.scale_.tolist(),
            pca_components=self.pca.components_.tolist(),
            pca_explained_variance_ratio=self.pca.explained_variance_ratio_.tolist(),
            cluster_centers_pca={str(k): m.cluster_centers_.tolist() for k, m in self.clusters.items()},
        )


def _ridge_prediction(train: pd.DataFrame, test: pd.DataFrame, columns: list[str], target: str) -> np.ndarray:
    estimator = make_pipeline(StandardScaler(), Ridge(alpha=10.))
    estimator.fit(train[columns], train[target])
    return estimator.predict(test[columns])


def _core_plus_pc_prediction(train: pd.DataFrame, test: pd.DataFrame, pc_columns: list[str], target: str) -> np.ndarray:
    pre = ColumnTransformer([
        ('core', OneHotEncoder(handle_unknown='ignore'), ['core_label']),
        ('pc', StandardScaler(), pc_columns),
    ])
    estimator = make_pipeline(pre, Ridge(alpha=10.))
    estimator.fit(train[['core_label', *pc_columns]], train[target])
    return estimator.predict(test[['core_label', *pc_columns]])


def evaluate(panel: pd.DataFrame, asset: str, hours: int, years=range(2020, 2026)) -> dict:
    outputs = {k: [] for k in ['scores', 'occupancy', 'persistence', 'cross_tabs', 'outcomes', 'fits']}
    for year in years:
        cutoff = pd.Timestamp(f'{year}-01-01', tz='UTC')
        fitting = panel.loc[(panel.index < cutoff) & (panel.label_end < cutoff)]
        test = panel.loc[(panel.index >= cutoff) & (panel.index < pd.Timestamp(f'{year+1}-01-01', tz='UTC'))]
        if test.empty:
            raise ValueError(f'No evaluation rows for {asset}/{hours}/{year}')
        model = CompressionModel().fit(fitting)
        train, test = model.transform(fitting), model.transform(test)
        if not (train.label_end.max() < cutoff):
            raise ValueError('Training maturity boundary violation')
        keys = dict(asset=asset, timeframe=hours, year=year)
        outputs['fits'].append(dict(
            **keys,
            fit_at=str(cutoff),
            latest_training_label_end=str(train.label_end.max()),
            training_rows=len(train),
            **model.metadata(),
        ))

        for k in KS:
            state = f'k{k}'
            counts = train[state].value_counts()
            for label, group in test.groupby(state):
                n_train = int(counts.get(label, 0))
                outputs['occupancy'].append(dict(
                    **keys,
                    representation=state,
                    state=label,
                    training_count=n_train,
                    evaluation_count=len(group),
                    fraction=len(group)/len(test),
                    sparse_training=n_train < MIN_SUPPORT,
                ))
                for target in TARGETS:
                    values = group[target].dropna()
                    outputs['outcomes'].append(dict(
                        **keys,
                        representation=state,
                        state=label,
                        target=target,
                        observations=len(values),
                        mean=values.mean(),
                        median=values.median(),
                        q10=values.quantile(.1),
                        q90=values.quantile(.9),
                    ))
            lengths = episode_lengths(test, state)
            persistence = transition_summary(test, state)
            outputs['persistence'].append(dict(
                **keys,
                representation=state,
                largest_state_fraction=float(test[state].value_counts(normalize=True).max()),
                sparse_eval_fraction=float(test[state].map(lambda s: counts.get(s, 0) < MIN_SUPPORT).mean()),
                episode_count=len(lengths),
                episode_mean=float(np.mean(lengths)) if lengths else None,
                episode_median=float(np.median(lengths)) if lengths else None,
                episode_q90=float(np.quantile(lengths, .9)) if lengths else None,
                **persistence,
            ))
            tab = pd.crosstab(test.core_label, test[state], normalize='index')
            for core_label, row in tab.iterrows():
                for label, fraction in row.items():
                    outputs['cross_tabs'].append(dict(
                        **keys,
                        representation=state,
                        core_label=core_label,
                        state=label,
                        conditional_fraction=float(fraction),
                    ))

        for target in TARGETS:
            tr = train.dropna(subset=[target])
            valid = test[target].notna()
            if len(tr) < 250:
                raise ValueError('Insufficient matured outcomes')
            prior = float(tr[target].mean())
            actual = test.loc[valid, target].to_numpy()
            base = float(np.mean((prior - actual) ** 2)) if valid.any() else None
            predictions: dict[str, np.ndarray] = {
                'constant': np.full(len(test), prior),
                'core_label': state_forecast(tr, test, 'core_label', target),
            }
            for n in range(1, len(FEATURES)+1):
                pcs = [f'pc{i}' for i in range(1, n+1)]
                predictions[f'pca_{n}'] = _ridge_prediction(tr, test, pcs, target)
                predictions[f'core_plus_pca_{n}'] = _core_plus_pc_prediction(tr, test, pcs, target)
            for k in KS:
                predictions[f'k{k}'] = state_forecast(tr, test, f'k{k}', target)

            core_loss = None
            for name, pred in predictions.items():
                if target in ('downside', 'future_efficiency'):
                    pred = np.clip(pred, 0, 1)
                loss = float(np.mean((pred[valid] - actual) ** 2)) if valid.any() else None
                if name == 'core_label':
                    core_loss = loss
                outputs['scores'].append(dict(
                    **keys,
                    representation=name,
                    target=target,
                    observations=int(valid.sum()),
                    mse=loss,
                    constant_mse=base,
                    skill_vs_constant=1-loss/base if base and loss is not None else None,
                    skill_vs_core=(1-loss/core_loss) if core_loss and loss is not None else None,
                ))
        print(f'{asset} {hours}H {year}: compression study complete', flush=True)
    return outputs


__all__ = ['evaluate', 'panel_from_hourly', 'CompressionModel', 'KS']
