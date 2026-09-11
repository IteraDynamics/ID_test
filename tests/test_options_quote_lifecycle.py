import pandas as pd
import pytest
from scripts.analyze_options_quote_review import select_legs, quote_values


def fixture_frame(date='2020-03-02'):
    return pd.DataFrame([
        dict(date=date,expiration='2020-04-06',type=kind,strike=strike,delta=delta,
             contract_id=cid,bid=bid,ask=ask,bid_size=1,ask_size=1)
        for kind,strike,delta,cid,bid,ask in [
            ('put',90,-.16,'SPY200406P00090000',1.,1.1),
            ('put',88,-.10,'SPY200406P00088000',.4,.5),
            ('call',110,.16,'SPY200406C00110000',1.,1.1),
            ('call',112,.10,'SPY200406C00112000',.4,.5)]])


def test_credit_liquidation_and_bad_quote_no_substitution():
    f=fixture_frame();legs=select_legs(f);q=quote_values(legs)
    assert q['bid_ask_credit']==pytest.approx(1.)
    assert q['midpoint_credit']==pytest.approx(1.2)
    assert q['immediate_liquidation_debit']==pytest.approx(1.4)
    assert q['spread_roundtrip']==pytest.approx(.4)
    f.loc[0,'ask']=.5
    assert not quote_values(select_legs(f))['valid_quotes']


def test_lifecycle_retains_next_session_contracts(tmp_path,monkeypatch):
    pytest.importorskip('pyarrow')
    from scripts import prepare_options_condor_panel as panel
    monkeypatch.setattr(panel,'YEARS',range(2020,2021))
    source=tmp_path/'artifacts/free_options_history_probe';source.mkdir(parents=True)
    f=pd.concat([fixture_frame(),fixture_frame('2020-03-03')],ignore_index=True)
    # Changed next-day deltas must not change contracts chosen on signal day.
    f.loc[f.date=='2020-03-03','delta']=0.
    f.to_parquet(source/'spy_options_2020.parquet',index=False)
    (source/'spy_options_2025.parquet').write_bytes(b'Not to be opened')
    report=panel.run(tmp_path,tmp_path/'output')
    candidates=pd.read_csv(tmp_path/'output/candidate_contracts.csv')
    quotes=pd.read_csv(tmp_path/'output/contract_daily_quotes.csv')
    assert report['selected_months']==1
    assert candidates.iloc[0].potential_execution_date=='2020-03-03'
    assert len(quotes)==8
    assert candidates.iloc[0].short_put=='SPY200406P00090000'
    with pytest.raises(FileExistsError):panel.run(tmp_path,tmp_path/'output')
