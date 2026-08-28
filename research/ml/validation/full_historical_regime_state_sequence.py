"""Deterministic source-only historical regime state ledger for Campaign #46."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.contracts import RegimeLabel, RegimeSignal

FROZEN_LABELS = (
    "UNKNOWN", "HIGH_VOL", "VOL_EXPANSION", "TREND_UP",
    "TREND_DOWN", "VOL_COMPRESSION", "RANGE",
)
FROZEN_DEFAULTS = {
    "fast_ema": 21,
    "slow_ema": 55,
    "atr_period": 14,
    "high_vol_threshold": 0.04,
    "mid_vol_threshold": 0.025,
    "compression_threshold": 0.012,
    "vol_expansion_lookback": 5,
    "momentum_lookback": 5,
    "min_bars": 60,
}
SOURCE_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
STATE_COLUMNS = (
    "bar_index", "timestamp", "regime_label", "confidence", "reason",
    "atr_pct", "atr_accel", "ema_roc", "ema_spread", "is_warmup",
    "source_row_digest",
)
RUN_COLUMNS = (
    "state_run_id", "state_run_ordinal", "regime_label", "start_bar_index",
    "end_bar_index", "start_timestamp", "end_timestamp", "duration_bars",
    "entered_from_regime_label", "exited_to_regime_label",
)
TRANSITION_COLUMNS = (
    "transition_id", "transition_ordinal", "anchor_bar_index", "anchor_timestamp",
    "prior_regime_label", "current_regime_label", "ordered_transition",
    "prior_state_start_timestamp", "prior_state_duration_bars",
    "prior_transition_timestamp", "spacing_since_prior_transition_bars",
    "spacing_since_prior_transition_hours", "current_state_age_bars",
    "anchor_source_row_digest",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iso_timestamp(value: Any) -> str:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        raise ValueError("timestamps must be timezone-naive")
    return ts.strftime("%Y-%m-%dT%H:%M:%S")


def validate_engine(engine: BaselineRegimeEngine) -> None:
    actual = {name: getattr(engine, name) for name in FROZEN_DEFAULTS}
    if actual != FROZEN_DEFAULTS:
        raise ValueError(f"classifier defaults mismatch: {actual}")
    labels = tuple(label.value for label in RegimeLabel)
    if labels != ("TREND_UP", "TREND_DOWN", "RANGE", "VOL_COMPRESSION", "VOL_EXPANSION", "HIGH_VOL", "UNKNOWN"):
        raise ValueError(f"regime labels mismatch: {labels}")
    if set(labels) != set(FROZEN_LABELS):
        raise ValueError("frozen regime label set mismatch")


def validate_ohlcv(df: pd.DataFrame) -> dict[str, Any]:
    if tuple(df.columns) != SOURCE_COLUMNS:
        raise ValueError(f"ordered schema mismatch: {tuple(df.columns)}")
    parsed = pd.to_datetime(df["timestamp"], errors="raise")
    if getattr(parsed.dt, "tz", None) is not None:
        raise ValueError("timestamps must be timezone-naive")
    if parsed.duplicated().any() or not parsed.is_monotonic_increasing:
        raise ValueError("timestamps must be unique and strictly increasing")
    if not ((parsed.dt.minute == 0) & (parsed.dt.second == 0) & (parsed.dt.microsecond == 0)).all():
        raise ValueError("timestamps must align to exact hours")
    numeric = df[list(SOURCE_COLUMNS[1:])].apply(pd.to_numeric, errors="raise")
    if not all(math.isfinite(float(v)) for v in numeric.to_numpy().ravel()):
        raise ValueError("non-finite OHLCV value")
    if (numeric[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC values must be positive")
    if (numeric["volume"] < 0).any():
        raise ValueError("volume must be nonnegative")
    if (numeric["high"] < numeric[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("invalid high")
    if (numeric["low"] > numeric[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("invalid low")
    diffs = parsed.diff().dropna().dt.total_seconds().div(3600)
    discontinuities = diffs[diffs != 1]
    missing = int(sum(int(hours) - 1 for hours in discontinuities))
    return {
        "row_count": len(df),
        "first_timestamp": parsed.iloc[0].strftime("%Y-%m-%d %H:%M:%S"),
        "last_timestamp": parsed.iloc[-1].strftime("%Y-%m-%d %H:%M:%S"),
        "discontinuity_count": int(len(discontinuities)),
        "missing_timestamp_count": missing,
        "largest_elapsed_hours": int(discontinuities.max()) if len(discontinuities) else 1,
        "largest_missing_timestamp_count": int(discontinuities.max() - 1) if len(discontinuities) else 0,
    }


def engine_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="raise")
    out = out.set_index("timestamp")
    return out[["open", "high", "low", "close", "volume"]].astype(float)


def source_row_digest(row: pd.Series) -> str:
    values = [iso_timestamp(row["timestamp"])] + [format(float(row[c]), ".17g") for c in SOURCE_COLUMNS[1:]]
    return sha256_bytes("|".join(values).encode("utf-8"))


def build_state_rows(df: pd.DataFrame, signals: list[RegimeSignal]) -> list[dict[str, Any]]:
    if len(df) != len(signals):
        raise ValueError("state/source row count mismatch")
    rows: list[dict[str, Any]] = []
    for i, (src_idx, src) in enumerate(df.iterrows()):
        sig = signals[i]
        expected_ts = iso_timestamp(src["timestamp"])
        if sig.bar_index != i or iso_timestamp(sig.timestamp) != expected_ts:
            raise ValueError(f"signal reconciliation failed at row {i}")
        sub = sig.sub_signals
        reason = sub.get("reason")
        if not reason:
            raise ValueError(f"missing reason at row {i}")
        label = sig.label.value
        row = {
            "bar_index": i,
            "timestamp": expected_ts,
            "regime_label": label,
            "confidence": float(sig.confidence),
            "reason": str(reason),
            "atr_pct": _finite_or_none(sub.get("atr_pct")),
            "atr_accel": _finite_or_none(sub.get("atr_accel")),
            "ema_roc": _finite_or_none(sub.get("ema_roc")),
            "ema_spread": _finite_or_none(sub.get("ema_spread")),
            "is_warmup": label == "UNKNOWN" and reason == "warmup",
            "source_row_digest": source_row_digest(src),
        }
        rows.append(row)
    return rows


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite classifier output")
    return value


def build_state_runs(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not states:
        return []
    runs: list[dict[str, Any]] = []
    start = 0
    for i in range(1, len(states) + 1):
        boundary = i == len(states) or states[i]["regime_label"] != states[i - 1]["regime_label"]
        if not boundary:
            continue
        first, last = states[start], states[i - 1]
        label = first["regime_label"]
        entered = states[start - 1]["regime_label"] if start > 0 else None
        exited = states[i]["regime_label"] if i < len(states) else None
        key = f"{label}|{start}|{i-1}|{first['timestamp']}|{last['timestamp']}"
        runs.append({
            "state_run_id": sha256_bytes(key.encode()),
            "state_run_ordinal": len(runs),
            "regime_label": label,
            "start_bar_index": start,
            "end_bar_index": i - 1,
            "start_timestamp": first["timestamp"],
            "end_timestamp": last["timestamp"],
            "duration_bars": i - start,
            "entered_from_regime_label": entered,
            "exited_to_regime_label": exited,
        })
        start = i
    return runs


def build_transitions(states: list[dict[str, Any]], runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    transitions: list[dict[str, Any]] = []
    prior_transition: dict[str, Any] | None = None
    for run_idx in range(1, len(runs)):
        prior_run, current_run = runs[run_idx - 1], runs[run_idx]
        anchor_idx = current_run["start_bar_index"]
        anchor = states[anchor_idx]
        key = f"{prior_run['regime_label']}|{current_run['regime_label']}|{anchor_idx}|{anchor['timestamp']}"
        row = {
            "transition_id": sha256_bytes(key.encode()),
            "transition_ordinal": len(transitions),
            "anchor_bar_index": anchor_idx,
            "anchor_timestamp": anchor["timestamp"],
            "prior_regime_label": prior_run["regime_label"],
            "current_regime_label": current_run["regime_label"],
            "ordered_transition": f"{prior_run['regime_label']} -> {current_run['regime_label']}",
            "prior_state_start_timestamp": prior_run["start_timestamp"],
            "prior_state_duration_bars": prior_run["duration_bars"],
            "prior_transition_timestamp": prior_transition["anchor_timestamp"] if prior_transition else None,
            "spacing_since_prior_transition_bars": anchor_idx - prior_transition["anchor_bar_index"] if prior_transition else None,
            "spacing_since_prior_transition_hours": _hours_between(prior_transition["anchor_timestamp"], anchor["timestamp"]) if prior_transition else None,
            "current_state_age_bars": 1,
            "anchor_source_row_digest": anchor["source_row_digest"],
        }
        transitions.append(row)
        prior_transition = row
    return transitions


def _hours_between(a: str, b: str) -> int:
    seconds = (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()
    if seconds % 3600:
        raise ValueError("transition timestamps are not whole-hour aligned")
    return int(seconds // 3600)


def purge_transitions(transitions: list[dict[str, Any]], hours: int = 168) -> list[dict[str, Any]]:
    eligible = [t for t in transitions if "UNKNOWN" not in (t["prior_regime_label"], t["current_regime_label"])]
    eligible.sort(key=lambda x: (x["anchor_timestamp"], x["anchor_bar_index"], x["transition_id"]))
    timestamps = [t["anchor_timestamp"] for t in eligible]
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("duplicate transition anchor timestamp")
    selected: list[dict[str, Any]] = []
    for row in eligible:
        if not selected or _hours_between(selected[-1]["anchor_timestamp"], row["anchor_timestamp"]) >= hours:
            selected.append(row)
    return selected


def allocate_folds(purged: list[dict[str, Any]]) -> list[dict[str, Any]]:
    n = len(purged)
    base, remainder = divmod(n, 3)
    sizes = [base + (1 if remainder >= 1 else 0), base + (1 if remainder >= 2 else 0), base]
    rows: list[dict[str, Any]] = []
    cursor = 0
    for fold, size in enumerate(sizes):
        for row in purged[cursor:cursor + size]:
            rows.append({"fold": fold, "transition_id": row["transition_id"], "anchor_timestamp": row["anchor_timestamp"]})
        cursor += size
    return rows


def support_summary(transitions: list[dict[str, Any]], purged: list[dict[str, Any]], folds: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [t for t in transitions if "UNKNOWN" not in (t["prior_regime_label"], t["current_regime_label"])]
    fold_counts = [sum(1 for row in folds if row["fold"] == i) for i in range(3)]
    by_category: dict[str, int] = {}
    for row in eligible:
        by_category[row["ordered_transition"]] = by_category.get(row["ordered_transition"], 0) + 1
    if len(purged) < 20:
        status = "INSUFFICIENT_OVERALL_SUPPORT"
    elif any(count < 5 for count in fold_counts):
        status = "INSUFFICIENT_FOLD_SUPPORT"
    else:
        status = "CAMPAIGN_45_SOURCE_FEASIBLE"
    return {
        "status": status,
        "total_transition_count": len(transitions),
        "eligible_non_unknown_transition_count": len(eligible),
        "purged_transition_count": len(purged),
        "fold_counts": fold_counts,
        "overall_minimum_met": len(purged) >= 20,
        "each_fold_minimum_met": all(count >= 5 for count in fold_counts),
        "eligible_counts_by_ordered_transition": dict(sorted(by_category.items())),
        "predictive_outcomes_generated": False,
    }


def json_text(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"


def csv_text(rows: list[dict[str, Any]], columns: Iterable[str]) -> str:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def classify_source(df: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    engine = BaselineRegimeEngine()
    validate_engine(engine)
    signals = engine.classify_dataframe(engine_frame(df))
    states = build_state_rows(df, signals)
    runs = build_state_runs(states)
    transitions = build_transitions(states, runs)
    purged = purge_transitions(transitions)
    folds = allocate_folds(purged)
    summary = support_summary(transitions, purged, folds)
    if sum(r["duration_bars"] for r in runs) != len(states):
        raise ValueError("state-run reconciliation failed")
    if transitions and len(transitions) != len(runs) - 1:
        raise ValueError("transition/run reconciliation failed")
    return states, runs, transitions, folds, summary
