import numpy as np
import pandas as pd
from research.latent_state_trajectories.study import TrajectoryModel, PCS, TRAJECTORY
from research.multidimensional_regimes.study import FEATURES

def frame(n=320):
    idx=pd.date_range('2018-01-01',periods=n,freq='D',tz='UTC')
    x=np.arange(n,dtype=float)
    d=pd.DataFrame(index=idx)
    d['strength']=np.sin(x/19); d['momentum']=np.cos(x/23); d['log_atr']=-5+.2*np.sin(x/31); d['atr_accel']=.1*np.cos(x/13); d['efficiency']=.2+.1*np.sin(x/17)
    d['core_label']=np.where((x.astype(int)//40)%2==0,'TREND_UP','VOL_COMPRESSION')
    return d

def test_trajectory_transform_is_deterministic():
    f=frame(); m=TrajectoryModel().fit(f.iloc[:280]); a=m.transform(f.iloc[280:]); b=m.transform(f.iloc[280:])
    np.testing.assert_allclose(a[PCS+TRAJECTORY].to_numpy(),b[PCS+TRAJECTORY].to_numpy(),equal_nan=True)

def test_future_mutation_does_not_change_past_trajectory():
    f=frame(); m=TrajectoryModel().fit(f.iloc[:280]); a=m.transform(f.iloc[280:].copy())
    g=f.iloc[280:].copy(); g.loc[g.index[-1],FEATURES]=[9,9,-1,9,.99]; b=m.transform(g)
    np.testing.assert_allclose(a.iloc[:-1][PCS+TRAJECTORY].to_numpy(),b.iloc[:-1][PCS+TRAJECTORY].to_numpy(),equal_nan=True)

def test_required_trajectory_columns_exist():
    f=frame(); out=TrajectoryModel().fit(f.iloc[:280]).transform(f.iloc[280:])
    assert set(PCS+TRAJECTORY).issubset(out.columns)
