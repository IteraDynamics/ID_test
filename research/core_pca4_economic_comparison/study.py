from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from research.conditional_market_behavior.study import add_forward_outcomes
from research.multidimensional_regimes.study import panel_from_hourly
from research.regime_state_compression.study import CompressionModel

YEARS = tuple(range(2020, 2026))
ASSETS = ('BTC', 'ETH')
TIMEFRAMES = (1, 4)
RISK_HORIZON_DAYS = 7
RIDGE_ALPHA = 10.0
MULTIPLIER_BOUNDS = (0.5, 1.5)
COST_BPS = (0, 5, 10, 20)
PCS = ('pc1', 'pc2', 'pc3', 'pc4')
TREND_DIRECTION = {'TREND_UP': 1.0, 'TREND_DOWN': -1.0}


def _decoder(core_plus_pca4: bool):
    transformers = [('core', OneHotEncoder(handle_unknown='ignore'), ['core_label'])]
    if core_plus_pca4:
        transformers.append(('pc', StandardScaler(), list(PCS)))
    return make_pipeline(ColumnTransformer(transformers), Ridge(alpha=RIDGE_ALPHA))


def _risk_multiplier(predicted_log_variance: np.ndarray, reference_variance: float) -> np.ndarray:
    predicted_variance = np.exp(np.asarray(predicted_log_variance, dtype=float))
    out = np.ones(len(predicted_variance), dtype=float)
    valid = np.isfinite(predicted_variance) & (predicted_variance > 0) & np.isfinite(reference_variance) & (reference_variance > 0)
    out[valid] = np.sqrt(reference_variance / predicted_variance[valid])
    return np.clip(out, *MULTIPLIER_BOUNDS)


def _metrics(returns: pd.Series, exposure: pd.Series, turnover: pd.Series) -> dict:
    r = returns.astype(float)
    n = len(r)
    if n == 0:
        return dict(observations=0)
    wealth = (1.0 + r).cumprod()
    cumulative = float(wealth.iloc[-1] - 1.0)
    years = n / 365.25
    cagr = float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 and wealth.iloc[-1] > 0 else None
    vol = float(r.std(ddof=1) * np.sqrt(365.25)) if n > 1 else None
    sharpe = float(r.mean() / r.std(ddof=1) * np.sqrt(365.25)) if n > 1 and r.std(ddof=1) > 0 else None
    drawdown = wealth / wealth.cummax() - 1.0
    max_dd = float(drawdown.min())
    calmar = float(cagr / abs(max_dd)) if cagr is not None and max_dd < 0 else None
    return dict(observations=n, cumulative_return=cumulative, cagr=cagr, annualized_volatility=vol,
                sharpe=sharpe, max_drawdown=max_dd, calmar=calmar,
                mean_absolute_exposure=float(exposure.abs().mean()), turnover=float(turnover.sum()),
                mean_turnover=float(turnover.mean()), fraction_invested=float(exposure.ne(0).mean()))


