"""Completed UTC bars -> 15 causal features and unchanged expert targets."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.fresh_crypto.data import ASSETS, WARMUP
from research.fresh_crypto.engine import size
from .design import FEATURES, PROFILES


class Panel:
    def __init__(self, frames):
        self.dates = frames["BTC"].index
        if not self.dates.equals(frames["ETH"].index):
            raise ValueError("BTC and ETH must share the complete UTC calendar")
        self.opens = np.column_stack([frames[a].open for a in ASSETS])
        self.closes = np.column_stack([frames[a].close for a in ASSETS])
        self.volume = np.column_stack([frames[a].volume for a in ASSETS])
        n = len(self.dates)
        self.x = np.full((n, len(FEATURES)), np.nan)
        self.cov = np.full((n, 2, 2), np.nan)
        self.trend = {p: np.full((n, 2), np.nan) for p in PROFILES}
        self.allocation = {p: np.full((n, 2), np.nan) for p in PROFILES}
        returns = self.closes[1:] / self.closes[:-1] - 1
        for t in range(WARMUP, n):
            recent, fast = returns[t-60:t], returns[t-20:t]
            vol = np.maximum(recent.std(axis=0, ddof=1), 1e-8)
            fast_vol = np.maximum(fast.std(axis=0, ddof=1), 1e-8)
            moves = [self.closes[t]/self.closes[t-w]-1 for w in (90, 180, 365)]
            strength = np.column_stack([move/(vol*np.sqrt(w)) for move, w in zip(moves, (90, 180, 365))])
            votes = np.mean([move > 0 for move in moves], axis=0)
            covariance = np.cov(recent, rowvar=False, ddof=1)
            self.cov[t] = 365*(.9*covariance+.1*np.diag(np.diag(covariance)))
            corr = covariance[0, 1]/np.prod(vol) if (recent.std(axis=0, ddof=1)>1e-8).all() else 0.
            move14 = self.closes[t]/self.closes[t-14]-1
            downside = np.sum(np.minimum(recent, 0.)**2, axis=0)/np.maximum(np.sum(recent**2, axis=0), 1e-16)
            volume_ratio = self.volume[t-19:t+1].mean(axis=0)/np.maximum(self.volume[t-59:t+1].mean(axis=0), 1e-12)-1
            self.x[t] = np.r_[strength.ravel(),
                               np.mean(move14/(fast_vol*np.sqrt(14))-strength[:, 0]),
                               votes.mean(), np.mean(fast_vol/vol), downside.mean(),
                               np.mean(self.closes[t]/self.closes[t-59:t+1].max(axis=0)-1),
                               corr, (move14[1]-move14[0])/max(np.std(recent[:, 1]-recent[:, 0], ddof=1)*np.sqrt(14), 1e-8),
                               volume_ratio.mean(), np.mean(vol)*np.sqrt(365)]
            for profile in PROFILES:
                self.trend[profile][t] = size(votes*.5, self.cov[t], profile)
                self.allocation[profile][t] = size(np.array([.5, .5]), self.cov[t], profile)
        if not np.isfinite(self.x[WARMUP:]).all():
            raise ValueError("Nonfinite causal features; no imputation is permitted")

    def frame(self):
        result = pd.DataFrame(self.x[WARMUP:], columns=FEATURES)
        result.insert(0, "signal_index", np.arange(WARMUP, len(self.dates)))
        result.insert(1, "signal_bar_start", self.dates[WARMUP:].astype(str))
        result.insert(2, "available_time", (self.dates[WARMUP:]+pd.Timedelta(days=1)).astype(str))
        return result
