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
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SCRIPTS_DIR = Path(__file__).resolve().parent
from scripts import run_ml_lab_experiment_005 as exp5
from scripts import run_ml_lab_experiment_009 as exp9
from scripts import run_ml_lab_experiment_010 as exp10
from research.artifact_io.v1 import sha256_file_v1

ROOT = SCRIPTS_DIR.parent
MANIFEST = ROOT / "docs/research/evidence/ML_LAB_EXPERIMENT_012_INPUT_MANIFEST.json"
FROZEN_MANIFEST_SHA256 = '87c600b9bbd90bfb446f1aaaad8083e5559e631df07396e5ef657dd8af4a97e6'
MODEL = "compact_macro_ridge"
BASELINES = ("price_ridge", "price_gbm", "macro_ridge", "macro_gbm")
MEMORIES = {"expanding": None, "trailing_3y": 3}
INTERACTIONS = (
    "curve_10y2y_pct252__x__vol_60d_xrank",
    "vix_pct252__x__vol_60d_xrank",
    "curve_10y2y_pct252__x__ret_120d_xrank",
    "rate2_pct252__x__vol_60d_xrank",
    "rate2_pct252__x__ret_120d_xrank",
    "rate2_chg20__x__ret_120d_xrank",
)
FEATURES = tuple(exp9.PRICE_FEATURES) + tuple(exp9.MACRO_STATES) + INTERACTIONS
KEYS = ["test_year", "memory_scheme", "model", "timestamp", "ticker"]
ANCHOR_KEYS = KEYS[:-1]
METRICS = ("rank_ic", "top_minus_bottom_raw_target")
REF_DIR = "artifacts/ml_lab_experiment_009"
INPUT_PATHS = tuple(f"data/{ticker}_1D.csv" for ticker in exp5.UNIVERSE) + tuple(
    f"{REF_DIR}/experiment_009_{name}.csv"
    for name in ("oos_predictions", "anchor_metrics", "macro_state")
)
TOLERANCE = 1e-10
PERIODS = ("pre_2022", "post_2022_2024")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return sha256_file_v1(Path(path), chunk_size=1024 * 1024, factory=hashlib.sha256)


def verify_inputs(root, manifest_path, synthetic=False):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    if not synthetic:
        # Freeze manifest values independently of Git checkout line endings.
        # Input artifact bytes themselves are always hashed without normalization.
        contract_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        require(hashlib.sha256(contract_bytes).hexdigest() == FROZEN_MANIFEST_SHA256,
                "FROZEN_MANIFEST_HASH_MISMATCH")
    require(bool(manifest.get("synthetic", False)) == synthetic, "MANIFEST_MODE_MISMATCH")
    require(manifest.get("last_allowed_date") == "2024-12-31", "MANIFEST_CUTOFF_MISMATCH")
    items = manifest["inputs"]
    require(len(items) == len(INPUT_PATHS) and {i["path"] for i in items} == set(INPUT_PATHS),
            "MANIFEST_INPUT_SET_MISMATCH")
    for item in items:
        path = root / item["path"]
        require(path.is_file(), f"MISSING_INPUT:{item['path']}")
        require(path.stat().st_size == item["bytes"] and sha256(path) == item["sha256"],
                f"INPUT_HASH_MISMATCH:{item['path']}")
    return manifest


def finite(frame, columns, context):
    require(set(columns).issubset(frame.columns), f"MISSING_COLUMNS:{context}")
    require(np.isfinite(frame[list(columns)].to_numpy(dtype=float)).all(), f"NONFINITE:{context}")


def dates(frame):
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    require(frame["timestamp"].notna().all(), "MISSING_TIMESTAMP")
    return frame


def indexed(frame, keys, context):
    require(frame[keys].notna().all().all(), f"MISSING_KEY:{context}")
    require(not frame.duplicated(keys).any(), f"DUPLICATE_KEYS:{context}")
    return frame.set_index(keys).sort_index()


def align_exact(expected, actual, keys, context):
    left = indexed(expected, keys, context + ":expected")
    right = indexed(actual, keys, context + ":actual")
    require(left.index.equals(right.index), f"ROW_KEY_MISMATCH:{context}")
    return left, right


