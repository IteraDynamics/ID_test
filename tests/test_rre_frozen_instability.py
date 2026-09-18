from __future__ import annotations

import numpy as np
import pandas as pd

from research.rre_frozen_instability import (
    FROZEN_C,
    FROZEN_HORIZON_DAYS,
    FROZEN_RANDOM_STATE,
)
from research.rre_entry_deferral import FROZEN_MODEL_HORIZON_DAYS, FROZEN_QUANTILE


def test_frozen_instability_identity_matches_spec():
    assert FROZEN_HORIZON_DAYS == 7 == FROZEN_MODEL_HORIZON_DAYS
    assert FROZEN_C == 0.1
    assert FROZEN_RANDOM_STATE == 1729
    assert FROZEN_QUANTILE == 0.80


def test_fit_accepts_utc_cutoff_with_naive_panel(monkeypatch):
    from research import rre_frozen_instability as mod

    idx = pd.date_range("2019-01-01", periods=40, freq="D")
    panel = pd.DataFrame(index=idx)
    panel["label_end"] = idx + pd.Timedelta(days=8)
    panel["core_label"] = np.where(np.arange(len(idx)) % 5 < 3, "TREND_UP", "RANGE")
    for i, col in enumerate(mod.PCS):
        panel[col] = np.sin(np.arange(len(idx)) / (3.0 + i))
    for col in mod.TRAJECTORY:
        panel[col] = 0.0

    class FakeTrajectory:
        def fit(self, frame):
            return self
        def transform(self, frame):
            out = frame.copy()
            for col in mod.TRAJECTORY:
                if col not in out:
                    out[col] = 0.0
            return out

    monkeypatch.setattr(mod, "TrajectoryModel", FakeTrajectory)
    monkeypatch.setattr(mod, "episode_age", lambda s: pd.Series(np.arange(len(s), dtype=float) + 1.0, index=s.index))
    monkeypatch.setattr(mod, "transition_target", lambda s, h: pd.Series((np.arange(len(s)) % 2).astype(float), index=s.index))
    model = mod.FrozenInstabilityModel.fit(panel, pd.Timestamp("2019-02-15", tz="UTC"))
    assert model.training_cutoff == pd.Timestamp("2019-02-15")
    assert model.latest_training_label_end < pd.Timestamp("2019-02-15")
