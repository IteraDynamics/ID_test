"""Price-dependence diagnostic only; correlations are not effective sample sizes."""
import json
from pathlib import Path
import numpy as np,pandas as pd
p=Path('artifacts/ml_crop_feasibility_20260910')
frames={a:pd.read_csv(p/f'{a}_1D.csv',index_col='timestamp',parse_dates=True) for a in ['CORN','WEAT','SOYB']}
cal=frames['SOYB'].index
for f in frames.values():cal=cal.intersection(f.index)
cal=cal[(cal>='2013-01-01')&(cal<'2025-01-01')]
# Price-only dependence diagnostic, not release-aligned trading or model evaluation.
prices=pd.DataFrame({a:f.reindex(cal)['close'] for a,f in frames.items()})
monthly=prices.resample('ME').last().pct_change().dropna()
r={'status':'DEPENDENCE_DIAGNOSTIC_ONLY','window':['2013-01-01','2024-12-31'],'months':len(monthly),'monthly_return_correlation':monthly.corr().to_dict(),'limitations':['Month-end close returns, not release-aligned open returns.','No WASDE predictors or strategy outcomes evaluated.','Correlated return series are not an effective sample-size estimate.','No spread or dollar-volume inference from adjusted prices times historical volume.']}
(p/'dependence.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
