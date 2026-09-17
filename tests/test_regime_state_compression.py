import numpy as np
import pandas as pd

from research.regime_state_compression.study import CompressionModel, KS, episode_lengths


def _frame(n=400):
    idx = pd.date_range('2019-01-01', periods=n, freq='D', tz='UTC')
    x = np.linspace(-2, 2, n)
    return pd.DataFrame({
        'strength': x,
        'momentum': np.sin(x),
        'log_atr': np.cos(x) / 4,
        'atr_accel': np.sin(2*x) / 5,
        'efficiency': np.linspace(.1, .9, n),
        'core_label': np.where(x > 0, 'TREND_UP', 'RANGE'),
    }, index=idx)


def test_compression_transform_is_deterministic():
    frame = _frame()
    a = CompressionModel().fit(frame).transform(frame)
    b = CompressionModel().fit(frame).transform(frame)
    for i in range(1, 6):
        np.testing.assert_allclose(a[f'pc{i}'], b[f'pc{i}'])
    for k in KS:
        assert a[f'k{k}'].tolist() == b[f'k{k}'].tolist()


def test_cluster_candidates_are_populated():
    frame = _frame()
    transformed = CompressionModel().fit(frame).transform(frame)
    for k in KS:
        assert transformed[f'k{k}'].nunique() == k


def test_pca_variance_is_ordered_and_complete():
    frame = _frame()
    model = CompressionModel().fit(frame)
    ratios = model.pca.explained_variance_ratio_
    assert len(ratios) == 5
    assert np.all(ratios[:-1] >= ratios[1:])
    assert np.isclose(ratios.sum(), 1.0)


def test_episode_lengths_break_on_state_change_and_gap():
    idx = pd.to_datetime(['2020-01-01','2020-01-02','2020-01-03','2020-01-05','2020-01-06'], utc=True)
    frame = pd.DataFrame({'state': ['A','A','B','B','B']}, index=idx)
    assert episode_lengths(frame, 'state') == [2, 1, 2]


def test_nonfinite_features_fail_closed():
    frame = _frame()
    frame.loc[frame.index[0], 'strength'] = np.nan
    try:
        CompressionModel().fit(frame)
    except ValueError as exc:
        assert 'finite' in str(exc)
    else:
        raise AssertionError('Expected nonfinite input to fail closed')
