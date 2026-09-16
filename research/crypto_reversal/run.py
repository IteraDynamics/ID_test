"""Local-only CLI. Packages successful runs and diagnostic failures for review."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import shutil
import subprocess
import traceback

import numpy as np
import pandas as pd

from .experiment import (START, END, HOUR, INPUTS, SCENARIOS, Run, combine, configuration,
                         load_input, metrics, period_summaries, policies, schedule,
                         signal_bars, simulate, trade_diagnostics)


def exposure_control(benchmark: Run, target: float) -> tuple[Run, float]:
    """Hindsight initial cash allocation matching realized mean risky weight."""
    b = benchmark.curve
    lo, hi = 0., 1.
    for _ in range(60):
        w = (lo+hi)/2
        nav = 1-w+w*b.nav
        weight = w*b.nav*b.exposure/nav
        if weight.iloc[1:].mean() < target:
            lo = w
        else:
            hi = w
    w = (lo+hi)/2
    c = b.copy()
    c['nav'] = 1-w+w*b.nav
    c['exposure'] = w*b.nav*b.exposure/c.nav
    c['fees'] = w*b.fees
    c['turnover'] = w*b.turnover*b.nav.shift(1, fill_value=1)/c.nav.shift(1, fill_value=1)
    return Run(c, [], [], {'hindsight_initial_risky_allocation': w}), w


def execute(frames: dict[str, pd.DataFrame], out: Path, start=START, end=END) -> dict:
    bars = {(asset, tf): signal_bars(f, tf) for asset, f in frames.items() for tf in (1, 4)}
    summary, diagnostics, trades, fills, signal_counts = [], [], [], [], []
    (out/'daily').mkdir()
    for (asset, tf), b in bars.items():
        signal_counts.append(dict(asset=asset, timeframe_hours=tf,
                                  shocks=int(b.loc[start:end].shock.sum()),
                                  stabilizations=int(b.loc[start:end].stabilized.sum())))
    # Every policy is run; no leaderboard-based pruning or adaptation.
    for scenario, (cost, delay) in SCENARIOS.items():
        bh = {}
        for asset, f in frames.items():
            bh[asset] = simulate(f, {start: {'signal_start': str(start-HOUR),
                                            'available_at': str(start-HOUR)}},
                                 int((end-start)/HOUR), cost, start, end)
        bh['MIX'] = combine(bh['BTC'], bh['ETH'])

        def record(name, role, runs, trade_stats=True, allocation=None):
            for asset, run in runs.items():
                keys = dict(scenario=scenario, policy=name, role=role, asset=asset)
                for row in period_summaries(run):
                    summary.append(dict(**keys, **row,
                                        hindsight_initial_allocation=allocation.get(asset) if allocation else None))
                if trade_stats:
                    diagnostics.append(dict(**keys, **run.diagnostics,
                                            **trade_diagnostics(run.trades, asset == 'MIX')))
                if asset != 'MIX' and trade_stats:
                    trades.extend(dict(**keys, **t) for t in run.trades)
                    fills.extend(dict(**keys, **t) for t in run.fills)
                # Exact UTC midnight marks; hourly paths are reconstructed from source + fills.
                daily = run.curve.loc[run.curve.index.hour == 0, ['nav', 'exposure']].copy()
                daily.index.name = 'valuation_time_utc'
                daily.to_csv(out/'daily'/f'{scenario}__{name}__{asset}.csv')

        record('buy_hold', 'benchmark', bh)
        cash = {a: Run(r.curve.assign(nav=1., exposure=0., fees=0., turnover=0.), [], [], {})
                for a, r in bh.items()}
        record('cash', 'benchmark', cash)
        for policy in policies():
            runs = {a: simulate(f, schedule(bars[a, policy.timeframe], policy, delay),
                                policy.hold_hours, cost, start, end) for a, f in frames.items()}
            runs['MIX'] = combine(runs['BTC'], runs['ETH'])
            record(policy.name, policy.role, runs)
            if policy.family == 'stabilized':
                controls, allocations = {}, {}
                for a in runs:
                    controls[a], allocations[a] = exposure_control(bh[a], metrics(runs[a].curve)['mean_exposure'])
                record(policy.name+'__exposure_control', 'hindsight_benchmark', controls,
                       trade_stats=False, allocation=allocations)
        print(f'{scenario}: all 18 policies and benchmarks completed; fill replay passed', flush=True)
    pd.DataFrame(summary).to_csv(out/'summary.csv', index=False)
    pd.DataFrame(diagnostics).to_csv(out/'diagnostics.csv', index=False)
    pd.DataFrame(trades).to_csv(out/'trades.csv', index=False)
    pd.DataFrame(fills).to_csv(out/'fills.csv', index=False)
    pd.DataFrame(signal_counts).to_csv(out/'signal_counts.csv', index=False)
    base = pd.DataFrame(summary)
    view = base[(base.scenario == 'base') & (base.period == 'full') & (base.asset == 'MIX')]
    columns = ['policy', 'cagr', 'zero_cash_sharpe', 'max_drawdown', 'mean_exposure']
    (out/'RESULTS.txt').write_text(
        'EXPLORATORY — no untouched OOS claim; primary is stabilized_4h_hold24h.\n'
        'Daily zero-cash Sharpe; drawdown uses hourly marks, with stale held gap marks reported.\n'
        'Exposure controls are hindsight-normalized, not deployable strategies.\n'
        'See all assets, years, costs and ablations in summary.csv; trades/fills support replay.\n'
        'Break-even cost is per-sleeve geometric trade economics, not an exchange fee quote.\n\n'
        +view[columns].to_string(index=False)+'\n', encoding='utf-8')
    print(view[columns].to_string(index=False), flush=True)
    return {'accounting_and_fill_replay_passed': True, 'summary_rows': len(summary),
            'fill_rows': len(fills), 'trade_rows': len(trades), 'performance_status': 'exploratory'}


def git_value(*args):
    try:
        return subprocess.check_output(['git', *args], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unavailable'


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--btc-csv', type=Path)
    parser.add_argument('--eth-csv', type=Path)
    parser.add_argument('--output-root', type=Path, default=Path('artifacts'))
    parser.add_argument('--check-only', action='store_true', help='Validate snapshots; do not compute signals or P&L')
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out = args.output_root.resolve()/f'crypto_reversal_{stamp}'
    out.mkdir(parents=True, exist_ok=False)
    config = configuration()
    config.update(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
                  git_commit=git_value('rev-parse', 'HEAD'), git_tree=git_value('rev-parse', 'HEAD^{tree}'),
                  git_dirty=bool(git_value('status', '--porcelain')), check_only=args.check_only)
    package = Path(__file__).parent
    config['code_sha256'] = {p.name: sha256(p.read_bytes()).hexdigest() for p in package.glob('*.py')}
    (out/'configuration.json').write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
    frames, inventory, status = {}, {}, {'success': False, 'performance': None}
    exit_code = 0
    try:
        for asset, override in [('BTC', args.btc_csv), ('ETH', args.eth_csv)]:
            path = override or args.data_root/INPUTS[asset][0]
            frames[asset], inventory[asset] = load_input(path, asset)
            if START not in frames[asset].index or END not in frames[asset].index:
                raise ValueError(f'{asset}: missing frozen start/terminal open')
        if not args.check_only:
            status.update(execute(frames, out))
        status['success'] = True
    except Exception as exc:
        exit_code = 1
        status['error'] = f'{type(exc).__name__}: {exc}'
        (out/'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        print(status['error'], flush=True)
    finally:
        (out/'data_inventory.json').write_text(json.dumps(inventory, indent=2)+'\n', encoding='utf-8')
        (out/'status.json').write_text(json.dumps(status, indent=2)+'\n', encoding='utf-8')
        manifest = {str(p.relative_to(out)): sha256(p.read_bytes()).hexdigest()
                    for p in sorted(out.rglob('*')) if p.is_file()}
        (out/'artifact_hashes.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
        archive = shutil.make_archive(str(out), 'zip', root_dir=out)
        print(f'SHARE {"DATA CHECK" if args.check_only else "RESULTS"} ZIP: {archive}', flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
