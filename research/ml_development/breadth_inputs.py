"""Manifest-verified adjusted eight-ETF inputs, pre-2025 only."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
ASSETS=("SPY","QQQ","GLD","IWM","EFA","EEM","IEF","TLT")

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
        assert (d.low <= d[['open', 'close']].min(axis=1)+1e-10*d.close).all(), asset
        assert (d.high+1e-10*d.close >= d[['open', 'close']].max(axis=1)).all(), asset
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

