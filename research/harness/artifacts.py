"""Research harness — artifact generation.

Saves backtest outputs to the artifacts/ directory:
- equity_curve.csv
- trades.csv
- summary.json
- summary.md
- chart.png (optional, requires matplotlib)
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from research.harness.backtest_engine import BacktestResult
from research.harness.metrics import BacktestMetrics

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))


def save_artifacts(
    result: BacktestResult,
    metrics: BacktestMetrics,
    run_id: str = "default",
    out_dir: Path | str | None = None,
    save_chart: bool = True,
) -> Path:
    """Save all backtest artifacts to disk.

    Parameters
    ----------
    result :
        BacktestResult from run_backtest().
    metrics :
        BacktestMetrics from compute_metrics().
    run_id :
        Label used to name output subdirectory.
    out_dir :
        Output directory.  Defaults to ARTIFACTS_DIR / run_id.
    save_chart :
        Whether to generate and save a chart PNG.

    Returns
    -------
    Path
        The output directory where artifacts were saved.
    """
    if out_dir is None:
        out_dir = ARTIFACTS_DIR / run_id
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Equity curve ─────────────────────────────────────────────────
    equity_df = pd.DataFrame({
        "equity": result.equity_curve,
        "exposure": result.position_series,
        "regime": result.regime_series.astype(str),
    })
    equity_df.index.name = "timestamp"
    equity_df.to_csv(out_dir / "equity_curve.csv")

    # ── Trades ───────────────────────────────────────────────────────
    if result.trades:
        trades_df = pd.DataFrame([
            {
                "bar_index": t.bar_index,
                "timestamp": t.timestamp,
                "direction": t.direction,
                "mid_price": t.mid_price,
                "effective_price": round(t.effective_price, 6),
                "qty": t.qty,
                "notional_usd": t.notional_usd,
                "fee_usd": round(t.fee_usd, 4),
                "slippage_usd": round(t.slippage_usd, 4),
                "spread_usd": round(t.spread_usd, 4),
                "cost_bps": round(t.cost_bps, 4),
                "prev_exposure": round(t.prev_exposure, 5),
                "new_exposure": round(t.new_exposure, 5),
                "reason": t.reason,
                "strategy_id": t.strategy_id,
            }
            for t in result.trades
        ])
        trades_df.to_csv(out_dir / "trades.csv", index=False)
    else:
        pd.DataFrame(columns=["bar_index", "timestamp", "direction", "mid_price", "effective_price", "cost_bps"]).to_csv(
            out_dir / "trades.csv", index=False
        )

    # ── Summary JSON ─────────────────────────────────────────────────
    summary = metrics.to_dict()
    summary["backtest_params"] = result.params
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    # ── Summary Markdown ─────────────────────────────────────────────
    with open(out_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write(metrics.to_markdown())
        f.write("\n\n---\n\n")
        f.write("## Backtest Parameters\n\n")
        for k, v in result.params.items():
            f.write(f"- **{k}**: {v}\n")

    # ── Chart PNG ────────────────────────────────────────────────────
    if save_chart:
        _save_chart(result, metrics, out_dir)

    return out_dir


def _save_chart(result: BacktestResult, metrics: BacktestMetrics, out_dir: Path) -> None:
    """Generate a 3-panel diagnostic chart."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        return

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    fig.suptitle(
        f"IteraDynamics Backtest — {metrics.strategy_id} / {metrics.asset}\n"
        f"CAGR: {metrics.cagr_pct:.1f}%  MaxDD: {metrics.max_drawdown_pct:.1f}%  "
        f"Sharpe: {metrics.sharpe:.2f}  Trades: {metrics.n_trades}",
        fontsize=11,
    )

    idx = result.equity_curve.index
    eq = result.equity_curve.values
    exp = result.position_series.values

    # Panel 1: Equity curve + drawdown fill
    ax1 = axes[0]
    ax1.plot(idx, eq, color="#2196F3", linewidth=1.2, label="NAV")
    running_max = result.equity_curve.cummax().values
    ax1.fill_between(idx, eq, running_max, alpha=0.25, color="red", label="Drawdown")
    ax1.set_ylabel("NAV ($)")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Panel 2: Exposure fraction
    ax2 = axes[1]
    ax2.fill_between(idx, exp, alpha=0.6, color="#4CAF50", label="Exposure")
    ax2.set_ylim(-0.05, 1.1)
    ax2.set_ylabel("Exposure")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Panel 3: Regime colour bands
    ax3 = axes[2]
    regime_colors = {
        "TREND_UP": "#4CAF50",
        "TREND_DOWN": "#F44336",
        "RANGE": "#9E9E9E",
        "VOL_COMPRESSION": "#2196F3",
        "VOL_EXPANSION": "#FF9800",
        "HIGH_VOL": "#E91E63",
        "UNKNOWN": "#BDBDBD",
    }
    regimes = result.regime_series.astype(str)
    # Draw regime as coloured background spans
    if len(idx) > 1:
        prev_regime = str(regimes.iloc[0])
        prev_i = 0
        for i in range(1, len(idx)):
            r = str(regimes.iloc[i])
            if r != prev_regime or i == len(idx) - 1:
                color = regime_colors.get(prev_regime, "#BDBDBD")
                ax3.axvspan(idx[prev_i], idx[i], alpha=0.4, color=color, label=prev_regime if prev_i == 0 else "")
                prev_regime = r
                prev_i = i

    # Add trade markers on equity panel
    if result.trades:
        buy_times = [pd.Timestamp(t.timestamp) for t in result.trades if t.direction == "BUY"]
        sell_times = [pd.Timestamp(t.timestamp) for t in result.trades if t.direction == "SELL"]
        if buy_times:
            buy_eq = [float(result.equity_curve.asof(bt)) for bt in buy_times]
            ax1.scatter(buy_times, buy_eq, marker="^", color="#4CAF50", s=30, zorder=5, label="Buy")
        if sell_times:
            sell_eq = [float(result.equity_curve.asof(st)) for st in sell_times]
            ax1.scatter(sell_times, sell_eq, marker="v", color="#F44336", s=30, zorder=5, label="Sell")

    # Legend for regimes
    from matplotlib.patches import Patch
    regime_shown = set(regimes.unique())
    patches = [Patch(color=regime_colors.get(r, "#BDBDBD"), label=r, alpha=0.6) for r in regime_shown]
    ax3.legend(handles=patches, loc="upper left", fontsize=7, ncol=3)
    ax3.set_ylabel("Regime")
    ax3.set_yticks([])
    ax3.grid(False)

    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(rotation=30)
    plt.tight_layout()
    plt.savefig(out_dir / "chart.png", dpi=120, bbox_inches="tight")
    plt.close(fig)
