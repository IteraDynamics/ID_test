"""Preserve the known HOLD discrepancy until a separate governed correction."""
import pandas as pd
import pytest
from research.harness.backtest_engine import run_backtest
from research.strategies.contracts import Action, StrategyIntent


class PartialHold:
    @staticmethod
    def generate_intent(df, ctx, closed_only=True):
        first = ctx.bar_index == 0
        return StrategyIntent(Action.ENTER_LONG if first else Action.HOLD, 1., .8 if first else .5, 1, 'characterize existing HOLD behavior')


def test_backtest_currently_retains_exposure_on_partial_hold():
    frame = pd.DataFrame({'open': 100., 'high': 100., 'low': 100., 'close': 100., 'volume': 1000.}, index=pd.date_range('2024-01-01', periods=4, freq='h'))
    result = run_backtest(frame, PartialHold, fee_rate=0., slippage_bps=0.)
    assert result.intent_series[-1].desired_exposure_frac == .5
    assert result.position_series.iloc[-1] == pytest.approx(result.position_series.iloc[0])
    assert result.position_series.iloc[-1] > .75
    assert len(result.trades) == 1