def load_panel(root):
    frames = exp5._load_universe(root / "data")
    require(all(f.index.max() <= exp5.LAST_ALLOWED_DATE for f in frames.values()), "SOURCE_CUTOFF_FAILURE")
    calendar = exp5._common_calendar(frames)
    panel = exp5._build_panel(frames, calendar)
    macro = dates(pd.read_csv(root / REF_DIR / "experiment_009_macro_state.csv"))
    macro = macro.loc[macro["timestamp"] <= exp5.LAST_ALLOWED_DATE].copy()
    indexed(macro, ["timestamp"], "macro")
    panel = exp9._augment_panel(panel, macro.set_index("timestamp"))
    indexed(panel, ["timestamp", "ticker"], "panel")
    finite(panel, list(exp9.AUGMENTED_FEATURES) + ["target_raw", "target_rank"], "panel")
    require(panel["target_end_date"].notna().all()
            and (panel["target_end_date"] <= exp5.LAST_ALLOWED_DATE).all(), "TARGET_CUTOFF_FAILURE")
    regimes = exp10._build_regimes(macro)
    # All evaluated anchors must have complete diagnostic states, without inner-join losses.
    used = regimes.set_index("timestamp").reindex(panel["timestamp"].unique())
    require(used.notna().all().all(), "MISSING_REGIME_STATES")
    finite(used, list(exp9.MACRO_STATES)[:1] + ["curve_10y2y", "vix_pct252", "DGS2"], "regimes")
    return panel, macro, regimes


def plan_folds(panel):
    folds, support, expected = [], [], []
    for year in sorted(int(y) for y in panel["timestamp"].dt.year.unique()):
        require(year <= 2024, "TEST_YEAR_CUTOFF_FAILURE")
        test = panel.loc[panel["timestamp"].dt.year == year].copy()
        start = test["timestamp"].min()
        for memory, years in MEMORIES.items():
            train = exp9._training_slice(panel, start, years)
            eligible = len(train) >= exp5.MIN_TRAIN_ROWS and train["timestamp"].nunique() >= 50
            support.append({
                "test_year": year, "memory_scheme": memory, "test_start": start,
                "train_rows": len(train), "train_anchors": train["timestamp"].nunique(),
                "test_rows": len(test), "test_anchors": test["timestamp"].nunique(),
                "max_train_target_end": train["target_end_date"].max() if len(train) else None,
                "eligible": bool(eligible),
            })
            if eligible:
                folds.append((year, memory, train, test))
                for model in BASELINES:
                    expected.append(test[["timestamp", "ticker", "target_end_date", "target_raw", "target_rank"]]
                                    .assign(test_year=year, memory_scheme=memory, model=model))
    require(bool(folds), "NO_ELIGIBLE_FOLDS")
    return folds, pd.DataFrame(support), pd.concat(expected, ignore_index=True)


def anchor_metrics(predictions):
    result = pd.DataFrame([
        exp9._anchor_metric(g)
        for _, g in predictions.groupby(ANCHOR_KEYS, sort=True)
    ])
    finite(result, list(METRICS) + ["assets"], "anchor_metrics")
    return result


def verify_references(expected, saved, saved_anchor):
    finite(saved, ["score", "target_raw", "target_rank"], "saved_predictions")
    require((saved["timestamp"] <= exp5.LAST_ALLOWED_DATE).all(), "REFERENCE_CUTOFF_FAILURE")
    left, right = align_exact(expected, saved, KEYS, "saved_predictions")
    deltas = (left[["target_raw", "target_rank"]] - right[["target_raw", "target_rank"]]).abs()
    require((deltas.to_numpy() <= TOLERANCE).all(), "REFERENCE_TARGET_PARITY_FAILURE")
    if "target_end_date" in right.columns:
        ends = pd.to_datetime(right["target_end_date"], utc=True, errors="raise")
        require(ends.notna().all() and ends.equals(left["target_end_date"]),
                "REFERENCE_TARGET_END_PARITY_FAILURE")
    restored = right.copy()
    restored["target_end_date"] = left["target_end_date"]
    restored = restored.reset_index()
    recomputed = anchor_metrics(restored)
    actual, reference = align_exact(recomputed, saved_anchor, ANCHOR_KEYS, "saved_anchor_metrics")
    finite(reference, list(METRICS) + ["assets"], "saved_anchor_metrics")
    require((actual["assets"] == reference["assets"]).all(), "REFERENCE_ASSET_COUNT_FAILURE")
    metric_delta = (actual[list(METRICS)] - reference[list(METRICS)]).abs()
    require((metric_delta.to_numpy() <= TOLERANCE).all(), "REFERENCE_METRIC_PARITY_FAILURE")
    checks = []
    for key, group in deltas.groupby(level=KEYS[:3], sort=True):
        md = metric_delta.xs(key, level=KEYS[:3])
        checks.append({
            "test_year": key[0], "memory_scheme": key[1], "model": key[2],
            "rows": len(group), "anchors": len(md),
            "max_target_raw_delta": group["target_raw"].max(),
            "max_target_rank_delta": group["target_rank"].max(),
            "max_rank_ic_delta": md["rank_ic"].max(),
            "max_spread_delta": md["top_minus_bottom_raw_target"].max(), "passed": True,
        })
    return restored, recomputed, pd.DataFrame(checks)


