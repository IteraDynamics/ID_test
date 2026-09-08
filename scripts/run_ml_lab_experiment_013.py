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
import json
import platform
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scripts import run_ml_lab_experiment_012 as ref

ROOT = ref.ROOT
BASELINES = {"low_vol_60d": ("vol_60d_xrank", -1),
             "momentum_60d": ("ret_60d_xrank", 1),
             "momentum_120d": ("ret_120d_xrank", 1)}
KEYS = ["memory_scheme", "test_year", "timestamp"]


def observations(root, panel):
    frames = ref.exp5._load_universe(root / "data")
    calendar = ref.exp5._common_calendar(frames)
    parts = []
    for ticker in ref.exp5.UNIVERSE:
        f = ref.exp5._asset_features(frames[ticker], calendar, ticker)
        g = panel.loc[panel.ticker == ticker, ["timestamp", "ticker", "target_end_date", "target_raw"]].copy()
        close = f["close"].reindex(g.timestamp).to_numpy()
        end = f["close"].reindex(g.target_end_date).to_numpy()
        vol = f["vol_60d"].reindex(g.timestamp).to_numpy()
        g["forward_return"] = end / close - 1
        ref.finite(g, ["forward_return"], "return_numerator")
        ref.require(np.allclose(g.forward_return / (vol * np.sqrt(20)), g.target_raw,
                                atol=ref.TOLERANCE, rtol=0), "RETURN_RECONSTRUCTION_FAILURE")
        parts.append(g[["timestamp", "ticker", "forward_return"]])
    return pd.concat(parts, ignore_index=True)


def audit(predictions):
    rows, selections, attribution, agreement = [], [], [], []
    for key, group in predictions.groupby(KEYS, sort=True):
        ridge = group.loc[group.model == "price_ridge"].set_index("ticker").sort_index()
        for model, g in group.groupby("model", sort=True):
            g = g.sort_values("ticker").copy()
            ref.require(len(g) == 14 and g.ticker.nunique() == 14, "ASSET_SUPPORT_FAILURE")
            ref.finite(g, ["score", "target_raw", "forward_return"], "audit")
            order = g.sort_values(["score", "ticker"], kind="stable")
            bottom, top = set(order.head(4).ticker), set(order.tail(4).ticker)
            for row in g.itertuples():
                weight = (int(row.ticker in top) - int(row.ticker in bottom)) / 4
                selections.append(dict(zip(KEYS, key), model=model, ticker=row.ticker,
                                       tail="top" if row.ticker in top else "bottom" if row.ticker in bottom else "middle"))
                for outcome in ("target_raw", "forward_return"):
                    attribution.append(dict(zip(KEYS, key), model=model, ticker=row.ticker,
                                            outcome=outcome, contribution=weight * getattr(row, outcome)))
            for outcome in ("target_raw", "forward_return"):
                ic = g.score.rank(method="average").corr(g[outcome].rank(method="average"))
                ref.require(np.isfinite(ic), "UNDEFINED_IC")
                rows.append(dict(zip(KEYS, key), model=model, outcome=outcome, rank_ic=ic,
                                 spread=order.tail(4)[outcome].mean()-order.head(4)[outcome].mean()))
            aligned = g.set_index("ticker").sort_index()
            corr = ridge.score.rank().corr(aligned.score.rank())
            ref.require(np.isfinite(corr), "UNDEFINED_AGREEMENT")
            agreement.append(dict(zip(KEYS, key), model=model, rank_correlation=corr))
    metrics = pd.DataFrame(rows)
    paired = []
    keys = KEYS + ["outcome"]
    r = metrics.loc[metrics.model == "price_ridge"]
    for baseline in BASELINES:
        left, right = ref.align_exact(r, metrics.loc[metrics.model == baseline], keys, baseline)
        paired.append((left[["rank_ic", "spread"]]-right[["rank_ic", "spread"]]).reset_index().assign(comparison="price_ridge_minus_"+baseline))
    selected = pd.DataFrame(selections)
    persistence = []
    for (memory, model, tail), g in selected.loc[selected["tail"] != "middle"].groupby(["memory_scheme", "model", "tail"], sort=True):
        previous = None
        for timestamp, a in g.groupby("timestamp", sort=True):
            current = set(a.ticker)
            if previous is not None:
                persistence.append({"memory_scheme": memory, "model": model, "tail": tail,
                                    "timestamp": timestamp, "retained_fraction": len(current & previous)/4})
            previous = current
    return {"anchor_metrics": metrics, "paired_differences": pd.concat(paired, ignore_index=True),
            "selections": selected, "asset_contributions": pd.DataFrame(attribution),
            "score_agreement": pd.DataFrame(agreement), "selection_persistence": pd.DataFrame(persistence)}


