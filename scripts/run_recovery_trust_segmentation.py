#!/usr/bin/env python
"""Recovery Trust Gate — Segmentation Audit Script.

Diagnostic only — no portfolio changes, no backtest reruns.

Loads candidates.csv (with pre-built features if available, otherwise rebuilds
them from raw data) and runs four segmentation analyses:

  1. Label quality by sleeve
  2. Walk-forward model results by segment
  3. 2023 candidate audit (GBM trained on <=2022 data)
  4. Gate activity by sleeve and year (OOS 2021-2025)

Usage
-----
# If features are embedded in candidates.csv (fast path):
python scripts/run_recovery_trust_segmentation.py \\
    --candidates-csv artifacts/recovery_trust/candidates.csv

# If features need to be rebuilt from raw data:
python scripts/run_recovery_trust_segmentation.py \\
    --candidates-csv artifacts/recovery_trust/candidates.csv \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --spy-data data/spy_daily.csv \\
    --qqq-data data/qqq_daily.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("recovery_trust_segmentation")

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

from research.ml.recovery_trust.model import FoldResult, run_walk_forward
from research.ml.recovery_trust.feature_builder import build_features


# ── Constants ──────────────────────────────────────────────────────────────────

FOLDS = [
    (2020, 2021),
    (2021, 2022),
    (2022, 2023),
    (2023, 2024),
    (2024, 2025),
]

# All columns that are NOT features
NON_FEATURE_COLS = {
    "timestamp", "bar_index", "proposed_exposure", "prior_exposure",
    "exposure_delta", "asset", "timeframe", "sleeve_label",
    "forward_return_60d", "max_drawdown_60d", "label", "label_str",
    "label_available",
}

SEGMENTS = {
    "btc_only":    lambda df: df["asset"].isin(["BTC"]) & df["sleeve_label"].str.contains("trend"),
    "eth_only":    lambda df: df["asset"].isin(["ETH"]) & df["sleeve_label"].str.contains("trend"),
    "crypto_only": lambda df: df["sleeve_label"].str.contains("trend"),
    "btc_4h_only": lambda df: df["sleeve_label"] == "BTC_4H_trend",
    "btc_1h_only": lambda df: df["sleeve_label"] == "BTC_1H_trend",
    "1h_only":     lambda df: df["sleeve_label"].str.contains("1H"),
    "4h_only":     lambda df: df["sleeve_label"].str.contains("4H"),
    "equity_only": lambda df: df["sleeve_label"].str.contains("equity"),
}

GATE_THRESHOLDS = {
    "full_pass":   (0.70, 1.01),
    "reduced_50":  (0.50, 0.70),
    "reduced_25":  (0.35, 0.50),
    "blocked":     (0.00, 0.35),
}


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Recovery Trust Gate — Segmentation Audit",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--candidates-csv",
        default="artifacts/recovery_trust/candidates.csv",
        help="Path to candidates.csv (may include pre-built feature columns)",
    )
    p.add_argument("--btc-data", default=None, help="BTC hourly OHLCV CSV (required if features missing)")
    p.add_argument("--eth-data", default=None, help="ETH hourly OHLCV CSV (optional)")
    p.add_argument("--spy-data", default=None, help="SPY daily OHLCV CSV (optional)")
    p.add_argument("--qqq-data", default=None, help="QQQ daily OHLCV CSV (optional)")
    p.add_argument("--out-dir",  default="artifacts/recovery_trust/segmentation", help="Output directory")
    p.add_argument("--data-start", default="2019-01-01", help="Data window start (used only if rebuilding features)")
    return p.parse_args()


# ── Data loading ───────────────────────────────────────────────────────────────

def _load_ohlcv(path: str, name: str, data_start: str) -> pd.DataFrame:
    """Load an OHLCV CSV, parse timestamps, filter to data_start."""
    df = pd.read_csv(path)
    # Try common timestamp column names
    for col in ("timestamp", "date", "datetime", "Date", "Datetime"):
        if col in df.columns:
            df.index = pd.to_datetime(df[col])
            df = df.drop(columns=[col])
            break
    else:
        # Assume index is already datetime
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df.loc[df.index >= data_start]
    # Normalise column names to lowercase
    df.columns = [c.lower() for c in df.columns]
    log.info("Loaded %s: %d bars (%s to %s)", name, len(df), df.index[0].date(), df.index[-1].date())
    return df


def _load_all_raw(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    raw: dict[str, pd.DataFrame] = {}
    if args.btc_data:
        raw["BTC"] = _load_ohlcv(args.btc_data, "BTC", args.data_start)
    if args.eth_data:
        try:
            raw["ETH"] = _load_ohlcv(args.eth_data, "ETH", args.data_start)
        except Exception as e:
            log.warning("Could not load ETH: %s", e)
    if args.spy_data:
        try:
            raw["SPY"] = _load_ohlcv(args.spy_data, "SPY", args.data_start)
        except Exception as e:
            log.warning("Could not load SPY: %s", e)
    if args.qqq_data:
        try:
            raw["QQQ"] = _load_ohlcv(args.qqq_data, "QQQ", args.data_start)
        except Exception as e:
            log.warning("Could not load QQQ: %s", e)
    return raw


# ── Feature detection / rebuilding ─────────────────────────────────────────────

def _detect_feature_cols(df: pd.DataFrame) -> list[str]:
    """Return columns that are features (i.e., not in NON_FEATURE_COLS)."""
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


def _load_candidates_and_features(
    candidates_csv: str,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load candidates_df and features_df.

    If features are embedded in candidates.csv, split them out.
    Otherwise rebuild via build_features() using raw data.
    """
    log.info("Loading candidates from %s", candidates_csv)
    cands = pd.read_csv(candidates_csv)
    cands["timestamp"] = pd.to_datetime(cands["timestamp"])

    feature_cols = _detect_feature_cols(cands)

    if feature_cols:
        log.info("Features found in CSV: %d columns — fast path", len(feature_cols))
        features_df = cands[feature_cols].copy()
        features_df.index = cands.index
        candidates_df = cands.drop(columns=feature_cols)
    else:
        log.info("No feature columns in CSV — rebuilding features from raw data")
        if not args.btc_data:
            log.error("--btc-data is required when features are not in candidates.csv")
            sys.exit(1)
        raw = _load_all_raw(args)
        candidates_df = cands.copy()
        features_df = build_features(candidates_df, raw)

    log.info(
        "Loaded %d candidates, %d features",
        len(candidates_df), len(features_df.columns),
    )
    return candidates_df, features_df


