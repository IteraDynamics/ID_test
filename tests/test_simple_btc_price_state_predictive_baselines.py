from __future__ import annotations

import importlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.ml.validation import simple_btc_price_state_predictive_baselines as subject


def synthetic_frame(hours: int = 900) -> pd.DataFrame:
    timestamps = pd.date_range("2020-01-01", periods=hours + 1, freq="h")
    returns = 0.0004 + 0.001 * np.sin(np.arange(hours + 1) / 17.0)
    closes = 100.0 * np.exp(np.cumsum(returns))
    return pd.DataFrame({"close": closes}, index=timestamps)


def write_source(path: Path, hours: int = 200) -> subject.FrozenContract:
    frame = synthetic_frame(hours).reset_index(names="timestamp")
    frame["timestamp"] = frame["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    frame["open"] = frame["close"]
    frame["high"] = frame["close"]
    frame["low"] = frame["close"]
    frame["volume"] = 1.0
    frame = frame[["timestamp", "open", "high", "low", "close", "volume"]]
    path.write_text(frame.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="")
    return subject.FrozenContract(
        source_path=str(path),
        source_sha256=subject.sha256_file(path),
        source_byte_count=path.stat().st_size,
        source_row_count=len(frame),
        first_timestamp=frame.iloc[0]["timestamp"],
        last_timestamp=frame.iloc[-1]["timestamp"],
        candidate_count=72,
        anchor_spacing_hours=168,
        expected_missing_timestamps=(),
    )


def rewrite_contract(path: Path, contract: subject.FrozenContract, **changes: object) -> subject.FrozenContract:
    return subject.FrozenContract(**{
        **contract.__dict__,
        "source_sha256": subject.sha256_file(path),
        "source_byte_count": path.stat().st_size,
        **changes,
    })


def test_candidate_inventory_exact_order() -> None:
    rows = subject.candidate_inventory()
    assert len(rows) == 72
    assert rows[0]["candidate_id"] == "return_trailing_24h__R__24h"
    assert rows[-1]["candidate_id"] == "drawdown_from_high_trailing_168h__V__168h"
    assert [row["candidate_ordinal"] for row in rows] == list(range(72))


def test_partition_counts_assign_remainder_early() -> None:
    assert subject.partition_counts(10) == (4, 3, 3)
    assert subject.partition_counts(11) == (4, 4, 3)
    assert subject.partition_counts(12) == (4, 4, 4)


def test_source_contract_and_order(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    contract = write_source(path)
    loaded = subject.load_source(path, contract)
    assert len(loaded) == contract.source_row_count
    bad = pd.read_csv(path)[["timestamp", "close", "open", "high", "low", "volume"]]
    path.write_text(bad.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="SOURCE_SCHEMA_MISMATCH"):
        subject.load_source(path, rewrite_contract(path, contract))


def test_source_rejects_duplicate_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    contract = write_source(path)
    frame = pd.read_csv(path)
    frame.loc[2, "timestamp"] = frame.loc[1, "timestamp"]
    path.write_text(frame.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="SOURCE_TIMESTAMP_ORDER_FAILURE"):
        subject.load_source(path, rewrite_contract(path, contract))


def test_source_rejects_non_hour_alignment(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    contract = write_source(path)
    frame = pd.read_csv(path)
    frame.loc[2, "timestamp"] = "2020-01-01 02:30:00"
    path.write_text(frame.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="SOURCE_TIMESTAMP_ALIGNMENT_FAILURE"):
        subject.load_source(path, rewrite_contract(path, contract))


def test_source_accepts_exact_declared_gap(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    contract = write_source(path)
    frame = pd.read_csv(path)
    missing = frame.loc[10, "timestamp"]
    frame = frame.drop(index=10).reset_index(drop=True)
    path.write_text(frame.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="")
    amended = rewrite_contract(
        path,
        contract,
        source_row_count=len(frame),
        expected_missing_timestamps=(missing,),
    )
    loaded = subject.load_source(path, amended)
    assert len(loaded) == len(frame)
    assert subject.source_gap_inventory(loaded.index) == (missing,)


def test_source_rejects_unregistered_gap(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    contract = write_source(path)
    frame = pd.read_csv(path).drop(index=10).reset_index(drop=True)
    path.write_text(frame.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="")
    altered = rewrite_contract(path, contract, source_row_count=len(frame))
    with pytest.raises(ValueError, match="SOURCE_GAP_INVENTORY_MISMATCH"):
        subject.load_source(path, altered)


def test_source_rejects_nonpositive_close(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    contract = write_source(path)
    frame = pd.read_csv(path)
    frame.loc[5, "close"] = 0.0
    path.write_text(frame.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="SOURCE_CLOSE_FAILURE"):
        subject.load_source(path, rewrite_contract(path, contract))


def test_predictor_formulas() -> None:
    frame = synthetic_frame(300)
    timestamp = frame.index[200]
    values = subject.predictor_values(frame, timestamp)
    closes = frame.loc[timestamp - pd.Timedelta(hours=168):timestamp, "close"].to_numpy()
    assert values["return_trailing_168h"] == pytest.approx(math.log(closes[-1] / closes[0]))
    assert values["realized_volatility_trailing_168h"] == pytest.approx(np.sqrt(np.sum(np.diff(np.log(closes)) ** 2)))
    assert values["distance_from_mean_trailing_168h"] == pytest.approx(closes[-1] / closes.mean() - 1)
    assert values["range_position_trailing_168h"] == pytest.approx((closes[-1] - closes.min()) / (closes.max() - closes.min()))
    assert values["drawdown_from_high_trailing_168h"] == pytest.approx(closes[-1] / closes.max() - 1)


def test_flat_range_is_unavailable() -> None:
    index = pd.date_range("2020-01-01", periods=169, freq="h")
    frame = pd.DataFrame({"close": np.full(169, 100.0)}, index=index)
    assert subject.predictor_values(frame, index[-1])["range_position_trailing_168h"] is None


def test_anchor_origin_spacing_and_partitions() -> None:
    frame = synthetic_frame(900)
    rows = subject.build_anchors(frame)
    assert rows[0]["anchor_timestamp"] == frame.index[168].strftime("%Y-%m-%d %H:%M:%S")
    timestamps = pd.to_datetime([row["anchor_timestamp"] for row in rows])
    assert set(np.diff(timestamps.values).astype("timedelta64[h]").astype(int)) == {168}
    assert tuple(sum(row["partition"] == p for row in rows) for p in (1, 2, 3)) == subject.partition_counts(len(rows))


def test_anchor_with_incomplete_trailing_window_is_skipped() -> None:
    frame = synthetic_frame(600).drop(pd.Timestamp("2020-01-03 00:00:00"))
    rows = subject.build_anchors(frame)
    scheduled_first = pd.Timestamp("2020-01-08 00:00:00")
    assert scheduled_first.strftime("%Y-%m-%d %H:%M:%S") not in {
        row["anchor_timestamp"] for row in rows
    }


def test_outcome_columns_and_unavailable_tail() -> None:
    frame = synthetic_frame(400)
    anchors = subject.build_anchors(frame)
    rows = subject.add_outcomes(frame, anchors)
    first = rows[0]
    timestamp = pd.Timestamp(first["anchor_timestamp"])
    expected = math.log(frame.loc[timestamp + pd.Timedelta(hours=24), "close"] / frame.loc[timestamp, "close"])
    assert first["outcome_R_24h"] == pytest.approx(expected)
    assert first["outcome_M_24h"] == pytest.approx(abs(expected))
    assert rows[-1]["outcome_R_168h"] is None


def test_outcome_with_internal_missing_hour_is_unavailable() -> None:
    frame = synthetic_frame(500)
    anchors = subject.build_anchors(frame)
    first_timestamp = pd.Timestamp(anchors[0]["anchor_timestamp"])
    frame = frame.drop(first_timestamp + pd.Timedelta(hours=12))
    row = subject.add_outcomes(frame, [anchors[0]])[0]
    assert row["outcome_R_24h"] is None
    assert row["outcome_M_24h"] is None
    assert row["outcome_V_24h"] is None


def test_population_standardization_and_ols() -> None:
    x = np.arange(1.0, 101.0)
    y = 2.5 * ((x - x.mean()) / x.std(ddof=0)) + 3.0
    design = np.column_stack((np.ones(len(x)), (x - x.mean()) / x.std(ddof=0)))
    result = subject.ols_hc3(design, y)
    assert result.coefficient == pytest.approx(2.5)
    assert result.n_obs == 100


def test_rank_deficient_design_fails() -> None:
    x = np.ones((20, 2))
    y = np.arange(20.0)
    with pytest.raises(ValueError, match="RANK_DEFICIENT_DESIGN"):
        subject.ols_hc3(x, y)


def test_zero_variance_status() -> None:
    anchors = []
    for partition in (1, 2, 3):
        for index in range(30):
            anchors.append({"partition": partition, "return_trailing_24h": 1.0, "outcome_R_24h": float(index)})
    result = subject.evaluate_candidate(anchors, subject.candidate_inventory()[0])
    assert result["status"] == "ZERO_OR_NONFINITE_VARIANCE"
    assert not result["rankable"]


def test_insufficient_support_precedes_variance() -> None:
    anchors = [{"partition": 1, "return_trailing_24h": 1.0, "outcome_R_24h": 1.0}]
    result = subject.evaluate_candidate(anchors, subject.candidate_inventory()[0])
    assert result["status"] == "INSUFFICIENT_SUPPORT"


def test_directional_consistency() -> None:
    rng = np.random.default_rng(7)
    anchors = []
    for partition in (1, 2, 3):
        for _ in range(40):
            x = float(rng.normal())
            anchors.append({"partition": partition, "return_trailing_24h": x, "outcome_R_24h": 0.5 * x + float(rng.normal(scale=0.2))})
    result = subject.evaluate_candidate(anchors, subject.candidate_inventory()[0])
    assert result["rankable"]
    assert result["directionally_consistent"]


def test_bh_ties_and_family_isolation() -> None:
    rows = []
    for ordinal, (family, p_value, candidate_id) in enumerate((("R", 0.01, "b"), ("R", 0.01, "a"), ("M", 0.9, "c"))):
        rows.append({"candidate_ordinal": ordinal, "candidate_id": candidate_id, "outcome_family": family, "rankable": True, "pooled_p_value": p_value, "directionally_consistent": True, "status": "MULTIPLICITY_NOT_MET", "family_bh_rank": None, "family_bh_adjusted_q_value": None})
    subject.apply_bh(rows)
    by_id = {row["candidate_id"]: row for row in rows}
    assert by_id["a"]["family_bh_rank"] == 1
    assert by_id["b"]["family_bh_rank"] == 2
    assert by_id["a"]["family_bh_adjusted_q_value"] == pytest.approx(0.01)
    assert by_id["c"]["family_bh_adjusted_q_value"] == pytest.approx(0.9)


def test_failed_candidates_remain_visible() -> None:
    rows = subject.evaluate_all([])
    assert len(rows) == 72
    assert all(row["status"] == "OUTCOME_OR_PREDICTOR_UNAVAILABLE" for row in rows)


def test_json_normalization_and_strictness(tmp_path: Path) -> None:
    text = subject.json_text({"negative_zero": -0.0, "nonfinite": float("nan")})
    assert '"negative_zero": 0.0' in text
    assert '"nonfinite": null' in text
    path = tmp_path / "bad.json"
    path.write_text('{"x": NaN}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="non-strict JSON"):
        subject.strict_json(path)


def test_csv_contract() -> None:
    text = subject.csv_text([{"a": True, "b": None, "c": 1.25}], ("a", "b", "c"))
    assert text == "a,b,c\ntrue,,1.25\n"
    assert "\r" not in text


def test_report_is_deterministic() -> None:
    source = {"source_path": "data/source.csv", "sha256": "abc"}
    results = [{"status": "MULTIPLICITY_NOT_MET", "rankable": True, "candidate_id": "x", "pooled_coefficient": 1.0, "family_bh_adjusted_q_value": 1.0}]
    first = subject.report_text(source, [], results)
    second = subject.report_text(source, [], results)
    assert first == second
    assert first.endswith("\n")


def test_preflight_generates_no_outcomes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frame = synthetic_frame(400)
    monkeypatch.setattr(subject, "load_source", lambda path: frame)
    monkeypatch.setattr(subject, "source_manifest", lambda path, predictive_outcomes_generated: {"predictive_outcomes_generated": predictive_outcomes_generated})
    payload = subject.preflight(tmp_path / "unused.csv")
    assert payload["predictive_outcomes_generated"] is False
    assert payload["source"]["predictive_outcomes_generated"] is False
    assert payload["missing_hour_count"] == len(subject.GOVERNED_MISSING_TIMESTAMPS)


def test_output_replay_and_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path = tmp_path / "source.csv"
    source_path.write_bytes(b"source")
    monkeypatch.setattr(subject, "source_manifest", lambda path, predictive_outcomes_generated: {"source_path": "data/source.csv", "sha256": subject.sha256_file(path), "predictive_outcomes_generated": predictive_outcomes_generated})
    frame = synthetic_frame(900)
    first = subject.build_output_texts(source_path, frame)
    second = subject.build_output_texts(source_path, frame)
    assert first == second
    assert tuple(first) == subject.OUTPUT_FILENAMES
    output = tmp_path / "output"
    for name, text in first.items():
        subject.write_lf(output / name, text)
    subject.validate_output_directory(output)


def test_import_has_no_file_side_effects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    importlib.reload(subject)
    assert set(tmp_path.iterdir()) == before
