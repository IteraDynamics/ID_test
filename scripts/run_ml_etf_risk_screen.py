"""Fixed, exploratory ETF risk screen. See ML_ETF_RISK_SCREEN_20260909.md.

Run as a module. Local adjusted OHLCV only; never downloads or touches runtime.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import warnings
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

ASSETS = ('SPY', 'QQQ', 'GLD')
FEATURES = ['ret5', 'ret20', 'ret60', 'trend', 'rv20', 'rv60', 'dd60', 'negative20', *ASSETS]
CONTROLS = ['constant100', 'constant75', 'constant50', 'trend', 'volatility']
MODELS = ['logistic', 'gbm']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_inputs(root):
    frames, sources = {}, []
    for asset in ASSETS:
        path = root / f'{asset}_1D.csv'
        mp = root / f'{asset}_1D.csv.manifest.json'
        m = json.loads(mp.read_text())
        d = pd.read_csv(path)
        assert list(d.columns) == m['schema'] == ['timestamp', 'open', 'high', 'low', 'close', 'volume'], asset
        dates = pd.to_datetime(d.pop('timestamp'), utc=True)
        assert dates.is_monotonic_increasing and not dates.duplicated().any(), asset
        assert len(d) == m['rows'] and m['request']['auto_adjust'] is True, asset
        assert m['request']['asset'] == asset and m['request']['interval'] == '1d', asset
        assert dates.iloc[0] == pd.Timestamp(m['actual_start']), asset
        assert dates.iloc[-1] == pd.Timestamp(m['actual_end']), asset
        d.index = pd.DatetimeIndex(dates)
        # Quarantine before features, validation summaries and all economic use.
        d = d.loc['2013-12-02':'2024-12-31'].astype(float)
        assert np.isfinite(d.to_numpy()).all(), asset
        assert (d[['open', 'high', 'low', 'close']] > 0).all().all(), asset
        assert (d.volume >= 0).all(), asset
        assert (d.low <= d[['open', 'close']].min(axis=1)).all(), asset
        assert (d.high >= d[['open', 'close']].max(axis=1)).all(), asset
        assert (d.low <= d.high).all(), asset
        frames[asset] = d
        sources.append({'asset': asset, 'csv_sha256': digest(path), 'manifest_sha256': digest(mp),
                        'source_rows': m['rows'], 'used_rows': len(d)})
    dates = frames['SPY'].index
    assert dates[0] == pd.Timestamp('2013-12-02', tz='UTC')
    assert dates[-1] == pd.Timestamp('2024-12-31', tz='UTC')
    for asset in ASSETS:
        assert frames[asset].index.equals(dates), f'{asset}: session mismatch'
    return frames, sources


def features(d):
    c, r = d.close, d.close.pct_change(fill_method=None)
    f = pd.DataFrame(index=d.index)
    for n in (5, 20, 60):
        f[f'ret{n}'] = c.pct_change(n, fill_method=None)
    f['trend'] = c / c.rolling(200).mean() - 1
    for n in (20, 60):
        f[f'rv{n}'] = r.rolling(n).std(ddof=1) * np.sqrt(252)
    f['dd60'] = c / c.rolling(60).max() - 1
    f['negative20'] = (r < 0).astype(float).rolling(20).mean()
    f.iloc[:200] = np.nan  # Require 200 prior closes, even though SMA includes t.
    return f


def panel(frames):
    rows = []
    for asset in ASSETS:
        d = frames[asset]
        f = features(d)
        future_min = pd.concat([d.close.shift(-k) for k in range(1, 22)], axis=1).min(axis=1, skipna=False)
        f['label'] = (future_min / d.open.shift(-1) - 1 <= -.05).astype(float).where(future_min.notna())
        f['label_end'] = pd.Series(d.index, index=d.index).shift(-21)
        for a in ASSETS:
            f[a] = float(a == asset)
        f['asset'] = asset
        f['session'] = np.arange(len(d))
        f['date'] = d.index
        rows.append(f)
    return pd.concat(rows, ignore_index=True)


def weekly_sessions(dates):
    iso = dates.isocalendar()
    keys = list(zip(iso.year, iso.week))
    return np.array([i for i in range(len(dates)-1) if keys[i] != keys[i+1]], dtype=int)


def training_rows(p, boundary):
    return p.loc[(p.label_end < boundary) & p[FEATURES + ['label']].notna().all(axis=1)]


def fit_predict(p, dates):
    sessions = weekly_sessions(dates)
    sessions = sessions[(dates[sessions].year >= 2018) & (sessions + 21 < len(dates))]
    predictions, support = [], []
    for year in range(2018, 2025):
        ss = sessions[dates[sessions].year == year]
        assert len(ss), f'No decisions in {year}'
        boundary = dates[ss[0]]
        train = training_rows(p, boundary)
        if train.label.nunique() != 2:
            raise ValueError('SCREEN_INCONCLUSIVE: one-class training fold')
        test = p.loc[p.session.isin(ss)].copy()
        assert len(test) == 3*len(ss) and test[FEATURES+['label']].notna().all().all()
        test['past_frequency'] = test.asset.map(train.groupby('asset').label.mean())
        with threadpool_limits(limits=1), warnings.catch_warnings():
            warnings.simplefilter('error', ConvergenceWarning)
            models = [make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=1000, solver='lbfgs')),
                      HistGradientBoostingClassifier(learning_rate=.05, max_iter=100, max_depth=2,
                          max_leaf_nodes=4, min_samples_leaf=100, l2_regularization=10,
                          early_stopping=False, random_state=0)]
            for name, model in zip(MODELS, models):
                model.fit(train[FEATURES], train.label)
                test[name] = model.predict_proba(test[FEATURES])[:, 1]
        predictions.append(test[['date', 'asset', 'session', 'label', 'past_frequency', *MODELS, 'trend', 'rv60']])
        for a in ASSETS:
            sub = train.loc[train.asset == a].sort_values('session')
            episodes = ((sub.label == 1) & (sub.label.shift(fill_value=0) != 1)).sum()
            support.append({'year': year, 'asset': a, 'first_signal': str(boundary),
                'training_rows': len(sub), 'training_dates': sub.date.nunique(),
                'last_training_label_end': str(sub.label_end.max()), 'positive_labels': int(sub.label.sum()),
                'positive_label_runs': int(episodes), 'weekly_decisions': len(ss)})
        print(f'{year}: completed two fixed fits; {len(ss)} weekly signals', flush=True)
    return pd.concat(predictions, ignore_index=True), pd.DataFrame(support)


def rebalance(holdings, cash, prices, weights, cost):
    """Solve V_after = V_before - cost * sum(abs(w*V_after - h*price))."""
    values = holdings * prices
    before = cash + values.sum()
    lo, hi = 0., before
    for _ in range(80):
        after = (lo+hi)/2
        if after + cost*np.abs(weights*after-values).sum() > before:
            hi = after
        else:
            lo = after
    after = (lo+hi)/2
    traded = np.abs(weights*after-values)
    fees = cost*traded
    new_holdings = weights*after/prices
    new_cash = cash - (weights*after-values).sum() - fees.sum()
    assert new_cash >= -1e-12 and abs(new_cash+sum(new_holdings*prices)-after) < 1e-10
    return new_holdings, max(0., new_cash), fees, traded, before


def target_weights(predictions, policy):
    if policy in MODELS:
        e = np.clip(1-predictions[policy].to_numpy(), .25, 1)
    elif policy.startswith('constant'):
        e = np.full(len(predictions), int(policy[8:])/100)
    elif policy == 'trend':
        e = np.where(predictions.trend > 0, 1., .25)
    else:
        rv = predictions.rv60.to_numpy()
        e = np.clip(np.divide(.10, rv, out=np.ones_like(rv), where=rv != 0), .25, 1)
    return e/3


def ledger(frames, predictions, policy, cost=.001, delay=0):
    """Close marks; first return includes initial open purchase; last is open liquidation.

    Same signal set and liquidating signal across scenarios. Delay shifts actual
    entry/exit sessions by one; retain the resulting genuine daily return dates.
    """
    dates = frames['SPY'].index
    signals = sorted(predictions.session.unique())
    assert len(signals) > 1
    # Last eligible signal supplies the exit; do not add an unevaluable interval.
    schedule = {}
    for s in signals[:-1]:
        pred = predictions.loc[predictions.session == s].set_index('asset').loc[list(ASSETS)]
        schedule[s+1+delay] = target_weights(pred, policy)
    start, end = signals[0]+1+delay, signals[-1]+1+delay
    assert end < len(dates)
    schedule[end] = np.zeros(3)
    opens = np.column_stack([frames[a].open for a in ASSETS])
    closes = np.column_stack([frames[a].close for a in ASSETS])
    holdings, cash, previous = np.zeros(3), 1., 1.
    previous_prices = opens[start]
    rows = []
    for i in range(start, end+1):
        fees, traded, before = np.zeros(3), np.zeros(3), previous
        contribution = holdings * (opens[i]-previous_prices)
        if i in schedule:
            holdings, cash, fees, traded, before = rebalance(holdings, cash, opens[i], schedule[i], cost)
        contribution += holdings*(closes[i]-opens[i])-fees
        values = holdings*closes[i]
        nav = cash+values.sum()
        ret = nav/previous-1
        assert abs(contribution.sum()/previous-ret) < 1e-10
        row = {'date': dates[i], 'nav': nav, 'return': ret, 'turnover': traded.sum()/before,
               'cost': fees.sum(), 'exposure': values.sum()/nav, 'cash_fraction': cash/nav}
        row.update({a+'_contribution': contribution[j]/previous for j,a in enumerate(ASSETS)})
        rows.append(row)
        previous, previous_prices = nav, closes[i]
    return pd.DataFrame(rows)


def metrics(d, path_metrics=True):
    r = d['return']
    mean, var = r.mean(), r.var(ddof=1)
    out = {'observations': len(r), 'ce': float(252*mean-1.5*252*var),
           'annualized_mean': float(252*mean), 'annualized_volatility': float(np.sqrt(252*var)),
           'turnover': float(d.turnover.sum()), 'average_exposure': float(d.exposure.mean()),
           'average_cash': float(d.cash_fraction.mean())}
    if path_metrics:
        nav = np.r_[1., (1+r).cumprod().to_numpy()]
        out.update(cagr=float(nav[-1]**(252/len(r))-1),
                   maximum_drawdown=float(np.min(nav/np.maximum.accumulate(nav)-1)),
                   worst_21_session_return=float(np.min(nav[21:]/nav[:-21]-1)) if len(r)>=21 else None)
    return out


def periods(years):
    return {'all': np.ones(len(years), dtype=bool), '2018_2020': years <= 2020,
            '2021_2024': years >= 2021, **{str(y): years == y for y in range(2018,2025)},
            **{f'exclude_{y}': years != y for y in range(2018,2025)}}


def forecast_metrics(pred):
    rows, bins = [], []
    for period, mask in periods(pred.date.dt.year.to_numpy()).items():
        for asset in ['pooled', *ASSETS]:
            sub = pred.loc[mask & ((pred.asset == asset) if asset != 'pooled' else True)]
            y = sub.label.to_numpy()
            baseline = np.mean((sub.past_frequency.to_numpy()-y)**2)
            for model in [*MODELS, 'past_frequency']:
                p = sub[model].to_numpy()
                brier = np.mean((p-y)**2)
                q = np.clip(p, 1e-15, 1-1e-15)
                rows.append({'period': period, 'asset': asset, 'model': model, 'rows': len(y),
                    'decision_dates': sub.date.nunique(), 'event_fraction': y.mean(), 'brier': brier,
                    'brier_skill': 1-brier/baseline if baseline else None,
                    'log_loss': -np.mean(y*np.log(q)+(1-y)*np.log(1-q))})
                group = np.minimum((p*5).astype(int), 4)
                for b in range(5):
                    take = group == b
                    bins.append({'period': period, 'asset': asset, 'model': model, 'bin': b,
                        'lower': b/5, 'upper': (b+1)/5, 'rows': int(take.sum()),
                        'mean_probability': p[take].mean() if take.any() else None,
                        'event_fraction': y[take].mean() if take.any() else None})
    return pd.DataFrame(rows), pd.DataFrame(bins)


def classify(forecast, economic):
    f = forecast[(forecast.asset == 'pooled') & (forecast.model == 'logistic')].set_index('period')
    def lift(scenario, period):
        s = economic[(economic.scenario == scenario) & (economic.period == period)].set_index('policy').ce
        return float(s['logistic'] - s.loc[CONTROLS].max())
    checks = {'brier_skill_2018_2020': float(f.loc['2018_2020', 'brier_skill']),
              'brier_skill_2021_2024': float(f.loc['2021_2024', 'brier_skill']),
              'ce_lift_all': lift('cost10', 'all'),
              'ce_lift_2018_2020': lift('cost10', '2018_2020'),
              'ce_lift_2021_2024': lift('cost10', '2021_2024'),
              'ce_lift_cost25': lift('cost25', 'all'), 'ce_lift_delay1': lift('delay1', 'all'),
              'ce_lift_exclude2020': lift('cost10', 'exclude_2020'),
              'brier_skill_exclude2020': float(f.loc['exclude_2020', 'brier_skill'])}
    main = all(checks[k]>0 for k in ['brier_skill_2018_2020', 'brier_skill_2021_2024',
                                     'ce_lift_2018_2020', 'ce_lift_2021_2024']) and checks['ce_lift_all'] > .005
    robust = checks['ce_lift_cost25'] > 0 and checks['ce_lift_delay1'] > 0
    no_crisis_rescue = checks['ce_lift_exclude2020'] > .005 and checks['brier_skill_exclude2020'] > 0
    return ('SCREEN_NEGATIVE' if not main else 'SCREEN_POSITIVE' if robust and no_crisis_rescue
            else 'SCREEN_INCONCLUSIVE'), checks


def run(root, output):
    output.mkdir(parents=True, exist_ok=False)
    frames, sources = load_inputs(root)
    p = panel(frames)
    pred, support = fit_predict(p, frames['SPY'].index)
    fm, calibration = forecast_metrics(pred)
    daily, economics, contributions = [], [], []
    for scenario, cost, delay in [('cost10', .001, 0), ('cost25', .0025, 0), ('delay1', .001, 1)]:
        for policy in [*CONTROLS, *MODELS]:
            d = ledger(frames, pred, policy, cost, delay)
            d['scenario'], d['policy'] = scenario, policy
            daily.append(d)
            for period, mask in periods(d.date.dt.year.to_numpy()).items():
                sub = d.loc[mask]
                economics.append({'scenario': scenario, 'policy': policy, 'period': period,
                                  **metrics(sub, not period.startswith('exclude_'))})
                for a in ASSETS:
                    contributions.append({'scenario': scenario, 'policy': policy, 'period': period,
                        'asset': a, 'annualized_mean_contribution': 252*sub[a+'_contribution'].mean(),
                        'sum_daily_return_contribution': sub[a+'_contribution'].sum()})
    econ = pd.DataFrame(economics)
    classification, checks = classify(fm, econ)
    artifacts = {'predictions': pred, 'fold_support': support, 'forecast_metrics': fm,
                 'calibration': calibration, 'daily_ledger': pd.concat(daily, ignore_index=True),
                 'economic_metrics': econ, 'asset_contributions': pd.DataFrame(contributions)}
    hashes = {}
    for name, data in artifacts.items():
        path = output/(name+'.csv')
        data.to_csv(path, index=False, lineterminator='\n')
        hashes[path.name] = digest(path)
    import sklearn
    report = {'classification': classification, 'checks': checks, 'fits': 14,
        'sources': sources, 'artifact_sha256': hashes,
        'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                        'pandas': pd.__version__, 'sklearn': sklearn.__version__},
        'code': {'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                 'runner_sha256': digest(__file__)},
        'forecast_dates': int(pred.date.nunique()), 'forecast_rows': len(pred),
        'first_signal': str(pred.date.min()), 'last_signal': str(pred.date.max()),
        'limitations': 'Exploratory, overlapping labels, correlated ETFs, retrospective fund selection; '
                       'adjusted synthetic units; cash zero; assumed costs; no significance or deployment claim.',
        'contribution_definition': 'Additive daily return contributions including allocated trading fees; not standalone ETF CE.',
        'exclusion_definition': 'Remove daily observations from continuous original ledger; no refit or reoptimized counterfactual. '
                                'No CAGR/drawdown on disconnected exclusion samples.',
        'replay': 'Ledger and report can be recomputed from cached predictions without additional fits.'}
    (output/'report.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({'classification': classification, 'checks': checks}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.input_root, args.output_dir)


if __name__ == '__main__':
    main()
