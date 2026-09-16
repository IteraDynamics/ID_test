import numpy as np
import pandas as pd
import pytest
from research.regime_reversal.experiment import tag_orders, select_orders, POLICY, GAP_LOOKBACK_HOURS
from research.crypto_reversal.experiment import HOUR, simulate


def fixture():
    idx = pd.date_range('2020-01-01', periods=400, freq='h', tz='UTC')
    close = np.linspace(100, 110, len(idx))
    frame = pd.DataFrame(dict(open=close, high=close+1, low=close-1, close=close, volume=1.), index=idx)
    start = idx[300]
    orders = {start+5*HOUR: {'signal_start':str(start), 'available_at':str(start+4*HOUR)}}
    return frame, orders, {start:'TREND_DOWN'}


def test_frozen_primary():
    assert POLICY.name == 'stabilized_4h_hold24h'
    assert GAP_LOOKBACK_HOURS == 240


def test_information_timing_and_no_future_gap_screen():
    frame, orders, states = fixture()
    result = tag_orders(frame, orders, states)
    entry = next(iter(orders))
    assert result[entry]['regime'] == 'TREND_DOWN'
    assert result[entry]['gap_clean']
    # A missing future exit must not affect eligibility.
    gapped = frame.drop(entry+24*HOUR)
    assert tag_orders(gapped, orders, states) == result
    assert not tag_orders(frame.drop(entry-10*HOUR), orders, states)[entry]['gap_clean']


def test_reject_unavailable_state():
    frame, orders, states = fixture()
    with pytest.raises(ValueError, match='Missing exact'):
        tag_orders(frame, orders, {})
    meta = next(iter(orders.values()))
    with pytest.raises(ValueError, match='timing'):
        tag_orders(frame, {pd.Timestamp(meta['available_at']): meta}, states)


def test_all_orders_preserve_exact_original_ledger():
    frame, orders, states = fixture()
    tagged = tag_orders(frame, orders, states)
    kwargs = dict(hold_hours=24, one_way_bps=30, start=frame.index[250], end=frame.index[-1])
    original = simulate(frame, orders, **kwargs)
    rerun = simulate(frame, select_orders(tagged), **kwargs)
    pd.testing.assert_frame_equal(original.curve, rerun.curve)
    assert original.trades == rerun.trades
    assert original.fills == rerun.fills
    assert select_orders(tagged, 'TREND_UP') == {}
    assert select_orders(tagged, 'TREND_DOWN') == tagged


def test_missing_exit_is_deferred_not_deleted():
    frame, orders, states = fixture()
    entry = next(iter(orders))
    frame = frame.drop(entry+24*HOUR)
    tagged = tag_orders(frame, orders, states)
    run = simulate(frame, select_orders(tagged, clean_only=True), 24, 30, frame.index[250], frame.index[-1])
    assert len(run.trades) == 1
    assert run.trades[0]['exit_delay_hours'] == 1