def fit_fold(train, test):
    require(tuple(train.loc[:, list(FEATURES)].columns) == FEATURES and len(FEATURES) == 22, "FEATURE_ORDER_FAILURE")
    require(len(set(FEATURES)) == 22 and set(INTERACTIONS).issubset(exp9.INTERACTION_FEATURES), "FEATURE_SET_FAILURE")
    require(len(train) >= exp5.MIN_TRAIN_ROWS and train["timestamp"].nunique() >= 50, "TRAIN_SUPPORT_FAILURE")
    start = test["timestamp"].min()
    require((train["timestamp"] < start).all() and (train["target_end_date"] < start).all(), "TRAIN_EMBARGO_FAILURE")
    require((test["target_end_date"] <= exp5.LAST_ALLOWED_DATE).all(), "TARGET_CUTOFF_FAILURE")
    finite(train, FEATURES + ("target_rank",), "training")
    finite(test, FEATURES, "test")
    model = Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=10.0))])
    model.fit(train[list(FEATURES)].astype(float), train["target_rank"].astype(float))
    require(tuple(model.feature_names_in_) == FEATURES, "FITTED_FEATURE_ORDER_FAILURE")
    scores = model.predict(test[list(FEATURES)].astype(float))
    require(np.isfinite(scores).all(), "NONFINITE_PREDICTIONS")
    return model, scores


def explain_fold(model, test, macro, year, memory):
    scaler, ridge = model.named_steps["scale"], model.named_steps["model"]
    raw = ridge.coef_ / scaler.scale_
    raw_intercept = float(ridge.intercept_ - np.dot(raw, scaler.mean_))
    coeff = pd.DataFrame({
        "feature": FEATURES, "feature_order": np.arange(len(FEATURES)),
        "coefficient": ridge.coef_, "scaler_mean": scaler.mean_, "scaler_scale": scaler.scale_,
        "raw_coefficient": raw, "intercept": ridge.intercept_, "raw_intercept": raw_intercept,
        "test_year": year, "memory_scheme": memory,
    })
    finite(coeff, ["coefficient", "scaler_mean", "scaler_scale", "raw_coefficient", "intercept", "raw_intercept"], "coefficients")
    check = test[list(FEATURES)].to_numpy() @ raw + raw_intercept
    require(np.allclose(check, model.predict(test[list(FEATURES)]), atol=TOLERANCE, rtol=0), "COEFFICIENT_RECONSTRUCTION_FAILURE")
    weights = dict(zip(FEATURES, raw, strict=True))
    states = macro.set_index("timestamp").loc[sorted(test["timestamp"].unique())]
    slopes = []
    for base in ("vol_60d_xrank", "ret_120d_xrank"):
        value = pd.Series(weights[base], index=states.index)
        for name in INTERACTIONS:
            state, feature = name.split("__x__")
            if feature == base:
                value = value + weights[name] * states[state]
        slopes.append(pd.DataFrame({"timestamp": states.index, "base": base, "effective_slope": value.to_numpy(),
                                    "test_year": year, "memory_scheme": memory}))
    return coeff, pd.concat(slopes, ignore_index=True)


def period(year):
    return "pre_2022" if year <= 2021 else "post_2022_2024"


def paired_differences(anchor):
    candidate = anchor.loc[anchor.model == MODEL].drop(columns="model")
    parts = []
    keys = ["test_year", "memory_scheme", "timestamp"]
    for model in BASELINES:
        ref = anchor.loc[anchor.model == model].drop(columns="model")
        left, right = align_exact(candidate, ref, keys, f"paired:{model}")
        delta = left[list(METRICS)] - right[list(METRICS)]
        parts.append(delta.reset_index().assign(comparison=f"{MODEL}_minus_{model}"))
    return pd.concat(parts, ignore_index=True)


