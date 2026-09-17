import numpy as np
import pandas as pd
from research.latent_transition_geometry.study import first_destination,HORIZONS

def test_first_destination_uses_first_change():
 s=pd.Series(['A','A','B','C','C'])
 out=first_destination(s,3)
 assert out.iloc[0]=='B' and out.iloc[1]=='B'

def test_first_destination_marks_incomplete_horizon_missing():
 s=pd.Series(['A','A','B','B','B'])
 out=first_destination(s,2)
 assert out.iloc[0]=='B'
 assert out.iloc[-1] is None and out.iloc[-2] is None

def test_horizons_are_frozen():
 assert HORIZONS==(1,2,3,5,7,10,14)
