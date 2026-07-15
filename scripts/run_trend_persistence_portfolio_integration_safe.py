from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import scripts.run_trend_persistence_portfolio_integration as integration


_original_read_ohlcv = integration.read_ohlcv
_original_oos_probabilities = integration._oos_probabilities


def _normalize_index(obj: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    out = obj.copy()
    index = pd.to_datetime(out.index)
    if getattr(index, "tz", None) is not None:
        index = index.tz_convert("UTC").tz_localize(None)
    else:
        index = index.tz_localize(None)
    out.index = index
    return out.sort_index()


def _read_ohlcv_tz_safe(path: Path) -> pd.DataFrame:
    return _normalize_index(_original_read_ohlcv(path))


def _oos_probabilities_tz_safe(
    ohlcv: pd.DataFrame,
    candidate_name: str,
    oos_start: str,
    oos_end: str,
) -> pd.DataFrame:
    normalized = _normalize_index(ohlcv)
    result = _original_oos_probabilities(
        normalized,
        candidate_name,
        oos_start,
        oos_end,
    )
    return _normalize_index(result)


integration.read_ohlcv = _read_ohlcv_tz_safe
integration._oos_probabilities = _oos_probabilities_tz_safe


if __name__ == "__main__":
    integration.main()
