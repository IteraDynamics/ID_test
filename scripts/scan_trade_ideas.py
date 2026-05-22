#!/usr/bin/env python
"""Trade idea radar scanner.

Console-first scanner for actionable, risk-defined trade candidates.

This is not a sleeve backtest and not a research memo generator. It scans the
available local market data, identifies active or near-active setups, ranks them,
and writes a simple trade blotter.

Research/paper only. No runtime, broker, or live execution code is modified.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from scripts.run_state_confirmed_risk_off_sweep import _load_close


DEFAULT_UNIVERSE = [
    "QQQ", "SMH", "XLK", "IGV", "XLC",
    "SPY", "RSP", "MTUM", "QUAL", "IWF", "IWM",
    "USMV", "SPLV", "SCHD",
    "TLT", "IEF", "GLD", "XLE", "XLF",
    "BTC-USD", "ETH-USD",
]

CRYPTO_FILE_MAP = {
    "BTC-USD": "BTC-USD_1D.csv",
    "ETH-USD": "ETH-USD_1D.csv",
}

BUCKETS = {
    "growth_risk_on": {"QQQ", "SMH", "XLK", "IGV", "XLC", "MTUM", "IWF", "IWM"},
    "defensive_quality": {"USMV", "SPLV", "SCHD", "QUAL", "RSP", "SPY"},
    "macro_rates_commodities": {"TLT", "IEF", "GLD", "XLE", "XLF"},
    "crypto": {"BTC-USD", "ETH-USD"},
}

BUCKET_ORDER = ["growth_risk_on", "macro_rates_commodities", "defensive_quality", "crypto", "other"]


@dataclass
class TradeIdea:
    ticker: str
    bucket: str
    trade_type: str
    direction: str
    setup: str
    status: str
    priority: str
    score: float
    confidence: str
    close: float
    trigger: float
    distance_to_trigger_pct: float
    stop: float
    channel_stop: float | None
    wide_stop: float | None
    target: float
    r_multiple: float
    horizon_days: int
    setup_age_days: int | None
    vol_rank: float | None
    ret_20d_pct: float | None
    ret_63d_pct: float | None
    ret_126d_pct: float | None
    trend_state: str
    why: str
    invalidation: str


def _bucket_for(ticker: str) -> str:
    for bucket, tickers in BUCKETS.items():
        if ticker in tickers:
            return bucket
    return "other"


def _trade_type_for(ticker: str, setup: str) -> str:
    bucket = _bucket_for(ticker)
    if bucket == "macro_rates_commodities":
        return "macro_tactical"
    if bucket == "crypto":
        return "crypto_tactical"
    if bucket == "defensive_quality":
        return "defensive_confirmation" if setup != "trend_reclaim" else "defensive_repair"
    if bucket == "growth_risk_on":
        return "growth_breakout" if "breakout" in setup else "growth_momentum"
    return "tactical"


def _priority(score: float, status: str, bucket: str) -> str:
    if status == "active" and score >= 80:
        return "A"
    if status in {"active", "trigger_watch_1pct"} and score >= 70:
        return "B"
    if bucket == "defensive_quality" and score >= 80:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def _bucket_score_adjustment(ticker: str, setup: str) -> float:
    bucket = _bucket_for(ticker)
    if bucket == "growth_risk_on":
        return 6.0
    if bucket == "crypto":
        return 4.0
    if bucket == "macro_rates_commodities":
        return 0.0
    if bucket == "defensive_quality":
        # Valid context signals, but should not crowd out higher-torque ideas.
        return -8.0 if setup == "vol_compression_breakout" else -4.0
    return 0.0


def _fmt_pct(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"{v:.2f}%"


def _fmt_price(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"{v:,.2f}"


def _data_path(data_dir: Path, ticker: str) -> Path:
    if ticker in CRYPTO_FILE_MAP:
        return data_dir / CRYPTO_FILE_MAP[ticker]
    return data_dir / f"{ticker}_1D.csv"


def _load_universe(data_dir: Path, tickers: list[str], start: str, end: str) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for ticker in tickers:
        path = _data_path(data_dir, ticker)
        if not path.exists():
            continue
        try:
            out[ticker] = _load_close(str(path), ticker, start, end).dropna()
        except Exception as exc:  # pragma: no cover - scanner should keep going.
            print(f"WARN: failed to load {ticker} from {path}: {exc}", file=sys.stderr)
    return out


def _last(series: pd.Series, default: float | None = None) -> float | None:
    s = series.dropna()
    if s.empty:
        return default
    return float(s.iloc[-1])


def _ret(close: pd.Series, days: int) -> float | None:
    if len(close.dropna()) <= days:
        return None
    value = close.iloc[-1] / close.iloc[-days - 1] - 1.0
    return float(value * 100.0)


def _trend_state(close: pd.Series) -> str:
    sma50 = _last(close.rolling(50, min_periods=50).mean())
    sma200 = _last(close.rolling(200, min_periods=200).mean())
    px = _last(close)
    if px is None or sma50 is None or sma200 is None:
        return "unknown"
    if px > sma50 > sma200:
        return "strong_uptrend"
    if px > sma200:
        return "uptrend"
    if px > sma50 and px < sma200:
        return "repairing"
    return "downtrend"


def _r_multiple(entry: float, stop: float, target: float) -> float:
    risk = max(entry - stop, 1e-12)
    reward = target - entry
    return float(reward / risk)


def _vol_rank(close: pd.Series, vol_window: int, rank_window: int) -> pd.Series:
    rets = close.pct_change(fill_method=None).fillna(0.0)
    vol = rets.rolling(vol_window, min_periods=vol_window).std() * math.sqrt(252.0)
    return vol.rolling(rank_window, min_periods=rank_window).rank(pct=True)


def _confidence(score: float) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def _status_from_distance(distance_pct: float, active_if_above: bool = True) -> str:
    if active_if_above and distance_pct <= 0:
        return "active"
    if 0 < distance_pct <= 1.0:
        return "trigger_watch_1pct"
    if 1.0 < distance_pct <= 3.0:
        return "near_trigger_3pct"
    return "watch"


def _score_common(status: str, trend: str, distance_pct: float, vol_rank_value: float | None) -> float:
    score = 35.0
    if status == "active":
        score += 25
    elif status == "trigger_watch_1pct":
        score += 18
    elif status == "near_trigger_3pct":
        score += 10
    if trend == "strong_uptrend":
        score += 15
    elif trend == "uptrend":
        score += 9
    elif trend == "repairing":
        score += 3
    else:
        score -= 8
    if vol_rank_value is not None:
        if vol_rank_value <= 0.20:
            score += 15
        elif vol_rank_value <= 0.30:
            score += 10
        elif vol_rank_value >= 0.80:
            score -= 8
    score -= min(max(distance_pct, 0.0), 10.0) * 1.5
    return max(0.0, min(100.0, score))


def _make_idea(
    *,
    ticker: str,
    setup: str,
    status: str,
    score: float,
    close: float,
    trigger: float,
    stop: float,
    channel_stop: float | None,
    wide_stop: float | None,
    horizon_days: int,
    setup_age_days: int | None,
    vol_rank_value: float | None,
    close_series: pd.Series,
    why: str,
    invalidation: str,
) -> TradeIdea:
    score = max(0.0, min(100.0, score + _bucket_score_adjustment(ticker, setup)))
    risk = max(close - stop, close * 0.01)
    target = close + 2.0 * risk
    bucket = _bucket_for(ticker)
    trade_type = _trade_type_for(ticker, setup)
    return TradeIdea(
        ticker=ticker,
        bucket=bucket,
        trade_type=trade_type,
        direction="LONG",
        setup=setup,
        status=status,
        priority=_priority(score, status, bucket),
        score=round(score, 2),
        confidence=_confidence(score),
        close=round(close, 4),
        trigger=round(trigger, 4),
        distance_to_trigger_pct=round((trigger / close - 1.0) * 100.0, 3),
        stop=round(stop, 4),
        channel_stop=None if channel_stop is None else round(channel_stop, 4),
        wide_stop=None if wide_stop is None else round(wide_stop, 4),
        target=round(target, 4),
        r_multiple=round(_r_multiple(close, stop, target), 2),
        horizon_days=horizon_days,
        setup_age_days=setup_age_days,
        vol_rank=None if vol_rank_value is None else round(vol_rank_value, 4),
        ret_20d_pct=None if _ret(close_series, 20) is None else round(float(_ret(close_series, 20)), 3),
        ret_63d_pct=None if _ret(close_series, 63) is None else round(float(_ret(close_series, 63)), 3),
        ret_126d_pct=None if _ret(close_series, 126) is None else round(float(_ret(close_series, 126)), 3),
        trend_state=_trend_state(close_series),
        why=why,
        invalidation=invalidation,
    )


def scan_vol_compression_breakout(close: pd.Series, ticker: str, args: argparse.Namespace) -> list[TradeIdea]:
    ideas: list[TradeIdea] = []
    if len(close) < max(args.vol_rank_window + args.vol_window, args.channel_window + 5, 220):
        return ideas
    px = float(close.iloc[-1])
    rank = _vol_rank(close, args.vol_window, args.vol_rank_window)
    compressed = rank <= args.compression_pctile
    compression_recent = compressed.rolling(args.compression_memory, min_periods=1).max().fillna(0).astype(bool)
    high = close.shift(1).rolling(args.channel_window, min_periods=args.channel_window).max()
    low = close.shift(1).rolling(args.channel_window, min_periods=args.channel_window).min()
    trigger = _last(high)
    channel_low = _last(low)
    vr = _last(rank)
    if trigger is None or channel_low is None:
        return ideas
    distance = (trigger / px - 1.0) * 100.0
    recent = bool(compression_recent.iloc[-1])
    if not recent and distance > args.near_trigger_pct:
        return ideas
    if distance > args.near_trigger_pct:
        return ideas
    status = _status_from_distance(distance)
    trend = _trend_state(close)
    score = _score_common(status, trend, distance, vr)
    if recent:
        score += 8
    channel_stop = float(channel_low)
    wide_stop = px * (1.0 - args.default_stop_pct)
    stop = max(channel_stop, wide_stop) if args.prefer_tighter_stop else min(channel_stop, wide_stop)
    ideas.append(
        _make_idea(
            ticker=ticker,
            setup="vol_compression_breakout",
            status=status,
            score=score,
            close=px,
            trigger=float(trigger),
            stop=float(stop),
            channel_stop=channel_stop,
            wide_stop=wide_stop,
            horizon_days=args.breakout_horizon_days,
            setup_age_days=None,
            vol_rank_value=vr,
            close_series=close,
            why=(
                f"Vol rank {_fmt_pct(None if vr is None else vr * 100)}; "
                f"compression_recent={recent}; price is {_fmt_pct(distance)} from {args.channel_window}d breakout."
            ),
            invalidation=(
                f"Channel stop {_fmt_price(channel_stop)}; wide stop {_fmt_price(wide_stop)}; "
                f"selected stop {_fmt_price(stop)}."
            ),
        )
    )
    return ideas


def scan_momentum_continuation(close: pd.Series, ticker: str, args: argparse.Namespace) -> list[TradeIdea]:
    ideas: list[TradeIdea] = []
    if len(close) < 220:
        return ideas
    px = float(close.iloc[-1])
    high20 = _last(close.shift(1).rolling(20, min_periods=20).max())
    low20 = _last(close.shift(1).rolling(20, min_periods=20).min())
    sma50 = _last(close.rolling(50, min_periods=50).mean())
    sma200 = _last(close.rolling(200, min_periods=200).mean())
    if high20 is None or low20 is None or sma50 is None or sma200 is None:
        return ideas
    r20 = _ret(close, 20) or 0.0
    r63 = _ret(close, 63) or 0.0
    if not (px > sma50 > sma200 and r20 > 0 and r63 > 0):
        return ideas
    distance = (high20 / px - 1.0) * 100.0
    if distance > args.near_trigger_pct:
        return ideas
    status = _status_from_distance(distance)
    score = _score_common(status, _trend_state(close), distance, None) + min(max(r63, 0.0), 25.0) * 0.7
    channel_stop = float(low20)
    wide_stop = px * (1.0 - args.default_stop_pct)
    stop = max(channel_stop, wide_stop) if args.prefer_tighter_stop else min(channel_stop, wide_stop)
    ideas.append(
        _make_idea(
            ticker=ticker,
            setup="momentum_continuation",
            status=status,
            score=score,
            close=px,
            trigger=float(high20),
            stop=float(stop),
            channel_stop=channel_stop,
            wide_stop=wide_stop,
            horizon_days=args.momentum_horizon_days,
            setup_age_days=None,
            vol_rank_value=None,
            close_series=close,
            why=f"Strong trend: close > SMA50 > SMA200; 20d return {_fmt_pct(r20)}, 63d return {_fmt_pct(r63)}.",
            invalidation=(
                f"Channel stop {_fmt_price(channel_stop)}; wide stop {_fmt_price(wide_stop)}; "
                f"loss of SMA50 support invalidates continuation."
            ),
        )
    )
    return ideas


def scan_trend_reclaim(close: pd.Series, ticker: str, args: argparse.Namespace) -> list[TradeIdea]:
    ideas: list[TradeIdea] = []
    if len(close) < 220:
        return ideas
    px = float(close.iloc[-1])
    sma200 = close.rolling(200, min_periods=200).mean()
    current_sma = _last(sma200)
    if current_sma is None:
        return ideas
    was_below_recently = bool(((close.shift(1) < sma200.shift(1)).tail(args.reclaim_lookback_days)).any())
    reclaimed = px > current_sma and was_below_recently
    distance = (current_sma / px - 1.0) * 100.0
    near_reclaim = abs(distance) <= args.near_reclaim_pct
    if not (reclaimed or near_reclaim):
        return ideas
    status = "active" if reclaimed else "reclaim_watch"
    r63 = _ret(close, 63) or 0.0
    score = 55.0 + (10.0 if reclaimed else 0.0) + min(max(r63, -10.0), 20.0) * 0.5
    wide_stop = px * (1.0 - args.default_stop_pct)
    stop = max(float(current_sma), wide_stop) if args.prefer_tighter_stop else wide_stop
    ideas.append(
        _make_idea(
            ticker=ticker,
            setup="trend_reclaim",
            status=status,
            score=score,
            close=px,
            trigger=float(current_sma),
            stop=float(stop),
            channel_stop=float(current_sma),
            wide_stop=wide_stop,
            horizon_days=args.reclaim_horizon_days,
            setup_age_days=None,
            vol_rank_value=None,
            close_series=close,
            why=f"Price is reclaiming/near SMA200 after trading below it in the prior {args.reclaim_lookback_days} days.",
            invalidation=f"Failed SMA200 reclaim or close below selected stop {_fmt_price(stop)}.",
        )
    )
    return ideas


def _sort_key(idea: TradeIdea) -> tuple[int, float, float]:
    priority_rank = {"A": 4, "B": 3, "C": 2, "D": 1}.get(idea.priority, 0)
    return (priority_rank, idea.score, -abs(idea.distance_to_trigger_pct))


def scan_all(prices: dict[str, pd.Series], args: argparse.Namespace) -> list[TradeIdea]:
    ideas: list[TradeIdea] = []
    for ticker, close in prices.items():
        close = close.dropna()
        ideas.extend(scan_vol_compression_breakout(close, ticker, args))
        ideas.extend(scan_momentum_continuation(close, ticker, args))
        ideas.extend(scan_trend_reclaim(close, ticker, args))
    return sorted(ideas, key=_sort_key, reverse=True)


def _print_section(title: str, ideas: list[TradeIdea], limit: int) -> None:
    print("-" * 182)
    print(f"  {title}")
    print("-" * 182)
    print(
        f"  {'#':>3} {'Ticker':<8} {'Type':<22} {'Setup':<27} {'Status':<18} {'Pri':<3} {'Score':>7} "
        f"{'Close':>10} {'Trigger':>10} {'Dist%':>8} {'Stop':>10} {'ChanStop':>10} {'Target':>10} {'R':>5}"
    )
    if not ideas:
        print("  No ideas in this bucket.")
        return
    for i, idea in enumerate(ideas[:limit], start=1):
        print(
            f"  {i:>3} {idea.ticker:<8} {idea.trade_type:<22} {idea.setup:<27} {idea.status:<18} {idea.priority:<3} "
            f"{idea.score:>7.1f} {_fmt_price(idea.close):>10} {_fmt_price(idea.trigger):>10} {_fmt_pct(idea.distance_to_trigger_pct):>8} "
            f"{_fmt_price(idea.stop):>10} {_fmt_price(idea.channel_stop):>10} {_fmt_price(idea.target):>10} {idea.r_multiple:>5.1f}"
        )
        print(f"      Why: {idea.why}")
        print(f"      Invalid: {idea.invalidation}")


def print_ideas(ideas: list[TradeIdea], limit: int, per_bucket: int) -> None:
    print("=" * 182)
    print("  TRADE IDEA RADAR — BUCKETED DESK VIEW")
    print("=" * 182)
    print("  Best overall:")
    _print_section("OVERALL TOP IDEAS", ideas, limit)
    for bucket in BUCKET_ORDER:
        bucket_ideas = [x for x in ideas if x.bucket == bucket]
        if bucket_ideas:
            _print_section(bucket.upper().replace("_", " "), bucket_ideas, per_bucket)
    print("=" * 182)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scan local market data for trade ideas")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--tickers", nargs="+", default=DEFAULT_UNIVERSE)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--top-n", type=int, default=15)
    p.add_argument("--per-bucket", type=int, default=8)
    p.add_argument("--out-dir", default="artifacts/trade_idea_radar")
    p.add_argument("--near-trigger-pct", type=float, default=3.0)
    p.add_argument("--near-reclaim-pct", type=float, default=1.5)
    p.add_argument("--default-stop-pct", type=float, default=0.08)
    p.add_argument("--prefer-tighter-stop", action="store_true", default=True)
    p.add_argument("--vol-window", type=int, default=20)
    p.add_argument("--vol-rank-window", type=int, default=90)
    p.add_argument("--compression-pctile", type=float, default=0.30)
    p.add_argument("--compression-memory", type=int, default=10)
    p.add_argument("--channel-window", type=int, default=20)
    p.add_argument("--breakout-horizon-days", type=int, default=20)
    p.add_argument("--momentum-horizon-days", type=int, default=20)
    p.add_argument("--reclaim-horizon-days", type=int, default=30)
    p.add_argument("--reclaim-lookback-days", type=int, default=30)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    prices = _load_universe(data_dir, args.tickers, args.start, args.end)
    if not prices:
        raise SystemExit(f"No data files found in {data_dir} for requested tickers")
    ideas = scan_all(prices, args)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = [asdict(x) for x in ideas]
    pd.DataFrame(rows).to_csv(out / "trade_ideas.csv", index=False)
    (out / "trade_ideas.json").write_text(json.dumps({"config": vars(args), "ideas": rows}, indent=2), encoding="utf-8")
    print_ideas(ideas, args.top_n, args.per_bucket)
    print(f"  Scanned : {len(prices)} tickers")
    print(f"  Ideas   : {len(ideas)}")
    print(f"  CSV     : {out / 'trade_ideas.csv'}")
    print(f"  JSON    : {out / 'trade_ideas.json'}")
    print("  Verdict : trade radar only; review before any execution.\n")


if __name__ == "__main__":
    main()
