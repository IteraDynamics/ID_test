import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts import run_ml_lab_experiment_011 as exp11


class MacroStateLoadingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "macro.csv"
        self.dates = pd.DatetimeIndex(
            ["2020-01-03", "2020-01-02"], tz="UTC", name="timestamp"
        )
        self.macro = pd.DataFrame(
            {name: [0.25, 0.75] for name in exp11.exp9.MACRO_STATES},
            index=self.dates,
        )
        self.panel = pd.DataFrame({
            "timestamp": [self.dates[1], self.dates[0], self.dates[1]],
            "ticker": ["AAA", "AAA", "BBB"],
            **{name: [0.1, 0.2, 0.3] for name in exp11.exp9.PRICE_FEATURES},
        })

    def test_csv_round_trip_preserves_macro_alignment_and_interactions(self):
        self.macro.to_csv(self.path)
        loaded = exp11._load_macro_state(self.path)
        pd.testing.assert_frame_equal(loaded, self.macro, check_index_type=False)
        expected = exp11.exp9._augment_panel(self.panel, self.macro)
        actual = exp11.exp9._augment_panel(self.panel, loaded)
        pd.testing.assert_frame_equal(actual, expected)

    def test_duplicate_macro_dates_still_fail_closed(self):
        pd.concat([self.macro, self.macro.iloc[:1]]).to_csv(self.path)
        loaded = exp11._load_macro_state(self.path)
        with self.assertRaises(pd.errors.MergeError):
            exp11.exp9._augment_panel(self.panel, loaded)


if __name__ == "__main__":
    unittest.main()
