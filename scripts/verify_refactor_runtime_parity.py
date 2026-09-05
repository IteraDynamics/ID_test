"""Independent baseline/current synthetic Core v1 and dashboard comparison.

Reads an unchanged baseline worktree and writes only within a temporary directory.
Never contacts market-data providers or operates production state.
"""
from __future__ import annotations

import argparse
import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from runtime.core_v1.dashboard.charts import nav_chart
from scripts import run_core_v1_paper_live as current
from scripts.run_core_v1_jump_risk_parity import FIXED_NOW, _args, frozen_market_snapshot

BASELINE_SHA = '83e4e119a2a7954c470a797a590e5d9c8213d353'


def runtime_output_paths(args):
    paths = {key: Path(getattr(args, key)) for key in
             ['state_path', 'signals_log', 'fills_log', 'market_data_log']}
    paths['errors_log'] = Path(args.signals_log).with_name('core_v1_errors.jsonl')
    return paths


def compare_runtime_outputs(args_a, args_b):
    before, after = runtime_output_paths(args_a), runtime_output_paths(args_b)
    for key, p in before.items():
        q = after[key]
        if p.exists() != q.exists():
            raise AssertionError(f'{key}: output presence differs')
        if p.exists() and p.read_bytes() != q.read_bytes():
            raise AssertionError(f'{key}: output bytes differ')


def run_failure_cycle(module, args, snapshot, provenance):
    # Corrupt only this temporary fixture's cash. The actual sleeve_nav function
    # must raise; do not mock run_cycle, the accounting function or the logger.
    state_path = Path(args.state_path)
    state = json.loads(state_path.read_text())
    state['sleeves'][module.SELECTED_CORE_V1_SLEEVES[0].label]['cash'] = 'synthetic invalid cash'
    state_path.write_text(json.dumps(state, sort_keys=True), encoding='utf-8')
    errors = runtime_output_paths(args)['errors_log']
    if errors.exists():
        raise AssertionError('Failure fixture requires a fresh error log')
    output, stderr = io.StringIO(), io.StringIO()
    with patch.object(module, 'parse_args', return_value=args), patch.object(module, 'utc_now', return_value=FIXED_NOW), patch.object(module, 'load_market_data', side_effect=lambda _: (copy.deepcopy(snapshot), copy.deepcopy(provenance))), patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden in synthetic parity')), redirect_stdout(output), redirect_stderr(stderr):
        try:
            module.main()
        except ValueError as exc:
            frames = []
            tb = exc.__traceback__
            while tb:
                frames.append(tb.tb_frame.f_code)
                tb = tb.tb_next
            if module.sleeve_nav.__code__ not in frames:
                raise AssertionError('Failure did not originate in accounting') from exc
            failure = (type(exc).__module__, type(exc).__qualname__, str(exc))
        else:
            raise AssertionError('Expected accounting failure to propagate through main')
    if not errors.exists() or not errors.read_bytes():
        raise AssertionError('Expected a non-empty error log from main')
    records = [json.loads(line) for line in errors.read_text().splitlines()]
    expected = {'timestamp': FIXED_NOW.isoformat(), 'error': failure[2], 'version': module.STATE_VERSION}
    if records != [expected]:
        raise AssertionError('Expected exactly one accounting failure record')
    return failure, output.getvalue(), stderr.getvalue()


