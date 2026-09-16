"""Import original execution and Core classifier; modify neither."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

from research.core_regime_reuse.adapter import CoreRegimeReader
from research.core_regime_reuse.run import completed_frame
from research.crypto_reversal.experiment import (
    START, END, HOUR, SCENARIOS, policies, signal_bars, schedule, simulate,
    combine, period_summaries, trade_diagnostics,
)
from research.regimes.contracts import RegimeLabel

POLICY = next(p for p in policies() if p.role == 'primary')
FILTERS = ['ALL'] + [r.value for r in RegimeLabel]
GAP_LOOKBACK_HOURS = max(168, 60 * POLICY.timeframe)


def tag_orders(frame, orders, states, timeframe=4):
    """State fixed at signal completion, before processing latency and entry.

    Gap exclusion depends only on already-observed history. Future missing
    exits are handled by the unchanged simulator, never screened away.
    """
    tagged = {}
    for entry, meta in orders.items():
        start = pd.Timestamp(meta['signal_start'])
        available = pd.Timestamp(meta['available_at'])
        if available != start + timeframe * HOUR or available >= entry:
            raise ValueError('Invalid signal/entry timing')
        if start not in states:
            raise ValueError(f'Missing exact regime bar: {start}')
        # This includes the last 60 classifier bars and original sigma window.
        expected = pd.date_range(available-GAP_LOOKBACK_HOURS*HOUR,
                                 available-HOUR, freq='h')
        clean = expected.isin(frame.index).all()
        tagged[entry] = dict(meta, regime=states[start],
                             regime_available_at=str(available), gap_clean=bool(clean))
    return tagged


def select_orders(tagged, regime='ALL', clean_only=False):
    return {t: m for t, m in tagged.items()
            if (regime == 'ALL' or m['regime'] == regime)
            and (not clean_only or m['gap_clean'])}


def execute(frames, out: Path, start=START, end=END):
    reader = CoreRegimeReader()
    states, bars = {}, {}
    for asset, frame in frames.items():
        completed = completed_frame(frame, 4, frame.index[-1]+HOUR)
        states[asset] = {t: s.label.value for t, s in zip(completed.index, reader.history(completed))}
        bars[asset] = signal_bars(frame, 4)
    summary, diagnostics, trades, fills, attributed, counts = [], [], [], [], [], []
    (out/'daily').mkdir()
    for scenario, (cost, delay) in SCENARIOS.items():
        tagged = {a: tag_orders(f, schedule(bars[a], POLICY, delay), states[a])
                  for a, f in frames.items()}
        for gap in ('original', 'past_gap_clean'):
            for regime in FILTERS:
                keys = dict(scenario=scenario, gap_mode=gap, regime_filter=regime)
                runs = {}
                for asset, frame in frames.items():
                    orders = select_orders(tagged[asset], regime, gap == 'past_gap_clean')
                    runs[asset] = simulate(frame, orders, POLICY.hold_hours, cost, start, end)
                    counts.append(dict(**keys, asset=asset, eligible_orders=sum(start <= t < end for t in orders)))
                    run = runs[asset]
                    for t in run.trades:
                        meta = tagged[asset][pd.Timestamp(t['entry_time'])]
                        row = dict(**keys, asset=asset, **t, regime=meta['regime'],
                                   regime_available_at=meta['regime_available_at'], gap_clean=meta['gap_clean'])
                        trades.append(row)
                        if gap == 'original' and regime == 'ALL':
                            attributed.append(row)
                    fills.extend(dict(**keys, asset=asset, **f) for f in run.fills)
                runs['MIX'] = combine(runs['BTC'], runs['ETH'])
                for asset, run in runs.items():
                    summary.extend(dict(**keys, asset=asset, **row) for row in period_summaries(run))
                    diagnostics.append(dict(**keys, asset=asset, **run.diagnostics,
                                            **trade_diagnostics(run.trades, asset == 'MIX')))
                    run.curve.loc[run.curve.index.hour == 0, ['nav', 'exposure']].to_csv(
                        out/'daily'/f'{scenario}__{gap}__{regime}__{asset}.csv', index_label='valuation_time')
            print(f'{scenario} / {gap}: all fixed state filters completed and accounting replay passed', flush=True)
    for name, rows in [('summary', summary), ('diagnostics', diagnostics), ('trades', trades),
                       ('fills', fills), ('eligible_orders', counts), ('attributed_original_trades', attributed)]:
        pd.DataFrame(rows).to_csv(out/f'{name}.csv', index=False)
    # Attribution is descriptive trade-level arithmetic; no invented bucket CAGR.
    group_rows = []
    for scenario in SCENARIOS:
        for asset in frames:
            for regime in [r.value for r in RegimeLabel]:
                for year in ['all'] + list(range(start.year, end.year+1)):
                    selected = [t for t in attributed if t['scenario'] == scenario and t['asset'] == asset
                                and t['regime'] == regime and (year == 'all' or pd.Timestamp(t['entry_time']).year == year)]
                    returns = [t['net_return'] for t in selected]
                    group_rows.append(dict(scenario=scenario, asset=asset, regime=regime, entry_year=year,
                        trades=len(selected), mean_net_trade_return=float(np.mean(returns)) if returns else None,
                        median_net_trade_return=float(np.median(returns)) if returns else None,
                        **{k:v for k,v in trade_diagnostics(selected).items() if k != 'trades'}))
    pd.DataFrame(group_rows).to_csv(out/'attribution_by_year.csv', index=False)
    return {'policy': POLICY.name, 'filters': FILTERS, 'gap_lookback_hours': GAP_LOOKBACK_HOURS,
            'source_lock': reader.source_lock, 'state': 'development only; all history previously exposed',
            'semantics': 'Attribution keeps original trades. State-only reruns may admit later signals originally blocked by an open position.',
            'gap_limit': 'Causal trailing-window sensitivity, not proof of gap-free EWM history; future gaps never used for entry selection.',
            'selection': 'All seven labels reported, including empty buckets. No state combination search or automatic promotion.'}
