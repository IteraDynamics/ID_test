from __future__ import annotations

"""Summarize the latest Core v1 Jump Risk diagnosis V2 evidence artifacts.

This is an observation-only reporting utility. It reads diagnosis outputs, ranks
feature shifts deterministically, and writes a compact summary without mutating
Core state, thresholds, orders, NAV, or exposure.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

MATERIAL_SHIFT = 0.50
MATERIAL_PSI = 0.25
MATERIAL_KS = 0.20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize Core v1 Jump Risk diagnosis V2 evidence.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--diagnosis-root",
        default="artifacts/core_v1_jump_risk_diagnosis_v2",
        help="Directory containing timestamped diagnosis V2 runs",
    )
    parser.add_argument(
        "--run-dir",
        help="Optional explicit diagnosis run directory; otherwise the newest run is used",
    )
    parser.add_argument("--stream", default="btc_extended_up")
    parser.add_argument("--top", type=int, default=10)
    return parser.parse_args()


def _latest_run(root: Path) -> Path:
    if not root.is_dir():
        raise NotADirectoryError(f"Diagnosis root not found: {root}")
    candidates = sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No diagnosis runs found under: {root}")
    return candidates[-1]


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise ValueError(f"Evidence file is missing required column: {column}")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def rank_evidence(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "feature",
        "reference_mean",
        "observation_mean",
        "standardized_mean_shift",
        "psi",
        "ks_statistic",
        "reference_missing_fraction",
        "observation_missing_fraction",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Evidence file is missing required columns: {missing}")

    ranked = frame.copy()
    ranked["standardized_mean_shift"] = _numeric(ranked, "standardized_mean_shift")
    ranked["psi"] = _numeric(ranked, "psi")
    ranked["ks_statistic"] = _numeric(ranked, "ks_statistic")
    ranked["missingness_increase"] = (
        _numeric(ranked, "observation_missing_fraction")
        - _numeric(ranked, "reference_missing_fraction")
    )
    ranked["material"] = (
        (ranked["standardized_mean_shift"] >= MATERIAL_SHIFT)
        | (ranked["psi"] >= MATERIAL_PSI)
        | (ranked["ks_statistic"] >= MATERIAL_KS)
    )
    ranked["severity_score"] = ranked[["standardized_mean_shift", "psi", "ks_statistic"]].max(axis=1)
    return ranked.sort_values(
        ["material", "severity_score", "standardized_mean_shift", "psi", "ks_statistic", "feature"],
        ascending=[False, False, False, False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)


def _stream_row(by_model: pd.DataFrame, stream: str) -> dict[str, Any]:
    asset, model = stream.split("_", 1)
    matches = by_model[
        (by_model["asset"].astype(str).str.upper() == asset.upper())
        & (by_model["model"].astype(str) == model)
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one diagnosis row for {stream}, found {len(matches)}")
    return matches.iloc[0].to_dict()


def summarize(run_dir: Path, stream: str, top: int) -> dict[str, Any]:
    if top < 1:
        raise ValueError("--top must be at least 1")

    by_model_path = run_dir / "jump_risk_diagnosis_v2_by_model.csv"
    evidence_path = run_dir / f"{stream}_feature_evidence.csv"
    if not by_model_path.exists():
        raise FileNotFoundError(by_model_path)
    if not evidence_path.exists():
        raise FileNotFoundError(evidence_path)

    by_model = pd.read_csv(by_model_path)
    diagnosis = _stream_row(by_model, stream)
    ranked = rank_evidence(pd.read_csv(evidence_path))
    material = ranked[ranked["material"]]

    columns = [
        "feature",
        "reference_mean",
        "observation_mean",
        "standardized_mean_shift",
        "psi",
        "ks_statistic",
        "missingness_increase",
        "material",
        "severity_score",
    ]
    top_rows = ranked.head(top)[columns].to_dict(orient="records")

    return {
        "experiment": "core_v1_jump_risk_diagnosis_v2_evidence_summary",
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "run_dir": str(run_dir.resolve()),
        "stream": stream,
        "diagnosis": diagnosis,
        "material_feature_count": int(len(material)),
        "top_feature_shifts": top_rows,
    }


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve() if args.run_dir else _latest_run(Path(args.diagnosis_root).resolve())
    payload = summarize(run_dir, args.stream, args.top)

    out_json = run_dir / f"{args.stream}_evidence_summary.json"
    out_csv = run_dir / f"{args.stream}_ranked_feature_evidence.csv"
    ranked = rank_evidence(pd.read_csv(run_dir / f"{args.stream}_feature_evidence.csv"))
    ranked.to_csv(out_csv, index=False)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

    diagnosis = payload["diagnosis"]
    print()
    print("Core v1 Jump Risk diagnosis V2 evidence summary")
    print(f"Run dir:       {run_dir}")
    print(f"Stream:        {args.stream}")
    print(f"Diagnosis:     {diagnosis['classification']} / {diagnosis['confidence']}")
    print(f"Material rows: {payload['material_feature_count']}")
    print()
    print(ranked.head(args.top)[[
        "feature",
        "reference_mean",
        "observation_mean",
        "standardized_mean_shift",
        "psi",
        "ks_statistic",
        "material",
    ]].to_string(index=False))
    print()
    print(f"JSON summary:  {out_json}")
    print(f"Ranked CSV:    {out_csv}")
    print("Observation only: no Core state, NAV, orders, thresholds, or exposure were changed.")


if __name__ == "__main__":
    main()
