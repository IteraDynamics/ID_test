#!/usr/bin/env python
"""IteraDynamics — Multi-Strategy Fund Walk-Forward Validator.

Runs the same three-sleeve fund structure (trend + hedge + MR) through
chronological expanding-window walk-forward folds. Each fold's OOS slice
is strictly future data that was invisible during the preceding period.

Walk-forward design (expanding window, annual OOS slices):

  Fold 1:  IS 2019-01-01 → 2020-12-31   OOS 2021-01-01 → 2021-12-31
  Fold 2:  IS 2019-01-01 → 2021-12-31   OOS 2022-01-01 → 2022-12-31
  Fold 3:  IS 2019-01-01 → 2022-12-31   OOS 2023-01-01 → 2023-12-31
  Fold 4:  IS 2019-01-01 → 2023-12-31   OOS 2024-01-01 → 2024-12-31

Stitched OOS: concatenation of the four OOS equity curves, scaled so
each fold starts from the prior fold's ending NAV (realistic compounding).

There is no ML calibration step here — these are rule-based strategies
with fixed parameters. Walk-forward validates that the strategy
architecture, not cherry-picked parameters, drives performance.

Usage
-----
# Default folds (2021–2024 OOS), BTC only:
python scripts/run_multi_strategy_walkforward.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv

# BTC + ETH:
python scripts/run_multi_strategy_walkforward.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv

# Custom OOS start (folds auto-generated from there to --oos-end):
python scripts/run_multi_strategy_walkforward.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --data-start 2019-01-01 --oos-start 2021-01-01 --oos-end 2024-12-31

PowerShell:
python scripts\\run_multi_strategy_walkforward.py `
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
log = logging.getLogger("multi_strategy_wf")

import numpy as np
import pandas as pd

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.resampler import resample_ohlcv, align_equity_curves
from research.harness.backtest_engine import run_backtest, BacktestResult
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import compute_metrics
from research.strategies import REGISTRY as STRATEGY_REGISTRY

# Re-use sleeve construction helpers from the fund runner
from scripts.run_multi_strategy_fund import (
    SleeveSpec,
    _build_sleeves,
    _load_asset,
    _sleeve_df,
    _run_sleeve,
    _combine_curves,
    _perf_dict,
    _annual_returns,
    _sleeve_activity,
)

TREND_STRATEGY = "trend_following_v8_ecap60_add80"
HEDGE_STRATEGY = "crash_short_v2"
MR_STRATEGY    = "mean_reversion"


# ── Fold definition ────────────────────────────────────────────────────────────

@dataclass
class WFFold:
    label: str
    is_start: str    # inclusive
    is_end: str      # inclusive
    oos_start: str   # inclusive
    oos_end: str     # inclusive


def _build_folds(data_start: str, oos_start: str, oos_end: str) -> list[WFFold]:
    """Build annual expanding-window folds from oos_start through oos_end."""
    oos_start_dt = pd.Timestamp(oos_start)
    oos_end_dt   = pd.Timestamp(oos_end)

    folds: list[WFFold] = []
    year = oos_start_dt.year
    while True:
        fold_oos_start = pd.Timestamp(f"{year}-01-01")
        fold_oos_end   = pd.Timestamp(f"{year}-12-31")

        if fold_oos_start > oos_end_dt:
            break
        if fold_oos_end > oos_end_dt:
            fold_oos_end = oos_end_dt

        # IS ends the day before OOS starts
        fold_is_end = fold_oos_start - pd.Timedelta(days=1)

        folds.append(WFFold(
            label=str(year),
            is_start=data_start,
            is_end=str(fold_is_end.date()),
            oos_start=str(fold_oos_start.date()),
            oos_end=str(fold_oos_end.date()),
        ))
        year += 1

    return folds


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Multi-strategy fund walk-forward OOS validation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", default=None)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--trend-weight", type=float, default=0.60)
    p.add_argument("--hedge-weight", type=float, default=0.20)
    p.add_argument("--mr-weight",    type=float, default=0.20)
    # Walk-forward window
    p.add_argument("--data-start",  default="2019-01-01",
                   help="Start of the full data window (IS begins here)")
    p.add_argument("--oos-start",   default="2021-01-01",
                   help="Start of the first OOS fold (year 1)")
    p.add_argument("--oos-end",     default="2024-12-31",
                   help="End of the last OOS fold")
    # Cost model
    p.add_argument("--fee",                  type=float, default=0.0006)
    p.add_argument("--base-slippage",        type=float, default=3.0)
    p.add_argument("--slippage-vol-factor",  type=float, default=50.0)
    p.add_argument("--cooldown",             type=int,   default=2)
    p.add_argument("--rebalance-threshold",  type=float, default=0.02)
    # Output
    p.add_argument("--out-dir", default="artifacts/multi_strategy_walkforward")
    return p.parse_args()


# ── Run one fold ───────────────────────────────────────────────────────────────

def _run_fold(
    fold: WFFold,
    raw_full: dict[str, pd.DataFrame],
    args: argparse.Namespace,
    exec_config: ExecutionConfig,
) -> dict:
    """Run OOS slice of one fold. Returns metrics dict."""
    log.info("Fold %s — OOS %s → %s", fold.label, fold.oos_start, fold.oos_end)

    # Slice raw data to OOS window only (strategies still see full history
    # up to oos_end, but we only evaluate from oos_start onward)
    raw_oos: dict[str, pd.DataFrame] = {}
    for asset, df in raw_full.items():
        sliced = df.loc[fold.oos_start: fold.oos_end]
        if len(sliced) < 100:
            log.warning("Fold %s %s: only %d bars in OOS — skipping",
                        fold.label, asset, len(sliced))
            return {}
        raw_oos[asset] = sliced

    specs = _build_sleeves(args)

    results: dict[str, BacktestResult] = {}
    for spec in specs:
        df = _sleeve_df(raw_oos, spec)
        results[spec.label] = _run_sleeve(spec, df, exec_config, args.rebalance_threshold)

    fund_nav  = _combine_curves(results, specs)
    all_trades = [t for r in results.values() for t in r.trades]
    perf = _perf_dict(fund_nav, all_trades)
    activity = _sleeve_activity(results, specs)

    return {
        "fold":       fold.label,
        "oos_start":  fold.oos_start,
        "oos_end":    fold.oos_end,
        "is_start":   fold.is_start,
        "is_end":     fold.is_end,
        "perf":       perf,
        "activity":   activity,
        "fund_nav":   fund_nav,
    }


# ── Stitch OOS equity curves ───────────────────────────────────────────────────

def _stitch_oos(fold_results: list[dict], initial_capital: float) -> pd.Series:
    """Chain OOS equity curves so each fold starts from prior fold's end NAV."""
    parts: list[pd.Series] = []
    running_nav = initial_capital

    for fr in fold_results:
        if not fr or "fund_nav" not in fr:
            continue
        curve = fr["fund_nav"].dropna()
        if curve.empty:
            continue
        # Rescale so this fold starts from running_nav
        scale = running_nav / float(curve.iloc[0])
        scaled = curve * scale
        parts.append(scaled)
        running_nav = float(scaled.iloc[-1])

    if not parts:
        return pd.Series(dtype=float)

    stitched = pd.concat(parts)
    stitched.name = "stitched_oos_nav"
    # Remove any duplicate timestamps at fold boundaries
    stitched = stitched[~stitched.index.duplicated(keep="last")]
    return stitched.sort_index()


