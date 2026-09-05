"""Independent baseline/current synthetic Core v1 and dashboard comparison.

Reads an unchanged baseline worktree and writes only within a temporary directory.
Never contacts market-data providers or operates production state.
"""
from __future__ import annotations

import argparse
import ast
import copy
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-root', required=True, type=Path)
    baseline = parser.parse_args().baseline_root.resolve()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=baseline, text=True).strip() == BASELINE_SHA
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=baseline, text=True).strip()
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
            for key in ['state_path', 'signals_log', 'fills_log', 'market_data_log']:
                p, q = Path(getattr(args_a, key)), Path(getattr(args_b, key))
                assert (p.read_bytes() if p.exists() else b'') == (q.read_bytes() if q.exists() else b''), key

    # Load only the original pure chart function; do not start the baseline UI.
    tree = ast.parse((baseline / 'scripts/core_v1_dashboard.py').read_text())
    chart = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'nav_chart')
    namespace = {'pd': pd, 'go': go, 'make_subplots': make_subplots, 'DRAWDOWN_AXIS_FLOOR': -.40, 'Any': object}
    exec(compile(ast.Module(body=[chart], type_ignores=[]), '<baseline-chart>', 'exec'), namespace)
    history = [{'timestamp': '2024-01-01', 'nav': 100000., 'ret': 0., 'drawdown': 0.}, {'timestamp': '2024-01-02', 'nav': 98000., 'ret': -.02, 'drawdown': -.02}]
    for fills in [[], [{'timestamp': '2024-01-02', 'side': 'BUY', 'sleeve': 'S', 'qty': 10., 'price': 100.}]]:
        assert namespace['nav_chart'](history, fills).to_json() == nav_chart(history, fills).to_json()
    assert namespace['nav_chart']([], []) is nav_chart([], []) is None
    print(json.dumps({'status': 'PASS', 'accounting_cases': accounting_cases, 'cycles': 3, 'cycle_state_and_logs_byte_identical': True, 'chart_specifications_identical': True, 'baseline': BASELINE_SHA}, indent=2))


if __name__ == '__main__':
    main()
