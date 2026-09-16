"""No copied indicators, tuning, strategy imports, or runtime writes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.contracts import RegimeSignal

ROOT = Path(__file__).resolve().parents[2]


def verify_source_lock() -> dict:
    """Reject source drift; normalize checkout line endings only."""
    lock = json.loads(Path(__file__).with_name("source_lock.json").read_text())
    for name, expected in lock["sha256"].items():
        actual = hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if actual != expected:
            raise RuntimeError(f"Pinned Core source differs: {name}; stop research, do not edit Core.")
    return lock


def validate_frame(frame: pd.DataFrame) -> None:
    """Require explicit, clean input rather than silently changing engine inputs."""
    if frame.empty or not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("Nonempty DatetimeIndex required")
    if frame.index.hasnans or not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValueError("Timestamps must be sorted, unique and nonmissing")
    ohlc = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(ohlc).all() or (ohlc <= 0).any():
        raise ValueError("OHLC must be finite and positive")
    if ((ohlc[:, 1] < ohlc.max(axis=1)) | (ohlc[:, 2] > ohlc.min(axis=1))).any():
        raise ValueError("Inconsistent OHLC bounds")


class CoreRegimeReader:
    """Use exact defaults and methods on caller-supplied completed bars.

    Input history must match Core's input for parity. Do not shorten warmup,
    infer a timeframe, or reinterpret confidence as a probability. Invalid
    inputs raise here; Core's paper wrapper instead catches errors as UNKNOWN.
    """

    def __init__(self) -> None:
        self.source_lock = verify_source_lock()
        self._engine = BaselineRegimeEngine()

    def snapshot(self, completed_bars: pd.DataFrame) -> RegimeSignal:
        validate_frame(completed_bars)
        return self._engine.classify_bar(completed_bars, len(completed_bars) - 1)

    def history(self, completed_bars: pd.DataFrame) -> list[RegimeSignal]:
        validate_frame(completed_bars)
        return self._engine.classify_dataframe(completed_bars)
