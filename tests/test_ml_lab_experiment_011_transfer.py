import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import run_ml_lab_experiment_011 as exp11


REPO_ROOT = Path(__file__).resolve().parents[1]


def synthetic_prices(calendar, seed):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.012, len(calendar))))
    return pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": rng.integers(100_000, 1_000_000, len(calendar)),
    }, index=calendar)


class DestinationPanelTests(unittest.TestCase):
    def test_destination_is_equivalent_under_ticker_renaming(self):
        calendar = pd.bdate_range("2023-01-02", periods=530, tz="UTC", name="timestamp")
        source = {
            ticker: synthetic_prices(calendar, i)
            for i, ticker in enumerate(exp11.exp5.UNIVERSE)
        }
        mapping = dict(zip(exp11.exp5.UNIVERSE, exp11.DESTINATION_UNIVERSE, strict=True))
        destination = {mapping[ticker]: frame for ticker, frame in source.items()}
        universe_before = list(exp11.exp5.UNIVERSE)
        original = exp11.exp5._build_panel(source, calendar)
        expected = original.assign(ticker=original["ticker"].map(mapping))
        expected = expected.sort_values(["timestamp", "ticker"]).reset_index(drop=True)

        actual = exp11._build_panel(destination, calendar)

        pd.testing.assert_frame_equal(actual, expected, check_exact=True)
        self.assertEqual(set(actual["ticker"]), set(exp11.DESTINATION_UNIVERSE))
        self.assertLessEqual(actual["target_end_date"].max(), exp11.exp5.LAST_ALLOWED_DATE)
        self.assertEqual(exp11.exp5.UNIVERSE, universe_before)
        pd.testing.assert_frame_equal(
            exp11.exp5._build_panel(source, calendar), original, check_exact=True
        )

    def test_missing_destination_member_fails_closed(self):
        calendar = pd.bdate_range("2020-01-01", periods=150, tz="UTC", name="timestamp")
        frames = {
            ticker: synthetic_prices(calendar, i)
            for i, ticker in enumerate(exp11.DESTINATION_UNIVERSE)
            if ticker != "EWA"
        }
        with self.assertRaisesRegex(KeyError, "EWA"):
            exp11._build_panel(frames, calendar)


class TransferRunnerIntegrationTests(unittest.TestCase):
    def test_real_cli_models_parity_reports_and_replay_on_synthetic_data(self):
        # Exercise the actual runners and frozen estimators, without market data or mocks.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "destination"
            reference = root / "experiment009"
            cache = reference / "source_cache"
            for folder in (source, destination, cache):
                folder.mkdir(parents=True)
            calendar = pd.bdate_range(
                "2018-01-01", "2022-02-28", tz="UTC", name="timestamp"
            )
            for i, ticker in enumerate(exp11.exp5.UNIVERSE):
                synthetic_prices(calendar, i).to_csv(source / f"{ticker}_1D.csv")
            for i, ticker in enumerate(exp11.DESTINATION_UNIVERSE):
                synthetic_prices(calendar, 100 + i).to_csv(destination / f"{ticker}_1D.csv")
            synthetic_prices(calendar, 200).to_csv(source / "VIX_1D.csv")
            rng = np.random.default_rng(300)
            for i, series in enumerate(exp11.exp9.FRED_SERIES):
                pd.DataFrame({
                    "DATE": calendar,
                    series: 2 + i + np.cumsum(rng.normal(0, 0.025, len(calendar))),
                }).to_csv(cache / f"{series}.csv", index=False)

            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            env.pop("PYTHONPATH", None)

            def run(script, *args):
                result = subprocess.run(
                    [sys.executable, str(REPO_ROOT / "scripts" / script), *map(str, args)],
                    cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=300,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)

            print("Synthetic integration: generating Experiment 009 reference", flush=True)
            run("run_ml_lab_experiment_009.py", "--data-dir", source, "--output-dir", reference)
            reports = []
            for name in ("run1", "run2"):
                print(f"Synthetic integration: Experiment 011 {name}", flush=True)
                output = root / name
                report = run(
                    "run_ml_lab_experiment_011.py", "--source-data-dir", source,
                    "--destination-data-dir", destination, "--experiment-009-dir", reference,
                    "--output-dir", output,
                )
                self.assertEqual(report, json.loads((output / "experiment_011_report.json").read_text()))
                self.assertTrue(report["source_parity"]["all_passed"])
                self.assertGreater(report["source_parity"]["checks"], 0)
                self.assertLessEqual(report["source_parity"]["max_abs_score_delta"], exp11.PARITY_TOLERANCE)
                self.assertFalse(report["design"]["destination_training_performed"])
                self.assertFalse(report["design"]["reserved_2025_campaign50_holdout_used"])
                self.assertEqual(report["design"]["source_universe"], exp11.exp5.UNIVERSE)
                self.assertEqual(report["design"]["destination_universe"], list(exp11.DESTINATION_UNIVERSE))
                predictions = pd.read_csv(output / report["artifact_files"]["transfer_predictions"])
                self.assertEqual(set(predictions["ticker"]), set(exp11.DESTINATION_UNIVERSE))
                self.assertEqual(set(predictions["model"]), set(exp11.MODEL_VARIANTS))
                self.assertEqual(set(predictions["memory_scheme"]), set(exp11.MEMORY_SCHEMES))
                self.assertEqual(set(predictions["period"]), {"pre_2022", "post_2022_2024"})
                for filename in report["artifact_files"].values():
                    self.assertGreater(len(pd.read_csv(output / filename)), 0, filename)
                reports.append(report)
            self.assertEqual(reports[0], reports[1])
            for filename in reports[0]["artifact_files"].values():
                self.assertEqual((root / "run1" / filename).read_bytes(), (root / "run2" / filename).read_bytes())


if __name__ == "__main__":
    unittest.main()
