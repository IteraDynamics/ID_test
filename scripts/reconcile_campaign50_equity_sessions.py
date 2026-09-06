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
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Keep standalone script execution working until the separate packaging migration.



EXPECTED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
TARGETS = ["SPY_1D.csv", "QQQ_1D.csv"]
BREADTH_MEMBERS = [
    "RSP_1D.csv",
    "MDY_1D.csv",
    "IWM_1D.csv",
    "IWD_1D.csv",
    "IWF_1D.csv",
    "XLB_1D.csv",
    "XLE_1D.csv",
    "XLF_1D.csv",
    "XLI_1D.csv",
    "XLK_1D.csv",
    "XLP_1D.csv",
    "XLU_1D.csv",
    "XLV_1D.csv",
    "XLY_1D.csv",
]
EXPECTED_SHA256 = {
    "IWD_1D.csv": "c609169db6f6d6220f64877da52fd707c78308af67bf793422d87c8c777e2d29",
    "IWF_1D.csv": "b5c1b73bcb75deac3329dd6e089071a8b2ecfb189240acb259617d29509b3788",
    "IWM_1D.csv": "e6cafc5ba4de5749770d439859e024b8e8026686c8e4f420da3d5f11743cea12",
    "MDY_1D.csv": "0d314431aff35303893a31f5eed4fba1fa4320a0064441b70ec989a96cbda53c",
    "QQQ_1D.csv": "34867c2b2da4aece23892b8e035e528f547173f3bc137cbe33b1295af0c1ff7b",
    "RSP_1D.csv": "9cf41b9eaa50ee49a8e28153ac2240fc4fbb62bf2eaa678b439a481f0d54fbdd",
    "SPY_1D.csv": "85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86",
    "XLB_1D.csv": "e85d3d0107eb8ed8d8044c00e5bdbddd4cf0ef64ba6a1d82b5541d2f2ef64087",
    "XLE_1D.csv": "18547a4e322f75f2ab6b1f1b79418f6bbe240880eb9ee60b4cfe009c67c2e4a6",
    "XLF_1D.csv": "205026d65898a823681b768213032bb89a7ea37f474251807d3d3e6f92b87d73",
    "XLI_1D.csv": "e6b9f3abdbe83c4561d8bb03fe6dd6a924e9a7dfb9d3da8e9f3aadc929d76d4e",
    "XLK_1D.csv": "1c63e414fac5090059d684b0736fc046517ae377b79887ffb0d5686d06fba874",
    "XLP_1D.csv": "a4ccb5e2d5cd8c191133f9977afaa70ddbfceb422767dd70ce81b4ef9ff75536",
    "XLU_1D.csv": "930b10eed5679c1acd2f9dc8329242f0510a97b1c23cbff692c700e59be00471",
    "XLV_1D.csv": "346d1f5f43e7bd357d041276914db95a539e1906549898102c8a387ac918e902",
    "XLY_1D.csv": "1a7b600eced3e741a56d0c98012f8163256848aeefb471e3aab2c6ecbaf1ec34",
}
INTERVALS = {
    "development": (date(2018, 1, 2), date(2022, 12, 30)),
    "validation": (date(2023, 1, 3), date(2024, 12, 31)),
    "holdout": (date(2025, 1, 2), date(2025, 12, 30)),
}
OHLC_RELATIVE_TOLERANCE = 1e-12


def sha256_file(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=hashlib.sha256)


def parse_timestamp(raw: str) -> datetime:
    normalized = raw.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed


def validate_float(value: str, field: str, filename: str, row_number: int) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"INVALID_{field.upper()}: {filename}:{row_number}") from exc
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        raise ValueError(f"NONFINITE_{field.upper()}: {filename}:{row_number}")
    return parsed


def ohlc_tolerance(*prices: float) -> float:
    return OHLC_RELATIVE_TOLERANCE * max(1.0, *(abs(price) for price in prices))


