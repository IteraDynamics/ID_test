"""Vintage feature construction and synthetic-label learning power; no real-label fits.

Run from repository root. Fixed design: annual expanding folds 2018-24, ridge
alpha=10, 21-session labels, delayed open entry, shared three-crop event vectors.
A necessary predictive gate is tested before any full economic campaign.
"""
from __future__ import annotations
import calendar
import collections
import hashlib
import json
from pathlib import Path
import re
import numpy as np
import pandas as pd

ROOT = Path('artifacts/ml_crop_feasibility_20260910')
OUT = Path('artifacts/ml_crop_learning_test_20260910')
ASSETS = ['CORN', 'WEAT', 'SOYB']


def build_features(rows):
    """Current forecast only; revisions reference the same year in prior release."""
    sources = collections.defaultdict(list)
    for row in rows:
        sources[row['source_file']].append(row)
    monthly = collections.defaultdict(list)
    for name in sorted(sources):
        monthly[name[:7]].append(name)
    selected = []
    for month, names in sorted(monthly.items()):
        def canonical(name):
            return sorted((r['asset'], r['crop_year'], r['forecast_month'], r['field'], r['value']) for r in sources[name])
        if any(canonical(n) != canonical(names[0]) for n in names[1:]):
            raise ValueError(f'Different selected fields in same-month versions: {month}')
        selected.append(names[0])  # earliest dated version, identical selected fields
    output = []
    prior = {}
    for name in selected:
        date = pd.Timestamp(name[:10], tz='UTC')
        by_asset = collections.defaultdict(dict)
        for row in sources[name]:
            if row['unit'] != 'million_bushels':
                raise ValueError('Unexpected unit')
            if row['report_month'] != date.strftime('%B %Y'):
                raise ValueError('Report/date mismatch')
            if row['forecast_month'][:3] != calendar.month_abbr[date.month]:
                continue
            if 'Proj.' not in row['crop_year']:
                continue
            match = re.fullmatch(r'(\d{4})/(\d{2}) Proj\.', row['crop_year'])
            if not match or (int(match[1])+1) % 100 != int(match[2]):
                raise ValueError('Malformed crop year')
            year = int(match[1])
            group = by_asset[row['asset']].setdefault(year, {})
            if row['field'] in group:
                raise ValueError('Duplicate feature field')
            group[row['field']] = row['value']
        for asset in ASSETS:
            years = by_asset[asset]
            valid = {}
            for year, values in years.items():
                if set(values) != {'supply, total', 'use, total', 'ending stocks'}:
                    raise ValueError('Incomplete balance')
                if any(v is None for v in values.values()):
                    continue
                if not all(np.isfinite(v) for v in values.values()):
                    raise ValueError('Nonfinite balance')
                supply, use, stocks = (values[k] for k in ['supply, total', 'use, total', 'ending stocks'])
                if use <= 0 or stocks < 0 or abs(supply-use-stocks) > 2:
                    raise ValueError('Invalid balance')
                valid[year] = stocks/use
            if not years or max(years) not in valid:
                prior[asset] = (date, valid)
                continue
            year = max(years)
            old = prior.get(asset)
            previous_ratio = old[1].get(year) if old and (date-old[0]).days <= 62 else None
            revision = valid[year]-previous_ratio if previous_ratio is not None else None
            output.append(dict(release_date=date.isoformat(), asset=asset, crop_year=year,
                               stocks_use=valid[year], revision=revision,
                               revision_missing=int(revision is None),
                               prior_release_date=old[0].isoformat() if previous_ratio is not None else None,
                               source_file=name))
            prior[asset] = (date, valid)
    frame = pd.DataFrame(output)
    frame['revision'] = frame['revision'].astype(float)
    frame['prior_release_date'] = frame['prior_release_date'].astype('string')
    return frame