# ── Helpers ────────────────────────────────────────────────────────────────────

def _gate_action(conf: float) -> str:
    if conf >= 0.70:
        return "full_pass"
    elif conf >= 0.50:
        return "reduced_50"
    elif conf >= 0.35:
        return "reduced_25"
    else:
        return "blocked"


def _format_cm(cm: np.ndarray | None) -> str:
    if cm is None:
        return "N/A"
    return f"[[{cm[0,0]} {cm[0,1]}] [{cm[1,0]} {cm[1,1]}]]"


def _auc_str(fr: FoldResult) -> str:
    return f"{fr.auc:.4f}" if fr.auc is not None else "N/A"


def _train_gbm(
    candidates_df: pd.DataFrame,
    features_df: pd.DataFrame,
    train_mask: np.ndarray,
) -> tuple | None:
    """Train a GBM on the given training mask. Returns (model, scaler, feature_cols) or None."""
    feature_cols = list(features_df.columns)
    X_all = features_df[feature_cols].values.astype(float)
    labels = candidates_df["label"].values

    train_idx = np.where(train_mask)[0]
    if len(train_idx) == 0:
        return None

    y_train = labels[train_idx]
    X_train = X_all[train_idx]

    n_pos = int((y_train == 1).sum())
    n_neg = int((y_train == 0).sum())
    if n_pos == 0 or n_neg == 0:
        log.warning("GBM training skipped: pos=%d neg=%d", n_pos, n_neg)
        return None

    sample_weight = np.where(y_train == 0, 1.0, float(n_neg) / float(n_pos))
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    gbm = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.05,
        random_state=42,
    )
    gbm.fit(X_train_scaled, y_train, sample_weight=sample_weight)
    return gbm, scaler, feature_cols


