"""Synthetic validation for the Core v1 live benchmark engine.

All fixtures are hand-constructed; no governed market data is read. A full
pass here is the synthetic PASS required before the governed run against real
sources on the machine that holds them.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from research.live_benchmarks import (
    CASH_ASSET,
    BenchmarkConfig,
    LiveBenchmarkError,
    build_static_benchmark,
    canonical_json_bytes,
    compute_metrics,
    daily_closes_from_hourly,
    load_daily_closes,
    nav_csv_bytes,
)
from scripts.run_core_v1_live_benchmarks import main as runner_main

HEADER = "timestamp,open,high,low,close,volume\n"


def write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text(HEADER + "".join(f"{row}\n" for row in rows), encoding="utf-8", newline="")
    return path


def daily_row(day: str, close: float) -> str:
    return f"{day} 00:00:00,{close},{close},{close},{close},100"


def hourly_row(stamp: str, close: float) -> str:
    return f"{stamp},{close},{close},{close},{close},5"


# ---------------------------------------------------------------- loaders


def test_load_daily_closes_ordered(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "spy.csv", [daily_row("2026-07-06", 100.0), daily_row("2026-07-07", 101.0)])
    closes = load_daily_closes(path)
    assert closes == {date(2026, 7, 6): 100.0, date(2026, 7, 7): 101.0}


def test_load_daily_closes_rejects_duplicates_and_disorder(tmp_path: Path) -> None:
    duplicated = write_csv(tmp_path / "dup.csv", [daily_row("2026-07-06", 100.0), daily_row("2026-07-06", 101.0)])
    with pytest.raises(LiveBenchmarkError, match="SOURCE_ORDER_FAILURE"):
        load_daily_closes(duplicated)
    unsorted = write_csv(tmp_path / "unsorted.csv", [daily_row("2026-07-07", 100.0), daily_row("2026-07-06", 99.0)])
    with pytest.raises(LiveBenchmarkError, match="SOURCE_ORDER_FAILURE"):
        load_daily_closes(unsorted)


def test_load_daily_closes_rejects_bad_values(tmp_path: Path) -> None:
    bad = write_csv(tmp_path / "bad.csv", ["2026-07-06 00:00:00,1,1,1,not_a_number,100"])
    with pytest.raises(LiveBenchmarkError, match="SOURCE_SCHEMA_FAILURE"):
        load_daily_closes(bad)
    negative = write_csv(tmp_path / "neg.csv", [daily_row("2026-07-06", -5.0)])
    with pytest.raises(LiveBenchmarkError, match="SOURCE_SCHEMA_FAILURE"):
        load_daily_closes(negative)
    empty = write_csv(tmp_path / "empty.csv", [])
    with pytest.raises(LiveBenchmarkError, match="no rows"):
        load_daily_closes(empty)


def test_load_daily_closes_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "schema.csv"
    path.write_text("timestamp,close\n2026-07-06 00:00:00,1\n", encoding="utf-8", newline="")
    with pytest.raises(LiveBenchmarkError, match="SOURCE_SCHEMA_FAILURE"):
        load_daily_closes(path)


def test_daily_closes_from_hourly_takes_last_bar_of_day(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "btc.csv",
        [
            hourly_row("2026-07-06 00:00:00", 10.0),
            hourly_row("2026-07-06 13:00:00", 11.0),
            # 2026-07-07 has a partial day: bars stop at 05:00.
            hourly_row("2026-07-07 04:00:00", 12.0),
            hourly_row("2026-07-07 05:00:00", 12.5),
        ],
    )
    closes = daily_closes_from_hourly(path)
    assert closes == {date(2026, 7, 6): 11.0, date(2026, 7, 7): 12.5}


def test_daily_closes_from_hourly_rejects_disorder(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "btc.csv",
        [hourly_row("2026-07-06 02:00:00", 10.0), hourly_row("2026-07-06 01:00:00", 9.0)],
    )
    with pytest.raises(LiveBenchmarkError, match="SOURCE_ORDER_FAILURE"):
        daily_closes_from_hourly(path)


# ---------------------------------------------------------------- engine


def two_asset_config(**overrides: object) -> BenchmarkConfig:
    parameters: dict[str, object] = dict(
        name="synthetic",
        weights={"AAA": 0.5, "BBB": 0.5},
        fees={"AAA": 0.0, "BBB": 0.0, CASH_ASSET: 0.0},
        inception=date(2026, 7, 6),
        end=date(2026, 8, 31),
        starting_capital=1000.0,
    )
    parameters.update(overrides)
    return BenchmarkConfig(**parameters)  # type: ignore[arg-type]


def test_config_validation() -> None:
    with pytest.raises(LiveBenchmarkError, match="weights sum"):
        two_asset_config(weights={"AAA": 0.5, "BBB": 0.6}).validate()
    with pytest.raises(LiveBenchmarkError, match="end precedes"):
        two_asset_config(end=date(2026, 7, 5)).validate()
    with pytest.raises(LiveBenchmarkError, match="missing fee"):
        two_asset_config(fees={"AAA": 0.0, CASH_ASSET: 0.0}).validate()
    with pytest.raises(LiveBenchmarkError, match="cash fee"):
        two_asset_config(fees={"AAA": 0.0, "BBB": 0.0, CASH_ASSET: 0.1}).validate()


def test_missing_inception_close_fails_closed() -> None:
    closes = {"AAA": {date(2026, 7, 7): 10.0}, "BBB": {date(2026, 7, 6): 5.0, date(2026, 7, 7): 5.0}}
    with pytest.raises(LiveBenchmarkError, match="inception"):
        build_static_benchmark(two_asset_config(), closes)


def test_static_benchmark_hand_computed_two_month_scenario() -> None:
    """Fee-free two-asset benchmark with a weekend gap and one rebalance.

    Hand computation:
    - inception 2026-07-06 (Mon): 500 in AAA at 10.0 -> 50 units; 500 in BBB at
      100.0 -> 5 units.
    - 2026-07-07: AAA 12.0, BBB fresh 100.0 -> NAV 50*12 + 5*100 = 1100.
    - 2026-07-08 is a crypto-only session for AAA (BBB carried at 100.0):
      AAA 14.0 -> NAV 50*14 + 500 = 1200.
    - 2026-08-03 (first BBB session in August): AAA 10.0, BBB 110.0 ->
      NAV 500 + 550 = 1050; rebalance to 50/50 -> 525 each: 52.5 AAA units,
      4.7727... BBB units.
    - 2026-08-04: AAA 10.0, BBB 132.0 -> NAV 525 + 4.772727*132 = 1155.
    """
    aaa = {
        date(2026, 7, 6): 10.0,
        date(2026, 7, 7): 12.0,
        date(2026, 7, 8): 14.0,
        date(2026, 8, 3): 10.0,
        date(2026, 8, 4): 10.0,
    }
    bbb = {
        date(2026, 7, 6): 100.0,
        date(2026, 7, 7): 100.0,
        date(2026, 8, 3): 110.0,
        date(2026, 8, 4): 132.0,
    }
    config = two_asset_config(weights={"AAA": 0.5, "BBB": 0.5}, end=date(2026, 8, 4))
    # Make BBB the "equity" whose fresh close gates rebalancing by reusing SPY.
    config = BenchmarkConfig(
        name=config.name,
        weights={"AAA": 0.5, "SPY": 0.5},
        fees={"AAA": 0.0, "SPY": 0.0, CASH_ASSET: 0.0},
        inception=config.inception,
        end=config.end,
        starting_capital=config.starting_capital,
    )
    result = build_static_benchmark(config, {"AAA": aaa, "SPY": bbb})

    assert result.dates == (
        date(2026, 7, 6),
        date(2026, 7, 7),
        date(2026, 7, 8),
        date(2026, 8, 3),
        date(2026, 8, 4),
    )
    assert result.rebalance_dates == (date(2026, 8, 3),)
    expected = (1000.0, 1100.0, 1200.0, 1050.0, 1155.0)
    assert result.nav == pytest.approx(expected)
    assert result.total_fees == 0.0


def test_initial_fees_reduce_starting_nav() -> None:
    closes = {"AAA": {date(2026, 7, 6): 10.0}}
    config = BenchmarkConfig(
        name="fees",
        weights={"AAA": 1.0},
        fees={"AAA": 0.01, CASH_ASSET: 0.0},
        inception=date(2026, 7, 6),
        end=date(2026, 7, 6),
        starting_capital=1000.0,
    )
    result = build_static_benchmark(config, closes)
    # notional = 1000 / 1.01; fee = notional * 0.01; NAV = notional.
    assert result.nav[0] == pytest.approx(1000.0 / 1.01)
    assert result.total_fees == pytest.approx(1000.0 / 1.01 * 0.01)


def test_rebalance_fees_charged_on_turnover() -> None:
    aaa = {date(2026, 7, 6): 10.0, date(2026, 8, 3): 20.0}
    spy = {date(2026, 7, 6): 100.0, date(2026, 8, 3): 100.0}
    fee = 0.001
    config = BenchmarkConfig(
        name="turnover",
        weights={"AAA": 0.5, "SPY": 0.5},
        fees={"AAA": fee, "SPY": fee, CASH_ASSET: 0.0},
        inception=date(2026, 7, 6),
        end=date(2026, 8, 3),
        starting_capital=1000.0,
    )
    result = build_static_benchmark(config, {"AAA": aaa, "SPY": spy})
    assert result.rebalance_dates == (date(2026, 8, 3),)
    # Hand computation: inception buys 500/1.001 notional per asset
    # (fees 2 * 0.4995005). AAA doubles by Aug 3 -> NAV 1498.5014985; the
    # rebalance turns over ~249.75 notional per asset -> fees 0.4995005 and
    # post-rebalance NAV 1498.001998.
    assert result.nav[-1] == pytest.approx(1498.001998, abs=1e-5)
    assert result.total_fees == pytest.approx(1.4985015, abs=1e-6)


def test_benchmark_b_cash_is_feeless_and_flat() -> None:
    spy = {date(2026, 7, 6): 100.0, date(2026, 7, 7): 110.0}
    config = BenchmarkConfig(
        name="b",
        weights={"SPY": 0.6, CASH_ASSET: 0.4},
        fees={"SPY": 0.0, CASH_ASSET: 0.0},
        inception=date(2026, 7, 6),
        end=date(2026, 7, 7),
        starting_capital=1000.0,
    )
    result = build_static_benchmark(config, {"SPY": spy})
    # 600 in SPY (+10%), 400 cash flat -> 660 + 400.
    assert result.nav == pytest.approx((1000.0, 1060.0))


# ---------------------------------------------------------------- coverage guard


def coverage_config(end: date, **overrides: object) -> BenchmarkConfig:
    parameters: dict[str, object] = dict(
        name="coverage",
        weights={"AAA": 0.5, "BBB": 0.5},
        fees={"AAA": 0.0, "BBB": 0.0, CASH_ASSET: 0.0},
        inception=date(2026, 7, 6),
        end=end,
        starting_capital=1000.0,
    )
    parameters.update(overrides)
    return BenchmarkConfig(**parameters)  # type: ignore[arg-type]


def test_coverage_guard_allows_sources_within_tolerance() -> None:
    # BBB stops on Friday 2026-07-10 and is valued through Monday 2026-07-13.
    aaa = {date(2026, 7, 6): 10.0, date(2026, 7, 13): 10.0}
    bbb = {date(2026, 7, 6): 10.0, date(2026, 7, 10): 10.0}
    result = build_static_benchmark(coverage_config(date(2026, 7, 13)), {"AAA": aaa, "BBB": bbb})
    assert result.dates[-1] == date(2026, 7, 13)


def test_coverage_guard_fails_closed_on_stale_source() -> None:
    aaa = {date(2026, 7, 6): 10.0, date(2026, 7, 31): 10.0}
    bbb = {date(2026, 7, 6): 10.0, date(2026, 7, 10): 10.0}
    with pytest.raises(LiveBenchmarkError, match=r"SOURCE_COVERAGE_FAILURE: BBB ends 2026-07-10"):
        build_static_benchmark(coverage_config(date(2026, 7, 31)), {"AAA": aaa, "BBB": bbb})


def test_coverage_guard_tolerance_is_configurable() -> None:
    aaa = {date(2026, 7, 6): 10.0, date(2026, 7, 31): 10.0}
    bbb = {date(2026, 7, 6): 10.0, date(2026, 7, 10): 10.0}
    config = coverage_config(date(2026, 7, 31), max_staleness_days=30)
    result = build_static_benchmark(config, {"AAA": aaa, "BBB": bbb})
    assert result.dates[-1] == date(2026, 7, 31)
    with pytest.raises(LiveBenchmarkError, match="negative max_staleness_days"):
        coverage_config(date(2026, 7, 31), max_staleness_days=-1).validate()


# ---------------------------------------------------------------- metrics


def test_metrics_hand_computed() -> None:
    result = build_static_benchmark(
        BenchmarkConfig(
            name="metrics",
            weights={"AAA": 1.0},
            fees={"AAA": 0.0, CASH_ASSET: 0.0},
            inception=date(2026, 1, 1),
            end=date(2026, 1, 3),
            starting_capital=100.0,
        ),
        {"AAA": {date(2026, 1, 1): 10.0, date(2026, 1, 2): 12.0, date(2026, 1, 3): 9.0}},
    )
    metrics = compute_metrics(result, 100.0)
    assert metrics["final_nav"] == pytest.approx(90.0)
    assert metrics["cumulative_return"] == pytest.approx(-0.1)
    # Peak 120 -> trough 90: drawdown 25%.
    assert metrics["max_drawdown"] == pytest.approx(0.25)
    assert metrics["annualized_return"] == pytest.approx(0.9 ** (365.25 / 2) - 1.0)
    assert metrics["rebalance_count"] == 0
    assert metrics["observations"] == 3


def test_metrics_flat_series_has_null_calmar_and_sharpe() -> None:
    result = build_static_benchmark(
        BenchmarkConfig(
            name="flat",
            weights={"AAA": 1.0},
            fees={"AAA": 0.0, CASH_ASSET: 0.0},
            inception=date(2026, 1, 1),
            end=date(2026, 1, 3),
            starting_capital=100.0,
        ),
        {"AAA": {date(2026, 1, 1): 10.0, date(2026, 1, 2): 10.0, date(2026, 1, 3): 10.0}},
    )
    metrics = compute_metrics(result, 100.0)
    assert metrics["max_drawdown"] == 0.0
    assert metrics["calmar"] is None
    assert metrics["sharpe_zero_benchmark"] is None


# ---------------------------------------------------------------- canonical bytes


def test_canonical_bytes_are_lf_only_and_deterministic() -> None:
    result = build_static_benchmark(
        two_asset_config(weights={"AAA": 1.0}, fees={"AAA": 0.0, CASH_ASSET: 0.0}, end=date(2026, 7, 7)),
        {"AAA": {date(2026, 7, 6): 10.0, date(2026, 7, 7): 11.0}},
    )
    first = nav_csv_bytes(result)
    second = nav_csv_bytes(result)
    assert first == second
    assert b"\r" not in first
    payload = canonical_json_bytes({"b": 1, "a": 2})
    assert payload == canonical_json_bytes({"a": 2, "b": 1})
    assert b"\r" not in payload


# ---------------------------------------------------------------- runner end-to-end


def test_runner_end_to_end_on_synthetic_fixtures(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Crypto trades every day; equities skip the weekend of Jul 11-12.
    weekdays = ["2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10", "2026-07-13", "2026-07-14"]
    all_days = ["2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10", "2026-07-11", "2026-07-12", "2026-07-13", "2026-07-14"]

    def hourly_fixture(name: str, base: float) -> Path:
        rows = []
        for index, day in enumerate(all_days):
            rows.append(hourly_row(f"{day} 00:00:00", base + index))
            rows.append(hourly_row(f"{day} 23:00:00", base + index + 0.5))
        return write_csv(tmp_path / name, rows)

    def daily_fixture(name: str, base: float) -> Path:
        return write_csv(tmp_path / name, [daily_row(day, base + index) for index, day in enumerate(weekdays)])

    btc = hourly_fixture("btc.csv", 100.0)
    eth = hourly_fixture("eth.csv", 50.0)
    spy = daily_fixture("spy.csv", 700.0)
    qqq = daily_fixture("qqq.csv", 600.0)
    gld = daily_fixture("gld.csv", 300.0)
    out_dir = tmp_path / "artifacts"

    argv = [
        "--btc-data", str(btc),
        "--eth-data", str(eth),
        "--spy-data", str(spy),
        "--qqq-data", str(qqq),
        "--gld-data", str(gld),
        "--end", "2026-07-14",
        "--out-dir", str(out_dir),
    ]
    assert runner_main(argv) == 0
    output = capsys.readouterr().out
    assert "status: PASS" in output

    produced = sorted(p.name for p in out_dir.iterdir())
    assert produced == ["benchmark_a_nav.csv", "benchmark_b_nav.csv", "benchmark_metrics.json", "manifest.json"]

    nav_a = (out_dir / "benchmark_a_nav.csv").read_bytes()
    assert b"\r" not in nav_a
    # Union calendar: crypto keeps the weekend in Benchmark A (8 sessions);
    # Benchmark B follows SPY only (6 sessions).
    assert nav_a.decode().count("\n") == 1 + len(all_days)
    nav_b = (out_dir / "benchmark_b_nav.csv").read_bytes()
    assert nav_b.decode().count("\n") == 1 + len(weekdays)

    # Replay: a second full invocation writes byte-identical artifacts.
    first_bytes = {p.name: p.read_bytes() for p in out_dir.iterdir()}
    assert runner_main(argv) == 0
    second_bytes = {p.name: p.read_bytes() for p in out_dir.iterdir()}
    assert first_bytes == second_bytes