def load_baseline_chart(path):
    # Execute only the baseline's literal constant and pure chart function.
    # Loading the full Streamlit module would start the app and perform I/O.
    tree = ast.parse(path.read_text())
    declarations = [n for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'DRAWDOWN_AXIS_FLOOR' for t in n.targets)]
    if len(declarations) != 1:
        raise AssertionError('Expected one baseline drawdown floor declaration')
    floor = ast.literal_eval(declarations[0].value)
    if type(floor) not in (float, int):
        raise AssertionError('Baseline drawdown floor must be numeric')
    chart = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'nav_chart')
    namespace = {'pd': pd, 'go': go, 'make_subplots': make_subplots, 'DRAWDOWN_AXIS_FLOOR': floor, 'Any': object}
    exec(compile(ast.Module(body=[chart], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['nav_chart']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-root', required=True, type=Path)
    baseline = parser.parse_args().baseline_root.resolve()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=baseline, text=True).strip() == BASELINE_SHA
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=baseline, text=True).strip()
    # Shared strategy/regime imports are valid comparison inputs only while their
    # source remains byte-identical to the independent baseline.
    root = Path(__file__).resolve().parents[1]
    protected = [root / 'runtime/core_v1/allocation.py', root / 'research/harness/backtest_engine.py', root / 'research/harness/resampler.py']
    protected += list((root / 'research/strategies').glob('*.py'))
    protected += list((root / 'research/regimes').glob('*.py'))
    for path in protected:
        assert path.read_bytes() == (baseline / path.relative_to(root)).read_bytes(), path
    spec = importlib.util.spec_from_file_location('baseline_paper_runtime', baseline / 'scripts/run_core_v1_paper_live.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)

    # Buy, partial sell, exit, minimum-delta hold, unavailable NAV and migration.
    accounting_cases = 0
    for capital in [0., 100_000.]:
        for fee in [0., .001]:
            state = {'sleeves': {'S': old.default_sleeve_state(capital, 1.)}}
            candidate = copy.deepcopy(state)
            for target, price in [(1., 100.), (1., 105.), (.5, 95.), (0., 110.), (0., 100.)]:
                result = old.execute_paper_fill(state, 'S', price, target, fee, 5., .02)
                actual = current.execute_paper_fill(candidate, 'S', price, target, fee, 5., .02)
                assert result == actual and state == candidate
                assert old.mark_to_market(state['sleeves']['S'], price) == current.mark_to_market(candidate['sleeves']['S'], price)
                accounting_cases += 1
    for original in [{}, {'qty': 10., 'cash': 500.}, {'qty': 0., 'cost_basis': None}, {'qty': 10., 'cost_basis': 1500.}]:
        a, b = copy.deepcopy(original), copy.deepcopy(original)
        old.migrate_sleeve_state(a, 100_000., .15)
        current.migrate_sleeve_state(b, 100_000., .15)
        assert a == b
    bil = pd.DataFrame({'close': [100., 100.1, 100.2]}, index=pd.date_range('2024-01-01', periods=3))
    for family in ['equity', 'gold', 'trend']:
        a = {'sleeves': {'S': old.default_sleeve_state(100_000., .2)}}
        b = copy.deepcopy(a)
        for _ in range(2):
            assert old.apply_cash_yield(a, 'S', family, bil) == current.apply_cash_yield(b, 'S', family, bil)
            assert a == b

    # Actual cycle orchestration, independently loaded baseline functions.
    snapshot, provenance = frozen_market_snapshot()
    with tempfile.TemporaryDirectory(prefix='itera-runtime-parity-') as temp:
        args_a = _args(Path(temp) / 'before', is_candidate=False)
        args_b = _args(Path(temp) / 'after', is_candidate=False)
        for cycle in range(3):
            def loader(_args):
                data = copy.deepcopy(snapshot)
                if cycle == 2:
                    for asset in ['BTC', 'ETH', 'SPY', 'QQQ', 'GLD']:
                        data[asset].iloc[-30:, :4] *= .65
                return data, copy.deepcopy(provenance)
            with patch.object(old, 'utc_now', return_value=FIXED_NOW), patch.object(current, 'utc_now', return_value=FIXED_NOW), patch.object(old, 'load_market_data', side_effect=loader), patch.object(current, 'load_market_data', side_effect=loader), patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden in synthetic parity')):
                assert old.run_cycle(args_a) == current.run_cycle(args_b)
            compare_runtime_outputs(args_a, args_b)
        # Fourth attempted cycle exercises main's real exception handler/logger.
        assert run_failure_cycle(old, args_a, snapshot, provenance) == run_failure_cycle(current, args_b, snapshot, provenance)
        compare_runtime_outputs(args_a, args_b)

    # Load only the original pure chart function; do not start the baseline UI.
    baseline_chart = load_baseline_chart(baseline / 'scripts/core_v1_dashboard.py')
    history = [{'timestamp': '2024-01-01', 'nav': 100000., 'ret': 0., 'drawdown': 0.}, {'timestamp': '2024-01-02', 'nav': 98000., 'ret': -.02, 'drawdown': -.02}]
    for fills in [[], [{'timestamp': '2024-01-02', 'side': 'BUY', 'sleeve': 'S', 'qty': 10., 'price': 100.}]]:
        assert baseline_chart(history, fills).to_json() == nav_chart(history, fills).to_json()
    assert baseline_chart([], []) is nav_chart([], []) is None
    print(json.dumps({'status': 'PASS', 'accounting_cases': accounting_cases, 'successful_cycles': 3, 'induced_failure_cycles': 1, 'error_logs_nonempty_and_byte_identical': True, 'cycle_state_and_logs_byte_identical': True, 'chart_specifications_identical': True, 'baseline': BASELINE_SHA}, indent=2))


if __name__ == '__main__':
    main()