def _score_gbm(
    model,
    scaler,
    feature_cols: list[str],
    features_df: pd.DataFrame,
    idx: np.ndarray,
) -> np.ndarray:
    """Score rows at `idx` with the GBM, returning recovery_confidence array."""
    X = features_df.iloc[idx][feature_cols].values.astype(float)
    X_scaled = scaler.transform(X)
    proba = model.predict_proba(X_scaled)
    classes = list(model.classes_)
    pos_col = classes.index(1) if 1 in classes else 0
    return proba[:, pos_col]


# ── Report 1: Label quality by sleeve ─────────────────────────────────────────

def report_label_quality(
    candidates_df: pd.DataFrame,
    out_dir: Path,
) -> pd.DataFrame:
    print()
    print("=" * 70)
    print("REPORT 1: LABEL QUALITY BY SLEEVE")
    print("=" * 70)

    rows = []
    if "sleeve_label" not in candidates_df.columns:
        print("  [sleeve_label column missing — skipping]")
        return pd.DataFrame()

    for sl, grp in candidates_df.groupby("sleeve_label"):
        n_total   = len(grp)
        n_pos     = int((grp["label"] == 1).sum())
        n_neg     = int((grp["label"] == 0).sum())
        n_amb     = int((grp["label"] == -1).sum())
        n_labelled = n_pos + n_neg
        pos_rate  = round(100 * n_pos / n_labelled, 1) if n_labelled else 0.0
        neg_rate  = round(100 * n_neg / n_labelled, 1) if n_labelled else 0.0
        amb_rate  = round(100 * n_amb / n_total,    1) if n_total    else 0.0
        rows.append({
            "sleeve_label": sl,
            "n_candidates": n_total,
            "n_labelled":   n_labelled,
            "n_positive":   n_pos,
            "pct_positive": pos_rate,
            "n_negative":   n_neg,
            "pct_negative": neg_rate,
            "n_ambiguous":  n_amb,
            "pct_ambiguous": amb_rate,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        print("  [no sleeve data]")
        return df

    # Print table
    hdr = (
        f"  {'sleeve_label':<25} {'cands':>6} {'labelled':>8} "
        f"{'pos':>5} {'pos%':>6} {'neg':>5} {'neg%':>6} {'amb':>5} {'amb%':>6}"
    )
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for _, r in df.iterrows():
        print(
            f"  {r['sleeve_label']:<25} {r['n_candidates']:>6} {r['n_labelled']:>8} "
            f"{r['n_positive']:>5} {r['pct_positive']:>5.1f}% "
            f"{r['n_negative']:>5} {r['pct_negative']:>5.1f}% "
            f"{r['n_ambiguous']:>5} {r['pct_ambiguous']:>5.1f}%"
        )

    out_path = out_dir / "label_quality_by_sleeve.csv"
    df.to_csv(out_path, index=False)
    log.info("Saved label quality -> %s", out_path)
    return df


# ── Report 2: Walk-forward results by segment ──────────────────────────────────

def report_segments(
    candidates_df: pd.DataFrame,
    features_df: pd.DataFrame,
    out_dir: Path,
) -> dict[str, dict]:
    print()
    print("=" * 70)
    print("REPORT 2: WALK-FORWARD MODEL RESULTS BY SEGMENT")
    print("=" * 70)

    segment_summary: dict[str, dict] = {}

    for seg_name, seg_fn in SEGMENTS.items():
        print()
        print(f"  SEGMENT: {seg_name}")
        print("  " + "-" * 60)

        # Apply filter
        try:
            mask = seg_fn(candidates_df)
        except Exception as e:
            print(f"    [filter error: {e}]")
            continue

        seg_cands = candidates_df[mask].copy().reset_index(drop=True)
        seg_feats = features_df[mask].copy().reset_index(drop=True)

        n_labelled = int(((seg_cands["label"] == 1) | (seg_cands["label"] == 0)).sum())
        n_total = len(seg_cands)
        n_pos   = int((seg_cands["label"] == 1).sum())
        n_neg   = int((seg_cands["label"] == 0).sum())
        n_amb   = int((seg_cands["label"] == -1).sum())

        print(f"    Total: {n_total}  Labelled: {n_labelled}  Pos: {n_pos}  Neg: {n_neg}  Amb: {n_amb}")

        if n_labelled < 20:
            print(f"    [SKIP — fewer than 20 labelled examples]")
            segment_summary[seg_name] = {"skipped": True, "n_labelled": n_labelled}
            continue

        all_fold_rows = []

        for model_type in ("logistic", "rf", "gbm"):
            if model_type == "rf"  and n_labelled < 40:
                print(f"    [{model_type.upper()} skipped — need 40 labelled, have {n_labelled}]")
                continue
            if model_type == "gbm" and n_labelled < 60:
                print(f"    [{model_type.upper()} skipped — need 60 labelled, have {n_labelled}]")
                continue

            print(f"\n    === {model_type.upper()} ===")
            try:
                fold_results = run_walk_forward(seg_cands, seg_feats, FOLDS, model_type=model_type)
            except Exception as e:
                print(f"    [walk-forward error: {e}]")
                continue

            aucs = []
            for fr in fold_results:
                lc = " [LOW CONFIDENCE]" if fr.low_confidence else ""
                auc_s = _auc_str(fr)
                if fr.auc is not None:
                    aucs.append(fr.auc)
                prec_s = f"{fr.precision_neg:.4f}" if fr.precision_neg is not None else "N/A"
                rec_s  = f"{fr.recall_neg:.4f}"    if fr.recall_neg  is not None else "N/A"

                print(f"    Fold {fr.fold_label}{lc}")
                print(f"      Train: {fr.train_count} ({fr.train_positive}+/{fr.train_negative}-) "
                      f"Test: {fr.test_count} ({fr.test_positive}+/{fr.test_negative}-)")
                print(f"      AUC: {auc_s}  Prec(neg): {prec_s}  Rec(neg): {rec_s}")
                print(f"      CM: {_format_cm(fr.confusion_matrix)}")

                all_fold_rows.append({
                    "segment":        seg_name,
                    "model":          model_type,
                    "fold":           fr.fold_label,
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
                    "confusion_matrix": _format_cm(fr.confusion_matrix),
                })

            # Feature importance from last fold
            last_fr = next((fr for fr in reversed(fold_results) if fr.feature_importance is not None), None)
            if last_fr and last_fr.feature_importance is not None:
                print(f"\n    Feature Importance ({model_type.upper()}, last fold):")
                for feat, val in last_fr.feature_importance.head(10).items():
                    print(f"      {feat:<35} {val:.4f}")

            if aucs:
                print(f"\n    AUC summary: min={min(aucs):.4f} max={max(aucs):.4f} mean={np.mean(aucs):.4f}")
                segment_summary[seg_name] = {
                    "skipped": False,
                    "n_labelled": n_labelled,
                    "n_pos": n_pos,
                    "n_neg": n_neg,
                    "pos_rate": round(100 * n_pos / n_labelled, 1) if n_labelled else 0,
                    "model": model_type,
                    "auc_mean": round(np.mean(aucs), 4),
                    "auc_min": round(min(aucs), 4),
                    "auc_max": round(max(aucs), 4),
                    "aucs": aucs,
                }

        if all_fold_rows:
            out_path = out_dir / f"segment_{seg_name}_results.csv"
            pd.DataFrame(all_fold_rows).to_csv(out_path, index=False)
            log.info("Saved segment results -> %s", out_path)

    return segment_summary


# ── Report 3: 2023 candidate audit ─────────────────────────────────────────────

def report_2023_audit(
    candidates_df: pd.DataFrame,
    features_df: pd.DataFrame,
    out_dir: Path,
) -> pd.DataFrame:
    print()
    print("=" * 70)
    print("REPORT 3: 2023 CANDIDATE AUDIT")
    print("=" * 70)
    print("  NOTE: Only forward_return_60d is available (not 30d/90d).")

    timestamps = pd.to_datetime(candidates_df["timestamp"])
    years = timestamps.dt.year.values
    labels = candidates_df["label"].values

    # Train GBM on label != -1 AND year <= 2022
    train_mask = (years <= 2022) & (labels != -1)
    gbm_result = _train_gbm(candidates_df, features_df, train_mask)

    scores_2023 = np.full(len(candidates_df), np.nan)
    if gbm_result is not None:
        gbm, scaler, feature_cols = gbm_result
        test_mask_2023 = years == 2023
        test_idx_2023 = np.where(test_mask_2023)[0]
        if len(test_idx_2023) > 0:
            scores_2023[test_idx_2023] = _score_gbm(gbm, scaler, feature_cols, features_df, test_idx_2023)
        n_train = int(train_mask.sum())
        log.info("GBM trained on %d examples (year<=2022), scored %d 2023 candidates", n_train, len(test_idx_2023))
    else:
        log.warning("GBM training failed — confidence scores will be NaN")

    # Build 2023 audit table
    mask_2023 = years == 2023
    cands_2023 = candidates_df[mask_2023].copy()
    cands_2023_pos = np.where(mask_2023)[0]

    if cands_2023.empty:
        print("  [No 2023 candidates]")
        return pd.DataFrame()

    result_rows = []
    for i, (_, row) in enumerate(cands_2023.iterrows()):
        orig_idx = cands_2023_pos[i]
        conf = float(scores_2023[orig_idx]) if not np.isnan(scores_2023[orig_idx]) else np.nan
        gate = _gate_action(conf) if not np.isnan(conf) else "N/A"

        fwd_ret = row.get("forward_return_60d", np.nan)
        try:
            fwd_ret = float(fwd_ret)
        except Exception:
            fwd_ret = np.nan

        was_profitable = bool(fwd_ret > 0) if not np.isnan(fwd_ret) else None

        result_rows.append({
            "sleeve_label":       row.get("sleeve_label", ""),
            "timestamp":          row["timestamp"],
            "asset":              row.get("asset", ""),
            "timeframe":          row.get("timeframe", ""),
            "proposed_exposure":  row.get("proposed_exposure", np.nan),
            "prior_exposure":     row.get("prior_exposure", np.nan),
            "label":              row.get("label", np.nan),
            "label_str":          row.get("label_str", ""),
            "forward_return_60d": fwd_ret,
            "max_drawdown_60d":   row.get("max_drawdown_60d", np.nan),
            "gbm_confidence":     round(conf, 4) if not np.isnan(conf) else np.nan,
            "gate_action":        gate,
            "was_profitable":     was_profitable,
        })

    df_audit = pd.DataFrame(result_rows)

    # Summary
    print()
    print(f"  Total 2023 candidates: {len(df_audit)}")
    if gbm_result is not None:
        gate_counts = df_audit["gate_action"].value_counts()
        print(f"  Gate decisions:")
        for action in ["blocked", "reduced_25", "reduced_50", "full_pass"]:
            cnt = gate_counts.get(action, 0)
            print(f"    {action:<15}: {cnt}")

    print()
    print("  By sleeve:")
    for sl, grp in df_audit.groupby("sleeve_label"):
        n_blocked = (grp["gate_action"] == "blocked").sum()
        n_pass    = (grp["gate_action"] == "full_pass").sum()
        n_pos_label = (grp["label"] == 1).sum()
        n_neg_label = (grp["label"] == 0).sum()
        profitable = grp["was_profitable"].sum() if "was_profitable" in grp else "?"
        print(f"    {sl:<25} n={len(grp):>3}  label(+/-)={n_pos_label}/{n_neg_label}  "
              f"blocked={n_blocked}  pass={n_pass}  profitable={profitable}")

    out_path = out_dir / "audit_2023_candidates.csv"
    df_audit.to_csv(out_path, index=False)
    log.info("Saved 2023 audit -> %s", out_path)
    return df_audit


# ── Report 4: Gate activity by sleeve and year ─────────────────────────────────

def report_gate_activity(
    candidates_df: pd.DataFrame,
    features_df: pd.DataFrame,
    out_dir: Path,
) -> pd.DataFrame:
    print()
    print("=" * 70)
    print("REPORT 4: GATE ACTIVITY BY SLEEVE AND YEAR (OOS 2021-2025)")
    print("=" * 70)

    timestamps = pd.to_datetime(candidates_df["timestamp"])
    years = timestamps.dt.year.values
    labels = candidates_df["label"].values
    feature_cols = list(features_df.columns)

    # Score each OOS candidate using the GBM trained on all IS data up to that fold
    all_confidence = np.full(len(candidates_df), np.nan)

    for train_end_year, test_year in FOLDS:
        train_mask = (years <= train_end_year) & (labels != -1)
        test_mask  = years == test_year

        gbm_result = _train_gbm(candidates_df, features_df, train_mask)
        if gbm_result is None:
            log.warning("Fold %d->%d: GBM training failed", train_end_year, test_year)
            continue

        gbm, scaler, _ = gbm_result
        test_idx = np.where(test_mask)[0]
        if len(test_idx) == 0:
            continue

        scores = _score_gbm(gbm, scaler, feature_cols, features_df, test_idx)
        all_confidence[test_idx] = scores
        log.info("Fold %d->%d: scored %d OOS candidates", train_end_year, test_year, len(test_idx))

    # Build gate activity table
    rows = []
    oos_years = [2021, 2022, 2023, 2024, 2025]

    for sl, grp_df in candidates_df.groupby("sleeve_label"):
        grp_idx = np.where(candidates_df["sleeve_label"] == sl)[0]
        grp_years = years[grp_idx]
        grp_conf = all_confidence[grp_idx]
        grp_fwd = None
        if "forward_return_60d" in grp_df.columns:
            grp_fwd = grp_df["forward_return_60d"].values.astype(float)

        for yr in oos_years:
            yr_mask = grp_years == yr
            if yr_mask.sum() == 0:
                continue

            yr_conf = grp_conf[yr_mask]
            n_candidates = int(yr_mask.sum())

            def _cnt(lo, hi, conf=yr_conf):
                valid = ~np.isnan(conf)
                return int(((conf >= lo) & (conf < hi) & valid).sum())

            n_blocked    = _cnt(0.00, 0.35)
            n_red25      = _cnt(0.35, 0.50)
            n_red50      = _cnt(0.50, 0.70)
            n_full_pass  = _cnt(0.70, 1.01)

            valid_conf = yr_conf[~np.isnan(yr_conf)]
            avg_conf = float(np.mean(valid_conf)) if len(valid_conf) > 0 else np.nan

            avg_fwd_blocked = np.nan
            avg_fwd_pass    = np.nan
            if grp_fwd is not None:
                yr_fwd = grp_fwd[yr_mask]
                valid_mask = ~np.isnan(yr_conf) & ~np.isnan(yr_fwd)
                blocked_fwd = yr_fwd[(yr_conf < 0.35) & valid_mask]
                pass_fwd    = yr_fwd[(yr_conf >= 0.70) & valid_mask]
                if len(blocked_fwd) > 0:
                    avg_fwd_blocked = float(np.mean(blocked_fwd))
                if len(pass_fwd) > 0:
                    avg_fwd_pass = float(np.mean(pass_fwd))

            rows.append({
                "sleeve_label":             sl,
                "year":                     yr,
                "n_candidates":             n_candidates,
                "n_blocked":                n_blocked,
                "n_reduced_25":             n_red25,
                "n_reduced_50":             n_red50,
                "n_full_pass":              n_full_pass,
                "avg_confidence":           round(avg_conf, 4) if not np.isnan(avg_conf) else np.nan,
                "avg_fwd_return_blocked":   round(avg_fwd_blocked, 4) if not np.isnan(avg_fwd_blocked) else np.nan,
                "avg_fwd_return_full_pass": round(avg_fwd_pass, 4)    if not np.isnan(avg_fwd_pass)    else np.nan,
            })

    df_gate = pd.DataFrame(rows)
    if df_gate.empty:
        print("  [No OOS data]")
        return df_gate

    # Print
    print()
    hdr = (
        f"  {'sleeve_label':<25} {'yr':>4} {'n':>4} "
        f"{'blk':>4} {'r25':>4} {'r50':>4} {'pass':>5} "
        f"{'avg_conf':>9} {'fwd_blk':>9} {'fwd_pass':>9}"
    )
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for _, r in df_gate.iterrows():
        def _fmt(val):
            if isinstance(val, float) and np.isnan(val):
                return "  N/A"
            return f"{val:.3f}"

        print(
            f"  {r['sleeve_label']:<25} {r['year']:>4} {r['n_candidates']:>4} "
            f"{r['n_blocked']:>4} {r['n_reduced_25']:>4} {r['n_reduced_50']:>4} {r['n_full_pass']:>5} "
            f"{_fmt(r['avg_confidence']):>9} {_fmt(r['avg_fwd_return_blocked']):>9} {_fmt(r['avg_fwd_return_full_pass']):>9}"
        )

    out_path = out_dir / "gate_activity_by_sleeve_year.csv"
    df_gate.to_csv(out_path, index=False)
    log.info("Saved gate activity -> %s", out_path)
    return df_gate


# ── Final summary ──────────────────────────────────────────────────────────────

def print_final_summary(
    candidates_df: pd.DataFrame,
    label_quality_df: pd.DataFrame,
    segment_summary: dict[str, dict],
) -> None:
    print()
    print("=" * 70)
    print("SEGMENTATION AUDIT SUMMARY")
    print("=" * 70)

    # Label quality summary
    print()
    print("LABEL QUALITY BY SEGMENT")
    print("-" * 50)
    for seg_name, info in segment_summary.items():
        if info.get("skipped"):
            print(f"  {seg_name:<20}: SKIPPED (n_labelled={info['n_labelled']})")
        else:
            n_lab = info.get("n_labelled", 0)
            pos_r = info.get("pos_rate", 0)
            auc_m = info.get("auc_mean", None)
            auc_s = f"{auc_m:.4f}" if auc_m is not None else "N/A"
            print(f"  {seg_name:<20}: n_labelled={n_lab:>4}  pos_rate={pos_r:.1f}%  best_auc(mean)={auc_s}")

    # Key findings
    print()
    print("KEY FINDING:")

    # Count unique sleeve families
    n_families = 0
    if "sleeve_label" in candidates_df.columns:
        sleeves = candidates_df["sleeve_label"].unique()
        n_families = len(sleeves)

    print(f"  - Universal model mixes {n_families} sleeve types")

    # Positive rates for key segments
    for seg_name in ("btc_4h_only", "eth_only", "1h_only", "equity_only"):
        info = segment_summary.get(seg_name, {})
        if not info.get("skipped") and "pos_rate" in info:
            print(f"  - {seg_name} positive rate: {info['pos_rate']:.1f}%")

    # Best/worst AUC segments
    scored = {
        k: v for k, v in segment_summary.items()
        if not v.get("skipped") and "auc_mean" in v
    }
    if scored:
        best_seg  = max(scored, key=lambda k: scored[k]["auc_mean"])
        worst_seg = min(scored, key=lambda k: scored[k]["auc_mean"])
        best_info  = scored[best_seg]
        worst_info = scored[worst_seg]

        auc_list = best_info.get("aucs", [])
        auc_vals = "  ".join(f"{a:.3f}" for a in auc_list)
        print(f"  - '{best_seg}' shows most consistent AUC across folds: [{auc_vals}] (mean={best_info['auc_mean']:.4f})")
        print(f"  - '{worst_seg}' shows lowest mean AUC: {worst_info['auc_mean']:.4f}")

    # Diagnosis
    print()
    print("ANSWER TO CORE QUESTION:")
    print("Is the universal GBM gate broken because of:")
    print("  A) Missing temporal context, or")
    print("  B) Mixing incompatible event families?")
    print()

    if not scored:
        print("  [Insufficient data to diagnose — all segments skipped]")
        return

    btc4h_info = scored.get("btc_4h_only")
    universal_auc = None
    # Infer universal from btc_only or crypto_only as proxy
    for fallback in ("crypto_only", "btc_only"):
        if fallback in scored:
            universal_auc = scored[fallback]["auc_mean"]
            break

    diagnosis = []

    if btc4h_info is not None and universal_auc is not None:
        delta = btc4h_info["auc_mean"] - universal_auc
        if delta > 0.03:
            diagnosis.append(
                f"B (primary): BTC_4H AUC ({btc4h_info['auc_mean']:.4f}) > universal proxy "
                f"({universal_auc:.4f}) by {delta:+.4f} — mixing incompatible families is the main driver"
            )
        else:
            diagnosis.append(
                f"Family mixing is NOT the primary cause: BTC_4H AUC ({btc4h_info['auc_mean']:.4f}) "
                f"not clearly better than universal proxy ({universal_auc:.4f}, delta={delta:+.4f})"
            )

    # Check if all segments fail similarly in 2023 (fold index 2 = 2022->2023)
    aucs_2023 = []
    for seg, info in scored.items():
        fold_aucs = info.get("aucs", [])
        if len(fold_aucs) > 2:
            aucs_2023.append(fold_aucs[2])
    if aucs_2023:
        mean_2023 = np.mean(aucs_2023)
        if mean_2023 < 0.55:
            diagnosis.append(
                f"A (contributing): Mean 2023-fold AUC across segments = {mean_2023:.4f} "
                f"(< 0.55) — temporal regime shift affects all segments"
            )
        else:
            diagnosis.append(
                f"A: Mean 2023-fold AUC across segments = {mean_2023:.4f} — temporal context appears adequate"
            )

    if not diagnosis:
        diagnosis.append("Insufficient segment coverage to diagnose root cause — run with more data")

    for d in diagnosis:
        print(f"  -> {d}")

    print()
    print("=" * 70)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates_csv = args.candidates_csv
    if not Path(candidates_csv).exists():
        log.error("candidates.csv not found at %s", candidates_csv)
        sys.exit(1)

    # Load data
    candidates_df, features_df = _load_candidates_and_features(candidates_csv, args)

    # Report 0: Temporal feature profile (only when temporal features present)
    temporal_cols = [
        "bars_since_last_entry",
        "days_since_last_full_exposure",
        "bars_in_defensive_state",
        "candidate_count_since_last_full_exposure",
        "candidate_count_since_last_successful_risk_on",
    ]
    present_temporal = [c for c in temporal_cols if c in features_df.columns and features_df[c].abs().sum() > 0]
    if present_temporal:
        print()
        print("=" * 70)
        print("REPORT 0: TEMPORAL FEATURE PROFILE (mean by year)")
        print("=" * 70)
        years = pd.to_datetime(candidates_df["timestamp"]).dt.year.values
        labels = candidates_df["label"].values
        feat_sub = features_df[present_temporal].copy()
        feat_sub["year"] = years
        feat_sub["label"] = labels
        # All candidates — mean by year
        print("\n  Mean values by year (all labelled candidates):")
        labelled_mask = labels != -1
        for yr in sorted(set(years)):
            mask = (years == yr) & labelled_mask
            if mask.sum() == 0:
                continue
            vals = feat_sub.loc[mask, present_temporal].mean()
            n_pos = int((labels[mask] == 1).sum())
            n_neg = int((labels[mask] == 0).sum())
            row_str = "  ".join(f"{c.split('_',1)[1][:18]}={vals[c]:.1f}" for c in present_temporal)
            print(f"    {yr}  n={mask.sum():>3} (+{n_pos}/-{n_neg})  {row_str}")
        print()
    else:
        print("\n  [Temporal features not present or all-zero — run experiment script to generate them]")

    # Report 1: Label quality by sleeve
    label_quality_df = report_label_quality(candidates_df, out_dir)

    # Report 2: Walk-forward by segment
    segment_summary = report_segments(candidates_df, features_df, out_dir)

    # Report 3: 2023 audit
    df_audit_2023 = report_2023_audit(candidates_df, features_df, out_dir)

    # Report 4: Gate activity
    df_gate = report_gate_activity(candidates_df, features_df, out_dir)

    # Final summary
    print_final_summary(candidates_df, label_quality_df, segment_summary)

    print(f"\nAll outputs saved to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
