from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.harness.campaign52_development import (
    CONTROL_IDS,
    Campaign52DevelopmentError,
    atomic_promote,
    bootstrap_seed,
    bootstrap_summary,
    daily_eod_nav,
    development_decision,
    ensure_development_path,
    fisher_yates,
    holm_adjust,
    permutation_seed,
    primary_metrics,
    static_mean_values,
    transform_block_permutation,
    transform_lag,
    transform_static,
)
from research.harness.campaign52_target_replay import TargetRecord, serialize_targets


def records_for_fold(fold: str, sleeve: str, timestamps, values):
    return [
        TargetRecord(
            stage="development",
            fold=fold,
            timestamp=pd.Timestamp(ts),
            sleeve_label=sleeve,
            asset="BTC",
            native_timeframe="1H",
            strategy_id="synthetic",
            action="HOLD",
            desired_exposure_frac=0.0,
            signed_target_exposure=float(value),
            sequence_number=i,
        )
        for i, (ts, value) in enumerate(zip(timestamps, values, strict=True))
    ]


def test_validation_paths_are_structurally_rejected():
    for value in ("root/validation/x", "root/2023/x", "root/2024/x", "root/2025/x"):
        with pytest.raises(Campaign52DevelopmentError, match="VALIDATION_PATH_FORBIDDEN"):
            ensure_development_path(value)
    assert ensure_development_path("root/development/2022") == Path("root/development/2022")


def test_static_mean_and_transform_are_exact():
    rows = records_for_fold("2020", "A", pd.date_range("2020-01-01", periods=3, freq="h"), [0.0, 0.5, 1.0])
    rows += records_for_fold("2021", "A", pd.date_range("2021-01-01", periods=1, freq="h"), [-0.5])
    rows += records_for_fold("2020", "B", pd.date_range("2020-01-01", periods=2, freq="h"), [0.2, 0.4])
    rows.sort(key=lambda r: (r.fold, r.sleeve_label, r.timestamp, r.sequence_number))
    means = static_mean_values(rows)
    assert means == {"A": 0.25, "B": pytest.approx(0.3)}
    transformed = transform_static(rows, means)
    assert {r.signed_target_exposure for r in transformed if r.sleeve_label == "A"} == {0.25}


def test_lag_requires_exact_same_fold_timestamp_and_zero_fills():
    times = pd.date_range("2020-01-01", periods=3, freq="24h")
    rows = records_for_fold("2020", "A", times, [0.1, 0.2, 0.3])
    transformed, counts = transform_lag(rows, 24)
    assert [r.signed_target_exposure for r in transformed] == [0.0, 0.1, 0.2]
    assert counts == {"matched_rows": 2, "zero_filled_rows": 1}
    with pytest.raises(Campaign52DevelopmentError, match="UNAUTHORIZED_LAG"):
        transform_lag(rows, 12)


def test_seed_derivation_and_fisher_yates_are_deterministic():
    assert permutation_seed("perm_01") == permutation_seed("perm_01")
    assert permutation_seed("perm_01") != permutation_seed("perm_02")
    assert bootstrap_seed("lag_24h") == bootstrap_seed("lag_24h")
    assert fisher_yates(8, 1234) == fisher_yates(8, 1234)
    assert sorted(fisher_yates(8, 1234)) == list(range(8))


def test_block_permutation_preserves_terminal_rows_and_is_shared_across_sleeves():
    start = pd.Timestamp("2020-01-01")
    # Two complete 28-day blocks plus a two-day terminal remainder.
    times = pd.date_range(start, periods=58, freq="1D")
    a = records_for_fold("2020", "A", times, np.arange(58))
    b = records_for_fold("2020", "B", times, np.arange(100, 158))
    rows = sorted(a + b, key=lambda r: (r.fold, r.sleeve_label, r.timestamp, r.sequence_number))
    out, manifest = transform_block_permutation(
        rows,
        "perm_01",
        fold_starts={"2020": start},
        fold_ends={"2020": pd.Timestamp("2020-02-27")},
    )
    assert manifest["folds"]["2020"]["complete_block_count"] == 2
    by_sleeve = {s: [r for r in out if r.sleeve_label == s] for s in ("A", "B")}
    assert [r.signed_target_exposure for r in by_sleeve["A"][-2:]] == [56.0, 57.0]
    assert [r.signed_target_exposure for r in by_sleeve["B"][-2:]] == [156.0, 157.0]
    # Shared permutation means source offsets between sleeves remain exactly 100.
    assert all(brow.signed_target_exposure - arow.signed_target_exposure == 100 for arow, brow in zip(by_sleeve["A"][:-2], by_sleeve["B"][:-2], strict=True))


