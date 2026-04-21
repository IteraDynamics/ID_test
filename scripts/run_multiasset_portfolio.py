#!/usr/bin/env python
"""IteraDynamics — Multi-Asset Portfolio Backtest CLI.

Runs N independent asset sleeves (each with its own OHLCV data, strategy,
and optional ML calibrator), then combines their equity curves into a single
blended portfolio NAV.  Fully asset-agnostic — pass any number of sleeves.

Usage
-----
# BTC (calibrated) + ETH (uncalibrated), equal weight:
python scripts/run_multiasset_portfolio.py \\
    --sleeve BTC,data/btcusd_3600s_2019-01-01_to_2025-12-30.csv,trend_following_v8_ecap60_add80,calibrated \\
    --sleeve ETH,data/ethusd_3600s_2019-01-01_to_2025-12-30.csv,trend_following_v8_ecap60_add80,uncalibrated \\
    --weights 0.5,0.5 \\
    --capital 100000

# Three assets, custom weights:
python scripts/run_multiasset_portfolio.py \\
    --sleeve BTC,data/btcusd.csv,trend_following_v8_ecap60_add80,calibrated \\
    --sleeve ETH,data/ethusd.csv,trend_following_v8_ecap60_add80,uncalibrated \\
    --sleeve SOL,data/solusd.csv,trend_following_v8_ecap60_add80,uncalibrated \\
    --weights 0.5,0.3,0.2 \\
    --capital 200000

PowerShell (backtick for line continuation):
    python scripts\\run_multiasset_portfolio.py `
        --sleeve BTC,data\\btcusd.csv,trend_following_v8_ecap60_add80,calibrated `
        --sleeve ETH,data\\ethusd.csv,trend_following_v8_ecap60_add80,uncalibrated `
        --weights 0.5,0.5 `
        --capital 100000

Sleeve format
-------------
    ASSET,path/to/data.csv,strategy_name[,calibrated]

    - ASSET      : any label (BTC, ETH, SOL, …)
    - data path  : OHLCV CSV — same format as run_backtest.py expects
    - strategy   : must be in REGISTRY (research/strategies/__init__.py)
    - calibrated : optional 4th field; loads saved ML calibrator for this sleeve
                   if no fitted model is found, falls back to uncalibrated silently
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("multiasset")

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.harness.backtest_engine import run_backtest
from research.harness.metrics import compute_metrics
from research.strategies import REGISTRY


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class SleeveSpec:
    """Parsed configuration for one asset sleeve."""
    asset: str
    data_path: str
    strategy_name: str
    calibrate: bool = False
    raw_weight: float = 1.0


@dataclass
class SleeveResult:
    """Backtest results for one asset sleeve."""
    spec: SleeveSpec
    normalized_weight: float
    equity_curve: pd.Series
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    calmar: float
    volatility_ann_pct: float
    n_trades: int
    win_rate_pct: float
    total_fees_usd: float
    total_slippage_usd: float
    avg_cost_per_trade_bps: float
    exit_entry_ratio: float
    calibrated: bool
    calibrator_method: str = ""


# ── Argument parsing ───────────────────────────────────────────────────────────

def _parse_sleeve(raw: str) -> SleeveSpec:
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) < 3:
        raise argparse.ArgumentTypeError(
            f"--sleeve requires at least 3 comma-separated values: "
            f"ASSET,data_path,strategy_name[,calibrated]. Got: '{raw}'"
        )
    return SleeveSpec(
        asset=parts[0].upper(),
        data_path=parts[1],
        strategy_name=parts[2],
        calibrate=len(parts) >= 4 and parts[3].strip().lower() == "calibrated",
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Multi-asset portfolio backtest — N independent asset sleeves, "
            "combined into a single NAV curve."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--sleeve",
        action="append",
        required=True,
        metavar="ASSET,data_path,strategy[,calibrated]",
        help=(
            "One asset sleeve. Repeat for each asset. "
            "Format: ASSET,path/to/data.csv,strategy_name[,calibrated]. "
            "Append ',calibrated' to load a saved ML calibrator for that sleeve."
        ),
    )
    p.add_argument(
        "--weights",
        default=None,
        help=(
            "Comma-separated sleeve weights matching --sleeve order. "
            "Need not sum to 1 — normalised automatically. "
            "Defaults to equal weights."
        ),
    )
    p.add_argument("--capital", type=float, default=100_000.0,
                   help="Total initial capital (USD) split across sleeves by weight")
    p.add_argument("--start", default=None,
                   help="Force start date (YYYY-MM-DD). Defaults to latest first-bar across sleeves.")
    p.add_argument("--end", default=None,
                   help="Force end date (YYYY-MM-DD). Defaults to earliest last-bar across sleeves.")
    p.add_argument("--output", default="artifacts/multiasset",
                   help="Base output directory")
    p.add_argument("--calibrators-dir", default=None,
                   help="Directory containing calibrator JSON files (default: artifacts/ml_models/)")
    # Execution cost overrides (applied uniformly to all sleeves)
    p.add_argument("--fee", type=float, default=None,
                   help="Taker fee rate override (e.g. 0.0006)")
    p.add_argument("--base-slippage", type=float, default=None,
                   help="Base slippage floor in bps")
    p.add_argument("--slippage-vol-factor", type=float, default=None,
                   help="Slippage bps per 100%% annualised ATR")
    p.add_argument("--cooldown", type=int, default=None,
                   help="Minimum bars between trades")
    p.add_argument("--no-chart", action="store_true",
                   help="Skip chart PNG generation")
    return p.parse_args()


# ── Chart ──────────────────────────────────────────────────────────────────────

def _plot(
    combined: pd.Series,
    sleeve_results: list[SleeveResult],
    out_path: Path,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        log.warning("matplotlib not available — skipping chart.")
        return

    colors = ["#2196F3", "#FF9800", "#4CAF50", "#E91E63", "#9C27B0",
              "#00BCD4", "#FF5722", "#795548"]

    fig, (ax_eq, ax_dd) = plt.subplots(
        2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [3, 1]}
    )

    # Normalise to 100 at start for visual comparison
    def _norm(s: pd.Series) -> pd.Series:
        return s / s.iloc[0] * 100

    ax_eq.plot(_norm(combined).index, _norm(combined).values,
               color="black", linewidth=2.5, label="Portfolio (combined)", zorder=10)

    for idx, sr in enumerate(sleeve_results):
        label = f"{sr.spec.asset} ({sr.normalized_weight:.0%})"
        if sr.calibrated:
            label += " cal"
        ax_eq.plot(
            _norm(sr.equity_curve).index, _norm(sr.equity_curve).values,
            color=colors[idx % len(colors)], linewidth=1.2, alpha=0.75, label=label,
        )

    ax_eq.set_ylabel("NAV (indexed to 100)", fontsize=11)
    ax_eq.set_title(
        f"Multi-Asset Portfolio — "
        + "+".join(sr.spec.asset for sr in sleeve_results),
        fontsize=13, fontweight="bold",
    )
    ax_eq.legend(loc="upper left", fontsize=9)
    ax_eq.grid(True, alpha=0.3)
    ax_eq.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Portfolio drawdown
    rolling_max = combined.expanding().max()
    drawdown = (combined - rolling_max) / rolling_max * 100
    ax_dd.fill_between(drawdown.index, drawdown.values, 0,
                       color="crimson", alpha=0.45, label="Portfolio drawdown")
    ax_dd.set_ylabel("Drawdown (%)", fontsize=11)
    ax_dd.set_xlabel("Date", fontsize=11)
    ax_dd.grid(True, alpha=0.3)
    ax_dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info("Chart saved: %s", out_path)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    t0 = time.time()

    # ── Parse sleeves ──────────────────────────────────────────────────
    sleeve_specs: list[SleeveSpec] = []
    for raw in args.sleeve:
        try:
            sleeve_specs.append(_parse_sleeve(raw))
        except argparse.ArgumentTypeError as e:
            log.error("%s", e)
            sys.exit(1)

    if len(sleeve_specs) == 1:
        log.warning("Only 1 sleeve — consider run_backtest.py for single-asset runs.")

    # ── Resolve weights ────────────────────────────────────────────────
    if args.weights:
        raw_weights = [float(w.strip()) for w in args.weights.split(",")]
        if len(raw_weights) != len(sleeve_specs):
            log.error(
                "--weights has %d values but %d sleeves specified.",
                len(raw_weights), len(sleeve_specs),
            )
            sys.exit(1)
    else:
        raw_weights = [1.0] * len(sleeve_specs)

    total_w = sum(raw_weights)
    normalized_weights = [w / total_w for w in raw_weights]
    for spec, w in zip(sleeve_specs, raw_weights):
        spec.raw_weight = w

    # ── Validate strategies ────────────────────────────────────────────
    for spec in sleeve_specs:
        if REGISTRY.get(spec.strategy_name) is None:
            log.error(
                "Unknown strategy '%s' for sleeve %s. Available: %s",
                spec.strategy_name, spec.asset, sorted(REGISTRY),
            )
            sys.exit(1)

    log.info(
        "Sleeves: %s",
        "  ".join(
            f"{s.asset}({nw:.0%}{'|cal' if s.calibrate else ''})"
            for s, nw in zip(sleeve_specs, normalized_weights)
        ),
    )

    # ── Load data and determine common date range ──────────────────────
    log.info("Loading data…")
    raw_dfs: dict[str, pd.DataFrame] = {}
    range_starts: list[pd.Timestamp] = []
    range_ends: list[pd.Timestamp] = []

    for spec in sleeve_specs:
        log.info("  [%s] %s", spec.asset, spec.data_path)
        df_raw = load_ohlcv(spec.data_path, asset=spec.asset)
        raw_dfs[spec.asset] = df_raw
        range_starts.append(df_raw.index[0])
        range_ends.append(df_raw.index[-1])
        log.info("    %d bars  %s → %s", len(df_raw),
                 df_raw.index[0].date(), df_raw.index[-1].date())

    common_start = max(range_starts)
    common_end = min(range_ends)

    if args.start:
        common_start = max(common_start, pd.Timestamp(args.start))
    if args.end:
        common_end = min(common_end, pd.Timestamp(args.end))

    if common_start >= common_end:
        log.error(
            "No overlapping date range across sleeves (%s → %s). "
            "Check your data files or --start/--end flags.",
            common_start.date(), common_end.date(),
        )
        sys.exit(1)

    log.info("Common period: %s → %s", common_start.date(), common_end.date())

    # ── Build execution config ─────────────────────────────────────────
    exec_config = ExecutionConfig.from_env()
    if args.fee is not None:
        exec_config.taker_fee_rate = args.fee
    if args.base_slippage is not None:
        exec_config.base_slippage_bps = args.base_slippage
    if args.slippage_vol_factor is not None:
        exec_config.slippage_vol_factor = args.slippage_vol_factor
    if args.cooldown is not None:
        exec_config.cooldown_bars = args.cooldown

    log.info(
        "Execution: fee=%.4f  base_slip=%.1fbps  vol_factor=%.1f  cooldown=%d",
        exec_config.taker_fee_rate, exec_config.base_slippage_bps,
        exec_config.slippage_vol_factor, exec_config.cooldown_bars,
    )

    # ── Run each sleeve independently ──────────────────────────────────
    sleeve_results: list[SleeveResult] = []

    for spec, nw in zip(sleeve_specs, normalized_weights):
        log.info("═" * 60)
        log.info(
            "[%s] strategy=%s  weight=%.0f%%  capital=$%.0f  calibrate=%s",
            spec.asset, spec.strategy_name, nw * 100, args.capital * nw, spec.calibrate,
        )

        df = raw_dfs[spec.asset].loc[common_start:common_end].copy()
        for warning in validate_ohlcv(df):
            log.warning("  [%s] %s", spec.asset, warning)

        strategy_module = REGISTRY[spec.strategy_name]
        strategy_id = getattr(strategy_module, "STRATEGY_ID", spec.strategy_name)

        # Load calibrator for this sleeve if requested
        calibrators = None
        cal_method = ""
        if spec.calibrate:
            try:
                from research.ml.calibration.model_store import load_calibrator
                cal = load_calibrator(strategy_id, models_dir=args.calibrators_dir)
                if cal is not None and cal.is_fitted:
                    calibrators = {strategy_id: cal}
                    cal_method = cal.calibration_method
                    log.info(
                        "  Calibrator loaded: method=%s  n_samples=%d",
                        cal_method, cal.n_samples,
                    )
                else:
                    log.warning(
                        "  No fitted calibrator for '%s' — sleeve runs uncalibrated.",
                        strategy_id,
                    )
            except ImportError:
                log.warning("  ML calibration package not available — running uncalibrated.")

        result = run_backtest(
            df=df,
            strategy_module=strategy_module,
            initial_capital=args.capital * nw,
            exec_config=exec_config,
            asset=spec.asset,
            calibrators=calibrators,
        )
        m = compute_metrics(result.equity_curve, result.trades, result.params)

        log.info(
            "  CAGR=%+.1f%%  DD=%.1f%%  Sharpe=%.3f  Calmar=%.3f  "
            "Trades=%d  Exit/Entry=%.3fx",
            m.cagr_pct, m.max_drawdown_pct, m.sharpe, m.calmar,
            m.n_trades, m.avg_exit_entry_notional_ratio,
        )

        sleeve_results.append(SleeveResult(
            spec=spec,
            normalized_weight=nw,
            equity_curve=result.equity_curve,
            cagr_pct=m.cagr_pct,
            max_drawdown_pct=m.max_drawdown_pct,
            sharpe=m.sharpe,
            calmar=m.calmar,
            volatility_ann_pct=m.volatility_ann_pct,
            n_trades=m.n_trades,
            win_rate_pct=m.win_rate_pct,
            total_fees_usd=m.total_fees_paid,
            total_slippage_usd=m.total_slippage_cost,
            avg_cost_per_trade_bps=m.avg_cost_per_trade_bps,
            exit_entry_ratio=m.avg_exit_entry_notional_ratio,
            calibrated=calibrators is not None,
            calibrator_method=cal_method,
        ))

    # ── Combine equity curves ──────────────────────────────────────────
    log.info("═" * 60)
    equity_df = pd.concat(
        [sr.equity_curve.rename(sr.spec.asset) for sr in sleeve_results],
        axis=1,
    ).ffill().dropna()

    combined_equity = equity_df.sum(axis=1)
    combined_equity.name = "portfolio"

    # ── Combined metrics (equity-curve derived) ────────────────────────
    asset_labels = [sr.spec.asset for sr in sleeve_results]
    portfolio_label = "+".join(asset_labels)

    combined_params = {
        "initial_capital": args.capital,
        "asset": portfolio_label,
        "strategy_id": "multiasset_portfolio",
        "start": str(combined_equity.index[0]),
        "end": str(combined_equity.index[-1]),
        "n_bars": len(combined_equity),
    }
    cm = compute_metrics(combined_equity, [], combined_params)

    total_fees = sum(sr.total_fees_usd for sr in sleeve_results)
    total_slippage = sum(sr.total_slippage_usd for sr in sleeve_results)
    total_trades = sum(sr.n_trades for sr in sleeve_results)
    total_return = (float(combined_equity.iloc[-1]) / args.capital - 1) * 100

    # ── Pairwise daily-return correlation ──────────────────────────────
    daily_ret = equity_df.resample("D").last().pct_change().dropna()
    corr_matrix = daily_ret.corr()

    # ── Console output ─────────────────────────────────────────────────
    w = 70
    print("\n" + "=" * w)
    print(f"  MULTI-ASSET PORTFOLIO — {portfolio_label}")
    print("=" * w)
    print(f"  Period:       {str(combined_equity.index[0].date())} → {str(combined_equity.index[-1].date())}")
    print(f"  Sleeves:      " + "  ".join(
        f"{sr.spec.asset}={sr.normalized_weight:.0%}" for sr in sleeve_results
    ))
    print(f"  Capital:      ${args.capital:>12,.2f}")
    print(f"  Final NAV:    ${float(combined_equity.iloc[-1]):>12,.2f}")
    print(f"  Total Return: {total_return:>+.2f}%")
    print(f"  CAGR:         {cm.cagr_pct:>+.2f}%")
    print(f"  Max Drawdown: {cm.max_drawdown_pct:.2f}%")
    print(f"  Sharpe:       {cm.sharpe:.3f}")
    print(f"  Calmar:       {cm.calmar:.3f}")
    print(f"  Ann. Vol:     {cm.volatility_ann_pct:.2f}%")
    print(f"  Total Trades: {total_trades}")
    print(f"  Total Fees:   ${total_fees:>12,.2f}")
    print(f"  Slippage:     ${total_slippage:>12,.2f}")
    print("=" * w)

    # Per-sleeve table
    print("\n  Per-Sleeve Performance:")
    col = "{:<6} {:>6}  {:>3}  {:>8}  {:>8}  {:>7}  {:>7}  {:>7}  {:>11}  {:>12}  {:>10}"
    hdr = col.format(
        "Asset", "Weight", "Cal",
        "CAGR", "Max DD", "Sharpe", "Calmar", "Trades",
        "Fees", "Slippage", "Exit/Entry",
    )
    print("  " + hdr)
    print("  " + "-" * len(hdr))
    for sr in sleeve_results:
        ee = f"{sr.exit_entry_ratio:.3f}x" if sr.exit_entry_ratio else "—"
        print("  " + col.format(
            sr.spec.asset,
            f"{sr.normalized_weight:.0%}",
            "YES" if sr.calibrated else "no",
            f"{sr.cagr_pct:+.1f}%",
            f"{sr.max_drawdown_pct:.1f}%",
            f"{sr.sharpe:.3f}",
            f"{sr.calmar:.3f}",
            sr.n_trades,
            f"${sr.total_fees_usd:,.0f}",
            f"${sr.total_slippage_usd:,.0f}",
            ee,
        ))

    if len(sleeve_results) >= 2:
        print("\n  Pairwise Daily-Return Correlation:")
        for i, a in enumerate(asset_labels):
            for j, b in enumerate(asset_labels):
                if j > i:
                    print(f"    {a} / {b}:  {corr_matrix.loc[a, b]:.3f}")

    print(f"\n  Elapsed: {time.time() - t0:.1f}s")
    print("=" * w)

    # ── Save artifacts ─────────────────────────────────────────────────
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output) / portfolio_label / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    combined_equity.to_csv(out_dir / "combined_equity_curve.csv", header=True)

    # Per-sleeve equity curves, indexed to 100
    indexed = pd.concat(
        [
            (sr.equity_curve / sr.equity_curve.iloc[0] * 100).rename(sr.spec.asset)
            for sr in sleeve_results
        ]
        + [(combined_equity / combined_equity.iloc[0] * 100).rename("portfolio")],
        axis=1,
    )
    indexed.to_csv(out_dir / "sleeve_equity_curves_indexed.csv")

    summary: dict = {
        "run_id": run_id,
        "portfolio": portfolio_label,
        "period_start": str(combined_equity.index[0].date()),
        "period_end": str(combined_equity.index[-1].date()),
        "initial_capital": args.capital,
        "final_nav": round(float(combined_equity.iloc[-1]), 2),
        "total_return_pct": round(total_return, 4),
        "cagr_pct": round(cm.cagr_pct, 4),
        "max_drawdown_pct": round(cm.max_drawdown_pct, 4),
        "sharpe": round(cm.sharpe, 4),
        "calmar": round(cm.calmar, 4),
        "volatility_ann_pct": round(cm.volatility_ann_pct, 4),
        "total_trades": total_trades,
        "total_fees_usd": round(total_fees, 2),
        "total_slippage_usd": round(total_slippage, 2),
        "sleeves": [
            {
                "asset": sr.spec.asset,
                "strategy": sr.spec.strategy_name,
                "data_path": sr.spec.data_path,
                "weight": round(sr.normalized_weight, 6),
                "calibrated": sr.calibrated,
                "calibrator_method": sr.calibrator_method,
                "cagr_pct": round(sr.cagr_pct, 4),
                "max_drawdown_pct": round(sr.max_drawdown_pct, 4),
                "sharpe": round(sr.sharpe, 4),
                "calmar": round(sr.calmar, 4),
                "volatility_ann_pct": round(sr.volatility_ann_pct, 4),
                "n_trades": sr.n_trades,
                "win_rate_pct": round(sr.win_rate_pct, 4),
                "total_fees_usd": round(sr.total_fees_usd, 2),
                "total_slippage_usd": round(sr.total_slippage_usd, 2),
                "avg_cost_per_trade_bps": round(sr.avg_cost_per_trade_bps, 4),
                "exit_entry_ratio": round(sr.exit_entry_ratio, 4) if sr.exit_entry_ratio else None,
            }
            for sr in sleeve_results
        ],
        "pairwise_correlation": {
            f"{a}/{b}": round(float(corr_matrix.loc[a, b]), 4)
            for i, a in enumerate(asset_labels)
            for j, b in enumerate(asset_labels)
            if j > i
        },
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    md: list[str] = [
        f"# Multi-Asset Portfolio — {portfolio_label}",
        "",
        f"**Run:** {run_id}  |  "
        f"**Period:** {summary['period_start']} → {summary['period_end']}",
        "",
        "## Combined Portfolio Metrics",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| CAGR | {cm.cagr_pct:+.2f}% |",
        f"| Max Drawdown | {cm.max_drawdown_pct:.2f}% |",
        f"| Sharpe | {cm.sharpe:.3f} |",
        f"| Calmar | {cm.calmar:.3f} |",
        f"| Ann. Vol | {cm.volatility_ann_pct:.2f}% |",
        f"| Total Return | {total_return:+.2f}% |",
        f"| Initial Capital | ${args.capital:,.0f} |",
        f"| Final NAV | ${float(combined_equity.iloc[-1]):,.2f} |",
        f"| Total Trades | {total_trades} |",
        f"| Total Fees | ${total_fees:,.2f} |",
        f"| Total Slippage | ${total_slippage:,.2f} |",
        "",
        "## Per-Sleeve Performance",
        "",
        "| Asset | Weight | Cal | CAGR | Max DD | Sharpe | Calmar | Trades | Exit/Entry |",
        "|-------|-------:|:---:|-----:|-------:|-------:|-------:|-------:|----------:|",
    ]
    for sr in sleeve_results:
        ee = f"{sr.exit_entry_ratio:.3f}x" if sr.exit_entry_ratio else "—"
        md.append(
            f"| {sr.spec.asset} | {sr.normalized_weight:.0%} | "
            f"{'✓' if sr.calibrated else '—'} | "
            f"{sr.cagr_pct:+.1f}% | {sr.max_drawdown_pct:.1f}% | "
            f"{sr.sharpe:.3f} | {sr.calmar:.3f} | {sr.n_trades} | {ee} |"
        )

    if len(sleeve_results) >= 2:
        md += [
            "",
            "## Pairwise Daily-Return Correlation",
            "",
            "| Pair | Correlation |",
            "|------|:-----------:|",
        ]
        for i, a in enumerate(asset_labels):
            for j, b in enumerate(asset_labels):
                if j > i:
                    md.append(f"| {a} / {b} | {corr_matrix.loc[a, b]:.3f} |")

    with open(out_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    if not args.no_chart:
        _plot(combined_equity, sleeve_results, out_dir / "chart.png")

    log.info("Artifacts saved to: %s", out_dir)
    log.info(
        "  combined_equity_curve.csv  sleeve_equity_curves_indexed.csv  "
        "summary.json  summary.md  chart.png"
    )


if __name__ == "__main__":
    main()
