#!/usr/bin/env python
"""Replay-validate a Core v1 paper export package against research/strategy logic.

Given an export directory produced by ``scripts/export_core_v1_paper_data.py``,
this tool:

1. Loads and structurally validates the export (required files present,
   rows parseable, required sleeves represented).
2. Reconstructs, per (cycle, sleeve), the exact bar the live paper runtime
   used (asset, timeframe, OHLCV, bar timestamp) from ``market_data.jsonl``.
3. Where enough historical bars are available in the export, independently
   recomputes the expected signal for that bar by calling the *same*
   research strategy functions the live runtime uses
   (``research.strategies.REGISTRY``, ``research.regimes.BaselineRegimeEngine``)
   and compares the result to what the runtime actually logged in
   ``signals.jsonl``.
4. Cross-checks the fill timeline (``fills.jsonl``) against the signals log
   for basic consistency (fill counts, chronology, side/qty/price sanity).

This is a read-only validation/reporting tool. It never modifies strategy,
allocation, execution, or dashboard code, and it never fabricates data — if
a required export file is missing, it fails clearly instead of guessing.

The report separates three independent questions, so a lookback limitation
never masquerades as data corruption:

- **Export integrity** — is the export well-formed and internally
  self-consistent (required files present, rows parse, timestamps valid,
  required sleeves present, cycle structure valid, and the signals/
  market_data logs agree with each other)? PASS/FAIL only — insufficient
  historical lookback is *not* an integrity problem.
- **Replay capability** — could signal recomputation actually be attempted?
  PASS if sufficient history existed, PARTIAL if only decision bars were
  available (the expected case for a single export snapshot), FAIL only if
  replay could not be attempted at all because the export is malformed or
  the strategy stack failed to import.
- **Runtime consistency** — where recomputation *was* attempted, did it
  agree with what the runtime logged, and is the fill timeline internally
  consistent? PASS/FAIL — a genuine behavioral finding, independent of
  lookback availability.

Overall status is PASS only if replay fully succeeded, PARTIAL if the
export is valid but lacks enough history to fully recompute signals, and
FAIL only if the export itself is invalid, corrupted, or internally
inconsistent.

Important limitation — read this before trusting a "PASS"
-----------------------------------------------------------
The live runtime's market-data export (see ``market_data_bar_row`` in
``scripts/run_core_v1_paper_live.py``) records only the *single last bar*
each strategy call used, not the full historical lookback window (e.g. a
175/200-day SMA needs ~180-205 daily bars; this tool only ever sees the one
bar per sleeve per cycle that was exported). It also does not record the
derived cross-asset columns (``btc_above_sma175``, ``btc_extension_sma365``,
``spy_above_sma175``, ``btc_in_parabolic``) the runtime injects before
calling strategy code.

Because of this, signal recomputation is only attempted for a given
(sleeve, cycle) when this tool can assemble at least as many historical
bars for that sleeve, from bars present elsewhere in the same export, as
the runtime itself reported using (the ``window_rows`` field in
``market_data.jsonl``). In practice, a single export snapshot almost never
contains enough bars for this, and cross-asset columns are essentially
never reconstructable from the export alone (strategies fall back to
local-asset approximations, which is a legitimate but different code path
than the runtime took). When recomputation is not possible, this tool says
so honestly and still validates everything it safely can: market data
integrity, cycle structure, bar timestamps, signal log internal
consistency, and fill timeline consistency.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_SLEEVE_LABELS: tuple[str, ...] = (
    "BTC_4H_trend",
    "ETH_1H_trend",
    "ETH_4H_trend",
    "SPY_1D_equity",
    "QQQ_1D_equity",
    "GLD_1D_gold",
)
INFORMATIONAL_SLEEVE_LABELS: tuple[str, ...] = ("BIL_yield",)

EXPOSURE_TOLERANCE = 1e-6

PARTIAL_LOOKBACK_MESSAGE = (
    "PARTIAL: exported market data contains only decision bars, not full "
    "historical windows required to recompute indicators. Signal parity "
    "cannot be fully recomputed from this export."
)


# ─────────────────────────────────────────────────────────────────────────
# Small coercion helpers (export data is a mix of native JSON types and
# CSV strings depending on which sibling file was actually loaded).
# ─────────────────────────────────────────────────────────────────────────


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    return str(value).strip().lower() in ("true", "1", "yes")


def _to_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if value is None or value == "":
        return None
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────
# Export structure validation and loading
# ─────────────────────────────────────────────────────────────────────────


def find_export_file(export_dir: Path, stem: str) -> Path | None:
    """Return the jsonl variant of a log if present, else the csv variant."""
    jsonl_path = export_dir / f"{stem}.jsonl"
    if jsonl_path.exists():
        return jsonl_path
    csv_path = export_dir / f"{stem}.csv"
    if csv_path.exists():
        return csv_path
    return None


def validate_export_structure(export_dir: Path) -> list[str]:
    """Return a list of human-readable problems; empty means structurally OK."""
    problems: list[str] = []
    if not export_dir.exists():
        return [f"export directory does not exist: {export_dir}"]
    if not export_dir.is_dir():
        return [f"export path is not a directory: {export_dir}"]

    if not (export_dir / "manifest.json").exists():
        problems.append("manifest.json: missing")
    if find_export_file(export_dir, "market_data") is None:
        problems.append("market_data.jsonl or market_data.csv: missing")
    if find_export_file(export_dir, "signals") is None:
        problems.append("signals.jsonl or signals.csv: missing")
    if find_export_file(export_dir, "fills") is None:
        problems.append("fills.jsonl or fills.csv: missing")
    if not (export_dir / "state.json").exists():
        problems.append("state.json: missing")
    return problems


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    return list(csv.DictReader(text.splitlines()))


def load_manifest(export_dir: Path) -> dict[str, Any]:
    return json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))


def load_state(export_dir: Path) -> dict[str, Any]:
    return json.loads((export_dir / "state.json").read_text(encoding="utf-8"))


def load_audit_report(export_dir: Path) -> dict[str, Any] | None:
    path = export_dir / "audit_report.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_market_data(export_dir: Path) -> tuple[list[dict[str, Any]], Path]:
    path = find_export_file(export_dir, "market_data")
    assert path is not None
    raw_rows = read_jsonl(path) if path.suffix == ".jsonl" else read_csv_rows(path)
    rows: list[dict[str, Any]] = []
    for r in raw_rows:
        rows.append(
            {
                "cycle": _to_int(r.get("cycle")),
                "sleeve": r.get("sleeve"),
                "asset": r.get("asset"),
                "timeframe": r.get("timeframe"),
                "source": r.get("source"),
                "bar_timestamp": r.get("bar_timestamp"),
                "open": _to_float(r.get("open")),
                "high": _to_float(r.get("high")),
                "low": _to_float(r.get("low")),
                "close": _to_float(r.get("close")),
                "volume": _to_float(r.get("volume")),
                "data_age_hours": _to_float(r.get("data_age_hours")),
                "bar_completed": _to_bool(r.get("bar_completed")),
                "window_rows": _to_int(r.get("window_rows")),
            }
        )
    return rows, path


def flatten_signal_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mirror export_core_v1_paper_data.flatten_signal_events: one row per
    (cycle, sleeve) decision. Duplicated here (not imported) because it is a
    tiny, generic reshape helper, not strategy/runtime logic."""
    rows: list[dict[str, Any]] = []
    for event in events:
        event_ctx = {
            "event_timestamp": event.get("timestamp"),
            "cycle": event.get("cycle"),
            "total_nav": event.get("total_nav"),
            "drawdown_frac": event.get("drawdown_frac"),
        }
        for sig in event.get("signals", []):
            row = dict(event_ctx)
            row.update(sig)
            rows.append(row)
    return rows