def load_source(path: Path) -> tuple[list[date], dict[str, Any]]:
    filename = path.name
    if not path.exists():
        raise ValueError(f"SOURCE_NOT_FOUND: {filename}")
    actual_hash = sha256_file(path)
    expected_hash = EXPECTED_SHA256[filename]
    if actual_hash != expected_hash:
        raise ValueError(f"SOURCE_HASH_MISMATCH: {filename}")

    sessions: list[date] = []
    seen: set[date] = set()
    previous: date | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise ValueError(f"SCHEMA_MISMATCH: {filename}")
        for row_number, row in enumerate(reader, start=2):
            timestamp = parse_timestamp(row["timestamp"])
            session = timestamp.date()
            if session in seen:
                raise ValueError(f"DUPLICATE_SESSION: {filename}:{session.isoformat()}")
            if previous is not None and session <= previous:
                raise ValueError(f"NONINCREASING_SESSION: {filename}:{session.isoformat()}")
            seen.add(session)
            sessions.append(session)
            previous = session

            open_price = validate_float(row["open"], "open", filename, row_number)
            high_price = validate_float(row["high"], "high", filename, row_number)
            low_price = validate_float(row["low"], "low", filename, row_number)
            close_price = validate_float(row["close"], "close", filename, row_number)
            volume = validate_float(row["volume"], "volume", filename, row_number)
            if min(open_price, high_price, low_price, close_price) <= 0:
                raise ValueError(f"NONPOSITIVE_PRICE: {filename}:{row_number}")
            tolerance = ohlc_tolerance(open_price, high_price, low_price, close_price)
            if low_price - min(open_price, high_price, close_price) > tolerance:
                raise ValueError(f"INVALID_LOW: {filename}:{row_number}")
            if max(open_price, low_price, close_price) - high_price > tolerance:
                raise ValueError(f"INVALID_HIGH: {filename}:{row_number}")
            if volume < 0:
                raise ValueError(f"NEGATIVE_VOLUME: {filename}:{row_number}")

    return sessions, {
        "path": filename,
        "sha256": actual_hash,
        "row_count": len(sessions),
        "first_session": sessions[0].isoformat() if sessions else None,
        "last_session": sessions[-1].isoformat() if sessions else None,
        "ohlc_relative_tolerance": OHLC_RELATIVE_TOLERANCE,
        "status": "PASS",
    }


def within_interval(session: date, start: date, end: date) -> bool:
    return start <= session <= end


def build_reconciliation(data_root: Path) -> dict[str, Any]:
    filenames = TARGETS + BREADTH_MEMBERS
    loaded: dict[str, list[date]] = {}
    source_records: list[dict[str, Any]] = []
    for filename in filenames:
        sessions, record = load_source(data_root / filename)
        loaded[filename] = sessions
        source_records.append(record)

    target_calendar = sorted(set(loaded["SPY_1D.csv"]) & set(loaded["QQQ_1D.csv"]))
    if not target_calendar:
        raise ValueError("EMPTY_TARGET_CALENDAR")

    target_set = set(target_calendar)
    member_records: list[dict[str, Any]] = []
    for filename in BREADTH_MEMBERS:
        member_set = set(loaded[filename])
        missing = sorted(target_set - member_set)
        extra = sorted(member_set - target_set)
        member_records.append(
            {
                "path": filename,
                "missing_target_session_count": len(missing),
                "missing_target_sessions": [item.isoformat() for item in missing],
                "extra_non_target_session_count": len(extra),
                "extra_non_target_sessions_through_target_end": [
                    item.isoformat() for item in extra if item <= target_calendar[-1]
                ],
            }
        )

    common_all = set(target_calendar)
    for filename in BREADTH_MEMBERS:
        common_all &= set(loaded[filename])
    common_all_sorted = sorted(common_all)

    interval_records: dict[str, Any] = {}
    for name, (start, end) in INTERVALS.items():
        target_interval = [item for item in target_calendar if within_interval(item, start, end)]
        common_interval = [item for item in common_all_sorted if within_interval(item, start, end)]
        interval_records[name] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "target_session_count": len(target_interval),
            "all_source_common_session_count": len(common_interval),
            "dropped_session_count": len(target_interval) - len(common_interval),
            "dropped_sessions": [
                item.isoformat() for item in target_interval if item not in common_all
            ],
        }

    return {
        "reconciliation_type": "campaign50_equity_source_only",
        "predictors_generated": False,
        "outcomes_generated": False,
        "ohlc_relative_tolerance": OHLC_RELATIVE_TOLERANCE,
        "target_calendar_definition": "intersection(SPY_1D.csv, QQQ_1D.csv)",
        "target_calendar_first_session": target_calendar[0].isoformat(),
        "target_calendar_last_session": target_calendar[-1].isoformat(),
        "target_calendar_session_count": len(target_calendar),
        "all_source_common_session_count": len(common_all_sorted),
        "sources": source_records,
        "breadth_member_reconciliation": member_records,
        "intervals": interval_records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile Campaign 50 equity source hashes, schemas, OHLCV validity, "
            "and common sessions without calculating predictors or outcomes."
        )
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument(
        "--output",
        default="artifacts/campaign50_equity_session_reconciliation.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    result = build_reconciliation(Path(args.data_root))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "all_source_common_session_count": result["all_source_common_session_count"],
                "outcomes_generated": False,
                "output": output.as_posix(),
                "predictors_generated": False,
                "target_calendar_session_count": result["target_calendar_session_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