# ── Reporting ──────────────────────────────────────────────────────────────────

def _md_table(rows: list[dict], cols: list[str]) -> str:
    if not rows:
        return "_No data._"
    header = "| " + " | ".join(cols) + " |"
    sep    = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines  = [header, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def _write_wf_report(
    out_dir: Path,
    fold_rows: list[dict],
    stitched_perf: dict,
    stitched_annual: dict,
    args: argparse.Namespace,
) -> None:
    lines = [
        "# Multi-Strategy Fund — Walk-Forward OOS Report",
        "",
        "## Stitched OOS Performance",
        "```text",
    ]
    for k, v in stitched_perf.items():
        lines.append(f"{k:<28} {v}")
    lines += ["```", "", "## Stitched Annual Returns", "```text"]
    for yr, ret in stitched_annual.items():
        lines.append(f"{yr}   {ret:+.2f}%")
    lines += ["```", "", "## Per-Fold OOS Results"]

    fold_summary_cols = [
        "fold", "oos_start", "oos_end",
        "cagr_pct", "max_drawdown_pct", "sharpe", "calmar",
        "n_trades", "total_fees_paid",
    ]
    fold_table_rows = []
    for fr in fold_rows:
        if not fr:
            continue
        p = fr["perf"]
        fold_table_rows.append({
            "fold":             fr["fold"],
            "oos_start":        fr["oos_start"],
            "oos_end":          fr["oos_end"],
            "cagr_pct":         p.get("cagr_pct", ""),
            "max_drawdown_pct": p.get("max_drawdown_pct", ""),
            "sharpe":           p.get("sharpe", ""),
            "calmar":           p.get("calmar", ""),
            "n_trades":         p.get("n_trades", ""),
            "total_fees_paid":  p.get("total_fees_paid", ""),
        })
    lines += [_md_table(fold_table_rows, fold_summary_cols), ""]

    lines += [
        "## Configuration",
        "```text",
        f"data_start     {args.data_start}",
        f"oos_start      {args.oos_start}",
        f"oos_end        {args.oos_end}",
        f"trend_weight   {args.trend_weight}",
        f"hedge_weight   {args.hedge_weight}",
        f"mr_weight      {args.mr_weight}",
        f"capital        ${args.capital:,.0f}",
        f"fee            {args.fee*10000:.1f} bps",
        f"base_slippage  {args.base_slippage:.1f} bps",
        f"slip_vol_fac   {args.slippage_vol_factor:.1f}",
        f"cooldown       {args.cooldown} bars",
        "```",
        "",
        "## Methodology",
        "",
        "Expanding-window walk-forward. Each fold's OOS slice is strictly",
        "future data. Strategies use fixed rule-based parameters — no ML",
        "retraining or parameter selection across folds.",
        "",
        "_Research only. Not financial advice._",
    ]
    (out_dir / "walkforward_report.md").write_text("\n".join(lines), encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Load full data ─────────────────────────────────────────────────
    raw_full: dict[str, pd.DataFrame] = {}
    raw_full["BTC"] = _load_asset(args.btc_data, "BTC", args.data_start, None)
    if args.eth_data:
        raw_full["ETH"] = _load_asset(args.eth_data, "ETH", args.data_start, None)

    # ── Build folds ────────────────────────────────────────────────────
    folds = _build_folds(args.data_start, args.oos_start, args.oos_end)
    log.info("Walk-forward: %d folds  OOS %s → %s",
             len(folds), args.oos_start, args.oos_end)
    for f in folds:
        log.info("  Fold %-6s  IS %s → %s   OOS %s → %s",
                 f.label, f.is_start, f.is_end, f.oos_start, f.oos_end)

    # ── Cost config ────────────────────────────────────────────────────
    exec_config = ExecutionConfig(
        taker_fee_rate=args.fee,
        base_slippage_bps=args.base_slippage,
        slippage_vol_factor=args.slippage_vol_factor,
        cooldown_bars=args.cooldown,
    )

    # ── Run folds ──────────────────────────────────────────────────────
    fold_results: list[dict] = []
    for fold in folds:
        fr = _run_fold(fold, raw_full, args, exec_config)
        fold_results.append(fr)
        if fr and "perf" in fr:
            p = fr["perf"]
            log.info(
                "  Fold %s OOS → CAGR %+.1f%%  MaxDD %.1f%%  Sharpe %.3f  Calmar %.3f",
                fold.label,
                p.get("cagr_pct", 0),
                p.get("max_drawdown_pct", 0),
                p.get("sharpe", 0),
                p.get("calmar", 0),
            )

    # ── Stitch OOS ─────────────────────────────────────────────────────
    stitched = _stitch_oos(fold_results, args.capital)

    if stitched.empty:
        log.error("No OOS equity curve produced — check data ranges")
        sys.exit(1)

    stitched_perf   = _perf_dict(stitched)
    stitched_annual = _annual_returns(stitched)

    # ── Print summary ──────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("STITCHED OOS RESULTS  (%s → %s)", args.oos_start, args.oos_end)
    log.info("  CAGR:          %+.2f%%", stitched_perf["cagr_pct"])
    log.info("  Total Return:  %+.2f%%", stitched_perf["total_return_pct"])
    log.info("  Max Drawdown:  %.2f%%",  stitched_perf["max_drawdown_pct"])
    log.info("  Sharpe:        %.3f",    stitched_perf["sharpe"])
    log.info("  Calmar:        %.3f",    stitched_perf["calmar"])
    log.info("  Ann Vol:       %.2f%%",  stitched_perf["volatility_ann_pct"])
    log.info("  Total Trades:  %d",      stitched_perf["n_trades"])
    log.info("-" * 60)
    log.info("ANNUAL OOS RETURNS")
    for yr, ret in stitched_annual.items():
        log.info("  %s   %+.2f%%", yr, ret)
    log.info("-" * 60)
    log.info("PER-FOLD OOS SUMMARY")
    for fr in fold_results:
        if not fr or "perf" not in fr:
            continue
        p = fr["perf"]
        log.info("  Fold %-6s  CAGR %+.1f%%  MaxDD %.1f%%  Sharpe %.3f  Calmar %.3f",
                 fr["fold"],
                 p.get("cagr_pct", 0),
                 p.get("max_drawdown_pct", 0),
                 p.get("sharpe", 0),
                 p.get("calmar", 0))
    log.info("=" * 60)

    # ── Save artifacts ─────────────────────────────────────────────────
    stitched.to_csv(out_dir / "stitched_oos_equity.csv")

    fold_perf_rows = []
    for fr in fold_results:
        if not fr or "perf" not in fr:
            continue
        row = {"fold": fr["fold"], "oos_start": fr["oos_start"], "oos_end": fr["oos_end"]}
        row.update(fr["perf"])
        fold_perf_rows.append(row)
    pd.DataFrame(fold_perf_rows).to_csv(out_dir / "fold_performance.csv", index=False)

    # Per-fold equity curves
    fold_curves: dict[str, pd.Series] = {}
    for fr in fold_results:
        if not fr or "fund_nav" not in fr:
            continue
        fold_curves[f"fold_{fr['fold']}"] = fr["fund_nav"]
    if fold_curves:
        fold_curves["stitched_oos"] = stitched
        try:
            pd.concat(fold_curves.values(), axis=1, keys=fold_curves.keys()).to_csv(
                out_dir / "fold_equity_curves.csv"
            )
        except Exception:
            pass

    summary = {
        "stitched_oos": stitched_perf,
        "stitched_annual_returns": stitched_annual,
        "folds": [
            {
                "fold":     fr.get("fold"),
                "oos_start": fr.get("oos_start"),
                "oos_end":   fr.get("oos_end"),
                "perf":      fr.get("perf", {}),
            }
            for fr in fold_results if fr
        ],
        "config": {
            "data_start":           args.data_start,
            "oos_start":            args.oos_start,
            "oos_end":              args.oos_end,
            "trend_weight":         args.trend_weight,
            "hedge_weight":         args.hedge_weight,
            "mr_weight":            args.mr_weight,
            "capital":              args.capital,
            "fee_bps":              args.fee * 10000,
            "base_slippage_bps":    args.base_slippage,
            "slippage_vol_factor":  args.slippage_vol_factor,
            "cooldown_bars":        args.cooldown,
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    _write_wf_report(out_dir, fold_results, stitched_perf, stitched_annual, args)
    log.info("Artifacts saved to %s", out_dir)


if __name__ == "__main__":
    main()
