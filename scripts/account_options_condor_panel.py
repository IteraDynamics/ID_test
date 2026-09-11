"""Retrospective one-contract quote accounting; not an executable options backtest.

Fixed entry contracts, next observed session, adverse sides, exit <=7 DTE.
No fitting, substitution, optimization, implied expiry payoff or zero imputation.
"""
import argparse,hashlib,io,json,zipfile
from pathlib import Path
import pandas as pd
import numpy as np

ROLES=['short_put','long_put','short_call','long_call']


def prices(day,ids,opening=False,zero_salvage=False):
    if any(c not in day.index for c in ids):return None
    f=day.loc[ids]
    if len(f)!=4:raise ValueError('Duplicate contract')
    if not np.isfinite(f[['bid','ask']]).all().all() or (f.bid<0).any() or (f.ask<f.bid).any():return None
    sizes=[f.iloc[i]['bid_size' if ((i%2==0)==opening) else 'ask_size'] for i in range(4)]
    mid=sum((r.bid+r.ask)/2*(1 if i%2==0 else -1) for i,(_,r) in enumerate(f.iterrows()))
    f=f.copy()
    for i,size in enumerate(sizes):
        if np.isfinite(size) and size>0: continue
        if zero_salvage and not opening and i%2==1 and np.isfinite(size) and size==0:
            f.iloc[i,f.columns.get_loc('bid')]=0.0
        else: return None
    credit=sum((r.bid if opening else r.ask) if i%2==0 else -(r.ask if opening else r.bid) for i,(_,r) in enumerate(f.iterrows()))
    return credit,mid


def run(bundle,out,zero_salvage=False):
    out.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(bundle) as z:
        manifest=json.loads(z.read('condor_panel_report.json'))
        for name,h in manifest['export_sha256'].items():assert hashlib.sha256(z.read(name)).hexdigest()==h,name
        candidates=pd.read_csv(io.BytesIO(z.read('candidate_contracts.csv')))
        quotes=pd.read_csv(io.BytesIO(z.read('contract_daily_quotes.csv')))
    assert not quotes.duplicated(['date','contract_id']).any()
    assert pd.to_datetime(quotes.date).max()<=pd.Timestamp('2024-12-31')
    daily={d:g.set_index('contract_id') for d,g in quotes.groupby('date')}
    sessions=sorted(daily)
    rows=[];marks=[]
    for _,c in candidates.iterrows():
        row={'signal_date':c.signal_date,'status':c.status};rows.append(row)
        if c.status!='SELECTED':continue
        ids=[c[r] for r in ROLES]
        entry=c.potential_execution_date
        row.update(entry_date=entry,expiration=c.expiration)
        assert entry>c.signal_date
        ep=prices(daily.get(entry,pd.DataFrame()),ids,opening=True)
        if ep is None:row['status']='REJECT_ENTRY_QUOTES';continue
        if ep[0]<=0:row['status']='REJECT_NONPOSITIVE_CREDIT';continue
        row['entry_credit_dollars']=100*ep[0]
        threshold=str((pd.Timestamp(c.expiration)-pd.Timedelta(days=7)).date())
        exits=[d for d in sessions if d>=threshold and d>entry and d<c.expiration]
        if not exits:row['status']='UNRESOLVED_EXIT';continue
        exit_date=exits[0];row['exit_date']=exit_date
        xp=prices(daily[exit_date],ids,zero_salvage=zero_salvage)
        if xp is None:row['status']='UNRESOLVED_EXIT_QUOTES';continue
        row.update(status='CLOSED',exit_debit_dollars=100*xp[0],gross_dollars=100*(ep[0]-xp[0]),midpoint_pnl_dollars=100*(ep[1]-xp[1]),net_dollars=100*(ep[0]-xp[0])-5.2)
        for side in ['put','call']:
            short_id,long_id=c['short_'+side],c['long_'+side]
            es,el=daily[entry].loc[short_id],daily[entry].loc[long_id]
            xs,xl=daily[exit_date].loc[short_id],daily[exit_date].loc[long_id]
            salvage=xl.bid if xl.bid_size>0 else 0.0
            row[side+'_net_dollars']=100*(es.bid-el.ask-xs.ask+salvage)-2.6
        row['zero_size_long_exits']=sum(daily[exit_date].loc[c[r],'bid_size']==0 for r in ['long_put','long_call'])
        assert abs(row['put_net_dollars']+row['call_net_dollars']-row['net_dollars'])<1e-7
        row['max_wing_dollars']=100*max(c.short_put_strike-c.long_put_strike,c.long_call_strike-c.short_call_strike)
        gaps=0
        for d in sessions:
            if not entry<=d<=exit_date:continue
            mp=prices(daily[d],ids,zero_salvage=zero_salvage)
            if mp is None:gaps+=1
            marks.append(dict(signal_date=c.signal_date,date=d,net_liquidation_pnl_dollars=None if mp is None else 100*(ep[0]-mp[0])-5.2,quotes_available=mp is not None))
        row['missing_daily_marks']=gaps
    f=pd.DataFrame(rows);m=pd.DataFrame(marks)
    f.to_csv(out/'trade_accounting.csv',index=False);m.to_csv(out/'daily_liabilities.csv',index=False)
    closed=f.loc[f.status=='CLOSED'].copy()
    yearly=closed.groupby(closed.signal_date.str[:4]).agg(trades=('net_dollars','size'),net_dollars=('net_dollars','sum'),gross_dollars=('gross_dollars','sum'),mean_net=('net_dollars','mean'),worst_trade=('net_dollars','min'))
    yearly.to_csv(out/'yearly_accounting.csv')
    report=dict(status='DESCRIPTIVE_QUOTE_ACCOUNTING_ONLY',zero_salvage_long_options=zero_salvage,bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),candidate_status_counts=f.status.value_counts().to_dict(),closed_trades=len(closed),net_dollars=float(closed.net_dollars.sum()),gross_dollars=float(closed.gross_dollars.sum()),midpoint_pnl_dollars=float(closed.midpoint_pnl_dollars.sum()),put_net_dollars=float(closed.put_net_dollars.sum()),call_net_dollars=float(closed.call_net_dollars.sum()),zero_size_long_exits=int(closed.zero_size_long_exits.sum()),win_fraction=float(closed.net_dollars.gt(0).mean()),mean_net_dollars=float(closed.net_dollars.mean()),median_net_dollars=float(closed.net_dollars.median()),worst_trade_dollars=float(closed.net_dollars.min()),best_trade_dollars=float(closed.net_dollars.max()),closed_trades_missing_marks=int(closed.missing_daily_marks.gt(0).sum()),fee_sensitivity={str(fee):float(closed.gross_dollars.sum()-len(closed)*8*fee) for fee in [0,.65,1,2]},assumptions=['Standard 100-share multiplier; one contract per leg per candidate.','Commission assumption $0.65 per contract per side; eight fills = $5.20 roundtrip; other fees excluded.','Source-observed session calendar; not independently verified exchange calendar.','No early assignment, exercise, dividends, partial fills or intraday quotes modeled.','If zero-salvage enabled, zero-size long bids receive zero value without claiming a fill; residual optionality is discarded. The full $5.20 fee reserve is retained.', 'No cash yield, financing, annualization or specified capital base.','Open or unresolved trades excluded from closed-trade statistics and explicitly counted.','Purpose-selected geometry and inspected history; not OOS confirmation.'])
    (out/'accounting_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps(report,indent=2));print(yearly.to_string())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--zero-salvage-longs',action='store_true');a=p.parse_args();run(a.bundle,a.output_dir,a.zero_salvage_longs)