def summaries(anchor, differences):
    model_rows, comparison_rows, yearly_rows, yearly_differences = [], [], [], []
    for (memory, model), group in anchor.groupby(["memory_scheme", "model"], sort=True):
        for label in ("all",) + PERIODS:
            selected = group if label == "all" else group.loc[group.test_year.map(period) == label]
            require(len(selected) > 0, f"MISSING_PERIOD:{memory}:{label}")
            model_rows.append({"memory_scheme": memory, "model": model, "period": label, **exp9._summary(selected)})
    for (year, memory, model), group in anchor.groupby(KEYS[:3], sort=True):
        yearly_rows.append({"test_year": year, "memory_scheme": memory, "model": model, **exp9._summary(group)})
    for (memory, comparison), group in differences.groupby(["memory_scheme", "comparison"], sort=True):
        for label in ("all",) + PERIODS:
            selected = group if label == "all" else group.loc[group.test_year.map(period) == label]
            comparison_rows.append({"memory_scheme": memory, "comparison": comparison, "period": label, **exp9._summary(selected)})
        for year, selected in group.groupby("test_year", sort=True):
            yearly_differences.append({"test_year": year, "memory_scheme": memory, "comparison": comparison, **exp9._summary(selected)})
    return tuple(pd.DataFrame(rows) for rows in (model_rows, comparison_rows, yearly_rows, yearly_differences))


def classify(models, comparisons, annual):
    components = {}
    for memory in MEMORIES:
        m = models.loc[models.memory_scheme == memory].set_index(["period", "model"])
        c = comparisons.loc[(comparisons.memory_scheme == memory)
                            & (comparisons.comparison == f"{MODEL}_minus_price_ridge")].set_index("period")
        a = annual.loc[(annual.memory_scheme == memory)
                       & (annual.comparison == f"{MODEL}_minus_price_ridge")]
        require(len(a) > 0, "MISSING_ANNUAL_COMPARISONS")
        cells = {}
        for label in PERIODS:
            row, own = c.loc[label], m.loc[(label, MODEL)]
            cells[label] = {
                "ic_increment": float(row.mean_rank_ic),
                "spread_increment": float(row.mean_top_minus_bottom_raw_target),
                "candidate_ic": float(own.mean_rank_ic),
                "candidate_spread": float(own.mean_top_minus_bottom_raw_target),
                "increment_positive": bool(row.mean_rank_ic > 0 and row.mean_top_minus_bottom_raw_target > 0),
                "candidate_positive": bool(own.mean_rank_ic > 0 and own.mean_top_minus_bottom_raw_target > 0),
            }
        positive_years = int((a.mean_rank_ic > 0).sum())
        majority = positive_years * 2 > len(a)
        own, gbm = m.loc[("all", MODEL)], m.loc[("all", "macro_gbm")]
        ic_match = own.mean_rank_ic >= gbm.mean_rank_ic
        spread_match = own.mean_top_minus_bottom_raw_target >= gbm.mean_top_minus_bottom_raw_target
        components[memory] = {
            "periods": cells, "positive_lift_years": positive_years, "evaluated_years": len(a),
            "strict_year_majority": bool(majority),
            "stable_baseline_lift": bool(majority and all(x["increment_positive"] and x["candidate_positive"] for x in cells.values())),
            "full_sample_gbm_ic_match": bool(ic_match), "full_sample_gbm_spread_match": bool(spread_match),
            "full_sample_gbm_matching": bool(ic_match and spread_match),
        }
    if not components["trailing_3y"]["stable_baseline_lift"]:
        label = "NO_STABLE_PRIMARY_SIMPLIFICATION"
    elif not all(x["stable_baseline_lift"] and x["full_sample_gbm_matching"] for x in components.values()):
        label = "PARTIAL_OR_MEMORY_DEPENDENT_SIMPLIFICATION"
    else:
        label = "EXPLORATORY_COMPACT_REPRESENTATION_SUPPORTED"
    return {"classification": label, "components": components}


