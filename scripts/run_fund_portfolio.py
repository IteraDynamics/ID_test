"""IteraDynamics — Multi-Sleeve Fund Portfolio Runner.

Combines multiple asset x timeframe sleeves of the same strategy into a
fund-style portfolio.  Each sleeve runs on its own allocated capital; the
combined equity is their sum.

Design
------
Asset x timeframe = one sleeve.  All sleeves use the same strategy module
(trend_following_v8_ecap60_add80).  This is portfolio construction, not
alpha research.

Default sleeves (equal-weight 25% each):
    BTC 1H  —  1-hour bars, optional calibration
    BTC 4H  —  4-hour resampled bars
    ETH 1H  —  1-hour bars  (requires --eth-data)
    ETH 4H  —  4-hour resampled bars  (requires --eth-data)

Usage examples
--------------
# Equal-weight BTC-only (no ETH data):
python scripts/run_fund_portfolio.py --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv --calibrate

# Full 4-sleeve equal-weight with ETH:
python scripts/run_fund_portfolio.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --calibrate

# Tilted weights (BTC 60% / ETH 40%, each split 60/40 across timeframes):
python scripts/run_fund_portfolio.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --weights tilted --calibrate

# Custom date range:
python scripts/run_fund_portfolio.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --start 2022-01-01 --end 2022-12-31 --calibrate

PowerShell (no line continuation):
python scripts\\run_fund_portfolio.py --btc-data data\\btcusd_3600s_2019-01-01_to_2025-12-30.csv --eth-data data\\ethusd_3600s_2019-01-01_to_2025-12-30.csv --calibrate
"""

from __future__ import annotations

import argparse
import logging
import os
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
log = logging.getLogger("run_fund")

import numpy as np
import pandas as pd

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.resampler import resample_ohlcv, align_equity_curves
from research.harness.backtest_engine import run_backtest, BacktestResult
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import compute_metrics, BacktestMetrics
from research.harness.artifacts import save_artifacts
from research.strategies import REGISTRY as STRATEGY_REGISTRY

STRATEGY_NAME = "trend_following_v8_ecap60_add80"  # Fund v1 default

# ── Profile registry ───────────────────────────────────────────────────────────
# fund_v1_current is the default and preserves existing behavior exactly.
# fund_v2_crypto_hybrid_eth4h_cap75 is a research/paper candidate — not live.
PROFILES: dict[str, dict[str, str]] = {
    "fund_v1_current": {
        "BTC_1H": "trend_following_v8_ecap60_add80",
        "BTC_4H": "trend_following_v8_ecap60_add80",
        "ETH_1H": "trend_following_v8_ecap60_add80",
        "ETH_4H": "trend_following_v8_ecap60_add80",
    },
    # Research/paper candidate only. Not the default. Not live. Not Fund v1.
    "fund_v2_crypto_hybrid_eth4h_cap75": {
        "BTC_1H": "trend_following_v8_ecap75",
        "BTC_4H": "trend_following_v8_ecap75",
        "ETH_1H": "trend_following_v8_ecap75",
        "ETH_4H": "trend_following_v8_cap75",
    },
}


# ── Sleeve definition ──────────────────────────────────────────────────────────

@dataclass
class SleeveConfig:
    label: str          # e.g. "BTC_1H"
    asset: str          # "BTC" or "ETH"
    timeframe: str      # "1H" or "4H"
    weight: float       # fraction of total capital [0, 1]
    data_path: str
    strategy_name: str = STRATEGY_NAME  # resolved from the selected profile
    calibrated: bool = False


