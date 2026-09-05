"""Adversarial checks for the migration verifiers, independent of market data."""
from types import SimpleNamespace
import json

import pytest

from scripts import verify_refactor_ml_parity as ml
from scripts import verify_refactor_runtime_parity as runtime


def test_empty_artifact_pairs_cannot_pass():
    with pytest.raises(AssertionError, match='non-empty'):
        ml.check_outputs_equal({}, {})


@pytest.mark.parametrize('count', [0, 60, 62])
def test_baseline_fixture_inventory_is_required(count):
    with pytest.raises(AssertionError, match='Expected 61'):
        ml.check_expected_inventory({str(i): b'output' for i in range(count)})


def test_exact_nonempty_inventory_can_pass():
    outputs = {str(i): b'output' for i in range(61)}
    ml.check_expected_inventory(outputs)
    ml.check_outputs_equal(outputs, dict(outputs))


def paths(root):
    root.mkdir()
    return SimpleNamespace(state_path=root / 'state.json', signals_log=root / 'signals.jsonl',
                           fills_log=root / 'fills.jsonl', market_data_log=root / 'market.jsonl')


@pytest.mark.parametrize('change', ['missing', 'empty', 'different'])
def test_runtime_comparator_detects_error_log_drift(tmp_path, change):
    before, after = paths(tmp_path / 'before'), paths(tmp_path / 'after')
    left = runtime.runtime_output_paths(before)['errors_log']
    right = runtime.runtime_output_paths(after)['errors_log']
    left.write_bytes(b'{"error":"failure"}\n')
    right.write_bytes(left.read_bytes())
    runtime.compare_runtime_outputs(before, after)
    if change == 'missing':
        right.unlink()
    else:
        right.write_bytes(b'' if change == 'empty' else b'{"error":"different"}\n')
    with pytest.raises(AssertionError, match='errors_log'):
        runtime.compare_runtime_outputs(before, after)


def test_failure_cycle_rejects_suppressed_error_logging(tmp_path, monkeypatch):
    args = runtime._args(tmp_path, is_candidate=False)
    state_path = runtime.Path(args.state_path)
    state_path.parent.mkdir(parents=True)
    state = {'sleeves': {s.label: runtime.current.default_sleeve_state(args.capital, s.weight)
                          for s in runtime.current.SELECTED_CORE_V1_SLEEVES}}
    state_path.write_text(json.dumps(state))
    snapshot, provenance = runtime.frozen_market_snapshot()
    monkeypatch.setattr(runtime.current, 'append_jsonl', lambda *args: None)
    with pytest.raises(AssertionError, match='non-empty error log'):
        runtime.run_failure_cycle(runtime.current, args, snapshot, provenance)


@pytest.mark.parametrize('floor', [-.4, -.25])
def test_chart_floor_comes_from_baseline_source(tmp_path, floor):
    source = tmp_path / 'dashboard.py'
    source.write_text(f'DRAWDOWN_AXIS_FLOOR = {floor}\ndef nav_chart(history, fills):\n    return DRAWDOWN_AXIS_FLOOR\nraise RuntimeError("must not start app")\n')
    assert runtime.load_baseline_chart(source)([], []) == floor


def test_missing_baseline_floor_fails_closed(tmp_path):
    source = tmp_path / 'dashboard.py'
    source.write_text('def nav_chart(history, fills):\n    return 0\n')
    with pytest.raises(AssertionError, match='one baseline drawdown floor'):
        runtime.load_baseline_chart(source)
