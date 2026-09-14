"""Continuous spot inventory, weekly mixture selection and an execution ablation."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.fresh_discovery.accounting import rebalance
from .design import FEATURES, LABEL_COST, SCORE_MARGIN, policies
from .models import decision_indices


def select_mixture(score, previous, expert_distance):
    """Fixed cost-sensitive hurdle, not a statistical confidence interval."""
    hurdle = SCORE_MARGIN+LABEL_COST*expert_distance
    return (1. if score>hurdle else 0. if score < -hurdle else previous), hurdle


def make_schedules(panel, predictions, first):
    lookup = {(row.profile, row.model, row.signal_index): row for row in predictions.itertuples()}
    due = set(decision_indices(panel, first))
    schedules, rows, decisions = {}, [], []
    for policy in policies():
        schedule, mixture = {}, .5
        for t in range(first, len(panel.dates)-3):
            if policy.role=="benchmark":
                if t>first:
                    continue
                target = np.array(dict(btc_buy_hold=[1.,0.], eth_buy_hold=[0.,1.],
                                       mix_buy_hold=[.5,.5], usd_cash=[0.,0.])[policy.family])
                coefficient = np.nan
            else:
                trend, allocation = panel.trend[policy.target][t], panel.allocation[policy.target][t]
                score, hurdle, fit_id = np.nan, np.nan, ""
                if policy.family=="trend":
                    mixture = 1.
                elif policy.family=="allocation":
                    mixture = 0.
                elif policy.family=="fixed_blend":
                    mixture = .5
                elif t in due:
                    if policy.family=="state_rule":
                        # Predetermined rule: favor protection when broad trend agreement
                        # is weak or fast volatility is at least 25% above slow volatility.
                        mixture = float(panel.x[t, FEATURES.index("trend_agreement")]<2/3 or
                                        panel.x[t, FEATURES.index("volatility_ratio")]>1.25)
                    else:
                        prediction = lookup[(policy.target, policy.family, t)]
                        score, fit_id = prediction.predicted_relative_log_return, prediction.fit_id
                        mixture, hurdle = select_mixture(score, mixture, float(np.abs(trend-allocation).sum()))
                if t in due:
                    decisions.append(dict(policy=policy.name, signal_index=t, signal_bar_start=str(panel.dates[t]),
                                          mixture=mixture, score=score, hurdle=hurdle, fit_id=fit_id))
                target = mixture*trend+(1-mixture)*allocation
                coefficient = mixture
                if np.sqrt(max(0., target @ panel.cov[t] @ target))>policy.target+1e-10:
                    raise ValueError("Mixture exceeds target risk budget")
            schedule[t] = (target, coefficient)
            rows.append(dict(policy=policy.name, signal_index=t, signal_bar_start=str(panel.dates[t]),
                             feature_available=str(panel.dates[t]+pd.Timedelta(days=1)),
                             base_fill_time=str(panel.dates[t]+pd.Timedelta(days=2)),
                             BTC=target[0], ETH=target[1], USD=1-target.sum(), mixture=coefficient))
        schedules[policy.name] = schedule
    return schedules, pd.DataFrame(rows), pd.DataFrame(decisions)


def should_trade(current_weights, target, covariance, risk_budget, band):
    if band==0:
        return True, "exact"
    risk = np.sqrt(max(0., current_weights @ covariance @ current_weights))
    if risk>risk_budget+1e-10:
        return True, "risk_reduction"
    if target.sum()<1e-12 and current_weights.sum()>1e-12:
        return True, "full_exit"
    if np.abs(target-current_weights).sum()>=band:
        return True, "outside_band"
    return False, "inside_band"


def simulate(panel, schedule, policy, cost_bps, delay, first):
    if cost_bps<0 or delay<0 or not schedule or min(schedule)<first:
        raise ValueError("Invalid execution settings")
    start, end = first+2, len(panel.dates)-1
    for t, (weights, _) in schedule.items():
        if (t>=end or np.shape(weights)!=(2,) or not np.isfinite(weights).all()
                or (weights<0).any() or weights.sum()>1+1e-12):
            raise ValueError("Invalid spot target")
    orders = {t+2+delay: (t, w, m) for t,(w,m) in schedule.items() if t+2+delay<end}
    orders[end] = (-1, np.zeros(2), np.nan)
    units, cash, previous_nav = np.zeros(2), 1., 1.
    previous_close = panel.closes[start-1]
    rows = []
    for t in range(start, end+1):
        opening, closing = panel.opens[t], panel.closes[t]
        pnl = units*(opening-previous_close)
        values = units*opening
        pre_nav = float(cash+values.sum())
        if pre_nav<=0:
            raise ValueError("Insolvent portfolio")
        fees, trades = np.zeros(2), np.zeros(2)
        signal, mixture, execute, reason = -2, np.nan, False, "no_order"
        if t in orders:
            signal, target, mixture = orders[t]
            if signal==first or t==end or policy.role=="benchmark":
                execute, reason = True, "boundary_or_benchmark"
            else:
                execute, reason = should_trade(values/pre_nav, target, panel.cov[signal], policy.target, policy.band)
            if execute:
                values, cash, fees, trades = rebalance(values, cash, target, cost_bps/10_000)
                units = values/opening
        pnl += units*(closing-opening)
        values = units*closing
        nav = float(cash+values.sum())
        residual = nav-previous_nav-pnl.sum()+fees.sum()
        if nav<=0 or cash < -1e-10*nav or abs(residual)>1e-10*previous_nav:
            raise ValueError("Cash/inventory/P&L reconciliation failed")
        rows.append(dict(date=str(panel.dates[t].date()), nav=nav, **{"return": nav/previous_nav-1},
                         turnover=float(np.abs(trades).sum())/pre_nav, execution_cost=float(fees.sum())/previous_nav,
                         gross_market_pnl=float(pnl.sum())/previous_nav,
                         BTC_weight=float(values[0])/nav, ETH_weight=float(values[1])/nav, USD_weight=cash/nav,
                         BTC_pnl=float(pnl[0]-fees[0])/previous_nav, ETH_pnl=float(pnl[1]-fees[1])/previous_nav,
                         risky_exposure=float(values.sum())/nav, mixture=mixture,
                         signal_bar_start=str(panel.dates[signal]) if signal>=0 else "",
                         feature_available=str(panel.dates[signal]+pd.Timedelta(days=1)) if signal>=0 else "",
                         fill_time=str(panel.dates[t]) if execute else "", executed=execute, execution_reason=reason,
                         terminal_liquidation=t==end, accounting_residual=residual/previous_nav))
        previous_nav, previous_close = nav, closing
    if np.abs(units).sum()>1e-12:
        raise ValueError("Portfolio did not liquidate")
    return pd.DataFrame(rows)