def _build_sleeves(args: argparse.Namespace, profile: str) -> list[SleeveConfig]:
    """Construct active sleeve list from CLI args, weight preset, and profile."""
    has_eth = bool(args.eth_data)

    # Raw weight map: label -> weight (before normalisation)
    if args.weights == "equal":
        raw: dict[str, float] = {
            "BTC_1H": 1.0,
            "BTC_4H": 1.0,
            "ETH_1H": 1.0,
            "ETH_4H": 1.0,
        }
    else:  # tilted: BTC 60% / ETH 40%, 1H 60% / 4H 40% within each
        raw = {
            "BTC_1H": 0.60 * 0.60,
            "BTC_4H": 0.60 * 0.40,
            "ETH_1H": 0.40 * 0.60,
            "ETH_4H": 0.40 * 0.40,
        }

    # Drop ETH sleeves if no data provided
    if not has_eth:
        for k in list(raw.keys()):
            if k.startswith("ETH"):
                del raw[k]
        if not raw:
            log.error("No sleeves remain after filtering. Provide --eth-data or use BTC-only.")
            sys.exit(1)

    total = sum(raw.values())
    sleeve_strategy_map = PROFILES[profile]
    sleeves = []
    for label, w in raw.items():
        asset = label.split("_")[0]
        tf    = label.split("_")[1]
        data  = args.btc_data if asset == "BTC" else args.eth_data
        sleeves.append(SleeveConfig(
            label=label,
            asset=asset,
            timeframe=tf,
            weight=w / total,
            data_path=data,
            strategy_name=sleeve_strategy_map[label],
            calibrated=args.calibrate,
        ))
    return sleeves


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _fmt_row(
    label: str,
    m: BacktestMetrics,
    width: int = 10,
) -> str:
    return (
        f"  {label:<16}"
        f" {m.cagr_pct:>{width}.2f}%"
        f" {m.max_drawdown_pct:>{width}.2f}%"
        f" {m.sharpe:>{width}.3f}"
        f" {m.calmar:>{width}.3f}"
        f" {m.n_trades:>{width}}"
        f" {m.avg_exit_entry_notional_ratio:>{width}.3f}x"
        f" {m.total_fees_paid:>{width},.0f}"
        f" {m.total_slippage_cost:>{width},.0f}"
    )


def _print_sleeve_table(
    sleeves: list[SleeveConfig],
    sleeve_metrics: dict[str, BacktestMetrics],
) -> None:
    hdr = (
        f"  {'Sleeve':<16}"
        f" {'CAGR%':>11}"
        f" {'MaxDD%':>11}"
        f" {'Sharpe':>11}"
        f" {'Calmar':>11}"
        f" {'Trades':>11}"
        f" {'Exit/Entry':>11}"
        f" {'Fees $':>11}"
        f" {'Slip $':>11}"
    )
    sep = "  " + "-" * (len(hdr) - 2)
    print(hdr)
    print(sep)
    for s in sleeves:
        m = sleeve_metrics[s.label]
        cal_tag = "*" if s.calibrated else " "
        print(_fmt_row(f"{s.label}{cal_tag}", m))


def _print_portfolio_table(m: BacktestMetrics) -> None:
    w = 14
    print(f"  {'Total Return':<22} {m.total_return_pct:>{w}.2f}%")
    print(f"  {'CAGR':<22} {m.cagr_pct:>{w}.2f}%")
    print(f"  {'Max Drawdown':<22} {m.max_drawdown_pct:>{w}.2f}%")
    print(f"  {'Sharpe':<22} {m.sharpe:>{w}.3f}")
    print(f"  {'Calmar':<22} {m.calmar:>{w}.3f}")
    print(f"  {'Ann. Vol':<22} {m.volatility_ann_pct:>{w}.2f}%")
    print(f"  {'Trades (total)':<22} {m.n_trades:>{w}}")
    print(f"  {'Total Fees $':<22} {m.total_fees_paid:>{w},.0f}")
    print(f"  {'Total Slippage $':<22} {m.total_slippage_cost:>{w},.0f}")


def _print_corr_matrix(corr: pd.DataFrame) -> None:
    labels = list(corr.columns)
    col_w = 10
    header = f"  {'':16}" + "".join(f"{l:>{col_w}}" for l in labels)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for row_label in labels:
        row = f"  {row_label:<16}"
        for col_label in labels:
            val = corr.loc[row_label, col_label]
            row += f"{val:>{col_w}.3f}"
        print(row)


# ── Chart ──────────────────────────────────────────────────────────────────────

