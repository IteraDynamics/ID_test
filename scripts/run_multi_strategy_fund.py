#!/usr/bin/env python
"""IteraDynamics — Multi-Strategy Fund Runner.

Three complementary strategy families on independent capital pools:

  Trend sleeve   (default 60%)  — BTC/ETH × 1H/4H, trend_following_v8_ecap60_add80
                                   The primary compounding engine. Active during
                                   TREND_UP and VOL_COMPRESSION regimes.

  Hedge sleeve   (default 20%)  — BTC/ETH × 1H, crash_short_v2
                                   Short-only crash hedge. Active only during
                                   confirmed TREND_DOWN + macro drawdown > 20%.
                                   Sits in cash otherwise (opportunity cost is
                                   the price of tail protection).

  MR sleeve      (default 20%)  — BTC/ETH × 1H, mean_reversion
                                   Counter-trend satellite. Active in RANGE and
                                   VOL_COMPRESSION regimes when RSI/BB are
                                   oversold. Reduces equity curve variance during
                                   consolidation periods when trend is flat.

Each sub-sleeve runs on its own capital bucket through the full backtest engine
with realistic costs (taker fees + dynamic slippage + spread). Combined NAV is
the sum of all sub-sleeve NAVs.

Usage
-----
# BTC only (no ETH data):
python scripts/run_multi_strategy_fund.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv

# BTC + ETH, full period:
python scripts/run_multi_strategy_fund.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv

# Custom sleeve weights (must sum to 1.0):
python scripts/run_multi_strategy_fund.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --trend-weight 0.65 --hedge-weight 0.20 --mr-weight 0.15

# OOS-only window:
python scripts/run_multi_strategy_fund.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --start 2021-01-01 --end 2024-12-31

PowerShell:
python scripts\\run_multi_strategy_fund.py `
    --btc-data data\\btcusd_3600s_2019-01-01_to_2025-12-30.csv `
    --eth-data data\\ethusd_3600s_2019-01-01_to_2025-12-30.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("multi_strategy_fund")

import numpy as np
import pandas as pd

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.resampler import resample_ohlcv, align_equity_curves
from research.harness.backtest_engine import run_backtest, BacktestResult
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import compute_metrics, BacktestMetrics
from research.strategies import REGISTRY as STRATEGY_REGISTRY

TREND_STRATEGY   = "trend_following_v8_ecap60_add80"
HEDGE_STRATEGY   = "crash_short_v4"
MR_STRATEGY      = "mean_reversion"
EQUITY_STRATEGY  = "equity_sma175"


# ── Sleeve definition ──────────────────────────────────────────────────────────

@dataclass
class SleeveSpec:
    label: str
    family: str        # "trend" | "hedge" | "mr"
    asset: str         # "BTC" | "ETH"
    timeframe: str     # "1H" | "4H"
    strategy: str      # key in STRATEGY_REGISTRY
    capital: float     # absolute USD allocation


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Multi-strategy fund: trend + hedge + mean-reversion",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True,
                   help="Path to BTC hourly OHLCV CSV")
    p.add_argument("--eth-data", default=None,
                   help="Path to ETH hourly OHLCV CSV (optional; omit for BTC-only)")
    p.add_argument("--spy-data", default=None,
                   help="Path to SPY daily OHLCV CSV (enables equity sleeve)")
    p.add_argument("--qqq-data", default=None,
                   help="Path to QQQ daily OHLCV CSV (optional; SPY-only if omitted)")
    p.add_argument("--bil-data", default=None,
                   help="Path to BIL daily OHLCV CSV (cash yield for idle equity capital)")
    p.add_argument("--capital", type=float, default=100_000.0,
                   help="Total fund capital (USD)")
    p.add_argument("--trend-weight", type=float, default=0.60,
                   help="Fraction of capital to trend sleeve")
    p.add_argument("--hedge-weight", type=float, default=0.20,
                   help="Fraction of capital to crash-hedge sleeve")
    p.add_argument("--mr-weight", type=float, default=0.20,
                   help="Fraction of capital to mean-reversion sleeve")
    p.add_argument("--equity-weight", type=float, default=0.0,
                   help="Fraction of capital to equity SMA175 sleeve (requires --spy-data)")
    p.add_argument("--start", default=None,
                   help="Backtest start date YYYY-MM-DD (default: data start)")
    p.add_argument("--end", default=None,
                   help="Backtest end date YYYY-MM-DD (default: data end)")
    # Cost model
    p.add_argument("--fee", type=float, default=0.0006,
                   help="Taker fee rate for crypto (default 6 bps)")
    p.add_argument("--equity-fee", type=float, default=0.0001,
                   help="Taker fee rate for equity ETFs (default 1 bp)")
    p.add_argument("--base-slippage", type=float, default=3.0,
                   help="Base slippage bps (crypto)")
    p.add_argument("--slippage-vol-factor", type=float, default=50.0,
                   help="Slippage bps per unit of ATR%% (crypto)")
    p.add_argument("--cooldown", type=int, default=2,
                   help="Cooldown bars between trades (trend/hedge sleeves)")
    p.add_argument("--mr-cooldown", type=int, default=12,
                   help="Cooldown bars for MR sleeves (matches 12H horizon)")
    p.add_argument("--rebalance-threshold", type=float, default=0.02,
                   help="Minimum exposure delta to trigger a trade")
    # Output
    p.add_argument("--out-dir", default="artifacts/multi_strategy_fund",
                   help="Output directory for artifacts")
    p.add_argument("--label", default="",
                   help="Optional label suffix for output files")
    return p.parse_args()


# ── Sleeve construction ────────────────────────────────────────────────────────

def _build_sleeves(args: argparse.Namespace) -> list[SleeveSpec]:
    ew = getattr(args, "equity_weight", 0.0)
    total_w = args.trend_weight + args.hedge_weight + args.mr_weight + ew
    if abs(total_w - 1.0) > 0.001:
        log.warning("Sleeve weights sum to %.4f — normalising to 1.0", total_w)
    tw = args.trend_weight / total_w
    hw = args.hedge_weight / total_w
    mw = args.mr_weight    / total_w
    eqw = ew / total_w

    has_eth = bool(args.eth_data)
    has_spy = bool(getattr(args, "spy_data", None))
    has_qqq = bool(getattr(args, "qqq_data", None))
    cap = args.capital

    # Trend: BTC 1H + 4H + (ETH 1H + 4H if available), equal sub-weight
    trend_assets = ["BTC", "BTC"] + (["ETH", "ETH"] if has_eth else [])
    trend_tfs    = ["1H",  "4H"]  + (["1H",  "4H"]  if has_eth else [])
    n_trend = len(trend_assets)
    trend_sub_w = 1.0 / n_trend

    sleeves: list[SleeveSpec] = []
    for asset, tf in zip(trend_assets, trend_tfs):
        sleeves.append(SleeveSpec(
            label=f"{asset}_{tf}_trend",
            family="trend",
            asset=asset,
            timeframe=tf,
            strategy=TREND_STRATEGY,
            capital=cap * tw * trend_sub_w,
        ))

    # Hedge: BTC 1H + (ETH 1H if available), equal sub-weight
    hedge_assets = ["BTC"] + (["ETH"] if has_eth else [])
    n_hedge = len(hedge_assets)
    hedge_sub_w = 1.0 / n_hedge
    for asset in hedge_assets:
        sleeves.append(SleeveSpec(
            label=f"{asset}_1H_hedge",
            family="hedge",
            asset=asset,
            timeframe="1H",
            strategy=HEDGE_STRATEGY,
            capital=cap * hw * hedge_sub_w,
        ))

    # MR: BTC 1H + (ETH 1H if available), equal sub-weight
    mr_assets = ["BTC"] + (["ETH"] if has_eth else [])
    n_mr = len(mr_assets)
    mr_sub_w = 1.0 / n_mr
    for asset in mr_assets:
        sleeves.append(SleeveSpec(
            label=f"{asset}_1H_mr",
            family="mr",
            asset=asset,
            timeframe="1H",
            strategy=MR_STRATEGY,
            capital=cap * mw * mr_sub_w,
        ))

    # Equity: SPY + QQQ daily (only if equity data provided and weight > 0)
    if eqw > 0:
        equity_assets = (["SPY"] if has_spy else []) + (["QQQ"] if has_qqq else [])
        if not equity_assets:
            log.warning("--equity-weight %.2f set but no equity data provided — skipping equity sleeve", eqw)
        else:
            eq_sub_w = 1.0 / len(equity_assets)
            for asset in equity_assets:
                sleeves.append(SleeveSpec(
                    label=f"{asset}_1D_equity",
                    family="equity",
                    asset=asset,
                    timeframe="1D",
                    strategy=EQUITY_STRATEGY,
                    capital=cap * eqw * eq_sub_w,
                ))

    return sleeves


# ── Data loading ───────────────────────────────────────────────────────────────

def _load_asset(path: str, asset: str, start: str | None, end: str | None) -> pd.DataFrame:
    df = load_ohlcv(path)
    validate_ohlcv(df)
    if start:
        df = df.loc[start:]
    if end:
        df = df.loc[:end]
    if df.empty:
        raise ValueError(f"No {asset} data in range {start}–{end}")
    log.info("%s: %d bars  %s → %s", asset, len(df), df.index[0], df.index[-1])
    return df


def _sleeve_df(raw: dict[str, pd.DataFrame], spec: SleeveSpec) -> pd.DataFrame:
    df = raw[spec.asset]
    if spec.timeframe.upper() == "4H":
        return resample_ohlcv(df, "4h")
    return df


# ── Run one sleeve ─────────────────────────────────────────────────────────────

def _run_sleeve(
    spec: SleeveSpec,
    df: pd.DataFrame,
    exec_config: ExecutionConfig,
    rebalance_threshold: float,
    cash_yield_series: "pd.Series | None" = None,
) -> BacktestResult:
    strategy = STRATEGY_REGISTRY[spec.strategy]
    log.info("Running %s  strategy=%s  capital=$%.0f",
             spec.label, spec.strategy, spec.capital)
    return run_backtest(
        df=df,
        strategy_module=strategy,
        initial_capital=spec.capital,
        exec_config=exec_config,
        asset=spec.asset,
        rebalance_threshold=rebalance_threshold,
        cash_yield_series=cash_yield_series,
    )


# ── Combine equity curves ──────────────────────────────────────────────────────

def _combine_curves(
    results: dict[str, BacktestResult],
    specs: list[SleeveSpec],
) -> pd.Series:
    """Sum all sub-sleeve NAVs on a common hourly index."""
    curves = {spec.label: results[spec.label].equity_curve for spec in specs}
    aligned = align_equity_curves(curves, base_freq="1h")
    combined = aligned.sum(axis=1)
    combined.name = "fund_nav"
    return combined


# ── Metrics helpers ────────────────────────────────────────────────────────────

def _perf_dict(eq: pd.Series, trades: list | None = None, initial_capital: float | None = None) -> dict:
    m = compute_metrics(eq, trades or [], initial_capital=initial_capital)
    return {
        "cagr_pct":          round(m.cagr_pct, 2),
        "total_return_pct":  round(m.total_return_pct, 2),
        "max_drawdown_pct":  round(m.max_drawdown_pct, 2),
        "sharpe":            round(m.sharpe, 3),
        "calmar":            round(m.calmar, 3),
        "volatility_ann_pct": round(m.volatility_ann_pct, 2),
        "n_trades":          m.n_trades,
        "win_rate_pct":      round(m.win_rate_pct, 2),
        "total_fees_paid":   round(m.total_fees_paid, 2),
        "total_slippage_cost": round(m.total_slippage_cost, 2),
        "initial_equity":    round(m.initial_equity, 2),
        "final_equity":      round(m.final_equity, 2),
        "start":             m.start,
        "end":               m.end,
    }


def _annual_returns(eq: pd.Series) -> dict[str, float]:
    """Calendar-year returns using period-start equity as base."""
    daily = eq.resample("D").last().dropna()
    out: dict[str, float] = {}
    for yr, grp in daily.groupby(daily.index.year):
        if len(grp) < 5:
            continue
        start_val = float(grp.iloc[0])
        end_val   = float(grp.iloc[-1])
        out[str(yr)] = round((end_val / start_val - 1) * 100, 2)
    return out


def _regime_exposure(results: dict[str, BacktestResult], specs: list[SleeveSpec]) -> dict:
    """Per-regime average exposure across trend sleeves."""
    trend_specs = [s for s in specs if s.family == "trend"]
    if not trend_specs:
        return {}
    rows = []
    for spec in trend_specs:
        r = results[spec.label]
        df = pd.DataFrame({
            "regime":   r.regime_series,
            "exposure": r.position_series.abs(),
        })
        rows.append(df)
    combined = pd.concat(rows)
    return {
        str(regime): round(float(grp["exposure"].mean()), 3)
        for regime, grp in combined.groupby("regime")
        if regime != "UNKNOWN"
    }


def _sleeve_activity(results: dict[str, BacktestResult], specs: list[SleeveSpec]) -> list[dict]:
    rows = []
    for spec in specs:
        r = results[spec.label]
        pos = r.position_series
        active_frac = float((pos.abs() > 0.01).mean())
        all_trades = r.trades
        total_cost = sum(t.fee_usd + t.slippage_usd + t.spread_usd for t in all_trades)
        rows.append({
            "sleeve":        spec.label,
            "family":        spec.family,
            "strategy":      spec.strategy,
            "capital":       round(spec.capital, 2),
            "n_trades":      len(all_trades),
            "active_frac":   round(active_frac, 3),
            "total_cost_usd": round(total_cost, 2),
            "final_equity":  round(r.final_equity, 2),
            "return_pct":    round(r.total_return_pct, 2),
        })
    return rows


# ── Markdown report ────────────────────────────────────────────────────────────

def _md_table(rows: list[dict], cols: list[str] | None = None) -> str:
    if not rows:
        return "_No data._"
    cols = cols or list(rows[0].keys())
    header = "| " + " | ".join(cols) + " |"
    sep    = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines  = [header, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def _write_report(
    out_dir: Path,
    fund_perf: dict,
    annual_rets: dict,
    sleeve_activity: list[dict],
    regime_exp: dict,
    args: argparse.Namespace,
    label: str,
) -> None:
    lines = [
        f"# Multi-Strategy Fund Report{' — ' + label if label else ''}",
        "",
        "## Fund Performance",
        "```text",
    ]
    for k, v in fund_perf.items():
        lines.append(f"{k:<28} {v}")
    lines += ["```", "", "## Annual Returns", "```text"]
    for yr, ret in annual_rets.items():
        lines.append(f"{yr}   {ret:+.2f}%")
    lines += [
        "```", "",
        "## Sleeve Activity",
        _md_table(sleeve_activity, cols=["sleeve","family","capital","n_trades","active_frac","total_cost_usd","return_pct"]),
        "",
        "## Regime Avg Exposure (Trend Sleeves)",
        "```text",
    ]
    for regime, exp in sorted(regime_exp.items()):
        lines.append(f"{regime:<20} {exp:.3f}")
    lines += [
        "```", "",
        "## Configuration",
        "```text",
        f"trend_weight  {args.trend_weight}",
        f"hedge_weight  {args.hedge_weight}",
        f"mr_weight     {args.mr_weight}",
        f"equity_weight {getattr(args, 'equity_weight', 0.0)}",
        f"capital       ${args.capital:,.0f}",
        f"fee           {args.fee*10000:.1f} bps (crypto)",
        f"equity_fee    {getattr(args, 'equity_fee', 0.0001)*10000:.1f} bps (equity)",
        f"base_slip     {args.base_slippage:.1f} bps",
        f"slip_vol_fac  {args.slippage_vol_factor:.1f}",
        f"cooldown      {args.cooldown} bars (trend/hedge)",
        f"mr_cooldown   {args.mr_cooldown} bars (MR sleeves)",
        "```",
        "",
        "_Research only. Not financial advice._",
    ]
    (out_dir / f"report{label}.md").write_text("\n".join(lines), encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    label = f"_{args.label}" if args.label else ""
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Validate weights ───────────────────────────────────────────────
    total_w = args.trend_weight + args.hedge_weight + args.mr_weight + getattr(args, "equity_weight", 0.0)
    if abs(total_w - 1.0) > 0.05:
        log.error("Sleeve weights sum to %.3f — must be close to 1.0", total_w)
        sys.exit(1)

    # ── Load data ──────────────────────────────────────────────────────
    raw: dict[str, pd.DataFrame] = {}
    raw["BTC"] = _load_asset(args.btc_data, "BTC", args.start, args.end)
    if args.eth_data:
        raw["ETH"] = _load_asset(args.eth_data, "ETH", args.start, args.end)
    if args.spy_data:
        raw["SPY"] = _load_asset(args.spy_data, "SPY", args.start, args.end)
    if args.qqq_data:
        raw["QQQ"] = _load_asset(args.qqq_data, "QQQ", args.start, args.end)

    # BIL daily returns — used as cash yield for idle equity capital
    bil_yield: pd.Series | None = None
    if getattr(args, "bil_data", None):
        bil_df = _load_asset(args.bil_data, "BIL", args.start, args.end)
        bil_yield = bil_df["close"].pct_change().fillna(0.0)
        log.info("BIL: %d bars  %s → %s  (cash yield for equity sleeves)",
                 len(bil_df), bil_df.index[0], bil_df.index[-1])

    # ── Build sleeves ──────────────────────────────────────────────────
    if getattr(args, "equity_weight", 0.0) > 0 and not args.spy_data and not getattr(args, "qqq_data", None):
        log.error("--equity-weight > 0 requires at least --spy-data or --qqq-data")
        sys.exit(1)

    specs = _build_sleeves(args)
    log.info("Configured %d sleeves  (trend=%d  hedge=%d  mr=%d  equity=%d)",
             len(specs),
             sum(1 for s in specs if s.family == "trend"),
             sum(1 for s in specs if s.family == "hedge"),
             sum(1 for s in specs if s.family == "mr"),
             sum(1 for s in specs if s.family == "equity"))

    # ── Execution configs (per family) ────────────────────────────────
    base_cfg = ExecutionConfig(
        taker_fee_rate=args.fee,
        base_slippage_bps=args.base_slippage,
        slippage_vol_factor=args.slippage_vol_factor,
        cooldown_bars=args.cooldown,
    )
    mr_cfg = ExecutionConfig(
        taker_fee_rate=args.fee,
        base_slippage_bps=args.base_slippage,
        slippage_vol_factor=args.slippage_vol_factor,
        cooldown_bars=args.mr_cooldown,
    )
    equity_cfg = ExecutionConfig(
        taker_fee_rate=getattr(args, "equity_fee", 0.0001),
        base_slippage_bps=0.5,        # very low base for liquid ETFs
        slippage_size_factor=1.0,     # minimal market impact (SPY/QQQ are enormous)
        slippage_vol_factor=2.0,      # low vol sensitivity for daily equity bars
        min_slippage_bps=0.1,         # near-zero floor
        max_slippage_bps=5.0,         # cap at 5 bps — generous for ETFs
        spread_k=0.02,                # daily ATR ~0.7% → half-spread ~0.7 bps/side
        min_spread_bps=0.2,           # ~0.2 bps/side for SPY/QQQ
        cooldown_bars=1,              # daily bars: 1-bar cooldown = one trading day
    )

    # ── Run all sleeves ────────────────────────────────────────────────
    specs = [s for s in specs if s.capital > 0]
    results: dict[str, BacktestResult] = {}
    for spec in specs:
        df = _sleeve_df(raw, spec)
        if spec.family == "equity":
            cfg = equity_cfg
            yield_series = bil_yield
        elif spec.family == "mr":
            cfg = mr_cfg
            yield_series = None
        else:
            cfg = base_cfg
            yield_series = None
        results[spec.label] = _run_sleeve(spec, df, cfg, args.rebalance_threshold, yield_series)

    # ── Combine ────────────────────────────────────────────────────────
    fund_nav = _combine_curves(results, specs)
    log.info("Fund NAV: $%.2f → $%.2f", fund_nav.iloc[0], fund_nav.iloc[-1])

    # ── Metrics ────────────────────────────────────────────────────────
    all_trades = [t for r in results.values() for t in r.trades]
    fund_perf  = _perf_dict(fund_nav, all_trades, initial_capital=args.capital)
    annual_ret = _annual_returns(fund_nav)
    sleeve_act = _sleeve_activity(results, specs)
    regime_exp = _regime_exposure(results, specs)

    # ── Print summary ──────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("FUND RESULTS")
    log.info("  CAGR:          %+.2f%%", fund_perf["cagr_pct"])
    log.info("  Total Return:  %+.2f%%", fund_perf["total_return_pct"])
    log.info("  Max Drawdown:  %.2f%%",  fund_perf["max_drawdown_pct"])
    log.info("  Sharpe:        %.3f",    fund_perf["sharpe"])
    log.info("  Calmar:        %.3f",    fund_perf["calmar"])
    log.info("  Ann Vol:       %.2f%%",  fund_perf["volatility_ann_pct"])
    log.info("  Total Trades:  %d",      fund_perf["n_trades"])
    log.info("  Total Fees:    $%.2f",   fund_perf["total_fees_paid"])
    log.info("  Total Slippage:$%.2f",   fund_perf["total_slippage_cost"])
    log.info("  Final NAV:     $%.2f",   fund_perf["final_equity"])
    log.info("-" * 60)
    log.info("ANNUAL RETURNS")
    for yr, ret in annual_ret.items():
        log.info("  %s   %+.2f%%", yr, ret)
    log.info("-" * 60)
    log.info("SLEEVE ACTIVITY")
    for row in sleeve_act:
        log.info("  %-28s  trades=%3d  active=%.0f%%  cost=$%.0f  ret=%+.1f%%",
                 row["sleeve"], row["n_trades"],
                 row["active_frac"] * 100,
                 row["total_cost_usd"], row["return_pct"])
    log.info("=" * 60)

    # ── Save artifacts ─────────────────────────────────────────────────
    fund_nav.to_csv(out_dir / f"fund_equity_curve{label}.csv")

    sleeve_curves = {spec.label: results[spec.label].equity_curve for spec in specs}
    aligned = align_equity_curves(sleeve_curves, base_freq="1h")
    aligned["fund_nav"] = fund_nav.reindex(aligned.index).ffill()
    aligned.to_csv(out_dir / f"all_equity_curves{label}.csv")

    pd.DataFrame(sleeve_act).to_csv(out_dir / f"sleeve_activity{label}.csv", index=False)

    summary = {
        "fund": fund_perf,
        "annual_returns": annual_ret,
        "sleeve_activity": sleeve_act,
        "regime_exposure": regime_exp,
        "config": {
            "trend_weight": args.trend_weight,
            "hedge_weight": args.hedge_weight,
            "mr_weight":    args.mr_weight,
            "capital":      args.capital,
            "fee_bps":      args.fee * 10000,
            "base_slippage_bps": args.base_slippage,
            "slippage_vol_factor": args.slippage_vol_factor,
            "cooldown_bars":    args.cooldown,
            "mr_cooldown_bars": args.mr_cooldown,
            "equity_weight":    getattr(args, "equity_weight", 0.0),
            "equity_fee_bps":   getattr(args, "equity_fee", 0.0001) * 10000,
            "btc_data":     args.btc_data,
            "eth_data":     args.eth_data,
            "spy_data":     getattr(args, "spy_data", None),
            "qqq_data":     getattr(args, "qqq_data", None),
            "start":        args.start,
            "end":          args.end,
        },
    }
    (out_dir / f"summary{label}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    _write_report(out_dir, fund_perf, annual_ret, sleeve_act, regime_exp, args, label)
    log.info("Artifacts saved to %s", out_dir)


if __name__ == "__main__":
    main()
