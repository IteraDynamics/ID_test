"""Campaign #52 research-only target capture and replay adapter.

This module is additive. It does not modify the canonical backtest engine or any
strategy. It mirrors canonical execution semantics so synthetic tests can prove
capture-only and unmodified-target replay equivalence before any governed-source
execution is considered.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from research.harness.execution_model import ExecutionConfig, compute_atr_pct_series, compute_fill
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.harness.backtest_engine import BacktestResult, TradeRecord

TARGET_HEADER = (
    "stage",
    "fold",
    "timestamp",
    "sleeve_label",
    "asset",
    "native_timeframe",
    "strategy_id",
    "action",
    "desired_exposure_frac",
    "signed_target_exposure",
    "sequence_number",
)


class Campaign52ReplayError(ValueError):
    """Fail-closed adapter error."""


@dataclass(frozen=True)
class TargetRecord:
    stage: str
    fold: str
    timestamp: pd.Timestamp
    sleeve_label: str
    asset: str
    native_timeframe: str
    strategy_id: str
    action: str
    desired_exposure_frac: float
    signed_target_exposure: float
    sequence_number: int


@dataclass
class CaptureReplayResult:
    result: BacktestResult
    targets: list[TargetRecord] = field(default_factory=list)


def intent_to_signed_target(
    intent: StrategyIntent,
    current_exposure: float,
    max_exposure: float = 1.0,
) -> float:
    """Convert one canonical intent to its pre-execution signed target."""
    if max_exposure < 0.0:
        raise Campaign52ReplayError("NEGATIVE_MAX_EXPOSURE")
    if intent.action in (Action.EXIT_LONG, Action.EXIT_SHORT, Action.FLAT):
        return 0.0
    if intent.action == Action.HOLD:
        return float(current_exposure)
    desired = min(float(intent.desired_exposure_frac), float(max_exposure))
    if intent.action == Action.ENTER_SHORT:
        return -desired
    if intent.action == Action.ENTER_LONG:
        return desired
    raise Campaign52ReplayError(f"UNSUPPORTED_ACTION:{intent.action}")


def _validate_action_target(record: TargetRecord) -> None:
    """Validate target semantics without clipping realized HOLD exposure drift.

    Entry intents remain bounded by the frozen desired-exposure contract.
    Exit and flat intents must target zero. HOLD intentionally inherits current
    realized exposure, which can move slightly outside +/-1 after price changes
    and execution costs; it must therefore be finite but is not entry-bounded.
    """
    try:
        action = Action(record.action)
    except ValueError as exc:
        raise Campaign52ReplayError(f"TARGET_ACTION_INVALID:{record.action}") from exc

    desired = float(record.desired_exposure_frac)
    target = float(record.signed_target_exposure)
    if not math.isfinite(desired) or not math.isfinite(target):
        raise Campaign52ReplayError("TARGET_NONFINITE")
    if not 0.0 <= desired <= 1.0:
        raise Campaign52ReplayError("TARGET_DESIRED_EXPOSURE_OUT_OF_RANGE")

    if action == Action.ENTER_LONG and not 0.0 <= target <= 1.0:
        raise Campaign52ReplayError("TARGET_EXPOSURE_OUT_OF_RANGE")
    if action == Action.ENTER_SHORT and not -1.0 <= target <= 0.0:
        raise Campaign52ReplayError("TARGET_EXPOSURE_OUT_OF_RANGE")
    if action in (Action.EXIT_LONG, Action.EXIT_SHORT, Action.FLAT) and target != 0.0:
        raise Campaign52ReplayError("TARGET_EXIT_NOT_FLAT")


def _validate_target_records(
    records: Sequence[TargetRecord],
    index: pd.DatetimeIndex,
    *,
    stage: str,
    fold: str,
    sleeve_label: str,
    asset: str,
    native_timeframe: str,
) -> dict[pd.Timestamp, TargetRecord]:
    if len(records) != len(index):
        raise Campaign52ReplayError("TARGET_COUNT_MISMATCH")
    mapping: dict[pd.Timestamp, TargetRecord] = {}
    previous_sequence = -1
    for record in records:
        ts = pd.Timestamp(record.timestamp)
        if ts in mapping:
            raise Campaign52ReplayError("DUPLICATE_TARGET_TIMESTAMP")
        if record.stage != stage or record.fold != fold:
            raise Campaign52ReplayError("TARGET_STAGE_FOLD_MISMATCH")
        if record.sleeve_label != sleeve_label or record.asset != asset:
            raise Campaign52ReplayError("TARGET_SLEEVE_ASSET_MISMATCH")
        if record.native_timeframe != native_timeframe:
            raise Campaign52ReplayError("TARGET_TIMEFRAME_MISMATCH")
        if record.sequence_number != previous_sequence + 1:
            raise Campaign52ReplayError("TARGET_SEQUENCE_FAILURE")
        _validate_action_target(record)
        mapping[ts] = record
        previous_sequence = record.sequence_number
    expected = set(pd.DatetimeIndex(index))
    if set(mapping) != expected:
        raise Campaign52ReplayError("TARGET_TIMESTAMP_SET_MISMATCH")
    return mapping


def run_capture_or_replay(
    *,
    df: pd.DataFrame,
    strategy_module: Any | None,
    target_records: Sequence[TargetRecord] | None = None,
    regime_engine: BaselineRegimeEngine | None = None,
    initial_capital: float = 100_000.0,
    exec_config: ExecutionConfig | None = None,
    max_exposure: float = 1.0,
    rebalance_threshold: float = 0.02,
    asset: str = "BTC",
    cash_yield_series: pd.Series | None = None,
    stage: str = "synthetic",
    fold: str = "synthetic_fold",
    sleeve_label: str = "synthetic_sleeve",
    native_timeframe: str = "1H",
) -> CaptureReplayResult:
    """Run synthetic capture mode or replay mode through canonical mechanics.

    Capture mode requires ``strategy_module`` and no ``target_records``.
    Replay mode requires ``target_records`` and does not call a strategy.
    """
    capture_mode = target_records is None
    if capture_mode and strategy_module is None:
        raise Campaign52ReplayError("CAPTURE_REQUIRES_STRATEGY")
    if not capture_mode and strategy_module is not None:
        raise Campaign52ReplayError("REPLAY_MUST_NOT_CALL_STRATEGY")
    if not isinstance(df.index, pd.DatetimeIndex) or not df.index.is_monotonic_increasing:
        raise Campaign52ReplayError("INVALID_DATAFRAME_INDEX")
    if df.index.has_duplicates:
        raise Campaign52ReplayError("DUPLICATE_DATAFRAME_TIMESTAMP")
    if "close" not in df.columns:
        raise Campaign52ReplayError("CLOSE_COLUMN_REQUIRED")

    if regime_engine is None:
        regime_engine = BaselineRegimeEngine()
    if exec_config is None:
        exec_config = ExecutionConfig()

    replay_map: dict[pd.Timestamp, TargetRecord] | None = None
    if target_records is not None:
        replay_map = _validate_target_records(
            target_records,
            df.index,
            stage=stage,
            fold=fold,
            sleeve_label=sleeve_label,
            asset=asset,
            native_timeframe=native_timeframe,
        )

    n = len(df)
    regime_signals = regime_engine.classify_dataframe(df)
    regime_labels = [signal.label for signal in regime_signals]
    atr_pct_series = compute_atr_pct_series(df)

    cash = float(initial_capital)
    position_units = 0.0
    current_exposure = 0.0
    last_trade_bar = -9999
    equity_arr = np.zeros(n, dtype=float)
    position_arr = np.zeros(n, dtype=float)
    trades: list[TradeRecord] = []
    intents: list[StrategyIntent] = []
    captured: list[TargetRecord] = []

    yield_arr: np.ndarray | None = None
    if cash_yield_series is not None:
        aligned = cash_yield_series.reindex(df.index, method="ffill").fillna(0.0)
        yield_arr = aligned.to_numpy(dtype=float)

    for i in range(n):
        ts = pd.Timestamp(df.index[i])
        close_price = float(df["close"].iloc[i])
        atr_pct = float(atr_pct_series.iloc[i])
        if yield_arr is not None:
            cash *= 1.0 + yield_arr[i]
        nav = cash + position_units * close_price

        if capture_mode:
            ctx = StrategyContext(
                regime=regime_labels[i],
                current_exposure_frac=min(1.0, abs(current_exposure)),
                asset=asset,
                bar_index=i,
                meta={"signed_exposure": current_exposure},
            )
            intent = strategy_module.generate_intent(df.iloc[: i + 1], ctx, closed_only=True)
            intents.append(intent)
            target_exposure = intent_to_signed_target(intent, current_exposure, max_exposure)
            captured.append(
                TargetRecord(
                    stage=stage,
                    fold=fold,
                    timestamp=ts,
                    sleeve_label=sleeve_label,
                    asset=asset,
                    native_timeframe=native_timeframe,
                    strategy_id=intent.strategy_id,
                    action=intent.action.value,
                    desired_exposure_frac=float(intent.desired_exposure_frac),
                    signed_target_exposure=float(target_exposure),
                    sequence_number=i,
                )
            )
            reason = intent.reason
            strategy_id = intent.strategy_id
        else:
            assert replay_map is not None
            record = replay_map[ts]
            target_exposure = float(record.signed_target_exposure)
            reason = f"campaign52_replay:{record.action}"
            strategy_id = record.strategy_id

        cooldown_ok = (i - last_trade_bar) >= exec_config.cooldown_bars
        delta = target_exposure - current_exposure
        if abs(delta) >= rebalance_threshold and cooldown_ok:
            direction = "BUY" if delta > 0 else "SELL"
            target_position_value = nav * target_exposure
            current_position_value = position_units * close_price
            trade_notional = abs(target_position_value - current_position_value)
            fill = compute_fill(
                mid_price=close_price,
                notional=trade_notional,
                nav=nav,
                atr_pct=atr_pct,
                direction=direction,
                config=exec_config,
            )
            if direction == "BUY":
                units_traded = trade_notional / fill.effective_price
                position_units += units_traded
                cash -= trade_notional + fill.fee_usd
            else:
                units_traded = trade_notional / fill.effective_price
                position_units -= units_traded
                if target_exposure >= 0:
                    position_units = max(0.0, position_units)
                cash += trade_notional - fill.fee_usd

            nav = cash + position_units * close_price
            prev_exposure = current_exposure
            current_exposure = (position_units * close_price) / nav if nav > 0 else 0.0
            last_trade_bar = i
            trades.append(
                TradeRecord(
                    bar_index=i,
                    timestamp=str(df.index[i]),
                    direction=direction,
                    mid_price=close_price,
                    effective_price=round(fill.effective_price, 6),
                    qty=units_traded,
                    notional_usd=trade_notional,
                    fee_usd=round(fill.fee_usd, 6),
                    slippage_usd=round(fill.slippage_usd, 6),
                    spread_usd=round(fill.spread_usd, 6),
                    cost_bps=round(fill.cost_bps, 4),
                    prev_exposure=round(prev_exposure, 6),
                    new_exposure=round(current_exposure, 6),
                    reason=reason,
                    strategy_id=strategy_id,
                )
            )

        equity_arr[i] = nav
        position_arr[i] = current_exposure

    result = BacktestResult(
        equity_curve=pd.Series(equity_arr, index=df.index, name="equity"),
        position_series=pd.Series(position_arr, index=df.index, name="exposure"),
        regime_series=pd.Series(regime_labels, index=df.index, name="regime", dtype=object),
        intent_series=intents,
        trades=trades,
        params={
            "initial_capital": initial_capital,
            "taker_fee_rate": exec_config.taker_fee_rate,
            "base_slippage_bps": exec_config.base_slippage_bps,
            "slippage_vol_factor": exec_config.slippage_vol_factor,
            "cooldown_bars": exec_config.cooldown_bars,
            "max_exposure": max_exposure,
            "rebalance_threshold": rebalance_threshold,
            "campaign52_mode": "capture" if capture_mode else "replay",
        },
    )
    return CaptureReplayResult(result=result, targets=captured if capture_mode else list(target_records or ()))


def serialize_targets(records: Iterable[TargetRecord], path: Path) -> None:
    """Write deterministic Campaign #52 target CSV serialization."""
    rows = sorted(
        records,
        key=lambda r: (r.stage, r.fold, r.sleeve_label, pd.Timestamp(r.timestamp), r.sequence_number),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(TARGET_HEADER)
        for record in rows:
            ts = pd.Timestamp(record.timestamp)
            if ts.tzinfo is not None:
                ts = ts.tz_convert("UTC").tz_localize(None)
            writer.writerow(
                (
                    record.stage,
                    record.fold,
                    ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    record.sleeve_label,
                    record.asset,
                    record.native_timeframe,
                    record.strategy_id,
                    record.action,
                    f"{record.desired_exposure_frac:.12f}",
                    f"{record.signed_target_exposure:.12f}",
                    record.sequence_number,
                )
            )
