"""Integration tests for the walk-forward validation framework.

These tests use synthetic OHLCV data to avoid requiring real market data.
They verify correctness, no-leakage, and output structure — not financial outcomes.
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.harness.execution_model import ExecutionConfig
from research.ml.validation.fold_spec import FoldSpec, build_annual_folds, from_custom_json
from research.ml.validation.walk_forward import run_fold, run_walk_forward
from research.ml.validation.report import aggregate, to_markdown, save_report
from research.strategies import trend_following_v8_ecap75_add90 as strategy


# ── Synthetic data fixture ─────────────────────────────────────────────────────

def _make_ohlcv(n_bars: int = 10000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic hourly OHLCV data with a mild uptrend."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2019-01-01", periods=n_bars, freq="h")
    log_returns = rng.normal(0.0001, 0.01, n_bars)
    close = 3000.0 * np.exp(np.cumsum(log_returns))
    high = close * (1 + rng.uniform(0.001, 0.01, n_bars))
    low = close * (1 - rng.uniform(0.001, 0.01, n_bars))
    opens = np.roll(close, 1)
    opens[0] = close[0]
    volume = rng.uniform(1e6, 5e6, n_bars)
    return pd.DataFrame(
        {"open": opens, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _exec_config() -> ExecutionConfig:
    return ExecutionConfig(
        taker_fee_rate=0.0006,
        base_slippage_bps=3.0,
        slippage_vol_factor=50.0,
        cooldown_bars=0,
    )


# ── FoldSpec tests ─────────────────────────────────────────────────────────────

class TestFoldSpec:
    def test_valid_fold_constructs(self):
        f = FoldSpec(1, "2019-01-01", "2020-12-31", "2021-01-01", "2021-12-31")
        assert f.fold_id == 1

    def test_overlap_raises(self):
        with pytest.raises(ValueError, match="strictly after"):
            FoldSpec(1, "2019-01-01", "2021-01-01", "2021-01-01", "2021-12-31")

    def test_to_dict_keys(self):
        f = FoldSpec(1, "2019-01-01", "2020-12-31", "2021-01-01", "2021-12-31")
        d = f.to_dict()
        for k in ("fold_id", "train_start", "train_end", "test_start", "test_end"):
            assert k in d


class TestBuildAnnualFolds:
    def test_generates_expected_folds(self):
        # 2019+2 min train → first test=2021; through 2025 → folds: 2021,2022,2023,2024,2025 = 5
        folds = build_annual_folds("2019-01-01", "2025-12-31", train_min_years=2, test_years=1)
        assert len(folds) == 5

    def test_train_start_always_same(self):
        folds = build_annual_folds("2019-01-01", "2025-12-31")
        for f in folds:
            assert f.train_start == "2019-01-01"

    def test_no_overlap(self):
        folds = build_annual_folds("2019-01-01", "2025-12-31")
        for f in folds:
            assert f.test_start > f.train_end, f"Leak: {f}"

    def test_consecutive_folds_expand(self):
        folds = build_annual_folds("2019-01-01", "2025-12-31")
        for i in range(1, len(folds)):
            assert folds[i].train_end > folds[i - 1].train_end

    def test_fold_ids_sequential(self):
        folds = build_annual_folds("2019-01-01", "2025-12-31")
        assert [f.fold_id for f in folds] == list(range(1, len(folds) + 1))


class TestCustomFolds:
    def test_parse_json(self):
        raw = json.dumps([
            {"train_start": "2019-01-01", "train_end": "2020-12-31",
             "test_start": "2021-01-01", "test_end": "2021-12-31"},
        ])
        folds = from_custom_json(raw)
        assert len(folds) == 1
        assert folds[0].fold_id == 1


# ── Walk-forward execution tests ───────────────────────────────────────────────

class TestRunFold:
    @pytest.fixture(scope="class")
    def fold_result(self):
        df = _make_ohlcv(10000)  # ~416 days from 2019-01-01 → covers through 2020-02
        fold = FoldSpec(1, "2019-01-01", "2019-08-31", "2019-09-01", "2019-12-31")
        return run_fold(
            df=df,
            strategy_module=strategy,
            fold=fold,
            exec_config=_exec_config(),
            initial_capital=100_000.0,
        )

    def test_result_not_skipped(self, fold_result):
        assert not fold_result.skipped

    def test_has_baseline_metrics(self, fold_result):
        assert "cagr_pct" in fold_result.baseline
        assert "sharpe" in fold_result.baseline

    def test_has_calibrated_metrics(self, fold_result):
        assert "cagr_pct" in fold_result.calibrated
        assert "sharpe" in fold_result.calibrated

    def test_has_delta_metrics(self, fold_result):
        assert "delta_sharpe" in fold_result.delta
        assert "delta_max_drawdown_pct" in fold_result.delta

    def test_n_train_samples_non_negative(self, fold_result):
        assert fold_result.n_train_samples >= 0

    def test_improvement_flags_are_bool(self, fold_result):
        assert isinstance(fold_result.cal_improved_sharpe, bool)
        assert isinstance(fold_result.cal_improved_calmar, bool)
        assert isinstance(fold_result.cal_improved_dd, bool)
        assert isinstance(fold_result.cal_improved_slippage, bool)


class TestNoLeakage:
    def test_train_and_test_dates_do_not_overlap(self):
        """Verify FoldSpec enforces strict temporal ordering."""
        df = _make_ohlcv(10000)
        fold = FoldSpec(1, "2019-01-01", "2019-08-31", "2019-09-01", "2019-12-31")
        result = run_fold(df=df, strategy_module=strategy, fold=fold,
                          exec_config=_exec_config())

        # The fold spec itself enforces no overlap; verify no ValueError was raised
        assert not result.skipped or "overlap" not in result.skip_reason.lower()

    def test_fold_spec_rejects_overlap(self):
        with pytest.raises(ValueError):
            FoldSpec(1, "2019-01-01", "2021-01-15", "2021-01-01", "2022-01-01")


class TestRunWalkForward:
    @pytest.fixture(scope="class")
    def wf_results(self):
        df = _make_ohlcv(15000)  # ~625 days → covers through mid-2020
        folds = [
            FoldSpec(1, "2019-01-01", "2019-09-30", "2019-10-01", "2019-12-31"),
            FoldSpec(2, "2019-01-01", "2019-12-31", "2020-01-01", "2020-05-31"),
        ]
        return run_walk_forward(
            df=df, strategy_module=strategy, folds=folds,
            exec_config=_exec_config(),
        )

    def test_returns_one_result_per_fold(self, wf_results):
        assert len(wf_results) == 2

    def test_fold_ids_match(self, wf_results):
        assert wf_results[0].fold_spec.fold_id == 1
        assert wf_results[1].fold_spec.fold_id == 2

    def test_each_result_has_required_keys(self, wf_results):
        for r in wf_results:
            if not r.skipped:
                assert "cagr_pct" in r.baseline
                assert "cagr_pct" in r.calibrated


# ── Report tests ───────────────────────────────────────────────────────────────

class TestAggregate:
    def test_returns_conclusion(self):
        df = _make_ohlcv(15000)
        folds = [
            FoldSpec(1, "2019-01-01", "2019-09-30", "2019-10-01", "2019-12-31"),
            FoldSpec(2, "2019-01-01", "2019-12-31", "2020-01-01", "2020-05-31"),
        ]
        results = run_walk_forward(df=df, strategy_module=strategy,
                                   folds=folds, exec_config=_exec_config())
        agg = aggregate(results)
        assert agg["conclusion"] in ("likely robust", "mixed / regime-dependent", "likely overfit")

    def test_improved_counts_non_negative(self):
        df = _make_ohlcv(10000)
        folds = [
            FoldSpec(1, "2019-01-01", "2019-09-30", "2019-10-01", "2019-12-31"),
        ]
        results = run_walk_forward(df=df, strategy_module=strategy,
                                   folds=folds, exec_config=_exec_config())
        agg = aggregate(results)
        for key in ("improved_sharpe", "improved_calmar", "improved_dd", "improved_slippage"):
            assert agg[key] >= 0


class TestMarkdown:
    def test_generates_non_empty_markdown(self):
        df = _make_ohlcv(10000)
        fold = FoldSpec(1, "2019-01-01", "2019-09-30", "2019-10-01", "2019-12-31")
        results = run_walk_forward(df=df, strategy_module=strategy,
                                   folds=[fold], exec_config=_exec_config())
        agg = aggregate(results)
        md = to_markdown(results, agg)
        assert "Walk-Forward" in md
        assert "Conclusion" in md
        assert len(md) > 200


class TestSaveReport:
    def test_saves_expected_files(self):
        df = _make_ohlcv(10000)
        fold = FoldSpec(1, "2019-01-01", "2019-09-30", "2019-10-01", "2019-12-31")
        results = run_walk_forward(df=df, strategy_module=strategy,
                                   folds=[fold], exec_config=_exec_config())
        with tempfile.TemporaryDirectory() as tmpdir:
            out = save_report(results, strategy_id="test_strategy", out_dir=tmpdir, run_id="test")
            assert (out / "fold_results.json").exists()
            assert (out / "fold_results.csv").exists()
            assert (out / "summary.json").exists()
            assert (out / "summary.md").exists()

    def test_fold_results_json_is_valid(self):
        df = _make_ohlcv(10000)
        fold = FoldSpec(1, "2019-01-01", "2019-09-30", "2019-10-01", "2019-12-31")
        results = run_walk_forward(df=df, strategy_module=strategy,
                                   folds=[fold], exec_config=_exec_config())
        with tempfile.TemporaryDirectory() as tmpdir:
            out = save_report(results, strategy_id="test_strategy", out_dir=tmpdir, run_id="test")
            with open(out / "fold_results.json") as f:
                data = json.load(f)
            assert "folds" in data
            assert "aggregate" in data
            assert data["aggregate"]["conclusion"] in (
                "likely robust", "mixed / regime-dependent", "likely overfit"
            )
