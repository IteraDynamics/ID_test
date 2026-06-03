"""Recovery Trust Gate — walk-forward ML model training and evaluation.

Trains logistic regression, random forest, or gradient boosting on labelled
candidate re-risk events, using chronological expanding-window folds to avoid
data leakage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_auc_score
from sklearn.preprocessing import StandardScaler

log = logging.getLogger(__name__)


@dataclass
class FoldResult:
    """Results for a single walk-forward fold."""

    fold_label: str
    train_count: int            # labelled examples used (excl ambiguous)
    test_count: int
    train_positive: int
    train_negative: int
    test_positive: int
    test_negative: int
    low_confidence: bool        # True if train_count < 30
    auc: float | None
    precision_neg: float | None   # precision on fake-rebound class (label=0)
    recall_neg: float | None
    confusion_matrix: np.ndarray | None
    test_probs: pd.Series | None  # index=candidate timestamps, values=recovery_confidence
    test_labels: pd.Series | None
    feature_importance: pd.Series | None  # for RF/GBM only


def _make_model(model_type: str):
    """Instantiate a sklearn classifier by name."""
    if model_type == "logistic":
        return LogisticRegression(
            C=0.1,
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
        )
    elif model_type == "rf":
        return RandomForestClassifier(
            n_estimators=100,
            max_depth=4,
            class_weight="balanced",
            random_state=42,
        )
    elif model_type == "gbm":
        return GradientBoostingClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.05,
            random_state=42,
        )
    else:
        raise ValueError(f"Unknown model_type: {model_type!r}. Choose 'logistic', 'rf', or 'gbm'.")


def run_walk_forward(
    candidates_df: pd.DataFrame,
    features_df: pd.DataFrame,
    folds: list[tuple[int, int]],
    model_type: str = "logistic",
) -> list[FoldResult]:
    """Run walk-forward cross-validation on labelled candidate re-risk events.

    Parameters
    ----------
    candidates_df:
        Must have columns: timestamp, label (1/0/-1).
    features_df:
        Feature matrix, same index as candidates_df.
    folds:
        List of (train_end_year, test_year) tuples, e.g.
        [(2020, 2021), (2021, 2022), ...]
    model_type:
        One of "logistic", "rf", "gbm".

    Returns
    -------
    list[FoldResult]
    """
    if len(candidates_df) != len(features_df):
        raise ValueError(
            f"candidates_df length {len(candidates_df)} != features_df length {len(features_df)}"
        )

    # Normalise timestamps to pd.Timestamp for reliable year extraction
    timestamps = pd.to_datetime(candidates_df["timestamp"])
    years = timestamps.dt.year.values
    labels = candidates_df["label"].values

    feature_cols = list(features_df.columns)
    X_all = features_df[feature_cols].values.astype(float)

    results: list[FoldResult] = []

    for train_end_year, test_year in folds:
        fold_label = f"{train_end_year}→{test_year}"
        log.info("Fold %s: train up to %d, test on %d", fold_label, train_end_year, test_year)

        # Train mask: year <= train_end_year AND label != -1 (not ambiguous)
        train_mask = (years <= train_end_year) & (labels != -1)
        # Test mask: year == test_year (include ambiguous for diagnostics)
        test_mask = years == test_year

        train_idx = np.where(train_mask)[0]
        test_idx  = np.where(test_mask)[0]

        train_labels = labels[train_idx]
        test_labels_all = labels[test_idx]

        train_count    = len(train_idx)
        train_positive = int((train_labels == 1).sum())
        train_negative = int((train_labels == 0).sum())

        # Test counts — only non-ambiguous for metric computation
        test_nonambig_mask = test_labels_all != -1
        test_nonambig_idx  = test_idx[test_nonambig_mask]
        test_nonambig_labels = labels[test_nonambig_idx]
        test_count    = len(test_nonambig_idx)
        test_positive = int((test_nonambig_labels == 1).sum())
        test_negative = int((test_nonambig_labels == 0).sum())

        low_confidence = train_count < 30

        if low_confidence:
            log.warning(
                "Fold %s: LOW CONFIDENCE — only %d training examples (< 30)",
                fold_label, train_count,
            )

        # Cannot train without both classes
        if train_positive == 0 or train_negative == 0:
            log.warning(
                "Fold %s: missing a class in train set (pos=%d neg=%d) — skipping",
                fold_label, train_positive, train_negative,
            )
            results.append(FoldResult(
                fold_label=fold_label,
                train_count=train_count,
                test_count=test_count,
                train_positive=train_positive,
                train_negative=train_negative,
                test_positive=test_positive,
                test_negative=test_negative,
                low_confidence=low_confidence,
                auc=None,
                precision_neg=None,
                recall_neg=None,
                confusion_matrix=None,
                test_probs=None,
                test_labels=None,
                feature_importance=None,
            ))
            continue

        X_train = X_all[train_idx]
        y_train = train_labels

        # Scale features using only train set statistics
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)

        # Fit model
        model = _make_model(model_type)
        model.fit(X_train_scaled, y_train)

        # Predict on all test bars (including ambiguous)
        test_probs_series: pd.Series | None = None
        test_labels_series: pd.Series | None = None
        auc: float | None = None
        prec_neg: float | None = None
        rec_neg:  float | None = None
        cm: np.ndarray | None = None

        if len(test_idx) > 0:
            X_test_all = X_all[test_idx]
            X_test_scaled = scaler.transform(X_test_all)

            # predict_proba returns [P(class=0), P(class=1)]
            proba = model.predict_proba(X_test_scaled)
            classes = list(model.classes_)
            if 1 in classes:
                pos_col = classes.index(1)
            else:
                pos_col = 0  # fallback

            recovery_conf = proba[:, pos_col]

            test_ts = timestamps.iloc[test_idx]
            test_probs_series  = pd.Series(recovery_conf, index=test_ts.values, name="recovery_confidence")
            test_labels_series = pd.Series(test_labels_all, index=test_ts.values, name="label")

        # Metrics only on non-ambiguous test set
        if test_count >= 10 and test_positive > 0 and test_negative > 0 and test_probs_series is not None:
            # Subset to non-ambiguous
            nonambig_ts = timestamps.iloc[test_nonambig_idx].values
            # Match by position in test_probs_series — find the indices that correspond
            # to non-ambiguous test rows (same order as test_idx)
            nonambig_in_test = np.where(test_nonambig_mask)[0]  # positions within test_idx
            probs_nonambig = recovery_conf[nonambig_in_test]
            y_pred_binary  = (probs_nonambig >= 0.5).astype(int)

            try:
                auc = float(roc_auc_score(test_nonambig_labels, probs_nonambig))
            except Exception as e:
                log.warning("Fold %s: AUC computation failed: %s", fold_label, e)
                auc = None

            try:
                prec, rec, _, _ = precision_recall_fscore_support(
                    test_nonambig_labels,
                    y_pred_binary,
                    labels=[0],
                    zero_division=0,
                )
                prec_neg = float(prec[0])
                rec_neg  = float(rec[0])
            except Exception as e:
                log.warning("Fold %s: precision/recall computation failed: %s", fold_label, e)

            try:
                cm = confusion_matrix(test_nonambig_labels, y_pred_binary, labels=[0, 1])
            except Exception as e:
                log.warning("Fold %s: confusion matrix failed: %s", fold_label, e)
        else:
            if test_count < 10:
                log.warning(
                    "Fold %s: only %d non-ambiguous test examples — skipping AUC/metrics",
                    fold_label, test_count,
                )
            elif test_positive == 0 or test_negative == 0:
                log.warning(
                    "Fold %s: test set missing a class (pos=%d neg=%d) — skipping AUC",
                    fold_label, test_positive, test_negative,
                )

        # Feature importance
        feat_imp: pd.Series | None = None
        try:
            if model_type in ("rf", "gbm"):
                imp = model.feature_importances_
            else:  # logistic
                imp = np.abs(model.coef_[0])
            feat_imp = pd.Series(imp, index=feature_cols, name="importance").sort_values(ascending=False)
        except Exception as e:
            log.warning("Fold %s: feature importance extraction failed: %s", fold_label, e)

        results.append(FoldResult(
            fold_label=fold_label,
            train_count=train_count,
            test_count=test_count,
            train_positive=train_positive,
            train_negative=train_negative,
            test_positive=test_positive,
            test_negative=test_negative,
            low_confidence=low_confidence,
            auc=auc,
            precision_neg=prec_neg,
            recall_neg=rec_neg,
            confusion_matrix=cm,
            test_probs=test_probs_series,
            test_labels=test_labels_series,
            feature_importance=feat_imp,
        ))

    return results
