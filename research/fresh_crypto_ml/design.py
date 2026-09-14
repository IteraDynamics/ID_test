"""Fixed trial budget and timing constants; no outcome-selected configuration."""
from dataclasses import asdict, dataclass

PROFILES = (.20, .40)
HORIZON = 14
LABEL_COST = .003
EVALUATION_START = "2020-01-01"
MIN_TRAIN = 500
SCORE_MARGIN = .001
FEATURES = (
    "btc_momentum90", "btc_momentum180", "btc_momentum365",
    "eth_momentum90", "eth_momentum180", "eth_momentum365",
    "acceleration", "trend_agreement", "volatility_ratio", "downside_fraction",
    "recent_drawdown", "btc_eth_correlation", "relative_strength14", "relative_volume", "annual_volatility",
)
MODELS = ("constant", "ridge", "boosted")
RIDGE = dict(alpha=100., solver="svd")
BOOSTED = dict(loss="squared_error", learning_rate=.05, max_iter=50, max_leaf_nodes=4,
               max_depth=2, min_samples_leaf=60, l2_regularization=10., early_stopping=False,
               random_state=20260914)
EXPECTED_INPUTS = {
    "BTC-USD.csv": "9864fb4539fd8199f2c4eab855e7dd8db4aa4e368a5eb670c0f870082a1f58d6",
    "ETH-USD.csv": "993cb7d7b63161181dfa245add3a146fef85a473173038103a8f94de44d4ece5",
}
SOURCE_COMMIT = "62cc0f1e110aa4f83e9502198e43105368fbc89e"


@dataclass(frozen=True)
class Policy:
    name: str
    family: str
    target: float | None
    band: float
    role: str


def policies():
    result = []
    for target in PROFILES:
        for band in (0., .02):
            for family in ("trend", "allocation", "fixed_blend", "state_rule", *MODELS):
                role = "candidate" if family in ("ridge", "boosted") else "control"
                result.append(Policy(f"{family}_vol{int(target*100)}_{'band2' if band else 'exact'}",
                                     family, target, band, role))
    return result + [Policy(family, family, None, 0., "benchmark")
                     for family in ("btc_buy_hold", "eth_buy_hold", "mix_buy_hold", "usd_cash")]


def registry():
    return dict(policies=[asdict(p) for p in policies()], horizon_days=HORIZON,
                label_one_way_cost=LABEL_COST, evaluation_start=EVALUATION_START,
                minimum_training_rows=MIN_TRAIN, features=FEATURES, ridge=RIDGE, boosted=BOOSTED,
                score_margin=SCORE_MARGIN, quarterly_refits=True, weekly_mixture_decisions=True,
                feature_clipping_quantiles=[.01, .99], labels_start_from="unit_USD_cash",
                label_terminal_convention="sell_all_at_open_after_14_calendar_days",
                label_eligibility="label_exit_open_strictly_before_model_fit_time",
                actual_equity_path="continuous_inventory_no_14_day_resets")
