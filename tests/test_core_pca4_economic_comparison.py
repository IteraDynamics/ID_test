import numpy as np
import pandas as pd
from research.core_pca4_economic_comparison.study import (
 COST_BPS,MULTIPLIER_BOUNDS,PCS,RIDGE_ALPHA,RISK_HORIZON_DAYS,TREND_DIRECTION,_metrics,_risk_multiplier,summarize_gate)

def test_frozen_specification():
 assert RISK_HORIZON_DAYS==7 and RIDGE_ALPHA==10.0
 assert MULTIPLIER_BOUNDS==(0.5,1.5) and COST_BPS==(0,5,10,20)
 assert PCS==('pc1','pc2','pc3','pc4')
 assert TREND_DIRECTION=={'TREND_UP':1.0,'TREND_DOWN':-1.0}

def test_risk_multiplier_is_inverse_vol_like_clipped_and_fail_closed():
 p=np.log(np.array([.25,1.,4.,np.nan]));m=_risk_multiplier(p,1.)
 assert np.allclose(m[:3],[1.5,1.,.5]) and m[3]==1.

def test_metrics_charge_returns_geometrically_and_drawdown_nonpositive():
 idx=pd.date_range('2020-01-01',periods=4,freq='D',tz='UTC');r=pd.Series([.1,-.1,.05,0.],index=idx);e=pd.Series([1.,1.,1.,0.],index=idx);t=pd.Series([1.,0.,0.,1.],index=idx);m=_metrics(r,e,t)
 assert m['observations']==4 and m['turnover']==2. and m['max_drawdown']<=0
 assert abs(m['cumulative_return']-((1.1*.9*1.05)-1))<1e-12

def test_gate_requires_all_frozen_rules():
 rows=[];metrics=[]
 for asset in ('BTC','ETH'):
  for tf in (1,4):
   for year in range(2020,2026):
    for bps in COST_BPS:rows.append(dict(asset=asset,timeframe=tf,year=year,cost_bps=bps,sharpe_diff=.1))
    for arm,dd in [('core',-.20),('core_plus_pca4',-.21)]:metrics.append(dict(asset=asset,timeframe=tf,year=year,cost_bps=10,arm=arm,max_drawdown=dd))
 gate=summarize_gate(pd.DataFrame(rows),pd.DataFrame(metrics));assert gate['status']=='PASS' and gate['eligible_folds']==24
 rows[0]['sharpe_diff']=-10.;gate=summarize_gate(pd.DataFrame(rows),pd.DataFrame(metrics));assert gate['status']=='FAIL'
