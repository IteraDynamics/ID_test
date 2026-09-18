from __future__ import annotations

if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError:
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)

import json

from runtime.core_v1.allocation import (
    EXPLICIT_ZERO_WEIGHT_SLEEVES,
    SELECTED_CORE_V1_SCENARIO,
    SELECTED_CORE_V1_SLEEVES,
    validate_selected_allocation,
)
from research.rre_entry_deferral import ELIGIBLE_SLEEVES, FROZEN_MODEL_HORIZON_DAYS, FROZEN_QUANTILE
from research.rre_frozen_instability import FROZEN_C, FROZEN_RANDOM_STATE

EXPECTED_SCENARIO = "candidate_btc1h_hedges_to_btc4h_gld_qqq"
EXPECTED_ACTIVE = {
    "BTC_4H_trend": 0.15, "ETH_1H_trend": 0.10, "ETH_4H_trend": 0.10,
    "SPY_1D_equity": 0.175, "QQQ_1D_equity": 0.275, "GLD_1D_gold": 0.20,
}
EXPECTED_ZERO = {"BTC_1H_trend": 0.0, "BTC_1H_hedge": 0.0, "ETH_1H_hedge": 0.0}
EXPECTED_ELIGIBLE = {"BTC_4H_trend", "ETH_1H_trend", "ETH_4H_trend"}


def main() -> None:
    validate_selected_allocation()
    active = {s.label: s.weight for s in SELECTED_CORE_V1_SLEEVES}
    zero = dict(EXPLICIT_ZERO_WEIGHT_SLEEVES)
    if SELECTED_CORE_V1_SCENARIO != EXPECTED_SCENARIO:
        raise SystemExit("FAIL: selected Core v1 scenario drift")
    if active != EXPECTED_ACTIVE:
        raise SystemExit(f"FAIL: active allocation drift: {active}")
    if zero != EXPECTED_ZERO:
        raise SystemExit(f"FAIL: zero-weight allocation drift: {zero}")
    if set(ELIGIBLE_SLEEVES) != EXPECTED_ELIGIBLE:
        raise SystemExit(f"FAIL: RRE eligible sleeve drift: {sorted(ELIGIBLE_SLEEVES)}")
    payload = {
        "status": "PASS",
        "economic_results_computed": False,
        "scenario": SELECTED_CORE_V1_SCENARIO,
        "active_sleeves": active,
        "explicit_zero_weight_sleeves": zero,
        "rre_eligible_sleeves": sorted(ELIGIBLE_SLEEVES),
        "instability_horizon_days": FROZEN_MODEL_HORIZON_DAYS,
        "training_quantile": FROZEN_QUANTILE,
        "logistic_C": FROZEN_C,
        "random_state": FROZEN_RANDOM_STATE,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
