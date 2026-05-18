#!/usr/bin/env python
"""IteraDynamics — Fund v2 Paper Trading Runner.

Profile: fund_v2_crypto_hybrid_eth4h_cap75  (research/paper candidate — NOT live)

Sleeve strategy mapping:
    BTC_1H  ->  trend_following_v8_ecap75
    BTC_4H  ->  trend_following_v8_ecap75
    ETH_1H  ->  trend_following_v8_ecap75
    ETH_4H  ->  trend_following_v8_cap75   <- differentiator vs Fund v1

Capital split (same as Fund v1):
    BTC broker: $50,000  (BTC_1H 25% + BTC_4H 25%)
    ETH broker: $50,000  (ETH_1H 25% + ETH_4H 25%)

Isolation guarantees:
    - Does NOT modify Fund v1 state, fills, or log files.
    - Uses separate state file:   runtime/argus/state/fund_v2_state.json
    - Uses separate fills log:    runtime/argus/state/fund_v2_fills.jsonl
    - Uses separate signals log:  runtime/argus/state/fund_v2_signals.jsonl
    - Broker/execution/governor logic is unchanged (same classes as Fund v1).
    - No live capital. Paper only.

Usage:
    python scripts/run_fund_v2_live.py
    python scripts/run_fund_v2_live.py --capital 100000 --poll 3600 --max-cycles 24
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.request
import urllib.error
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fund_v2")

from research.strategies import trend_following_v8_ecap75
from research.strategies import trend_following_v8_cap75
from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.harness.resampler import resample_ohlcv
from research.harness.execution_model import compute_atr_pct_scalar
from runtime.argus.brokers.paper_broker import PaperBroker
from runtime.argus.governors.drawdown_governor import DrawdownGovernor
from runtime.argus.governors.exposure_governor import ExposureGovernor

# ── Profile identity ───────────────────────────────────────────────────────────

PROFILE_NAME = "fund_v2_crypto_hybrid_eth4h_cap75"

# Per-sleeve strategy assignment — the defining characteristic of this profile.
STRATEGY_MAP: dict[str, Any] = {
    "BTC_1H": trend_following_v8_ecap75,
    "BTC_4H": trend_following_v8_ecap75,
    "ETH_1H": trend_following_v8_ecap75,
    "ETH_4H": trend_following_v8_cap75,   # hard-cap variant for ETH 4H
}
STRATEGY_NAMES: dict[str, str] = {
    k: getattr(v, "STRATEGY_ID", k) for k, v in STRATEGY_MAP.items()
}

COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product}/candles"

TARGET_1H_BARS = 900
MIN_1H_BARS    = 250
MIN_4H_BARS    = 200

DEFAULT_STATE_PATH   = "runtime/argus/state/fund_v2_state.json"
DEFAULT_FILLS_LOG    = "runtime/argus/state/fund_v2_fills.jsonl"
DEFAULT_SIGNALS_LOG  = "runtime/argus/state/fund_v2_signals.jsonl"
REBALANCE_THRESHOLD  = 0.05


# ── State dataclass ────────────────────────────────────────────────────────────

@dataclass
class FundV2State:
    mode: str     = PROFILE_NAME
    strategy: str = "mixed_per_sleeve"
    cycle: int    = 0
    timestamp: str = ""
    # ── Portfolio ──────────────────────────────────────────────────────────────
    portfolio_nav: float = 0.0
    portfolio_target_exposure: float = 0.0
    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_fees: float = 0.0
    total_slippage: float = 0.0
    # ── BTC broker ────────────────────────────────────────────────────────────
    btc_nav: float = 0.0
    btc_exposure: float = 0.0
    btc_position_units: float = 0.0
    btc_cash: float = 0.0
    btc_avg_entry_price: float = 0.0
    btc_realized_pnl: float = 0.0
    btc_unrealized_pnl: float = 0.0
    btc_cumulative_fees: float = 0.0
    btc_cumulative_slippage: float = 0.0
    btc_fill_count: int = 0
    btc_high_water_mark: float = 0.0
    btc_drawdown_halted: bool = False
    # ── ETH broker ────────────────────────────────────────────────────────────
    eth_nav: float = 0.0
    eth_exposure: float = 0.0
    eth_position_units: float = 0.0
    eth_cash: float = 0.0
    eth_avg_entry_price: float = 0.0
    eth_realized_pnl: float = 0.0
    eth_unrealized_pnl: float = 0.0
    eth_cumulative_fees: float = 0.0
    eth_cumulative_slippage: float = 0.0
    eth_fill_count: int = 0
    eth_high_water_mark: float = 0.0
    eth_drawdown_halted: bool = False
    # ── Per-sleeve strategy map (informational) ────────────────────────────────
    sleeve_strategies: dict = field(default_factory=lambda: dict(STRATEGY_NAMES))
    # ── Per-sleeve audit (list of dicts) ──────────────────────────────────────
    sleeves: list[dict] = field(default_factory=list)
    # ── Last decisions ────────────────────────────────────────────────────────
    last_btc_decision: str = ""
    last_eth_decision: str = ""
    last_updated: str = ""
    # ── Operational metadata ──────────────────────────────────────────────────
    rebalance_threshold: float = 0.0
    btc_nav_drift: float = 0.0
    eth_nav_drift: float = 0.0

    def save(self, path: str | Path = DEFAULT_STATE_PATH) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.last_updated = datetime.utcnow().isoformat()
        with open(out, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_STATE_PATH) -> "FundV2State":
        p = Path(path)
        if not p.exists():
            log.info("[fund_v2] No state at %s — starting fresh.", p)
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            valid = set(cls.__dataclass_fields__.keys())
            return cls(**{k: v for k, v in data.items() if k in valid})
        except Exception as exc:
            log.warning("[fund_v2] Could not load state (%s) — starting fresh: %s", p, exc)
            return cls()


# ── Coinbase data fetching (paginated) ─────────────────────────────────────────

def _parse_candles(raw: list) -> pd.DataFrame:
    df = pd.DataFrame(raw, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
    df = df.set_index("time").rename_axis("timestamp")
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df.sort_index()
    return df[~df.index.duplicated(keep="last")]


def fetch_candles_paginated(
    product_id: str,
    granularity: int = 3600,
    n_candles: int = TARGET_1H_BARS,
) -> pd.DataFrame:
    all_frames: list[pd.DataFrame] = []
    end_time: datetime | None = None
    remaining = n_candles

    while remaining > 0:
        url = (
            f"{COINBASE_CANDLES_URL.format(product=product_id)}"
            f"?granularity={granularity}"
        )
        if end_time is not None:
            start_dt = end_time - timedelta(seconds=300 * granularity)
            url += (
                f"&start={start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                f"&end={end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )

        req = urllib.request.Request(
            url, headers={"User-Agent": "IteraDynamics/fund-v2"}
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            if all_frames:
                collected = sum(len(f) for f in all_frames)
                log.warning(
                    "[fund_v2] %s: pagination stopped at %d bars (API error: %s)",
                    product_id, collected, exc,
                )
                break
            raise RuntimeError(
                f"Coinbase fetch failed for {product_id}: {exc}"
            ) from exc

        if not raw:
            break

        page_df = _parse_candles(raw)
        all_frames.append(page_df)
        remaining -= len(page_df)

        if len(page_df) < 300:
            break

        oldest = page_df.index[0]
        end_time = oldest.to_pydatetime() - timedelta(seconds=granularity)
        time.sleep(0.25)

    if not all_frames:
        raise RuntimeError(f"No candles returned for {product_id}")

    combined = pd.concat(all_frames)
    combined = combined[~combined.index.duplicated(keep="last")]
    return combined.sort_index()


def get_asset_data(product_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (df_1h, df_4h) with the last open bar stripped."""
    df_raw = fetch_candles_paginated(product_id)

    if len(df_raw) < MIN_1H_BARS:
        raise RuntimeError(
            f"{product_id}: only {len(df_raw)} 1H bars fetched, need {MIN_1H_BARS}"
        )

    df_1h = df_raw.iloc[:-1]
    df_4h = resample_ohlcv(df_1h, "4h")

    if not df_4h.empty:
        last_4h_start = df_4h.index[-1]
        n_constituent = int(
            (
                (df_1h.index >= last_4h_start)
                & (df_1h.index < last_4h_start + pd.Timedelta(hours=4))
            ).sum()
        )
        if n_constituent < 4:
            df_4h = df_4h.iloc[:-1]
            log.debug(
                "[fund_v2] %s: dropped incomplete trailing 4H bar at %s (%d/4 bars)",
                product_id, last_4h_start, n_constituent,
            )

    if len(df_4h) < MIN_4H_BARS:
        log.warning(
            "[fund_v2] %s: only %d 4H bars available (min recommended: %d).",
            product_id, len(df_4h), MIN_4H_BARS,
        )

    log.info(
        "[fund_v2] %s: %d 1H bars (%s -> %s)  |  %d 4H bars (%s -> %s)",
        product_id,
        len(df_1h), df_1h.index[0], df_1h.index[-1],
        len(df_4h),
        df_4h.index[0] if not df_4h.empty else "—",
        df_4h.index[-1] if not df_4h.empty else "—",
    )
    return df_1h, df_4h