def slope_summaries(slopes):
    rows = []
    dimensions = [("annual", "test_year")] + [(name, f"{name}_regime") for name in ("rate", "curve", "vix", "zirp")]
    for family, column in dimensions:
        for (memory, base, state), group in slopes.groupby(["memory_scheme", "base", column], sort=True):
            values = group.effective_slope
            rows.append({"memory_scheme": memory, "base": base, "family": family, "state": str(state),
                         "anchors": len(group), "mean_slope": values.mean(), "median_slope": values.median(),
                         "min_slope": values.min(), "max_slope": values.max(), "positive_fraction": (values > 0).mean()})
    return pd.DataFrame(rows)


def json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(f"Unsupported report value: {type(value).__name__}")


def run(root, manifest_path, output_dir, synthetic=False):
    require(not output_dir.exists(), "OUTPUT_DIRECTORY_ALREADY_EXISTS")
    manifest = verify_inputs(root, manifest_path, synthetic)
    manifest_hash = sha256(manifest_path)
    print("Input hashes verified; rebuilding the frozen U.S. panel", file=sys.stderr, flush=True)
    panel, macro, regimes = load_panel(root)
    folds, support, expected = plan_folds(panel)
    saved = dates(pd.read_csv(root / REF_DIR / "experiment_009_oos_predictions.csv", float_precision="round_trip"))
    saved_anchor = dates(pd.read_csv(root / REF_DIR / "experiment_009_anchor_metrics.csv", float_precision="round_trip"))
    reference, ref_metrics, parity = verify_references(expected, saved, saved_anchor)
    print(f"All {len(parity)} reference checks passed; fitting {len(folds)} compact Ridge folds", file=sys.stderr, flush=True)
    predictions, coefficients, slope_parts = [reference], [], []
    for year, memory, train, test in folds:
        fitted, scores = fit_fold(train, test)
        predictions.append(test[["timestamp", "ticker", "target_end_date", "target_raw", "target_rank"]]
                           .assign(test_year=year, memory_scheme=memory, model=MODEL, score=scores))
        coeff, slopes = explain_fold(fitted, test, macro, year, memory)
        coefficients.append(coeff)
        slope_parts.append(slopes)
    predictions = pd.concat(predictions, ignore_index=True).sort_values(KEYS).reset_index(drop=True)
    candidate_metrics = anchor_metrics(predictions.loc[predictions.model == MODEL])
    metrics = pd.concat([ref_metrics, candidate_metrics], ignore_index=True).sort_values(ANCHOR_KEYS).reset_index(drop=True)
    differences = paired_differences(metrics)
    model_summary, comparisons, yearly, yearly_comparisons = summaries(metrics, differences)
    disposition = classify(model_summary, comparisons, yearly_comparisons)
    slopes = pd.concat(slope_parts, ignore_index=True).merge(regimes, on="timestamp", how="left", validate="many_to_one")
    require(slopes.notna().all().all(), "SLOPE_REGIME_ALIGNMENT_FAILURE")
    finite(slopes, ["effective_slope"], "slopes")
    fidelity = []
    selected = predictions.loc[predictions.model.isin([MODEL, "macro_gbm"])]
    for (year, memory, timestamp), group in selected.groupby(["test_year", "memory_scheme", "timestamp"], sort=True):
        table = group.pivot(index="ticker", columns="model", values="score")
        fidelity.append({"test_year": year, "memory_scheme": memory, "timestamp": timestamp,
                         "rank_correlation": table[MODEL].corr(table["macro_gbm"], method="spearman")})
    fidelity = pd.DataFrame(fidelity)
    finite(fidelity, ["rank_correlation"], "score_fidelity")
    tables = {
        "oos_predictions": predictions, "anchor_metrics": metrics, "yearly_metrics": yearly,
        "comparison_summary": comparisons, "yearly_comparisons": yearly_comparisons,
        "fold_support": support, "reference_parity": parity,
        "coefficients": pd.concat(coefficients, ignore_index=True), "effective_slopes": slopes,
        "slope_summary": slope_summaries(slopes), "score_fidelity": fidelity,
    }
    for name, table in tables.items():
        # Undefined support dates are permitted only for early, ineligible folds.
        finite(table, table.select_dtypes(include="number").columns, name)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable"
    report = {
        "experiment": "ML_LAB_EXPERIMENT_012_COMPACT_MACRO_INTERACTION_SIMPLIFICATION",
        "status": "EXPLORATORY_NONCONFIRMATORY", "synthetic": synthetic, **disposition,
        "design": {"candidate": MODEL, "features": list(FEATURES), "feature_count": len(FEATURES),
                   "ridge_alpha": 10.0, "source_universe": list(exp5.UNIVERSE), "memory_schemes": MEMORIES,
                   "primary_memory": "trailing_3y", "baselines": list(BASELINES),
                   "baselines_refitted": False, "candidate_fits": len(folds), "destination_training_performed": False,
                   "reserved_2025_holdout_used": False, "last_allowed_date": "2024-12-31",
                   "target_changed": False, "hyperparameters_changed": False,
                   "core_runtime_portfolio_changed": False},
        "reference_parity": {"checks": len(parity), "all_passed": bool(parity.passed.all()),
                             "tolerance": TOLERANCE, "max_deltas": parity.filter(like="max_").max().to_dict()},
        "inputs": manifest["inputs"], "manifest_sha256": manifest_hash,
        "code": {"commit": commit, "files": {
            path.relative_to(ROOT).as_posix(): sha256(path)
            for path in sorted(set(
                [Path(__file__), SCRIPTS_DIR / "_checkout_bootstrap.py"]
                + [SCRIPTS_DIR / f"run_ml_lab_experiment_{n:03}.py" for n in (5, 9, 10)]
                + list((ROOT / "research/ml_lab").rglob("*.py"))
                + list((ROOT / "research/artifact_io").rglob("*.py"))
            ))
        }},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                        "scipy": scipy.__version__, "scikit_learn": sklearn.__version__},
        "model_summary": model_summary.to_dict(orient="records"),
        "comparisons": comparisons.to_dict(orient="records"),
        "yearly_comparisons": yearly_comparisons.to_dict(orient="records"),
        "slope_summary": tables["slope_summary"].to_dict(orient="records"),
        "artifact_files": {name: f"experiment_012_{name}.csv" for name in tables},
        "limitations": "Discovery-contaminated, overlapping targets; descriptive rules, no significance or causal claim. No international portability or production implication.",
    }
    # Check for concurrent input changes before publishing a complete output directory.
    verify_inputs(root, manifest_path, synthetic)
    require(sha256(manifest_path) == manifest_hash, "MANIFEST_CHANGED_DURING_RUN")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".experiment012-", dir=output_dir.parent) as temp:
        stage = Path(temp) / "outputs"
        stage.mkdir()
        for name, table in tables.items():
            table.to_csv(stage / report["artifact_files"][name], index=False)
        report["artifact_sha256"] = {name: sha256(stage / filename) for name, filename in report["artifact_files"].items()}
        encoded = json.dumps(report, indent=2, sort_keys=True, default=json_default, allow_nan=False)
        (stage / "experiment_012_report.json").write_text(encoded, encoding="utf-8")
        stage.rename(output_dir)
    print(encoded)
    return report


