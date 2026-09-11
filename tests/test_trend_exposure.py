import unittest
import numpy as np
import pandas as pd
from research.ml_development import trend_exposure as e

class ExposureTests(unittest.TestCase):
    def test_trade_leverage_and_costs(self):
        h,cash,fees,_=e.trade(np.zeros(2),1.,np.ones(2),np.array([2.,0.]),.001)
        self.assertAlmostEqual(h.sum()+cash,1/1.002)
        self.assertLess(cash,0)
        self.assertEqual(h[1],0)
    def test_cap_and_cash_displacement(self):
        w=np.r_[np.full(12,.5/12),.5]
        self.assertAlmostEqual(e.scaled(w,2)[-1],0)
        self.assertAlmostEqual(e.scaled(w,3).sum(),1.5)
        self.assertAlmostEqual(e.scaled(w,3,True).sum(),1.)
    def test_financing_calendar_and_reconciliation(self):
        dates=pd.to_datetime(['2024-01-04','2024-01-05','2024-01-08','2024-01-09'],utc=True)
        fs={a:pd.DataFrame({'open':100.,'close':100.},index=dates) for a in e.t.ASSETS}
        d=e.simulate(fs,{0:np.r_[np.full(12,.75/12),.25]},2,False,0,.1)
        self.assertAlmostEqual(d.interest.iloc[1],.5*.1*3/365)
        self.assertAlmostEqual(d.nav.iloc[-1],1-d.interest.sum())
        self.assertEqual(d.debt.iloc[-1],0)
    def test_recovery(self):
        dates=pd.Series(pd.date_range('2020-01-01',periods=5))
        r=e.recovery([1.,.9,.95,1.1,1.],dates)
        self.assertEqual(r['longest_recovered_episode_days'],3)
        self.assertEqual(r['terminal_unrecovered_days'],1)

if __name__=='__main__':unittest.main()
