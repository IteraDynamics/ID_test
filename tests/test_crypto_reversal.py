from dataclasses import replace
import json

import numpy as np
import pandas as pd
import pytest

from research.crypto_reversal.experiment import (
    HOUR, Run, combine, load_input, metrics, policies, schedule, signal_bars,
    simulate, trade_diagnostics, validate_frame)
from research.crypto_reversal.run import execute, exposure_control, main


def prices(n=300):
    index = pd.date_range('2020-01-01', periods=n, freq='h', tz='UTC')
    close = 100*np.exp(np.cumsum(np.where(np.arange(n) % 2, .001, -.001)))
    opening = np.r_[100., close[:-1]]
    return pd.DataFrame(dict(open=opening, high=np.maximum(opening, close)*1.002,
                             low=np.minimum(opening, close)*.998, close=close, volume=1.), index=index)


def order(f, i):
    return {f.index[i]: {'signal_start': str(f.index[i]-2*HOUR),
                          'available_at': str(f.index[i]-HOUR)}}


def test_exact_spot_accounting_and_terminal_costs():
    f = prices(10)
    r = simulate(f, order(f, 2), 7, 30, f.index[0], f.index[-1])
    expected = (f.open.iloc[-1]/f.open.iloc[2])*(1-.003)/(1+.003)
    assert r.curve.nav.iloc[-1] == pytest.approx(expected)
    assert len(r.trades) == 1 and len(r.fills) == 2
    assert r.trades[0]['terminal_exit']
    assert r.diagnostics['replay_max_relative_error'] < 1e-12
    assert r.curve.exposure.iloc[-1] == 0
    assert r.curve.fees.sum() == pytest.approx(sum(x['fee'] for x in r.fills))


def test_missing_exit_defers_instead_of_deleting_trade():
    f = prices(12)
    r = simulate(f.drop(f.index[[5, 6]]), order(f, 2), 3, 0, f.index[0], f.index[-1])
    assert r.trades[0]['exit_time'] == str(f.index[7])
    assert r.trades[0]['exit_delay_hours'] == 2
    assert r.trades[0]['hold_hours'] == 5
    assert r.diagnostics['held_stale_marks'] == 2
    assert r.diagnostics['deferred_exits'] == 1


def test_missing_entry_cancels_no_fill_or_future_substitution():
    f = prices(10)
    r = simulate(f.drop(f.index[2]), order(f, 2), 3, 30, f.index[0], f.index[-1])
    assert not r.fills
    assert r.diagnostics['cancelled_missing_entries'] == 1
    assert (r.curve.nav == 1).all()


def test_no_overlap_or_same_open_reentry():
    f = prices(15)
    orders = order(f, 2) | order(f, 3) | order(f, 5) | order(f, 6)
    r = simulate(f, orders, 3, 0, f.index[0], f.index[-1])
    assert [t['entry_time'] for t in r.trades] == [str(f.index[2]), str(f.index[6])]
    assert r.diagnostics['ignored_signals'] == 2


def test_information_boundary_and_lag():
    f = prices()
    b = signal_bars(f, 4)
    b.loc[:, 'stabilized'] = False
    b.loc[b.index[10], 'stabilized'] = True
    p = policies()[0]
    a, d = schedule(b, p, 1), schedule(b, p, 2)
    t = b.index[10]
    assert list(a) == [t+5*HOUR]
    assert list(d) == [t+6*HOUR]
    bad = {f.index[2]: {'available_at': str(f.index[2]), 'signal_start': str(f.index[1])}}
    with pytest.raises(ValueError, match='availability'):
        simulate(f, bad, 3, 0, f.index[0], f.index[-1])


def test_stabilization_and_trailing_sigma_use_only_completed_past():
    f = prices()
    shock = 200
    f.loc[f.index[shock], ['open', 'high', 'low', 'close']] = [100., 101., 89., 90.]
    f.loc[f.index[shock+1], ['open', 'high', 'low', 'close']] = [90., 95., 90., 94.]
    b = signal_bars(f, 1)
    assert b.shock.iloc[shock] and b.stabilized.iloc[shock+1]
    old_sigma = b.sigma_prior.iloc[shock]
    changed = f.copy()
    changed.loc[changed.index[shock], ['close', 'low']] = [80., 79.]
    assert signal_bars(changed, 1).sigma_prior.iloc[shock] == old_sigma
    future = f.copy()
    future.iloc[shock+2:, :4] *= 5
    pd.testing.assert_frame_equal(signal_bars(future, 1).iloc[:shock+2], b.iloc[:shock+2])
    partial = signal_bars(f.iloc[:shock+2], 1)
    pd.testing.assert_frame_equal(partial, b.iloc[:shock+2])