def main():
    parser = argparse.ArgumentParser(description="Frozen ML Lab Experiment 012; one compact Ridge candidate")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/ml_lab_experiment_012")
    parser.add_argument("--input-root", type=Path, help="Original data/artifact checkout; frozen manifest is always read from this code checkout")
    parser.add_argument("--preflight-only", action="store_true", help="Verify input bytes only; do not load observations or fit")
    parser.add_argument("--synthetic-input-root", type=Path)
    parser.add_argument("--synthetic-manifest", type=Path)
    args = parser.parse_args()
    synthetic = args.synthetic_input_root is not None
    require(synthetic == (args.synthetic_manifest is not None), "SYNTHETIC_ARGUMENTS_MUST_BE_PAIRED")
    require(not (synthetic and args.input_root), "INPUT_ROOT_MODES_EXCLUSIVE")
    root = args.synthetic_input_root.resolve() if synthetic else (args.input_root.resolve() if args.input_root else ROOT)
    require(not synthetic or root != ROOT, "SYNTHETIC_ROOT_MUST_BE_ISOLATED")
    manifest_path = args.synthetic_manifest if synthetic else MANIFEST
    if args.preflight_only:
        checked = verify_inputs(root, manifest_path, synthetic)
        print(json.dumps({"status": "INPUT_BYTES_VERIFIED_NO_FIT", "inputs": len(checked["inputs"]), "synthetic": synthetic}))
        return
    run(root, manifest_path, args.output_dir.resolve(), synthetic)


if __name__ == "__main__":
    main()
