"""Build a lagged SPY/options research panel; no model selection or trading results.

Run as python -m scripts.prepare_ml_options_variance. Original gamma artifacts
are never read or overwritten. Only option files 2008--2024 are opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

CUTOFF = pd.Timestamp('2024-12-31')
COLUMNS = ['date', 'expiration', 'strike', 'type', 'open_interest',
           'implied_volatility', 'gamma', 'delta', 'bid', 'ask']
OPTIONS = ['iv_near', 'iv_far', 'put_call_skew', 'iv_term_slope',
           'gamma_strike_concentration', 'front_gamma_share', 'log_gamma_z252']


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def dates(s):
    return pd.to_datetime(s, errors='raise', utc=True).dt.tz_convert(None).dt.normalize()


def load_prices(path):
    f = pd.read_csv(path)
    f.columns = f.columns.str.lower().str.strip()
    f['date'] = dates(f['timestamp'])
    f = f.loc[f.date <= CUTOFF, ['date', 'close']].copy()
    f['close'] = pd.to_numeric(f['close'], errors='raise')
    if f.date.duplicated().any() or not np.isfinite(f.close).all() or (f.close <= 0).any():
        raise ValueError('Invalid or duplicate SPY prices; repair source explicitly')
    f = f.sort_values('date').reset_index(drop=True)
    if f.empty or f.date.min() > pd.Timestamp('2008-01-02'):
        raise ValueError('Use the long SPY history covering 2008, not the short 2013 file')
    if f.date.max() < pd.Timestamp('2024-12-31'):
        raise ValueError('SPY history must extend through 2024-12-31')
    return f


def clean_chain(f):
    f = f[COLUMNS].copy()
    f['date'], f['expiration'] = dates(f.date), dates(f.expiration)
    # Filter before inspecting numeric outcomes or constructing features.
    f = f[f.date <= CUTOFF].copy()
    f['type'] = f.type.astype(str).str.lower().replace({'c': 'call', 'p': 'put'})
    for c in COLUMNS[2:]:
        if c != 'type':
            f[c] = pd.to_numeric(f[c], errors='coerce')
    if f.duplicated(['date', 'expiration', 'strike', 'type']).any():
        raise ValueError('Duplicate option contracts; no silent deduplication')
    f['dte'] = (f.expiration - f.date).dt.days
    mid = (f.bid + f.ask) / 2
    ok = (np.isfinite(f[['strike', 'open_interest', 'implied_volatility', 'gamma', 'delta', 'bid', 'ask']]).all(axis=1)
          & f.type.isin(['call', 'put']) & (f.strike > 0) & (f.open_interest > 0)
          & f.implied_volatility.between(0.0001, 5) & (f.gamma >= 0)
          & (f.bid > 0) & (f.ask >= f.bid) & ((f.ask-f.bid)/mid <= 0.5)
          & f.dte.between(7, 90)
          & (((f.type == 'call') & f.delta.between(0, 1))
             | ((f.type == 'put') & f.delta.between(-1, 0))))
    return f.loc[ok].copy(), {'input_rows': len(f), 'accepted_rows': int(ok.sum()),
                            'excluded_rows': int((~ok).sum())}


def select_iv(g, kind, delta_target):
    lo, hi = (0.35, 0.65) if delta_target == 0.5 else (0.15, 0.35)
    f = g[(g.type == kind) & g.delta.abs().between(lo, hi)].copy()
    if f.empty:
        return np.nan
    f['distance'] = (f.delta.abs()-delta_target).abs()
    return float(f.sort_values(['distance', 'strike']).iloc[0].implied_volatility)


def tenor(g, target, lo, hi):
    f = g[g.dte.between(lo, hi)]
    if f.empty:
        return np.nan, np.nan, np.nan
    expiries = f[['expiration', 'dte']].drop_duplicates().copy()
    expiries['distance'] = (expiries.dte-target).abs()
    expiry = expiries.sort_values(['distance', 'expiration']).iloc[0].expiration
    f = f[f.expiration == expiry]
    call, put = select_iv(f, 'call', 0.5), select_iv(f, 'put', 0.5)
    atm = (call+put)/2  # Requires both sides; no silent one-sided fallback.
    skew = select_iv(f, 'put', 0.25)-select_iv(f, 'call', 0.25)
    return atm, skew, int(f.dte.iloc[0])


def summarize_chain(f):
    rows = []
    for date, g in f.groupby('date', sort=True):
        near, skew, near_dte = tenor(g, 30, 21, 45)
        far, _, far_dte = tenor(g, 60, 46, 90)
        weight = g.gamma*g.open_interest
        total = float(weight.sum())
        concentration = float(weight.groupby(g.strike).sum().max()/total) if total > 0 else np.nan
        rows.append(dict(date=date, iv_near=near, iv_far=far, put_call_skew=skew,
                         iv_term_slope=far-near, near_dte=near_dte, far_dte=far_dte,
                         gamma_strike_concentration=concentration,
                         front_gamma_share=float(weight[g.dte <= 30].sum()/total) if total > 0 else np.nan,
                         total_gamma=total, accepted_contracts=len(g)))
    return pd.DataFrame(rows)


def make_panel(prices, states):
    p = prices.copy().set_index('date')
    ret = np.log(p.close).diff()
    for n in (5, 21, 63):
        p[f'rv_{n}'] = ret.pow(2).rolling(n).mean()
    p['return_21'] = np.log(p.close/p.close.shift(21))
    # Observation at t; wait through t+1 close; target contains t+2..t+6 returns.
    p['execution_date'] = pd.Series(p.index, index=p.index).shift(-1)
    p['target_end'] = pd.Series(p.index, index=p.index).shift(-6)
    p['future_variance_5'] = pd.concat([ret.pow(2).shift(-j) for j in range(2, 7)], axis=1).sum(axis=1, min_count=5)
    p['anchor'] = np.arange(len(p)) % 5 == 0
    s = states.set_index('date').sort_index()
    if s.index.duplicated().any():
        raise ValueError('Duplicate option observation dates across files')
    # Rolling normalization uses previous 252 SPY sessions, never future values.
    lg = np.log(s.total_gamma.where(s.total_gamma > 0)).reindex(p.index)
    mean, sd = lg.shift(1).rolling(252, min_periods=126).mean(), lg.shift(1).rolling(252, min_periods=126).std()
    s['log_gamma_z252'] = ((lg-mean)/sd.where(sd > 0)).reindex(s.index)
    out = p.join(s, how='left').reset_index().rename(columns={'date': 'source_date'})
    out = out[out.source_date >= pd.Timestamp('2008-01-01')].copy()
    out['complete'] = out[OPTIONS+['rv_5', 'rv_21', 'rv_63', 'return_21', 'future_variance_5']].notna().all(axis=1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input-root', type=Path, required=True)
    ap.add_argument('--spy-csv', type=Path, default=Path('artifacts/month_end_rebalance_data/SPY_1D.csv'))
    ap.add_argument('--options-dir', type=Path, default=Path('artifacts/free_options_history_probe'))
    ap.add_argument('--output-dir', type=Path, required=True)
    a = ap.parse_args()
    if a.output_dir.exists():
        raise ValueError('Output directory already exists; choose a new directory')
    price_path = a.input_root / a.spy_csv
    prices = load_prices(price_path)
    manifest = [{'path': str(a.spy_csv), 'sha256': digest(price_path)}]
    summaries, quality = [], []
    for year in range(2008, 2025):
        path = a.input_root / a.options_dir / f'spy_options_{year}.parquet'
        print(f'Aggregating {year}', flush=True)
        f = pd.read_parquet(path, columns=COLUMNS)
        f, q = clean_chain(f)
        if f.empty or not f.date.dt.year.eq(year).all():
            raise ValueError(f'Empty or wrong-year option file: {year}')
        summaries.append(summarize_chain(f))
        quality.append({'year': year, **q})
        manifest.append({'path': str(path.relative_to(a.input_root)), 'sha256': digest(path)})
    states = pd.concat(summaries, ignore_index=True)
    panel = make_panel(prices, states)
    # Same matched sample for all subsequent nested model comparisons.
    anchors = panel[panel.anchor & panel.complete].copy()
    if anchors.empty:
        raise ValueError('No complete five-session anchors')
    report = dict(status='PREPARED_FOR_DESIGN_AND_POWER_REVIEW', synthetic=False,
                  runner_sha256=digest(Path(__file__)),
                  environment={'pandas': pd.__version__, 'numpy': np.__version__},
                  last_allowed_date='2024-12-31', options_2025_opened=False,
                  historical_2025_gamma_screen_already_inspected=True,
                  model_fits=0, original_gamma_screen_modified=False,
                  target='Sum of five squared daily log returns after execution close',
                  timing='source t; execution close t+1; target returns t+2 through t+6',
                  limitations=['Discovery-contaminated history; not confirmation',
                               'Close adjustment semantics require source review',
                               'IV/Greeks are vendor estimates, not verified exchange observations',
                               'Session completeness is not verified against an exchange calendar',
                               'Nearest-expiry delta-selected IV proxies, not interpolated constant maturity IV'],
                  panel_rows=len(panel), complete_anchors=len(anchors), quality=quality,
                  yearly_complete_anchors={str(k): int(v) for k,v in anchors.groupby(anchors.source_date.dt.year).size().items()},
                  sources=manifest)
    a.output_dir.mkdir(parents=True)
    for name, frame in [('options_daily_features.csv', panel), ('options_variance_anchors.csv', anchors)]:
        frame.to_csv(a.output_dir/name, index=False, lineterminator='\n', float_format='%.17g')
    report['artifact_sha256'] = {n: digest(a.output_dir/n) for n in ['options_daily_features.csv', 'options_variance_anchors.csv']}
    (a.output_dir/'options_variance_preparation.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['status', 'panel_rows', 'complete_anchors', 'yearly_complete_anchors']}, indent=2))


if __name__ == '__main__':
    main()
