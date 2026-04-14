"""Research harness — backtest performance metrics.

All metrics are computed from an equity curve and trade log.
No I/O, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

HOURS_PER_YEAR = 365.25 * 24
TRADING_DAYS_PER_YEAR = 365.25  # crypto — no market holidays


@dataclass
class BacktestMetrics:
    """Flat summary of backtest performance statistics."""

    # Returns
    total_return_pct: float
    cagr_pct: float

    # Risk
    max_drawdown_pct: float
    volatility_ann_pct: float

    # Risk-adjusted
    calmar: float
    sharpe: float

    # Trade statistics
    n_trades: int
    win_rate_pct: float
    avg_trade_return_pct: float
    avg_win_pct: float
    avg_loss_pct: float

    # Equity
    initial_equity: float
    final_equity: float

    # Period
    start: str
    end: str
    n_bars: int
    bars_per_year: float

    # Extra context
    strategy_id: str = "unknown"
    asset: str = "BTC"

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "start": self.start,
            "end": self.end,
            "n_bars": self.n_bars,
            "initial_equity": round(self.initial_equity, 2),
            "final_equity": round(self.final_equity, 2),
            "total_return_pct": round(self.total_return_pct, 4),
            "cagr_pct": round(self.cagr_pct, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "volatility_ann_pct": round(self.volatility_ann_pct, 4),
            "calmar": round(self.calmar, 4),
            "sharpe": round(self.sharpe, 4),
            "n_trades": self.n_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "avg_trade_return_pct": round(self.avg_trade_return_pct, 4),
            "avg_win_pct": round(self.avg_win_pct, 4),
            "avg_loss_pct": round(self.avg_loss_pct, 4),
        }

    def to_markdown(self) -> str:
        d = self.to_dict()
        lines = [
            f"# Backtest Results: {d['strategy_id']} / {d['asset']}",
            f"**Period:** {d['start']} → {d['end']}  ({d['n_bars']} bars)",
            "",
            "## Returns",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Initial Capital | ${d['initial_equity']:,.2f} |",
            f"| Final Equity | ${d['final_equity']:,.2f} |",
            f"| Total Return | {d['total_return_pct']:.2f}% |",
            f"| CAGR | {d['cagr_pct']:.2f}% |",
            "",
            "## Risk",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Max Drawdown | {d['max_drawdown_pct']:.2f}% |",
            f"| Ann. Volatility | {d['volatility_ann_pct']:.2f}% |",
            f"| Calmar Ratio | {d['calmar']:.3f} |",
            f"| Sharpe Ratio | {d['sharpe']:.3f} |",
            "",
            "## Trades",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Trades | {d['n_trades']} |",
            f"| Win Rate | {d['win_rate_pct']:.1f}% |",
            f"| Avg Trade Return | {d['avg_trade_return_pct']:.3f}% |",
            f"| Avg Win | {d['avg_win_pct']:.3f}% |",
            f"| Avg Loss | {d['avg_loss_pct']:.3f}% |",
        ]
        return "\n".join(lines)


def compute_metrics(
    equity_curve: pd.Series,
    trades: list,
    params: dict | None = None,
) -> BacktestMetrics:
    """Compute all performance metrics from an equity curve and trade list.

    Parameters
    ----------
    equity_curve :
        Series of NAV values, indexed by datetime.
    trades :
        List of TradeRecord objects (from BacktestResult.trades).
    params :
        Optional dict of backtest params (for labelling output).

    Returns
    -------
    BacktestMetrics
    """
    params = params or {}
    eq = equity_curve.dropna()

    if len(eq) < 2:
        return _empty_metrics(params)

    initial = float(eq.iloc[0])
    final = float(eq.iloc[-1])

    # ── Returns ───────────────────────────────────────────────────────
    total_ret = (final / initial - 1.0) * 100.0

    # Years elapsed — use actual index range
    n_bars = len(eq)
    bars_per_year = _infer_bars_per_year(eq)
    years = n_bars / bars_per_year if bars_per_year > 0 else 1.0
    cagr = ((final / initial) ** (1.0 / max(years, 1 / 365)) - 1.0) * 100.0

    # ── Drawdown ──────────────────────────────────────────────────────
    running_max = eq.cummax()
    drawdown = (eq - running_max) / running_max
    max_dd = float(drawdown.min()) * 100.0  # negative number, in %

    # ── Volatility ────────────────────────────────────────────────────
    bar_returns = eq.pct_change().dropna()
    vol_per_bar = float(bar_returns.std())
    vol_ann = vol_per_bar * np.sqrt(bars_per_year) * 100.0

    # ── Sharpe (bar returns, 0 risk-free) ─────────────────────────────
    mean_ret = float(bar_returns.mean())
    std_ret = float(bar_returns.std())
    sharpe = (mean_ret / std_ret * np.sqrt(bars_per_year)) if std_ret > 1e-12 else 0.0

    # ── Calmar ────────────────────────────────────────────────────────
    calmar = (cagr / abs(max_dd)) if abs(max_dd) > 1e-6 else 0.0

    # ── Trade stats ───────────────────────────────────────────────────
    n_trades, win_rate, avg_ret, avg_win, avg_loss = _trade_stats(trades, equity_curve)

    return BacktestMetrics(
        total_return_pct=round(total_ret, 4),
        cagr_pct=round(cagr, 4),
        max_drawdown_pct=round(max_dd, 4),
        volatility_ann_pct=round(vol_ann, 4),
        calmar=round(calmar, 4),
        sharpe=round(sharpe, 4),
        n_trades=n_trades,
        win_rate_pct=round(win_rate, 2),
        avg_trade_return_pct=round(avg_ret, 4),
        avg_win_pct=round(avg_win, 4),
        avg_loss_pct=round(avg_loss, 4),
        initial_equity=round(initial, 2),
        final_equity=round(final, 2),
        start=str(eq.index[0]),
        end=str(eq.index[-1]),
        n_bars=n_bars,
        bars_per_year=round(bars_per_year, 1),
        strategy_id=params.get("strategy_id", "unknown"),
        asset=params.get("asset", "BTC"),
    )


def _infer_bars_per_year(eq: pd.Series) -> float:
    """Infer bar frequency from the DatetimeIndex."""
    if not isinstance(eq.index, pd.DatetimeIndex) or len(eq) < 2:
        return HOURS_PER_YEAR  # default to hourly

    delta = (eq.index[-1] - eq.index[0]).total_seconds()
    n = len(eq) - 1
    if delta <= 0 or n <= 0:
        return HOURS_PER_YEAR

    bar_seconds = delta / n
    seconds_per_year = 365.25 * 24 * 3600
    return seconds_per_year / bar_seconds


def _trade_stats(trades: list, equity_curve: pd.Series) -> tuple[int, float, float, float, float]:
    """Compute trade-level statistics from round-trip pairs.

    Pairs BUY trades with subsequent SELL trades on bar_index basis.
    """
    if not trades:
        return 0, 0.0, 0.0, 0.0, 0.0

    # Build round-trip pairs: find consecutive BUY → SELL pairs
    buys = [t for t in trades if t.direction == "BUY"]
    sells = [t for t in trades if t.direction == "SELL"]
    if not buys or not sells:
        return len(trades), 0.0, 0.0, 0.0, 0.0

    # Simple pair-off: match each BUY to the next SELL after it
    paired_returns: list[float] = []
    sell_idx = 0
    for buy in buys:
        while sell_idx < len(sells) and sells[sell_idx].bar_index <= buy.bar_index:
            sell_idx += 1
        if sell_idx >= len(sells):
            break
        sell = sells[sell_idx]
        # Round-trip return (approximate, using prices)
        if buy.price > 0:
            rt_ret = (sell.price / buy.price - 1.0) * 100.0
            # Deduct total fee+slippage from both legs as % of entry
            cost_pct = (buy.fee_usd + buy.slippage_usd + sell.fee_usd + sell.slippage_usd) / (
                buy.notional_usd
            ) * 100.0 if buy.notional_usd > 0 else 0.0
            paired_returns.append(rt_ret - cost_pct)
        sell_idx += 1

    if not paired_returns:
        return len(trades), 0.0, 0.0, 0.0, 0.0

    arr = np.array(paired_returns)
    wins = arr[arr > 0]
    losses = arr[arr <= 0]
    win_rate = 100.0 * len(wins) / len(arr)
    avg_ret = float(np.mean(arr))
    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0

    return len(trades), win_rate, avg_ret, avg_win, avg_loss


def _empty_metrics(params: dict) -> BacktestMetrics:
    return BacktestMetrics(
        total_return_pct=0.0,
        cagr_pct=0.0,
        max_drawdown_pct=0.0,
        volatility_ann_pct=0.0,
        calmar=0.0,
        sharpe=0.0,
        n_trades=0,
        win_rate_pct=0.0,
        avg_trade_return_pct=0.0,
        avg_win_pct=0.0,
        avg_loss_pct=0.0,
        initial_equity=0.0,
        final_equity=0.0,
        start="",
        end="",
        n_bars=0,
        bars_per_year=HOURS_PER_YEAR,
        strategy_id=params.get("strategy_id", "unknown"),
        asset=params.get("asset", "BTC"),
    )
