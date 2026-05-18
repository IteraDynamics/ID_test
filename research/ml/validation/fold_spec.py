"""Walk-forward fold definitions and split logic.

Each FoldSpec defines one expanding-window fold:
  train_start → train_end : calibrator is trained on this period only
  test_start  → test_end  : calibrator is evaluated on this strictly future period

No-leakage guarantee: test_start is always strictly after train_end.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class FoldSpec:
    """One walk-forward fold: expanding training window + held-out test window."""

    fold_id: int
    train_start: str  # YYYY-MM-DD
    train_end: str
    test_start: str
    test_end: str

    def __post_init__(self) -> None:
        te = date.fromisoformat(self.train_end)
        ts = date.fromisoformat(self.test_start)
        if ts <= te:
            raise ValueError(
                f"Fold {self.fold_id}: test_start ({self.test_start}) must be "
                f"strictly after train_end ({self.train_end})"
            )

    def __str__(self) -> str:
        return (
            f"Fold {self.fold_id}: "
            f"train={self.train_start}→{self.train_end}  "
            f"test={self.test_start}→{self.test_end}"
        )

    def to_dict(self) -> dict:
        return {
            "fold_id": self.fold_id,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
        }


def build_annual_folds(
    data_start: str,
    data_end: str,
    train_min_years: int = 2,
    test_years: int = 1,
) -> list[FoldSpec]:
    """Build expanding-window annual folds.

    The training window always starts at data_start and expands by
    test_years each fold.  The first fold requires train_min_years of
    training data before a test window begins.  The last fold consumes
    all remaining data even if shorter than test_years.

    Example (train_min_years=2, test_years=1, data 2019-2025):
      Fold 1: train=2019-01-01→2020-12-31  test=2021-01-01→2021-12-31
      Fold 2: train=2019-01-01→2021-12-31  test=2022-01-01→2022-12-31
      Fold 3: train=2019-01-01→2022-12-31  test=2023-01-01→2023-12-31
      Fold 4: train=2019-01-01→2023-12-31  test=2024-01-01→2025-12-31
    """
    start = date.fromisoformat(data_start)
    end = date.fromisoformat(data_end)

    # First training window ends at start + train_min_years - 1 day
    first_train_end = date(start.year + train_min_years, start.month, start.day) - timedelta(days=1)

    folds: list[FoldSpec] = []
    fold_id = 1
    train_end_dt = first_train_end

    while True:
        test_start_dt = train_end_dt + timedelta(days=1)
        if test_start_dt >= end:
            break  # no room for a test period

        # Test window: test_years of data, or up to data end
        tentative_test_end = date(test_start_dt.year + test_years - 1, 12, 31)
        test_end_dt = min(tentative_test_end, end)

        folds.append(FoldSpec(
            fold_id=fold_id,
            train_start=data_start,
            train_end=train_end_dt.isoformat(),
            test_start=test_start_dt.isoformat(),
            test_end=test_end_dt.isoformat(),
        ))

        fold_id += 1
        train_end_dt = test_end_dt  # expand training window for next fold

        if test_end_dt >= end:
            break  # consumed all data

    return folds


def from_custom_json(json_str: str) -> list[FoldSpec]:
    """Parse custom fold specs from a JSON string or file path.

    Expected JSON format::

        [
          {
            "train_start": "2019-01-01", "train_end": "2020-12-31",
            "test_start":  "2021-01-01", "test_end":  "2021-12-31"
          },
          ...
        ]
    """
    raw = json.loads(json_str)
    folds: list[FoldSpec] = []
    for i, d in enumerate(raw):
        folds.append(FoldSpec(
            fold_id=i + 1,
            train_start=d["train_start"],
            train_end=d["train_end"],
            test_start=d["test_start"],
            test_end=d["test_end"],
        ))
    return folds