def _save_fund_chart(
    aligned: pd.DataFrame,
    portfolio_equity: pd.Series,
    sleeves: list[SleeveConfig],
    out_path: Path,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as mticker
    except ImportError:
        log.warning("matplotlib not available — skipping chart")
        return

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    fig.patch.set_facecolor("#1a1a2e")
    for ax in axes:
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="#cccccc")
        ax.xaxis.label.set_color("#cccccc")
        ax.yaxis.label.set_color("#cccccc")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444466")

    # Panel 1: portfolio equity + drawdown
    ax1 = axes[0]
    port_norm = portfolio_equity / portfolio_equity.iloc[0] * 100
    ax1.plot(port_norm.index, port_norm.values, color="#00d4ff", linewidth=1.5, label="Portfolio")

    running_max = port_norm.cummax()
    drawdown = (port_norm - running_max) / running_max * 100
    ax1.fill_between(drawdown.index, drawdown.values, 0, alpha=0.25, color="#ff4466")

    ax1.set_ylabel("NAV (rebased 100)", color="#cccccc")
    ax1.set_title("Fund Portfolio — Equity & Drawdown", color="#ffffff", pad=10)
    ax1.legend(loc="upper left", facecolor="#1a1a2e", labelcolor="#cccccc")
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))

    # Panel 2: per-sleeve equity (normalised)
    ax2 = axes[1]
    colours = ["#f5a623", "#7ed321", "#bd10e0", "#4a90e2"]
    for (s, colour) in zip(sleeves, colours):
        if s.label in aligned.columns:
            curve = aligned[s.label]
            norm  = curve / curve.iloc[0] * 100
            cal_tag = "*" if s.calibrated else ""
            ax2.plot(norm.index, norm.values, color=colour,
                     linewidth=0.9, alpha=0.85, label=f"{s.label}{cal_tag} ({s.weight:.0%})")

    ax2.set_ylabel("NAV (rebased 100)", color="#cccccc")
    ax2.set_title("Per-Sleeve Equity (normalised)", color="#ffffff", pad=10)
    ax2.legend(loc="upper left", facecolor="#1a1a2e", labelcolor="#cccccc", fontsize=8)
    ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))

    plt.tight_layout(pad=1.5)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Chart saved: %s", out_path)


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Multi-sleeve fund portfolio runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True, help="Path to BTC/USD 1H OHLCV CSV")
    p.add_argument("--eth-data", default=None,  help="Path to ETH/USD 1H OHLCV CSV (optional)")
    p.add_argument("--capital",  type=float, default=100_000.0, help="Total portfolio capital (USD)")
    p.add_argument("--start",    default=None, help="Start date YYYY-MM-DD")
    p.add_argument("--end",      default=None, help="End date YYYY-MM-DD")
    p.add_argument(
        "--weights",
        choices=["equal", "tilted"],
        default="equal",
        help=(
            "equal: 25%% each sleeve.  "
            "tilted: BTC 60%% / ETH 40%%, 1H 60%% / 4H 40%% within each asset."
        ),
    )
    p.add_argument(
        "--profile",
        choices=list(PROFILES.keys()),
        default="fund_v1_current",
        help=(
            "Portfolio profile to run. Default: fund_v1_current (existing behavior unchanged). "
            "'fund_v2_crypto_hybrid_eth4h_cap75' is a research/paper candidate — not live."
        ),
    )
    p.add_argument("--calibrate",    action="store_true", help="Load ML calibrators where available")
    p.add_argument("--calibrators-dir", default=None)
    p.add_argument("--fee",          type=float, default=None)
    p.add_argument("--base-slippage", type=float, default=None)
    p.add_argument("--cooldown",     type=int,   default=None)
    p.add_argument("--rebalance-threshold", type=float, default=None)
    p.add_argument("--out-dir",      default=None)
    p.add_argument("--no-chart",     action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    sleeves = _build_sleeves(args, args.profile)

    # ── Execution config ───────────────────────────────────────────────────────
    exec_config = ExecutionConfig.from_env()
    if args.fee is not None:
        exec_config.taker_fee_rate = args.fee
    if args.base_slippage is not None:
        exec_config.base_slippage_bps = args.base_slippage
    if args.cooldown is not None:
        exec_config.cooldown_bars = args.cooldown
    rebalance_threshold = (
        args.rebalance_threshold
        if args.rebalance_threshold is not None
        else float(os.getenv("REBALANCE_THRESHOLD", "0.02"))
    )

    # ── Load calibrators (per unique strategy in the selected profile) ──────────
    calibrators: dict | None = None
    if args.calibrate:
        try:
            from research.ml.calibration.model_store import load_calibrator
            calibrators = {}
            unique_strats = set(PROFILES[args.profile].values())
            for sname in unique_strats:
                cal = load_calibrator(sname, models_dir=args.calibrators_dir)
                if cal is not None and cal.is_fitted:
                    calibrators[sname] = cal
                    log.info("Calibrator loaded for %s", sname)
                else:
                    log.warning(
                        "No fitted calibrator for %s — sleeve(s) will run uncalibrated", sname
                    )
        except ImportError:
            log.warning("ML calibration not available — skipping")

    # ── Load data (once per unique path+asset) ─────────────────────────────────
    raw_data: dict[str, pd.DataFrame] = {}
    for s in sleeves:
        key = f"{s.asset}_{s.data_path}"
        if key not in raw_data:
            log.info("Loading %s data: %s", s.asset, s.data_path)
            df = load_ohlcv(s.data_path, start=args.start, end=args.end, asset=s.asset)
            for w in validate_ohlcv(df):
                log.warning("Data warning [%s]: %s", s.asset, w)
            log.info(
                "Loaded %d bars  %s -> %s  [%s]",
                len(df), df.index[0], df.index[-1], s.asset,
            )
            raw_data[key] = df

    # ── Run each sleeve ────────────────────────────────────────────────────────
    sleeve_results: dict[str, BacktestResult] = {}
    for s in sleeves:
        key = f"{s.asset}_{s.data_path}"
        df = raw_data[key]

        if s.timeframe == "4H":
            df = resample_ohlcv(df, "4h")
            log.info(
                "Resampled %s to 4H: %d bars  %s -> %s",
                s.asset, len(df), df.index[0], df.index[-1],
            )

        sleeve_capital = args.capital * s.weight
        cal_tag = " (calibrated)" if (s.calibrated and calibrators) else ""
        log.info(
            "Running sleeve %s [%s] — $%.0f (%.0f%%)%s",
            s.label, s.strategy_name, sleeve_capital, s.weight * 100, cal_tag,
        )

        sleeve_strategy = STRATEGY_REGISTRY[s.strategy_name]
        result = run_backtest(
            df=df,
            strategy_module=sleeve_strategy,
            initial_capital=sleeve_capital,
            exec_config=exec_config,
            rebalance_threshold=rebalance_threshold,
            asset=s.asset,
            calibrators=calibrators if s.calibrated else None,
        )
        sleeve_results[s.label] = result

    # ── Align equity curves & build portfolio equity ───────────────────────────
    raw_curves = {s.label: sleeve_results[s.label].equity_curve for s in sleeves}
    aligned = align_equity_curves(raw_curves, base_freq="1h")
    portfolio_equity = aligned.sum(axis=1)
    portfolio_equity.name = "equity"

    # ── Compute per-sleeve metrics ─────────────────────────────────────────────
    sleeve_metrics: dict[str, BacktestMetrics] = {}
    for s in sleeves:
        r = sleeve_results[s.label]
        sleeve_metrics[s.label] = compute_metrics(
            r.equity_curve,
            r.trades,
            {
                "strategy_id": s.strategy_name,
                "asset": s.asset,
                "timeframe": s.timeframe,
                "initial_capital": args.capital * s.weight,
            },
        )

    # ── Compute portfolio metrics ──────────────────────────────────────────────
    all_trades = [t for s in sleeves for t in sleeve_results[s.label].trades]
    unique_strats = sorted(set(s.strategy_name for s in sleeves))
    portfolio_params = {
        "profile": args.profile,
        "strategy_id": "fund_portfolio",
        "sleeve_strategies": {s.label: s.strategy_name for s in sleeves},
        "initial_capital": args.capital,
        "n_sleeves": len(sleeves),
        "weights": args.weights,
        "calibrated": bool(args.calibrate and calibrators),
        "start": str(aligned.index[0]),
        "end":   str(aligned.index[-1]),
    }
    portfolio_m = compute_metrics(portfolio_equity, all_trades, portfolio_params)

    # ── Correlation matrix (daily returns) ────────────────────────────────────
    daily = aligned.resample("1D").last().dropna(how="all")
    daily_returns = daily.pct_change().dropna(how="all")
    corr = daily_returns.corr()

    # ── Print output ───────────────────────────────────────────────────────────
    cal_str = " (calibrated)" if (args.calibrate and calibrators) else ""
    weights_str = args.weights.upper()
    n_active = len(sleeves)
    strategy_display = (
        unique_strats[0] if len(unique_strats) == 1
        else "mixed — " + ", ".join(unique_strats)
    )

    print("\n" + "=" * 100)
    print(f"  FUND PORTFOLIO — {n_active} sleeves  |  {weights_str} weights{cal_str}")
    print(f"  Profile:  {args.profile}")
    print(f"  Strategy: {strategy_display}")
    print(f"  Capital:  ${args.capital:,.0f}  |  "
          f"Period: {str(aligned.index[0])[:10]} -> {str(aligned.index[-1])[:10]}")
    print("=" * 100)

    print("\n  PER-SLEEVE METRICS  (* = calibrated)")
    _print_sleeve_table(sleeves, sleeve_metrics)

    print("\n  PORTFOLIO METRICS")
    print("  " + "-" * 50)
    _print_portfolio_table(portfolio_m)

    print("\n  DAILY-RETURN CORRELATION MATRIX")
    print("  " + "-" * 50)
    _print_corr_matrix(corr)

    print("\n  SLEEVE WEIGHTS")
    for s in sleeves:
        cal_tag = " *" if (s.calibrated and calibrators) else ""
        print(f"  {s.label:<12}  {s.weight:>6.1%}  ->  ${args.capital * s.weight:>10,.0f}{cal_tag}")

    print("=" * 100 + "\n")

    # ── Save artifacts ─────────────────────────────────────────────────────────
    run_id = (
        f"{args.profile}"
        f"_{args.weights}"
        f"{'_cal' if (args.calibrate and calibrators) else ''}"
        f"_{n_active}s"
        f"_{str(aligned.index[0])[:10]}_{str(aligned.index[-1])[:10]}"
    )
    out_dir = Path(args.out_dir) if args.out_dir else Path("artifacts") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    equity_df = pd.DataFrame({
        "portfolio": portfolio_equity,
        **{s.label: aligned[s.label] for s in sleeves},
    })
    equity_df.to_csv(out_dir / "equity_curves.csv")
    corr.to_csv(out_dir / "correlation_matrix.csv")
    daily_returns.to_csv(out_dir / "daily_returns.csv")

    for s in sleeves:
        m = sleeve_metrics[s.label]
        import json
        summary = {**m.__dict__, "sleeve": s.label, "weight": s.weight}
        (out_dir / f"sleeve_{s.label}.json").write_text(
            json.dumps(summary, indent=2, default=str)
        )

    import json
    port_summary = {**portfolio_m.__dict__, **portfolio_params}
    (out_dir / "portfolio_summary.json").write_text(
        json.dumps(port_summary, indent=2, default=str)
    )

    if not args.no_chart:
        _save_fund_chart(
            aligned=aligned,
            portfolio_equity=portfolio_equity,
            sleeves=sleeves,
            out_path=out_dir / "fund_chart.png",
        )

    log.info("Artifacts saved to: %s", out_dir)
    print(f"  Artifacts: {out_dir}\n")


if __name__ == "__main__":
    main()
