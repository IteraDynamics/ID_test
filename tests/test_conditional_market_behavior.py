import numpy as np
import pandas as pd
from research.conditional_market_behavior.study import HORIZONS,OUTCOMES,STABILITY_HORIZON,add_forward_outcomes

def test_frozen_specification():
 assert HORIZONS==(1,3,5,7,14)
 assert STABILITY_HORIZON==7
 assert OUTCOMES==('log_return','log_variance','downside_semivariance','max_adverse_excursion','max_favorable_excursion','absolute_return','path_efficiency','sign_persistence')

def test_forward_outcomes_use_future_only_and_fail_closed():
 idx=pd.date_range('2020-01-01',periods=24*20,freq='h',tz='UTC');hourly=pd.DataFrame({'close':np.exp(np.arange(len(idx))*.001)},index=idx)
 pidx=pd.date_range('2020-01-02',periods=15,freq='D',tz='UTC');panel=pd.DataFrame(index=pidx);out=add_forward_outcomes(panel,hourly)
 assert out.loc[pidx[0],'log_return_1d']>0
 assert out.loc[pidx[0],'max_adverse_excursion_1d']>0
 assert np.isnan(out.loc[pidx[-1],'log_return_1d'])
 assert out.loc[pidx[0],'outcome_end_14d']==pidx[0]+pd.Timedelta(days=14)

def test_path_efficiency_bounded_when_defined():
 idx=pd.date_range('2020-01-01',periods=24*20,freq='h',tz='UTC');hourly=pd.DataFrame({'close':100+np.sin(np.arange(len(idx))/20)+np.arange(len(idx))*.01},index=idx)
 panel=pd.DataFrame(index=pd.date_range('2020-01-02',periods=15,freq='D',tz='UTC'));out=add_forward_outcomes(panel,hourly);v=out['path_efficiency_7d'].dropna();assert ((v>=0)&(v<=1+1e-12)).all()
