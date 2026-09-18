"""Frozen causal 7-day Core-instability scorer for the RRE deferral experiment."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from research.core_regime_stability.study import AGE, episode_age, transition_target
from research.latent_state_trajectories.study import PCS, TRAJECTORY, TrajectoryModel

FROZEN_HORIZON_DAYS = 7
FROZEN_C = 0.1
FROZEN_RANDOM_STATE = 1729


class FrozenInstabilityError(ValueError):
    pass


@dataclass
class FrozenInstabilityModel:
    trajectory: TrajectoryModel
    classifier: object
    training_probabilities: np.ndarray
    training_cutoff: pd.Timestamp
    latest_training_label_end: pd.Timestamp

    @classmethod
    def fit(cls, panel: pd.DataFrame, cutoff: pd.Timestamp) -> "FrozenInstabilityModel":
        cutoff = pd.Timestamp(cutoff)
        panel_tz = getattr(panel.index, "tz", None)
        if panel_tz is None:
            if cutoff.tzinfo is not None:
                cutoff = cutoff.tz_convert("UTC").tz_localize(None)
        else:
            if cutoff.tzinfo is None:
                cutoff = cutoff.tz_localize(panel_tz)
            else:
                cutoff = cutoff.tz_convert(panel_tz)
        label_end = pd.to_datetime(panel.label_end, errors="raise")
        label_tz = getattr(label_end.dt, "tz", None)
        label_cutoff = cutoff
        if label_tz is None and cutoff.tzinfo is not None:
            label_cutoff = cutoff.tz_convert("UTC").tz_localize(None)
        elif label_tz is not None and cutoff.tzinfo is None:
            label_cutoff = cutoff.tz_localize(label_tz)
        elif label_tz is not None and cutoff.tzinfo is not None:
            label_cutoff = cutoff.tz_convert(label_tz)
        fitting = panel.loc[(panel.index < cutoff) & (label_end < label_cutoff)].copy()
        if fitting.empty:
            raise FrozenInstabilityError("EMPTY_MATURED_TRAINING_PANEL")
        trajectory = TrajectoryModel().fit(fitting)
        train = trajectory.transform(fitting)
        train["episode_age"] = episode_age(train.core_label)
        target = "transition_7d"
        train[target] = transition_target(train.core_label, FROZEN_HORIZON_DAYS)
        cols = PCS + TRAJECTORY + AGE
        tr = train.dropna(subset=[target, *cols]).copy()
        if tr.empty or tr[target].nunique() < 2:
            raise FrozenInstabilityError("INSUFFICIENT_TRAINING_CLASSES")
        pre = ColumnTransformer([
            ("core", OneHotEncoder(handle_unknown="ignore"), ["core_label"]),
            ("x", StandardScaler(), cols),
        ])
        classifier = make_pipeline(
            pre,
            LogisticRegression(C=FROZEN_C, max_iter=3000, random_state=FROZEN_RANDOM_STATE),
        )
        x = tr[["core_label", *cols]]
        classifier.fit(x, tr[target].astype(int))
        class_index = list(classifier.classes_).index(1)
        p = classifier.predict_proba(x)[:, class_index]
        if not np.all(np.isfinite(p)):
            raise FrozenInstabilityError("NONFINITE_TRAINING_PROBABILITY")
        return cls(
            trajectory=trajectory,
            classifier=classifier,
            training_probabilities=np.asarray(p, dtype=float),
            training_cutoff=cutoff,
            latest_training_label_end=pd.Timestamp(fitting.label_end.max()),
        )

    def transform_and_score(self, frame: pd.DataFrame) -> pd.Series:
        transformed = self.trajectory.transform(frame.copy())
        transformed["episode_age"] = episode_age(transformed.core_label)
        cols = PCS + TRAJECTORY + AGE
        valid = transformed[cols].notna().all(axis=1)
        out = pd.Series(np.nan, index=transformed.index, dtype=float, name="instability_7d")
        if valid.any():
            x = transformed.loc[valid, ["core_label", *cols]]
            class_index = list(self.classifier.classes_).index(1)
            out.loc[valid] = self.classifier.predict_proba(x)[:, class_index]
        return out
