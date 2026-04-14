"""Layer 1 — BaselineRegimeEngine.

Classifies market regime using three independent sub-signals:

1. Trend direction   — dual EMA crossover (fast vs slow).
2. Volatility level  — ATR as % of close (normalised historical volatility).
3. Trend momentum    — rate-of-change of the slow EMA.

Classification rules (applied in priority order):
    HIGH_VOL        — vol_pct > HIGH_VOL_THRESHOLD
    VOL_EXPANSION   — vol_pct accelerating AND above mid threshold
    TREND_UP        — fast EMA > slow EMA AND momentum > 0 AND vol in range
    TREND_DOWN      — fast EMA < slow EMA AND momentum < 0 AND vol in range
    VOL_COMPRESSION — vol_pct < COMPRESSION_THRESHOLD
    RANGE           — no clear directional signal
    UNKNOWN         — insufficient data (warmup period)

All parameters are constructor-injectable for testability.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from research.regimes.contracts import RegimeLabel, RegimeSignal


class BaselineRegimeEngine:
    """Deterministic regime classifier.

    Parameters
    ----------
    fast_ema : int
        Period for the fast exponential moving average (default 21).
    slow_ema : int
        Period for the slow exponential moving average (default 55).
    atr_period : int
        ATR lookback period in bars (default 14).
    high_vol_threshold : float
        ATR-as-%-of-close threshold above which we declare HIGH_VOL (default 0.04 = 4%).
    mid_vol_threshold : float
        ATR threshold above which VOL_EXPANSION is possible (default 0.025 = 2.5%).
    compression_threshold : float
        ATR threshold below which we declare VOL_COMPRESSION (default 0.012 = 1.2%).
    vol_expansion_lookback : int
        Bars over which ATR acceleration is measured (default 5).
    momentum_lookback : int
        Bars over which slow EMA rate-of-change is computed (default 5).
    min_bars : int
        Minimum closed bars needed before any non-UNKNOWN signal is emitted.
    """

    def __init__(
        self,
        fast_ema: int = 21,
        slow_ema: int = 55,
        atr_period: int = 14,
        high_vol_threshold: float = 0.04,
        mid_vol_threshold: float = 0.025,
        compression_threshold: float = 0.012,
        vol_expansion_lookback: int = 5,
        momentum_lookback: int = 5,
        min_bars: int = 60,
    ) -> None:
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.atr_period = atr_period
        self.high_vol_threshold = high_vol_threshold
        self.mid_vol_threshold = mid_vol_threshold
        self.compression_threshold = compression_threshold
        self.vol_expansion_lookback = vol_expansion_lookback
        self.momentum_lookback = momentum_lookback
        self.min_bars = min_bars

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────

    def classify_bar(self, df: pd.DataFrame, bar_idx: int) -> RegimeSignal:
        """Classify a single closed bar by its integer position in *df*.

        Parameters
        ----------
        df :
            OHLCV DataFrame with columns [open, high, low, close, volume].
            Must already contain all bars up to and including *bar_idx*.
        bar_idx :
            0-based integer index of the bar to classify.

        Returns
        -------
        RegimeSignal
            Immutable signal for this bar.

        Notes
        -----
        Only uses data at positions 0..bar_idx — no lookahead.
        """
        if bar_idx < self.min_bars:
            return RegimeSignal(
                label=RegimeLabel.UNKNOWN,
                confidence=0.0,
                bar_index=bar_idx,
                timestamp=self._ts(df, bar_idx),
                sub_signals={"reason": "warmup"},
            )

        window = df.iloc[: bar_idx + 1]
        indicators_series = self._compute_indicators(window)

        # Extract last-bar scalar values before classification
        indicators = {
            k: float(v.iloc[-1]) if hasattr(v, "iloc") else float(v)
            for k, v in indicators_series.items()
        }

        label, confidence, sub_signals = self._classify(indicators)
        sub_signals["bar_idx"] = bar_idx
        return RegimeSignal(
            label=label,
            confidence=confidence,
            sub_signals=sub_signals,
            bar_index=bar_idx,
            timestamp=self._ts(df, bar_idx),
        )

    def classify_dataframe(self, df: pd.DataFrame) -> list[RegimeSignal]:
        """Classify every bar in *df* using only past data at each step.

        Vectorised computation of indicators over the full DataFrame, then
        bar-by-bar classification.  This is O(n) in bar count for a fixed
        indicator window and is safe for offline research use.
        """
        indicators_full = self._compute_indicators(df)

        signals: list[RegimeSignal] = []
        for i in range(len(df)):
            if i < self.min_bars:
                signals.append(
                    RegimeSignal(
                        label=RegimeLabel.UNKNOWN,
                        confidence=0.0,
                        bar_index=i,
                        timestamp=self._ts(df, i),
                        sub_signals={"reason": "warmup"},
                    )
                )
                continue

            # Slice indicator series at bar i
            row = {k: v.iloc[i] if hasattr(v, "iloc") else v for k, v in indicators_full.items()}
            label, confidence, sub_signals = self._classify(row)
            sub_signals["bar_idx"] = i
            signals.append(
                RegimeSignal(
                    label=label,
                    confidence=confidence,
                    sub_signals=sub_signals,
                    bar_index=i,
                    timestamp=self._ts(df, i),
                )
            )
        return signals

    # ─────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────

    def _compute_indicators(self, df: pd.DataFrame) -> dict:
        """Compute all intermediate indicator series over *df*."""
        close = df["close"]
        high = df["high"]
        low = df["low"]

        ema_fast = close.ewm(span=self.fast_ema, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow_ema, adjust=False).mean()

        atr = self._atr(high, low, close, self.atr_period)
        atr_pct = atr / close

        # ATR acceleration: ratio of current ATR to ATR `vol_expansion_lookback` bars ago
        atr_prev = atr.shift(self.vol_expansion_lookback)
        atr_accel = (atr / atr_prev) - 1.0  # positive = expanding

        # Slow EMA rate of change (momentum proxy)
        ema_slow_prev = ema_slow.shift(self.momentum_lookback)
        ema_roc = (ema_slow - ema_slow_prev) / ema_slow_prev

        # EMA spread as fraction of price — indicates trend strength
        ema_spread = (ema_fast - ema_slow) / close

        return {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "atr_pct": atr_pct,
            "atr_accel": atr_accel,
            "ema_roc": ema_roc,
            "ema_spread": ema_spread,
        }

    def _classify(self, ind: dict) -> tuple[RegimeLabel, float, dict]:
        """Map indicator snapshot to a RegimeLabel + confidence score.

        *ind* may contain either scalar values (from a single-bar classify_bar
        call) or it may be a row-slice dict where each value is already scalar
        (from classify_dataframe). We ensure scalar extraction here.
        """

        def s(v):
            """Extract scalar from a possible pandas scalar, 0-d array, or float."""
            try:
                val = float(v)
            except (TypeError, ValueError):
                return 0.0
            return val if not np.isnan(val) else 0.0

        atr_pct = s(ind["atr_pct"])
        atr_accel = s(ind["atr_accel"])
        ema_roc = s(ind["ema_roc"])
        ema_spread = s(ind["ema_spread"])

        sub: dict = {
            "atr_pct": round(atr_pct, 5),
            "atr_accel": round(atr_accel, 5),
            "ema_roc": round(ema_roc, 6),
            "ema_spread": round(ema_spread, 6),
        }

        # ── Priority 1: HIGH_VOL ─────────────────────────────────────
        if atr_pct > self.high_vol_threshold:
            sub["reason"] = "atr_pct above high_vol_threshold"
            return RegimeLabel.HIGH_VOL, self._vol_confidence(atr_pct, self.high_vol_threshold, 0.08), sub

        # ── Priority 2: VOL_EXPANSION ────────────────────────────────
        if atr_pct > self.mid_vol_threshold and atr_accel > 0.10:
            sub["reason"] = "atr_pct mid-range and accelerating"
            return RegimeLabel.VOL_EXPANSION, min(0.5 + atr_accel * 2, 1.0), sub

        # ── Priority 3: VOL_COMPRESSION ─────────────────────────────
        if atr_pct < self.compression_threshold:
            sub["reason"] = "atr_pct below compression_threshold"
            conf = 1.0 - (atr_pct / self.compression_threshold)
            return RegimeLabel.VOL_COMPRESSION, round(min(conf, 1.0), 4), sub

        # ── Priority 4: Trend ────────────────────────────────────────
        trend_up = ema_spread > 0 and ema_roc > 0
        trend_dn = ema_spread < 0 and ema_roc < 0

        if trend_up:
            confidence = min(abs(ema_spread) * 20 + abs(ema_roc) * 10, 1.0)
            sub["reason"] = "ema_fast > ema_slow, positive momentum"
            return RegimeLabel.TREND_UP, round(confidence, 4), sub

        if trend_dn:
            confidence = min(abs(ema_spread) * 20 + abs(ema_roc) * 10, 1.0)
            sub["reason"] = "ema_fast < ema_slow, negative momentum"
            return RegimeLabel.TREND_DOWN, round(confidence, 4), sub

        # ── Default: RANGE ───────────────────────────────────────────
        sub["reason"] = "no dominant signal"
        return RegimeLabel.RANGE, 0.5, sub

    @staticmethod
    def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """True Range Average — standard Wilder ATR."""
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _vol_confidence(current: float, low_thresh: float, high_thresh: float) -> float:
        """Scale confidence between 0.5 and 1.0 based on normalised position in range."""
        span = high_thresh - low_thresh
        if span <= 0:
            return 0.5
        return round(min(0.5 + 0.5 * (current - low_thresh) / span, 1.0), 4)

    @staticmethod
    def _ts(df: pd.DataFrame, i: int) -> str:
        """Return timestamp string for bar at position *i*, or empty string."""
        try:
            idx = df.index[i]
            return str(idx)
        except Exception:
            return ""
