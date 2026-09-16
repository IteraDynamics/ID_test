"""Causal hourly spot ledger and a fixed, small reversal hypothesis family."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

HOUR = pd.Timedelta(hours=1)
START = pd.Timestamp('2020-01-01', tz='UTC')
END = pd.Timestamp('2025-12-31', tz='UTC')
INPUTS = {
    'BTC': ('btcusd_3600s_2018-01-01_to_2025-12-31.csv',
            'd7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079'),
    'ETH': ('ethusd_3600s_2018-01-01_to_2025-12-31.csv',
            '73721a1ef1dffbff64bf6ef2d92fb508a59b20d5c847684d96fdc7015912845f'),
}
SCENARIOS = {'frictionless': (0., 1), 'base': (30., 1),
             'cost_stress': (75., 1), 'delay_stress': (30., 2)}


@dataclass(frozen=True)
class Policy:
    name: str
    family: str
    timeframe: int
    hold_hours: int
    role: str


def policies() -> list[Policy]:
    return [Policy(f'{family}_{tf}h_hold{hold}h', family, tf, hold,
                   'primary' if (family, tf, hold) == ('stabilized', 4, 24)
                   else 'candidate' if family == 'stabilized' else 'ablation')
            for tf in (4, 1) for hold in (24, 6, 48)
            for family in ('stabilized', 'immediate', 'wait_one_bar')]


def validate_frame(frame: pd.DataFrame) -> None:
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError('UTC-aware DatetimeIndex required')
    if (frame.empty or frame.index.hasnans or frame.index.has_duplicates
            or not frame.index.is_monotonic_increasing
            or (frame.index != frame.index.floor('h')).any()):
        raise ValueError('Empty, duplicate, unordered or non-hourly timestamp')
    required = ['open', 'high', 'low', 'close', 'volume']
    if not set(required).issubset(frame.columns):
        raise ValueError('OHLCV columns required')
    x = frame[required].to_numpy(float)
    if not np.isfinite(x).all() or (x[:, :4] <= 0).any() or (x[:, 4] < 0).any():
        raise ValueError('Nonfinite, nonpositive price or negative volume')
    if ((frame.low > frame[['open', 'close']].min(axis=1)).any()
            or (frame.high < frame[['open', 'close']].max(axis=1)).any()):
        raise ValueError('OHLC range invalid')


def load_input(path: Path, asset: str) -> tuple[pd.DataFrame, dict]:
    digest = sha256(path.read_bytes()).hexdigest()
    if digest != INPUTS[asset][1]:
        raise ValueError(f'{asset}: snapshot SHA256 differs from frozen source: {digest}')
    frame = pd.read_csv(path)
    if list(frame.columns) != ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
        raise ValueError(f'{asset}: unexpected schema')
    frame.index = pd.to_datetime(frame.pop('timestamp'), utc=True, errors='raise')
    validate_frame(frame)
    expected = pd.date_range(frame.index[0], frame.index[-1], freq='h')
    missing = expected.difference(frame.index)
    return frame, dict(path=str(path.resolve()), sha256=digest, rows=len(frame),
                      first=str(frame.index[0]), last=str(frame.index[-1]),
                      missing_hours=len(missing), missing_timestamps=list(map(str, missing)),
                      timestamp_meaning='UTC bucket start', source='Coinbase Exchange')


def signal_bars(frame: pd.DataFrame, hours: int) -> pd.DataFrame:
    if hours not in (1, 4):
        raise ValueError('Only frozen 1h/4h signal bars supported')
    grid = frame.reindex(pd.date_range(frame.index[0].floor('4h'),
                                     frame.index[-1], freq='h'))
    grouped = grid.resample(f'{hours}h', origin='start_day', closed='left', label='left')
    bars = grouped.agg({'open': 'first', 'high': 'max', 'low': 'min',
                        'close': 'last', 'volume': 'sum'})
    bars.loc[grouped['close'].count() != hours, :] = np.nan
    ret = np.log(bars.close / bars.close.shift(1))
    sigma = ret.shift(1).rolling(168 // hours, min_periods=168 // hours).std(ddof=1)
    bars['sigma_prior'] = sigma
    bars['shock'] = (ret <= -2.5 * sigma) & (sigma > 0) & (bars.close < bars.open)
    bars['stabilized'] = (bars.shock.shift(1, fill_value=False)
                          & (bars.low >= bars.low.shift(1))
                          & (bars.close > bars.close.shift(1)) & (bars.close > bars.open))
    bars['wait_one_bar'] = bars.shock.shift(1, fill_value=False) & bars.close.notna()
    return bars


def schedule(bars: pd.DataFrame, policy: Policy, delay_hours: int) -> dict:
    if delay_hours not in (1, 2):
        raise ValueError('Only frozen 1h/2h processing latency supported')
    column = 'shock' if policy.family == 'immediate' else policy.family
    selected = bars.index[bars[column]]
    # Mapping only past completed bars to later hourly opens; no exit-price screening.
    return {t + (policy.timeframe + delay_hours) * HOUR:
            {'signal_start': str(t), 'available_at': str(t + policy.timeframe * HOUR)}
            for t in selected}


@dataclass
class Run:
    curve: pd.DataFrame
    trades: list[dict]
    fills: list[dict]
    diagnostics: dict


def simulate(frame: pd.DataFrame, orders: dict, hold_hours: int, one_way_bps: float,
             start: pd.Timestamp = START, end: pd.Timestamp = END) -> Run:
    """All-in single-asset spot sleeve. Missing exits defer, never delete a trade."""
    if hold_hours <= 0 or not 0 <= one_way_bps < 10000 or end <= start:
        raise ValueError('Invalid duration or costs')
    grid = pd.date_range(start, end, freq='h')
    if grid[-1] != end or start not in frame.index or end not in frame.index:
        raise ValueError('Observed start/end opens on exact hour boundaries required')
    f = frame.reindex(grid)
    opens, closes = f.open.to_numpy(), f.close.to_numpy()
    count = len(grid)
    times = {t: i for i, t in enumerate(grid)}
    planned = {}
    for t, meta in orders.items():
        if t in times:
            if pd.Timestamp(meta['available_at']) >= t:
                raise ValueError('Fill must strictly follow information availability')
            planned[times[t]] = meta
    nav = np.ones(count)
    exposure = np.zeros(count)
    fees = np.zeros(count)
    traded_notional = np.zeros(count)
    delta_cash = np.zeros(count)
    delta_units = np.zeros(count)
    marks = np.zeros(count)
    cash, units, mark = 1., 0., float(opens[0])
    active = None
    trades, fills = [], []
    cost = one_way_bps / 10000
    missing_entries = stale_marks = ignored_signals = 0
    max_residual = 0.
    # Valuation time i+1 is close of the candle starting at grid[i].
    # Last iteration is terminal liquidation at end's OPEN, without end's close.
    for i in range(count):
        timestamp = grid[i]
        terminal = i == count - 1
        output = min(i + 1, count - 1)
        old_nav = cash + units * mark
        old_units = units
        opening = opens[i] if np.isfinite(opens[i]) else mark
        fee_here = turnover_here = 0.
        cash_change = units_change = 0.
        exited = False
        if active is not None and (i >= active['due_index'] or terminal) and np.isfinite(opens[i]):
            notional = units * opening
            fee = notional * cost
            turnover_here += notional
            cash_change += notional - fee
            units_change -= units
            fills.append(dict(time=str(timestamp), side='sell', price=float(opening),
                              units=float(units), fee=float(fee), reason='terminal' if terminal else 'timed'))
            cash += notional - fee
            fee_here += fee
            trades.append(dict(entry_time=active['entry_time'], exit_time=str(timestamp),
                               available_at=active['available_at'], signal_start=active['signal_start'],
                               entry_price=active['entry_price'], exit_price=float(opening),
                               units=float(units), entry_fee=active['entry_fee'], exit_fee=float(fee),
                               start_equity=active['start_equity'], end_equity=float(cash),
                               net_return=float(cash / active['start_equity'] - 1),
                               gross_return=float(opening / active['entry_price'] - 1),
                               net_pnl=float(cash - active['start_equity']),
                               hold_hours=i - active['entry_index'],
                               exit_delay_hours=max(0, i-active['due_index']), terminal_exit=terminal))
            units = 0.
            active = None
            exited = True
        if not terminal and i in planned:
            if active is not None or exited:
                ignored_signals += 1
            elif i + hold_hours > count - 1:
                ignored_signals += 1
            elif not np.isfinite(opens[i]):
                missing_entries += 1
            else:
                before = cash
                units = cash / (opening * (1 + cost))
                notional = units * opening
                fee = notional * cost
                cash_change -= notional + fee
                units_change += units
                cash -= notional + fee
                fee_here += fee
                turnover_here += notional
                active = dict(entry_index=i, due_index=i+hold_hours, entry_time=str(timestamp),
                              entry_price=float(opening), entry_fee=float(fee),
                              start_equity=float(before), **planned[i])
                fills.append(dict(time=str(timestamp), side='buy', price=float(opening),
                                  units=float(units), fee=float(fee), reason='signal'))
        closing = opening if terminal else closes[i] if np.isfinite(closes[i]) else mark
        if not terminal and not np.isfinite(closes[i]) and units > 0:
            stale_marks += 1
        value = cash + units * closing
        market_pnl = old_units * (opening-mark) + units * (closing-opening)
        residual = value - old_nav - market_pnl + fee_here
        max_residual = max(max_residual, abs(residual) / max(old_nav, 1e-30))
        if value <= 0 or cash < -1e-10 * value or max_residual > 1e-10:
            raise ValueError('Cash/NAV/P&L reconciliation failed')
        nav[output] = value
        exposure[output] = units * closing / value
        fees[output] += fee_here
        traded_notional[output] += turnover_here
        delta_cash[output] += cash_change
        delta_units[output] += units_change
        marks[output] = closing
        mark = closing
    if units != 0 or active is not None:
        raise ValueError('Unliquidated terminal position')
    # Independent fill replay, including two executions sharing the terminal valuation time.
    replay = 1 + np.cumsum(delta_cash) + np.cumsum(delta_units) * marks
    error = float(np.max(np.abs(replay - nav) / nav))
    if error > 1e-9:
        raise ValueError('Independent fill replay failed')
    turnover = traded_notional / np.r_[1., nav[:-1]]
    curve = pd.DataFrame(dict(nav=nav, exposure=exposure, fees=fees, turnover=turnover), index=grid)
    return Run(curve, trades, fills, dict(accounting_max_relative_error=max_residual,
               replay_max_relative_error=error, cancelled_missing_entries=missing_entries,
               held_stale_marks=stale_marks, ignored_signals=ignored_signals,
               deferred_exits=sum(t['exit_delay_hours'] > 0 for t in trades)))


def combine(a: Run, b: Run) -> Run:
    if not a.curve.index.equals(b.curve.index):
        raise ValueError('Sleeve calendars differ')
    x, y = a.curve, b.curve
    c = (x + y) / 2
    c['exposure'] = (x.exposure*x.nav + y.exposure*y.nav) / (x.nav+y.nav)
    # Turnover denominator is combined pre-interval NAV (a descriptive normalization).
    previous_a = x.nav.shift(1, fill_value=1.)
    previous_b = y.nav.shift(1, fill_value=1.)
    c['turnover'] = (x.turnover*previous_a + y.turnover*previous_b) / (previous_a+previous_b)
    return Run(c, [dict(t, asset=k) for k, r in [('BTC', a), ('ETH', b)] for t in r.trades],
               [], {'combination': 'equal initial capital, no sleeve rebalancing'})


def metrics(curve: pd.DataFrame) -> dict:
    years = (curve.index[-1] - curve.index[0]).total_seconds() / (365.25*86400)
    if years <= 0:
        raise ValueError('Nonpositive metric duration')
    nav = curve.nav.to_numpy()
    cagr = (nav[-1]/nav[0])**(1/years)-1
    dd = float(np.min(nav / np.maximum.accumulate(nav)-1))
    # Index is UTC boundary time, so daily close marks should be midnight marks.
    daily = curve.loc[curve.index.hour == 0, 'nav']
    returns = daily.pct_change().dropna().to_numpy()
    sd = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.
    return dict(cagr=float(cagr), zero_cash_sharpe=float(np.mean(returns)/sd*np.sqrt(365))
                if sd > 1e-14 else None, annual_vol=float(sd*np.sqrt(365)),
                max_drawdown=dd, calmar=float(cagr/-dd) if dd < -1e-14 else None,
                terminal_multiple=float(nav[-1]/nav[0]),
                mean_exposure=float(curve.exposure.iloc[1:].mean()),
                one_way_turnover_per_year=float(curve.turnover.iloc[1:].sum()/years),
                fees_initial_capital=float(curve.fees.iloc[1:].sum()/nav[0]),
                worst_day=float(returns.min()) if len(returns) else None)


def trade_diagnostics(trades: list[dict], combined: bool = False) -> dict:
    if not trades:
        return dict(trades=0, win_fraction=None, geometric_break_even_one_way_bps=None,
                    top5_positive_pnl_share=None, terminal_multiple_without_top5=1.)
    gross_logs = np.log1p([t['gross_return'] for t in trades])
    mean_log = float(np.mean(gross_logs))
    # Product of all-in trades at cost c is G*((1-c)/(1+c))**N.
    # Combined sleeves are not one compounded trade sequence: no aggregate root claimed.
    break_even = 10000*np.tanh(mean_log/2) if mean_log >= 0 and not combined else None
    positive = sorted([max(0., t['net_pnl']) for t in trades], reverse=True)
    largest = set(sorted((i for i, t in enumerate(trades) if t['net_return'] > 0),
                         key=lambda i: trades[i]['net_return'], reverse=True)[:5])
    if combined:
        terminal = sum(float(np.prod([1+t['net_return'] for i, t in enumerate(trades)
                                      if t['asset'] == asset and i not in largest]))
                       for asset in ('BTC', 'ETH'))/2
    else:
        terminal = float(np.prod([1+t['net_return'] for i, t in enumerate(trades) if i not in largest]))
    return dict(trades=len(trades), win_fraction=float(np.mean([t['net_return'] > 0 for t in trades])),
                geometric_break_even_one_way_bps=float(break_even) if break_even is not None else None,
                top5_positive_pnl_share=float(sum(positive[:5])/sum(positive)) if sum(positive) else None,
                terminal_multiple_without_top5=terminal)


def period_summaries(run: Run) -> list[dict]:
    c = run.curve
    intervals = [('full', c.index[0], c.index[-1]),
                 ('2020_2022', START, pd.Timestamp('2023-01-01', tz='UTC')),
                 ('2023_end', pd.Timestamp('2023-01-01', tz='UTC'), END)]
    intervals += [(str(y), pd.Timestamp(f'{y}-01-01', tz='UTC'),
                   min(pd.Timestamp(f'{y+1}-01-01', tz='UTC'), c.index[-1]))
                  for y in range(c.index[0].year, c.index[-1].year+1)]
    rows = []
    for name, lo, hi in intervals:
        lo, hi = max(lo, c.index[0]), min(hi, c.index[-1])
        if hi <= lo:
            continue
        sub = c.loc[lo:hi]
        # Fees/turnover at lo already belong to the prior interval.
        rows.append(dict(period=name, **metrics(sub)))
    return rows


def configuration() -> dict:
    return dict(start=str(START), terminal_open=str(END), sigma_lookback_hours=168,
                shock_sigma=-2.5, policies=[asdict(p) for p in policies()],
                scenarios={k: dict(one_way_bps=v[0], delay_hours=v[1]) for k, v in SCENARIOS.items()},
                state='exploratory; all years previously exposed; not OOS', cash_yield=0,
                source_hashes={k: v[1] for k, v in INPUTS.items()})
