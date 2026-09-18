from pathlib import Path
import pandas as pd
import pytest
from scripts.preflight_rre_daily_source_lineage import EXPECTED_COLUMNS, GateError, load

def write(path,dates):
    rows=[]
    for i,d in enumerate(dates):
        p=100+i
        rows.append(dict(timestamp=d,open=p,high=p+2,low=p-2,close=p+1,volume=1000+i))
    pd.DataFrame(rows,columns=EXPECTED_COLUMNS).to_csv(path,index=False)

def test_load_clean(tmp_path):
    p=tmp_path/"x.csv"; write(p,["2020-01-02","2020-01-03"])
    assert len(load(p))==2

def test_load_duplicate(tmp_path):
    p=tmp_path/"x.csv"; write(p,["2020-01-02","2020-01-02"])
    with pytest.raises(GateError,match="DUPLICATE"): load(p)

def test_load_bad_high(tmp_path):
    p=tmp_path/"x.csv"; write(p,["2020-01-02"])
    df=pd.read_csv(p);df.loc[0,"high"]=50;df.to_csv(p,index=False)
    with pytest.raises(GateError,match="HIGH"): load(p)