def test_incomplete_4h_bars_and_missing_lookback_disable_signals():
    f = prices()
    gap = f.index[100]
    b = signal_bars(f.drop(gap), 4)
    assert pd.isna(b.loc[gap.floor('4h'), 'close'])
    assert b.loc[gap.floor('4h')+4*HOUR:gap.floor('4h')+168*HOUR, 'sigma_prior'].isna().all()
    partial = signal_bars(f.iloc[:102], 4)
    assert pd.isna(partial.iloc[-1].close)


def test_combination_is_capital_weighted_not_average_returns():
    f = prices(10)
    a = simulate(f, order(f, 2), 4, 30, f.index[0], f.index[-1])
    b = simulate(f, {}, 4, 30, f.index[0], f.index[-1])
    c = combine(a, b)
    np.testing.assert_allclose(c.curve.nav, .5*a.curve.nav+.5*b.curve.nav)
    np.testing.assert_allclose(c.curve.exposure, a.curve.exposure*a.curve.nav/(a.curve.nav+b.curve.nav))


def test_exposure_control_matches_mean_and_is_labeled_hindsight():
    f = prices(200)
    b = simulate(f, order(f, 0), 199, 30, f.index[0], f.index[-1])
    c, w = exposure_control(b, .2)
    assert c.curve.exposure.iloc[1:].mean() == pytest.approx(.2)
    assert 0 < w < 1
    assert 'hindsight_initial_risky_allocation' in c.diagnostics


def test_validation_rejects_bad_prices_duplicates_and_snapshot(tmp_path):
    f = prices(20)
    validate_frame(f)
    with pytest.raises(ValueError): validate_frame(pd.concat([f, f]))
    bad = f.copy()
    bad.iloc[2, bad.columns.get_loc('open')] = -1
    with pytest.raises(ValueError): validate_frame(bad)
    bad = f.copy()
    bad.iloc[2, bad.columns.get_loc('open')] = 10000
    with pytest.raises(ValueError, match='range'): validate_frame(bad)
    path = tmp_path/'unknown.csv'
    path.write_text('wrong data')
    with pytest.raises(ValueError, match='SHA256'): load_input(path, 'BTC')


def test_drawdown_includes_initial_capital_and_sharpe_is_daily():
    idx = pd.date_range('2020-01-01', periods=49, freq='h', tz='UTC')
    nav = np.r_[1., np.full(24, .9), np.full(24, .99)]
    curve = pd.DataFrame(dict(nav=nav, exposure=0., fees=0., turnover=0.), index=idx)
    m = metrics(curve)
    assert m['max_drawdown'] == pytest.approx(-.1)
    assert m['zero_cash_sharpe'] == pytest.approx(0., abs=1e-12)


def test_break_even_cost_solves_compounding_equation():
    ts = [dict(gross_return=.02, net_return=.01, net_pnl=.01)]*10
    d = trade_diagnostics(ts)
    c = d['geometric_break_even_one_way_bps']/10000
    assert (1.02*(1-c)/(1+c))**10 == pytest.approx(1.)
    assert d['terminal_multiple_without_top5'] == pytest.approx(1.01**5)


def test_cli_failure_is_packaged_without_network(tmp_path):
    code = main(['--data-root', str(tmp_path/'missing'), '--output-root', str(tmp_path)])
    assert code == 1
    assert len(list(tmp_path.glob('*.zip'))) == 1
    status = json.loads(next(tmp_path.glob('crypto_reversal_*/status.json')).read_text())
    assert status['success'] is False and status['performance'] is None


def test_entire_experiment_writes_all_controls_on_synthetic_data(tmp_path, capsys):
    f = prices(300)
    status = execute({'BTC': f, 'ETH': f.copy()}, tmp_path, f.index[200], f.index[296])
    assert status['accounting_and_fill_replay_passed']
    summary = pd.read_csv(tmp_path/'summary.csv')
    full = summary[summary.period == 'full']
    assert len(full) == 4*26*3  # 18 policies + 6 exposure controls + cash and buy-hold.
    assert len(full[full.role == 'primary']) == 12
    assert set(full.asset) == {'BTC', 'ETH', 'MIX'}
    assert (tmp_path/'fills.csv').is_file()
    assert 'EXPLORATORY' in (tmp_path/'RESULTS.txt').read_text()