def test_unequal_complete_block_rows_fail_closed():
    start = pd.Timestamp("2020-01-01")
    times = list(pd.date_range(start, periods=56, freq="1D"))
    times.pop(40)
    rows = records_for_fold("2020", "A", times, np.arange(len(times)))
    with pytest.raises(Campaign52DevelopmentError, match="UNEQUAL_COMPLETE_BLOCK_ROWS"):
        transform_block_permutation(
            rows,
            "perm_01",
            fold_starts={"2020": start},
            fold_ends={"2020": pd.Timestamp("2020-02-25")},
        )


def test_two_pass_target_bytes_are_identical(tmp_path: Path):
    rows = records_for_fold("2020", "A", pd.date_range("2020-01-01", periods=4, freq="h"), [0.1, 0.2, 0.3, 0.4])
    first, _ = transform_lag(rows, 24)
    second, _ = transform_lag(rows, 24)
    p1 = tmp_path / "one.csv"
    p2 = tmp_path / "two.csv"
    serialize_targets(first, p1)
    serialize_targets(second, p2)
    assert p1.read_bytes() == p2.read_bytes()


def test_daily_eod_and_primary_metric_edge_cases():
    idx = pd.date_range("2020-01-01", periods=48, freq="h")
    nav = pd.Series(np.linspace(100.0, 110.0, 48), index=idx)
    daily = daily_eod_nav(nav)
    assert list(daily.index) == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02")]
    assert daily.iloc[-1] == 110.0
    metrics = primary_metrics(pd.Series([100.0, 110.0], index=pd.to_datetime(["2020-01-01", "2021-01-01"])))
    expected = 1.1 ** (365.25 / 366.0) - 1.0
    assert metrics["annualized_geometric_return"] == pytest.approx(expected)
    assert metrics["max_drawdown_magnitude"] == 0.0
    assert np.isinf(metrics["calmar"])


def test_bootstrap_is_reproducible_and_frozen():
    paired = np.linspace(-0.01, 0.02, 63)
    one = bootstrap_summary(paired, "lag_24h")
    two = bootstrap_summary(paired, "lag_24h")
    assert one == two
    assert one["replications"] == 10_000
    assert one["block_length"] == 21
    assert 0.0 <= one["one_sided_p"] <= 1.0


def test_holm_handles_ties_and_unrankable_controls():
    raw = {cid: 0.02 for cid in CONTROL_IDS}
    raw["perm_16"] = None
    adjusted = holm_adjust(raw)
    assert list(adjusted) == list(CONTROL_IDS)
    assert adjusted["perm_16"] == 1.0
    ordered = sorted(adjusted.values())
    assert ordered == sorted(ordered)


def test_development_decision_boundaries():
    canonical = {"annualized_geometric_return": 0.20, "max_drawdown_magnitude": 0.20, "calmar": 1.0}
    weak = {"annualized_geometric_return": 0.10, "max_drawdown_magnitude": 0.30, "calmar": 0.5}
    controls = {cid: dict(weak) for cid in CONTROL_IDS}
    pvals = {cid: 0.05 for cid in CONTROL_IDS}
    passed = development_decision(canonical, controls, pvals)
    assert passed["development_gate_passed"] is True
    controls["lag_24h"] = dict(canonical)
    controls["lag_168h"] = dict(canonical)
    failed = development_decision(canonical, controls, pvals)
    assert failed["development_gate_passed"] is False
    assert failed["classification"] == "DEVELOPMENT_NEGATIVE"


def test_atomic_promotion_rejects_stale_output(tmp_path: Path):
    temp = tmp_path / "development_tmp"
    final = tmp_path / "development_final"
    temp.mkdir()
    (temp / "manifest.json").write_text("{}\n", encoding="utf-8")
    atomic_promote(temp, final)
    assert final.is_dir() and not temp.exists()
    another = tmp_path / "another_tmp"
    another.mkdir()
    with pytest.raises(Campaign52DevelopmentError, match="STALE_OUTPUT_EXISTS"):
        atomic_promote(another, final)
