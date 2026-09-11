import unittest
import numpy as np
from scripts.run_ml_options_variance import predict_fold,summarize

class ForecastTests(unittest.TestCase):
    def test_evaluation_labels_cannot_affect_predictions(self):
        rng=np.random.default_rng(10)
        x=rng.normal(size=(150,4));y=np.exp(x[:,0]+rng.normal(size=150))
        train=np.arange(150)<100;test=~train
        for kind in ['ridge','gbm']:
            a=predict_fold(x,y,train,test,kind)
            changed=y.copy();changed[test]*=100000
            np.testing.assert_array_equal(a,predict_fold(x,changed,train,test,kind))
            self.assertTrue((a>0).all())

    def test_known_perfect_forecast_has_zero_qlike(self):
        import pandas as pd
        f=pd.DataFrame({'year':np.repeat(np.arange(2018,2025),25),'future_variance_5':.001})
        for k in ['rv21','iv_near_raw','ridge_A','ridge_B','gbm_A','gbm_B','gbm_C']:f[k]=.002
        f['ridge_C']=.001
        r=summarize(f)
        self.assertTrue(r['primary_gate_passed'])
        self.assertEqual(next(x['mean_qlike'] for x in r['metrics'] if x['model']=='ridge_C'),0)
