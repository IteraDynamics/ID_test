from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from research.harness.backtest_engine import run_backtest
from research.harness.cross_asset_state import compute_btc_macro_state, inject_btc_macro_state
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import compute_metrics
from research.harness.resampler import align_equity_curves, resample_ohlcv
from research.strategies import REGISTRY as STRATEGY_REGISTRY
from research.strategies import trend_following_v11
from scripts.run_multi_strategy_fund import _build_sleeves, _load_asset
from scripts.run_multi_strategy_walkforward import _build_folds


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("core_v1_sleeve_audit")

HEDGE_STRATEGY = "crash_short_v6"
MR_STRATEGY = "mean_reversion"
EQUITY_STRATEGY = "equity_sma175_v3"
GOLD_STRATEGY = "gold_sma_v1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Core v1 sleeve-level contribution audit using the canonical WFO sleeve logic.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", default=None)
    p.add_argument("--spy-data", default=None)
    p.add_argument("--qqq-data", default=None)
    p.add_argument("--bil-data", default=None)
    p.add_argument("--gld-data", default=None)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--trend-weight", type=float, default=0.40)
    p.add_argument("--equity-weight", type=float, default=0.35)
    p.add_argument("--gold-weight", type=float, default=0.15)
    p.add_argument("--hedge-weight", type=float, default=0.10)
    p.add_argument("--mr-weight", type=float, default=0.00)
    p.add_argument("--data-start", default="2019-01-01")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--equity-fee", type=float, default=0.0001)
    p.add_argument("--base-slippage", type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--cooldown", type=int, default=2)
    p.add_argument("--mr-cooldown", type=int, default=12)
    p.add_argument("--rebalance-threshold", type=float, default=0.02)
    p.add_argument("--out-dir", default="artifacts/core_v1_sleeve_contribution/baseline_40_35_15_10")
    return p.parse_args()


def sleeve_df(raw: dict[str, pd.DataFrame], spec) -> pd.DataFrame:
    df = raw[spec.asset]
    if spec.timeframe.upper() == "4H":
        return resample_ohlcv(df, "4h")
    return df


def strategy_for(spec):
    if spec.family == "trend":
        return trend_following_v11
    if spec.family == "hedge":
        return STRATEGY_REGISTRY[HEDGE_STRATEGY]
    if spec.family == "mr":
        return STRATEGY_REGISTRY[MR_STRATEGY]
    if spec.family == "equity":
        return STRATEGY_REGISTRY[EQUITY_STRATEGY]
    if spec.family == "gold":
        return STRATEGY_REGISTRY[GOLD_STRATEGY]
    return STRATEGY_REGISTRY[spec.strategy]


def perf_dict(eq: pd.Series, trades: list | None = None, initial_capital: float | None = None) -> dict:
    m = compute_metrics(eq.dropna(), trades or [], initial_capital=initial_capital)
    return {
        "cagr_pct": round(m.cagr_pct, 2),
        "total_return_pct": round(m.total_return_pct, 2),
        "max_drawdown_pct": round(m.max_drawdown_pct, 2),
        "sharpe": round(m.sharpe, 3),
        "calmar": round(m.calmar, 3),
        "volatility_ann_pct": round(m.volatility_ann_pct, 2),
        "n_trades": m.n_trades,
        "win_rate_pct": round(m.win_rate_pct, 2),
        "total_fees_paid": round(m.total_fees_paid, 2),
        "total_slippage_cost": round(m.total_slippage_cost, 2),
        "initial_equity": round(m.initial_equity, 2),
        "final_equity": round(m.final_equity, 2),
    }


def annual_returns(eq: pd.Series) -> dict[str, float]:
    daily = eq.resample("D").last().dropna()
    out: dict[str, float] = {}
    for yr, grp in daily.groupby(daily.index.year):
        if len(grp) >= 5 and float(grp.iloc[0]) != 0:
            out[str(yr)] = round((float(grp.iloc[-1]) / float(grp.iloc[0]) - 1.0) * 100.0, 2)
    return out


def write_series(path: Path, series: pd.Series, column: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    series.rename(column).to_csv(path, header=True)


def load_data(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    raw: dict[str, pd.DataFrame] = {"BTC": _load_asset(args.btc_data, "BTC", args.data_start, None)}
    if args.eth_data:
        raw["ETH"] = _load_asset(args.eth_data, "ETH", args.data_start, None)
    if args.spy_data:
        raw["SPY"] = _load_asset(args.spy_data, "SPY", args.data_start, None)
    if args.qqq_data:
        raw["QQQ"] = _load_asset(args.qqq_data, "QQQ", args.data_start, None)
    if args.gld_data:
        raw["GLD"] = _load_asset(args.gld_data, "GLD", args.data_start, None)
    return raw


def make_execution_configs(args: argparse.Namespace) -> tuple[ExecutionConfig, ExecutionConfig, ExecutionConfig]:
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
    return base_cfg, mr_cfg, equity_cfg


def run_audit(args: argparse.Namespace) -> dict:
    out_dir = Path(args.out_dir)
    curves_dir = out_dir / "sleeve_curves"
    scaled_curves_dir = out_dir / "scaled_sleeve_curves"
    out_dir.mkdir(parents=True, exist_ok=True)
    curves_dir.mkdir(parents=True, exist_ok=True)
    scaled_curves_dir.mkdir(parents=True, exist_ok=True)

    raw = load_data(args)
    specs = [s for s in _build_sleeves(args) if s.capital > 0]
    folds = _build_folds(args.data_start, args.oos_start, args.oos_end)
    base_cfg, mr_cfg, equity_cfg = make_execution_configs(args)

    btc_state_full = compute_btc_macro_state(raw["BTC"])
    log.info("BTC macro state rows: %d", len(btc_state_full))

    spy_sma175_full = None
    if "SPY" in raw:
        spy_close = raw["SPY"]["close"]
        spy_sma175_full = (spy_close > spy_close.rolling(175).mean()).rename("spy_above_sma175")
        log.info("SPY SMA175 signal rows: %d", len(spy_sma175_full))

    btc_parabolic_full = None
    if not btc_state_full.empty:
        btc_parabolic_full = btc_state_full["btc_parabolic_hard"].rename("btc_in_parabolic")

    bil_yield_full = None
    if args.bil_data:
        bil_df = _load_asset(args.bil_data, "BIL", args.data_start, None)
        bil_yield_full = bil_df["close"].pct_change().fillna(0.0)

    sleeve_summary_rows: list[dict] = []
    annual_rows: list[dict] = []
    scaled_annual_rows: list[dict] = []
    stitched_by_sleeve: dict[str, list[pd.Series]] = {spec.label: [] for spec in specs}
    fold_fund_curves: list[pd.Series] = []
    audit_rows: list[dict] = []
    running_nav = float(args.capital)

    for fold in folds:
        log.info("Fold %s — OOS %s to %s", fold.label, fold.oos_start, fold.oos_end)
        raw_window = {asset: df.loc[fold.is_start : fold.oos_end] for asset, df in raw.items()}
        btc_state_window = btc_state_full.loc[fold.is_start : fold.oos_end]
        spy_window = None if spy_sma175_full is None else spy_sma175_full.loc[fold.is_start : fold.oos_end]
        btc_para_window = None if btc_parabolic_full is None else btc_parabolic_full.loc[fold.is_start : fold.oos_end]
        bil_window = None if bil_yield_full is None else bil_yield_full.loc[fold.is_start : fold.oos_end]

        fold_curves: dict[str, pd.Series] = {}
        fold_results = {}
        fold_rows_idx: list[int] = []

        for spec in specs:
            if spec.asset not in raw_window:
                continue
            log.info("Fold %s running %-16s family=%s capital=$%.0f", fold.label, spec.label, spec.family, spec.capital)
            df = sleeve_df(raw_window, spec)
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
                strategy_module=strategy_for(spec),
                initial_capital=spec.capital,
                exec_config=cfg,
                asset=spec.asset,
                rebalance_threshold=args.rebalance_threshold,
                cash_yield_series=cash_yield,
            )
            fold_results[spec.label] = result
            oos_curve = result.equity_curve.loc[fold.oos_start : fold.oos_end].dropna()
            fold_curves[spec.label] = oos_curve
            write_series(curves_dir / f"fold_{fold.label}__{spec.label}.csv", oos_curve, "equity")

            trades = [t for t in result.trades if pd.Timestamp(t.timestamp) >= pd.Timestamp(fold.oos_start)]
            metrics = perf_dict(oos_curve, trades, initial_capital=spec.capital)
            row = {
                "fold": fold.label,
                "oos_start": fold.oos_start,
                "oos_end": fold.oos_end,
                "sleeve": spec.label,
                "family": spec.family,
                "asset": spec.asset,
                "timeframe": spec.timeframe,
                "strategy": spec.strategy,
                "capital": round(spec.capital, 2),
                **metrics,
                "pnl_dollars": round(metrics["final_equity"] - metrics["initial_equity"], 2),
                "return_on_total_capital_pct": round(((metrics["final_equity"] - metrics["initial_equity"]) / args.capital) * 100.0, 4),
            }
            sleeve_summary_rows.append(row)
            fold_rows_idx.append(len(sleeve_summary_rows) - 1)

            for year, value in annual_returns(oos_curve).items():
                annual_rows.append({"fold": fold.label, "sleeve": spec.label, "family": spec.family, "year": year, "return_pct": value})

            if spec.family == "trend":
                start_ts = pd.Timestamp(fold.oos_start)
                for intent_idx, intent in enumerate(result.intent_series):
                    ts = result.position_series.index[intent_idx]
                    if ts < start_ts:
                        continue
                    if "btc_state_source" in intent.meta:
                        audit_rows.append(
                            {
                                "fold": fold.label,
                                "timestamp": ts,
                                "sleeve": spec.label,
                                "asset": spec.asset,
                                "btc_state_source": intent.meta.get("btc_state_source"),
                                "btc_parabolic_state_source": intent.meta.get("btc_parabolic_state_source"),
                            }
                        )

        if fold_curves:
            aligned = align_equity_curves(fold_curves, base_freq="1h")
            fund = aligned.sum(axis=1).loc[fold.oos_start : fold.oos_end].dropna()
            if fund.empty:
                continue

            # Match the canonical WFO stitching semantics: each fold is scaled so
            # its first OOS NAV equals the running fund NAV from prior folds.
            scale = running_nav / float(fund.iloc[0])
            scaled_fund = fund * scale
            scaled_fund.name = f"fold_{fold.label}_fund_nav_scaled"
            fold_fund_curves.append(scaled_fund)
            running_nav = float(scaled_fund.iloc[-1])

            for spec in specs:
                curve = fold_curves.get(spec.label)
                if curve is None or curve.empty:
                    continue
                scaled_curve = curve * scale
                stitched_by_sleeve[spec.label].append(scaled_curve)
                write_series(scaled_curves_dir / f"fold_{fold.label}__{spec.label}.csv", scaled_curve, "scaled_equity")

                scaled_initial = float(scaled_curve.iloc[0])
                scaled_final = float(scaled_curve.iloc[-1])
                scaled_pnl = scaled_final - scaled_initial
                for idx in fold_rows_idx:
                    if sleeve_summary_rows[idx]["sleeve"] == spec.label:
                        sleeve_summary_rows[idx]["fold_scale"] = round(scale, 8)
                        sleeve_summary_rows[idx]["scaled_initial_equity"] = round(scaled_initial, 2)
                        sleeve_summary_rows[idx]["scaled_final_equity"] = round(scaled_final, 2)
                        sleeve_summary_rows[idx]["scaled_pnl_dollars"] = round(scaled_pnl, 2)
                        sleeve_summary_rows[idx]["scaled_return_on_total_start_nav_pct"] = round((scaled_pnl / float(scaled_fund.iloc[0])) * 100.0, 4)
                        break

                for year, value in annual_returns(scaled_curve).items():
                    scaled_annual_rows.append({"fold": fold.label, "sleeve": spec.label, "family": spec.family, "year": year, "return_pct": value})

    sleeve_summary = pd.DataFrame(sleeve_summary_rows)
    sleeve_summary.to_csv(out_dir / "sleeve_fold_summary.csv", index=False)
    pd.DataFrame(annual_rows).to_csv(out_dir / "sleeve_annual_returns.csv", index=False)
    pd.DataFrame(scaled_annual_rows).to_csv(out_dir / "scaled_sleeve_annual_returns.csv", index=False)
    pd.DataFrame(audit_rows).to_csv(out_dir / "sleeve_cross_asset_state_audit.csv", index=False)

    stitched_sleeves = {}
    for sleeve, parts in stitched_by_sleeve.items():
        if not parts:
            continue
        stitched = pd.concat(parts).sort_index()
        stitched = stitched[~stitched.index.duplicated(keep="last")]
        stitched.name = sleeve
        stitched_sleeves[sleeve] = stitched
        write_series(out_dir / "stitched_sleeves" / f"{sleeve}.csv", stitched, "scaled_equity")

    stitched_aligned = align_equity_curves(stitched_sleeves, base_freq="1h") if stitched_sleeves else pd.DataFrame()
    if not stitched_aligned.empty:
        stitched_aligned.to_csv(out_dir / "stitched_sleeve_equity_matrix.csv")
        daily_returns = stitched_aligned.resample("D").last().pct_change().dropna(how="all")
        daily_returns.corr().to_csv(out_dir / "sleeve_daily_return_correlation.csv")

    if fold_fund_curves:
        fund = pd.concat(fold_fund_curves).sort_index()
        fund = fund[~fund.index.duplicated(keep="last")]
        fund.name = "stitched_fund_nav_from_sleeves"
        write_series(out_dir / "stitched_fund_nav_from_sleeves.csv", fund, "fund_nav")
        fund_metrics = perf_dict(fund, [], initial_capital=args.capital)
        fund_annual = annual_returns(fund)
    else:
        fund_metrics = {}
        fund_annual = {}

    by_sleeve = []
    if not sleeve_summary.empty:
        pnl_col = "scaled_pnl_dollars" if "scaled_pnl_dollars" in sleeve_summary.columns else "pnl_dollars"
        contrib_col = "scaled_return_on_total_start_nav_pct" if "scaled_return_on_total_start_nav_pct" in sleeve_summary.columns else "return_on_total_capital_pct"
        grouped = sleeve_summary.groupby(["sleeve", "family"], as_index=False).agg(
            capital=("capital", "first"),
            pnl_dollars=(pnl_col, "sum"),
            return_on_total_nav_pct=(contrib_col, "sum"),
            n_trades=("n_trades", "sum"),
            avg_sharpe=("sharpe", "mean"),
            worst_fold_dd=("max_drawdown_pct", "min"),
            best_fold_return=("total_return_pct", "max"),
            worst_fold_return=("total_return_pct", "min"),
        )
        grouped = grouped.sort_values("pnl_dollars", ascending=False)
        grouped.to_csv(out_dir / "sleeve_contribution_summary.csv", index=False)
        by_sleeve = grouped.to_dict(orient="records")

    summary = {
        "fund_metrics": fund_metrics,
        "fund_annual_returns": fund_annual,
        "sleeve_contribution_summary": by_sleeve,
        "audit_rows": len(audit_rows),
        "config": vars(args),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report(out_dir, summary, sleeve_summary)
    return summary


def write_report(out_dir: Path, summary: dict, sleeve_summary: pd.DataFrame) -> None:
    lines = ["# Core v1 Sleeve Contribution Audit", ""]
    lines += ["## Reconstructed Fund Metrics", "```text"]
    for k, v in summary.get("fund_metrics", {}).items():
        lines.append(f"{k:<28} {v}")
    lines += ["```", "", "## Annual Returns", "```text"]
    for yr, ret in summary.get("fund_annual_returns", {}).items():
        lines.append(f"{yr}   {ret:+.2f}%")
    lines += ["```", "", "## Sleeve Contribution Summary", ""]
    cols = ["sleeve", "family", "capital", "pnl_dollars", "return_on_total_nav_pct", "n_trades", "avg_sharpe", "worst_fold_dd", "best_fold_return", "worst_fold_return"]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for row in summary.get("sleeve_contribution_summary", []):
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")

    if not sleeve_summary.empty:
        lines += ["", "## Worst Sleeve-Folds by Return", ""]
        worst = sleeve_summary.sort_values("total_return_pct").head(10)
        cols2 = ["fold", "sleeve", "family", "total_return_pct", "max_drawdown_pct", "sharpe", "n_trades", "pnl_dollars"]
        lines.append("| " + " | ".join(cols2) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols2)) + " |")
        for _, row in worst.iterrows():
            lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols2) + " |")

        lines += ["", "## Best Sleeve-Folds by Return", ""]
        best = sleeve_summary.sort_values("total_return_pct", ascending=False).head(10)
        lines.append("| " + " | ".join(cols2) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols2)) + " |")
        for _, row in best.iterrows():
            lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols2) + " |")

    lines += ["", "## Outputs", "```text"]
    lines += [
        "sleeve_fold_summary.csv",
        "sleeve_annual_returns.csv",
        "scaled_sleeve_annual_returns.csv",
        "sleeve_contribution_summary.csv",
        "sleeve_daily_return_correlation.csv",
        "stitched_sleeve_equity_matrix.csv",
        "stitched_sleeves/*.csv",
        "sleeve_curves/fold_YYYY__SLEEVE.csv",
        "scaled_sleeve_curves/fold_YYYY__SLEEVE.csv",
    ]
    lines += ["```", "", "_Research only. Not financial advice._"]
    (out_dir / "sleeve_contribution_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    try:
        summary = run_audit(args)
        m = summary.get("fund_metrics", {})
        log.info(
            "Reconstructed fund → CAGR %.2f%% MaxDD %.2f%% Sharpe %.3f Calmar %.3f",
            m.get("cagr_pct", 0.0),
            m.get("max_drawdown_pct", 0.0),
            m.get("sharpe", 0.0),
            m.get("calmar", 0.0),
        )
        log.info("Wrote artifacts to %s", args.out_dir)
    except Exception:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "runner_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
