import pandas as pd
import pytest
from scripts.account_options_condor_panel import prices


def fixture():
    return pd.DataFrame(dict(contract_id=['sp','lp','sc','lc'],bid=[1.,.4,1.,.4],ask=[1.1,.5,1.1,.5],bid_size=[1,1,1,1],ask_size=[1,1,1,1])).set_index('contract_id')


def test_roundtrip_signs_and_midpoint():
    f=fixture();ids=list(f.index)
    assert prices(f,ids,opening=True)==pytest.approx((1.,1.2))
    assert prices(f,ids)==pytest.approx((1.4,1.2))


def test_unsellable_long_zero_recovery_not_short_fill():
    f=fixture();ids=list(f.index);f.loc['lc','bid_size']=0
    assert prices(f,ids) is None
    assert prices(f,ids,zero_salvage=True)==pytest.approx((1.8,1.2))
    f.loc['sc','ask_size']=0
    assert prices(f,ids,zero_salvage=True) is None
    assert prices(f.drop('sc'),ids,zero_salvage=True) is None