def summarize(frame, label):
    rows = []
    for (memory, name, outcome), g in frame.groupby(["memory_scheme", label, "outcome"], sort=True):
        periods = {"all": g, "pre_2022": g.loc[g.test_year < 2022], "post_2022_2024": g.loc[g.test_year >= 2022]}
        periods.update({str(y): a for y, a in g.groupby("test_year", sort=True)})
        for period, a in periods.items():
            ref.require(len(a)>0, "MISSING_PERIOD")
            rows.append({"memory_scheme": memory, label: name, "outcome": outcome, "period": period,
                         "anchors": len(a), "mean_ic": a.rank_ic.mean(), "median_ic": a.rank_ic.median(),
                         "positive_ic_fraction": (a.rank_ic>0).mean(), "mean_spread": a.spread.mean(), "median_spread": a.spread.median()})
    return pd.DataFrame(rows)


def classify(summary):
    components = []
    for memory in ref.MEMORIES:
        for baseline in BASELINES:
            g = summary.loc[(summary.memory_scheme == memory) & (summary.comparison == "price_ridge_minus_"+baseline) & (summary.outcome == "target_raw")]
            p = g.loc[g.period.isin(ref.PERIODS)]
            annual = g.loc[g.period.str.fullmatch(r"[0-9]{4}")]
            ref.require(len(p)==2 and len(annual)>0, "CLASSIFICATION_SUPPORT_FAILURE")
            passed = bool((p.mean_ic>0).all() and (p.mean_spread>0).all() and (annual.mean_ic>0).sum()*2>len(annual))
            components.append({"memory_scheme": memory, "baseline": baseline, "passed": passed,
                               "positive_ic_years": int((annual.mean_ic>0).sum()), "years": len(annual)})
    primary = all(x["passed"] for x in components if x["memory_scheme"]=="trailing_3y")
    label = "NO_STABLE_PRIMARY_BASELINE_INCREMENT" if not primary else "EXPLORATORY_BASELINE_INCREMENT_RECURRENT" if all(x["passed"] for x in components) else "MEMORY_DEPENDENT_BASELINE_INCREMENT"
    return {"classification": label, "components": components}


