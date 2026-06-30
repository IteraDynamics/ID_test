#!/usr/bin/env python
"""Clean Core v1 investigative paper-trading runner.

This runner intentionally does not use the older Argus unified runtime. It exists
only to operate the validated Selected Core v1 allocation:

- BTC 4H trend: 15%
- ETH 1H trend: 10%
- ETH 4H trend: 10%
- SPY equity: 17.5%
- QQQ equity: 27.5%
- GLD gold: 20%
- BTC 1H trend / BTC hedge / ETH hedge: 0%

It fetches public market data, computes current research-strategy intents for
those sleeves, paper-fills toward target exposure, and writes state/log files for
review and dashboarding.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv()

from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.contracts import RegimeLabel
from research.strategies import REGISTRY as STRATEGY_REGISTRY
from research.strategies.contracts import StrategyContext
from research.harness.resampler import resample_ohlcv
from runtime.core_v1.allocation import (
    SELECTED_CORE_V1_SCENARIO,
    SELECTED_CORE_V1_SLEEVES,
    validate_selected_allocation,
)

COINBASE_URL = "https://api.exchange.coinbase.com/products/{product}/candles"
STOOQ_URL = "https://stooq.com/q/d/l/"
STATE_VERSION = "core_v1_paper_runtime_v2"


def utc_now() -> datetime:
    return datetime.now(UTC)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str, sort_keys=True) + "\n")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def fetch_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "IteraDynamics-CoreV1-Paper/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "IteraDynamics-CoreV1-Paper/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def fetch_coinbase_hourly(product: str, days: int = 420) -> pd.DataFrame:
    """Fetch hourly Coinbase candles in <=300-candle chunks."""
    end = utc_now().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    rows: list[list[float]] = []
    chunk_start = start
    max_hours = 300

    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(hours=max_hours), end)
        params = urllib.parse.urlencode(
            {
                "granularity": 3600,
                "start": chunk_start.isoformat().replace("+00:00", "Z"),
                "end": chunk_end.isoformat().replace("+00:00", "Z"),
            }
        )
        url = f"{COINBASE_URL.format(product=product)}?{params}"
        data = fetch_json(url)
        if isinstance(data, list):
            rows.extend(data)
        time.sleep(0.12)
        chunk_start = chunk_end

    if not rows:
        raise RuntimeError(f"No Coinbase candles returned for {product}")

    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(None)
    df = df.drop(columns=["time"]).drop_duplicates("timestamp").set_index("timestamp").sort_index()
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def fetch_stooq_daily(symbol: str, days: int = 520) -> pd.DataFrame:
    params = urllib.parse.urlencode({"s": f"{symbol.lower()}.us", "i": "d"})
    text = fetch_text(f"{STOOQ_URL}?{params}")
    reader = csv.DictReader(text.splitlines())
    rows = list(reader)
    if not rows or "Date" not in rows[0]:
        raise RuntimeError(f"No Stooq daily data returned for {symbol}")
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["Date"], utc=False)
    for c in ("Open", "High", "Low", "Close", "Volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna().set_index("timestamp").sort_index()
    cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=days)
    return df.loc[df.index >= cutoff]


def maybe_load_local(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        from research.harness.data_loader import load_ohlcv
        df = load_ohlcv(str(path))
        return None if df.empty else df
    except Exception as e:
        print(f"local load failed for {path}: {e}", file=sys.stderr)
        return None


def load_market_data(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}

    for asset, product in {"BTC": "BTC-USD", "ETH": "ETH-USD"}.items():
        try:
            data[asset] = fetch_coinbase_hourly(product, days=args.crypto_days)
        except Exception as e:
            errors[asset] = str(e)
            local = maybe_load_local(Path(args.data_dir) / f"{asset.lower()}usd_3600s_2018-01-01_to_2025-12-31.csv")
            if local is not None:
                data[asset] = local

    for asset in ("SPY", "QQQ", "GLD", "BIL"):
        try:
            fetched = fetch_stooq_daily(asset, days=args.etf_days)
            if fetched.empty:
                raise RuntimeError(f"Empty ETF data returned for {asset}")
            data[asset] = fetched
        except Exception as e:
            errors[asset] = str(e)
            local = maybe_load_local(Path(args.data_dir) / f"{asset}_1D.csv")
            if local is not None and not local.empty:
                data[asset] = local

    required = {"BTC", "ETH", "SPY", "QQQ", "GLD", "BIL"}
    missing = sorted(required - set(data))
    if missing:
        raise RuntimeError(f"Missing market data for {missing}; errors={errors}")
    return data


def latest_price(df: pd.DataFrame) -> float:
    return float(df["close"].dropna().iloc[-1])


def btc_state_columns(data: dict[str, pd.DataFrame], index: pd.DatetimeIndex) -> pd.DataFrame:
    btc_daily = data["BTC"]["close"].resample("D").last().dropna()
    btc_hourly = data["BTC"]["close"]
    btc_above = (btc_daily > btc_daily.rolling(175).mean()).rename("btc_above_sma175")
    btc_ext = ((btc_hourly - btc_hourly.rolling(365 * 24).mean()) / btc_hourly.rolling(365 * 24).mean()).rename("btc_extension_sma365")
    btc_para_daily = (btc_ext.resample("D").last() > 1.0).rename("btc_in_parabolic")
    out = pd.DataFrame(index=index)
    out["btc_above_sma175"] = btc_above.reindex(index, method="ffill")
    out["btc_extension_sma365"] = btc_ext.reindex(index, method="ffill")
    out["btc_in_parabolic"] = btc_para_daily.reindex(index, method="ffill")
    return out


def spy_state(data: dict[str, pd.DataFrame], index: pd.DatetimeIndex) -> pd.Series:
    spy = data["SPY"]["close"]
    state = (spy > spy.rolling(175).mean()).rename("spy_above_sma175")
    return state.reindex(index, method="ffill")


def sleeve_dataframe(sleeve, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if sleeve.asset in ("BTC", "ETH"):
        df = data[sleeve.asset]
        if sleeve.timeframe == "4H":
            df = resample_ohlcv(df, "4h")
        df = df.copy()
        btc_cols = btc_state_columns(data, df.index)
        df["btc_above_sma175"] = btc_cols["btc_above_sma175"]
        df["btc_extension_sma365"] = btc_cols["btc_extension_sma365"]
        df["spy_above_sma175"] = spy_state(data, df.index)
        return df.dropna(subset=["open", "high", "low", "close"])

    df = data[sleeve.asset].copy()
    if sleeve.family == "equity":
        btc_cols = btc_state_columns(data, df.index)
        df["btc_in_parabolic"] = btc_cols["btc_in_parabolic"]
    return df.dropna(subset=["open", "high", "low", "close"])


def classify_regime(df: pd.DataFrame) -> RegimeLabel:
    try:
        sig = BaselineRegimeEngine().classify_bar(df, len(df) - 1)
        return sig.label
    except Exception:
        return RegimeLabel.UNKNOWN


def default_sleeve_state(capital: float, weight: float) -> dict[str, Any]:
    return {
        "cash": capital * weight,
        "qty": 0.0,
        "cost_basis": 0.0,
        "avg_entry": None,
        "realized_pnl": 0.0,
        "last_action": None,
        "last_price": None,
        "last_target_exposure": 0.0,
        "last_timestamp": None,
    }


def migrate_sleeve_state(s: dict[str, Any], capital: float, weight: float) -> None:
    s.setdefault("cash", capital * weight)
    s.setdefault("qty", 0.0)
    s.setdefault("realized_pnl", 0.0)
    s.setdefault("last_action", None)
    s.setdefault("last_price", None)
    s.setdefault("last_target_exposure", 0.0)
    s.setdefault("last_timestamp", None)

    qty = float(s.get("qty", 0.0) or 0.0)
    if "cost_basis" not in s or s.get("cost_basis") is None:
        # Backward-compatible migration for positions opened before cost-basis telemetry existed.
        # Use the sleeve's initial allocation as the best available starting basis.
        s["cost_basis"] = capital * weight if abs(qty) > 1e-12 else 0.0
        s["basis_source"] = "backfilled_initial_allocation" if abs(qty) > 1e-12 else "none"
    cost_basis = float(s.get("cost_basis", 0.0) or 0.0)
    s["avg_entry"] = cost_basis / qty if abs(qty) > 1e-12 and cost_basis > 0 else None


def load_state(path: Path, capital: float) -> dict[str, Any]:
    default_sleeves = {s.label: default_sleeve_state(capital, s.weight) for s in SELECTED_CORE_V1_SLEEVES}
    state = read_json(path, {})
    if not state:
        return {
            "version": STATE_VERSION,
            "scenario": SELECTED_CORE_V1_SCENARIO,
            "started_at": utc_now().isoformat(),
            "cycle": 0,
            "capital": capital,
            "sleeves": default_sleeves,
            "realized_pnl": 0.0,
            "realized_fees": 0.0,
            "realized_slippage": 0.0,
            "high_water_nav": capital,
        }

    state.setdefault("sleeves", {})
    for sleeve in SELECTED_CORE_V1_SLEEVES:
        s = state["sleeves"].setdefault(sleeve.label, default_sleeve_state(capital, sleeve.weight))
        migrate_sleeve_state(s, capital, sleeve.weight)

    state["version"] = STATE_VERSION
    state.setdefault("scenario", SELECTED_CORE_V1_SCENARIO)
    state.setdefault("capital", capital)
    state.setdefault("cycle", 0)
    state.setdefault("realized_pnl", 0.0)
    state.setdefault("realized_fees", 0.0)
    state.setdefault("realized_slippage", 0.0)
    state.setdefault("high_water_nav", capital)
    return state


def sleeve_nav(sleeve_state: dict[str, Any], price: float) -> float:
    return float(sleeve_state.get("cash", 0.0)) + float(sleeve_state.get("qty", 0.0)) * price


def apply_cash_yield(state: dict[str, Any], sleeve_label: str, sleeve_family: str, bil: pd.DataFrame) -> float:
    if sleeve_family not in ("equity", "gold"):
        return 0.0
    s = state["sleeves"][sleeve_label]
    last_ts = s.get("last_bil_yield_date")
    returns = bil["close"].pct_change().dropna()
    if returns.empty:
        return 0.0
    if last_ts:
        returns = returns.loc[returns.index > pd.Timestamp(last_ts)]
    if returns.empty:
        return 0.0
    growth = float((1.0 + returns).prod())
    cash_before = float(s.get("cash", 0.0))
    cash_yield = cash_before * (growth - 1.0)
    s["cash"] = cash_before * growth
    s["last_bil_yield_date"] = str(returns.index[-1].date())
    return cash_yield


def execute_paper_fill(
    state: dict[str, Any],
    sleeve_label: str,
    price: float,
    target_exposure: float,
    fee_rate: float,
    slippage_bps: float,
    min_delta: float,
) -> dict[str, Any] | None:
    s = state["sleeves"][sleeve_label]
    nav = sleeve_nav(s, price)
    if nav <= 0:
        return None

    current_qty = float(s.get("qty", 0.0) or 0.0)
    current_cost_basis = float(s.get("cost_basis", 0.0) or 0.0)
    current_value = current_qty * price
    current_exposure = current_value / nav
    delta_exposure = target_exposure - current_exposure
    if abs(delta_exposure) < min_delta:
        return None

    target_value = nav * target_exposure
    delta_value = target_value - current_value
    side = "BUY" if delta_value > 0 else "SELL"
    slip = slippage_bps / 10000.0
    fill_price = price * (1.0 + slip if side == "BUY" else 1.0 - slip)
    qty = abs(delta_value) / fill_price
    notional = qty * fill_price
    fee = notional * fee_rate
    realized_trade_pnl = 0.0
    sold_cost_basis = 0.0

    if side == "BUY":
        max_affordable = max(0.0, float(s.get("cash", 0.0))) / (fill_price * (1.0 + fee_rate))
        qty = min(qty, max_affordable)
        notional = qty * fill_price
        fee = notional * fee_rate
        s["qty"] = current_qty + qty
        s["cash"] = float(s.get("cash", 0.0)) - notional - fee
        s["cost_basis"] = current_cost_basis + notional + fee
    else:
        qty = min(qty, max(0.0, current_qty))
        notional = qty * fill_price
        fee = notional * fee_rate
        if current_qty > 0:
            sold_cost_basis = current_cost_basis * (qty / current_qty)
        realized_trade_pnl = notional - fee - sold_cost_basis
        remaining_qty = current_qty - qty
        remaining_cost_basis = max(0.0, current_cost_basis - sold_cost_basis)
        if remaining_qty < 1e-12:
            remaining_qty = 0.0
            remaining_cost_basis = 0.0
        s["qty"] = remaining_qty
        s["cash"] = float(s.get("cash", 0.0)) + notional - fee
        s["cost_basis"] = remaining_cost_basis
        s["realized_pnl"] = float(s.get("realized_pnl", 0.0)) + realized_trade_pnl
        state["realized_pnl"] = float(state.get("realized_pnl", 0.0)) + realized_trade_pnl

    new_qty = float(s.get("qty", 0.0) or 0.0)
    new_cost_basis = float(s.get("cost_basis", 0.0) or 0.0)
    s["avg_entry"] = new_cost_basis / new_qty if new_qty > 1e-12 and new_cost_basis > 0 else None

    slippage_cost = abs(qty * (fill_price - price))
    state["realized_fees"] = float(state.get("realized_fees", 0.0)) + fee
    state["realized_slippage"] = float(state.get("realized_slippage", 0.0)) + slippage_cost
    return {
        "side": side,
        "qty": qty,
        "price": fill_price,
        "mid": price,
        "notional": notional,
        "fee": fee,
        "slippage_cost": slippage_cost,
        "realized_pnl": realized_trade_pnl,
        "sold_cost_basis": sold_cost_basis,
        "cost_basis_after": s.get("cost_basis", 0.0),
        "avg_entry_after": s.get("avg_entry"),
    }


def mark_to_market(s: dict[str, Any], price: float) -> dict[str, float]:
    qty = float(s.get("qty", 0.0) or 0.0)
    cost_basis = float(s.get("cost_basis", 0.0) or 0.0)
    position_value = qty * price
    unrealized_pnl = position_value - cost_basis if qty > 1e-12 else 0.0
    return {
        "qty": qty,
        "cost_basis": cost_basis,
        "position_value": position_value,
        "avg_entry": cost_basis / qty if qty > 1e-12 and cost_basis > 0 else 0.0,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_return": unrealized_pnl / cost_basis if cost_basis > 0 else 0.0,
    }


def update_daily_pnl_state(state: dict[str, Any], total_nav: float) -> dict[str, Any]:
    today = utc_now().date().isoformat()
    previous_nav = float(state.get("last_total_nav") or state.get("capital") or total_nav)
    if state.get("day_start_date") != today:
        state["day_start_date"] = today
        state["day_start_nav"] = previous_nav
    day_start_nav = float(state.get("day_start_nav") or previous_nav)
    today_pnl = total_nav - day_start_nav
    today_return = today_pnl / day_start_nav if day_start_nav > 0 else 0.0
    state["today_pnl"] = today_pnl
    state["today_return"] = today_return
    return {"date": today, "day_start_nav": day_start_nav, "today_pnl": today_pnl, "today_return": today_return}


def run_cycle(args: argparse.Namespace) -> dict[str, Any]:
    validate_selected_allocation()
    state_path = Path(args.state_path)
    state = load_state(state_path, args.capital)
    data = load_market_data(args)

    signals: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []
    cash_yield_total = 0.0

    for sleeve in SELECTED_CORE_V1_SLEEVES:
        df = sleeve_dataframe(sleeve, data)
        price = latest_price(df)
        ts = df.index[-1]
        s_state = state["sleeves"][sleeve.label]
        cash_yield_total += apply_cash_yield(state, sleeve.label, sleeve.family, data["BIL"])
        nav_before = sleeve_nav(s_state, price)
        current_exposure = 0.0 if nav_before <= 0 else (float(s_state.get("qty", 0.0)) * price / nav_before)
        previous_action = s_state.get("last_action")
        regime = classify_regime(df)
        ctx = StrategyContext(regime=regime, current_exposure_frac=current_exposure, asset=sleeve.asset, bar_index=len(df) - 1)
        strategy = STRATEGY_REGISTRY[sleeve.strategy]
        intent = strategy.generate_intent(df, ctx, closed_only=True)
        action = intent.action.value if hasattr(intent.action, "value") else str(intent.action)
        target_exposure = max(0.0, min(1.0, float(intent.desired_exposure_frac)))
        fee_rate = args.equity_fee if sleeve.family in ("equity", "gold") else args.fee
        slippage_bps = args.equity_slippage_bps if sleeve.family in ("equity", "gold") else args.crypto_slippage_bps
        fill = execute_paper_fill(
            state,
            sleeve.label,
            price,
            target_exposure,
            fee_rate,
            slippage_bps,
            args.rebalance_threshold,
        )
        nav_after = sleeve_nav(state["sleeves"][sleeve.label], price)
        mtm = mark_to_market(state["sleeves"][sleeve.label], price)
        state["sleeves"][sleeve.label]["last_action"] = action
        state["sleeves"][sleeve.label]["last_price"] = price
        state["sleeves"][sleeve.label]["last_target_exposure"] = target_exposure
        state["sleeves"][sleeve.label]["last_timestamp"] = str(ts)
        row = {
            "sleeve": sleeve.label,
            "family": sleeve.family,
            "asset": sleeve.asset,
            "timeframe": sleeve.timeframe,
            "strategy": sleeve.strategy,
            "allocation_weight": sleeve.weight,
            "bar_timestamp": str(ts),
            "price": price,
            "regime": regime.value,
            "action": action,
            "previous_action": previous_action,
            "action_changed": previous_action is not None and previous_action != action,
            "confidence": float(intent.confidence),
            "target_exposure": target_exposure,
            "current_exposure_before": current_exposure,
            "nav_before": nav_before,
            "nav_after": nav_after,
            "position_value": mtm["position_value"],
            "cost_basis": mtm["cost_basis"],
            "avg_entry": mtm["avg_entry"],
            "unrealized_pnl": mtm["unrealized_pnl"],
            "unrealized_return": mtm["unrealized_return"],
            "realized_pnl": float(state["sleeves"][sleeve.label].get("realized_pnl", 0.0)),
            "reason": intent.reason,
            "meta": intent.meta,
            "fill": fill,
        }
        signals.append(row)
        if fill:
            fills.append({**fill, "sleeve": sleeve.label, "asset": sleeve.asset, "timestamp": utc_now().isoformat()})

    sleeve_navs: dict[str, float] = {}
    sleeve_telemetry: dict[str, dict[str, float]] = {}
    for sleeve in SELECTED_CORE_V1_SLEEVES:
        price = float(state["sleeves"][sleeve.label].get("last_price") or latest_price(data[sleeve.asset]))
        sleeve_navs[sleeve.label] = sleeve_nav(state["sleeves"][sleeve.label], price)
        sleeve_telemetry[sleeve.label] = mark_to_market(state["sleeves"][sleeve.label], price)

    total_nav = float(sum(sleeve_navs.values()))
    total_cash = float(sum(float(state["sleeves"][s.label].get("cash", 0.0)) for s in SELECTED_CORE_V1_SLEEVES))
    total_position_value = float(sum(v["position_value"] for v in sleeve_telemetry.values()))
    total_cost_basis = float(sum(v["cost_basis"] for v in sleeve_telemetry.values()))
    unrealized_pnl = float(sum(v["unrealized_pnl"] for v in sleeve_telemetry.values()))
    daily_pnl = update_daily_pnl_state(state, total_nav)
    hwm = max(float(state.get("high_water_nav", args.capital)), total_nav)
    state["high_water_nav"] = hwm
    state["cycle"] = int(state.get("cycle", 0)) + 1
    state["last_cycle_at"] = utc_now().isoformat()
    state["last_total_nav"] = total_nav
    state["drawdown_frac"] = 0.0 if hwm <= 0 else total_nav / hwm - 1.0
    state["sleeve_navs"] = sleeve_navs
    state["sleeve_telemetry"] = sleeve_telemetry
    state["total_cash"] = total_cash
    state["total_position_value"] = total_position_value
    state["total_cost_basis"] = total_cost_basis
    state["unrealized_pnl"] = unrealized_pnl
    state["open_position_count"] = int(sum(1 for v in sleeve_telemetry.values() if abs(v["qty"]) > 1e-12))
    write_json_atomic(state_path, state)

    event = {
        "timestamp": state["last_cycle_at"],
        "version": STATE_VERSION,
        "scenario": SELECTED_CORE_V1_SCENARIO,
        "cycle": state["cycle"],
        "total_nav": total_nav,
        "drawdown_frac": state["drawdown_frac"],
        "cash_yield_applied": cash_yield_total,
        "sleeve_navs": sleeve_navs,
        "sleeve_telemetry": sleeve_telemetry,
        "signals": signals,
        "fills": fills,
        "today_pnl": daily_pnl["today_pnl"],
        "today_return": daily_pnl["today_return"],
        "cash_total": total_cash,
        "position_value_total": total_position_value,
        "cost_basis_total": total_cost_basis,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": state.get("realized_pnl", 0.0),
        "fees_total": state.get("realized_fees", 0.0),
        "slippage_total": state.get("realized_slippage", 0.0),
    }
    append_jsonl(Path(args.signals_log), event)
    for fill in fills:
        append_jsonl(Path(args.fills_log), fill)
    return event


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Selected Core v1 investigative paper trader")
    p.add_argument("--capital", type=float, default=float(os.getenv("CORE_V1_CAPITAL", "100000")))
    p.add_argument("--poll", type=int, default=int(os.getenv("CORE_V1_POLL_SECONDS", "3600")))
    p.add_argument("--max-cycles", type=int, default=None)
    p.add_argument("--state-path", default=os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
    p.add_argument("--signals-log", default=os.getenv("CORE_V1_SIGNALS_LOG", "/opt/itera/logs/core_v1_signals.jsonl"))
    p.add_argument("--fills-log", default=os.getenv("CORE_V1_FILLS_LOG", "/opt/itera/logs/core_v1_fills.jsonl"))
    p.add_argument("--data-dir", default=os.getenv("DATA_DIR", "data"))
    p.add_argument("--crypto-days", type=int, default=int(os.getenv("CORE_V1_CRYPTO_DAYS", "420")))
    p.add_argument("--etf-days", type=int, default=int(os.getenv("CORE_V1_ETF_DAYS", "520")))
    p.add_argument("--fee", type=float, default=float(os.getenv("FEE_RATE", "0.0006")))
    p.add_argument("--equity-fee", type=float, default=float(os.getenv("EQUITY_FEE_RATE", "0.0001")))
    p.add_argument("--crypto-slippage-bps", type=float, default=float(os.getenv("CORE_V1_CRYPTO_SLIPPAGE_BPS", "3.0")))
    p.add_argument("--equity-slippage-bps", type=float, default=float(os.getenv("CORE_V1_EQUITY_SLIPPAGE_BPS", "0.5")))
    p.add_argument("--rebalance-threshold", type=float, default=float(os.getenv("REBALANCE_THRESHOLD", "0.02")))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cycles = 0
    while True:
        try:
            event = run_cycle(args)
            print(
                f"{event['timestamp']} Core v1 cycle={event['cycle']} NAV=${event['total_nav']:,.2f} "
                f"DD={event['drawdown_frac']:.2%} today={event['today_pnl']:+,.2f} fills={len(event['fills'])}",
                flush=True,
            )
            for s in event["signals"]:
                changed = " changed" if s.get("action_changed") else ""
                print(
                    f"  {s['sleeve']}: {s['action']}{changed} target={s['target_exposure']:.3f} "
                    f"price={s['price']:.2f} regime={s['regime']} uPnL={s['unrealized_pnl']:+,.2f} | {s['reason']}",
                    flush=True,
                )
        except Exception as e:
            err = {"timestamp": utc_now().isoformat(), "error": str(e), "version": STATE_VERSION}
            append_jsonl(Path(args.signals_log).with_name("core_v1_errors.jsonl"), err)
            print(f"ERROR Core v1 cycle failed: {e}", file=sys.stderr, flush=True)
            raise

        cycles += 1
        if args.max_cycles is not None and cycles >= args.max_cycles:
            break
        time.sleep(args.poll)


if __name__ == "__main__":
    main()
