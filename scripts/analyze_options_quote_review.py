"""Audit uploaded quote windows; entry pricing diagnostics, never performance."""
from __future__ import annotations
import argparse, hashlib, io, json, zipfile
from pathlib import Path
import numpy as np
import pandas as pd


def select_legs(frame):
    """Fixed inherited geometry: nearest 35 DTE in 30--45, 16delta, 2% wings.

    Selection uses vendor delta and listed strikes, never in_the_money/mark/last.
    Pick contracts first; do not substitute a different strike for a bad quote.
    """
    f=frame.copy()
    dte=(pd.to_datetime(f.expiration)-pd.to_datetime(f.date)).dt.days
    f=f.loc[dte.between(30,45)].copy()
    if f.empty: return None
    exps=f[['date','expiration']].drop_duplicates()
    exps['distance']=abs((pd.to_datetime(exps.expiration)-pd.to_datetime(exps.date)).dt.days-35)
    expiry=exps.sort_values(['distance','expiration']).iloc[0].expiration
    f=f.loc[f.expiration==expiry]
    legs={}
    for kind,target in [('put',-.16),('call',.16)]:
        g=f.loc[(f.type==kind)&np.isfinite(f.delta)&np.isfinite(f.strike)&(f.strike>0)].copy()
        g=g.loc[g.delta.between(-1,0) if kind=='put' else g.delta.between(0,1)]
        if g.empty: return None
        g['distance']=abs(g.delta-target)
        short=g.sort_values(['distance','strike']).iloc[0]
        if abs(short.delta-target)>.05: return None
        wing=g.loc[g.strike<short.strike].copy() if kind=='put' else g.loc[g.strike>short.strike].copy()
        if wing.empty: return None
        wing['distance']=abs(wing.strike-short.strike*(.98 if kind=='put' else 1.02))
        long=wing.sort_values(['distance','strike']).iloc[0]
        legs['short_'+kind]=short
        legs['long_'+kind]=long
    if legs['short_put'].strike>=legs['short_call'].strike: return None
    return legs


def quote_values(legs):
    rows=list(legs.values())
    valid=all(np.isfinite(r.bid) and np.isfinite(r.ask) and r.bid>=0 and r.ask>=r.bid for r in rows)
    if not valid: return {'valid_quotes':False}
    mid=sum((r.bid+r.ask)/2*(1 if k.startswith('short') else -1) for k,r in legs.items())
    credit=sum(r.bid if k.startswith('short') else -r.ask for k,r in legs.items())
    debit=sum(r.ask if k.startswith('short') else -r.bid for k,r in legs.items())
    return dict(valid_quotes=True, midpoint_credit=mid, bid_ask_credit=credit,
                immediate_liquidation_debit=debit, spread_roundtrip=debit-credit,
                all_sides_positive_size=all(r.bid_size>0 and r.ask_size>0 for r in rows),
                all_short_bids_positive=all(r.bid>0 for k,r in legs.items() if k.startswith('short')))


def run(bundle, output):
    output.mkdir(parents=True,exist_ok=False)
    report={'status':'CONTINUE_QUOTE_RESEARCH_NOT_A_BACKTEST','bundle_sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(), 'windows':[]}
    entries=[]
    with zipfile.ZipFile(bundle) as z:
        original=json.loads(z.read('quote_review_report.json'))
        for name,expected in original['export_sha256'].items():
            raw=z.read(name)
            assert hashlib.sha256(raw).hexdigest()==expected, name
            f=pd.read_csv(io.BytesIO(raw))
            assert (pd.to_datetime(f.date).dt.year<=2024).all()
            parsed=f.contract_id.str.extract(r'^SPY(\d{6})([CP])(\d{8})$')
            id_ok=(pd.to_datetime(parsed[0],format='%y%m%d',errors='coerce')==pd.to_datetime(f.expiration)) & (parsed[1].map({'C':'call','P':'put'})==f.type) & ((pd.to_numeric(parsed[2],errors='coerce')/1000-f.strike).abs()<1e-8)
            daily={d:g for d,g in f.groupby('date',sort=True)}
            dates=list(daily)
            report['windows'].append(dict(file=name,rows=len(f),days=len(dates),id_mismatches=int((~id_ok).sum()),duplicates=int(f.duplicated(['date','contract_id']).sum()),itm_nonzero=int(f.in_the_money.ne(0).sum()),zero_bid=int(f.bid.eq(0).sum()),crossed=int(f.ask.lt(f.bid).sum()),mark_mid_disagreement_over_cent=int((abs(f.mark-(f.bid+f.ask)/2)>.010001).sum())))
            for i,(date,g) in enumerate(daily.items()):
                legs=select_legs(g)
                if legs is None:
                    entries.append(dict(date=date,status='NO_GEOMETRY'));continue
                entry=dict(date=date,status='SELECTED',expiration=legs['short_put'].expiration)
                entry.update(quote_values(legs))
                for role,r in legs.items():
                    entry[role]=r.contract_id
                    entry[role+'_strike']=float(r.strike)
                entry['max_wing_width']=max(legs['short_put'].strike-legs['long_put'].strike,legs['long_call'].strike-legs['short_call'].strike)
                if i+1<len(dates):
                    nxt=daily[dates[i+1]].set_index('contract_id',drop=False)
                    entry['next_date']=dates[i+1]
                    entry['next_all_contracts_present']=all(r.contract_id in nxt.index for r in legs.values())
                    if entry['next_all_contracts_present']:
                        entry.update({'next_'+k:v for k,v in quote_values({role:nxt.loc[r.contract_id] for role,r in legs.items()}).items()})
                entries.append(entry)
    frame=pd.DataFrame(entries)
    frame.to_csv(output/'entry_quote_diagnostics.csv',index=False)
    good=frame.loc[frame.valid_quotes.eq(True)]
    report['aggregate']=dict(rows=sum(x['rows'] for x in report['windows']),candidate_days=len(frame),selected=len(good),median_midpoint_credit=float(good.midpoint_credit.median()),median_bid_ask_credit=float(good.bid_ask_credit.median()),median_spread_roundtrip=float(good.spread_roundtrip.median()),positive_credit=int(good.bid_ask_credit.gt(0).sum()),all_sides_positive_size=int(good.all_sides_positive_size.sum()),next_observations=int(frame.next_date.notna().sum()),next_contracts_present=int(frame.next_all_contracts_present.eq(True).sum()))
    report['units']='Option price per share; multiply by assumed standard 100-share deliverable for contract dollars. Deliverables not independently certified.'
    report['limitations']=['Purpose-selected overlapping quote samples; no P&L, annualization or significance claim.','Same-day quotes are diagnostics only; next-session contracts selected from previous session.','Vendor end-of-day timestamp claim is not independent timestamp verification.','Bid/ask snapshots and sizes do not certify simultaneous executable fills.']
    report['diagnostics_sha256']=hashlib.sha256((output/'entry_quote_diagnostics.csv').read_bytes()).hexdigest()
    (output/'quote_audit.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();run(a.bundle,a.output_dir)
