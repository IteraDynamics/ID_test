"""Recovery Trust Gate — feature builder.

For each candidate re-risk event, compute a feature vector using ONLY data
available up to and including the candidate timestamp.  No future data leakage.

Temporal features require per-sleeve position history.  Pass
``position_data`` (dict keyed by sleeve_label → pd.Series[float]) to
enable bars_since_last_entry, days_since_last_full_exposure,
bars_in_defensive_state, candidate_count_since_last_full_exposure, and
candidate_count_since_last_successful_risk_on.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Threshold for "in a position" vs flat
_ENTRY_THRESH      = 0.10   # position > this → considered entered
_FULL_EXP_THRESH   = 0.90   # position >= this → full exposure
_DEFENSIVE_THRESH  = 0.25   # position <= this → defensive state


# ── Helpers ────────────────────────────────────────────────────────────────────

def _daily(df: pd.DataFrame) -> pd.DataFrame:
    """Resample an intraday OHLCV DataFrame to daily close."""
    if df.empty:
        return df
    try:
        freq = pd.infer_freq(df.index[:20])
    except Exception:
        freq = None
    if freq is not None and "D" not in freq.upper():
        return df.resample("D").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna(subset=["close"])
    return df


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()


def _safe(val, default=0.0):
    """Return val if finite, else default."""
    try:
        v = float(val)
        return v if np.isfinite(v) else default
    except Exception:
        return default


def _realized_vol(close: pd.Series, window: int) -> float:
    """Annualised realized volatility from daily log returns."""
    if len(close) < window + 1:
        return 0.0
    log_ret = np.log(close / close.shift(1)).dropna()
    if len(log_ret) < window:
        return 0.0
    return float(log_ret.tail(window).std() * np.sqrt(252))


# ── Main function ──────────────────────────────────────────────────────────────

def _temporal_features(
    ts: pd.Timestamp,
    sleeve_label: str,
    position_data: dict[str, pd.Series],
    candidates_df: pd.DataFrame,
    cand_idx: int,
) -> dict[str, float]:
    """Compute temporal state features for one candidate without lookahead.

    All computations use position history strictly before or at ``ts`` and
    only *prior* rows in candidates_df (rows with integer index < cand_idx).
    """
    feat: dict[str, float] = {}
    DEFAULT = {
        "bars_since_last_entry": 0.0,
        "days_since_last_full_exposure": 0.0,
        "bars_in_defensive_state": 0.0,
        "candidate_count_since_last_full_exposure": 0.0,
        "candidate_count_since_last_successful_risk_on": 0.0,
    }

    pos_series = position_data.get(sleeve_label)
    if pos_series is None or pos_series.empty:
        return DEFAULT.copy()

    pos_hist = pos_series[pos_series.index <= ts]
    if pos_hist.empty:
        return DEFAULT.copy()

    vals = pos_hist.values
    n = len(vals)

    # ── bars_since_last_entry ─────────────────────────────────────────────
    # Last bar where position transitioned from ≤_ENTRY_THRESH to >_ENTRY_THRESH
    was_flat = vals[:-1] <= _ENTRY_THRESH
    is_in    = vals[1:]  > _ENTRY_THRESH
    entry_mask = was_flat & is_in
    entry_indices = np.where(entry_mask)[0] + 1  # index of the bar that crossed up
    if len(entry_indices):
        feat["bars_since_last_entry"] = float(n - 1 - entry_indices[-1])
    else:
        feat["bars_since_last_entry"] = float(n)  # never entered — use full length

    # ── days_since_last_full_exposure ──────────────────────────────────────
    full_mask = vals >= _FULL_EXP_THRESH
    full_indices = np.where(full_mask)[0]
    if len(full_indices):
        last_full_ts = pos_hist.index[full_indices[-1]]
        feat["days_since_last_full_exposure"] = float((ts - last_full_ts).total_seconds() / 86400)
    else:
        # No full exposure ever — use days since series start
        feat["days_since_last_full_exposure"] = float((ts - pos_hist.index[0]).total_seconds() / 86400)

    # ── bars_in_defensive_state ────────────────────────────────────────────
    # Consecutive bars up to and including ts where position <= _DEFENSIVE_THRESH
    rev = vals[::-1]
    defensive_run = 0
    for v in rev:
        if v <= _DEFENSIVE_THRESH:
            defensive_run += 1
        else:
            break
    feat["bars_in_defensive_state"] = float(defensive_run)

    # ── candidate_count_since_last_full_exposure ───────────────────────────
    # Count prior candidates for same sleeve that occurred after last full exposure
    if full_indices.size:
        last_full_ts_cfe = pos_hist.index[full_indices[-1]]
    else:
        last_full_ts_cfe = pos_hist.index[0]

    prior_cands = candidates_df.iloc[:cand_idx]
    prior_sleeve = prior_cands[prior_cands["sleeve_label"] == sleeve_label]
    since_full = prior_sleeve[pd.to_datetime(prior_sleeve["timestamp"]) > last_full_ts_cfe]
    feat["candidate_count_since_last_full_exposure"] = float(len(since_full))

    # ── candidate_count_since_last_successful_risk_on ──────────────────────
    # Look at prior labeled candidates for same sleeve; find most recent label==1;
    # count how many candidates have occurred since that successful re-risk.
    # If label column doesn't exist or no positives yet, fall back to full prior count.
    if "label" in prior_sleeve.columns:
        successful = prior_sleeve[prior_sleeve["label"] == 1]
        if len(successful):
            last_success_ts = pd.to_datetime(successful["timestamp"].iloc[-1])
            since_success = prior_sleeve[pd.to_datetime(prior_sleeve["timestamp"]) > last_success_ts]
            feat["candidate_count_since_last_successful_risk_on"] = float(len(since_success))
        else:
            # No successful re-risk yet in this sleeve — total prior candidate count
            feat["candidate_count_since_last_successful_risk_on"] = float(len(prior_sleeve))
    else:
        feat["candidate_count_since_last_successful_risk_on"] = 0.0

    return feat


def build_features(
    candidates_df: pd.DataFrame,
    raw_data: dict[str, pd.DataFrame],
    position_data: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """Build feature matrix for all candidate re-risk events.

    Parameters
    ----------
    candidates_df:
        Output of label_candidates() — must have 'timestamp' column.
    raw_data:
        Dict with keys "BTC" (hourly), "ETH" (hourly, optional),
        "SPY" (daily, optional), "QQQ" (daily, optional).
    position_data:
        Optional dict keyed by sleeve_label → pd.Series[float] (exposure
        fraction, DatetimeIndex).  When provided, enables 5 temporal features.

    Returns
    -------
    pd.DataFrame with one row per candidate (same index as candidates_df)
    and all feature columns.  Missing values filled with 0 after logging.
    """
    # Pre-compute daily versions of each asset
    btc_raw  = raw_data.get("BTC", pd.DataFrame())
    eth_raw  = raw_data.get("ETH", pd.DataFrame())
    spy_raw  = raw_data.get("SPY", pd.DataFrame())
    qqq_raw  = raw_data.get("QQQ", pd.DataFrame())

    btc_d = _daily(btc_raw) if not btc_raw.empty else pd.DataFrame()
    eth_d = _daily(eth_raw) if not eth_raw.empty else pd.DataFrame()
    spy_d = spy_raw.copy()  if not spy_raw.empty  else pd.DataFrame()
    qqq_d = qqq_raw.copy()  if not qqq_raw.empty  else pd.DataFrame()

    feature_rows = []

    for idx, row in candidates_df.iterrows():
        ts = pd.Timestamp(row["timestamp"])
        feat: dict[str, float] = {}

        # ── BTC features ───────────────────────────────────────────────────────
        if not btc_d.empty:
            btc_hist = btc_d.loc[btc_d.index <= ts]
            if len(btc_hist) >= 2:
                close_btc = btc_hist["close"]
                c = float(close_btc.iloc[-1])

                sma50_btc  = _sma(close_btc, 50)
                sma175_btc = _sma(close_btc, 175)
                sma365_btc = _sma(close_btc, 365)

                s50  = _safe(sma50_btc.iloc[-1])
                s175 = _safe(sma175_btc.iloc[-1])
                s365 = _safe(sma365_btc.iloc[-1])

                feat["btc_pct_vs_sma175"] = _safe((c - s175) / s175 if s175 else 0.0)
                feat["btc_pct_vs_sma50"]  = _safe((c - s50)  / s50  if s50  else 0.0)

                # Drawdown features
                high_90d  = _safe(close_btc.tail(90).max(),  c)
                high_180d = _safe(close_btc.tail(180).max(), c)
                feat["btc_drawdown_90d"]  = _safe(c / high_90d  - 1.0 if high_90d  else 0.0)
                feat["btc_drawdown_180d"] = _safe(c / high_180d - 1.0 if high_180d else 0.0)

                feat["btc_realized_vol_30d"] = _safe(_realized_vol(close_btc, 30))

                # Rebound strength: how much has price bounced off 30d low
                low_30d = _safe(close_btc.tail(30).min(), c)
                feat["btc_rebound_strength"] = _safe(c / low_30d - 1.0 if low_30d else 0.0)

                # Parabolic tier based on SMA365 extension
                ext = _safe((c - s365) / s365 if s365 else 0.0)
                feat["btc_extension_pct"] = ext
                if ext < 0.60:
                    feat["btc_parabolic_tier"] = 0.0
                elif ext < 1.00:
                    feat["btc_parabolic_tier"] = 1.0
                else:
                    feat["btc_parabolic_tier"] = 2.0

                # Returns
                if len(close_btc) >= 21:
                    feat["btc_return_20d"] = _safe(close_btc.iloc[-1] / close_btc.iloc[-21] - 1.0)
                else:
                    feat["btc_return_20d"] = 0.0
                if len(close_btc) >= 61:
                    feat["btc_return_60d"] = _safe(close_btc.iloc[-1] / close_btc.iloc[-61] - 1.0)
                else:
                    feat["btc_return_60d"] = 0.0
            else:
                log.warning("ts=%s: insufficient BTC history (%d bars) — zeroing BTC features", ts, len(btc_hist))
                for k in [
                    "btc_pct_vs_sma175", "btc_pct_vs_sma50",
                    "btc_drawdown_90d", "btc_drawdown_180d",
                    "btc_realized_vol_30d", "btc_rebound_strength",
                    "btc_extension_pct", "btc_parabolic_tier",
                    "btc_return_20d", "btc_return_60d",
                ]:
                    feat[k] = 0.0
        else:
            log.warning("ts=%s: no BTC data — zeroing BTC features", ts)
            for k in [
                "btc_pct_vs_sma175", "btc_pct_vs_sma50",
                "btc_drawdown_90d", "btc_drawdown_180d",
                "btc_realized_vol_30d", "btc_rebound_strength",
                "btc_extension_pct", "btc_parabolic_tier",
                "btc_return_20d", "btc_return_60d",
            ]:
                feat[k] = 0.0

        # ── ETH features ───────────────────────────────────────────────────────
        if not eth_d.empty:
            eth_hist = eth_d.loc[eth_d.index <= ts]
            if len(eth_hist) >= 51:
                close_eth = eth_hist["close"]
                c_eth = float(close_eth.iloc[-1])
                sma50_eth = _sma(close_eth, 50)
                s50_eth = _safe(sma50_eth.iloc[-1])
                feat["eth_pct_vs_sma50"] = _safe((c_eth - s50_eth) / s50_eth if s50_eth else 0.0)
                if len(close_eth) >= 21:
                    feat["eth_return_20d"] = _safe(close_eth.iloc[-1] / close_eth.iloc[-21] - 1.0)
                else:
                    feat["eth_return_20d"] = 0.0
                eth_pos = 1 if feat["eth_return_20d"] > 0 and feat["btc_return_20d"] > 0 else 0
                feat["eth_confirms_btc"] = float(eth_pos)
            else:
                log.warning("ts=%s: insufficient ETH history — zeroing ETH features", ts)
                feat["eth_pct_vs_sma50"]  = 0.0
                feat["eth_return_20d"]    = 0.0
                feat["eth_confirms_btc"]  = 0.0
        else:
            feat["eth_pct_vs_sma50"]  = 0.0
            feat["eth_return_20d"]    = 0.0
            feat["eth_confirms_btc"]  = 0.0

        # ── SPY features ───────────────────────────────────────────────────────
        if not spy_d.empty:
            spy_hist = spy_d.loc[spy_d.index <= ts]
            if len(spy_hist) >= 51:
                close_spy = spy_hist["close"]
                c_spy = float(close_spy.iloc[-1])
                sma50_spy  = _sma(close_spy, 50)
                sma175_spy = _sma(close_spy, 175)
                s50_spy  = _safe(sma50_spy.iloc[-1])
                s175_spy = _safe(sma175_spy.iloc[-1])
                feat["spy_above_sma175"] = float(c_spy > s175_spy if s175_spy else 0)
                feat["spy_above_sma50"]  = float(c_spy > s50_spy  if s50_spy  else 0)
                feat["spy_return_20d"] = _safe(close_spy.iloc[-1] / close_spy.iloc[-21] - 1.0) if len(close_spy) >= 21 else 0.0
                feat["spy_return_60d"] = _safe(close_spy.iloc[-1] / close_spy.iloc[-61] - 1.0) if len(close_spy) >= 61 else 0.0
            else:
                log.warning("ts=%s: insufficient SPY history — zeroing SPY features", ts)
                feat["spy_above_sma175"] = 0.0
                feat["spy_above_sma50"]  = 0.0
                feat["spy_return_20d"]   = 0.0
                feat["spy_return_60d"]   = 0.0
        else:
            feat["spy_above_sma175"] = 0.0
            feat["spy_above_sma50"]  = 0.0
            feat["spy_return_20d"]   = 0.0
            feat["spy_return_60d"]   = 0.0

        # ── QQQ features ───────────────────────────────────────────────────────
        if not qqq_d.empty:
            qqq_hist = qqq_d.loc[qqq_d.index <= ts]
            if len(qqq_hist) >= 51:
                close_qqq = qqq_hist["close"]
                c_qqq = float(close_qqq.iloc[-1])
                sma50_qqq = _sma(close_qqq, 50)
                s50_qqq = _safe(sma50_qqq.iloc[-1])
                feat["qqq_above_sma50"]  = float(c_qqq > s50_qqq if s50_qqq else 0)
                feat["qqq_return_20d"] = _safe(close_qqq.iloc[-1] / close_qqq.iloc[-21] - 1.0) if len(close_qqq) >= 21 else 0.0
            else:
                feat["qqq_above_sma50"]  = 0.0
                feat["qqq_return_20d"]   = 0.0
        else:
            feat["qqq_above_sma50"]  = 0.0
            feat["qqq_return_20d"]   = 0.0

        # ── Cross-asset features ───────────────────────────────────────────────
        feat["equity_crypto_agree"] = float(
            bool(feat["spy_above_sma50"]) and feat["btc_pct_vs_sma50"] > 0
        )

        breadth_checks = []
        breadth_checks.append(feat["btc_pct_vs_sma50"] > 0)
        if not eth_d.empty:
            breadth_checks.append(feat["eth_pct_vs_sma50"] > 0)
        if not spy_d.empty:
            breadth_checks.append(bool(feat["spy_above_sma50"]))
        if not qqq_d.empty:
            breadth_checks.append(bool(feat["qqq_above_sma50"]))
        feat["trend_breadth"] = _safe(sum(breadth_checks) / len(breadth_checks)) if breadth_checks else 0.0

        # ── Candidate context ──────────────────────────────────────────────────
        feat["proposed_exposure"] = _safe(row.get("proposed_exposure", 0.0))
        feat["prior_exposure"]    = _safe(row.get("prior_exposure", 0.0))
        feat["exposure_delta"]    = _safe(row.get("exposure_delta", 0.0))

        # ── Temporal / state features ──────────────────────────────────────────
        sleeve_label = str(row.get("sleeve_label", ""))
        if position_data is not None:
            tfeat = _temporal_features(ts, sleeve_label, position_data, candidates_df, idx)
            feat.update({k: _safe(v) for k, v in tfeat.items()})
        else:
            for k in (
                "bars_since_last_entry",
                "days_since_last_full_exposure",
                "bars_in_defensive_state",
                "candidate_count_since_last_full_exposure",
                "candidate_count_since_last_successful_risk_on",
            ):
                feat[k] = 0.0

        # Final NaN/inf safety sweep
        for k, v in feat.items():
            if not np.isfinite(v):
                log.warning("ts=%s: feature %s is non-finite (%s) — replacing with 0", ts, k, v)
                feat[k] = 0.0

        feature_rows.append(feat)

    result = pd.DataFrame(feature_rows, index=candidates_df.index)
    log.info("Built feature matrix: %d rows × %d features", len(result), len(result.columns))
    return result
