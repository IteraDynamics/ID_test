from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.update_campaign49_coinbase_source import (
    FIXED_START,
    REVISION_ERROR,
    build_manifest,
    inventory_csv_bytes,
    output_stem,
    reconcile_prior_interval,
)


HEADER = "timestamp,open,high,low,close,volume\n"


def csv_bytes(rows: list[str]) -> bytes:
    return (HEADER + "\n".join(rows) + "\n").encode("utf-8")


def row(timestamp: str, close: str = "100") -> str:
    return f"{timestamp},100,101,99,{close},5"


def test_inventory_accepts_exact_hourly_source_and_records_gap() -> None:
    raw = csv_bytes(
        [
            row("2026-01-01 00:00:00"),
            row("2026-01-01 01:00:00"),
            row("2026-01-01 03:00:00"),
        ]
    )

    inventory = inventory_csv_bytes(raw)

    assert inventory.first_timestamp == datetime(2026, 1, 1, 0)
    assert inventory.last_timestamp == datetime(2026, 1, 1, 3)
    assert inventory.missing_timestamps == (datetime(2026, 1, 1, 2),)


def test_inventory_rejects_non_lf_serialization() -> None:
    raw = (
        "timestamp,open,high,low,close,volume\r\n"
        "2026-01-01 00:00:00,100,101,99,100,5\r\n"
    ).encode("utf-8")

    with pytest.raises(ValueError, match="NON_LF_LINE_ENDING_FAILURE"):
        inventory_csv_bytes(raw)


def test_inventory_rejects_off_hour_timestamp() -> None:
    raw = csv_bytes([row("2026-01-01 00:30:00")])

    with pytest.raises(ValueError, match="HOUR_ALIGNMENT_FAILURE"):
        inventory_csv_bytes(raw)


def test_inventory_rejects_duplicate_timestamp() -> None:
    raw = csv_bytes(
        [
            row("2026-01-01 00:00:00"),
            row("2026-01-01 00:00:00"),
        ]
    )

    with pytest.raises(ValueError, match="DUPLICATE_TIMESTAMP_FAILURE"):
        inventory_csv_bytes(raw)


def test_inventory_rejects_invalid_ohlc_relationship() -> None:
    raw = csv_bytes(["2026-01-01 00:00:00,102,101,99,100,5"])

    with pytest.raises(ValueError, match="OHLC_RELATIONSHIP_FAILURE"):
        inventory_csv_bytes(raw)


def test_reconciliation_accepts_unchanged_prefix_and_extension() -> None:
    prior = inventory_csv_bytes(
        csv_bytes(
            [
                row("2026-01-01 00:00:00"),
                row("2026-01-01 01:00:00"),
            ]
        )
    )
    candidate = inventory_csv_bytes(
        csv_bytes(
            [
                row("2026-01-01 00:00:00"),
                row("2026-01-01 01:00:00"),
                row("2026-01-01 02:00:00"),
            ]
        )
    )

    reconcile_prior_interval(prior, candidate)


def test_reconciliation_rejects_changed_historical_value() -> None:
    prior = inventory_csv_bytes(csv_bytes([row("2026-01-01 00:00:00")]))
    candidate = inventory_csv_bytes(
        csv_bytes(
            [
                row("2026-01-01 00:00:00", close="100.5"),
                row("2026-01-01 01:00:00"),
            ]
        )
    )

    with pytest.raises(ValueError, match=REVISION_ERROR):
        reconcile_prior_interval(prior, candidate)


def test_reconciliation_rejects_disappeared_historical_candle() -> None:
    prior = inventory_csv_bytes(
        csv_bytes(
            [
                row("2026-01-01 00:00:00"),
                row("2026-01-01 01:00:00"),
            ]
        )
    )
    candidate = inventory_csv_bytes(
        csv_bytes(
            [
                row("2026-01-01 00:00:00"),
                row("2026-01-01 02:00:00"),
            ]
        )
    )

    with pytest.raises(ValueError, match=REVISION_ERROR):
        reconcile_prior_interval(prior, candidate)


def test_reconciliation_rejects_new_candle_inside_prior_gap() -> None:
    prior = inventory_csv_bytes(
        csv_bytes(
            [
                row("2026-01-01 00:00:00"),
                row("2026-01-01 02:00:00"),
            ]
        )
    )
    candidate = inventory_csv_bytes(
        csv_bytes(
            [
                row("2026-01-01 00:00:00"),
                row("2026-01-01 01:00:00"),
                row("2026-01-01 02:00:00"),
                row("2026-01-01 03:00:00"),
            ]
        )
    )

    with pytest.raises(ValueError, match=REVISION_ERROR):
        reconcile_prior_interval(prior, candidate)


def test_reconciliation_requires_extension() -> None:
    prior = inventory_csv_bytes(csv_bytes([row("2026-01-01 00:00:00")]))
    candidate = inventory_csv_bytes(csv_bytes([row("2026-01-01 00:00:00")]))

    with pytest.raises(ValueError, match="CUMULATIVE_END_NOT_EXTENDED"):
        reconcile_prior_interval(prior, candidate)


def test_output_stem_includes_exact_end_hour() -> None:
    end = datetime(2027, 1, 7, 0, 0, tzinfo=timezone.utc)

    assert output_stem(end) == "btcusd_3600s_2026-01-01_to_2027-01-07T000000Z"


def test_manifest_is_source_only_and_reconciled(tmp_path: Path) -> None:
    prior = inventory_csv_bytes(csv_bytes([row("2026-01-01 00:00:00")]))
    candidate = inventory_csv_bytes(
        csv_bytes(
            [
                row("2026-01-01 00:00:00"),
                row("2026-01-01 02:00:00"),
            ]
        )
    )
    source_path = tmp_path / "source.csv"
    manifest_path = tmp_path / "source.source_manifest.json"

    manifest = build_manifest(
        candidate=candidate,
        prior=prior,
        prior_path=Path("data/prior.csv"),
        source_path=source_path,
        manifest_path=manifest_path,
        end=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
        acquisition_command="deterministic command",
    )

    assert manifest["historical_revision_check"] == "PASS"
    assert manifest["source_validation_status"] == "PASS"
    assert manifest["missing_timestamps"] == ["2026-01-01 01:00:00"]
    assert manifest["prior_sha256"] == hashlib.sha256(prior.raw).hexdigest()
    assert manifest["sha256"] == hashlib.sha256(candidate.raw).hexdigest()
    assert "predictor" not in manifest
    assert "outcome" not in manifest
    assert manifest["fixed_start"] == FIXED_START.isoformat().replace("+00:00", "Z")
