import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import run_ml_lab_experiment_012 as exp
from test_ml_lab_experiment_011_transfer import synthetic_prices


def manifest_for(root):
    manifest = {"synthetic": True, "last_allowed_date": "2024-12-31", "inputs": []}
    for name in exp.INPUT_PATHS:
        data = (root / name).read_bytes()
        manifest["inputs"].append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class InputTests(unittest.TestCase):
    def test_missing_changed_and_wrong_mode_inputs_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in exp.INPUT_PATHS:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic fixture\n")
            manifest = manifest_for(root)
            exp.verify_inputs(root, manifest, synthetic=True)
            with self.assertRaisesRegex(ValueError, "MODE_MISMATCH"):
                exp.verify_inputs(root, manifest, synthetic=False)
            path = root / exp.INPUT_PATHS[0]
            path.write_text("changed data\n")
            with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
                exp.verify_inputs(root, manifest, synthetic=True)
            path.unlink()
            with self.assertRaisesRegex(ValueError, "MISSING_INPUT"):
                exp.verify_inputs(root, manifest, synthetic=True)


class FoldIntegrityTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(12)
        stamps = pd.bdate_range("2018-01-01", periods=80, tz="UTC").repeat(14)
        self.train = pd.DataFrame(rng.normal(size=(len(stamps), 22)), columns=exp.FEATURES)
        self.train["timestamp"] = stamps
        self.train["target_end_date"] = stamps + pd.Timedelta(days=28)
        self.train["target_rank"] = rng.uniform(size=len(stamps))
        self.test = self.train.iloc[:14].copy()
        self.test["timestamp"] = pd.Timestamp("2020-01-02", tz="UTC")
        self.test["target_end_date"] = pd.Timestamp("2020-01-30", tz="UTC")

    def test_exact_frozen_feature_order_and_training_only_scaling(self):
        expected = (
            "ret_5d_xrank", "ret_20d_xrank", "ret_60d_xrank", "ret_120d_xrank",
            "vol_20d_xrank", "vol_60d_xrank", "vol_ratio_20_60_xrank", "distance_sma_20_xrank",
            "distance_sma_120_xrank", "drawdown_120_xrank", "range_position_120_xrank", "volume_z_60_xrank",
            "rate2_pct252", "curve_10y2y_pct252", "rate2_chg20", "vix_pct252",
            "curve_10y2y_pct252__x__vol_60d_xrank", "vix_pct252__x__vol_60d_xrank",
            "curve_10y2y_pct252__x__ret_120d_xrank", "rate2_pct252__x__vol_60d_xrank",
            "rate2_pct252__x__ret_120d_xrank", "rate2_chg20__x__ret_120d_xrank",
        )
        self.assertEqual(exp.FEATURES, expected)
        fitted, _ = exp.fit_fold(self.train[self.train.columns[::-1]], self.test)
        changed = self.test.copy()
        changed[list(expected)] += 1_000_000
        second, _ = exp.fit_fold(self.train, changed)
        self.assertEqual(tuple(fitted.feature_names_in_), expected)
        np.testing.assert_allclose(fitted.named_steps["scale"].mean_, self.train[list(expected)].mean().to_numpy())
        np.testing.assert_array_equal(fitted.named_steps["scale"].mean_, second.named_steps["scale"].mean_)
        np.testing.assert_array_equal(fitted.named_steps["model"].coef_, second.named_steps["model"].coef_)

    def test_embargo_and_target_cutoff_fail(self):
        leaky = self.train.copy()
        leaky.loc[0, "target_end_date"] = self.test["timestamp"].min()
        with self.assertRaisesRegex(ValueError, "EMBARGO"):
            exp.fit_fold(leaky, self.test)
        future = self.test.copy()
        future["target_end_date"] = pd.Timestamp("2025-01-02", tz="UTC")
        with self.assertRaisesRegex(ValueError, "CUTOFF"):
            exp.fit_fold(self.train, future)

    def test_trailing_window_and_strict_end_embargo(self):
        panel = self.train.copy()
        start = pd.Timestamp("2021-03-01", tz="UTC")
        selected = exp.exp9._training_slice(panel, start, 3)
        self.assertTrue((selected.timestamp >= start - pd.DateOffset(years=3)).all())
        self.assertTrue((selected.target_end_date < start).all())
        self.assertLess(len(selected), len(panel))


class ReferenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.expected = pd.DataFrame({
            "timestamp": [pd.Timestamp("2020-01-02", tz="UTC")] * 14,
            "ticker": exp.exp5.UNIVERSE, "test_year": 2020, "memory_scheme": "expanding",
            "model": "price_ridge", "target_raw": np.arange(14, dtype=float),
            "target_rank": np.arange(1, 15) / 14,
            "target_end_date": pd.Timestamp("2020-01-30", tz="UTC"),
        })
        self.saved = self.expected.drop(columns="target_end_date").assign(score=np.arange(14, dtype=float))
        self.anchor = exp.anchor_metrics(self.saved)

    def test_unchanged_reference_passes(self):
        _, _, parity = exp.verify_references(self.expected, self.saved, self.anchor)
        self.assertTrue(parity.passed.all())

    def test_missing_extra_and_duplicate_prediction_rows_fail(self):
        for bad in (self.saved.iloc[:-1], pd.concat([self.saved, self.saved.iloc[:1]]),
                    pd.concat([self.saved, self.saved.iloc[:1].assign(ticker="UNEXPECTED")])):
            with self.subTest(rows=len(bad)):
                with self.assertRaisesRegex(ValueError, "(ROW_KEY_MISMATCH|DUPLICATE_KEYS)"):
                    exp.verify_references(self.expected, bad, self.anchor)

    def test_target_metric_and_duplicate_anchor_failures(self):
        bad = self.saved.copy()
        bad.loc[0, "target_raw"] += 0.1
        with self.assertRaisesRegex(ValueError, "TARGET_PARITY"):
            exp.verify_references(self.expected, bad, self.anchor)
        bad = self.anchor.copy()
        bad.loc[0, "rank_ic"] -= 0.1
        with self.assertRaisesRegex(ValueError, "METRIC_PARITY"):
            exp.verify_references(self.expected, self.saved, bad)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_KEYS"):
            exp.verify_references(self.expected, self.saved, pd.concat([self.anchor, self.anchor]))

    def test_changed_scores_and_nonfinite_values_fail(self):
        bad = self.saved.copy()
        bad["score"] *= -1
        with self.assertRaisesRegex(ValueError, "METRIC_PARITY"):
            exp.verify_references(self.expected, bad, self.anchor)
        bad.loc[0, "score"] = np.inf
        with self.assertRaisesRegex(ValueError, "NONFINITE"):
            exp.verify_references(self.expected, bad, self.anchor)


class DispositionTests(unittest.TestCase):
    def inputs(self):
        models, comparisons, annual = [], [], []
        for memory in exp.MEMORIES:
            for period in ("all",) + exp.PERIODS:
                for model in (exp.MODEL, "macro_gbm"):
                    models.append({"memory_scheme": memory, "period": period, "model": model,
                                   "mean_rank_ic": 0.1, "mean_top_minus_bottom_raw_target": 0.1})
                comparisons.append({"memory_scheme": memory, "period": period,
                                    "comparison": f"{exp.MODEL}_minus_price_ridge",
                                    "mean_rank_ic": 0.01, "mean_top_minus_bottom_raw_target": 0.01})
            for year in (2021, 2022):
                annual.append({"memory_scheme": memory, "test_year": year,
                               "comparison": f"{exp.MODEL}_minus_price_ridge", "mean_rank_ic": 0.01})
        return pd.DataFrame(models), pd.DataFrame(comparisons), pd.DataFrame(annual)

    def test_all_branches_and_primary_precedence(self):
        m, c, a = self.inputs()
        self.assertEqual(exp.classify(m, c, a)["classification"], "EXPLORATORY_COMPACT_REPRESENTATION_SUPPORTED")
        c.loc[(c.memory_scheme == "expanding") & (c.period == "pre_2022"), "mean_rank_ic"] = -0.01
        self.assertEqual(exp.classify(m, c, a)["classification"], "PARTIAL_OR_MEMORY_DEPENDENT_SIMPLIFICATION")
        c.loc[(c.memory_scheme == "trailing_3y") & (c.period == "post_2022_2024"), "mean_rank_ic"] = 0.0
        self.assertEqual(exp.classify(m, c, a)["classification"], "NO_STABLE_PRIMARY_SIMPLIFICATION")

    def test_strict_majority_absolute_performance_and_gbm_matching(self):
        m, c, a = self.inputs()
        a.loc[(a.memory_scheme == "trailing_3y") & (a.test_year == 2021), "mean_rank_ic"] = 0.0
        self.assertEqual(exp.classify(m, c, a)["classification"], "NO_STABLE_PRIMARY_SIMPLIFICATION")
        m, c, a = self.inputs()
        m.loc[(m.memory_scheme == "trailing_3y") & (m.period == "pre_2022") & (m.model == exp.MODEL), "mean_rank_ic"] = 0.0
        self.assertEqual(exp.classify(m, c, a)["classification"], "NO_STABLE_PRIMARY_SIMPLIFICATION")
        m, c, a = self.inputs()
        m.loc[(m.period == "all") & (m.model == "macro_gbm"), "mean_rank_ic"] = 0.2
        self.assertEqual(exp.classify(m, c, a)["classification"], "PARTIAL_OR_MEMORY_DEPENDENT_SIMPLIFICATION")


class SyntheticRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        data = cls.root / "data"
        cache = cls.root / exp.REF_DIR / "source_cache"
        data.mkdir()
        cache.mkdir(parents=True)
        calendar = pd.bdate_range("2018-01-01", "2022-02-28", tz="UTC", name="timestamp")
        for i, ticker in enumerate(exp.exp5.UNIVERSE):
            synthetic_prices(calendar, i).to_csv(data / f"{ticker}_1D.csv")
        synthetic_prices(calendar, 200).to_csv(data / "VIX_1D.csv")
        rng = np.random.default_rng(300)
        for i, series in enumerate(exp.exp9.FRED_SERIES):
            pd.DataFrame({"DATE": calendar, series: 2 + i + np.cumsum(rng.normal(0, .025, len(calendar)))})\
                .to_csv(cache / f"{series}.csv", index=False)
        print("Synthetic 012: generating actual Experiment 009 reference artifacts", flush=True)
        result = subprocess.run([sys.executable, str(exp.SCRIPTS_DIR / "run_ml_lab_experiment_009.py"),
                                 "--data-dir", str(data), "--output-dir", str(cls.root / exp.REF_DIR)],
                                capture_output=True, text=True, timeout=300)
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stderr)
        cls.manifest = manifest_for(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def command(self, output):
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        env.pop("PYTHONPATH", None)
        return subprocess.run([
            sys.executable, str(exp.SCRIPTS_DIR / "run_ml_lab_experiment_012.py"),
            "--synthetic-input-root", str(self.root), "--synthetic-manifest", str(self.manifest),
            "--output-dir", str(output),
        ], cwd=exp.ROOT, env=env, text=True, capture_output=True, timeout=300)

    def test_complete_cli_and_identical_replay(self):
        reports = []
        for name in ("run1", "run2"):
            print(f"Synthetic 012: full runner {name}", flush=True)
            output = self.root / name
            result = self.command(output)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            reports.append(report)
            self.assertTrue(report["synthetic"])
            self.assertTrue(report["reference_parity"]["all_passed"])
            self.assertFalse(report["design"]["baselines_refitted"])
            self.assertFalse(report["design"]["reserved_2025_holdout_used"])
            self.assertEqual(report["design"]["feature_count"], 22)
            self.assertEqual(set(report["components"]), set(exp.MEMORIES))
            self.assertEqual(json.loads((output / "experiment_012_report.json").read_text()), report)
            for key, filename in report["artifact_files"].items():
                self.assertGreater(len(pd.read_csv(output / filename)), 0, filename)
                self.assertEqual(exp.sha256(output / filename), report["artifact_sha256"][key])
        self.assertEqual(reports[0], reports[1])
        for filename in reports[0]["artifact_files"].values():
            self.assertEqual((self.root / "run1" / filename).read_bytes(), (self.root / "run2" / filename).read_bytes())
        self.assertNotEqual(self.command(self.root / "run1").returncode, 0)

    def test_future_source_and_macro_rows_excluded_before_panel_computation(self):
        before, _, _ = exp.load_panel(self.root)
        source = self.root / "data/RSP_1D.csv"
        macro = self.root / exp.REF_DIR / "experiment_009_macro_state.csv"
        original = {path: path.read_bytes() for path in (source, macro)}
        try:
            for path in (source, macro):
                frame = pd.read_csv(path)
                tail = frame.iloc[-1:].copy()
                tail["timestamp"] = "2025-01-02 00:00:00+00:00"
                for column in tail.columns.difference(["timestamp"]):
                    tail[column] = 1e12
                pd.concat([frame, tail]).to_csv(path, index=False)
            after, _, _ = exp.load_panel(self.root)
            pd.testing.assert_frame_equal(before, after, check_exact=False, atol=1e-10, rtol=0)
            self.assertLessEqual(after.target_end_date.max(), exp.exp5.LAST_ALLOWED_DATE)
        finally:
            for path, content in original.items():
                path.write_bytes(content)

    def test_input_failure_publishes_no_success_report(self):
        original = self.manifest.read_bytes()
        try:
            manifest = json.loads(original)
            manifest["inputs"][0]["sha256"] = "0" * 64
            self.manifest.write_text(json.dumps(manifest))
            output = self.root / "failed"
            result = self.command(output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("INPUT_HASH_MISMATCH", result.stderr)
            self.assertFalse(output.exists())
        finally:
            self.manifest.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
