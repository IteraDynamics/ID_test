from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


UTC = timezone.utc
TIMESTAMP_NAMES = {
    "timestamp",
    "time",
    "datetime",
    "date",
    "as_of",
    "asof",
    "updated_at",
    "created_at",
    "cycle_at",
    "cycle_time",
    "last_cycle",
    "last_update",
    "bar_timestamp",
    "bar_time",
    "signal_timestamp",
    "fill_timestamp",
}


@dataclass(frozen=True)
class FileObservation:
    path: str
    exists: bool
    mtime_utc: str | None
    size_bytes: int | None


@dataclass(frozen=True)
class ProbeObservation:
    observed_at_utc: str
    next_hour_utc: str
    seconds_to_next_hour: float
    btc_latest_bar_timestamp_utc: str | None
    btc_latest_bar_close_utc: str | None
    btc_bar_age_seconds: float | None
    eth_latest_bar_timestamp_utc: str | None
    eth_latest_bar_close_utc: str | None
    eth_bar_age_seconds: float | None
    core_state_latest_embedded_timestamp_utc: str | None
    core_state_age_seconds: float | None
    btc_file: FileObservation
    eth_file: FileObservation
    core_state_file: FileObservation
    ready_for_shadow_decision: bool
    reason_codes: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Observation-only cadence probe for Core v1 + Jump Risk paper integration. "
            "It never changes allocations, NAV, orders, fills, or runtime state."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--btc-data", required=True, help="Live BTC hourly OHLCV CSV used by the runtime")
    parser.add_argument("--eth-data", required=True, help="Live ETH hourly OHLCV CSV used by the runtime")
    parser.add_argument("--core-state", required=True, help="Core v1 paper state JSON")
    parser.add_argument("--out-dir", default="artifacts/jump_risk_runtime_cadence")
    parser.add_argument("--run-name", default="jump-risk-runtime-cadence-probe-v0")
    parser.add_argument("--duration-seconds", type=float, default=3900.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument(
        "--bar-timestamp-semantics",
        choices=("open", "close"),
        default="open",
        help="Whether each hourly CSV timestamp denotes the bar open or bar close",
    )
    parser.add_argument(
        "--max-finalized-bar-age-seconds",
        type=float,
        default=4500.0,
        help="Fail closed when the newest completed hourly bar is older than this",
    )
    parser.add_argument(
        "--max-core-state-age-seconds",
        type=float,
        default=900.0,
        help="Fail closed when the newest Core state timestamp is older than this",
    )
    parser.add_argument(
        "--decision-safety-margin-seconds",
        type=float,
        default=300.0,
        help="Minimum time required before the next hourly boundary",
    )
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | pd.Timestamp | None) -> str | None:
    if value is None:
        return None
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("UTC")
    else:
        parsed = parsed.tz_convert("UTC")
    return parsed.isoformat()


def next_hour(now: datetime) -> datetime:
    stamp = pd.Timestamp(now).tz_convert("UTC")
    return (stamp.floor("h") + pd.Timedelta(hours=1)).to_pydatetime()


def file_observation(path: Path) -> FileObservation:
    if not path.exists():
        return FileObservation(str(path), False, None, None)
    stat = path.stat()
    return FileObservation(
        path=str(path),
        exists=True,
        mtime_utc=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
        size_bytes=int(stat.st_size),
    )


def detect_timestamp_column(path: Path) -> str:
    columns = list(pd.read_csv(path, nrows=0).columns)
    lowered = {str(column).strip().lower(): str(column) for column in columns}
    for name in ("timestamp", "datetime", "date", "time"):
        if name in lowered:
            return lowered[name]
    if not columns:
        raise ValueError(f"CSV has no columns: {path}")
    return str(columns[0])


