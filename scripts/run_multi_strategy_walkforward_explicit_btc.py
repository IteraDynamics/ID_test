#!/usr/bin/env python
from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path


import pandas as pd

from research.harness.backtest_engine import BacktestResult, run_backtest
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import compute_metrics
from research.harness.resampler import align_equity_curves, resample_ohlcv
from research.strategies import REGISTRY as STRATEGY_REGISTRY
from research.strategies import trend_following_v11_explicit_btc
from scripts.cross_asset_state import compute_btc_macro_state, inject_btc_macro_state
from scripts.run_multi_strategy_fund import SleeveSpec, _build_sleeves, _load_asset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("wf_explicit_btc")

HEDGE_STRATEGY = "crash_short_v6"
MR_STRATEGY = "mean_reversion"
EQUITY_STRATEGY = "equity_sma175_v3"
GOLD_STRATEGY = "gold_sma_v1"


@dataclass
class WFFold:
    label: str
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Multi-strategy walk-forward with explicit BTC macro state",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", default=None)
    p.add_argument("--spy-data", default=None)
    p.add_argument("--qqq-data", default=None)
    p.add_argument("--bil-data", default=None)
    p.add_argument("--gld-data", default=None)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--trend-weight", type=float, default=0.60)
    p.add_argument("--hedge-weight", type=float, default=0.20)
    p.add_argument("--mr-weight", type=float, default=0.20)
    p.add_argument("--equity-weight", type=float, default=0.0)
    p.add_argument("--gold-weight", type=float, default=0.0)
    p.add_argument("--data-start", default="2019-01-01")
    p.add_argument("--oos-start", default="2021-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--equity-fee", type=float, default=0.0001)
    p.add_argument("--base-slippage", type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--cooldown", type=int, default=2)
    p.add_argument("--mr-cooldown", type=int, default=12)
    p.add_argument("--rebalance-threshold", type=float, default=0.02)
    p.add_argument("--out-dir", default="artifacts/wf_explicit_btc")
    return p.parse_args()


def _build_folds(data_start: str, oos_start: str, oos_end: str) -> list[WFFold]:
    oos_start_dt = pd.Timestamp(oos_start)
    oos_end_dt = pd.Timestamp(oos_end)
    folds: list[WFFold] = []
    year = oos_start_dt.year
    while True:
        fold_oos_start = pd.Timestamp(f"{year}-01-01")
        fold_oos_end = pd.Timestamp(f"{year}-12-31")
        if fold_oos_start > oos_end_dt:
            break
        if fold_oos_end > oos_end_dt:
            fold_oos_end = oos_end_dt
        fold_is_end = fold_oos_start - pd.Timedelta(days=1)
        folds.append(
            WFFold(
                label=str(year),
                is_start=data_start,
                is_end=str(fold_is_end.date()),
                oos_start=str(fold_oos_start.date()),
                oos_end=str(fold_oos_end.date()),
            )
        )
        year += 1
    return folds


def _sleeve_df(raw: dict[str, pd.DataFrame], spec: SleeveSpec) -> pd.DataFrame:
    df = raw[spec.asset]
    if spec.timeframe.upper() == "4H":
        return resample_ohlcv(df, "4h")
    return df


def _strategy_for(spec: SleeveSpec):
    if spec.family == "trend":
        return trend_following_v11_explicit_btc
    if spec.family == "hedge":
        return STRATEGY_REGISTRY[HEDGE_STRATEGY]
    if spec.family == "mr":
        return STRATEGY_REGISTRY[MR_STRATEGY]
    if spec.family == "equity":
        return STRATEGY_REGISTRY[EQUITY_STRATEGY]
    if spec.family == "gold":
        return STRATEGY_REGISTRY[GOLD_STRATEGY]
    return STRATEGY_REGISTRY[spec.strategy]


def _combine_curves(results: dict[str, BacktestResult], specs: list[SleeveSpec]) -> pd.Series:
    curves = {spec.label: results[spec.label].equity_curve for spec in specs if spec.label in results}
    aligned = align_equity_curves(curves, base_freq="1h")
    out = aligned.sum(axis=1)
    out.name = "fund_nav"
    return out


def _perf(eq: pd.Series, initial_capital: float | None = None) -> dict:
    m = compute_metrics(eq, [], initial_capital=initial_capital)
    return {
        "cagr_pct": round(m.cagr_pct, 2),
        "total_return_pct": round(m.total_return_pct, 2),
        "max_drawdown_pct": round(m.max_drawdown_pct, 2),
        "sharpe": round(m.sharpe, 3),
        "calmar": round(m.calmar, 3),
        "volatility_ann_pct": round(m.volatility_ann_pct, 2),
        "initial_equity": round(m.initial_equity, 2),
        "final_equity": round(m.final_equity, 2),
    }


def _annual_returns(eq: pd.Series) -> dict[str, float]:
    daily = eq.resample("D").last().dropna()
    out: dict[str, float] = {}
    for yr, grp in daily.groupby(daily.index.year):
        if len(grp) >= 5:
            out[str(yr)] = round((float(grp.iloc[-1]) / float(grp.iloc[0]) - 1.0) * 100.0, 2)
    return out


def _stitch(fold_results: list[dict], initial_capital: float) -> pd.Series:
    parts: list[pd.Series] = []
    running_nav = initial_capital
    for fr in fold_results:
        curve = fr.get("fund_nav", pd.Series(dtype=float)).dropna()
        if curve.empty:
            continue
        scale = running_nav / float(curve.iloc[0])
        scaled = curve * scale
        parts.append(scaled)
        running_nav = float(scaled.iloc[-1])
    if not parts:
        return pd.Series(dtype=float)
    stitched = pd.concat(parts)
    stitched = stitched[~stitched.index.duplicated(keep="last")]
    stitched.name = "stitched_oos_nav"
    return stitched.sort_index()


def _run_fold(
    fold: WFFold,
    raw_full: dict[str, pd.DataFrame],
    args: argparse.Namespace,
    base_cfg: ExecutionConfig,
    mr_cfg: ExecutionConfig,
    equity_cfg: ExecutionConfig,
    btc_state_full: pd.DataFrame | None,
    spy_sma175_full: pd.Series | None,
    btc_parabolic_full: pd.Series | None,
    bil_yield_full: pd.Series | None,
) -> dict:
    log.info("Fold %s — OOS %s to %s", fold.label, fold.oos_start, fold.oos_end)
    raw_window = {asset: df.loc[fold.is_start : fold.oos_end] for asset, df in raw_full.items()}
    specs = [s for s in _build_sleeves(args) if s.capital > 0]

    btc_state_window = None if btc_state_full is None else btc_state_full.loc[fold.is_start : fold.oos_end]
    spy_window = None if spy_sma175_full is None else spy_sma175_full.loc[fold.is_start : fold.oos_end]
    btc_para_window = None if btc_parabolic_full is None else btc_parabolic_full.loc[fold.is_start : fold.oos_end]
    bil_window = None if bil_yield_full is None else bil_yield_full.loc[fold.is_start : fold.oos_end]

    results: dict[str, BacktestResult] = {}
    audit_rows: list[dict] = []
    for spec in specs:
        if spec.asset not in raw_window:
            continue
        df = _sleeve_df(raw_window, spec)
        if spec.family == "trend":
            df = inject_btc_macro_state(df, btc_state_window)
        if spec.family in ("trend", "hedge") and spy_window is not None:
            df = df.copy()
            df["spy_above_sma175"] = spy_window.reindex(df.index, method="ffill")
        if spec.family == "equity" and btc_para_window is not None:
            df = df.copy()
            df["btc_in_parabolic"] = btc_para_window.reindex(df.index, method="ffill")

        cfg = equity_cfg if spec.family in ("equity", "gold") else mr_cfg if spec.family == "mr" else base_cfg
        cash_yield = bil_window if spec.family in ("equity", "gold") else None
        result = run_backtest(
            df=df,
            strategy_module=_strategy_for(spec),
            initial_capital=spec.capital,
            exec_config=cfg,
            asset=spec.asset,
            rebalance_threshold=args.rebalance_threshold,
            cash_yield_series=cash_yield,
        )
        results[spec.label] = result

        if spec.family == "trend":
            start_ts = pd.Timestamp(fold.oos_start)
            for intent_idx, intent in enumerate(result.intent_series):
                ts = result.position_series.index[intent_idx]
                if ts < start_ts:
                    continue
                if intent.action.name in ("ENTER_LONG", "FLAT", "EXIT_LONG") and "btc_state_source" in intent.meta:
                    audit_rows.append(
                        {
                            "fold": fold.label,
                            "timestamp": ts,
                            "sleeve": spec.label,
                            "asset": spec.asset,
                            "action": intent.action.name,
                            "desired_exposure": intent.desired_exposure_frac,
                            "btc_above_sma175": intent.meta.get("btc_above_sma175"),
                            "btc_state_source": intent.meta.get("btc_state_source"),
                            "btc_extension_sma365": intent.meta.get("btc_extension_sma365"),
                            "btc_parabolic_state_source": intent.meta.get("btc_parabolic_state_source"),
                            "parabolic_tier": intent.meta.get("parabolic_tier"),
                            "reason": intent.reason,
                        }
                    )

    fund_nav_full = _combine_curves(results, specs)
    fund_nav = fund_nav_full.loc[fold.oos_start : fold.oos_end]
    return {"fold": fold.label, "fund_nav": fund_nav, "perf": _perf(fund_nav), "audit_rows": audit_rows}


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw: dict[str, pd.DataFrame] = {"BTC": _load_asset(args.btc_data, "BTC", args.data_start, None)}
    if args.eth_data:
        raw["ETH"] = _load_asset(args.eth_data, "ETH", args.data_start, None)
    if args.spy_data:
        raw["SPY"] = _load_asset(args.spy_data, "SPY", args.data_start, None)
    if args.qqq_data:
        raw["QQQ"] = _load_asset(args.qqq_data, "QQQ", args.data_start, None)
    if args.gld_data:
        raw["GLD"] = _load_asset(args.gld_data, "GLD", args.data_start, None)

    btc_state = compute_btc_macro_state(raw["BTC"])
    log.info("BTC macro state rows: %d", len(btc_state))

    spy_sma175 = None
    if "SPY" in raw:
        spy_close = raw["SPY"]["close"]
        spy_sma175 = (spy_close > spy_close.rolling(175).mean()).rename("spy_above_sma175")

    btc_parabolic = None
    if not btc_state.empty:
        btc_parabolic = btc_state["btc_parabolic_hard"].rename("btc_in_parabolic")

    bil_yield = None
    if args.bil_data:
        bil_df = _load_asset(args.bil_data, "BIL", args.data_start, None)
        bil_yield = bil_df["close"].pct_change().fillna(0.0)

    base_cfg = ExecutionConfig(
        taker_fee_rate=args.fee,
        base_slippage_bps=args.base_slippage,
        slippage_vol_factor=args.slippage_vol_factor,
        cooldown_bars=args.cooldown,
    )
    mr_cfg = ExecutionConfig(
        taker_fee_rate=args.fee,
        base_slippage_bps=args.base_slippage,
        slippage_vol_factor=args.slippage_vol_factor,
        cooldown_bars=args.mr_cooldown,
    )
    equity_cfg = ExecutionConfig(
        taker_fee_rate=args.equity_fee,
        base_slippage_bps=0.5,
        slippage_size_factor=1.0,
        slippage_vol_factor=2.0,
        min_slippage_bps=0.1,
        max_slippage_bps=5.0,
        spread_k=0.02,
        min_spread_bps=0.2,
        cooldown_bars=1,
    )

    folds = _build_folds(args.data_start, args.oos_start, args.oos_end)
    fold_results = [
        _run_fold(f, raw, args, base_cfg, mr_cfg, equity_cfg, btc_state, spy_sma175, btc_parabolic, bil_yield)
        for f in folds
    ]

    stitched = _stitch(fold_results, args.capital)
    if stitched.empty:
        raise SystemExit("No stitched OOS NAV produced")

    perf = _perf(stitched, initial_capital=args.capital)
    annual = _annual_returns(stitched)
    audit_rows = [row for fr in fold_results for row in fr.get("audit_rows", [])]
    pd.DataFrame(audit_rows).to_csv(out_dir / "cross_asset_state_audit.csv", index=False)
    stitched.to_csv(out_dir / "stitched_oos_nav.csv", header=True)

    lines = ["# Explicit BTC State Walk-Forward", "", "## Stitched OOS Performance", "```text"]
    for k, v in perf.items():
        lines.append(f"{k:<24} {v}")
    lines += ["```", "", "## Annual Returns", "```text"]
    for yr, ret in annual.items():
        lines.append(f"{yr}   {ret:+.2f}%")
    lines += ["```", "", "## Audit", f"Rows written: {len(audit_rows)}", "", "Research only. Not financial advice."]
    (out_dir / "walkforward_explicit_btc_report.md").write_text("\n".join(lines), encoding="utf-8")

    log.info("STITCHED OOS RESULTS %s to %s", args.oos_start, args.oos_end)
    log.info("CAGR %.2f%%  MaxDD %.2f%%  Sharpe %.3f  Calmar %.3f", perf["cagr_pct"], perf["max_drawdown_pct"], perf["sharpe"], perf["calmar"])
    for yr, ret in annual.items():
        log.info("%s  %+0.2f%%", yr, ret)
    log.info("Wrote artifacts to %s", out_dir)


if __name__ == "__main__":
    main()