def evaluate(hourly: pd.DataFrame, asset: str, hours: int, years=YEARS) -> dict:
    base = add_forward_outcomes(panel_from_hourly(hourly, hours), hourly)
    outputs = {'metrics': [], 'pairs': [], 'fits': []}
    target = f'log_variance_{RISK_HORIZON_DAYS}d'
    for year in years:
        cutoff = pd.Timestamp(f'{year}-01-01', tz='UTC')
        finish = pd.Timestamp(f'{year+1}-01-01', tz='UTC')
        fitting = base.loc[(base.index < cutoff) & (base.label_end < cutoff)].copy()
        evaluation = base.loc[(base.index >= cutoff) & (base.index < finish)].copy()
        if evaluation.empty:
            raise ValueError(f'No evaluation rows for {asset}/{hours}/{year}')
        cm = CompressionModel().fit(fitting)
        train = cm.transform(fitting)
        test = cm.transform(evaluation)
        matured = train.loc[train[f'outcome_end_{RISK_HORIZON_DAYS}d'] < cutoff].dropna(subset=[target]).copy()
        if len(matured) < 250:
            raise ValueError('Insufficient matured risk outcomes')
        if not (matured.label_end.max() < cutoff):
            raise ValueError('Training maturity boundary violation')
        reference_variance = float(np.exp(matured[target].mean()))
        direction = test.core_label.map(TREND_DIRECTION).fillna(0.0).astype(float)
        next_return = np.expm1(test['log_return_1d'].astype(float))
        common = next_return.notna()
        arms = {}
        for name, use_pca in [('core', False), ('core_plus_pca4', True)]:
            model = _decoder(use_pca)
            cols = ['core_label', *PCS] if use_pca else ['core_label']
            model.fit(matured[cols], matured[target])
            pred = pd.Series(model.predict(test[cols]), index=test.index, dtype=float)
            multiplier = pd.Series(_risk_multiplier(pred.to_numpy(), reference_variance), index=test.index)
            if use_pca:
                unavailable = ~test[list(PCS)].notna().all(axis=1)
                multiplier.loc[unavailable] = 1.0
            exposure = direction * multiplier
            turnover = exposure.diff().abs()
            if len(turnover):
                turnover.iloc[0] = abs(exposure.iloc[0])
            gross = exposure * next_return
            arms[name] = dict(exposure=exposure, turnover=turnover, gross=gross)
            for bps in COST_BPS:
                net = gross - turnover * (bps / 10000.0)
                valid = common & net.notna() & exposure.notna() & turnover.notna()
                metrics = _metrics(net.loc[valid], exposure.loc[valid], turnover.loc[valid])
                outputs['metrics'].append(dict(asset=asset, timeframe=hours, year=year, arm=name,
                                               cost_bps=bps, **metrics))
        outputs['fits'].append(dict(asset=asset, timeframe=hours, year=year, fit_at=str(cutoff),
                                    training_rows=len(matured), evaluation_rows=int(common.sum()),
                                    latest_training_label_end=str(matured.label_end.max()),
                                    reference_variance=reference_variance,
                                    pca_explained_variance_ratio=cm.pca.explained_variance_ratio_[:4].tolist()))
        frame = pd.DataFrame(outputs['metrics'])
        fold = frame[(frame.asset == asset) & (frame.timeframe == hours) & (frame.year == year)]
        for bps in COST_BPS:
            a = fold[(fold.arm == 'core') & (fold.cost_bps == bps)].iloc[0]
            b = fold[(fold.arm == 'core_plus_pca4') & (fold.cost_bps == bps)].iloc[0]
            outputs['pairs'].append(dict(asset=asset, timeframe=hours, year=year, cost_bps=bps,
                cumulative_return_diff=float(b.cumulative_return-a.cumulative_return),
                sharpe_diff=(float(b.sharpe-a.sharpe) if pd.notna(a.sharpe) and pd.notna(b.sharpe) else None),
                max_drawdown_diff=float(b.max_drawdown-a.max_drawdown),
                calmar_diff=(float(b.calmar-a.calmar) if pd.notna(a.calmar) and pd.notna(b.calmar) else None)))
        print(f'{asset} {hours}H {year}: economic comparison complete', flush=True)
    return outputs


def summarize_gate(pairs: pd.DataFrame, metrics: pd.DataFrame) -> dict:
    primary = pairs[pairs.cost_bps == 10].dropna(subset=['sharpe_diff'])
    eligible = len(primary)
    wins = int((primary.sharpe_diff > 0).sum())
    mean_diff = float(primary.sharpe_diff.mean()) if eligible else None
    by_asset = {str(k): float(v) for k, v in primary.groupby('asset').sharpe_diff.mean().items()}
    by_timeframe = {str(k): float(v) for k, v in primary.groupby('timeframe').sharpe_diff.mean().items()}
    cost_means = {str(b): float(pairs[pairs.cost_bps == b].sharpe_diff.dropna().mean()) for b in COST_BPS}
    m10 = metrics[metrics.cost_bps == 10]
    core_dd = float(m10[m10.arm == 'core'].max_drawdown.mean())
    pca_dd = float(m10[m10.arm == 'core_plus_pca4'].max_drawdown.mean())
    core_mag = abs(core_dd)
    dd_ok = (abs(pca_dd) <= 1.10 * core_mag) if core_mag > 0 else (pca_dd >= core_dd)
    rules = {
        'wins_at_least_16_of_24': eligible == 24 and wins >= 16,
        'positive_mean_sharpe_diff_10bps': mean_diff is not None and mean_diff > 0,
        'positive_each_asset': len(by_asset) == 2 and all(v > 0 for v in by_asset.values()),
        'positive_each_timeframe': len(by_timeframe) == 2 and all(v > 0 for v in by_timeframe.values()),
        'drawdown_not_worse_by_more_than_10pct': bool(dd_ok),
        'positive_mean_sharpe_all_costs': all(v > 0 for v in cost_means.values()),
    }
    return dict(status='PASS' if all(rules.values()) else 'FAIL', eligible_folds=eligible,
                positive_sharpe_folds_10bps=wins, mean_sharpe_diff_10bps=mean_diff,
                mean_sharpe_diff_by_asset_10bps=by_asset, mean_sharpe_diff_by_timeframe_10bps=by_timeframe,
                mean_sharpe_diff_by_cost=cost_means, mean_core_max_drawdown_10bps=core_dd,
                mean_core_plus_pca4_max_drawdown_10bps=pca_dd, rules=rules)


__all__ = ['evaluate', 'summarize_gate', 'YEARS', 'ASSETS', 'TIMEFRAMES', 'RISK_HORIZON_DAYS',
           'RIDGE_ALPHA', 'MULTIPLIER_BOUNDS', 'COST_BPS', 'PCS', 'TREND_DIRECTION']
