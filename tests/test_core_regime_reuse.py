import ast
from dataclasses import asdict
import json

import numpy as np
import pandas as pd
import pytest

from research.core_regime_reuse import adapter
from research.core_regime_reuse.adapter import CoreRegimeReader, ROOT
from research.core_regime_reuse.run import completed_frame
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.contracts import RegimeLabel


def frame(n=180, width=0.015):
    rng = np.random.default_rng(17)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n)))
    return pd.DataFrame({'open': close, 'high': close*(1+width),
                         'low': close*(1-width), 'close': close, 'volume': 10.0},
                        index=pd.date_range('2020-01-01', periods=n, freq='h', tz='UTC'))


@pytest.mark.parametrize('width', [0.001, 0.015, 0.04])
def test_exact_engine_parity_and_causal_prefixes(width):
    df = frame(width=width)
    original = df.copy(deep=True)
    reader = CoreRegimeReader()
    history = reader.history(df)
    assert [asdict(s) for s in history] == [asdict(s) for s in BaselineRegimeEngine().classify_dataframe(df)]
    for i in (0, 59, 60, 75, 130, 179):
        assert asdict(history[i]) == asdict(reader.snapshot(df.iloc[:i+1]))
    poisoned = df.copy()
    poisoned.iloc[100:, :4] *= 10
    assert [asdict(s) for s in reader.history(poisoned)[:100]] == [asdict(s) for s in history[:100]]
    pd.testing.assert_frame_equal(df, original)


def test_actual_core_wrapper_without_importing_paper_runtime():
    # Execute only the recovered pure function's AST, never the runtime module.
    tree = ast.parse((ROOT/'scripts/run_core_v1_paper_live.py').read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'classify_regime')
    namespace = {'pd': pd, 'BaselineRegimeEngine': BaselineRegimeEngine, 'RegimeLabel': RegimeLabel}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<Core classify_regime only>', 'exec'), namespace)
    df = frame()
    for length in (1, 60, 61, 180):
        assert CoreRegimeReader().snapshot(df.iloc[:length]).label == namespace['classify_regime'](df.iloc[:length])


def test_warmup_boundary_is_61st_observation():
    signals = CoreRegimeReader().history(frame())
    assert all(s.label == RegimeLabel.UNKNOWN for s in signals[:60])
    assert signals[60].label != RegimeLabel.UNKNOWN


def test_completed_four_hour_boundary():
    df = frame(8)
    before = completed_frame(df, 4, pd.Timestamp('2020-01-01T07:59:59Z'))
    after = completed_frame(df, 4, pd.Timestamp('2020-01-01T08:00:00Z'))
    assert len(before) == 1
    assert len(after) == 2
    assert after.iloc[1].close == df.iloc[7].close
    assert after.iloc[1].high == df.iloc[4:8].high.max()


def test_gap_preserves_core_resampler_behavior():
    df = frame(8).drop(pd.Timestamp('2020-01-01T02:00:00Z'))
    out = completed_frame(df, 4, pd.Timestamp('2020-01-01T08:00:00Z'))
    assert len(out) == 2
    assert out.iloc[0].volume == 30


@pytest.mark.parametrize('bad', ['nan', 'duplicate', 'reverse', 'bounds'])
def test_research_boundary_rejects_invalid_data(bad):
    df = frame()
    if bad == 'nan':
        df.iloc[0, 3] = np.nan
    elif bad == 'duplicate':
        df = pd.concat([df, df.iloc[-1:]])
    elif bad == 'reverse':
        df = df.iloc[::-1]
    else:
        df.iloc[0, 1] = df.iloc[0, 2] - 1
    with pytest.raises(ValueError):
        CoreRegimeReader().history(df)


def test_pin_drift_fails_without_touching_core(tmp_path, monkeypatch):
    lock = json.loads((ROOT/'research/core_regime_reuse/source_lock.json').read_text())
    for path in lock['sha256']:
        target = tmp_path/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/path).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
    monkeypatch.setattr(adapter, 'ROOT', tmp_path)
    adapter.verify_source_lock()  # Windows checkout line endings accepted.
    (tmp_path/'research/regimes/baseline_engine.py').write_text('# changed\n')
    with pytest.raises(RuntimeError, match='Pinned Core source differs'):
        CoreRegimeReader()
