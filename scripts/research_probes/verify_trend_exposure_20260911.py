"""Independent holdings/debit replay of seven primary paths; run from repo root."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from research.ml_development import trend_foundation as t


def run(root, energy, crop, output):
    fs,_,_=t.inputs(root,energy,crop)
    schedules,_=t.schedules(fs);schedule=schedules['trend']
    original=pd.read_csv(output/'daily_ledger.csv')
    dates=fs['SPY'].index;opens=np.column_stack([fs[a].open for a in t.ASSETS]);closes=np.column_stack([fs[a].close for a in t.ASSETS])
    deltas={}
    for label,k,cap in [('1x',1,False),('1.5x',1.5,False),('2x',2,False),('2.5x',2.5,False),('3x',3,False),('4x',4,False),('2x_cashcap',2,True)]:
        cash=1.;units=np.zeros(13);nav=[];interest_total=0.
        for i in range(min(schedule)+1,len(dates)):
            if i>min(schedule)+1:
                interest=max(-cash,0)*.08*(dates[i]-dates[i-1]).days/365
                cash-=interest;interest_total+=interest
            values=units*opens[i];equity=cash+values.sum()
            if values.sum()>0:assert equity/values.sum()>=.30
            weights=None
            if i==len(dates)-1:weights=np.zeros(13)
            elif i-1 in schedule:
                risky=schedule[i-1][:-1]*k
                if cap:risky=risky/max(1.,risky.sum())
                weights=np.r_[risky,max(0.,1-risky.sum())]
            if weights is not None:
                net=brentq(lambda x:x+.001*np.abs(weights*x-values).sum()-equity,0.,equity,xtol=1e-14)
                target=weights*net
                cash-=float((target-values).sum()+.001*np.abs(target-values).sum())
                units=target/opens[i]
            nav.append(float(cash+(units*closes[i]).sum()))
        g=original[(original.scenario=='primary8')&(original.level==label)]
        delta=float(np.max(np.abs(np.array(nav)-g.nav.to_numpy())))
        assert delta<1e-10,(label,delta)
        assert abs(interest_total-g.interest.sum())<1e-10
        assert np.max(np.abs(units))==0
        deltas[label]=delta
    report=dict(independent_primary_paths=7,solver='scipy brentq',max_nav_deltas=deltas,financing_totals_match=True,terminal_positions_zero=True)
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    for n in ['etf-root','energy-zip','crop-zip','output-dir']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.etf_root,a.energy_zip,a.crop_zip,a.output_dir)