def load_signals(export_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Path]:
    """Returns (raw_events, flattened_rows, source_path). raw_events is empty
    when only the CSV variant is available (CSV is already flattened)."""
    path = find_export_file(export_dir, "signals")
    assert path is not None
    if path.suffix == ".jsonl":
        events = read_jsonl(path)
        flat = flatten_signal_events(events)
    else:
        events = []
        flat = read_csv_rows(path)
        for row in flat:
            row["meta"] = _to_dict(row.get("meta"))
            row["fill"] = _to_dict(row.get("fill"))

    rows: list[dict[str, Any]] = []
    for r in flat:
        rows.append(
            {
                "cycle": _to_int(r.get("cycle")),
                "sleeve": r.get("sleeve"),
                "family": r.get("family"),
                "asset": r.get("asset"),
                "timeframe": r.get("timeframe"),
                "strategy": r.get("strategy"),
                "bar_timestamp": r.get("bar_timestamp"),
                "price": _to_float(r.get("price")),
                "regime": r.get("regime"),
                "action": r.get("action"),
                "previous_action": r.get("previous_action"),
                "confidence": _to_float(r.get("confidence")),
                "target_exposure": _to_float(r.get("target_exposure")),
                "current_exposure_before": _to_float(r.get("current_exposure_before")),
                "reason": r.get("reason"),
                "meta": r.get("meta") if isinstance(r.get("meta"), dict) else None,
                "fill": r.get("fill") if isinstance(r.get("fill"), dict) else None,
            }
        )
    return events, rows, path


