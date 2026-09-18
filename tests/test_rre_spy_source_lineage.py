from pathlib import Path
import pandas as pd
import pytest

from scripts.preflight_rre_spy_source_lineage import EXPECTED_COLUMNS, SourceGateError, load_validate


def write(path:Path,dates):
    rows=[]
    for i,d in enumerate(dates):
        p=100+i
        rows.append(dict(timestamp=d,open=p,high=p+2,low=p-2,close=p+1,volume=1000+i))
    pd.DataFrame(rows,columns=EXPECTED_COLUMNS).to_csv(path,index=False)


def test_load_validate_accepts_clean_source(tmp_path):
    p=tmp_path/"x.csv";write(p,["2020-01-02","2020-01-03"])
    got=load_validate(p)
    assert len(got)==2
    assert list(got.columns)==["open","high","low","close","volume"]


def test_load_validate_rejects_duplicate_timestamp(tmp_path):
    p=tmp_path/"x.csv";write(p,["2020-01-02","2020-01-02"])
    with pytest.raises(SourceGateError,match="DUPLICATE_TIMESTAMP"): load_validate(p)


def test_load_validate_rejects_bad_ohlc(tmp_path):
    p=tmp_path/"x.csv";write(p,["2020-01-02"])
    df=pd.read_csv(p);df.loc[0,"high"]=50;df.to_csv(p,index=False)
    with pytest.raises(SourceGateError,match="INVALID_HIGH"): load_validate(p)
