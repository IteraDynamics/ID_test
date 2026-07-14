from __future__ import annotations

from dataclasses import dataclass

SELECTED_CORE_V1_SCENARIO = "candidate_btc1h_hedges_to_btc4h_gld_qqq"


@dataclass(frozen=True)
class CoreV1Sleeve:
    label: str
    family: str
    asset: str
    timeframe: str
    strategy: str
    weight: float


SELECTED_CORE_V1_SLEEVES: tuple[CoreV1Sleeve, ...] = (
    CoreV1Sleeve("BTC_4H_trend", "trend", "BTC", "4H", "trend_following_v11", 0.15),
    CoreV1Sleeve("ETH_1H_trend", "trend", "ETH", "1H", "trend_following_v11", 0.10),
    CoreV1Sleeve("ETH_4H_trend", "trend", "ETH", "4H", "trend_following_v11", 0.10),
    CoreV1Sleeve("SPY_1D_equity", "equity", "SPY", "1D", "equity_sma175_v3", 0.175),
    CoreV1Sleeve("QQQ_1D_equity", "equity", "QQQ", "1D", "equity_sma175_v3", 0.275),
    CoreV1Sleeve("GLD_1D_gold", "gold", "GLD", "1D", "gold_sma_v1", 0.20),
)

EXPLICIT_ZERO_WEIGHT_SLEEVES: dict[str, float] = {
    "BTC_1H_trend": 0.0,
    "BTC_1H_hedge": 0.0,
    "ETH_1H_hedge": 0.0,
}


def validate_selected_allocation() -> None:
    total = sum(s.weight for s in SELECTED_CORE_V1_SLEEVES) + sum(EXPLICIT_ZERO_WEIGHT_SLEEVES.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"Selected Core v1 allocation sums to {total:.12f}, not 1.0")
    labels = {s.label for s in SELECTED_CORE_V1_SLEEVES}
    required = {"BTC_4H_trend", "ETH_1H_trend", "ETH_4H_trend", "SPY_1D_equity", "QQQ_1D_equity", "GLD_1D_gold"}
    missing = required - labels
    if missing:
        raise ValueError(f"Selected Core v1 allocation missing required sleeves: {sorted(missing)}")
