from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Keep standalone script execution working until the separate packaging migration.



DATE_CANDIDATES = (
    "date",
    "datetime",
    "timestamp",
    "time",
    "Date",
    "Datetime",
    "Timestamp",
)
SUPPORTED_SUFFIXES = {".csv"}


def sha256_file(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=hashlib.sha256)


def _parse_date(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def inspect_csv(path: Path, root: Path) -> dict[str, Any]:
    byte_count = path.stat().st_size
    result: dict[str, Any] = {
        "path": path.relative_to(root).as_posix(),
        "suffix": path.suffix.lower(),
        "byte_count": byte_count,
        "sha256": sha256_file(path),
        "status": "PASS",
    }

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = reader.fieldnames or []
            result["columns"] = columns
            date_column = next((name for name in DATE_CANDIDATES if name in columns), None)
            result["date_column"] = date_column

            row_count = 0
            first_date: datetime | None = None
            last_date: datetime | None = None
            duplicate_date_count = 0
            unparseable_date_count = 0
            seen_dates: set[str] = set()

            for row in reader:
                row_count += 1
                if date_column is None:
                    continue
                raw_date = (row.get(date_column) or "").strip()
                parsed = _parse_date(raw_date)
                if parsed is None:
                    unparseable_date_count += 1
                    continue
                canonical = parsed.isoformat()
                if canonical in seen_dates:
                    duplicate_date_count += 1
                else:
                    seen_dates.add(canonical)
                first_date = parsed if first_date is None or parsed < first_date else first_date
                last_date = parsed if last_date is None or parsed > last_date else last_date

            result.update(
                {
                    "row_count": row_count,
                    "first_date": first_date.isoformat() if first_date else None,
                    "last_date": last_date.isoformat() if last_date else None,
                    "duplicate_date_count": duplicate_date_count,
                    "unparseable_date_count": unparseable_date_count,
                }
            )
    except (OSError, UnicodeError, csv.Error) as exc:
        result["status"] = "READ_FAILURE"
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def build_inventory(root: Path) -> dict[str, Any]:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"DATA_ROOT_NOT_FOUND: {root}")

    files = [
        path
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower())
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    records = [inspect_csv(path, root) for path in files]
    return {
        "inventory_type": "campaign50_equity_source_only",
        "root": root.resolve().as_posix(),
        "file_count": len(records),
        "total_bytes": sum(int(record["byte_count"]) for record in records),
        "supported_suffixes": sorted(SUPPORTED_SUFFIXES),
        "outcomes_generated": False,
        "predictors_generated": False,
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory local Campaign 50 equity source files without calculating "
            "predictors, returns, breadth values, or holdout outcomes."
        )
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument(
        "--output",
        default="artifacts/campaign50_equity_source_inventory.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.data_root)
    output = Path(args.output)
    inventory = build_inventory(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(inventory, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "file_count": inventory["file_count"],
        "total_bytes": inventory["total_bytes"],
        "output": output.as_posix(),
        "outcomes_generated": False,
        "predictors_generated": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