# ── Signal generation ──────────────────────────────────────────────────────────

def _bar_age_seconds(df: pd.DataFrame) -> int:
    try:
        last_bar = df.index[-1]
        if hasattr(last_bar, "tzinfo") and last_bar.tzinfo is None:
            last_bar = last_bar.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - last_bar).total_seconds())
    except Exception:
        return -1


def run_sleeve(
    label: str,
    asset: str,
    weight: float,
    df: pd.DataFrame,
    strategy_module: Any,
    regime_engine: BaselineRegimeEngine,
    current_exposure: float,
) -> dict:
    """Generate a signal for one sleeve.  Returns a serialisable audit record."""
    bar_index = len(df) - 1
    regime_signal = regime_engine.classify_bar(df, bar_index)

    ctx = StrategyContext(
        regime=regime_signal.label,
        current_exposure_frac=max(0.0, min(1.0, current_exposure)),
        asset=asset,
        bar_index=bar_index,
    )
    intent: StrategyIntent = strategy_module.generate_intent(df, ctx, closed_only=True)

    cal_conf = float(
        intent.meta.get("ml_calibration", {}).get(
            "calibrated_confidence", intent.confidence
        )
    )

    strategy_id = getattr(strategy_module, "STRATEGY_ID", label)

    log.info(
        "[fund_v2] Sleeve %-8s [%s] | regime=%-12s action=%-12s "
        "raw=%.3f cal=%.3f desired_exp=%.3f | %s",
        label,
        strategy_id,
        regime_signal.label.value,
        intent.action.value,
        float(intent.confidence),
        cal_conf,
        float(intent.desired_exposure_frac),
        intent.reason[:80],
    )

    return {
        "label": label,
        "asset": asset,
        "timeframe": label.split("_")[1],
        "weight": weight,
        "strategy_id": strategy_id,
        "regime": regime_signal.label.value,
        "action": intent.action.value,
        "raw_confidence": round(float(intent.confidence), 4),
        "calibrated_confidence": round(cal_conf, 4),
        "desired_exposure": round(float(intent.desired_exposure_frac), 4),
        "weighted_contribution": round(weight * float(intent.desired_exposure_frac), 4),
        "reason": intent.reason,
        "bar_timestamp": str(df.index[-1]),
        "bar_age_seconds": _bar_age_seconds(df),
        "_intent": intent,
        "_regime": regime_signal.label,
    }


