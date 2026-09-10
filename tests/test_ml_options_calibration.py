import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.calibrate_ml_options_variance import run


class CalibrationTests(unittest.TestCase):
    def write_zip(self, path, poison=False):
        rng = np.random.default_rng(2)
        dates = pd.bdate_range('2008-01-01', '2024-12-20')[::5]
        n = len(dates)
        f = pd.DataFrame({'source_date': dates.strftime('%Y-%m-%d'),
                          'target_end': (dates+pd.offsets.BDay(6)).strftime('%Y-%m-%d')})
        for col in ['rv_5','rv_21','rv_63','iv_near','iv_far','put_call_skew',
                    'gamma_strike_concentration','front_gamma_share','log_gamma_z252']:
            f[col] = np.exp(rng.normal(-2,.4,n))
        f['return_21'] = rng.normal(0,.03,n)
        f['iv_term_slope'] = f.iv_far-f.iv_near
        f['future_variance_5'] = np.exp(rng.normal(-8,1,n))
        if poison:
            f.loc[f.source_date >= '2018-01-01','future_variance_5'] = 1e20
        data = f.to_csv(index=False).encode()
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('options_variance_anchors.csv',data)
            z.writestr('options_variance_preparation.json',json.dumps({'artifact_sha256':{
                'options_variance_anchors.csv':hashlib.sha256(data).hexdigest()}}))

    def test_real_evaluation_labels_cannot_change_calibration(self):
        with tempfile.TemporaryDirectory() as td:
            a,b = Path(td)/'a.zip',Path(td)/'b.zip'
            self.write_zip(a); self.write_zip(b,poison=True)
            first, second = run(a,repetitions=2),run(b,repetitions=2)
            self.assertEqual(first['scenarios'],second['scenarios'])
            self.assertEqual(first['training_log_residual_sd'],second['training_log_residual_sd'])
            self.assertEqual(first,run(a,repetitions=2))

    def test_modified_input_fails_hash_check(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('options_variance_anchors.csv','wrong')
                z.writestr('options_variance_preparation.json',json.dumps({'artifact_sha256':{'options_variance_anchors.csv':'wrong'}}))
            with self.assertRaises(ValueError):run(p,repetitions=2)
