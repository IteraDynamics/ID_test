"""Synthetic mechanics for the trend foundation, not performance claims."""
import unittest
import numpy as np
import pandas as pd
from research.ml_development import trend_foundation as t


class TrendTests(unittest.TestCase):
    def test_relative_trend_cash_and_budget(self):
        price=np.full((400,len(t.ASSETS)),100.)
        w,strength,_=t.target(price,300,True)
        self.assertEqual(w[-1],1.)
        price[:,:-1]=100*np.exp(np.arange(400)[:,None]*.001)
        w,strength,_=t.target(price,300,True)
        np.testing.assert_array_equal(strength,np.ones(12))
        self.assertAlmostEqual(w[:-1].sum(),.75)
        for group in t.GROUPS.values():self.assertAlmostEqual(sum(w[t.ASSETS.index(a)] for a in group),.15)
        price[:,-1]=100*np.exp(np.arange(400)*.002)
        self.assertEqual(t.target(price,300,True)[0][-1],1.)

    def test_future_prices_do_not_change_target(self):
        rng=np.random.default_rng(1);price=100*np.exp(np.cumsum(rng.normal(.0003,.008,(400,len(t.ASSETS))),axis=0))
        price[:,-1]=100*np.exp(np.arange(400)*.0001)
        before=t.target(price,300,True)[0]
        price[301:]*=5
        np.testing.assert_array_equal(before,t.target(price,300,True)[0])

    def test_risk_constraint(self):
        cov=np.eye(13);cov[-1,-1]=0
        w=t.risk_limit(np.full(12,.75/12),cov)
        self.assertLessEqual(w@cov@w,.01+1e-12)
        self.assertAlmostEqual(w.sum(),1.)
        self.assertLess(w[:-1].sum(),.75)

    def test_cost_and_delayed_entry_accounting(self):
        dates=pd.bdate_range('2018-01-01',periods=8,tz='UTC')
        fs={a:pd.DataFrame({'open':100.,'close':100.},index=dates) for a in t.ASSETS}
        w=np.r_[np.full(12,.75/12),.25]
        normal=t.ledger(fs,{0:w},.001,0);late=t.ledger(fs,{0:w},.001,1)
        self.assertEqual(normal.date.tolist(),late.date.tolist())
        self.assertEqual(late['return'].iloc[0],0)
        self.assertAlmostEqual(late.nav.iloc[-1],(1-.001)/(1+.001),places=12)
        self.assertEqual(late.exposure.iloc[-1],0)
        self.assertAlmostEqual(normal.nav.iloc[-1],late.nav.iloc[-1],places=12)


if __name__=='__main__':unittest.main()