# ── Portfolio allocation (per-asset, two sleeves each) ─────────────────────────

def _desired_exposure(intent: StrategyIntent, current_exposure: float) -> float:
    if intent.action in (Action.EXIT_LONG, Action.FLAT):
        return 0.0
    if intent.action == Action.HOLD:
        return current_exposure
    return float(intent.desired_exposure_frac)


def allocate_asset(
    asset: str,
    sleeve_a: dict,
    sleeve_b: dict,
    current_exposure: float,
    current_nav: float,
    dd_gov: DrawdownGovernor,
    exp_gov: ExposureGovernor,
    rebalance_threshold: float,
) -> dict:
    """Blend two same-asset sleeve signals and apply governors."""
    intent_a: StrategyIntent = sleeve_a["_intent"]
    intent_b: StrategyIntent = sleeve_b["_intent"]
    regime = sleeve_a["_regime"]

    desired_a = _desired_exposure(intent_a, current_exposure)
    desired_b = _desired_exposure(intent_b, current_exposure)
    blended = 0.5 * desired_a + 0.5 * desired_b

    all_exit = (
        intent_a.action in (Action.EXIT_LONG, Action.FLAT)
        and intent_b.action in (Action.EXIT_LONG, Action.FLAT)
    )
    if all_exit:
        if current_exposure <= 1e-6:
            return {
                "action": "HOLD", "approved": False,
                "target_exposure": current_exposure,
                "blended_exposure": 0.0,
                "reason": "All sleeves exit — already flat",
            }
        notional = current_exposure * current_nav
        if notional < float(exp_gov.min_trade_notional):
            return {
                "action": "HOLD", "approved": False,
                "target_exposure": current_exposure,
                "blended_exposure": 0.0,
                "reason": f"All sleeves exit — notional ${notional:.0f} below minimum",
            }
        return {
            "action": "SELL", "approved": True,
            "target_exposure": 0.0,
            "blended_exposure": 0.0,
            "reason": "All sleeves exiting — full close",
        }

    delta = blended - current_exposure

    if abs(delta) < rebalance_threshold:
        return {
            "action": "HOLD", "approved": False,
            "target_exposure": current_exposure,
            "blended_exposure": blended,
            "reason": f"delta={delta:.4f} below threshold={rebalance_threshold}",
        }

    dominant = intent_a if desired_a >= desired_b else intent_b

    if delta > 0:
        entry_ok, capped, gov_reason = exp_gov.check_entry(
            intent=dominant,
            current_nav=current_nav,
            current_exposure=current_exposure,
            regime=regime,
            drawdown_governor_allows=dd_gov.is_buy_allowed(),
        )
        return {
            "action": "BUY" if entry_ok else "HOLD",
            "approved": entry_ok,
            "target_exposure": min(blended, capped) if entry_ok else current_exposure,
            "blended_exposure": blended,
            "reason": gov_reason,
        }
    else:
        if current_exposure <= 1e-6:
            return {
                "action": "HOLD", "approved": False,
                "target_exposure": current_exposure,
                "blended_exposure": blended,
                "reason": "Reduce signal — already flat",
            }
        notional = current_exposure * current_nav
        if notional < float(exp_gov.min_trade_notional):
            return {
                "action": "HOLD", "approved": False,
                "target_exposure": current_exposure,
                "blended_exposure": blended,
                "reason": f"Position notional ${notional:.0f} below minimum",
            }
        return {
            "action": "SELL", "approved": True,
            "target_exposure": blended,
            "blended_exposure": blended,
            "reason": "Reduce exposure — blended signal declining",
        }


