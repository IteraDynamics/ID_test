"""Print the field schema of a Core v1 paper export's logs.

Read-only. Used to establish exactly which timestamps the running paper
runtime already records, before building any cadence measurement on top of
them. Prints each log's field names, the fields that look like timestamps,
and one redacted sample row.

Usage:
    python scripts/inspect_paper_log_schema.py --paper-export artifacts/core_v1_paper_export/manual
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TIMESTAMP_HINTS = ("time", "ts", "at", "stamp", "bar", "cycle", "date")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--paper-export", required=True)
    p.add_argument("--logs", nargs="*", default=["market_data", "signals", "fills", "errors"])
    return p.parse_args()


def first_rows(path: Path, count: int = 3) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
            if len(rows) >= count:
                break
    return rows


def describe(name: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n=== {name} ===")
    if not rows:
        print("  (absent or unparseable)")
        return

    keys: set[str] = set()
    for row in rows:
        keys.update(row.keys())
    print(f"  top-level fields ({len(keys)}): {sorted(keys)}")

    stamped = sorted(k for k in keys if any(h in k.lower() for h in TIMESTAMP_HINTS))
    print(f"  timestamp-like    : {stamped}")

    sample = rows[0]
    for key, value in sorted(sample.items()):
        if isinstance(value, (dict, list)):
            if isinstance(value, list) and value and isinstance(value[0], dict):
                nested = sorted(value[0].keys())
                print(f"  nested list '{key}' element fields: {nested}")
                nested_stamps = [k for k in nested if any(h in k.lower() for h in TIMESTAMP_HINTS)]
                print(f"    timestamp-like within '{key}': {nested_stamps}")
            elif isinstance(value, dict):
                print(f"  nested dict '{key}' fields: {sorted(value.keys())}")

    print("  sample row (truncated):")
    compact = {
        key: (str(value)[:70] + "..." if len(str(value)) > 70 else value)
        for key, value in sorted(sample.items())
    }
    for key, value in compact.items():
        print(f"    {key}: {value}")


def main() -> int:
    args = parse_args()
    export_dir = Path(args.paper_export)
    if not export_dir.exists():
        print(f"No such export directory: {export_dir}")
        return 1
    print(f"Paper export: {export_dir}")
    for name in args.logs:
        describe(name, first_rows(export_dir / f"{name}.jsonl"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
