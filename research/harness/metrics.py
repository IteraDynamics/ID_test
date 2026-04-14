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

    # Execution costs
    total_fees_paid: float
    total_slippage_cost: float
    avg_cost_per_trade_bps: float
    turnover_x: float               # sum(notional) / initial_capital

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
            "total_fees_paid": round(self.total_fees_paid, 2),
            "total_slippage_cost": round(self.total_slippage_cost, 2),
            "avg_cost_per_trade_bps": round(self.avg_cost_per_trade_bps, 2),
            "turnover_x": round(self.turnover_x, 4),
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
            "",
            "## Execution Costs",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Fees Paid | ${d['total_fees_paid']:,.2f} |",
            f"| Total Slippage Cost | ${d['total_slippage_cost']:,.2f} |",
            f"| Avg Cost / Trade | {d['avg_cost_per_trade_bps']:.1f} bps |",
            f"| Turnover | {d['turnover_x']:.2f}x |",
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

    # ── Execution cost aggregates ─────────────────────────────────────
    total_fees = sum(getattr(t, "fee_usd", 0.0) for t in trades)
    total_slippage = sum(
        getattr(t, "slippage_usd", 0.0) + getattr(t, "spread_usd", 0.0)
        for t in trades
    )
    cost_bps_list = [getattr(t, "cost_bps", 0.0) for t in trades]
    avg_cost_bps = float(np.mean(cost_bps_list)) if cost_bps_list else 0.0
    total_notional = sum(getattr(t, "notional_usd", 0.0) for t in trades)
    turnover_x = total_notional / initial if initial > 0 else 0.0

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
        total_fees_paid=round(total_fees, 2),
        total_slippage_cost=round(total_slippage, 2),
        avg_cost_per_trade_bps=round(avg_cost_bps, 2),
        turnover_x=round(turnover_x, 4),
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
    """Compute win rate using true equity-based round-trip cycles.

    A cycle is defined as the period during which the strategy holds a
    non-zero position continuously: from first entry (exposure crosses
    above zero) to full exit (exposure returns to zero).  The P&L of
    each cycle is measured from the equity curve value at the first BUY
    to the equity curve value at the last SELL in that cycle.

    This avoids the inflated win rate caused by pairing every small
    position *addition* (BUY rebalance) with the eventual exit SELL.
    That naive pairing always looks like a win in a sustained uptrend,
    regardless of whether the overall cycle was profitable.
    """
    if not trades:
        return 0, 0.0, 0.0, 0.0, 0.0

    if equity_curve is None or len(equity_curve) == 0:
        return len(trades), 0.0, 0.0, 0.0, 0.0

    # ── Group trades into continuous holding cycles ───────────────────
    # A cycle ends when a SELL trade brings the running exposure near 0.
    # We approximate this by detecting SELL trades that follow all BUYs
    # before the next BUY burst (i.e. the last SELL before a gap).

    sorted_trades = sorted(trades, key=lambda t: t.bar_index)

    cycles: list[tuple[int, int]] = []   # (entry_bar, exit_bar)
    cycle_start: int | None = None
    last_sell_bar: int | None = None

    for t in sorted_trades:
        if t.direction == "BUY":
            if cycle_start is None:
                cycle_start = t.bar_index
            last_sell_bar = None   # reset: still in a cycle
        elif t.direction == "SELL":
            last_sell_bar = t.bar_index

    # Re-scan to find actual cycle boundaries using exposure transitions
    # Strategy: each time we see a SELL and the next event is a BUY (or end),
    # that SELL closes the cycle.
    cycle_start = None
    i = 0
    while i < len(sorted_trades):
        t = sorted_trades[i]
        if t.direction == "BUY" and cycle_start is None:
            cycle_start = t.bar_index
        elif t.direction == "SELL":
            # Check if the next trade is a BUY (new cycle) or there is none
            next_is_buy_or_end = (
                i + 1 >= len(sorted_trades)
                or sorted_trades[i + 1].direction == "BUY"
            )
            if next_is_buy_or_end and cycle_start is not None:
                cycles.append((cycle_start, t.bar_index))
                cycle_start = None
        i += 1

    if not cycles:
        return len(trades), 0.0, 0.0, 0.0, 0.0

    # ── Measure each cycle's return from the equity curve ─────────────
    eq = equity_curve
    cycle_returns: list[float] = []

    for entry_bar, exit_bar in cycles:
        # Guard against out-of-range indices
        if entry_bar >= len(eq) or exit_bar >= len(eq):
            continue
        eq_entry = float(eq.iloc[entry_bar])
        eq_exit = float(eq.iloc[exit_bar])
        if eq_entry > 0:
            cycle_ret = (eq_exit / eq_entry - 1.0) * 100.0
            cycle_returns.append(cycle_ret)

    if not cycle_returns:
        return len(trades), 0.0, 0.0, 0.0, 0.0

    arr = np.array(cycle_returns)
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
        total_fees_paid=0.0,
        total_slippage_cost=0.0,
        avg_cost_per_trade_bps=0.0,
        turnover_x=0.0,
        initial_equity=0.0,
        final_equity=0.0,
        start="",
        end="",
        n_bars=0,
        bars_per_year=HOURS_PER_YEAR,
        strategy_id=params.get("strategy_id", "unknown"),
        asset=params.get("asset", "BTC"),
    )
