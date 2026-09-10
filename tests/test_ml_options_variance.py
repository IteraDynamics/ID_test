import unittest

import numpy as np
import pandas as pd

from scripts.prepare_ml_options_variance import clean_chain, make_panel, summarize_chain


class OptionsVarianceTests(unittest.TestCase):
    def prices(self):
        dates = pd.bdate_range('2008-01-01', periods=320)
        returns = np.arange(320)/100000
        return pd.DataFrame({'date': dates, 'close': 100*np.exp(np.cumsum(returns))})

    def states(self, p):
        return pd.DataFrame({'date': p.date, 'total_gamma': np.exp(np.arange(len(p))/100),
                             'iv_near': .2, 'iv_far': .22, 'put_call_skew': .03,
                             'iv_term_slope': .02, 'gamma_strike_concentration': .1,
                             'front_gamma_share': .4})

    def test_target_waits_full_session_and_uses_squared_daily_returns(self):
        p = self.prices()
        result = make_panel(p, self.states(p))
        i = 150
        expected = sum((j/100000)**2 for j in range(i+2, i+7))
        self.assertAlmostEqual(result.future_variance_5.iloc[i], expected, places=14)
        self.assertEqual(result.execution_date.iloc[i], p.date.iloc[i+1])
        self.assertEqual(result.target_end.iloc[i], p.date.iloc[i+6])
        self.assertTrue(result.future_variance_5.tail(6).isna().all())

    def test_future_changes_cannot_change_past_features(self):
        p = self.prices()
        s = self.states(p)
        a = make_panel(p, s)
        p.loc[201:, 'close'] *= 3
        s.loc[201:, 'total_gamma'] *= 100
        b = make_panel(p, s)
        cols = ['rv_5', 'rv_21', 'rv_63', 'log_gamma_z252', 'iv_near']
        pd.testing.assert_frame_equal(a.loc[:200, cols], b.loc[:200, cols])
        self.assertNotEqual(a.future_variance_5.iloc[198], b.future_variance_5.iloc[198])

    def test_anchor_target_intervals_do_not_overlap(self):
        p = self.prices()
        r = make_panel(p, self.states(p))
        r = r[r.anchor & r.complete]
        self.assertTrue((r.execution_date.iloc[1:].to_numpy() >= r.target_end.iloc[:-1].to_numpy()).all())

    def chain(self):
        rows = []
        for dte in [30, 60]:
            for kind, sign in [('call', 1), ('put', -1)]:
                for delta, strike in [(.25, 95), (.5, 100)]:
                    rows.append(dict(date='2008-01-02', expiration=pd.Timestamp('2008-01-02')+pd.Timedelta(days=dte),
                                     strike=strike, type=kind, open_interest=100, implied_volatility=.2+(kind=='put')*.04,
                                     gamma=.01, delta=sign*delta, bid=1, ask=1.1))
        return pd.DataFrame(rows)

    def test_invalid_quotes_excluded_and_duplicate_contracts_rejected(self):
        f = self.chain()
        f.loc[0, 'ask'] = .5
        valid, counts = clean_chain(f)
        self.assertEqual(counts['excluded_rows'], 1)
        self.assertEqual(len(valid), 7)
        with self.assertRaises(ValueError):
            clean_chain(pd.concat([f, f.iloc[:1]]))

    def test_delta_features_and_missing_sides(self):
        f, _ = clean_chain(self.chain())
        a = summarize_chain(f).iloc[0]
        self.assertAlmostEqual(a.iv_near, .22)
        self.assertAlmostEqual(a.put_call_skew, .04)
        b = summarize_chain(f[f.type=='call']).iloc[0]
        self.assertTrue(np.isnan(b.iv_near))


if __name__ == '__main__':
    unittest.main()
