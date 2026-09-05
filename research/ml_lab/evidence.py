"""Shared file hashing and existing NumPy/pandas JSON scalar conversion.

Callers retain their original JSON options, CSV formats and publication order.
This extraction intentionally does not rewrite historical evidence formats.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

def _sha256(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=hashlib.sha256)


def _json_default(value: Any) -> Any:
    """Convert numpy/pandas scalar values in report payloads to stdlib JSON types."""
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(value))
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


sha256_file = _sha256
json_scalar = _json_default
