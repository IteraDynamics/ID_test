"""Synthetic mechanics, not evidence of market profitability."""
import unittest
import numpy as np
import pandas as pd
from research.ml_development import decision_alignment as d


class DecisionAlignmentTests(unittest.TestCase):
    def test_no_trade_uses_marginal_cost(self):
        current=np.r_[.25,np.zeros(7),.75]
        mu=np.r_[.001,np.zeros(8)]
        w,hold,_=d.optimize(mu,np.zeros((9,9)),current,.001)
        self.assertTrue(hold)
        np.testing.assert_array_equal(w,current)
        self.assertEqual(d.inc.gated(mu[:8],.001).sum(),0)
        _,hold2,_=d.optimize(mu,np.zeros((9,9)),np.r_[np.zeros(8),1.],.001)
        self.assertTrue(hold2)

    def test_known_optimum_and_risk_cap(self):
        mu=np.r_[.02,np.zeros(8)]
        w,hold,_=d.optimize(mu,np.zeros((9,9)),np.r_[np.zeros(8),1.],.001)
        self.assertFalse(hold)
        self.assertAlmostEqual(w[0],.25,places=7)
        cov=np.diag([1.]+[0.]*8)
        w,_,_=d.optimize(mu,cov,np.r_[np.zeros(8),1.],.001)
        self.assertAlmostEqual(w[0],.1,places=6)
        self.assertTrue(d.feasible(w,cov))

    def test_risk_penalty_units(self):
        cov=np.diag([.04]+[0.]*8)
        mu=np.r_[3*(5/252)*.04*.15,np.zeros(8)]
        w,_,_=d.optimize(mu,cov,np.r_[np.zeros(8),1.],0)
        self.assertAlmostEqual(w[0],.15,places=6)

    @staticmethod
    def fixture():
        dates=pd.bdate_range('2016-01-04',periods=800,tz='UTC').delete([270,281,315])
        frames={a:pd.DataFrame({'open':100.,'close':100.,'high':101.,'low':99.,'volume':1000.},index=dates) for a in d.port.ALL_ASSETS}
        f=pd.DataFrame([dict(date=dates[s],asset=a,label_end=dates[s+6],mean=.01 if a=='SPY' else 0.) for s in [300,305,310] for a in d.inc.b.ASSETS])
        return frames,f

    def test_holiday_grid_and_self_financing(self):
        fs,f=self.fixture()
        daily,w,orders=d.simulate(fs,f,'opt:mean',.001)
        # One paid entry, hold flat prices, one paid liquidation.
        self.assertEqual(len(orders),1)
        self.assertEqual(w.no_trade.tolist(),[False,True,True])
        self.assertAlmostEqual(daily.nav.iloc[-1],(1-.001)/(1+.001),places=10)
        self.assertAlmostEqual(daily['return'].add(1).prod(),daily.nav.iloc[-1],places=12)
        self.assertEqual(daily.date.iloc[-1],f.label_end.max())

    def test_next_open_cannot_change_prior_decision(self):
        fs,f=self.fixture()
        _,_,before=d.simulate(fs,f,'opt:mean',.001)
        changed={a:v.copy() for a,v in fs.items()}
        changed['SPY'].iloc[301,changed['SPY'].columns.get_loc('open')]=150.
        _,_,after=d.simulate(changed,f,'opt:mean',.001)
        np.testing.assert_array_equal(before[301],after[301])

    def test_future_label_canary(self):
        fs,f=self.fixture()
        q=d.aligned_panel(fs)
        dates=fs['SPY'].index
        active=q[q.weekly].drop_duplicates('date')
        self.assertTrue((np.diff(dates.get_indexer(active.date))==5).all())
        self.assertTrue((dates.get_indexer(active.label_end)-dates.get_indexer(active.date)==6).all())
        # Mutating an ineligible outcome cannot enter a split's training set.
        q['date']=q['date']+pd.DateOffset(years=2)
        q['label_end']=q['label_end']+pd.DateOffset(years=2)
        tr,va=d.inc.b.split(q,2020)
        copy=q.copy();copy.loc[copy.label_end>=va.date.min(),'target']=1e6
        tr2,_=d.inc.b.split(copy,2020)
        pd.testing.assert_frame_equal(tr,tr2)

    def test_replay_preserves_no_trade(self):
        fs,f=self.fixture()
        _,_,orders=d.simulate(fs,f,'opt:mean',.001)
        daily,_,again=d.simulate(fs,f,'opt:mean',0,replay=orders)
        self.assertEqual(set(orders),set(again))
        self.assertAlmostEqual(daily.nav.iloc[-1],1.)


if __name__=='__main__':unittest.main()
