"""Accounting and valuation mechanics, not evidence of investment returns."""
from copy import deepcopy
import json

import pytest

from research.active_equity import crox_underwriting as m


@pytest.fixture
def inputs():
    return json.loads(m.INPUT.read_text())


def test_cash_bridge_and_trailing_window(inputs):
    r = m.cash_bridge(inputs)
    assert r["h1_cash_change_reconciled"] == pytest.approx(39.920)
    assert r["ttm_fcf"] == pytest.approx(704.620)
    assert r["ttm_fcf_less_sbc_diagnostic"] == pytest.approx(663.103)
    assert r["h1_income_tax_movement_improvement"] > r["h1_fcf_improvement"]


def test_bad_cash_transcription_rejected(inputs):
    inputs["observed"]["h1_2026"]["inventory"] += 1
    with pytest.raises(ValueError, match="reconcile"):
        m.cash_bridge(inputs)


def test_debt_subtracted_once_and_share_denominator(inputs):
    original = m.value(inputs, "base")
    inputs["assumptions"]["debt_value_proxy"] += 49
    changed = m.value(inputs, "base")
    assert original["value_per_share"]-changed["value_per_share"] == pytest.approx(1)
    assert original["rows"] == changed["rows"]
    inputs["assumptions"]["diluted_shares"] *= 2
    assert m.value(inputs, "base")["value_per_share"] == pytest.approx(changed["value_per_share"]/2)


def test_discount_and_cash_cost_monotonicity(inputs):
    assert m.value(inputs, "base", .10)["value_per_share"] > m.value(inputs, "base", .14)["value_per_share"]
    first = m.value(inputs, "base")
    inputs["scenarios"]["base"]["capex"] += 10
    assert m.value(inputs, "base")["value_per_share"] < first["value_per_share"]


def test_buyback_fair_price_neutrality_and_overpayment():
    neutral = m.buyback(1000, 10, 100, 100)
    assert neutral["value_before"] == pytest.approx(neutral["value_after"])
    overpriced = m.buyback(1000, 10, 100, 120)
    assert overpriced["value_after"] < overpriced["value_before"]
    taxed = m.buyback(1000, 10, 100, 100, .01)
    assert taxed["value_after"] < taxed["value_before"]


def test_invalid_terminal_and_no_fake_tax_refund(inputs):
    with pytest.raises(ValueError):
        m.value(inputs, "base", .01)
    inputs["scenarios"]["bear"]["corporate_cost"] = 5000
    assert all(r["cash_tax"] == 0 for r in m.value(inputs, "bear")["rows"])
    assert m.value(inputs, "bear")["value_per_share"] == 0


def test_no_release_of_working_capital_in_decline(inputs):
    assert all(r["nwc_investment"] == 0 for r in m.value(inputs, "bear")["rows"])


def test_output_is_scenarios_not_performance(inputs):
    before = deepcopy(inputs)
    r = m.analyze(inputs)
    assert r["performance"] is None and r["decision"] == "WATCH"
    assert inputs == before
    assert r["scenarios"]["bear"]["value_per_share"] < r["scenarios"]["base"]["value_per_share"] < r["scenarios"]["bull"]["value_per_share"]