def latest_csv_timestamp(path: Path) -> pd.Timestamp | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    timestamp_column = detect_timestamp_column(path)
    frame = pd.read_csv(path, usecols=[timestamp_column])
    parsed = pd.to_datetime(frame[timestamp_column], utc=True, errors="coerce").dropna()
    if parsed.empty:
        return None
    return pd.Timestamp(parsed.max()).tz_convert("UTC")


def bar_close(timestamp: pd.Timestamp | None, semantics: str) -> pd.Timestamp | None:
    if timestamp is None:
        return None
    return timestamp + pd.Timedelta(hours=1) if semantics == "open" else timestamp


def parse_timestamp(value: Any) -> pd.Timestamp | None:
    if value is None or isinstance(value, (dict, list, tuple, bool)):
        return None
    try:
        parsed = pd.to_datetime(value, utc=True, errors="coerce")
    except (TypeError, ValueError, OverflowError):
        return None
    if isinstance(parsed, pd.DatetimeIndex):
        return None
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).tz_convert("UTC")


def collect_embedded_timestamps(value: Any, parent_key: str = "") -> list[pd.Timestamp]:
    found: list[pd.Timestamp] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).strip().lower()
            if key_text in TIMESTAMP_NAMES or any(token in key_text for token in ("timestamp", "updated", "cycle", "as_of")):
                parsed = parse_timestamp(child)
                if parsed is not None:
                    found.append(parsed)
            found.extend(collect_embedded_timestamps(child, key_text))
    elif isinstance(value, list):
        for child in value:
            found.extend(collect_embedded_timestamps(child, parent_key))
    return found


def latest_state_timestamp(path: Path) -> pd.Timestamp | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    timestamps = collect_embedded_timestamps(payload)
    if timestamps:
        return max(timestamps)
    return pd.Timestamp(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))


def age_seconds(now: datetime, value: pd.Timestamp | None) -> float | None:
    if value is None:
        return None
    return float((pd.Timestamp(now) - value).total_seconds())


def observe(args: argparse.Namespace) -> ProbeObservation:
    now = utc_now()
    boundary = next_hour(now)
    btc_path = Path(args.btc_data)
    eth_path = Path(args.eth_data)
    state_path = Path(args.core_state)

    btc_timestamp = latest_csv_timestamp(btc_path)
    eth_timestamp = latest_csv_timestamp(eth_path)
    btc_close = bar_close(btc_timestamp, args.bar_timestamp_semantics)
    eth_close = bar_close(eth_timestamp, args.bar_timestamp_semantics)
    state_timestamp = latest_state_timestamp(state_path)

    btc_age = age_seconds(now, btc_close)
    eth_age = age_seconds(now, eth_close)
    state_age = age_seconds(now, state_timestamp)
    margin = float((boundary - now).total_seconds())

    reasons: list[str] = []
    if btc_close is None:
        reasons.append("BTC_BAR_MISSING")
    elif btc_close > pd.Timestamp(now):
        reasons.append("BTC_BAR_NOT_CLOSED")
    elif btc_age is None or btc_age > args.max_finalized_bar_age_seconds:
        reasons.append("BTC_BAR_STALE")

    if eth_close is None:
        reasons.append("ETH_BAR_MISSING")
    elif eth_close > pd.Timestamp(now):
        reasons.append("ETH_BAR_NOT_CLOSED")
    elif eth_age is None or eth_age > args.max_finalized_bar_age_seconds:
        reasons.append("ETH_BAR_STALE")

    if state_timestamp is None:
        reasons.append("CORE_STATE_TIMESTAMP_MISSING")
    elif state_timestamp > pd.Timestamp(now) + pd.Timedelta(seconds=5):
        reasons.append("CORE_STATE_TIMESTAMP_IN_FUTURE")
    elif state_age is None or state_age > args.max_core_state_age_seconds:
        reasons.append("CORE_STATE_STALE")

    if margin < args.decision_safety_margin_seconds:
        reasons.append("INSUFFICIENT_NEXT_HOUR_MARGIN")

    ready = not reasons
    return ProbeObservation(
        observed_at_utc=now.isoformat(),
        next_hour_utc=boundary.isoformat(),
        seconds_to_next_hour=margin,
        btc_latest_bar_timestamp_utc=iso(btc_timestamp),
        btc_latest_bar_close_utc=iso(btc_close),
        btc_bar_age_seconds=btc_age,
        eth_latest_bar_timestamp_utc=iso(eth_timestamp),
        eth_latest_bar_close_utc=iso(eth_close),
        eth_bar_age_seconds=eth_age,
        core_state_latest_embedded_timestamp_utc=iso(state_timestamp),
        core_state_age_seconds=state_age,
        btc_file=file_observation(btc_path),
        eth_file=file_observation(eth_path),
        core_state_file=file_observation(state_path),
        ready_for_shadow_decision=ready,
        reason_codes=reasons if reasons else ["READY"],
    )


