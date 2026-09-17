import numpy as np
import pandas as pd
from research.core_regime_stability.study import episode_age,transition_target,HORIZONS

def test_episode_age_resets_on_core_change():
 s=pd.Series(['A','A','A','B','B','A'])
 assert episode_age(s).tolist()==[1.,2.,3.,1.,2.,1.]

def test_transition_target_detects_any_change():
 s=pd.Series(['A','A','B','B','C','C'])
 y=transition_target(s,2)
 assert y.iloc[0]==1 and y.iloc[2]==1

def test_transition_target_incomplete_window_is_missing():
 s=pd.Series(['A','A','A','A'])
 y=transition_target(s,2)
 assert y.iloc[0]==0 and np.isnan(y.iloc[-1]) and np.isnan(y.iloc[-2])

def test_horizons_frozen():
 assert HORIZONS==(1,2,3,5,7,10,14)
