import numpy as np
import pandas as pd
import pytest

from research.multidimensional_regimes.study import (
    FEATURES, STATES, TARGETS, StateModel, evaluate, panel_from_hourly, state_forecast, transition_rows,
)


def fixture_panel():
    rng = np.random.default_rng(73)
    index = pd.date_range('2018-01-01', '2020-01-15', freq='D', tz='UTC')
    p = pd.DataFrame(rng.normal(size=(len(index), len(FEATURES))), index=index, columns=FEATURES)
    p['log_atr'] -= 4
    p['efficiency'] = rng.uniform(size=len(p))
    p['atr_accel'] *= .2
    p['core_label'] = np.where(p.strength > 0, 'UP', 'DOWN')
    for target in TARGETS:
        p[target] = rng.normal(size=len(p))
    p['downside'] = rng.integers(0, 2, size=len(p))
    p['future_efficiency'] = rng.uniform(size=len(p))
    p['label_end'] = p.index + pd.Timedelta(days=1)
    return p


def test_fit_is_deterministic_and_outcome_independent():
    p = fixture_panel().iloc[:400]
    altered = p.copy()
    altered[TARGETS] = 1000
    a, b = StateModel().fit(p), StateModel().fit(altered)
    assert a.metadata() == b.metadata()
    pd.testing.assert_frame_equal(a.transform(p)[STATES], b.transform(p)[STATES])


def test_transform_is_batch_and_future_independent():
    p = fixture_panel()
    model = StateModel().fit(p.iloc[:400])
    expected = model.transform(p.iloc[400:410])[STATES]
    changed = p.iloc[400:].copy()
    changed.loc[changed.index[10:], FEATURES] = 999
    pd.testing.assert_frame_equal(expected, model.transform(changed).iloc[:10][STATES])


def test_training_only_cutoffs_and_rule_axes():
    p = fixture_panel()
    model = StateModel().fit(p.iloc[:400])
    np.testing.assert_allclose(model.vol_cutoffs, p.iloc[:400].log_atr.quantile([1/3, 2/3]))
    out = model.transform(p)
    assert out.rule_joint.nunique() <= 81
    assert out.learned.nunique() <= 6
    assert set(out.direction) <= {'UP', 'DOWN', 'NEUTRAL'}
    assert set(out.path_structure) <= {'CHOPPY', 'MIXED', 'PERSISTENT'}


def test_rejects_insufficient_and_nonfinite_features():
    p = fixture_panel()
    with pytest.raises(ValueError):
        StateModel().fit(p.iloc[:249])
    model = StateModel().fit(p)
    p.iloc[0, 0] = np.inf
    with pytest.raises(ValueError):
        model.transform(p)


def test_sparse_and_unseen_fallback():
    train = pd.DataFrame({'s': ['a']*30 + ['b']*2, 'y': [1.]*30 + [10.]*2})
    pred = state_forecast(train, pd.DataFrame({'s': ['a', 'b', 'new']}), 's', 'y')
    prior = train.y.mean()
    np.testing.assert_allclose(pred, [(30+20*prior)/50, prior, prior])


def test_transitions_do_not_bridge_missing_days():
    p = pd.DataFrame({'state': ['a', 'b', 'c']}, index=pd.to_datetime(['2020-01-01', '2020-01-02', '2020-01-04'], utc=True))
    assert transition_rows(p, 'state') == [dict(from_state='a', to_state='b', transitions=1, probability=1.)]


def test_walk_forward_boundaries_and_outcome_poisoning():
    p = fixture_panel()
    original = evaluate(p, 'SYNTHETIC', 1, years=[2020])
    p.loc[p.index.year == 2020, TARGETS] = 999
    poisoned = evaluate(p, 'SYNTHETIC', 1, years=[2020])
    assert original['states'] == poisoned['states']
    assert original['fits'] == poisoned['fits']
    assert [r['prediction'] for r in original['forecasts']] == [r['prediction'] for r in poisoned['forecasts']]
    for row in original['forecasts']:
        assert pd.Timestamp(row['latest_training_label_end']) < pd.Timestamp(row['fit_at'])
        assert pd.Timestamp(row['fit_at']) <= pd.Timestamp(row['available_at'])
    assert len(original['scores']) == 7*4
    assert {r['observations'] for r in original['scores']} == {15}
    assert all(np.isfinite(r['mse']) for r in original['scores'])


@pytest.mark.parametrize('hours', [1, 4])
def test_hourly_alignment_prefix_invariance_and_gap(hours):
    rng = np.random.default_rng(21)
    close = 100*np.exp(np.cumsum(rng.normal(0, .003, 3000)))
    frame = pd.DataFrame(dict(open=close, high=close*1.01, low=close*.99,
                              close=close, volume=1.),
                         index=pd.date_range('2018-01-01', periods=3000, freq='h', tz='UTC'))
    full = panel_from_hourly(frame, hours)
    short = panel_from_hourly(frame.iloc[:2800], hours)
    pd.testing.assert_frame_equal(full.loc[short.index, FEATURES+['core_label']], short[FEATURES+['core_label']])
    t = full.dropna(subset=TARGETS).index[0]
    hour = pd.Timedelta(hours=1)
    past = frame.loc[t-25*hour:t-hour, 'close'].to_numpy()
    future = frame.loc[t-hour:t+23*hour, 'close'].to_numpy()
    for col, prices in [('efficiency', past), ('future_efficiency', future)]:
        returns = np.diff(np.log(prices))
        assert full.loc[t, col] == pytest.approx(abs(returns.sum())/abs(returns).sum())
    gapped = panel_from_hourly(frame.drop(t+5*hour), hours)
    pd.testing.assert_series_equal(full.loc[t, FEATURES], gapped.loc[t, FEATURES])
    assert gapped.loc[t, TARGETS].isna().all()
