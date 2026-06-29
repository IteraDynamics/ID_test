"""Recovery Trust Gate — position scaler.

Applies ML-derived recovery confidence scores to scale or block the Core
strategy's proposed exposure increases.  The ML gate operates ONLY on
candidate re-risk events; all other bars pass through unchanged.

Key invariant: ML never blocks exits.  EXIT_LONG, EXIT_SHORT, and FLAT
signals always execute at full exposure (or flat), regardless of ML score.
"""

from __future__ import annotations

import logging

import pandas as pd

from research.strategies.contracts import Action, StrategyIntent

log = logging.getLogger(__name__)


# Scaler bands (LOCKED — matches spec)
BAND_FULL   = 0.70   # >= 0.70 → 100% of proposed
BAND_HALF   = 0.50   # 0.50–0.70 → 50% of proposed
BAND_QUARTER= 0.35   # 0.35–0.50 → 25% of proposed
BAND_BLOCK  = 0.35   # < 0.35 → block (hold prior exposure)


def _scale_factor(confidence: float) -> float:
    """Return the exposure scale factor for a given recovery confidence."""
    if confidence >= BAND_FULL:
        return 1.00
    elif confidence >= BAND_HALF:
        return 0.50
    elif confidence >= BAND_QUARTER:
        return 0.25
    else:
        return 0.00   # block


def apply_scaler(
    position_series: pd.Series,
    intent_series: list[StrategyIntent],
    ml_probs: pd.Series,
    candidates_df: pd.DataFrame,
) -> pd.Series:
    """Scale or block exposure increases at candidate re-risk events.

    Parameters
    ----------
    position_series:
        Core's executed exposure fractions (original, unmodified).
    intent_series:
        One StrategyIntent per bar, same order as position_series.
    ml_probs:
        pd.Series indexed by timestamp → recovery_confidence in [0, 1].
        Typically from FoldResult.test_probs (walk-forward OOS predictions).
    candidates_df:
        Output of detect_candidates() (with label columns optionally added).
        Must have 'timestamp', 'proposed_exposure', 'prior_exposure' columns.

    Returns
    -------
    pd.Series of scaled exposures, same index as position_series.
    """
    # Build lookup: timestamp → (prior_exposure, proposed_exposure)
    cand_by_ts: dict[pd.Timestamp, dict] = {}
    for _, row in candidates_df.iterrows():
        ts = pd.Timestamp(row["timestamp"])
        cand_by_ts[ts] = {
            "prior_exposure":    float(row["prior_exposure"]),
            "proposed_exposure": float(row["proposed_exposure"]),
        }

    # Build lookup: timestamp → recovery_confidence from ml_probs
    prob_by_ts: dict[pd.Timestamp, float] = {}
    if ml_probs is not None:
        for ts, p in ml_probs.items():
            prob_by_ts[pd.Timestamp(ts)] = float(p)

    scaled = position_series.copy().astype(float)
    pos_values = position_series.values

    # Track current scale factor between candidate events
    # (for proportional scaling of subsequent HOLD bars)
    active_scale: float | None = None
    active_proposed: float | None = None

    for i, intent in enumerate(intent_series):
        ts = scaled.index[i]

        # Exits always pass through unchanged
        if intent.action in (Action.EXIT_LONG, Action.EXIT_SHORT, Action.FLAT):
            active_scale = None
            active_proposed = None
            continue

        if ts in cand_by_ts:
            # This is a candidate re-risk bar — apply ML gate
            confidence = prob_by_ts.get(ts)
            if confidence is None:
                log.debug("ts=%s: candidate has no ML probability — passing through unchanged", ts)
                active_scale = None
                active_proposed = None
                continue

            factor = _scale_factor(confidence)
            proposed = cand_by_ts[ts]["proposed_exposure"]
            prior    = cand_by_ts[ts]["prior_exposure"]

            if factor == 0.0:
                # Block: hold prior exposure (don't increase)
                scaled.iloc[i] = prior
                log.debug(
                    "ts=%s: BLOCKED (conf=%.3f < %.2f), holding prior=%.2f",
                    ts, confidence, BAND_BLOCK, prior,
                )
            else:
                new_exp = proposed * factor
                scaled.iloc[i] = new_exp
                log.debug(
                    "ts=%s: SCALED (conf=%.3f, factor=%.2f), proposed=%.2f → %.2f",
                    ts, confidence, factor, proposed, new_exp,
                )

            active_scale    = factor
            active_proposed = proposed

        elif active_scale is not None and active_proposed is not None:
            # Subsequent HOLD bar after a scaled entry — scale proportionally
            original_exp = float(pos_values[i])
            if original_exp > 0 and active_proposed > 0:
                # Scale by the same factor that was applied at the entry bar
                new_exp = original_exp * active_scale
                scaled.iloc[i] = new_exp
            # If a new re-risk or exit comes, the loop will reset active_scale

    return scaled


def apply_binary_veto(
    position_series: pd.Series,
    intent_series: list[StrategyIntent],
    ml_probs: pd.Series,
    candidates_df: pd.DataFrame,
    threshold: float = 0.50,
) -> pd.Series:
    """Binary veto: allow full exposure if confidence >= threshold, else block.

    Parameters
    ----------
    threshold:
        Confidence cutoff.  >= threshold → allow; < threshold → block at prior.

    Returns
    -------
    pd.Series of binary-vetoed exposures, same index as position_series.
    """
    cand_by_ts: dict[pd.Timestamp, dict] = {}
    for _, row in candidates_df.iterrows():
        ts = pd.Timestamp(row["timestamp"])
        cand_by_ts[ts] = {
            "prior_exposure":    float(row["prior_exposure"]),
            "proposed_exposure": float(row["proposed_exposure"]),
        }

    prob_by_ts: dict[pd.Timestamp, float] = {}
    if ml_probs is not None:
        for ts, p in ml_probs.items():
            prob_by_ts[pd.Timestamp(ts)] = float(p)

    scaled = position_series.copy().astype(float)

    for i, intent in enumerate(intent_series):
        ts = scaled.index[i]

        # Exits always pass through
        if intent.action in (Action.EXIT_LONG, Action.EXIT_SHORT, Action.FLAT):
            continue

        if ts in cand_by_ts:
            confidence = prob_by_ts.get(ts)
            if confidence is None:
                continue

            if confidence < threshold:
                prior = cand_by_ts[ts]["prior_exposure"]
                scaled.iloc[i] = prior
                log.debug(
                    "ts=%s: binary VETO (conf=%.3f < %.2f), holding prior=%.2f",
                    ts, confidence, threshold, prior,
                )
            # else: allow — keep original position_series value

    return scaled
