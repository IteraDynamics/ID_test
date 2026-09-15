"""Reproduce hand-transcribed rehearsal arithmetic. Offline; no ledger writes.

This is a worked research example, not an automated source verifier or backtest.
"""
import json
from pathlib import Path


def calculate(data):
    result = {"status": data["status"], "performance": None, "cases": {}}
    for ticker in ("CROX", "DUOL"):
        d = data[ticker]
        growth = d["revenue_2026"] / d["revenue_2025"] - 1
        margin = d["operating_income_2026"] / d["revenue_2026"]
        prior = d["operating_income_2025"] / d["revenue_2025"]
        result["cases"][ticker] = {
            "revenue_yoy": growth, "gaap_margin_2026": margin,
            "gaap_margin_2025": prior, "margin_change_pp": (margin-prior)*100,
            "simple_screen_pass": growth > 0 and margin > prior,
            "rehearsal_action": "watch", "cohort_eligible": None,
        }
    d = data["CROX"]
    midpoint = (d["fy_adjusted_eps_guidance_low"] + d["fy_adjusted_eps_guidance_high"]) / 2
    result["cases"]["CROX"].update({
        "adjusted_operating_income_yoy": d["adjusted_operating_income_2026"] / d["adjusted_operating_income_2025"] - 1,
        "adjusted_margin_2026": d["adjusted_operating_income_2026"] / d["revenue_2026"],
        "adjusted_margin_2025": d["adjusted_operating_income_2025"] / d["revenue_2025"],
        "adjusted_net_income_yoy": d["adjusted_net_income_2026"] / d["adjusted_net_income_2025"] - 1,
        "adjusted_diluted_shares_yoy": d["adjusted_diluted_shares_2026"] / d["adjusted_diluted_shares_2025"] - 1,
        "indicative_forward_adjusted_pe": d["indicative_price"] / midpoint,
        "illustrative_stress_pe": d["indicative_price"] / (midpoint*(1-data["assumptions"]["crox_eps_stress_haircut"])),
    })
    d = data["DUOL"]
    ev_proxy = d["indicative_price"]*d["estimated_diluted_shares_june30"] - d["cash_and_equivalents"] - d["short_term_investments"]
    compensation_allowance = d["fy_revenue_guidance"]*d["fy_sbc_revenue_guidance"]
    result["cases"]["DUOL"].update({
        "reported_operating_income_change_m": d["operating_income_2026"]-d["operating_income_2025"],
        "founder_comp_yoy_favorable_swing_m": d["founder_comp_benefit_2026"]+d["founder_comp_expense_2025"],
        "operating_income_excluding_founder_line_2026_m": d["operating_income_2026"]-d["founder_comp_benefit_2026"],
        "operating_income_excluding_founder_line_2025_m": d["operating_income_2025"]+d["founder_comp_expense_2025"],
        "illustrative_ev_proxy_m": ev_proxy,
        "ev_proxy_to_guided_revenue": ev_proxy/d["fy_revenue_guidance"],
        "ev_proxy_to_guided_adjusted_ebitda": ev_proxy/d["fy_adjusted_ebitda_guidance"],
        "guided_ebitda_minus_sbc_allowance_m": d["fy_adjusted_ebitda_guidance"]-compensation_allowance,
        "ev_proxy_to_ebitda_minus_sbc_allowance": ev_proxy/(d["fy_adjusted_ebitda_guidance"]-compensation_allowance),
        "warning": "Founder-line exclusion is a diagnostic, not normalized earnings. EBITDA minus SBC is neither GAAP income nor FCF. Do not also charge future dilution for the same compensation in a valuation model.",
    })
    return result


if __name__ == "__main__":
    inputs = Path(__file__).parent / "rehearsals" / "20260915_inputs.json"
    print(json.dumps(calculate(json.loads(inputs.read_text())), indent=2, allow_nan=False))
