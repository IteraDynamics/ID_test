import pandas as pd
from research.latent_transition_geometry.study import first_destination,HORIZONS,_multiclass

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

def test_conditional_destination_excludes_no_transition():
 train=pd.DataFrame({'x':[0.,1.,2.,3.,4.,5.],'destination':['NO_TRANSITION','A','B','A','B','NO_TRANSITION']})
 test=pd.DataFrame({'x':[1.,2.,3.],'destination':['A','B','NO_TRANSITION']})
 score=_multiclass(train,test,['x'],'destination',conditional_transition=True)
 assert score is not None
 assert score['observations']==2
 assert score['classes']==2
