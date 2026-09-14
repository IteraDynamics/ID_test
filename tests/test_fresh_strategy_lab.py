"""Synthetic mechanics only: these tests say nothing about market profitability."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from research.fresh_lab.data import SYMBOLS, digest, load_panel, write_json
from research.fresh_lab.engine import Scenario, carry, simulate
from research.fresh_lab.metrics import metrics, pareto
from research.fresh_lab.signals import held_events, registry, targets


FREE = Scenario("free", 0, financing_rate=0, borrow_rate=0)


def panel_from_prices(open_prices, close_prices, dividends=None):
    dates = pd.bdate_range("2020-01-01", periods=len(close_prices))
    o = pd.DataFrame({"SPY": open_prices}, index=dates, dtype=float)
    c = pd.DataFrame({"SPY": close_prices}, index=dates, dtype=float)
    d = pd.DataFrame({"SPY": dividends or [0] * len(dates)}, index=dates, dtype=float)
    return finish_panel(o, c, d)


def finish_panel(o, c, d):
    r = (c + d) / c.shift(1) - 1
    return {"Open": o, "Close": c, "Dividends": d, "total_return": r,
            "total_index": (1 + r.fillna(0)).cumprod(),
            "night_return": (o + d) / c.shift(1) - 1, "day_return": c / o - 1}


def synthetic_panel(n=420):
    rng = np.random.default_rng(20260914)
    dates = pd.bdate_range("2004-01-02", periods=n)
    market = rng.normal(0.0002, .011, (n, 1))
    movements = market + rng.normal(0, .006, (n, len(SYMBOLS)))
    c = pd.DataFrame(100 * np.exp(np.cumsum(movements, axis=0)),
                     index=dates, columns=SYMBOLS)
    previous = c.shift(1).fillna(100)
    o = previous * np.exp(rng.normal(0, .004, c.shape))
    return finish_panel(o, c, c * 0)


class FreshLabTests(unittest.TestCase):
    def test_exact_entry_exit_cost_and_cash_identity(self):
        panel = panel_from_prices([100] * 4, [100] * 4)
        target = panel["Close"] * 0 + 1
        ledger = simulate(panel, target, "hold", 1,
                          Scenario("one_percent", 100, financing_rate=0, borrow_rate=0),
                          str(target.index[1].date()))
        self.assertAlmostEqual(ledger["nav"].iloc[-1], .98, places=12)
        self.assertAlmostEqual(ledger["turnover"].iloc[0], 1)
        self.assertEqual(ledger["orders"].sum(), 2)
        np.testing.assert_allclose(ledger["cash"] + ledger["holdings_value"], ledger["nav"])
        self.assertEqual(ledger["holdings_value"].iloc[-1], 0)
        self.assertLess(ledger["accounting_error"].abs().max(), 1e-12)

    def test_dividend_credited_to_overnight_holder_and_short_pays(self):
        panel = panel_from_prices([100, 100, 99, 99], [100, 100, 99, 99], [0, 0, 1, 0])
        target = panel["Close"] * 0 + 1
        start = str(target.index[1].date())
        night = simulate(panel, target, "night", 1, FREE, start)
        day = simulate(panel, target, "day", 1, FREE, start)
        short = simulate(panel, -target, "full", 1, FREE, start)
        self.assertAlmostEqual(night["dividend_cash"].sum(), .01)
        self.assertEqual(day["dividend_cash"].sum(), 0)
        self.assertAlmostEqual(short["dividend_cash"].sum(), -.01)
        for ledger in (night, day, short):
            self.assertAlmostEqual(ledger["nav"].iloc[-1], 1, places=12)

    def test_quantities_fixed_before_fill_and_current_signal_not_used(self):
        panel = panel_from_prices([100, 200, 200, 200], [100, 200, 200, 200])
        target = panel["Close"] * 0 + 1
        start = str(target.index[1].date())
        first = simulate(panel, target, "full", 1, FREE, start)
        altered = target.copy()
        altered.iloc[1:] = 0
        second = simulate(panel, altered, "full", 1, FREE, start)
        pd.testing.assert_series_equal(first.iloc[0], second.iloc[0])
        self.assertAlmostEqual(first["turnover"].iloc[0], 2)
        self.assertAlmostEqual(first["gross_open"].iloc[0], 2)

    def test_extra_session_delay_changes_information_boundary(self):
        panel = panel_from_prices([100] * 5, [100] * 5)
        target = panel["Close"] * 0
        target.iloc[1] = 1
        start = str(target.index[2].date())
        normal = simulate(panel, target, "full", 1, FREE, start)
        delayed = simulate(panel, target, "full", 1,
                            Scenario("delay", 0, delay=1, financing_rate=0, borrow_rate=0), start)
        self.assertEqual(normal["gross_open"].iloc[0], 1)
        self.assertEqual(delayed["gross_open"].iloc[0], 0)
        self.assertEqual(delayed["gross_open"].iloc[1], 1)

    def test_initial_loss_and_open_drawdown_are_counted(self):
        panel = panel_from_prices([100, 100, 80, 100], [100, 100, 100, 100])
        target = panel["Close"] * 0 + 1
        ledger = simulate(panel, target, "hold", 1, FREE, str(target.index[1].date()))
        result = metrics(ledger)
        self.assertAlmostEqual(result["max_drawdown"], .2)
        self.assertAlmostEqual(result["max_close_drawdown"], 0)
        panel = panel_from_prices([100, 100, 90, 90], [100, 90, 90, 90])
        ledger = simulate(panel, target, "hold", 1, FREE, str(target.index[1].date()))
        self.assertAlmostEqual(metrics(ledger)["max_drawdown"], .1)

    def test_financing_segregates_short_proceeds(self):
        interest, cost = carry(1, np.array([.02, -.02]), np.array([100., 100.]), 1,
                               Scenario("carry", 0, financing_rate=.06, borrow_rate=.03))
        self.assertEqual(interest, 0)
        self.assertAlmostEqual(cost, .12)  # $1 loan + $2 short borrow

    def test_event_holding_has_no_repeat_trigger_extension(self):
        flags = pd.DataFrame({"x": [True, True, True, False, True, False]})
        held = held_events(flags, 3)["x"].tolist()
        self.assertEqual(held, [1, 1, 1, 0, 1, 1])

    def test_registry_and_signal_exposure_constraints(self):
        panel = synthetic_panel()
        candidates = registry()
        self.assertEqual(len(candidates), 31)
        self.assertEqual(len({c.name for c in candidates}), 31)
        self.assertEqual(sum(not c.benchmark for c in candidates), 25)
        for candidate in candidates:
            weights = targets(panel, candidate)
            self.assertTrue(np.isfinite(weights.to_numpy()).all())
            self.assertLessEqual(weights.abs().sum(axis=1).max(), 1 + 1e-12)
            if candidate.family == "sector_residual":
                self.assertLess(weights.sum(axis=1).abs().max(), 1e-12)

    def test_future_perturbation_does_not_change_any_earlier_signal(self):
        panel = synthetic_panel()
        cutoff = 300
        o, c, d = (panel[k].copy() for k in ("Open", "Close", "Dividends"))
        o.iloc[cutoff:] *= 2
        c.iloc[cutoff:] *= 3
        changed = finish_panel(o, c, d)
        for candidate in registry():
            original = targets(panel, candidate)
            modified = targets(changed, candidate)
            pd.testing.assert_frame_equal(original.iloc[:cutoff], modified.iloc[:cutoff])
        # A deliberately forward-looking canary MUST change: the test has power.
        original_bad = panel["Close"].shift(-1)
        changed_bad = changed["Close"].shift(-1)
        self.assertFalse(original_bad.iloc[:cutoff].equals(changed_bad.iloc[:cutoff]))

    def test_source_hash_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SPY.csv"
            path.write_text("changed\n", encoding="utf-8")
            write_json(root / "manifest.json", {
                "start": "2004-01-01", "end_exclusive": "2024-01-01",
                "symbols": list(SYMBOLS),
                "files": {"SPY": {"filename": "SPY.csv", "sha256": "wrong"}},
            })
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                load_panel(root)

    def test_loader_valid_snapshot_duplicate_and_future_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dates = pd.bdate_range("2004-01-01", "2023-12-29")
            frame = pd.DataFrame({
                "Open": 100., "High": 101., "Low": 99., "Close": 100.,
                "Adj Close": 100., "Volume": 1000, "Dividends": 0., "Stock Splits": 0.,
            }, index=dates)
            frame.index.name = "date"
            def save(value):
                value.to_csv(root / "SPY.csv")
                write_json(root / "manifest.json", {
                    "start": "2004-01-01", "end_exclusive": "2024-01-01",
                    "symbols": ["SPY"], "files": {
                        "SPY": {"filename": "SPY.csv", "sha256": digest(root / "SPY.csv")}},
                })
            with patch("research.fresh_lab.data.SYMBOLS", ("SPY",)):
                save(frame)
                panel, _ = load_panel(root)
                self.assertEqual(len(panel["Close"]), len(frame))
                save(pd.concat([frame.iloc[:1], frame]))
                with self.assertRaisesRegex(ValueError, "duplicate or unsorted"):
                    load_panel(root)
                later = frame.iloc[-1:].copy()
                later.index = pd.DatetimeIndex(["2024-01-02"], name="date")
                save(pd.concat([frame, later]))
                with self.assertRaisesRegex(ValueError, "outside development window"):
                    load_panel(root)

    def test_pareto_dominance_and_undefined_sharpe(self):
        table = pd.DataFrame({"cagr": [.1, .05, .2, 0],
                              "sharpe_hac20": [1., .5, .8, np.nan],
                              "max_drawdown": [.1, .2, .2, 0]})
        self.assertEqual(pareto(table).tolist(), [True, False, True, False])

    def test_small_full_pipeline_and_replay(self):
        from research.fresh_lab.run import run
        from research.fresh_lab.signals import Candidate
        panel = synthetic_panel(600)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("research.fresh_lab.run.load_panel", return_value=(panel, {"synthetic": True})), \
                 patch("research.fresh_lab.run.registry", return_value=[
                     Candidate("synthetic_index", "index", benchmark=True)]), \
                 patch("research.fresh_lab.run.SCORE_START", str(panel["Close"].index[300].date())), \
                 patch("research.fresh_lab.run.git_state", return_value={"commit": "synthetic"}), \
                 patch("research.fresh_lab.run.importlib.metadata.version", return_value="synthetic"):
                bundle = run(root / "unused", root / "run", reuse_data=True)
            self.assertTrue(bundle.exists())
            report = json.loads((root / "run" / "report.json").read_text())
            self.assertEqual(report["counts"]["completed"], 10)
            self.assertEqual(report["counts"]["byte_identical_replays"], 2)
            for name, sha in report["outputs"].items():
                self.assertEqual(digest(root / "run" / name), sha)
            summary = pd.read_csv(root / "run" / "summary.csv")
            self.assertTrue((summary["status"] == "completed").all())
            self.assertFalse(report["oos_run"])
            self.assertFalse(report["monte_carlo_run"])


if __name__ == "__main__":
    unittest.main()