def signature(observation: ProbeObservation) -> tuple[Any, ...]:
    return (
        observation.btc_latest_bar_timestamp_utc,
        observation.eth_latest_bar_timestamp_utc,
        observation.core_state_latest_embedded_timestamp_utc,
        observation.btc_file.mtime_utc,
        observation.eth_file.mtime_utc,
        observation.core_state_file.mtime_utc,
        observation.ready_for_shadow_decision,
        tuple(observation.reason_codes),
    )


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path: Path, payload: Any) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str, separators=(",", ":")) + "\n")
        handle.flush()


def read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def summarize(events: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    if not events:
        return {
            "status": "NO_OBSERVATIONS",
            "observation_count": 0,
            "paper_activation_allowed": False,
        }

    ready_count = sum(bool(event["ready_for_shadow_decision"]) for event in events)
    all_reasons: dict[str, int] = {}
    for event in events:
        for reason in event.get("reason_codes", []):
            all_reasons[reason] = all_reasons.get(reason, 0) + 1

    btc_bars = {event.get("btc_latest_bar_timestamp_utc") for event in events if event.get("btc_latest_bar_timestamp_utc")}
    eth_bars = {event.get("eth_latest_bar_timestamp_utc") for event in events if event.get("eth_latest_bar_timestamp_utc")}
    state_times = {
        event.get("core_state_latest_embedded_timestamp_utc")
        for event in events
        if event.get("core_state_latest_embedded_timestamp_utc")
    }
    ready_rate = ready_count / len(events)

    # A single probe run is evidence gathering only. It cannot authorize paper
    # activation regardless of observed readiness.
    status = "OBSERVATION_COMPLETE"
    if ready_count == 0:
        status = "FAIL_CLOSED_NO_READY_OBSERVATIONS"
    elif ready_rate < 0.50:
        status = "MIXED_CADENCE_REQUIRES_REVIEW"

    return {
        "status": status,
        "paper_activation_allowed": False,
        "observation_only": True,
        "observation_count": len(events),
        "ready_observation_count": ready_count,
        "ready_observation_rate": ready_rate,
        "distinct_btc_bar_timestamps": len(btc_bars),
        "distinct_eth_bar_timestamps": len(eth_bars),
        "distinct_core_state_timestamps": len(state_times),
        "reason_counts": dict(sorted(all_reasons.items())),
        "config": vars(args),
        "interpretation": (
            "This probe measures source-file and Core-state cadence only. It does not score Jump Risk, "
            "change Core allocations, create simulated orders, or approve paper activation."
        ),
    }


def write_csv(events: list[dict[str, Any]], path: Path) -> None:
    rows: list[dict[str, Any]] = []
    for event in events:
        rows.append(
            {
                "observed_at_utc": event.get("observed_at_utc"),
                "next_hour_utc": event.get("next_hour_utc"),
                "seconds_to_next_hour": event.get("seconds_to_next_hour"),
                "btc_latest_bar_timestamp_utc": event.get("btc_latest_bar_timestamp_utc"),
                "btc_latest_bar_close_utc": event.get("btc_latest_bar_close_utc"),
                "btc_bar_age_seconds": event.get("btc_bar_age_seconds"),
                "eth_latest_bar_timestamp_utc": event.get("eth_latest_bar_timestamp_utc"),
                "eth_latest_bar_close_utc": event.get("eth_latest_bar_close_utc"),
                "eth_bar_age_seconds": event.get("eth_bar_age_seconds"),
                "core_state_latest_embedded_timestamp_utc": event.get(
                    "core_state_latest_embedded_timestamp_utc"
                ),
                "core_state_age_seconds": event.get("core_state_age_seconds"),
                "ready_for_shadow_decision": event.get("ready_for_shadow_decision"),
                "reason_codes": "|".join(event.get("reason_codes", [])),
            }
        )
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_args(args: argparse.Namespace) -> None:
    if args.duration_seconds <= 0:
        raise ValueError("--duration-seconds must be positive")
    if args.poll_seconds <= 0:
        raise ValueError("--poll-seconds must be positive")
    if args.max_finalized_bar_age_seconds <= 0:
        raise ValueError("--max-finalized-bar-age-seconds must be positive")
    if args.max_core_state_age_seconds <= 0:
        raise ValueError("--max-core-state-age-seconds must be positive")
    if args.decision_safety_margin_seconds < 0 or args.decision_safety_margin_seconds >= 3600:
        raise ValueError("--decision-safety-margin-seconds must be in [0, 3600)")


def main() -> None:
    args = parse_args()
    validate_args(args)

    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_{args.run_name}"
    run_dir.mkdir(parents=True, exist_ok=False)
    event_path = run_dir / "jump_risk_runtime_cadence_events.jsonl"

    started = time.monotonic()
    deadline = started + args.duration_seconds
    last_signature: tuple[Any, ...] | None = None
    event_count = 0

    print("Jump Risk runtime cadence probe")
    print("Mode: OBSERVATION ONLY — no runtime state or allocations will be changed")
    print(f"Out dir: {run_dir}")

    while True:
        observation = observe(args)
        current_signature = signature(observation)
        # Record state transitions, plus a heartbeat at least once per minute.
        elapsed = time.monotonic() - started
        heartbeat_due = event_count == 0 or math.floor(elapsed / 60) >= event_count
        if current_signature != last_signature or heartbeat_due:
            payload = asdict(observation)
            append_jsonl(event_path, payload)
            event_count += 1
            last_signature = current_signature
            print(
                f"[{observation.observed_at_utc}] ready={observation.ready_for_shadow_decision} "
                f"btc={observation.btc_latest_bar_timestamp_utc} "
                f"eth={observation.eth_latest_bar_timestamp_utc} "
                f"core={observation.core_state_latest_embedded_timestamp_utc} "
                f"reasons={','.join(observation.reason_codes)}"
            )

        if time.monotonic() >= deadline:
            break
        time.sleep(min(args.poll_seconds, max(0.0, deadline - time.monotonic())))

    events = read_events(event_path)
    summary = summarize(events, args)
    atomic_json(run_dir / "jump_risk_runtime_cadence_summary.json", summary)
    write_csv(events, run_dir / "jump_risk_runtime_cadence_events.csv")

    print()
    print("Jump Risk runtime cadence probe complete")
    print(f"Status: {summary['status']}")
    print(f"Observations: {summary['observation_count']}")
    print(f"Ready rate: {summary.get('ready_observation_rate', 0.0):.1%}")
    print("Paper activation allowed: NO")
    print("Reference files:")
    print(f"- {event_path}")
    print(f"- {run_dir / 'jump_risk_runtime_cadence_events.csv'}")
    print(f"- {run_dir / 'jump_risk_runtime_cadence_summary.json'}")


if __name__ == "__main__":
    main()