def load_fills(export_dir: Path) -> tuple[list[dict[str, Any]], Path]:
    path = find_export_file(export_dir, "fills")
    assert path is not None
    raw_rows = read_jsonl(path) if path.suffix == ".jsonl" else read_csv_rows(path)
    rows: list[dict[str, Any]] = []
    for r in raw_rows:
        rows.append(
            {
                "sleeve": r.get("sleeve"),
                "asset": r.get("asset"),
                "timestamp": r.get("timestamp"),
                "side": r.get("side"),
                "qty": _to_float(r.get("qty")),
                "price": _to_float(r.get("price")),
                "notional": _to_float(r.get("notional")),
                "fee": _to_float(r.get("fee")),
            }
        )
    return rows, path


# ─────────────────────────────────────────────────────────────────────────
# Structural validation
# ─────────────────────────────────────────────────────────────────────────


_OHLC_EPSILON = 1e-9


def check_market_data_integrity(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Returns (integrity_issues, freshness_notes).

    integrity_issues are hard export-well-formedness problems: missing
    fields, unparseable timestamps, OHLC values that are not internally
    coherent. These are file/parsing concerns and belong in export
    integrity.

    freshness_notes are informational: e.g. the runtime flagged a bar as
    not-yet-completed (bar_completed=False). That describes a runtime
    data-quality condition, not a malformed export file, so it is reported
    separately and does not affect export integrity.
    """
    import pandas as pd

    issues: list[str] = []
    freshness_notes: list[str] = []
    for r in rows:
        label = f"cycle={r['cycle']} sleeve={r['sleeve']}"
        if r["bar_timestamp"] is None:
            issues.append(f"{label}: missing bar_timestamp")
        elif pd.isna(pd.to_datetime(r["bar_timestamp"], errors="coerce")):
            issues.append(f"{label}: unparseable bar_timestamp {r['bar_timestamp']!r}")
        for field in ("open", "high", "low", "close"):
            if r[field] is None:
                issues.append(f"{label}: missing {field}")
        o, h, l, c = r["open"], r["high"], r["low"], r["close"]
        if None not in (o, h, l, c):
            if h < l - _OHLC_EPSILON:
                issues.append(f"{label}: high {h} < low {l}")
            if h < o - _OHLC_EPSILON or h < c - _OHLC_EPSILON:
                issues.append(f"{label}: high {h} is not the max of open/close")
            if l > o + _OHLC_EPSILON or l > c + _OHLC_EPSILON:
                issues.append(f"{label}: low {l} is not the min of open/close")
            if c <= 0:
                issues.append(f"{label}: non-positive close {c}")
        if r["bar_completed"] is False:
            freshness_notes.append(f"{label}: bar_completed=False — runtime may have used an in-progress candle")
    return issues, freshness_notes


def check_cross_log_consistency(
    market_rows: list[dict[str, Any]], signal_rows: list[dict[str, Any]]
) -> list[str]:
    """The export's own files must agree with each other: for every
    strategy-relevant market_data row, there must be a matching signals row
    for the same (sleeve, cycle) that references the same bar and price.
    This is a self-consistency property of the export, independent of
    whether enough history exists to recompute anything."""
    issues: list[str] = []
    signal_index = {(r["sleeve"], r["cycle"]): r for r in signal_rows}
    for mrow in market_rows:
        if mrow["sleeve"] in INFORMATIONAL_SLEEVE_LABELS:
            continue
        key = (mrow["sleeve"], mrow["cycle"])
        srow = signal_index.get(key)
        label = f"cycle={mrow['cycle']} sleeve={mrow['sleeve']}"
        if srow is None:
            issues.append(f"{label}: market_data row has no matching signals row")
            continue
        if srow["bar_timestamp"] != mrow["bar_timestamp"]:
            issues.append(
                f"{label}: bar_timestamp mismatch between signals ({srow['bar_timestamp']}) "
                f"and market_data ({mrow['bar_timestamp']})"
            )
        if srow["price"] is not None and mrow["close"] is not None and abs(srow["price"] - mrow["close"]) > 1e-6:
            issues.append(f"{label}: logged price {srow['price']} != market_data close {mrow['close']}")
    return issues


def check_required_sleeves_present(rows: list[dict[str, Any]]) -> dict[str, bool]:
    seen = {r["sleeve"] for r in rows}
    return {label: label in seen for label in REQUIRED_SLEEVE_LABELS}


def check_cycles(rows: list[dict[str, Any]]) -> tuple[list[int], list[int], bool]:
    """Returns (sorted_cycles, missing_cycles, ok)."""
    cycles = sorted({r["cycle"] for r in rows if r["cycle"] is not None})
    if not cycles:
        return [], [], False
    full_range = set(range(cycles[0], cycles[-1] + 1))
    missing = sorted(full_range - set(cycles))
    return cycles, missing, True


def check_fill_timeline(
    fills: list[dict[str, Any]], signal_rows: list[dict[str, Any]]
) -> tuple[str, list[str]]:
    issues: list[str] = []
    logged_fill_count = sum(1 for s in signal_rows if s.get("fill"))
    if logged_fill_count != len(fills):
        issues.append(
            f"fills.jsonl/csv has {len(fills)} fill(s) but signals log shows {logged_fill_count} "
            "nested fill(s) — counts should match 1:1"
        )

    timestamps = [f["timestamp"] for f in fills if f.get("timestamp")]
    if timestamps != sorted(timestamps):
        issues.append("fills are not in chronological order")

    known_sleeves = set(REQUIRED_SLEEVE_LABELS) | set(INFORMATIONAL_SLEEVE_LABELS)
    for i, f in enumerate(fills):
        label = f"fill[{i}] sleeve={f.get('sleeve')}"
        if f.get("sleeve") not in known_sleeves:
            issues.append(f"{label}: unrecognized sleeve label")
        if f.get("qty") is not None and f["qty"] <= 0:
            issues.append(f"{label}: non-positive qty {f['qty']}")
        if f.get("price") is not None and f["price"] <= 0:
            issues.append(f"{label}: non-positive price {f['price']}")
        if f.get("side") not in ("BUY", "SELL"):
            issues.append(f"{label}: unrecognized side {f.get('side')!r}")

    if not fills:
        status = "PASS"
    elif issues:
        status = "FAIL"
    else:
        status = "PASS"
    return status, issues


# ─────────────────────────────────────────────────────────────────────────
# Strategy stack import (best-effort — replay degrades gracefully if this
# fails, per the "do not fabricate" requirement)
# ─────────────────────────────────────────────────────────────────────────


class StrategyStack:
    def __init__(self) -> None:
        import sys as _sys

        if str(REPO_ROOT) not in _sys.path:
            _sys.path.insert(0, str(REPO_ROOT))
        from research.regimes.baseline_engine import BaselineRegimeEngine
        from research.regimes.contracts import RegimeLabel
        from research.strategies import REGISTRY
        from research.strategies.contracts import StrategyContext
        from runtime.core_v1.allocation import SELECTED_CORE_V1_SLEEVES

        self.BaselineRegimeEngine = BaselineRegimeEngine
        self.RegimeLabel = RegimeLabel
        self.REGISTRY = REGISTRY
        self.StrategyContext = StrategyContext
        self.sleeves_by_label = {s.label: s for s in SELECTED_CORE_V1_SLEEVES}

    def classify_regime(self, df: Any) -> Any:
        try:
            return self.BaselineRegimeEngine().classify_bar(df, len(df) - 1).label
        except Exception:
            return self.RegimeLabel.UNKNOWN


def try_import_strategy_stack() -> tuple[StrategyStack | None, str | None]:
    try:
        return StrategyStack(), None
    except Exception as e:  # pragma: no cover - environment-dependent
        return None, f"{type(e).__name__}: {e}"


# ─────────────────────────────────────────────────────────────────────────
# Per-sleeve replay
# ─────────────────────────────────────────────────────────────────────────


def build_sleeve_bar_series(market_rows: list[dict[str, Any]], sleeve_label: str) -> Any:
    """Distinct, ascending-sorted OHLCV series assembled from every bar this
    export happens to contain for `sleeve_label`, across all cycles."""
    import pandas as pd

    by_ts: dict[str, dict[str, Any]] = {}
    for r in market_rows:
        if r["sleeve"] != sleeve_label or r["bar_timestamp"] is None:
            continue
        by_ts[r["bar_timestamp"]] = r
    if not by_ts:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    idx = pd.to_datetime(sorted(by_ts.keys()))
    ordered = [by_ts[ts] for ts in sorted(by_ts.keys())]
    df = pd.DataFrame(
        {
            "open": [r["open"] for r in ordered],
            "high": [r["high"] for r in ordered],
            "low": [r["low"] for r in ordered],
            "close": [r["close"] for r in ordered],
            "volume": [r["volume"] for r in ordered],
        },
        index=idx,
    )
    return df.dropna(subset=["open", "high", "low", "close"])


def replay_sleeve(
    sleeve_label: str,
    market_rows: list[dict[str, Any]],
    signal_rows: list[dict[str, Any]],
    stack: StrategyStack | None,
    import_error: str | None,
) -> dict[str, Any]:
    """Per-cycle replay for one sleeve.

    Cross-log structural agreement (does signals.jsonl describe the same bar
    market_data.jsonl does?) is validated once, globally, by
    check_cross_log_consistency — not here. This function only decides,
    per (sleeve, cycle), whether replay was *capable* of running (enough
    history) and, when it was, whether the recomputed result *matches* the
    runtime's logged decision. Those are the two separate questions the
    replay_capability and runtime_consistency report axes answer.
    """
    sleeve_market_rows = [r for r in market_rows if r["sleeve"] == sleeve_label]
    sleeve_signal_rows = {r["cycle"]: r for r in signal_rows if r["sleeve"] == sleeve_label}

    result: dict[str, Any] = {
        "sleeve": sleeve_label,
        "status": "NO_DATA",
        "cycles": [],
        "reasons": [],
    }

    if not sleeve_market_rows:
        result["reasons"].append("no market_data rows found for this sleeve")
        return result

    full_series = build_sleeve_bar_series(market_rows, sleeve_label) if stack is not None else None
    sleeve_meta = stack.sleeves_by_label.get(sleeve_label) if stack is not None else None

    per_cycle: list[dict[str, Any]] = []
    for mrow in sorted(sleeve_market_rows, key=lambda r: (r["cycle"] is None, r["cycle"])):
        srow = sleeve_signal_rows.get(mrow["cycle"])
        cycle_result: dict[str, Any] = {
            "cycle": mrow["cycle"],
            "bar_timestamp": mrow["bar_timestamp"],
            "runtime_price": mrow["close"],
        }

        if srow is None:
            # Already recorded as an export integrity issue by
            # check_cross_log_consistency — nothing further to evaluate here.
            cycle_result["status"] = "NOT_EVALUATED"
            cycle_result["reason"] = "no matching signals row (see export integrity issues)"
            per_cycle.append(cycle_result)
            continue

        cycle_result["runtime_action"] = srow["action"]
        cycle_result["runtime_regime"] = srow["regime"]
        cycle_result["runtime_target_exposure"] = srow["target_exposure"]
        cycle_result["runtime_reason"] = srow["reason"]

        if stack is None or sleeve_meta is None or full_series is None:
            cycle_result["status"] = "STACK_UNAVAILABLE"
            cycle_result["reason"] = f"strategy stack import failed — cannot recompute ({import_error})"
            per_cycle.append(cycle_result)
            continue

        bar_ts = mrow["bar_timestamp"]
        window = full_series[full_series.index <= bar_ts] if bar_ts else full_series.iloc[0:0]
        available_n = len(window)
        required_n = mrow["window_rows"]
        if required_n is None or available_n < required_n:
            cycle_result["status"] = "INSUFFICIENT_HISTORY"
            cycle_result["available_bars"] = available_n
            cycle_result["required_bars"] = required_n
            cycle_result["reason"] = (
                f"export contains {available_n} bar(s) for this sleeve on or before {bar_ts}, "
                f"but the runtime used a {required_n if required_n is not None else 'unknown'}-bar "
                "window for this decision — indicators cannot be recomputed"
            )
            per_cycle.append(cycle_result)
            continue

        try:
            regime = stack.classify_regime(window)
            ctx = stack.StrategyContext(
                regime=regime,
                current_exposure_frac=min(1.0, max(0.0, srow["current_exposure_before"] or 0.0)),
                asset=sleeve_meta.asset,
                bar_index=available_n - 1,
            )
            strategy = stack.REGISTRY[sleeve_meta.strategy]
            intent = strategy.generate_intent(window, ctx, closed_only=True)
        except Exception as e:
            cycle_result["status"] = "FAIL"
            cycle_result["reason"] = f"replay recompute raised {type(e).__name__}: {e}"
            per_cycle.append(cycle_result)
            continue

        replayed_action = intent.action.value if hasattr(intent.action, "value") else str(intent.action)
        replayed_regime = regime.value if hasattr(regime, "value") else str(regime)
        cycle_result["replayed_action"] = replayed_action
        cycle_result["replayed_regime"] = replayed_regime
        cycle_result["replayed_target_exposure"] = float(intent.desired_exposure_frac)
        cycle_result["replayed_reason"] = intent.reason
        cycle_result["fallback_columns_used"] = "btc_above_sma175/btc_extension_sma365/spy_above_sma175/btc_in_parabolic not present in export"

        action_match = replayed_action == srow["action"]
        exposure_match = (
            srow["target_exposure"] is not None
            and abs(intent.desired_exposure_frac - srow["target_exposure"]) <= EXPOSURE_TOLERANCE
        )
        regime_match = replayed_regime == srow["regime"]
        reason_match = (
            isinstance(intent.reason, str)
            and isinstance(srow["reason"], str)
            and intent.reason.strip().lower() == srow["reason"].strip().lower()
        )
        cycle_result["reason_match"] = reason_match

        if action_match and exposure_match and regime_match:
            cycle_result["status"] = "PASS_WITH_FALLBACK"
            cycle_result["reason"] = "recomputed via strategy fallback path (cross-asset columns unavailable in export); result matched runtime"
        else:
            cycle_result["status"] = "MISMATCH"
            mismatch_fields = []
            if not action_match:
                mismatch_fields.append("action")
            if not exposure_match:
                mismatch_fields.append("target_exposure")
            if not regime_match:
                mismatch_fields.append("regime")
            cycle_result["reason"] = (
                "recomputed signal diverges on " + ", ".join(mismatch_fields)
                + " (recompute used strategy fallback path since cross-asset columns are unavailable in export — "
                "divergence may be caused by that fallback rather than a real runtime defect)"
            )
        per_cycle.append(cycle_result)

    result["cycles"] = per_cycle
    statuses = {c["status"] for c in per_cycle if c["status"] != "NOT_EVALUATED"}
    if "FAIL" in statuses or "MISMATCH" in statuses:
        # A genuine recompute-vs-runtime divergence: a runtime_consistency
        # concern, not a lookback limitation.
        result["status"] = "FAIL"
    elif "STACK_UNAVAILABLE" in statuses:
        # Replay mechanism itself is broken — capability concern, not a
        # lookback limitation either.
        result["status"] = "FAIL"
    elif statuses == {"PASS_WITH_FALLBACK"}:
        result["status"] = "PASS"
    elif "PASS_WITH_FALLBACK" in statuses:
        result["status"] = "PARTIAL"
    elif statuses == {"INSUFFICIENT_HISTORY"}:
        result["status"] = "PARTIAL"
        result["reasons"].append("insufficient historical bars in export to recompute any cycle for this sleeve")
    elif not statuses:
        result["status"] = "NO_DATA"
        result["reasons"].append("no runtime-logged signal matched any market_data row for this sleeve")
    else:
        result["status"] = "PARTIAL"
    return result


# ─────────────────────────────────────────────────────────────────────────
# Report assembly
# ─────────────────────────────────────────────────────────────────────────


def build_report(export_dir: Path) -> dict[str, Any]:
    manifest = load_manifest(export_dir)
    state = load_state(export_dir)
    audit_report = load_audit_report(export_dir)

    market_rows, market_path = load_market_data(export_dir)
    events, signal_rows, signals_path = load_signals(export_dir)
    fills, fills_path = load_fills(export_dir)

    integrity_issues, freshness_notes = check_market_data_integrity(market_rows)
    cross_log_issues = check_cross_log_consistency(market_rows, signal_rows)
    sleeves_present = check_required_sleeves_present(market_rows)
    cycles, missing_cycles, cycles_ok = check_cycles(market_rows)
    fill_status, fill_issues = check_fill_timeline(fills, signal_rows)

    stack, import_error = try_import_strategy_stack()

    sleeve_results: dict[str, Any] = {}
    for label in REQUIRED_SLEEVE_LABELS:
        sleeve_results[label] = replay_sleeve(label, market_rows, signal_rows, stack, import_error)

    mismatches: list[dict[str, Any]] = []
    for label, res in sleeve_results.items():
        for c in res["cycles"]:
            if c.get("status") == "MISMATCH":
                mismatches.append({"sleeve": label, **c})

    # ── Axis 1: export integrity ──────────────────────────────────────
    # Is the export itself well-formed and internally self-consistent?
    # Insufficient lookback history is NOT an integrity problem — it is
    # an expected, honest limitation of a single decision-bar export and
    # belongs entirely to axis 2 (replay capability).
    market_data_rows_ok = len(market_rows) > 0 and not integrity_issues
    required_sleeves_present = all(sleeves_present.values())
    export_structure_ok = not validate_export_structure(export_dir)
    export_integrity_issues = list(integrity_issues) + list(cross_log_issues)
    export_integrity_ok = (
        export_structure_ok
        and market_data_rows_ok
        and required_sleeves_present
        and cycles_ok
        and not cross_log_issues
    )
    export_integrity_status = "PASS" if export_integrity_ok else "FAIL"

    # ── Axis 2: replay capability ────────────────────────────────────
    # Could recomputation actually be *attempted*? This says nothing
    # about whether the recomputed result agreed with the runtime.
    all_cycle_statuses = [c["status"] for res in sleeve_results.values() for c in res["cycles"]]
    attempted_statuses = {"PASS_WITH_FALLBACK", "MISMATCH"}
    capable_cycle_exists = any(s in attempted_statuses for s in all_cycle_statuses)
    insufficient_cycle_exists = "INSUFFICIENT_HISTORY" in all_cycle_statuses
    stack_unavailable = stack is None or "STACK_UNAVAILABLE" in all_cycle_statuses

    if export_integrity_status == "FAIL" or stack_unavailable:
        replay_capability_status = "FAIL"
    elif capable_cycle_exists and not insufficient_cycle_exists:
        replay_capability_status = "PASS"
    else:
        # Either nothing could be attempted (decision-bars-only export —
        # the common, expected case) or a mix of capable/insufficient
        # cycles. Either way replay is only partially possible, not broken.
        replay_capability_status = "PARTIAL"

    replay_possible = capable_cycle_exists

    # ── Axis 3: runtime consistency ──────────────────────────────────
    # Where replay *was* attempted, did it agree with the runtime? And is
    # the fill timeline internally consistent? Both are genuine behavioral
    # findings, independent of lookback availability.
    mismatch_exists = any(s == "MISMATCH" for s in all_cycle_statuses)
    runtime_consistency_status = "FAIL" if (mismatch_exists or fill_status == "FAIL") else "PASS"

    signal_events_loaded = len(signal_rows) > 0
    fills_loaded_ok = True  # zero fills is a valid, loadable state
    audit_report_present = audit_report is not None
    state_snapshot_present = bool(state)

    # ── Overall status ────────────────────────────────────────────────
    # PASS only if the export is valid, consistent, and replay fully
    # succeeded. PARTIAL if the export is valid and consistent but lacks
    # enough historical context to fully recompute signals. FAIL only if
    # the export itself is invalid, corrupted, or internally inconsistent.
    if export_integrity_status == "FAIL" or runtime_consistency_status == "FAIL":
        overall_status = "FAIL"
    elif replay_capability_status != "PASS":
        overall_status = "PARTIAL"
    else:
        overall_status = "PASS"

    limitations: list[str] = []
    if replay_capability_status == "PARTIAL" and not stack_unavailable:
        limitations.append(PARTIAL_LOOKBACK_MESSAGE)
    if stack is None:
        limitations.append(f"strategy stack import failed — signal recomputation skipped entirely ({import_error})")
    if freshness_notes:
        limitations.append(
            f"{len(freshness_notes)} bar(s) flagged bar_completed=False by the runtime "
            "(informational data-quality note — does not affect export integrity)"
        )

    report: dict[str, Any] = {
        "export_dir": str(export_dir),
        "replay_timestamp": datetime.now(UTC).isoformat(),
        "manifest_export_timestamp": manifest.get("export_timestamp"),
        "runtime_git_commit": manifest.get("git_commit"),
        "runtime_git_branch": manifest.get("git_branch"),
        "runtime_version": manifest.get("runtime_version"),
        "loaded": {
            "market_data_rows": len(market_rows),
            "cycles": len(cycles),
            "signal_events": len(events) if events else len({r["cycle"] for r in signal_rows if r["cycle"] is not None}),
            "signal_rows": len(signal_rows),
            "fills": len(fills),
        },
        "sources": {
            "market_data": str(market_path),
            "signals": str(signals_path),
            "fills": str(fills_path),
        },
        "validation": {
            "export_integrity_status": export_integrity_status,
            "replay_capability_status": replay_capability_status,
            "runtime_consistency_status": runtime_consistency_status,
            "fill_timeline_status": fill_status,
            "overall_status": overall_status,
            # Detail fields underlying the three axes above.
            "export_structure_ok": export_structure_ok,
            "market_data_rows_ok": market_data_rows_ok,
            "required_sleeves_present": required_sleeves_present,
            "cycles_contiguous_or_explained": cycles_ok,
            "signal_events_loaded": signal_events_loaded,
            "fills_loaded": fills_loaded_ok,
            "audit_report_present": audit_report_present,
            "state_snapshot_present": state_snapshot_present,
            "replay_possible": replay_possible,
        },
        "required_sleeves_present_detail": sleeves_present,
        "cycles": cycles,
        "missing_cycles": missing_cycles,
        "export_integrity_issues": export_integrity_issues,
        "market_data_integrity_issues": integrity_issues,
        "cross_log_consistency_issues": cross_log_issues,
        "bar_freshness_notes": freshness_notes,
        "fill_timeline_issues": fill_issues,
        "strategy_import_ok": stack is not None,
        "strategy_import_error": import_error,
        "sleeve_results": sleeve_results,
        "mismatches": mismatches,
        "limitations": limitations,
    }
    return report


# ─────────────────────────────────────────────────────────────────────────
# Output writers
# ─────────────────────────────────────────────────────────────────────────


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")


def write_csv_reports(report: dict[str, Any], out_dir: Path) -> None:
    rows: list[dict[str, Any]] = []
    for label, res in report["sleeve_results"].items():
        for c in res["cycles"]:
            rows.append({"sleeve": label, "sleeve_status": res["status"], **c})

    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    replay_csv = out_dir / "replay_report.csv"
    with replay_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    if report["mismatches"]:
        mismatch_fieldnames: list[str] = []
        mseen: set[str] = set()
        for row in report["mismatches"]:
            for key in row:
                if key not in mseen:
                    mseen.add(key)
                    mismatch_fieldnames.append(key)
        with (out_dir / "mismatches.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=mismatch_fieldnames, restval="", extrasaction="ignore")
            writer.writeheader()
            for row in report["mismatches"]:
                writer.writerow(row)


def render_terminal_report(report: dict[str, Any]) -> str:
    v = report["validation"]
    loaded = report["loaded"]
    lines: list[str] = []
    lines.append("Core v1 Replay Validation")
    lines.append(f"Export: {report['export_dir']}")
    lines.append(f"Runtime branch: {report['runtime_git_branch']}")
    lines.append(f"Runtime commit: {report['runtime_git_commit']}")
    lines.append(f"Replay timestamp: {report['replay_timestamp']}")
    lines.append("")
    lines.append("Loaded:")
    lines.append(f"- market data rows: {loaded['market_data_rows']}")
    lines.append(f"- cycles: {loaded['cycles']}")
    lines.append(f"- signal events: {loaded['signal_events']}")
    lines.append(f"- fills: {loaded['fills']}")
    lines.append("")
    lines.append("Validation:")
    lines.append(f"- export integrity: {v['export_integrity_status']}")
    lines.append(f"- replay capability: {v['replay_capability_status']}")
    lines.append(f"- runtime consistency: {v['runtime_consistency_status']}")
    lines.append(f"- fill timeline consistency: {v['fill_timeline_status']}")
    lines.append(f"- audit report included: {'yes' if v['audit_report_present'] else 'no'}")
    lines.append(f"- state snapshot included: {'yes' if v['state_snapshot_present'] else 'no'}")
    if v["export_integrity_status"] == "FAIL" and report["export_integrity_issues"]:
        lines.append("")
        lines.append("Export integrity issues:")
        for issue in report["export_integrity_issues"]:
            lines.append(f"- {issue}")
    lines.append("")
    lines.append("Sleeve Results:")
    for label, res in report["sleeve_results"].items():
        lines.append(f"{label}: {res['status']}")
    lines.append("")
    lines.append("Mismatches:")
    if report["mismatches"]:
        for m in report["mismatches"]:
            lines.append(f"- {m['sleeve']} cycle={m.get('cycle')}: {m.get('reason')}")
    else:
        lines.append("- none")
    if report["limitations"]:
        lines.append("")
        lines.append("Limitations:")
        for limitation in report["limitations"]:
            lines.append(f"- {limitation}")
    lines.append("")
    lines.append("Overall:")
    lines.append(v["overall_status"])
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Replay-validate a Core v1 paper export against research strategy logic"
    )
    p.add_argument("export_dir", help="Export directory produced by scripts/export_core_v1_paper_data.py")
    p.add_argument("--strict", action="store_true", help="Exit nonzero on PARTIAL as well as FAIL")
    p.add_argument("--json", action="store_true", help="Print the JSON report summary to stdout")
    p.add_argument("--output-dir", default=None, help="Override the machine-readable report destination")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    export_dir = Path(args.export_dir)

    structure_problems = validate_export_structure(export_dir)
    if structure_problems:
        print(
            "Core v1 replay aborted — export directory is missing required file(s):",
            file=sys.stderr,
        )
        for p in structure_problems:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(2)

    report = build_report(export_dir)

    out_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "artifacts" / "core_v1_replay_reports" / export_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json_report(report, out_dir / "replay_report.json")
    write_csv_reports(report, out_dir)
    terminal_report = render_terminal_report(report)
    (out_dir / "summary.txt").write_text(terminal_report + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(terminal_report)
        print(f"\nMachine-readable report written to {out_dir}", file=sys.stderr)

    overall = report["validation"]["overall_status"]
    if overall == "FAIL":
        raise SystemExit(2)
    if overall == "PARTIAL" and args.strict:
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