def make_panel(features):
    prices = {a: pd.read_csv(ROOT/f'{a}_1D.csv', index_col='timestamp', parse_dates=True) for a in ASSETS}
    prices['BIL'] = pd.read_csv('artifacts/ml_energy_feasibility_20260910/BIL_1D.csv', index_col='timestamp', parse_dates=True)
    cal = prices['BIL'].index
    for f in prices.values():
        if not f.index.is_unique or not f.index.is_monotonic_increasing or f.index.max().year > 2024:
            raise ValueError('Invalid price calendar')
        cal = cal.intersection(f.index)
    rows = []
    for date, group in features.groupby('release_date', sort=True):
        if set(group.asset) != set(ASSETS):
            continue
        release = pd.Timestamp(date)
        known = cal.searchsorted(release, side='right')-1
        entry = cal.searchsorted(release, side='right')+1
        exit_ = entry+21
        if known < 63 or exit_ >= len(cal):
            continue
        if any(prices[a].loc[cal[[entry,exit_]], 'volume'].min() <= 0 for a in ASSETS+['BIL']):
            continue
        cash = prices['BIL'].loc[cal[exit_], 'open']/prices['BIL'].loc[cal[entry], 'open']-1
        for a in ASSETS:
            row = group[group.asset == a].iloc[0].to_dict()
            f = prices[a].reindex(cal)
            row.update(entry_date=cal[entry].isoformat(), exit_date=cal[exit_].isoformat(),
                       feature_price_date=cal[known].isoformat(),
                       momentum21=f.close.iloc[known]/f.close.iloc[known-21]-1,
                       momentum63=f.close.iloc[known]/f.close.iloc[known-63]-1,
                       volatility63=f.close.iloc[known-63:known+1].pct_change().dropna().std(),
                       target=f.open.iloc[exit_]/f.open.iloc[entry]-1-cash,
                       month_sin=np.sin(2*np.pi*release.month/12),
                       month_cos=np.cos(2*np.pi*release.month/12))
            rows.append(row)
    return pd.DataFrame(rows)


def ridge_operator(x, train, test, alpha=10.):
    """Train-only scaling and centered ridge with unpenalized intercept."""
    z=x[train];mu=z.mean(0);sd=z.std(0);sd[sd<1e-12]=1
    z=(z-mu)/sd;zt=(x[test]-mu)/sd
    h=zt@np.linalg.solve(z.T@z+alpha*np.eye(z.shape[1]),z.T)
    return h+(1-h.sum(1,keepdims=True))/len(train)


def operators(panel):
    controls=['month_sin','month_cos','momentum21','momentum63','volatility63']
    identity=np.column_stack([(panel.asset==a).astype(float) for a in ASSETS])
    x0=np.column_stack([identity,panel[controls].to_numpy(float)])
    x1=np.column_stack([x0,panel[['stocks_use','revision','revision_missing']].fillna(0).to_numpy(float)])
    release=pd.to_datetime(panel.release_date);ends=pd.to_datetime(panel.exit_date)
    hs=[np.zeros((len(panel),len(panel))) for _ in range(2)];evaluated=[];folds=[]
    for year in range(2018,2025):
        test=np.flatnonzero(release.dt.year==year)
        if not len(test):continue
        cutoff=release.iloc[test].min()
        train=np.flatnonzero((release<cutoff)&(ends<cutoff))
        if len(train)<100:raise ValueError('Insufficient training support')
        for x,h in zip([x0,x1],hs):h[np.ix_(test,train)]=ridge_operator(x,train,test)
        evaluated.extend(test.tolist())
        folds.append(dict(year=year,train_rows=len(train),test_rows=len(test),
                          latest_training_exit=ends.iloc[train].max().isoformat(),cutoff=cutoff.isoformat()))
    return hs,np.array(evaluated),folds


