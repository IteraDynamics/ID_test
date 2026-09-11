"""Offline monthly candidate/lifecycle extraction, 2008--2024. No P&L or tuning.

Use first observed session of each month as signal date; reserve next observed
session for potential execution. Full quote lifecycle enables later accounting.
This is discovery data, not a sealed holdout or a deployable strategy.
"""
from __future__ import annotations
import argparse, hashlib, json, platform, zipfile
from pathlib import Path
import pandas as pd
import pyarrow
from scripts.analyze_options_quote_review import select_legs

YEARS=range(2008,2025)
SELECTION_COLUMNS=['date','expiration','strike','type','delta','contract_id']


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()


def run(root, output):
    folder=root/'artifacts/free_options_history_probe'
    paths=[folder/f'spy_options_{year}.parquet' for year in YEARS]
    missing=[str(p) for p in paths if not p.is_file()]
    if missing: raise FileNotFoundError('Missing historical sources: '+', '.join(missing))
    output.mkdir(parents=True,exist_ok=False)
    report={'purpose':'MONTHLY_CONTRACT_LIFECYCLE_DATA_ONLY',
            'environment':{'python':platform.python_version(),'pandas':pd.__version__,'pyarrow':pyarrow.__version__},
            'selection':{'signal':'first observed session each calendar month','execution':'next observed session; quote feasibility assessed separately',
                         'expiry':'nearest 35 calendar days within 30--45; earlier expiry breaks ties',
                         'short_delta':.16,'maximum_delta_distance':.05,'wing_distance_fraction_of_short_strike':.02},
            'sources':[],'limitations':['No return or trading approval implied.','Month boundaries follow observed source sessions, not an independently verified exchange calendar.',
            'Delta is vendor supplied. Contract deliverables and historical availability are unverified.',
            'Data ends 2024-12-31; unfinished cycles must not be treated as zero P&L.']}
    selections=[]; contracts=set(); sessions=[]
    for year,path in zip(YEARS,paths):
        print(f'Selecting {year}',flush=True)
        report['sources'].append({'file':path.name,'bytes':path.stat().st_size,'sha256':digest(path)})
        f=pd.read_parquet(path,columns=SELECTION_COLUMNS)
        dates=pd.to_datetime(f.date,errors='raise')
        if not dates.dt.year.eq(year).all(): raise ValueError(f'Mislabeled source year: {path.name}')
        f['date']=dates.dt.strftime('%Y-%m-%d')
        f['expiration']=pd.to_datetime(f.expiration,errors='raise').dt.strftime('%Y-%m-%d')
        if f.duplicated(['date','contract_id']).any(): raise ValueError(f'Duplicate contract/day: {path.name}')
        dates=sorted(f.date.unique()); sessions.extend(dates)
        first=pd.Series(dates).groupby(pd.Series(dates).str[:7]).first().tolist()
        for date in first:
            legs=select_legs(f.loc[f.date==date])
            row={'signal_date':date,'status':'NO_GEOMETRY' if legs is None else 'SELECTED'}
            if legs is not None:
                row['expiration']=legs['short_put'].expiration
                for role,r in legs.items():
                    row[role]=r.contract_id;row[role+'_strike']=float(r.strike)
                    contracts.add(r.contract_id)
            selections.append(row)
        del f
    next_session=dict(zip(sessions[:-1],sessions[1:]))
    for row in selections: row['potential_execution_date']=next_session.get(row['signal_date'])
    pd.DataFrame(selections).to_csv(output/'candidate_contracts.csv',index=False)
    quote_path=output/'contract_daily_quotes.csv';written=False;counts={};columns=None
    for year,path in zip(YEARS,paths):
        print(f'Extracting contract history {year}',flush=True)
        if digest(path)!=report['sources'][year-min(YEARS)]['sha256']:
            raise ValueError(f'Source changed during extraction: {path.name}')
        f=pd.read_parquet(path)
        if columns is None: columns=list(f.columns)
        if set(f.columns)!=set(columns): raise ValueError(f'Quote schema changed: {path.name}')
        f=f[columns]
        g=f.loc[f.contract_id.isin(contracts)].copy()
        if len(g):
            g.to_csv(quote_path,index=False,mode='a' if written else 'w',header=not written)
            written=True
        counts[str(year)]=len(g)
        del f,g
    if not written: raise ValueError('No selected contract histories; no review ZIP produced')
    report.update(candidate_months=len(selections),selected_months=sum(r['status']=='SELECTED' for r in selections),unique_contracts=len(contracts),export_rows_by_year=counts)
    report['export_sha256']={p.name:digest(p) for p in output.glob('*.csv')}
    (output/'condor_panel_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    zip_path=output.with_name(output.name+'.zip')
    with zipfile.ZipFile(zip_path,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(output.iterdir()): z.write(p,p.name)
    print(f'Upload this file: {zip_path.resolve()}')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();run(a.input_root.resolve(),a.output_dir.resolve())
