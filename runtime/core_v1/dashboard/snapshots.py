"""Read-only snapshot loading and existing intraday derivations.

Missing/malformed-file behavior and input ordering are intentionally preserved.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pandas as pd

def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_jsonl(path: Path, n: int = 800) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-n:]:
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def parse_ts(value: Any) -> pd.Timestamp | None:
    if not value:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(ts) else ts


def intraday_nav_baseline(events: list[dict[str, Any]]) -> tuple[float | None, int]:
    today = pd.Timestamp.now(tz="UTC").date()
    today_events = []
    for e in events:
        ts = parse_ts(e.get("timestamp"))
        if ts is not None and ts.date() == today and e.get("total_nav") is not None:
            today_events.append(e)
    if not today_events:
        return None, 0
    return float(today_events[0].get("total_nav")), len(today_events)


def latest_same_day_navs(events: list[dict[str, Any]]) -> dict[str, float]:
    today = pd.Timestamp.now(tz="UTC").date()
    for e in events:
        ts = parse_ts(e.get("timestamp"))
        if ts is not None and ts.date() == today and e.get("sleeve_navs"):
            return {k: float(v) for k, v in e.get("sleeve_navs", {}).items()}
    return {}
