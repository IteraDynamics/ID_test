"""Integration tests — full backtest pipeline.

Verifies:
- End-to-end backtest runs without error on synthetic data.
- Output shapes are consistent with input.
- No lookahead: equity at bar i uses only data up to bar i.
- Metrics are numerically sane.
- Artifact generation does not raise.
- Portfolio backtest runs with all three sleeves.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.fixtures.data_factory import make_df, make_flat_df

from research.harness.data_loader import make_synthetic_ohlcv
from research.harness.backtest_engine import run_backtest, BacktestResult
from research.harness.metrics import compute_metrics, BacktestMetrics
from research.harness.artifacts import save_artifacts
from research.strategies import (
    equity_qqq_sma_band_v1,
    equity_qqq_trend_v1,
    equity_spy_sma_band_v1,
    mean_reversion,
    trend_following,
    volatility_breakout,
)
from research.portfolio.blend import run_portfolio_backtest, SleeveConfig
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext


@pytest.fixture
def df_500():
    return make_synthetic_ohlcv(n_bars=500, seed=0)


@pytest.fixture
def df_1000():
    return make_synthetic_ohlcv(n_bars=1000, seed=7)


# ─────────────────────────────────────────────────────────────────────────────
# Single-strategy backtest
# ─────────────────────────────────────────────────────────────────────────────

class TestSingleStrategyBacktest:
    def test_trend_following_runs(self, df_500):
        result = run_backtest(df_500, trend_following, initial_capital=100_000)
        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) == len(df_500)

    def test_vol_breakout_runs(self, df_500):
        result = run_backtest(df_500, volatility_breakout, initial_capital=100_000)
        assert len(result.equity_curve) == len(df_500)

    def test_mean_reversion_runs(self, df_500):
        df_flat = make_flat_df(n=500)
        result = run_backtest(df_flat, mean_reversion, initial_capital=100_000)
        assert len(result.equity_curve) == len(df_flat)

    def test_equity_curve_starts_at_initial_capital(self, df_500):
        result = run_backtest(df_500, trend_following, initial_capital=50_000)
        # First bar: no trade yet, equity ≈ initial capital
        assert abs(float(result.equity_curve.iloc[0]) - 50_000) < 100

    def test_equity_curve_always_positive(self, df_500):
        result = run_backtest(df_500, trend_following)
        assert (result.equity_curve > 0).all()

    def test_exposure_in_bounds(self, df_500):
        result = run_backtest(df_500, trend_following)
        assert (result.position_series >= 0.0).all()
        assert (result.position_series <= 1.001).all()  # 0.1% tolerance for float arithmetic

    def test_output_aligned_to_input(self, df_500):
        result = run_backtest(df_500, trend_following)
        assert (result.equity_curve.index == df_500.index).all()
        assert len(result.intent_series) == len(df_500)

    def test_regime_series_aligned(self, df_500):
        result = run_backtest(df_500, trend_following)
        assert len(result.regime_series) == len(df_500)

    def test_deterministic(self, df_500):
        r1 = run_backtest(df_500, trend_following, initial_capital=100_000)
        r2 = run_backtest(df_500, trend_following, initial_capital=100_000)
        assert (r1.equity_curve.values == r2.equity_curve.values).all()

    def test_params_stored(self, df_500):
        result = run_backtest(df_500, trend_following, initial_capital=75_000)
        assert result.params["initial_capital"] == 75_000

    def test_no_lookahead_bar_50_vs_bar_200(self):
        """Equity at bar 50 must be identical whether we run to bar 50 or bar 200."""
        df = make_synthetic_ohlcv(n_bars=300, seed=3)
        r_full = run_backtest(df, trend_following)
        r_short = run_backtest(df.iloc[:51], trend_following)
        # The equity at bar 50 from the full run must match the short run
        assert abs(
            float(r_full.equity_curve.iloc[50]) - float(r_short.equity_curve.iloc[50])
        ) < 1.0, "Lookahead detected: equity at bar 50 differs between full and truncated runs"


# ─────────────────────────────────────────────────────────────────────────────
# Research-only equity sleeves
# ─────────────────────────────────────────────────────────────────────────────

class TestResearchEquitySleeves:
    def test_spy_sma_sleeve_enters_when_close_above_sma(self):
        df = make_synthetic_ohlcv(n_bars=220, seed=11)
        df["close"] = np.linspace(100.0, 150.0, len(df))
        df["open"] = df["close"]
        df["high"] = df["close"] * 1.01
        df["low"] = df["close"] * 0.99
        ctx = StrategyContext(regime=RegimeLabel.TREND_UP, asset="SPY")

        intent = equity_spy_sma_band_v1.generate_intent(df, ctx)

        assert intent.action == Action.ENTER_LONG
        assert intent.desired_exposure_frac == 1.0
        assert intent.meta["single_asset_sleeve"] is True
        assert "target_weights" not in intent.meta

    def test_qqq_sma_sleeve_exits_when_close_below_sma(self):
        df = make_synthetic_ohlcv(n_bars=220, seed=12)
        df["close"] = np.linspace(150.0, 100.0, len(df))
        df["open"] = df["close"]
        df["high"] = df["close"] * 1.01
        df["low"] = df["close"] * 0.99
        ctx = StrategyContext(
            regime=RegimeLabel.TREND_DOWN,
            asset="QQQ",
            current_exposure_frac=1.0,
        )

        intent = equity_qqq_sma_band_v1.generate_intent(df, ctx)

        assert intent.action == Action.EXIT_LONG
        assert intent.desired_exposure_frac == 0.0
        assert intent.meta["single_asset_sleeve"] is True
        assert "target_weights" not in intent.meta

    def test_qqq_growth_sleeve_runs_in_backtest(self, df_500):
        result = run_backtest(
            df_500,
            equity_qqq_trend_v1,
            initial_capital=25_000,
            asset="QQQ",
        )
        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) == len(df_500)
        assert (result.equity_curve > 0).all()


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

class TestBacktestMetrics:
    def test_metrics_run(self, df_500):
        result = run_backtest(df_500, trend_following)
        m = compute_metrics(result.equity_curve, result.trades, result.params)
        assert isinstance(m, BacktestMetrics)

    def test_n_bars_correct(self, df_500):
        result = run_backtest(df_500, trend_following)
        m = compute_metrics(result.equity_curve, result.trades, result.params)
        assert m.n_bars == len(df_500)

    def test_initial_equity_correct(self, df_500):
        result = run_backtest(df_500, trend_following, initial_capital=123_456)
        m = compute_metrics(result.equity_curve, result.trades, result.params)
        assert abs(m.initial_equity - 123_456) < 100

    def test_max_drawdown_non_positive(self, df_500):
        result = run_backtest(df_500, trend_following)
        m = compute_metrics(result.equity_curve, result.trades, result.params)
        assert m.max_drawdown_pct <= 0.0

    def test_sharpe_is_float(self, df_500):
        result = run_backtest(df_500, trend_following)
        m = compute_metrics(result.equity_curve, result.trades, result.params)
        assert isinstance(m.sharpe, float)

    def test_to_dict_has_required_keys(self, df_500):
        result = run_backtest(df_500, trend_following)
        m = compute_metrics(result.equity_curve, result.trades, result.params)
        d = m.to_dict()
        for key in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "n_trades"]:
            assert key in d

    def test_to_markdown_is_string(self, df_500):
        result = run_backtest(df_500, trend_following)
        m = compute_metrics(result.equity_curve, result.trades, result.params)
        md = m.to_markdown()
        assert isinstance(md, str)
        assert "CAGR" in md


# ─────────────────────────────────────────────────────────────────────────────
# Artifacts
# ─────────────────────────────────────────────────────────────────────────────

class TestArtifacts:
    def test_save_artifacts(self, df_500):
        result = run_backtest(df_500, trend_following)
        m = compute_metrics(result.equity_curve, result.trades, result.params)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = save_artifacts(result, m, run_id="test", out_dir=tmpdir, save_chart=False)
            files = list(Path(tmpdir).rglob("*"))
            fnames = {f.name for f in files if f.is_file()}
            assert "equity_curve.csv" in fnames
            assert "trades.csv" in fnames
            assert "summary.json" in fnames
            assert "summary.md" in fnames

    def test_equity_curve_csv_correct(self, df_500):
        result = run_backtest(df_500, trend_following)
        m = compute_metrics(result.equity_curve, result.trades, result.params)
        with tempfile.TemporaryDirectory() as tmpdir:
            save_artifacts(result, m, run_id="test", out_dir=tmpdir, save_chart=False)
            eq_df = pd.read_csv(Path(tmpdir) / "equity_curve.csv", index_col=0)
            assert "equity" in eq_df.columns
            assert len(eq_df) == len(df_500)


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio backtest
# ─────────────────────────────────────────────────────────────────────────────

class TestPortfolioBacktest:
    def test_portfolio_runs(self, df_1000):
        sleeves = [
            SleeveConfig(strategy_module=trend_following, weight=0.5, label="trend"),
            SleeveConfig(strategy_module=volatility_breakout, weight=0.3, label="vol"),
            SleeveConfig(strategy_module=mean_reversion, weight=0.2, label="rev"),
        ]
        port_result, metrics = run_portfolio_backtest(
            df=df_1000,
            sleeves=sleeves,
            initial_capital=100_000,
        )
        assert len(port_result.equity_curve) == len(df_1000)
        assert isinstance(metrics, BacktestMetrics)

    def test_portfolio_equity_positive(self, df_1000):
        sleeves = [
            SleeveConfig(strategy_module=trend_following, weight=1.0, label="trend"),
        ]
        port_result, _ = run_portfolio_backtest(df_1000, sleeves)
        assert (port_result.equity_curve > 0).all()

    def test_portfolio_blended_exposure_in_bounds(self, df_1000):
        sleeves = [
            SleeveConfig(strategy_module=trend_following, weight=0.6, label="trend"),
            SleeveConfig(strategy_module=volatility_breakout, weight=0.4, label="vol"),
        ]
        port_result, _ = run_portfolio_backtest(df_1000, sleeves)
        assert (port_result.blended_exposure >= 0.0).all()
        assert (port_result.blended_exposure <= 1.001).all()

    def test_empty_sleeves_raises(self, df_1000):
        with pytest.raises(ValueError, match="No sleeves"):
            run_portfolio_backtest(df_1000, sleeves=[])
