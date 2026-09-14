"""Transparent descriptive screen statistics; no significance or promotion claims."""
from __future__ import annotations

import numpy as np
import pandas as pd


def metrics(frame: pd.DataFrame, cash_returns: np.ndarray,
            market_returns: np.ndarray) -> dict:
    r = frame["return"].to_numpy(float)
    if len(r) < 2 or len(r) != len(cash_returns) or len(r) != len(market_returns):
        raise ValueError("Metric observations must be paired")
    if not np.isfinite(np.r_[r, cash_returns, market_returns]).all() or (r <= -1).any():
        raise ValueError("Invalid metric inputs")
    excess = r - cash_returns
    market = market_returns - cash_returns
    wealth = np.r_[1.0, np.cumprod(1 + r)]
    dd = wealth / np.maximum.accumulate(wealth) - 1
    dates = pd.to_datetime(frame.date)
    years = ((dates.iloc[-1] - dates.iloc[0]).days + 1) / 365.25
    cagr = float(wealth[-1] ** (1 / years) - 1)
    vol = float(r.std(ddof=1) * np.sqrt(252))
    excess_vol = float(excess.std(ddof=1) * np.sqrt(252))
    max_dd = float(dd.min())
    underwater = longest = 0
    for value in dd[1:]:
        underwater = underwater + 1 if value < -1e-12 else 0
        longest = max(longest, underwater)
    beta = float(np.cov(excess, market, ddof=1)[0, 1] / market.var(ddof=1)) if market.var(ddof=1) > 1e-20 else None
    tail_n = max(1, int(np.ceil(len(r) * .05)))
    result = dict(observations=len(r), first_date=str(dates.iloc[0].date()),
                  last_date=str(dates.iloc[-1].date()), cagr=cagr,
                  annualized_mean_return=float(252 * r.mean()),
                  annualized_volatility=vol,
                  excess_sharpe=float(252 * excess.mean() / excess_vol) if excess_vol > 1e-12 else None,
                  calmar=cagr / abs(max_dd) if max_dd < -1e-12 else None,
                  max_drawdown=max_dd, longest_underwater_sessions=longest,
                  worst_day=float(r.min()), expected_shortfall_95=float(np.sort(r)[:tail_n].mean()),
                  certainty_equivalent_gamma3=float(252 * (r.mean() - 1.5 * r.var(ddof=1))),
                  spy_beta=beta,
                  descriptive_alpha_annual=float(252 * (excess.mean() - beta * market.mean())) if beta is not None else None,
                  # Ledger rounding can turn economically flat returns into +/- eps.
                  # This reporting tolerance does not alter returns or trading logic.
                  positive_day_fraction=float((r > 1e-12).mean()),
                  annual_one_way_turnover=float(frame.turnover.sum() / years),
                  mean_gross_exposure=float(frame.gross_risky_exposure.mean()),
                  max_gross_exposure=float(frame.gross_risky_exposure.max()),
                  mean_net_exposure=float(frame.net_risky_exposure.mean()),
                  rebalances=int(frame.rebalance.sum()),
                  annual_execution_drag=float(frame.execution_cost.sum() / years),
                  annual_funding_drag=float(frame.funding_cost.sum() / years),
                  annual_borrow_drag=float(frame.borrow_cost.sum() / years))
    return result


def summarize(ledgers: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary, annual, exclusions = [], [], []
    # One common frictionless BIL and SPY reference: costs/delays must not change
    # the benchmark used for excess returns or factor attribution.
    refs = ledgers[ledgers.scenario == "frictionless"]
    cash = refs[refs.policy == "bil_buy_hold"].set_index("date")["return"]
    market = refs[refs.policy == "spy_buy_hold"].set_index("date")["return"]
    for (scenario, policy), frame in ledgers.groupby(["scenario", "policy"], sort=True):
        frame = frame.sort_values("date").reset_index(drop=True)
        base = dict(scenario=scenario, policy=policy)
        for period, mask in (
            ("full", np.ones(len(frame), dtype=bool)),
            ("2008_2016", frame.date < "2017-01-01"),
            ("2017_2024", frame.date >= "2017-01-01"),
        ):
            selected = frame.loc[mask]
            if len(selected) > 1:
                summary.append(dict(**base, period=period,
                                    **metrics(selected, cash.loc[selected.date].to_numpy(),
                                              market.loc[selected.date].to_numpy())))
        year = frame.date.str[:4]
        for yr, selected in frame.groupby(year):
            r = selected["return"].to_numpy()
            annual.append(dict(**base, year=int(yr), observations=len(r),
                               total_return=float(np.prod(1 + r) - 1),
                               excess_mean_annual=float(252 * (r - cash.loc[selected.date]).mean())))
        # Descriptive deletion only. Do not label concatenated years an investable path.
        for yr in sorted(year.unique()):
            selected = frame.loc[year != yr]
            r = selected["return"].to_numpy()
            if len(r) < 2:
                continue
            ex = r - cash.loc[selected.date].to_numpy()
            vol = ex.std(ddof=1) * np.sqrt(252)
            exclusions.append(dict(**base, excluded_year=int(yr), observations=len(r),
                                   annualized_geometric_return=float(np.prod(1 + r) ** (252 / len(r)) - 1),
                                   excess_sharpe=float(252 * ex.mean() / vol) if vol > 1e-12 else None,
                                   status="DESCRIPTIVE_YEAR_DELETION_NOT_A_TRADING_PATH"))
    return (pd.DataFrame(summary), pd.DataFrame(annual),
            pd.DataFrame(exclusions, columns=["scenario", "policy", "excluded_year", "observations",
                                             "annualized_geometric_return", "excess_sharpe", "status"]))


def pareto_flags(frame: pd.DataFrame) -> pd.DataFrame:
    """CAGR/Sharpe/drawdown dominance, without an invented blended objective."""
    frame = frame.copy()
    frame["pareto_cagr_sharpe_drawdown"] = False
    for _, group in frame.groupby(["scenario", "period"]):
        values = group[["cagr", "excess_sharpe", "max_drawdown"]].to_numpy(float)
        for i, key in enumerate(group.index):
            if np.isfinite(values[i]).all():
                dominates = (values >= values[i]).all(axis=1) & (values > values[i]).any(axis=1)
                frame.loc[key, "pareto_cagr_sharpe_drawdown"] = not dominates.any()
    return frame
