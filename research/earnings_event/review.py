"""Reproduce structural review and outcome-blind source sample; never returns."""
from __future__ import annotations
import argparse
from bisect import bisect_right
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
from .audit import events, price_inventory, read_rows, day, finite, digest


def select_sample(data_root, cutoff=date(2024,12,31), size=30):
    clean,counts,_=events(data_root/'earnings_surprise_history.csv',cutoff)
    candidates=[]; inventories={}; cached={}
    for ticker,d in clean:
        if ticker not in cached:
            path=data_root/(ticker+'_1D.csv')
            if not path.is_file():
                inventories[ticker]={'structural_ok':False,'error':'missing exact root file'}
                cached[ticker]=[]
            else:
                inventories[ticker],cached[ticker]=price_inventory(path,cutoff)
        ds=cached[ticker];k=bisect_right(ds,d)
        if k>=60 and k+6<len(ds):
            candidates.append({'ticker':ticker,'date':str(d),
                'rank_hash':hashlib.sha256((ticker+'|'+str(d)).encode()).hexdigest()})
    sample=sorted(candidates,key=lambda r:r['rank_hash'])[:size]
    spy_inv,spy_dates=price_inventory(data_root/'SPY_1D.csv',cutoff)
    spy_set=set(spy_dates)
    adjustment=Counter(); invalid=[]; gaps=[]; manifests=[]
    for ticker in sorted(inventories):
        path=data_root/(ticker+'_1D.csv')
        if not path.is_file(): continue
        manifest=path.with_suffix('.csv.manifest.json')
        if manifest.is_file():
            m=json.loads(manifest.read_text(encoding='utf-8-sig'))
            adjustment[str(m.get('request',{}).get('auto_adjust'))]+=1
            manifests.append({'ticker':ticker,'sha256':digest(manifest),
                              'auto_adjust':m.get('request',{}).get('auto_adjust')})
        _,rows=read_rows(path)
        for n,r in enumerate(rows,2):
            try:
                if day(r['timestamp'])>cutoff:continue
                o,h,l,c,v=[float(r[k]) for k in ('open','high','low','close','volume')]
                bad=not all(finite(x) for x in (o,h,l,c,v)) or min(o,h,l,c)<=0 or v<0 or l>min(o,c) or h<max(o,c)
            except (KeyError,ValueError,TypeError,OverflowError):bad=True
            if bad:invalid.append({'ticker':ticker,'csv_row':n,'values':r})
        ds=cached[ticker]
        if ds:
            missing=sorted(d for d in spy_set-set(ds) if ds[0]<=d<=ds[-1])
            extra=sorted(set(ds)-spy_set)
            if missing or extra:gaps.append({'ticker':ticker,'missing_spy_dates':[str(d) for d in missing],
                                            'extra_dates':[str(d) for d in extra]})
    return {'status':'SOURCE_REPAIR_REQUIRED_NO_PERFORMANCE', 'cutoff':str(cutoff),
            'earnings_sha256':digest(data_root/'earnings_surprise_history.csv'),
            'counts':counts,'candidate_windows':len(candidates),
            'candidate_tickers':len({r['ticker'] for r in candidates}),
            'stock_auto_adjust_counts':dict(adjustment),
            'stock_manifest_hashes':manifests,'invalid_rows':invalid,
            'spy':spy_inv,'calendar_proxy_discrepancies':gaps,
            'calendar_note':'SPY observed dates are a diagnostic proxy, not a verified exchange calendar.',
            'sample_rule':'SHA256(ticker|YYYY-MM-DD), first 30 from structurally clean five-session coverage; no replacement',
            'sample':sample,'source_review_complete':False,'performance':None}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=select_sample(a.data_root)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(f'Review: {a.output}; {result["candidate_windows"]} candidate windows; no performance computed')

if __name__=='__main__':main()