def run(root, manifest_path, output, synthetic=False):
    ref.require(not output.exists(), "OUTPUT_DIRECTORY_ALREADY_EXISTS")
    manifest = ref.verify_inputs(root, manifest_path, synthetic)
    mh = ref.sha256(manifest_path)
    panel, _, _ = ref.load_panel(root)
    _, support, expected = ref.plan_folds(panel)
    saved = ref.dates(pd.read_csv(root/ref.REF_DIR/"experiment_009_oos_predictions.csv", float_precision="round_trip"))
    anchors = ref.dates(pd.read_csv(root/ref.REF_DIR/"experiment_009_anchor_metrics.csv", float_precision="round_trip"))
    restored, _, parity = ref.verify_references(expected, saved, anchors)
    ridge = restored.loc[restored.model == "price_ridge"].copy()
    if not synthetic:
        for memory in ref.MEMORIES:
            g = ridge.loc[ridge.memory_scheme == memory]
            ref.require(g.timestamp.nunique()==902 and set(g.test_year)==set(range(2007,2025)) and g.loc[g.test_year>=2022].timestamp.nunique()==147, "FROZEN_SUPPORT_MISMATCH")
    features = panel[["timestamp", "ticker"] + [x[0] for x in BASELINES.values()]]
    ridge = ridge.merge(features, on=["timestamp", "ticker"], validate="many_to_one", how="left")
    ridge = ridge.merge(observations(root, panel), on=["timestamp", "ticker"], validate="many_to_one", how="left")
    ref.finite(ridge, [x[0] for x in BASELINES.values()] + ["forward_return"], "joined_features")
    parts = [ridge]
    for name, (feature, sign) in BASELINES.items():
        parts.append(ridge.assign(model=name, score=sign*ridge[feature]))
    predictions = pd.concat(parts, ignore_index=True).sort_values(ref.KEYS).reset_index(drop=True)
    tables = audit(predictions)
    tables.update(predictions=predictions, reference_parity=parity, fold_support=support)
    tables["model_summary"] = summarize(tables["anchor_metrics"], "model")
    tables["comparison_summary"] = summarize(tables["paired_differences"], "comparison")
    sources = sorted(set([Path(__file__), Path(ref.__file__)] + list((ROOT/"research/ml_lab").rglob("*.py")) + list((ROOT/"research/artifact_io").rglob("*.py")) + [ROOT/"scripts/_checkout_bootstrap.py"] + [ROOT/f"scripts/run_ml_lab_experiment_{i}.py" for i in ("005","009","010")]))
    report = {"experiment": "ML_LAB_EXPERIMENT_013_BASELINE_AUDIT", "status": "EXPLORATORY_NONCONFIRMATORY",
              "synthetic": synthetic, "fits": 0,
              "specification_sha256": ref.sha256(ROOT/"docs/research/ML_LAB_EXPERIMENT_013_BASELINE_AUDIT.md"), "reserved_2025_holdout_used": False,
              "inputs": manifest["inputs"], "manifest_sha256": mh,
              "code": {"commit": subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(), "files": {str(p.relative_to(ROOT).as_posix()):ref.sha256(p) for p in sources}},
              "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": ref.scipy.__version__, "sklearn": ref.sklearn.__version__},
              "reference_checks": len(parity), "model_summary": tables["model_summary"].to_dict("records"),
              "comparisons": tables["comparison_summary"].to_dict("records"),
              **classify(tables["comparison_summary"]),
              "limitations": "Discovery-contaminated overlapping targets. Return numerator is diagnostic, not net P&L; persistence is not portfolio turnover.",
              "artifact_files": {name:f"experiment_013_{name}.csv" for name in tables}}
    ref.verify_inputs(root, manifest_path, synthetic)
    ref.require(ref.sha256(manifest_path)==mh, "MANIFEST_CHANGED_DURING_RUN")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".experiment013-", dir=output.parent) as temp:
        stage = Path(temp)/"outputs"
        stage.mkdir()
        for name, table in tables.items():
            table.to_csv(stage/report["artifact_files"][name], index=False)
        report["artifact_sha256"] = {k:ref.sha256(stage/v) for k,v in report["artifact_files"].items()}
        encoded = json.dumps(report, sort_keys=True, indent=2, allow_nan=False, default=ref.json_default)
        (stage/"experiment_013_report.json").write_text(encoded, encoding="utf-8")
        stage.rename(output)
    return report


def main():
    p = argparse.ArgumentParser(description="Experiment 013: saved Ridge baseline audit; no fitting")
    p.add_argument("--input-root", type=Path, default=ROOT)
    p.add_argument("--output-dir", type=Path, default=ROOT/"artifacts/ml_lab_experiment_013")
    p.add_argument("--preflight-only", action="store_true")
    a = p.parse_args()
    if a.preflight_only:
        ref.verify_inputs(a.input_root.resolve(), ref.MANIFEST)
        print("INPUT_BYTES_VERIFIED_NO_FIT")
    else:
        print(json.dumps(run(a.input_root.resolve(), ref.MANIFEST, a.output_dir.resolve()), default=ref.json_default))


if __name__ == "__main__":
    main()