def simulate(panel, hs, evaluated, draws=2000):
    """Known linear crop signal, realistic joint noise; actual targets never fitted."""
    n=len(panel)//3
    noise=panel.target.to_numpy().reshape(n,3)
    noise=(noise-noise.mean(0))/noise.std(0)
    # Fixed economic direction and scale, selected before predictive outcomes.
    # Global normalization calibrates the synthetic DGP only, never a model transform.
    g=(-.5*panel.stocks_use/.1-.5*panel.revision.fillna(0)/.03).to_numpy()
    nuisance=np.column_stack([np.ones(len(panel)),
        *[(panel.asset==a).astype(float) for a in ASSETS],
        panel[['month_sin','month_cos','momentum21','momentum63','volatility63']].to_numpy(float)])
    g=g-nuisance@np.linalg.lstsq(nuisance,g,rcond=None)[0]
    g=g/g.std()
    signal_errors=[(g-h@g)[evaluated] for h in hs]
    rng=np.random.default_rng(29011);results=[]
    for block in [3,6]:
        starts=rng.integers(0,n,(draws,(n+block-1)//block))
        ix=((starts[:,:,None]+np.arange(block))%n).reshape(draws,-1)[:,:n]
        y=noise[ix].reshape(draws,-1)
        errs=[(y-y@h.T)[:,evaluated] for h in hs]
        null=(errs[0]**2-errs[1]**2).mean(1)
        threshold=max(0.,float(np.quantile(null[:draws//2],.95)))
        oracle_null=(y[:,evaluated]*g[evaluated]).mean(1)
        oracle_threshold=max(0.,float(np.quantile(oracle_null[:draws//2],.95)))
        for effect in [0.,.02,.05,.10,.15,.20,.50,.80]:
            e=[np.sqrt(1-effect**2)*err+effect*s for err,s in zip(errs,signal_errors)]
            gain=(e[0]**2-e[1]**2).mean(1)
            oracle_score=np.sqrt(1-effect**2)*oracle_null+effect*(g[evaluated]**2).mean()
            results.append(dict(block_events=block,injected_effect=effect,
                                detection_fraction=float((gain[draws//2:]>threshold).mean()),
                                null_threshold=threshold,evaluation_draws=draws//2,
                                known_signal_detection_fraction=float((oracle_score[draws//2:]>oracle_threshold).mean())))
    return results


def main():
    OUT.mkdir(exist_ok=True)
    audit=json.loads(Path('docs/research/ML_CROP_FEASIBILITY_AUDIT_20260910.json').read_text())
    for name, meta in audit['price_audit'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=meta['sha256']:
            raise ValueError('Price input hash mismatch: '+name)
    for meta in audit['xml_manifest']:
        if 'error' not in meta and hashlib.sha256((ROOT/'xml'/meta['file']).read_bytes()).hexdigest()!=meta['sha256']:
            raise ValueError('Raw XML input hash mismatch')
    rows=json.loads((ROOT/'parsed_cells.json').read_text())
    features=build_features(rows)
    # Future-release deletion must leave all earlier feature rows identical.
    cutoff='2018-01-01'
    truncated=build_features([r for r in rows if r['source_file'][:10]<cutoff])
    pd.testing.assert_frame_equal(features[features.release_date<cutoff].reset_index(drop=True),truncated)
    panel=make_panel(features);hs,evaluated,folds=operators(panel)
    results=simulate(panel,hs,evaluated)
    central=[r['detection_fraction'] for r in results if r['injected_effect']==.05]
    report=dict(status='SYNTHETIC_LEARNING_POWER_ONLY',actual_label_model_fits=0,
                feature_rows=len(features),panel_rows=len(panel),events=len(panel)//3,
                test_events=len(evaluated)//3,first_entry=panel.entry_date.min(),last_exit=panel.exit_date.max(),
                missing_revisions=int(features.revision_missing.sum()),folds=folds,
                future_release_invariance_passed=True,seed=29011,alpha=10,central_effect=.05,
                necessary_gate_power_passed=min(central)>=.5,results=results,
                limitations=[
                    'Necessary predictive gate only. Full joint economic-gate power cannot exceed its power under this DGP.',
                    'No real-label fitted predictions, feature-return correlations, strategy backtest or break-even costs computed.',
                    'Synthetic signal is residualized against nuisance controls over the full design matrix, then standardized solely to define an incremental DGP. Model scaling remains train-only.',
                    'Injected effect is a DGP amplitude, not a measured market IC. Noise calibration is a simulation assumption.',
                    'Joint calendar-block noise preserves within-block serial and cross-asset dependence, not all regimes.',
                    'Annual expanding folds purge training labels ending on/after first test release.',
                    'Entry after one full post-release session; 21-session overlapping targets retained jointly. No 2025 prices.',
                    'Zero-volume endpoints excluded, but historical fills, spreads, mandates and broker access remain unverified.',
                    'No estimated market-consensus surprise: revisions compare identical crop years across source vintages.',
                    'Known-signal comparator uses the injected signal directly with a separate score test; optimistic diagnostic, not a fitted strategy or formal universal upper bound.',
                    'Passing this preliminary necessary gate alone would not authorize or validate an economic campaign.'
                ])
    features.to_csv(OUT/'crop_features.csv',index=False)
    # Save labels for reproducibility, without reporting observed predictive results.
    panel.to_csv(OUT/'crop_panel.csv',index=False)
    for key in ['crop_features.csv','crop_panel.csv']:
        report.setdefault('artifact_sha256',{})[key]=hashlib.sha256((OUT/key).read_bytes()).hexdigest()
    report['input_sha256']={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'parsed_cells.json',Path('artifacts/ml_energy_feasibility_20260910/BIL_1D.csv')]}
    report['strong_signal_canary_passed']=all(r['detection_fraction']>.95 for r in results if r['injected_effect']==.8)
    (OUT/'learning_power_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
