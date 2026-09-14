"""Quarterly expanding fits, strict label maturity, fixed model/hurdle choices."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits

from .design import BOOSTED, EVALUATION_START, FEATURES, MIN_TRAIN, MODELS, PROFILES, RIDGE


def first_signal(panel):
    first = int(panel.dates.searchsorted(pd.Timestamp(EVALUATION_START, tz="UTC")))-2
    if first<365 or first+3>=len(panel.dates):
        raise ValueError("Need pre-2020 training history and 2020+ development observations")
    return first


def decision_indices(panel, first):
    return [t for t in range(first, len(panel.dates)-3) if t==first or panel.dates[t+2].weekday()==0]


def eligible_labels(labels, cutoff, minimum=MIN_TRAIN):
    ends = pd.to_datetime(labels.label_available, utc=True)
    available = pd.to_datetime(labels.feature_available, utc=True)
    selected = labels.loc[(ends<cutoff) & (available<cutoff)].copy()
    if len(selected)<minimum:
        raise ValueError(f"Only {len(selected)} matured training labels at {cutoff}; need {minimum}")
    if not (pd.to_datetime(selected.label_available, utc=True)<cutoff).all():
        raise ValueError("Training label crosses fit boundary")
    return selected


class Transform:
    def fit(self, x):
        if not np.isfinite(x).all():
            raise ValueError("Nonfinite training features")
        self.lower, self.upper = np.quantile(x, [.01, .99], axis=0)
        clipped = np.clip(x, self.lower, self.upper)
        self.mean, self.scale = clipped.mean(axis=0), np.maximum(clipped.std(axis=0), 1e-8)
        return self

    def apply(self, x):
        if not np.isfinite(x).all():
            raise ValueError("Nonfinite prediction features")
        return (np.clip(x, self.lower, self.upper)-self.mean)/self.scale

    def record(self):
        return {key: getattr(self, key).tolist() for key in ("lower", "upper", "mean", "scale")}


def fit_predict(kind, x, y, future):
    if kind=="constant":
        return np.full(len(future), y.mean()), {"constant": float(y.mean())}
    transform = Transform().fit(x)
    model = Ridge(**RIDGE) if kind=="ridge" else HistGradientBoostingRegressor(**BOOSTED) if kind=="boosted" else None
    if model is None:
        raise ValueError(f"Unknown model {kind}")
    # Fixed thread count avoids oversubscription and makes within-run replay explicit.
    with threadpool_limits(limits=1):
        model.fit(transform.apply(x), y)
        predictions = model.predict(transform.apply(future))
    record = dict(preprocessing=transform.record())
    if kind=="ridge":
        record.update(coefficients=model.coef_.tolist(), intercept=float(model.intercept_))
    return predictions, record


def walk_forward(panel, labels, first=None):
    first = first_signal(panel) if first is None else first
    decisions = decision_indices(panel, first)
    quarters = {}
    for t in decisions:
        quarter = str(panel.dates[t+2].tz_localize(None).to_period("Q"))
        quarters.setdefault(quarter, []).append(t)
    predictions, fits = [], []
    for profile in PROFILES:
        profile_labels = labels[labels.profile==profile]
        for quarter, times in quarters.items():
            cutoff = panel.dates[times[0]]+pd.Timedelta(days=1)
            train = eligible_labels(profile_labels, cutoff)
            indices = train.signal_index.to_numpy(dtype=int)
            x, y, future = panel.x[indices], train.target.to_numpy(), panel.x[times]
            training_hash = hashlib.sha256(np.c_[indices, x, y].astype("<f8").tobytes()).hexdigest()
            for kind in MODELS:
                prediction, details = fit_predict(kind, x, y, future)
                replay, replay_details = fit_predict(kind, x, y, future)
                if not np.array_equal(prediction, replay) or details!=replay_details:
                    raise ValueError(f"Model replay failed: {kind}/{profile}/{quarter}")
                fit_id = f"{kind}_vol{int(profile*100)}_{quarter}"
                fits.append(dict(fit_id=fit_id, profile=profile, model=kind, quarter=quarter,
                                 fit_time=str(cutoff), training_rows=len(train),
                                 first_training_signal=str(panel.dates[indices.min()]),
                                 last_training_signal=str(panel.dates[indices.max()]),
                                 latest_label_available=str(pd.to_datetime(train.label_available,utc=True).max()),
                                 training_sha256=training_hash, features=list(FEATURES),
                                 implementation_details=details, replay_exact=True))
                for t, value in zip(times, prediction):
                    predictions.append(dict(profile=profile, model=kind, fit_id=fit_id, signal_index=t,
                                            signal_bar_start=str(panel.dates[t]),
                                            feature_available=str(panel.dates[t]+pd.Timedelta(days=1)),
                                            base_fill_time=str(panel.dates[t]+pd.Timedelta(days=2)),
                                            fit_time=str(cutoff), predicted_relative_log_return=float(value)))
            print(f"vol{int(profile*100)} {quarter}: {len(train)} matured labels, three predictors replayed", flush=True)
    return pd.DataFrame(predictions), fits
