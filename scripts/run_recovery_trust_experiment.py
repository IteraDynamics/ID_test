#!/usr/bin/env python
"""Recovery Trust Gate — diagnostic experiment script (v1).

Runs the full pipeline:
  1. Load data
  2. Build sleeves (using existing fund runner helpers)
  3. Run backtests to get intent_series and position_series
  4. Detect candidate re-risk events per sleeve
  5. Label candidates with forward returns
  6. Build feature matrix
  7. Print diagnostic report
  8. Run walk-forward ML experiment (logistic, RF if enough data, GBM if enough)
  9. Save artifacts

DIAGNOSTIC MODE ONLY in v1 — no portfolio comparison.

Usage
-----
# Minimum — BTC only:
python scripts/run_recovery_trust_experiment.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv

# Full:
python scripts/run_recovery_trust_experiment.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --spy-data data/spy_daily.csv \\
    --qqq-data data/qqq_daily.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("recovery_trust_experiment")

import numpy as np
import pandas as pd

from research.harness.backtest_engine import run_backtest, BacktestResult
from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.harness.resampler import resample_ohlcv
from research.strategies import REGISTRY as STRATEGY_REGISTRY

# Re-use sleeve helpers from the fund runner
from scripts.run_multi_strategy_fund import (
    SleeveSpec,
    _build_sleeves,
    _load_asset,
    _sleeve_df,
    _run_sleeve,
)

from research.harness.metrics import compute_metrics
from research.harness.resampler import align_equity_curves
from research.ml.recovery_trust.candidate_detector import detect_candidates
from research.ml.recovery_trust.labeler import label_candidates
from research.ml.recovery_trust.feature_builder import build_features
from research.ml.recovery_trust.model import FoldResult, run_walk_forward
from scripts.run_multi_strategy_walkforward import _build_folds, WFFold


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Recovery Trust Gate — ML experiment (diagnostic v1)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True, help="Path to BTC hourly OHLCV CSV")
    p.add_argument("--eth-data",  default=None, help="Path to ETH hourly OHLCV CSV (optional)")
    p.add_argument("--spy-data",  default=None, help="Path to SPY daily OHLCV CSV (optional)")
    p.add_argument("--qqq-data",  default=None, help="Path to QQQ daily OHLCV CSV (optional)")
    p.add_argument("--bil-data",  default=None, help="Path to BIL daily OHLCV CSV (optional)")
    p.add_argument("--data-start",   default="2019-01-01", help="Data window start")
    p.add_argument("--oos-start",    default="2021-01-01", help="OOS window start (for reference)")
    p.add_argument("--oos-end",      default="2025-12-31", help="OOS window end (for reference)")
    p.add_argument("--horizon-days", type=int,   default=60,          help="Forward label horizon (calendar days)")
    p.add_argument("--out-dir",      default="artifacts/recovery_trust", help="Output directory")
    p.add_argument("--capital",      type=float, default=100_000.0,   help="Total fund capital (USD)")
    p.add_argument("--trend-weight", type=float, default=0.45)
    p.add_argument("--hedge-weight", type=float, default=0.10)
    p.add_argument("--equity-weight",type=float, default=0.45)
    p.add_argument("--mr-weight",    type=float, default=0.0)
    # Cost model
    p.add_argument("--fee",                 type=float, default=0.0006)
    p.add_argument("--equity-fee",          type=float, default=0.0001)
    p.add_argument("--base-slippage",       type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--cooldown",            type=int,   default=2)
    p.add_argument("--rebalance-threshold", type=float, default=0.02)
    return p.parse_args()


# ── Data loading ───────────────────────────────────────────────────────────────

def _load_all_data(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    """Load all available asset data into a dict keyed by asset name."""
    raw: dict[str, pd.DataFrame] = {}

    raw["BTC"] = _load_asset(args.btc_data, "BTC", args.data_start, None)

    if args.eth_data:
        try:
            raw["ETH"] = _load_asset(args.eth_data, "ETH", args.data_start, None)
        except Exception as e:
            log.warning("Could not load ETH data: %s — continuing without ETH", e)

    if args.spy_data:
        try:
            raw["SPY"] = _load_asset(args.spy_data, "SPY", args.data_start, None)
        except Exception as e:
            log.warning("Could not load SPY data: %s — continuing without SPY", e)

    if args.qqq_data:
        try:
            raw["QQQ"] = _load_asset(args.qqq_data, "QQQ", args.data_start, None)
        except Exception as e:
            log.warning("Could not load QQQ data: %s — continuing without QQQ", e)

    return raw


# ── Execution configs ──────────────────────────────────────────────────────────

def _exec_config_crypto(args: argparse.Namespace) -> ExecutionConfig:
    return ExecutionConfig(
        taker_fee_rate=args.fee,
        base_slippage_bps=args.base_slippage,
        slippage_vol_factor=args.slippage_vol_factor,
    )


def _exec_config_equity(args: argparse.Namespace) -> ExecutionConfig:
    return ExecutionConfig(
        taker_fee_rate=args.equity_fee,
        base_slippage_bps=1.0,
        slippage_vol_factor=5.0,
    )


# ── Run all sleeves ────────────────────────────────────────────────────────────

def _run_all_sleeves(
    sleeves: list[SleeveSpec],
    raw: dict[str, pd.DataFrame],
    args: argparse.Namespace,
    bil_yield: pd.Series | None,
) -> dict[str, BacktestResult]:
    results: dict[str, BacktestResult] = {}
    for spec in sleeves:
        if spec.asset not in raw:
            log.warning("Sleeve %s: asset %s not available — skipping", spec.label, spec.asset)
            continue
        df = _sleeve_df(raw, spec)
        is_equity = spec.family == "equity"
        exec_cfg  = _exec_config_equity(args) if is_equity else _exec_config_crypto(args)
        cash_yield = bil_yield if is_equity else None
        result = _run_sleeve(
            spec=spec,
            df=df,
            exec_config=exec_cfg,
            rebalance_threshold=args.rebalance_threshold,
            cash_yield_series=cash_yield,
        )
        results[spec.label] = result
    return results


# ── Diagnostic report helpers ─────────────────────────────────────────────────

def _candidates_per_year(candidates_df: pd.DataFrame) -> dict[int, int]:
    years = pd.to_datetime(candidates_df["timestamp"]).dt.year
    return dict(years.value_counts().sort_index())


def _class_balance(candidates_df: pd.DataFrame) -> dict:
    n_total = len(candidates_df)
    n_pos   = int((candidates_df["label"] == 1).sum())
    n_neg   = int((candidates_df["label"] == 0).sum())
    n_amb   = int((candidates_df["label"] == -1).sum())
    n_labelled = n_pos + n_neg
    return {
        "total":     n_total,
        "positive":  n_pos,
        "negative":  n_neg,
        "ambiguous": n_amb,
        "labelled":  n_labelled,
        "pct_positive": round(100 * n_pos / n_labelled, 1) if n_labelled else 0.0,
        "pct_negative": round(100 * n_neg / n_labelled, 1) if n_labelled else 0.0,
    }


def _fold_sample_counts(candidates_df: pd.DataFrame, folds: list[tuple[int, int]]) -> list[dict]:
    years  = pd.to_datetime(candidates_df["timestamp"]).dt.year.values
    labels = candidates_df["label"].values
    rows   = []
    for train_end, test_yr in folds:
        train_mask = (years <= train_end) & (labels != -1)
        test_mask  = years == test_yr
        rows.append({
            "fold":         f"{train_end}→{test_yr}",
            "train_count":  int(train_mask.sum()),
            "train_pos":    int(((labels == 1) & (years <= train_end)).sum()),
            "train_neg":    int(((labels == 0) & (years <= train_end)).sum()),
            "test_count":   int(test_mask.sum()),
            "test_pos":     int(((labels == 1) & (years == test_yr)).sum()),
            "test_neg":     int(((labels == 0) & (years == test_yr)).sum()),
            "test_amb":     int(((labels == -1) & (years == test_yr)).sum()),
        })
    return rows


def _format_cm(cm: np.ndarray | None) -> str:
    if cm is None:
        return "N/A"
    return f"[[{cm[0,0]} {cm[0,1]}] [{cm[1,0]} {cm[1,1]}]]"


def _build_report(
    candidates_df: pd.DataFrame,
    class_bal: dict,
    per_year: dict[int, int],
    fold_counts: list[dict],
    fold_results: dict[str, list[FoldResult]],
    feat_importance_logistic: pd.Series | None,
    feat_importance_rf: pd.Series | None,
    feat_importance_gbm: pd.Series | None,
) -> str:
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("RECOVERY TRUST GATE — DIAGNOSTIC REPORT (v1)")
    lines.append("=" * 70)
    lines.append("")

    # ── Candidate summary ──────────────────────────────────────────────────
    lines.append("CANDIDATE DETECTION SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  Total candidates detected : {class_bal['total']}")
    lines.append(f"  Labelled (excl ambiguous) : {class_bal['labelled']}")
    lines.append(f"    Positive (genuine)      : {class_bal['positive']}  ({class_bal['pct_positive']}%)")
    lines.append(f"    Negative (fake rebound) : {class_bal['negative']}  ({class_bal['pct_negative']}%)")
    lines.append(f"    Ambiguous               : {class_bal['ambiguous']}")
    lines.append("")

    lines.append("CANDIDATES PER YEAR")
    lines.append("-" * 40)
    for yr, cnt in sorted(per_year.items()):
        lines.append(f"  {yr}: {cnt}")
    lines.append("")

    if "sleeve_label" in candidates_df.columns:
        lines.append("PER-SLEEVE BREAKDOWN")
        lines.append("-" * 40)
        for sl, grp in candidates_df.groupby("sleeve_label"):
            n_pos = int((grp["label"] == 1).sum()) if "label" in grp.columns else "?"
            n_neg = int((grp["label"] == 0).sum()) if "label" in grp.columns else "?"
            lines.append(f"  {sl}: {len(grp)} candidates  (pos={n_pos}, neg={n_neg})")
        lines.append("")

    # ── Fold sample counts ─────────────────────────────────────────────────
    lines.append("FOLD SAMPLE COUNTS")
    lines.append("-" * 40)
    lines.append(f"  {'Fold':<15} {'Train':>7} {'Pos':>5} {'Neg':>5} | {'Test':>6} {'Pos':>5} {'Neg':>5} {'Amb':>5}")
    lines.append(f"  {'-'*15} {'-'*7} {'-'*5} {'-'*5}   {'-'*6} {'-'*5} {'-'*5} {'-'*5}")
    for fc in fold_counts:
        lines.append(
            f"  {fc['fold']:<15} {fc['train_count']:>7} {fc['train_pos']:>5} {fc['train_neg']:>5} "
            f"| {fc['test_count']:>6} {fc['test_pos']:>5} {fc['test_neg']:>5} {fc['test_amb']:>5}"
        )
    lines.append("")

    # ── Model fold results ─────────────────────────────────────────────────
    for model_name, folds_list in fold_results.items():
        lines.append(f"WALK-FORWARD RESULTS — {model_name.upper()}")
        lines.append("-" * 60)
        for fr in folds_list:
            lc_flag = " [LOW CONFIDENCE]" if fr.low_confidence else ""
            lines.append(f"  Fold: {fr.fold_label}{lc_flag}")
            lines.append(f"    Train: {fr.train_count} total  ({fr.train_positive} pos, {fr.train_negative} neg)")
            lines.append(f"    Test:  {fr.test_count} total  ({fr.test_positive} pos, {fr.test_negative} neg)")
            auc_str = f"{fr.auc:.4f}" if fr.auc is not None else "N/A"
            lines.append(f"    AUC: {auc_str}")
            prec_str = f"{fr.precision_neg:.4f}" if fr.precision_neg is not None else "N/A"
            rec_str  = f"{fr.recall_neg:.4f}"    if fr.recall_neg  is not None else "N/A"
            lines.append(f"    Precision(neg class): {prec_str}  Recall(neg class): {rec_str}")
            lines.append(f"    Confusion matrix (rows=actual, cols=pred, order=[0,1]): {_format_cm(fr.confusion_matrix)}")
            lines.append("")
        lines.append("")

    # ── Feature importance ─────────────────────────────────────────────────
    def _fmt_imp(imp: pd.Series | None, title: str, top_n: int = 15) -> None:
        if imp is None:
            return
        lines.append(f"FEATURE IMPORTANCE — {title}")
        lines.append("-" * 40)
        for feat, val in imp.head(top_n).items():
            lines.append(f"  {feat:<35} {val:.4f}")
        lines.append("")

    # Use last fold's feature importance (most data)
    if "logistic" in fold_results:
        last_fr = next((fr for fr in reversed(fold_results["logistic"]) if fr.feature_importance is not None), None)
        if last_fr:
            _fmt_imp(last_fr.feature_importance, "LOGISTIC REGRESSION (last fold)")
    if "rf" in fold_results:
        last_fr = next((fr for fr in reversed(fold_results["rf"]) if fr.feature_importance is not None), None)
        if last_fr:
            _fmt_imp(last_fr.feature_importance, "RANDOM FOREST (last fold)")
    if "gbm" in fold_results:
        last_fr = next((fr for fr in reversed(fold_results["gbm"]) if fr.feature_importance is not None), None)
        if last_fr:
            _fmt_imp(last_fr.feature_importance, "GRADIENT BOOSTING (last fold)")

    lines.append("=" * 70)
    return "\n".join(lines)


# ── Portfolio comparison ───────────────────────────────────────────────────────

def _gbm_confidence(
    model,
    scaler,
    feature_row: np.ndarray,
) -> float:
    """Return GBM recovery_confidence for a single feature row. Returns 0.5 on NaN."""
    if np.any(np.isnan(feature_row)):
        return 0.5
    x = scaler.transform(feature_row.reshape(1, -1))
    proba = model.predict_proba(x)[0]
    classes = list(model.classes_)
    pos_col = classes.index(1) if 1 in classes else 0
    return float(proba[pos_col])


def _scale_factor_from_confidence(conf: float) -> float:
    """Map GBM recovery_confidence to a position scale factor."""
    if conf >= 0.70:
        return 1.0
    elif conf >= 0.50:
        return 0.50
    elif conf >= 0.35:
        return 0.25
    else:
        return 0.0


def _reconstruct_scaled_nav(
    baseline_position: pd.Series,
    asset_prices: pd.Series,
    candidates_in_oos: pd.DataFrame,
    model,
    scaler,
    feature_cols: list[str],
    features_df: pd.DataFrame,
    initial_nav: float,
) -> pd.Series:
    """Reconstruct per-sleeve NAV using scaled positions at re-risk events.

    EXIT/FLAT signals always pass through unchanged — ML only scales re-risk entries.
    For subsequent HOLD bars after a scaled entry, the scaling ratio is maintained
    until the next signal change.
    """
    # Build mapping from candidate timestamp -> scale_factor
    cand_scale: dict[pd.Timestamp, float] = {}
    for _, row in candidates_in_oos.iterrows():
        ts = pd.Timestamp(row["timestamp"])
        cand_idx = row.name  # integer index in features_df
        if cand_idx in features_df.index:
            feat_row = features_df.loc[cand_idx, feature_cols].values.astype(float)
        else:
            feat_row = np.full(len(feature_cols), np.nan)
        conf = _gbm_confidence(model, scaler, feat_row)
        cand_scale[ts] = _scale_factor_from_confidence(conf)

    # Build scaled position series
    baseline_arr = baseline_position.values.copy()
    scaled_arr = baseline_arr.copy()
    index = baseline_position.index

    current_scale: float = 1.0
    prev_baseline: float = float(baseline_arr[0]) if len(baseline_arr) > 0 else 0.0

    for i, ts in enumerate(index):
        bp = float(baseline_arr[i])
        position_changed = abs(bp - prev_baseline) > 0.05

        if ts in cand_scale:
            # Re-risk event — apply GBM scale
            current_scale = cand_scale[ts]
            scaled_arr[i] = bp * current_scale
        elif position_changed:
            # New signal: exit/flat or new entry not flagged as re-risk
            if bp <= 0.01:
                current_scale = 1.0
            else:
                current_scale = 1.0
            scaled_arr[i] = bp
        else:
            # HOLD bar — maintain current scale ratio
            scaled_arr[i] = bp * current_scale

        prev_baseline = bp

    scaled_pos = pd.Series(scaled_arr, index=index, name="scaled_exposure")

    # Reconstruct NAV: nav[t] = nav[t-1] * (1 + scaled_pos[t-1] * asset_return[t])
    asset_aligned = asset_prices.reindex(index, method="ffill").ffill().bfill()
    asset_ret = asset_aligned.pct_change().fillna(0.0)

    nav_arr = np.empty(len(index))
    nav_arr[0] = initial_nav
    for i in range(1, len(index)):
        nav_arr[i] = nav_arr[i - 1] * (1.0 + scaled_arr[i - 1] * float(asset_ret.iloc[i]))

    return pd.Series(nav_arr, index=index, name="scaled_nav")


def run_portfolio_comparison(
    all_candidates_df: pd.DataFrame,
    features_df: pd.DataFrame,
    fold_results_gbm: list[FoldResult],
    raw: dict[str, pd.DataFrame],
    args: argparse.Namespace,
    bil_yield: "pd.Series | None",
    out_dir: Path,
) -> None:
    """Compute baseline vs GBM-gated portfolio comparison across OOS folds.

    For each walk-forward fold (2021-2025):
    - Re-run OOS sleeve backtests to get baseline position_series
    - Train a fresh GBM on IS candidates with sample_weight imbalance handling
    - Reconstruct scaled NAV per sleeve using GBM recovery confidence scores
    - Combine sleeves, stitch folds, compute and print metrics
    """
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler

    log.info("Starting portfolio comparison (baseline vs GBM scaler)...")

    oos_start  = args.oos_start
    oos_end    = args.oos_end
    data_start = args.data_start

    wf_folds = _build_folds(data_start, oos_start, oos_end)

    sleeves = [s for s in _build_sleeves(args) if s.capital > 0 and s.family != "hedge"]

    # Candidates and features
    timestamps = pd.to_datetime(all_candidates_df["timestamp"])
    years  = timestamps.dt.year.values
    labels = all_candidates_df["label"].values
    feature_cols = list(features_df.columns)
    X_all = features_df[feature_cols].values.astype(float)

    exec_config_map: dict[str, ExecutionConfig] = {}
    for spec in sleeves:
        if spec.family == "equity":
            exec_config_map[spec.label] = _exec_config_equity(args)
        else:
            exec_config_map[spec.label] = _exec_config_crypto(args)

    # Gate activity counters
    gate_counts: dict = {
        "total": 0,
        "blocked": 0,
        "reduced_25": 0,
        "reduced_50": 0,
        "full_pass": 0,
        "by_year": {},
    }

    baseline_fold_navs: list[pd.Series] = []
    scaled_fold_navs:   list[pd.Series] = []
    per_fold_metrics:   list[dict] = []

    for fold in wf_folds:
        fold_year = int(fold.label)
        log.info("Portfolio comparison fold %s  OOS %s → %s",
                 fold.label, fold.oos_start, fold.oos_end)

        # Train fresh GBM on IS labelled candidates
        train_end_year = int(fold.is_end[:4])
        train_mask = (years <= train_end_year) & (labels != -1)
        train_idx  = np.where(train_mask)[0]
        y_train    = labels[train_idx]
        X_train    = X_all[train_idx]

        n_pos = int((y_train == 1).sum())
        n_neg = int((y_train == 0).sum())

        if n_pos == 0 or n_neg == 0 or len(train_idx) < 10:
            log.warning(
                "Fold %s: insufficient IS training data (pos=%d neg=%d) — skipping",
                fold.label, n_pos, n_neg,
            )
            continue

        # Handle class imbalance with sample_weight (GBM has no class_weight param)
        sample_weight = np.where(y_train == 0, 1.0, float(n_neg) / float(n_pos))

        fold_scaler = StandardScaler()
        X_train_scaled = fold_scaler.fit_transform(X_train)

        gbm = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.05,
            random_state=42,
        )
        gbm.fit(X_train_scaled, y_train, sample_weight=sample_weight)

        # OOS candidates for this fold
        oos_cands_mask = (years == fold_year)
        oos_cands_df   = all_candidates_df[oos_cands_mask].copy()

        # Slice raw with IS warmup so indicators are primed
        raw_window: dict[str, pd.DataFrame] = {}
        for asset, df in raw.items():
            raw_window[asset] = df.loc[fold.is_start: fold.oos_end]

        baseline_sleeve_navs: list[pd.Series] = []
        scaled_sleeve_navs:   list[pd.Series] = []

        for spec in sleeves:
            if spec.asset not in raw_window:
                continue

            df_sleeve = _sleeve_df(raw_window, spec)
            exec_cfg  = exec_config_map[spec.label]
            cash_yield = bil_yield if spec.family == "equity" else None

            result = _run_sleeve(
                spec=spec,
                df=df_sleeve,
                exec_config=exec_cfg,
                rebalance_threshold=args.rebalance_threshold,
                cash_yield_series=cash_yield,
            )

            # Slice to OOS window
            baseline_pos_oos = result.position_series.loc[fold.oos_start: fold.oos_end]
            equity_oos       = result.equity_curve.loc[fold.oos_start: fold.oos_end]

            if baseline_pos_oos.empty or equity_oos.empty:
                continue

            initial_nav = float(equity_oos.iloc[0])
            baseline_sleeve_navs.append(equity_oos.rename(spec.label))

            # Candidates for this sleeve in OOS
            sleeve_oos_cands = oos_cands_df[oos_cands_df["sleeve_label"] == spec.label].copy()

            # Asset price series for returns computation
            asset_prices = _sleeve_df(raw_window, spec)["close"]

            scaled_nav = _reconstruct_scaled_nav(
                baseline_position=baseline_pos_oos,
                asset_prices=asset_prices,
                candidates_in_oos=sleeve_oos_cands,
                model=gbm,
                scaler=fold_scaler,
                feature_cols=feature_cols,
                features_df=features_df,
                initial_nav=initial_nav,
            )
            scaled_sleeve_navs.append(scaled_nav.rename(spec.label))

            # Tally gate activity
            for _, cand_row in sleeve_oos_cands.iterrows():
                cand_idx = cand_row.name
                if cand_idx in features_df.index:
                    feat_row = features_df.loc[cand_idx, feature_cols].values.astype(float)
                else:
                    feat_row = np.full(len(feature_cols), np.nan)
                conf = _gbm_confidence(gbm, fold_scaler, feat_row)
                sf   = _scale_factor_from_confidence(conf)

                gate_counts["total"] += 1
                year_key = str(fold_year)
                gate_counts["by_year"].setdefault(year_key, 0)
                gate_counts["by_year"][year_key] += 1

                if sf == 0.0:
                    gate_counts["blocked"] += 1
                elif sf == 0.25:
                    gate_counts["reduced_25"] += 1
                elif sf == 0.50:
                    gate_counts["reduced_50"] += 1
                else:
                    gate_counts["full_pass"] += 1

        if not baseline_sleeve_navs:
            log.warning("Fold %s: no sleeve results — skipping", fold.label)
            continue

        def _sum_navs(nav_list: list[pd.Series]) -> pd.Series:
            if not nav_list:
                return pd.Series(dtype=float)
            aligned_df = align_equity_curves(
                {s.name: s for s in nav_list}, base_freq="1h"
            )
            combined      = aligned_df.sum(axis=1)
            combined.name = "fund_nav"
            return combined

        baseline_fund = _sum_navs(baseline_sleeve_navs)
        scaled_fund   = _sum_navs(scaled_sleeve_navs if scaled_sleeve_navs else baseline_sleeve_navs)

        baseline_fold_navs.append(baseline_fund)
        scaled_fold_navs.append(scaled_fund)

        b_m = compute_metrics(baseline_fund, [])
        s_m = compute_metrics(scaled_fund,   [])
        per_fold_metrics.append({
            "fold":            fold.label,
            "oos_start":       fold.oos_start,
            "oos_end":         fold.oos_end,
            "baseline_cagr":   round(b_m.cagr_pct, 2),
            "baseline_mdd":    round(b_m.max_drawdown_pct, 2),
            "baseline_sharpe": round(b_m.sharpe, 3),
            "baseline_calmar": round(b_m.calmar, 3),
            "scaler_cagr":     round(s_m.cagr_pct, 2),
            "scaler_mdd":      round(s_m.max_drawdown_pct, 2),
            "scaler_sharpe":   round(s_m.sharpe, 3),
            "scaler_calmar":   round(s_m.calmar, 3),
        })

    if not baseline_fold_navs:
        log.warning("Portfolio comparison: no OOS folds produced results — skipping output")
        return

    # ── Stitch OOS equity curves ────────────────────────────────────────────────
    def _stitch(fold_navs: list[pd.Series], initial_capital: float) -> pd.Series:
        parts: list[pd.Series] = []
        running_nav = initial_capital
        for nav in fold_navs:
            nav = nav.dropna()
            if nav.empty:
                continue
            scale  = running_nav / float(nav.iloc[0])
            scaled = nav * scale
            parts.append(scaled)
            running_nav = float(scaled.iloc[-1])
        if not parts:
            return pd.Series(dtype=float)
        stitched = pd.concat(parts)
        stitched = stitched[~stitched.index.duplicated(keep="last")]
        return stitched.sort_index()

    baseline_stitched = _stitch(baseline_fold_navs, args.capital)
    scaled_stitched   = _stitch(scaled_fold_navs,   args.capital)

    b_metrics = compute_metrics(baseline_stitched, [], initial_capital=args.capital)
    s_metrics = compute_metrics(scaled_stitched,   [], initial_capital=args.capital)

    def _annual_ret(eq: pd.Series) -> dict[int, float]:
        daily = eq.resample("D").last().dropna()
        out: dict[int, float] = {}
        for yr, grp in daily.groupby(daily.index.year):
            if len(grp) < 5:
                continue
            out[int(yr)] = round((float(grp.iloc[-1]) / float(grp.iloc[0]) - 1) * 100, 1)
        return out

    b_annual = _annual_ret(baseline_stitched)
    s_annual = _annual_ret(scaled_stitched)

    # ── Print comparison table ─────────────────────────────────────────────────
    print()
    print("=" * 70)
    print(f"PORTFOLIO COMPARISON — {oos_start} → {oos_end}")
    print("=" * 70)
    print()

    def _delta(b: float, s: float) -> str:
        d = s - b
        return f"{d:+.3f}" if abs(d) < 10 else f"{d:+.2f}"

    print(f"{'':30} {'BASELINE':>12}  {'GBM SCALER':>12}  {'DELTA':>8}")
    print(f"{'CAGR %':<30} {b_metrics.cagr_pct:>12.2f}  {s_metrics.cagr_pct:>12.2f}  {_delta(b_metrics.cagr_pct, s_metrics.cagr_pct):>8}")
    print(f"{'Max Drawdown %':<30} {b_metrics.max_drawdown_pct:>12.2f}  {s_metrics.max_drawdown_pct:>12.2f}  {_delta(b_metrics.max_drawdown_pct, s_metrics.max_drawdown_pct):>8}")
    print(f"{'Sharpe':<30} {b_metrics.sharpe:>12.3f}  {s_metrics.sharpe:>12.3f}  {_delta(b_metrics.sharpe, s_metrics.sharpe):>8}")
    print(f"{'Calmar':<30} {b_metrics.calmar:>12.3f}  {s_metrics.calmar:>12.3f}  {_delta(b_metrics.calmar, s_metrics.calmar):>8}")
    print(f"{'Ann Vol %':<30} {b_metrics.volatility_ann_pct:>12.2f}  {s_metrics.volatility_ann_pct:>12.2f}")
    print()

    all_years = sorted(set(list(b_annual.keys()) + list(s_annual.keys())))
    print("ANNUAL RETURNS")
    print(f"{'':12} {'BASELINE':>10}  {'GBM SCALER':>12}")
    for yr in all_years:
        bv = b_annual.get(yr, float("nan"))
        sv = s_annual.get(yr, float("nan"))
        bv_s = f"{bv:+.1f}%" if not np.isnan(bv) else "  N/A "
        sv_s = f"{sv:+.1f}%" if not np.isnan(sv) else "  N/A "
        print(f"  {yr}        {bv_s:>10}   {sv_s:>10}")
    print()

    print("GBM GATE ACTIVITY")
    print(f"  Total re-risk decisions gated:  {gate_counts['total']}")
    print(f"  Blocked (conf < 0.35):          {gate_counts['blocked']}")
    print(f"  Reduced to 25% (0.35-0.50):     {gate_counts['reduced_25']}")
    print(f"  Reduced to 50% (0.50-0.70):     {gate_counts['reduced_50']}")
    print(f"  Full pass (conf >= 0.70):        {gate_counts['full_pass']}")
    by_yr_str = "  ".join(f"{yr}={cnt}" for yr, cnt in sorted(gate_counts["by_year"].items()))
    print(f"  Per year: {by_yr_str}")
    print()

    # ── Save CSV ──────────────────────────────────────────────────────────────
    csv_path = out_dir / "portfolio_comparison.csv"
    pd.DataFrame(per_fold_metrics).to_csv(csv_path, index=False)
    log.info("Saved portfolio comparison → %s", csv_path)


# ── Save artifacts ─────────────────────────────────────────────────────────────

def _save_fold_results_csv(fold_results_list: list[FoldResult], path: Path) -> None:
    rows = []
    for fr in fold_results_list:
        rows.append({
            "fold_label":     fr.fold_label,
            "train_count":    fr.train_count,
            "test_count":     fr.test_count,
            "train_positive": fr.train_positive,
            "train_negative": fr.train_negative,
            "test_positive":  fr.test_positive,
            "test_negative":  fr.test_negative,
            "low_confidence": fr.low_confidence,
            "auc":            fr.auc if fr.auc is not None else "",
            "precision_neg":  fr.precision_neg if fr.precision_neg is not None else "",
            "recall_neg":     fr.recall_neg if fr.recall_neg is not None else "",
        })
    pd.DataFrame(rows).to_csv(path, index=False)
    log.info("Saved fold results → %s", path)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load data
    log.info("Loading data...")
    raw = _load_all_data(args)

    # BIL cash yield (optional)
    bil_yield: pd.Series | None = None
    if args.bil_data:
        try:
            bil_df = _load_asset(args.bil_data, "BIL", args.data_start, None)
            bil_yield = bil_df["close"].pct_change().fillna(0.0)
            log.info("BIL cash yield loaded: %d bars", len(bil_yield))
        except Exception as e:
            log.warning("Could not load BIL data: %s — no cash yield applied", e)

    # 2. Build sleeves — skip zero-capital and hedge sleeves.
    # Hedge sleeves (crash_short_v6) re-risk into SHORT positions; excluding them
    # from backtests entirely saves ~18 min and they are not needed for candidate detection.
    log.info("Building sleeves...")
    sleeves = [s for s in _build_sleeves(args) if s.capital > 0 and s.family != "hedge"]
    log.info("Sleeves: %s", [s.label for s in sleeves])

    # 3. Run backtests
    log.info("Running sleeve backtests (IS+OOS full period)...")
    results = _run_all_sleeves(sleeves, raw, args, bil_yield)
    log.info("Completed %d/%d sleeves", len(results), len(sleeves))

    # 4. Detect candidates per sleeve — exclude hedge sleeves.
    # Hedge (crash_short_v6) re-risks into SHORT positions; the labeling logic
    # assumes long re-entries (positive forward return = good).  Mixing short
    # re-entries inverts ~92% of the training labels and destroys model signal.
    log.info("Detecting candidate re-risk events (trend + equity sleeves only)...")
    all_candidates: list[pd.DataFrame] = []
    for spec in sleeves:
        if spec.label not in results:
            continue
        result = results[spec.label]
        df_sleeve = _sleeve_df(raw, spec)
        cands = detect_candidates(
            position_series=result.position_series,
            intent_series=result.intent_series,
            df_index=df_sleeve.index,
            asset=spec.asset,
            timeframe=spec.timeframe,
            sleeve_label=spec.label,
        )
        all_candidates.append(cands)

    if not all_candidates:
        log.error("No candidates detected across any sleeve — aborting")
        sys.exit(1)

    candidates_df = pd.concat(all_candidates, ignore_index=True)
    candidates_df = candidates_df.sort_values("timestamp").reset_index(drop=True)
    log.info("Total candidates detected: %d", len(candidates_df))

    # 5. Label candidates
    log.info("Labelling candidates (horizon=%d days)...", args.horizon_days)
    # Use BTC daily close as primary price series for crypto candidates;
    # for equity sleeves use the appropriate asset's close
    def _price_series_for_sleeve(spec: SleeveSpec) -> pd.Series:
        asset_df = raw.get(spec.asset)
        if asset_df is None:
            return raw["BTC"]["close"]
        return asset_df["close"]

    # Label per sleeve, then recombine
    labelled_parts: list[pd.DataFrame] = []
    for spec in sleeves:
        if spec.label not in results:
            continue
        sleeve_cands = candidates_df[candidates_df["sleeve_label"] == spec.label].copy()
        if sleeve_cands.empty:
            continue
        price_series = _price_series_for_sleeve(spec)
        sleeve_labelled = label_candidates(sleeve_cands, price_series, horizon_days=args.horizon_days)
        labelled_parts.append(sleeve_labelled)

    if not labelled_parts:
        log.error("No labelled candidates — aborting")
        sys.exit(1)

    candidates_df = pd.concat(labelled_parts, ignore_index=True)
    candidates_df = candidates_df.sort_values("timestamp").reset_index(drop=True)

    # 6. Build features (with temporal features from position history)
    log.info("Building feature matrix (including temporal features)...")
    position_data = {
        spec.label: results[spec.label].position_series
        for spec in sleeves
        if spec.label in results
    }
    features_df = build_features(candidates_df, raw, position_data=position_data)

    # 7. Diagnostic report data
    class_bal = _class_balance(candidates_df)
    per_year  = _candidates_per_year(candidates_df)

    n_labelled = class_bal["labelled"]
    folds = [
        (2020, 2021),
        (2021, 2022),
        (2022, 2023),
        (2023, 2024),
        (2024, 2025),
    ]
    fold_counts = _fold_sample_counts(candidates_df, folds)

    # 8. Print initial diagnostic info
    print()
    print(f"Total candidates detected : {class_bal['total']}")
    print(f"Labelled (excl ambiguous) : {n_labelled}")
    print(f"  Positive : {class_bal['positive']}  ({class_bal['pct_positive']}%)")
    print(f"  Negative : {class_bal['negative']}  ({class_bal['pct_negative']}%)")
    print(f"  Ambiguous: {class_bal['ambiguous']}")
    print()

    # 9. Walk-forward experiments
    fold_results: dict[str, list[FoldResult]] = {}

    log.info("Running walk-forward — logistic regression...")
    lr_results = run_walk_forward(candidates_df, features_df, folds, model_type="logistic")
    fold_results["logistic"] = lr_results

    if n_labelled >= 60:
        log.info("Running walk-forward — random forest (n_labelled=%d >= 60)...", n_labelled)
        rf_results = run_walk_forward(candidates_df, features_df, folds, model_type="rf")
        fold_results["rf"] = rf_results
    else:
        log.info("Skipping RF (n_labelled=%d < 60)", n_labelled)

    if n_labelled >= 80:
        log.info("Running walk-forward — gradient boosting (n_labelled=%d >= 80)...", n_labelled)
        gbm_results = run_walk_forward(candidates_df, features_df, folds, model_type="gbm")
        fold_results["gbm"] = gbm_results
    else:
        log.info("Skipping GBM (n_labelled=%d < 80)", n_labelled)

    # 10–11. Build and print full report
    report = _build_report(
        candidates_df=candidates_df,
        class_bal=class_bal,
        per_year=per_year,
        fold_counts=fold_counts,
        fold_results=fold_results,
        feat_importance_logistic=None,  # included inside fold_results
        feat_importance_rf=None,
        feat_importance_gbm=None,
    )
    print(report)

    # 12. Save artifacts
    # candidates with labels and features
    candidates_with_features = candidates_df.copy()
    for col in features_df.columns:
        candidates_with_features[col] = features_df[col].values
    cands_path = out_dir / "candidates.csv"
    candidates_with_features.to_csv(cands_path, index=False)
    log.info("Saved candidates → %s", cands_path)

    for model_name, fold_list in fold_results.items():
        csv_path = out_dir / f"fold_results_{model_name}.csv"
        _save_fold_results_csv(fold_list, csv_path)

    summary_path = out_dir / "summary.txt"
    summary_path.write_text(report, encoding="utf-8")
    log.info("Saved summary → %s", summary_path)

    # 13. Portfolio comparison (GBM scaler vs baseline)
    if "gbm" in fold_results:
        run_portfolio_comparison(
            all_candidates_df=candidates_df,
            features_df=features_df,
            fold_results_gbm=fold_results["gbm"],
            raw=raw,
            args=args,
            bil_yield=bil_yield,
            out_dir=out_dir,
        )
    else:
        print()
        print("Portfolio comparison skipped — GBM model not trained (need n_labelled >= 80)")

    print(f"Artifacts saved to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
