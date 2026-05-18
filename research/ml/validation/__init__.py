"""research.ml.validation — Walk-forward validation for calibration robustness.

Public API
----------
FoldSpec            — defines one train/test window
FoldResult          — complete results for one fold
build_annual_folds  — generate expanding-window annual folds
run_fold            — execute one fold (train calibrator → test both versions)
run_walk_forward    — iterate over all folds
"""

from research.ml.validation.fold_spec import FoldSpec, build_annual_folds, from_custom_json
from research.ml.validation.walk_forward import FoldResult, run_fold, run_walk_forward

__all__ = [
    "FoldSpec",
    "FoldResult",
    "build_annual_folds",
    "from_custom_json",
    "run_fold",
    "run_walk_forward",
]
