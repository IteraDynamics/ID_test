import unittest
import numpy as np
import pandas as pd
from scripts.run_ml_iv_sizing import rebalance,simulate

class SizingTests(unittest.TestCase):
    def test_fees_and_weights_are_self_financing(self):
        s,b,c,t=rebalance(.8,.2,.3,.001)
        self.assertAlmostEqual(s+b+c,1)
        self.assertAlmostEqual(s/(s+b),.3)
        self.assertAlmostEqual(c,.001*t)
        self.assertAlmostEqual(t,abs(s-.8)+abs(b-.2))
    def test_new_weight_cannot_earn_execution_day_return(self):
        f=pd.DataFrame({'date':pd.date_range('2020-01-01',periods=3),
                        'spy_return':[.5,.1,.1],'bil_return':[0.,0.,0.],
                        'iv_signal':[.5,np.nan,np.nan]})
        r=simulate(f,'iv',1,0)
        self.assertAlmostEqual(r['return'].iloc[0],0)
        self.assertAlmostEqual(r['return'].iloc[1],.05)
        self.assertAlmostEqual(r.end_spy_weight.iloc[1],.55/1.05)
        self.assertAlmostEqual(r['return'].iloc[2],(.605+.5)/1.05-1)
    def test_fees_reduce_wealth_and_cash_earns_return(self):
        f=pd.DataFrame({'date':pd.date_range('2020-01-01',periods=3),
                        'spy_return':[0.,0.,0.],'bil_return':[.001,.001,.001],
                        'iv_signal':[0.,1.,0.]})
        a=simulate(f,'iv',1,0);b=simulate(f,'iv',1,10)
        self.assertAlmostEqual(a['return'].iloc[0],.001)
        self.assertLess(np.prod(1+b['return']),np.prod(1+a['return']))
