"""Replay fixed original trade slots at alternative entry weights, spot only."""
from __future__ import annotations
import numpy as np
import pandas as pd
from research.crypto_reversal.experiment import Run,HOUR


def replay(frame,original,weights,cost_bps):
    grid=original.curve.index
    data=frame.reindex(grid)
    entries={pd.Timestamp(t['entry_time']):t for t in original.trades}
    exits={pd.Timestamp(t['exit_time']):t for t in original.trades}
    if set(weights)!=set(entries):raise ValueError('Weight map must match original trade slots')
    if any(not np.isfinite(w) or not 0<=w<=1 for w in weights.values()):
        raise ValueError('Spot weight must be in [0,1]')
    cost=cost_bps/10000
    if not 0<=cost<1:raise ValueError('Invalid costs')
    nav=np.ones(len(grid));exposure=np.zeros(len(grid));fees=np.zeros(len(grid));notional=np.zeros(len(grid))
    cash_delta=np.zeros(len(grid));unit_delta=np.zeros(len(grid));marks=np.zeros(len(grid))
    cash=1.;units=0.;mark=float(data.open.iloc[0]);active=None;trades=[];fills=[]
    max_error=0.
    for i,t in enumerate(grid):
        j=min(i+1,len(grid)-1);terminal=i==len(grid)-1
        old_nav=cash+units*mark;old_units=units
        opening=float(data.open.iloc[i]) if pd.notna(data.open.iloc[i]) else mark
        fee_here=0.
        if t in exits and active is not None:
            if pd.isna(data.open.iloc[i]):raise ValueError('Original exit not observable')
            gross=units*opening;fee=gross*cost
            cash+=gross-fee;cash_delta[j]+=gross-fee;unit_delta[j]-=units
            notional[j]+=gross;fee_here+=fee
            fills.append(dict(time=str(t),side='sell',units=units,price=opening,fee=fee))
            trades.append(dict(entry_time=active['entry_time'],exit_time=str(t),
                weight=active['weight'],gross_return=opening/active['entry_price']-1,
                net_return=cash/active['start_equity']-1,net_pnl=cash-active['start_equity']))
            units=0.;active=None
        if t in entries and weights[t]>0:
            if active is not None or pd.isna(data.open.iloc[i]):raise ValueError('Invalid entry slot')
            before=cash;weight=weights[t]
            units=before*weight/(opening*(1+cost));gross=units*opening;fee=gross*cost
            cash-=gross+fee;cash_delta[j]-=gross+fee;unit_delta[j]+=units
            notional[j]+=gross;fee_here+=fee
            active=dict(entry_time=str(t),entry_price=opening,start_equity=before,weight=weight)
            fills.append(dict(time=str(t),side='buy',units=units,price=opening,fee=fee))
        closing=opening if terminal else float(data.close.iloc[i]) if pd.notna(data.close.iloc[i]) else mark
        value=cash+units*closing
        pnl=old_units*(opening-mark)+units*(closing-opening)
        max_error=max(max_error,abs(value-old_nav-pnl+fee_here)/max(old_nav,1e-30))
        if value<=0 or cash < -1e-10 or max_error>1e-10:raise ValueError('Accounting error')
        nav[j]=value;exposure[j]=units*closing/value;fees[j]+=fee_here;marks[j]=closing;mark=closing
    independent=1+np.cumsum(cash_delta)+np.cumsum(unit_delta)*marks
    replay_error=float(np.max(abs(independent-nav)/nav))
    if replay_error>1e-9 or units!=0:raise ValueError('Fill replay or liquidation error')
    curve=pd.DataFrame(dict(nav=nav,exposure=exposure,fees=fees,
        turnover=notional/np.r_[1.,nav[:-1]]),index=grid)
    return Run(curve,trades,fills,dict(accounting_max_error=max_error,replay_max_error=replay_error,
        original_trade_slots=len(original.trades),positive_weight_trades=len(trades)))
