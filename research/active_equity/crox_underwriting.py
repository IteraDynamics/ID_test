"""Offline, assumption-driven underwriting. No pilot writes, downloads or orders."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile

INPUT = Path(__file__).parent / "rehearsals/crox_underwriting_20260915.json"
ROOT = Path(__file__).resolve().parents[2]
MEMO = ROOT / "docs/research/CROX_UNDERWRITING_20260915.md"


def cash_bridge(d: dict) -> dict:
    o = d["observed"]
    h, prior = o["h1_2026"], o["h1_2025"]
    components = ("net_income", "da", "lease_cost", "sbc", "impairment", "deferred_tax",
                  "other_noncash", "ar", "inventory", "prepaid_other", "ap_accrued",
                  "lease_movement", "income_tax_movement")
    cfo = sum(h[k] for k in components)
    financing = h["borrowed"]-h["repaid"]-h["repurchase_including_excise"]-h["withholding_repurchases"]
    cash_change = cfo-h["capex"]+financing+h["fx_cash"]
    if abs(cfo-h["cfo"]) > 0.000001 or abs(cash_change-h["cash_change"]) > 0.000001:
        raise ValueError("Source cash-flow components do not reconcile")
    ttm_cfo = o["cfo_fy2025"]+h["cfo"]-prior["cfo"]
    ttm_capex = o["capex_fy2025"]+h["capex"]-prior["capex"]
    sbc = o["sbc_fy2025"]+h["sbc"]-prior["sbc"]
    tax_movement = o["income_tax_movement_fy2025"]+h["income_tax_movement"]-prior["income_tax_movement"]
    return {"h1_cfo_reconciled": cfo, "h1_cash_change_reconciled": cash_change,
            "h1_fcf": h["cfo"]-h["capex"], "prior_h1_fcf": prior["cfo"]-prior["capex"],
            "h1_fcf_improvement": (h["cfo"]-h["capex"])-(prior["cfo"]-prior["capex"]),
            "h1_income_tax_movement_improvement": h["income_tax_movement"]-prior["income_tax_movement"],
            "h1_net_borrowing": h["borrowed"]-h["repaid"],
            "ttm_cfo": ttm_cfo, "ttm_capex": ttm_capex, "ttm_fcf": ttm_cfo-ttm_capex,
            "ttm_sbc": sbc, "ttm_fcf_less_sbc_diagnostic": ttm_cfo-ttm_capex-sbc,
            "ttm_tax_movement": tax_movement,
            "ttm_fcf_less_sbc_and_tax_movement_diagnostic": ttm_cfo-ttm_capex-sbc-tax_movement,
            "note": "Historical levered cash flow, not FCFF; subtracting SBC and tax movements is a diagnostic, not GAAP or a fully normalized forecast. Tax movement is not total cash tax paid."}


def value(d: dict, name: str, discount: float | None = None) -> dict:
    s, a, o = d["scenarios"][name], d["assumptions"], d["observed"]
    rate = a["discount_rate"] if discount is None else discount
    g, years = s["terminal_growth"], a["years"]
    if rate <= g or rate <= 0 or a["diluted_shares"] <= 0 or years < 1:
        raise ValueError("Require positive discount above terminal growth, positive shares and horizon")
    c, h = o["crocs_revenue_fy2025"]*s["crocs_initial_factor"], o["heydude_revenue_fy2025"]*s["heydude_initial_factor"]
    previous = o["crocs_revenue_fy2025"]+o["heydude_revenue_fy2025"]
    corp, rows = s["corporate_cost"], []
    for year in range(1, years+1):
        revenue = c+h
        ebit = c*s["crocs_margin"]+h*s["heydude_margin"]-corp
        cash_tax = max(ebit, 0)*s["tax_rate"]  # No automatic credit for losses.
        nwc = max(revenue-previous, 0)*s["incremental_nwc_fraction"]
        fcff = ebit-cash_tax+s["da"]-s["capex"]-nwc
        rows.append({"year": year, "crocs_revenue": c, "heydude_revenue": h,
                     "crocs_ebit": c*s["crocs_margin"], "heydude_ebit": h*s["heydude_margin"],
                     "corporate_cost": corp, "ebit_including_sbc": ebit,
                     "cash_tax": cash_tax, "da": s["da"], "capex": s["capex"], "nwc_investment": nwc, "fcff": fcff})
        previous = revenue
        c *= 1+s["crocs_growth"]
        h *= 1+s["heydude_growth"]
        corp *= 1+s["corporate_growth"]
    terminal = rows[-1]["fcff"]*(1+g)/(rate-g)
    terminal_pv = terminal/(1+rate)**years
    ev = sum(row["fcff"]/(1+rate)**row["year"] for row in rows)+terminal_pv
    settlement_pv = s["incremental_tax_settlement_year2"]/(1+rate)**2
    excess_cash = max(o["june30_cash"]-a["operating_cash_reserve"], 0)
    equity = ev-a["debt_value_proxy"]+excess_cash-settlement_pv
    per_share = max(equity, 0)/a["diluted_shares"]
    return {"scenario": name, "rows": rows, "discount_rate": rate, "operating_value": ev,
            "terminal_value_share": terminal_pv/ev, "excess_cash": excess_cash,
            "incremental_tax_settlement_pv": settlement_pv, "equity_value_unfloored": equity,
            "value_per_share": per_share, "difference_from_quote": per_share/a["price_reference"]-1}


def buyback(equity: float, shares: float, spend: float, price: float, excise: float = 0.0) -> dict:
    if price <= 0 or shares <= 0 or spend < 0 or spend >= equity or excise < 0:
        raise ValueError("Invalid illustrative repurchase")
    retired = spend/(price*(1+excise))
    if retired >= shares:
        raise ValueError("Repurchase exceeds shares")
    return {"shares_retired": retired, "value_before": equity/shares,
            "value_after": (equity-spend)/(shares-retired),
            "note": "One-off incremental transaction with total cash/debt cost removed from equity. Not added to DCF or assumed as a free share-count reduction."}


def analyze(d: dict) -> dict:
    cases = {name: value(d, name) for name in d["scenarios"]}
    a, base = d["assumptions"], cases["base"]
    no_settlement = deepcopy(d)
    no_settlement["scenarios"]["base"]["incremental_tax_settlement_year2"] = 0
    return {"status": d["status"], "decision": "WATCH", "performance": None,
            "cash_bridge": cash_bridge(d), "scenarios": cases,
            "base_discount_sensitivity": {str(r): value(d, "base", r)["value_per_share"] for r in [0.10, 0.12, 0.14]},
            "base_without_incremental_tax_settlement": value(no_settlement, "base")["value_per_share"],
            "conditional_research_entry_ceiling": base["value_per_share"]*(1-a["illustrative_margin_of_safety"]),
            "buyback_at_reference": buyback(base["equity_value_unfloored"], a["diluted_shares"], a["incremental_buyback_spend"], a["price_reference"], a["illustrative_buyback_excise_rate"]),
            "warning": "WATCH is the original authored judgment, not a recalculated recommendation if inputs change. Scenarios have no probabilities and are not trading-return forecasts. Entry ceiling requires thesis and current data revalidation."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    d = json.loads(INPUT.read_text())
    result = analyze(d)
    print(json.dumps(result, indent=2, allow_nan=False))
    if args.output_dir:
        folder = args.output_dir / ("crox_underwriting_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
        bundle = folder.with_suffix(".zip")
        with zipfile.ZipFile(bundle, "x", compression=zipfile.ZIP_DEFLATED) as z:
            z.write(folder / "results.json", "results.json")
            z.write(INPUT, "inputs.json")
            z.write(Path(__file__), "model.py")
            z.write(MEMO, "memo.md")
        print(f"SHARE UNDERWRITING ZIP: {bundle.resolve()}")


if __name__ == "__main__":
    main()