# ── Audit log helpers ──────────────────────────────────────────────────────────

def _append_fill_log(
    path: Path,
    fill: Any,
    cycle: int,
    broker: PaperBroker,
    price: float,
) -> None:
    record = {
        "timestamp": fill.timestamp.isoformat(),
        "cycle": cycle,
        "profile": PROFILE_NAME,
        "asset": fill.asset,
        "side": fill.side,
        "qty": round(fill.qty, 8),
        "fill_price": round(fill.fill_price, 6),
        "mid_price": round(fill.mid_price, 6),
        "slippage_cost": round(fill.slippage_usd + fill.spread_usd, 6),
        "fee": round(fill.fee, 6),
        "cost_bps": round(fill.cost_bps, 4),
        "avg_entry_price": round(broker.get_avg_entry_price(fill.asset), 6),
        "realized_pnl": round(broker.get_realized_pnl(fill.asset), 4),
        "cash_after": round(broker.get_balance()["USD"], 4),
        "position_after": round(broker.get_position(fill.asset), 8),
        "nav_after": round(broker.get_nav(fill.asset, price), 4),
        "cumulative_fees": round(broker.get_cumulative_fees(), 6),
        "cumulative_slippage": round(broker.get_cumulative_slippage(), 6),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _append_signal_log(
    path: Path,
    cycle: int,
    sleeve_list: list[dict],
) -> None:
    """Append per-cycle sleeve signals to the append-only signals JSONL log."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cycle": cycle,
        "profile": PROFILE_NAME,
        "sleeves": [
            {k: v for k, v in s.items() if not k.startswith("_")}
            for s in sleeve_list
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


# ── Execution ──────────────────────────────────────────────────────────────────

def execute_asset(
    asset: str,
    broker: PaperBroker,
    decision: dict,
    price: float,
    df_for_atr: pd.DataFrame,
) -> Any:
    if not decision["approved"] or decision["action"] not in ("BUY", "SELL"):
        return None

    atr_pct = compute_atr_pct_scalar(df_for_atr)
    qty = broker.compute_order_qty(
        asset=asset,
        side=decision["action"],
        target_exposure_frac=decision["target_exposure"],
        current_price=price,
    )

    if qty <= 1e-8:
        return None

    order, fill = broker.submit_and_fill(
        asset=asset,
        side=decision["action"],
        qty=qty,
        price=price,
        reason=decision["reason"][:120],
        atr_pct=atr_pct,
    )

    if fill:
        slippage_cost = fill.slippage_usd + fill.spread_usd
        log.info(
            "[fund_v2] %s FILL: %s %.8f units @ $%.4f  "
            "(mid=$%.4f  slip=$%.4f  fee=$%.4f  cost=%.1fbps) | "
            "cash=$%.2f  pos=%.8f  NAV=$%.2f",
            asset, fill.side, fill.qty, fill.fill_price,
            fill.mid_price, slippage_cost, fill.fee, fill.cost_bps,
            broker.get_balance()["USD"],
            broker.get_position(asset),
            broker.get_nav(asset, price),
        )
    return fill


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            f"Fund v2 paper trading — profile={PROFILE_NAME}  "
            "BTC(1H+4H) + ETH(1H+4H), equal-weight, per-sleeve strategies"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--capital",    type=float, default=100_000.0,
                   help="Total portfolio capital (USD)")
    p.add_argument("--poll",       type=int,   default=3600,
                   help="Poll interval in seconds")
    p.add_argument("--max-cycles", type=int,   default=None,
                   help="Stop after N cycles (useful for testing)")
    p.add_argument("--state-path", default=DEFAULT_STATE_PATH,
                   help="Path to fund_v2 state JSON file")
    p.add_argument("--rebalance-threshold", type=float, default=REBALANCE_THRESHOLD,
                   help="Minimum exposure delta to trigger a trade")
    p.add_argument("--fills-log",  default=DEFAULT_FILLS_LOG,
                   help="Append-only JSONL fill audit log")
    p.add_argument("--signals-log", default=DEFAULT_SIGNALS_LOG,
                   help="Append-only JSONL per-cycle signals log")
    return p.parse_args()


# ── Main loop ──────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    btc_capital = args.capital * 0.50
    eth_capital = args.capital * 0.50

    fills_log   = Path(args.fills_log)
    signals_log = Path(args.signals_log)

    log.info(
        "[fund_v2] ══ Fund v2 paper trader starting ══  "
        "profile=%s  BTC=$%.0f  ETH=$%.0f  poll=%ds  rebalance_threshold=%.2f",
        PROFILE_NAME, btc_capital, eth_capital,
        args.poll, args.rebalance_threshold,
    )
    log.info("[fund_v2] Sleeve strategy mapping: %s", STRATEGY_NAMES)
    log.info("[fund_v2] Fills log: %s  |  Signals log: %s", fills_log, signals_log)

    # ── Per-asset paper brokers ────────────────────────────────────────────────
    btc_broker = PaperBroker(initial_cash=btc_capital)
    eth_broker = PaperBroker(initial_cash=eth_capital)

    # ── Per-asset governors ────────────────────────────────────────────────────
    btc_dd_gov  = DrawdownGovernor()
    eth_dd_gov  = DrawdownGovernor()
    btc_exp_gov = ExposureGovernor()
    eth_exp_gov = ExposureGovernor()

    # ── Shared regime engine ───────────────────────────────────────────────────
    regime_engine = BaselineRegimeEngine()

    # ── State ──────────────────────────────────────────────────────────────────
    state = FundV2State.load(args.state_path)
    state.mode                = PROFILE_NAME
    state.strategy            = "mixed_per_sleeve"
    state.sleeve_strategies   = dict(STRATEGY_NAMES)
    state.rebalance_threshold = args.rebalance_threshold

    # ── Main loop ──────────────────────────────────────────────────────────────
    cycle = state.cycle
    while True:
        cycle_wall = time.monotonic()
        cycle += 1
        log.info(
            "[fund_v2] ── Cycle %d  %s  mode=fund_v2 ──",
            cycle, datetime.now(timezone.utc).isoformat(),
        )

        try:
            # ── Fetch & resample data ──────────────────────────────────────────
            btc_1h, btc_4h = get_asset_data("BTC-USD")
            eth_1h, eth_4h = get_asset_data("ETH-USD")

            btc_price = float(btc_1h["close"].iloc[-1])
            eth_price = float(eth_1h["close"].iloc[-1])

            # ── Current broker snapshot ────────────────────────────────────────
            btc_nav   = btc_broker.get_nav("BTC", btc_price)
            eth_nav   = eth_broker.get_nav("ETH", eth_price)
            btc_units = btc_broker.get_position("BTC")
            eth_units = eth_broker.get_position("ETH")
            btc_exp   = (btc_units * btc_price) / btc_nav if btc_nav > 0 else 0.0
            eth_exp   = (eth_units * eth_price) / eth_nav if eth_nav > 0 else 0.0

            # ── Update drawdown governors ──────────────────────────────────────
            btc_dd_gov.update(btc_nav)
            eth_dd_gov.update(eth_nav)

            # ── Four sleeve signals (per-sleeve strategy) ──────────────────────
            btc_1h_sl = run_sleeve(
                "BTC_1H", "BTC", 0.25, btc_1h,
                STRATEGY_MAP["BTC_1H"], regime_engine, btc_exp,
            )
            btc_4h_sl = run_sleeve(
                "BTC_4H", "BTC", 0.25, btc_4h,
                STRATEGY_MAP["BTC_4H"], regime_engine, btc_exp,
            )
            eth_1h_sl = run_sleeve(
                "ETH_1H", "ETH", 0.25, eth_1h,
                STRATEGY_MAP["ETH_1H"], regime_engine, eth_exp,
            )
            eth_4h_sl = run_sleeve(
                "ETH_4H", "ETH", 0.25, eth_4h,
                STRATEGY_MAP["ETH_4H"], regime_engine, eth_exp,
            )

            sleeve_list = [btc_1h_sl, btc_4h_sl, eth_1h_sl, eth_4h_sl]

            # ── Write per-cycle signals log ────────────────────────────────────
            _append_signal_log(signals_log, cycle, sleeve_list)

            # ── Portfolio aggregate exposure ───────────────────────────────────
            portfolio_target = sum(s["weighted_contribution"] for s in sleeve_list)
            log.info(
                "[fund_v2] Portfolio aggregate target exposure: %.4f  "
                "(BTC_1H=%.3f  BTC_4H=%.3f  ETH_1H=%.3f  ETH_4H=%.3f)",
                portfolio_target,
                btc_1h_sl["weighted_contribution"],
                btc_4h_sl["weighted_contribution"],
                eth_1h_sl["weighted_contribution"],
                eth_4h_sl["weighted_contribution"],
            )

            # ── Per-asset allocation (blend 1H + 4H, apply governors) ──────────
            btc_decision = allocate_asset(
                asset="BTC",
                sleeve_a=btc_1h_sl,
                sleeve_b=btc_4h_sl,
                current_exposure=btc_exp,
                current_nav=btc_nav,
                dd_gov=btc_dd_gov,
                exp_gov=btc_exp_gov,
                rebalance_threshold=args.rebalance_threshold,
            )
            eth_decision = allocate_asset(
                asset="ETH",
                sleeve_a=eth_1h_sl,
                sleeve_b=eth_4h_sl,
                current_exposure=eth_exp,
                current_nav=eth_nav,
                dd_gov=eth_dd_gov,
                exp_gov=eth_exp_gov,
                rebalance_threshold=args.rebalance_threshold,
            )

            log.info(
                "[fund_v2] BTC governor: action=%s target=%.4f approved=%s | %s",
                btc_decision["action"], btc_decision["target_exposure"],
                btc_decision["approved"], btc_decision["reason"],
            )
            log.info(
                "[fund_v2] ETH governor: action=%s target=%.4f approved=%s | %s",
                eth_decision["action"], eth_decision["target_exposure"],
                eth_decision["approved"], eth_decision["reason"],
            )

            # ── Execute ────────────────────────────────────────────────────────
            btc_fill = execute_asset("BTC", btc_broker, btc_decision, btc_price, btc_1h)
            if btc_fill:
                _append_fill_log(fills_log, btc_fill, cycle, btc_broker, btc_price)

            eth_fill = execute_asset("ETH", eth_broker, eth_decision, eth_price, eth_1h)
            if eth_fill:
                _append_fill_log(fills_log, eth_fill, cycle, eth_broker, eth_price)

            # ── Post-fill snapshot ─────────────────────────────────────────────
            new_btc_nav   = btc_broker.get_nav("BTC", btc_price)
            new_eth_nav   = eth_broker.get_nav("ETH", eth_price)
            new_btc_units = btc_broker.get_position("BTC")
            new_eth_units = eth_broker.get_position("ETH")
            new_btc_exp   = (new_btc_units * btc_price) / new_btc_nav if new_btc_nav > 0 else 0.0
            new_eth_exp   = (new_eth_units * eth_price) / new_eth_nav if new_eth_nav > 0 else 0.0

            # ── NAV conservation check ─────────────────────────────────────────
            btc_nav_drift = btc_broker.check_nav_conservation("BTC", btc_price)
            eth_nav_drift = eth_broker.check_nav_conservation("ETH", eth_price)
            if abs(btc_nav_drift) > 0.01:
                log.error(
                    "[fund_v2] BTC NAV DRIFT DETECTED: drift=%.6f  "
                    "cash=%.4f  pos=%.8f  price=%.4f  nav=%.4f",
                    btc_nav_drift,
                    btc_broker.get_balance()["USD"], new_btc_units, btc_price, new_btc_nav,
                )
            if abs(eth_nav_drift) > 0.01:
                log.error(
                    "[fund_v2] ETH NAV DRIFT DETECTED: drift=%.6f  "
                    "cash=%.4f  pos=%.8f  price=%.4f  nav=%.4f",
                    eth_nav_drift,
                    eth_broker.get_balance()["USD"], new_eth_units, eth_price, new_eth_nav,
                )
            state.btc_nav_drift = btc_nav_drift
            state.eth_nav_drift = eth_nav_drift

            # ── PnL snapshot ───────────────────────────────────────────────────
            btc_realized   = btc_broker.get_realized_pnl("BTC")
            btc_unrealized = btc_broker.get_unrealized_pnl("BTC", btc_price)
            eth_realized   = eth_broker.get_realized_pnl("ETH")
            eth_unrealized = eth_broker.get_unrealized_pnl("ETH", eth_price)

            log.info(
                "[fund_v2] Portfolio NAV=$%.2f  "
                "BTC NAV=$%.2f exp=%.3f  ETH NAV=$%.2f exp=%.3f",
                new_btc_nav + new_eth_nav,
                new_btc_nav, new_btc_exp,
                new_eth_nav, new_eth_exp,
            )
            log.info(
                "[fund_v2] BTC: cash=$%.2f | pos=%.8f@$%.2f (val=$%.2f) | NAV=$%.2f | "
                "entry=$%.2f | realized=$%.2f unrealized=$%.2f | "
                "fees=$%.4f slip=$%.4f",
                btc_broker.get_balance()["USD"],
                new_btc_units, btc_price, new_btc_units * btc_price,
                new_btc_nav,
                btc_broker.get_avg_entry_price("BTC"),
                btc_realized, btc_unrealized,
                btc_broker.get_cumulative_fees(),
                btc_broker.get_cumulative_slippage(),
            )
            log.info(
                "[fund_v2] ETH: cash=$%.2f | pos=%.8f@$%.2f (val=$%.2f) | NAV=$%.2f | "
                "entry=$%.2f | realized=$%.2f unrealized=$%.2f | "
                "fees=$%.4f slip=$%.4f",
                eth_broker.get_balance()["USD"],
                new_eth_units, eth_price, new_eth_units * eth_price,
                new_eth_nav,
                eth_broker.get_avg_entry_price("ETH"),
                eth_realized, eth_unrealized,
                eth_broker.get_cumulative_fees(),
                eth_broker.get_cumulative_slippage(),
            )
            log.info(
                "[fund_v2] Portfolio PnL: realized=$%.2f  unrealized=$%.2f  "
                "total=$%.2f | fees=$%.4f  slip=$%.4f",
                btc_realized + eth_realized,
                btc_unrealized + eth_unrealized,
                btc_realized + eth_realized + btc_unrealized + eth_unrealized,
                btc_broker.get_cumulative_fees() + eth_broker.get_cumulative_fees(),
                btc_broker.get_cumulative_slippage() + eth_broker.get_cumulative_slippage(),
            )

            # ── Persist state ──────────────────────────────────────────────────
            state.cycle                      = cycle
            state.timestamp                  = datetime.now(timezone.utc).isoformat()
            state.portfolio_nav              = new_btc_nav + new_eth_nav
            state.portfolio_target_exposure  = portfolio_target
            state.total_realized_pnl         = btc_realized + eth_realized
            state.total_unrealized_pnl       = btc_unrealized + eth_unrealized
            state.total_fees                 = (
                btc_broker.get_cumulative_fees() + eth_broker.get_cumulative_fees()
            )
            state.total_slippage             = (
                btc_broker.get_cumulative_slippage() + eth_broker.get_cumulative_slippage()
            )
            state.btc_nav                    = new_btc_nav
            state.btc_exposure               = new_btc_exp
            state.btc_position_units         = new_btc_units
            state.btc_cash                   = btc_broker.get_balance().get("USD", 0.0)
            state.btc_avg_entry_price        = btc_broker.get_avg_entry_price("BTC")
            state.btc_realized_pnl           = btc_realized
            state.btc_unrealized_pnl         = btc_unrealized
            state.btc_cumulative_fees        = btc_broker.get_cumulative_fees()
            state.btc_cumulative_slippage    = btc_broker.get_cumulative_slippage()
            state.btc_fill_count             = len(btc_broker.fill_history)
            state.btc_high_water_mark        = btc_dd_gov._high_water_mark or new_btc_nav
            state.btc_drawdown_halted        = not btc_dd_gov.is_buy_allowed()
            state.eth_nav                    = new_eth_nav
            state.eth_exposure               = new_eth_exp
            state.eth_position_units         = new_eth_units
            state.eth_cash                   = eth_broker.get_balance().get("USD", 0.0)
            state.eth_avg_entry_price        = eth_broker.get_avg_entry_price("ETH")
            state.eth_realized_pnl           = eth_realized
            state.eth_unrealized_pnl         = eth_unrealized
            state.eth_cumulative_fees        = eth_broker.get_cumulative_fees()
            state.eth_cumulative_slippage    = eth_broker.get_cumulative_slippage()
            state.eth_fill_count             = len(eth_broker.fill_history)
            state.eth_high_water_mark        = eth_dd_gov._high_water_mark or new_eth_nav
            state.eth_drawdown_halted        = not eth_dd_gov.is_buy_allowed()
            state.last_btc_decision          = (
                f"{btc_decision['action']} approved={btc_decision['approved']}"
            )
            state.last_eth_decision          = (
                f"{eth_decision['action']} approved={eth_decision['approved']}"
            )
            state.sleeves = [
                {k: v for k, v in s.items() if not k.startswith("_")}
                for s in sleeve_list
            ]
            state.save(args.state_path)
            log.info("[fund_v2] State saved -> %s", args.state_path)

        except Exception as exc:
            log.exception("[fund_v2] Cycle %d error: %s", cycle, exc)

        if args.max_cycles and cycle >= args.max_cycles:
            log.info("[fund_v2] Reached max_cycles=%d — stopping.", args.max_cycles)
            break

        elapsed = time.monotonic() - cycle_wall
        sleep_sec = max(0.0, args.poll - elapsed)
        log.info("[fund_v2] Sleeping %.0fs until next cycle.", sleep_sec)
        time.sleep(sleep_sec)


if __name__ == "__main__":
    main()
