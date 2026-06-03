"""Recovery Trust Gate — candidate re-risk event detector.

A candidate is a bar where the Core strategy proposes a significant exposure
increase (re-risk), potentially into a fake rebound.  The detector identifies
these events so they can be labelled, featurised, and gated by the ML model.
"""

from __future__ import annotations

import logging
from typing import Sequence

import pandas as pd

from research.strategies.contracts import Action, StrategyIntent

log = logging.getLogger(__name__)

# Thresholds (LOCKED — matches spec)
MIN_EXPOSURE_DELTA = 0.10    # +10pp minimum increase
MIN_NEW_EXPOSURE   = 0.25    # new proposed exposure >= 25%
COOLDOWN_BARS      = 10      # bars between candidates on same asset
RESET_EXPOSURE     = 0.10    # exposure floor that resets the cooldown


def detect_candidates(
    position_series: pd.Series,
    intent_series: Sequence[StrategyIntent],
    df_index: pd.Index,
    *,
    asset: str = "unknown",
    timeframe: str = "unknown",
    sleeve_label: str = "unknown",
) -> pd.DataFrame:
    """Detect candidate re-risk events from Core strategy output.

    Parameters
    ----------
    position_series:
        Actual executed exposure fractions [0, 1] indexed to df_index.
        This is what was *held* at each bar, not what was proposed.
    intent_series:
        One StrategyIntent per bar, same order as df_index.
    df_index:
        The DatetimeIndex of the underlying OHLCV DataFrame.
    asset, timeframe, sleeve_label:
        Metadata attached to every output row.

    Returns
    -------
    pd.DataFrame with columns:
        timestamp, bar_index, proposed_exposure, prior_exposure,
        exposure_delta, asset, timeframe, sleeve_label
    """
    if len(intent_series) != len(df_index):
        raise ValueError(
            f"intent_series length {len(intent_series)} != df_index length {len(df_index)}"
        )
    if len(position_series) != len(df_index):
        raise ValueError(
            f"position_series length {len(position_series)} != df_index length {len(df_index)}"
        )

    records = []
    last_candidate_bar: int | None = None  # bar_index of last fired candidate

    pos_values = position_series.values  # fast numpy access

    for i, intent in enumerate(intent_series):
        ts = df_index[i]

        # Proposed exposure from the Core's intent
        proposed = float(intent.desired_exposure_frac)

        # Prior actual execution (bar i-1)
        prior = float(pos_values[i - 1]) if i > 0 else 0.0

        delta = proposed - prior

        # Condition 1: meaningful exposure increase
        if delta < MIN_EXPOSURE_DELTA:
            continue

        # Condition 2: new exposure is material
        if proposed < MIN_NEW_EXPOSURE:
            continue

        # Condition 3: action must be ENTER_LONG or HOLD (not exits/flat)
        if intent.action in (Action.EXIT_LONG, Action.EXIT_SHORT, Action.FLAT):
            continue

        # Condition 4: cooldown check
        if last_candidate_bar is not None:
            bars_since = i - last_candidate_bar
            if bars_since < COOLDOWN_BARS:
                # Check if exposure returned to <= RESET_EXPOSURE between candidates
                window_exposure = pos_values[last_candidate_bar + 1 : i]
                reset_occurred = len(window_exposure) > 0 and float(window_exposure.min()) <= RESET_EXPOSURE
                if not reset_occurred:
                    log.debug(
                        "bar %d: cooldown active (%d bars since last candidate, no reset) — skip",
                        i, bars_since,
                    )
                    continue

        records.append({
            "timestamp":        ts,
            "bar_index":        i,
            "proposed_exposure": proposed,
            "prior_exposure":   prior,
            "exposure_delta":   delta,
            "asset":            asset,
            "timeframe":        timeframe,
            "sleeve_label":     sleeve_label,
        })
        last_candidate_bar = i

    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=[
            "timestamp", "bar_index", "proposed_exposure", "prior_exposure",
            "exposure_delta", "asset", "timeframe", "sleeve_label",
        ])
    log.info(
        "%s [%s]: detected %d candidate re-risk events",
        sleeve_label, asset, len(df),
    )
    return df
