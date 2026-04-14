"""Diagnostic chart utilities.

Standalone plotting functions for regime analysis and multi-strategy comparison.
These functions do not depend on backtest internals — they accept plain Series/DataFrames.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np


def plot_regime_distribution(
    regime_series: pd.Series,
    out_path: Path | str | None = None,
    title: str = "Regime Distribution",
) -> None:
    """Bar chart of regime label frequency.

    Parameters
    ----------
    regime_series :
        Series of RegimeLabel (or str) values.
    out_path :
        Optional save path for the PNG.  If None, plt.show() is called.
    title :
        Chart title.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available — skipping chart.")
        return

    counts = regime_series.astype(str).value_counts().sort_values(ascending=False)
    pcts = 100 * counts / counts.sum()

    regime_colors = {
        "TREND_UP": "#4CAF50",
        "TREND_DOWN": "#F44336",
        "RANGE": "#9E9E9E",
        "VOL_COMPRESSION": "#2196F3",
        "VOL_EXPANSION": "#FF9800",
        "HIGH_VOL": "#E91E63",
        "UNKNOWN": "#BDBDBD",
    }
    colors = [regime_colors.get(r, "#9E9E9E") for r in pcts.index]

    fig, ax = plt.subplots(figsize=(9, 4))
    bars = ax.bar(pcts.index, pcts.values, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_title(title, fontsize=12)
    ax.set_ylabel("% of bars")
    ax.set_xlabel("Regime")

    for bar, val in zip(bars, pcts.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.3,
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    if out_path:
        plt.savefig(out_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


def plot_equity_comparison(
    equity_curves: dict[str, pd.Series],
    out_path: Path | str | None = None,
    title: str = "Strategy Equity Comparison",
    normalise: bool = True,
) -> None:
    """Overlay multiple equity curves on a single chart.

    Parameters
    ----------
    equity_curves :
        Dict of label → equity Series.
    out_path :
        Optional save path for PNG.
    title :
        Chart title.
    normalise :
        If True, all curves start at 1.0 (useful for comparison).
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available — skipping chart.")
        return

    color_cycle = [
        "#2196F3", "#4CAF50", "#FF9800", "#E91E63", "#9C27B0", "#00BCD4"
    ]

    fig, ax = plt.subplots(figsize=(12, 5))
    for i, (label, eq) in enumerate(equity_curves.items()):
        eq_plot = eq.dropna()
        if normalise and len(eq_plot) > 0 and eq_plot.iloc[0] != 0:
            eq_plot = eq_plot / eq_plot.iloc[0]
        color = color_cycle[i % len(color_cycle)]
        ax.plot(eq_plot.index, eq_plot.values, label=label, color=color, linewidth=1.2)

    ax.set_title(title, fontsize=12)
    ax.set_ylabel("Normalised NAV" if normalise else "NAV ($)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate(rotation=30)
    plt.tight_layout()

    if out_path:
        plt.savefig(out_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()
