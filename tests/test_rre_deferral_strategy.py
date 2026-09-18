from __future__ import annotations

from types import SimpleNamespace
import pandas as pd

from research.rre_deferral_strategy import RREDeferralStrategy
from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.regimes.contracts import RegimeLabel


class Stub:
    STRATEGY_ID="stub"
    @staticmethod
    def generate_intent(df,ctx,closed_only=True):
        return StrategyIntent(Action.ENTER_LONG,1.0,.9,24,"canonical",{}, "stub")


def frame():
    return pd.DataFrame({"close":[100.]},index=pd.DatetimeIndex(["2024-06-01T04:00:00Z"]))


def ctx(exposure=.2):
    return StrategyContext(RegimeLabel.TREND_UP,exposure,"BTC",0,{})


def test_wrapper_defers_using_latest_prior_daily_score():
    scores=pd.Series([.9],index=pd.DatetimeIndex(["2024-06-01T00:00:00Z"]))
    w=RREDeferralStrategy(Stub,"BTC_4H_trend",scores,.8)
    got=w.generate_intent(frame(),ctx())
    assert got.action==Action.HOLD
    assert got.desired_exposure_frac==.2
    assert got.horizon_hours==24
    assert w.audit[0]["deferred"] is True


def test_wrapper_never_uses_future_daily_score():
    scores=pd.Series([.9],index=pd.DatetimeIndex(["2024-06-02T00:00:00Z"]))
    w=RREDeferralStrategy(Stub,"BTC_4H_trend",scores,.8)
    got=w.generate_intent(frame(),ctx())
    assert got.action==Action.ENTER_LONG
    assert w.audit[0]["reason_code"]=="RRE_UNAVAILABLE_CANONICAL"


def test_wrapper_below_cutoff_preserves_exact_canonical_intent():
    scores=pd.Series([.79],index=pd.DatetimeIndex(["2024-06-01T00:00:00Z"]))
    w=RREDeferralStrategy(Stub,"ETH_1H_trend",scores,.8)
    got=w.generate_intent(frame(),ctx())
    assert got==Stub.generate_intent(frame(),ctx())
