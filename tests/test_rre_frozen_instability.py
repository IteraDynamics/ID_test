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
