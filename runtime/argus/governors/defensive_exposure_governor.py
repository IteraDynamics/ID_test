"""Defensive exposure governor — fund-level risk reducer for Fund v2.

This governor implements the A_light_dd20_trend defensive overlay that survived
research testing after transition-cost estimates. It is intentionally not an
alpha sleeve and never increases risk. It only returns an exposure scale in
``{1.00, 0.75}`` based on closed-bar BTC/ETH market data.

Research parameters promoted from scripts/run_fund_defensive_overlay.py:
    - Risk index: equal-weight normalised BTC + ETH close index
    - Rolling high lookback: 90 days on 1H bars = 2160 bars
    - Trigger: index drawdown >= 20% and index below EMA(200 days)
    - Release: index drawdown <= 12% or index back above EMA(200 days)
    - Confirm: 24 bars
    - Release confirm: 48 bars
    - Risk-off scale: 0.75

Contract:
    update(btc_close, eth_close, timestamp=None) -> DefensiveExposureDecision

The caller owns persistence. Use ``state_dict`` / ``load_state`` to persist the
small amount of governor state needed for live runtime continuity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DefensiveExposureDecision:
    """Decision emitted by DefensiveExposureGovernor.

    exposure_scale:
        Multiplicative scale applied to the already-computed Fund v1 target
        exposure. Always in [0, 1]. A value below 1.0 means defensive mode.
    active:
        True when risk-off mode is active.
    reason:
        Human-readable audit reason.
    meta:
        Numeric diagnostics suitable for logs/dashboard/state JSON.
    """

    exposure_scale: float
    active: bool
    reason: str
    meta: dict[str, Any] = field(default_factory=dict)


class DefensiveExposureGovernor:
    """Closed-bar defensive exposure reducer.

    Parameters are defaults from the A_light_dd20_trend research candidate.
    The governor builds an equal-weight normalised BTC/ETH index internally and
    applies the trigger/release logic in a strictly forward-only manner.
    """

    def __init__(
        self,
        lookback_bars: int = 90 * 24,
        dd_trigger: float = 0.20,
        dd_release: float = 0.12,
        trend_ema_span: int = 200 * 24,
        risk_off_scale: float = 0.75,
        confirm_bars: int = 24,
        release_confirm_bars: int = 48,
        min_warmup_bars: int | None = None,
        max_history_bars: int | None = None,
    ) -> None:
        if not 0.0 < risk_off_scale <= 1.0:
            raise ValueError(f"risk_off_scale must be in (0, 1], got {risk_off_scale}")
        if not 0.0 < dd_release <= dd_trigger <= 1.0:
            raise ValueError(
                "drawdown thresholds must satisfy 0 < dd_release <= dd_trigger <= 1"
            )
        if lookback_bars <= 1 or trend_ema_span <= 1:
            raise ValueError("lookback_bars and trend_ema_span must be > 1")
        if confirm_bars < 1 or release_confirm_bars < 1:
            raise ValueError("confirm_bars and release_confirm_bars must be >= 1")

        self.lookback_bars = int(lookback_bars)
        self.dd_trigger = float(dd_trigger)
        self.dd_release = float(dd_release)
        self.trend_ema_span = int(trend_ema_span)
        self.risk_off_scale = float(risk_off_scale)
        self.confirm_bars = int(confirm_bars)
        self.release_confirm_bars = int(release_confirm_bars)
        self.min_warmup_bars = int(min_warmup_bars or max(24, self.lookback_bars // 10))
        self.max_history_bars = int(max_history_bars or max(self.lookback_bars * 2, self.trend_ema_span * 2))

        self._btc_base: float | None = None
        self._eth_base: float | None = None
        self._index_history: list[float] = []
        self._last_ema: float | None = None
        self._active: bool = False
        self._risk_count: int = 0
        self._release_count: int = 0
        self._last_timestamp: str | None = None
        self._last_decision: DefensiveExposureDecision = DefensiveExposureDecision(
            exposure_scale=1.0,
            active=False,
            reason="Governor initialised — no closed bars evaluated yet",
            meta={},
        )

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_scale(self) -> float:
        return self.risk_off_scale if self._active else 1.0

    def update(
        self,
        btc_close: float,
        eth_close: float,
        timestamp: Any | None = None,
    ) -> DefensiveExposureDecision:
        """Update the governor with one closed BTC/ETH bar.

        Parameters
        ----------
        btc_close, eth_close:
            Closed-bar prices. Both must be positive.
        timestamp:
            Optional timestamp used only for audit metadata.
        """
        if btc_close <= 0 or eth_close <= 0:
            raise ValueError("btc_close and eth_close must be positive")

        if self._btc_base is None:
            self._btc_base = float(btc_close)
            self._eth_base = float(eth_close)

        idx_value = 0.5 * (float(btc_close) / self._btc_base) + 0.5 * (float(eth_close) / self._eth_base)
        self._index_history.append(idx_value)
        if len(self._index_history) > self.max_history_bars:
            self._index_history = self._index_history[-self.max_history_bars:]

        alpha = 2.0 / (self.trend_ema_span + 1.0)
        if self._last_ema is None:
            self._last_ema = idx_value
        else:
            self._last_ema = alpha * idx_value + (1.0 - alpha) * self._last_ema

        n = len(self._index_history)
        timestamp_s = None if timestamp is None else str(timestamp)
        self._last_timestamp = timestamp_s

        if n < self.min_warmup_bars:
            self._last_decision = DefensiveExposureDecision(
                exposure_scale=1.0,
                active=False,
                reason=f"Warmup: {n}/{self.min_warmup_bars} bars available",
                meta=self._meta(idx_value, 0.0, False, timestamp_s, warmup=True),
            )
            return self._last_decision

        window = self._index_history[-self.lookback_bars:]
        rolling_high = max(window)
        drawdown = 1.0 - (idx_value / rolling_high) if rolling_high > 0 else 0.0
        below_trend = idx_value < float(self._last_ema)

        risk_raw = drawdown >= self.dd_trigger and below_trend
        release_raw = drawdown <= self.dd_release or not below_trend

        self._risk_count = self._risk_count + 1 if risk_raw else 0
        self._release_count = self._release_count + 1 if release_raw else 0

        transition = "none"
        if not self._active and self._risk_count >= self.confirm_bars:
            self._active = True
            self._release_count = 0
            transition = "activated"
        elif self._active and self._release_count >= self.release_confirm_bars:
            self._active = False
            self._risk_count = 0
            transition = "released"

        scale = self.current_scale
        if self._active:
            reason = (
                f"Risk-off active: index DD={drawdown:.2%}, "
                f"below_trend={below_trend}, scale={scale:.2f}"
            )
        else:
            reason = (
                f"Risk-on: index DD={drawdown:.2%}, "
                f"below_trend={below_trend}, scale=1.00"
            )
        if transition != "none":
            reason = f"Defensive governor {transition}. {reason}"

        self._last_decision = DefensiveExposureDecision(
            exposure_scale=scale,
            active=self._active,
            reason=reason,
            meta=self._meta(idx_value, drawdown, below_trend, timestamp_s, transition=transition),
        )
        return self._last_decision

    def apply_scale(self, target_exposure: float) -> float:
        """Apply the latest defensive scale to a target exposure fraction."""
        return max(0.0, min(1.0, float(target_exposure) * self.current_scale))

    def last_decision(self) -> DefensiveExposureDecision:
        return self._last_decision

    def _meta(
        self,
        index_value: float,
        drawdown: float,
        below_trend: bool,
        timestamp: str | None,
        warmup: bool = False,
        transition: str = "none",
    ) -> dict[str, Any]:
        return {
            "timestamp": timestamp,
            "index_value": index_value,
            "ema_value": self._last_ema,
            "index_drawdown": drawdown,
            "index_drawdown_pct": drawdown * 100.0,
            "below_trend": below_trend,
            "active": self._active,
            "exposure_scale": self.current_scale,
            "risk_count": self._risk_count,
            "release_count": self._release_count,
            "transition": transition,
            "warmup": warmup,
            "params": {
                "lookback_bars": self.lookback_bars,
                "dd_trigger": self.dd_trigger,
                "dd_release": self.dd_release,
                "trend_ema_span": self.trend_ema_span,
                "risk_off_scale": self.risk_off_scale,
                "confirm_bars": self.confirm_bars,
                "release_confirm_bars": self.release_confirm_bars,
                "min_warmup_bars": self.min_warmup_bars,
            },
        }

    def state_dict(self) -> dict[str, Any]:
        return {
            "btc_base": self._btc_base,
            "eth_base": self._eth_base,
            "index_history": list(self._index_history),
            "last_ema": self._last_ema,
            "active": self._active,
            "risk_count": self._risk_count,
            "release_count": self._release_count,
            "last_timestamp": self._last_timestamp,
            "params": self._meta(0.0, 0.0, False, None).get("params", {}),
        }

    def load_state(self, state: dict[str, Any]) -> None:
        self._btc_base = state.get("btc_base")
        self._eth_base = state.get("eth_base")
        self._index_history = [float(x) for x in state.get("index_history", [])]
        if len(self._index_history) > self.max_history_bars:
            self._index_history = self._index_history[-self.max_history_bars:]
        self._last_ema = state.get("last_ema")
        self._active = bool(state.get("active", False))
        self._risk_count = int(state.get("risk_count", 0))
        self._release_count = int(state.get("release_count", 0))
        self._last_timestamp = state.get("last_timestamp")
        self._last_decision = DefensiveExposureDecision(
            exposure_scale=self.current_scale,
            active=self._active,
            reason="State loaded",
            meta=self._meta(
                self._index_history[-1] if self._index_history else 0.0,
                0.0,
                False,
                self._last_timestamp,
            ),
        )

    def reset(self) -> None:
        self._btc_base = None
        self._eth_base = None
        self._index_history.clear()
        self._last_ema = None
        self._active = False
        self._risk_count = 0
        self._release_count = 0
        self._last_timestamp = None
        self._last_decision = DefensiveExposureDecision(
            exposure_scale=1.0,
            active=False,
            reason="Governor reset",
            meta={},
        )
