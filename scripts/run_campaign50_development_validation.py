from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from research.campaign50_equity_breadth import (
    BINARY_PREDICTORS,
    BREADTH_MEMBERS,
    DISCOVERY_CUTOFF,
    EXPECTED_COLUMNS,
    EXPECTED_SIGNS,
    HORIZONS,
    PREDICTORS,
    TARGETS,
    Campaign50Error,
    build_predictors,
    candidate_inventory,
    canonical_csv_bytes,
    canonical_json_bytes,
    compatibility_matches,
    expected_sign_matches,
    forward_returns,
    holm_adjust,
    ols_hc3,
    parse_timestamp,
    sha256_file,
    support_gate,
)
from scripts.reconcile_campaign50_equity_sessions import EXPECTED_SHA256

# Keep standalone script execution working until the separate packaging migration.
import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
if str(_ArtifactPath(__file__).resolve().parents[1]) not in _artifact_sys.path:
    _artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parents[1]))



CAMPAIGN_ID = "campaign50"
STAGE_ID = "development_validation"
EXPECTED_BRANCH = "agent/campaign-50-holdout-first-alpha-research-planning"
STATISTICAL_SPEC_COMMIT = "36dd499d00740062f10c1c070896f740f55f6808"
SOURCE_UNIVERSE_COMMIT = "f32cac981bf55d0b1799949988df70e5546394e5"
EXECUTION_GO_COMMIT = "010dd98d7668aa60cebc014f192de3ff121206d4"
DEVELOPMENT = (date(2018, 1, 2), date(2022, 12, 30))
VALIDATION = (date(2023, 1, 3), date(2024, 12, 31))
REQUIRED_LOOKBACK = 220
CANONICAL_FILES = (
    "campaign50_preflight.json",
    "campaign50_candidate_inventory.csv",
    "campaign50_development_results.csv",
    "campaign50_validation_results.csv",
    "campaign50_shortlist.csv",
    "campaign50_stage_manifest.json",
)

RESULT_FIELDS = (
    "candidate_key",
    "predictor",
    "target",
    "horizon",
    "expected_sign",
    "status",
    "rankable",
    "n",
    "event_n",
    "non_event_n",
    "beta0",
    "beta1",
    "se_beta1",
    "t_stat",
    "raw_p",
    "holm_p",
    "ci_low",
    "ci_high",
    "sign_matches",
    "development_compatibility_matches",
)


class ExecutionError(Campaign50Error):
    pass


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _source_filename(symbol: str) -> str:
    return f"{symbol}_1D.csv"


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    if not math.isfinite(value):
        raise ExecutionError("NONFINITE_MODEL_RESULT")
    return format(value, ".17g")


def _bool_text(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _int_text(value: int | None) -> str:
    return "" if value is None else str(value)


def _sha256_bytes(payload: bytes) -> str:
    from research.artifact_io.v1 import sha256_bytes_v1
    return sha256_bytes_v1(payload, factory=hashlib.sha256)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def _validate_repository_state() -> tuple[str, str]:
    branch = _git("branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise ExecutionError(f"SOURCE_IDENTITY_FAILURE: branch={branch}")
    tracked_status = _git("status", "--porcelain", "--untracked-files=no")
    if tracked_status:
        raise ExecutionError("SOURCE_IDENTITY_FAILURE: tracked worktree modifications")
    head = _git("rev-parse", "HEAD")
    ancestor_check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXECUTION_GO_COMMIT, head],
        capture_output=True,
        text=True,
    )
    if ancestor_check.returncode != 0:
        raise ExecutionError("SOURCE_IDENTITY_FAILURE: execution GO absent from HEAD")
    return branch, head


def _load_source_before_cutoff(
    path: Path,
    expected_sha256: str,
) -> tuple[list[date], list[float], bool]:
    if not path.exists():
        raise ExecutionError(f"SOURCE_IDENTITY_FAILURE: missing {path.name}")
    actual_hash = sha256_file(path)
    if actual_hash != expected_sha256:
        raise ExecutionError(f"SOURCE_IDENTITY_FAILURE: hash mismatch {path.name}")

    sessions: list[date] = []
    closes: list[float] = []
    previous: date | None = None
    post_cutoff_seen = False
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise ExecutionError(f"SOURCE_SCHEMA_FAILURE: {path.name}")
        for row_number, row in enumerate(reader, start=2):
            session = parse_timestamp(row["timestamp"]).date()
            if previous is not None and session <= previous:
                raise ExecutionError(f"SOURCE_ORDER_FAILURE: {path.name}:{row_number}")
            previous = session
            if session > DISCOVERY_CUTOFF:
                post_cutoff_seen = True
                continue
            if post_cutoff_seen:
                raise ExecutionError(
                    f"SOURCE_ORDER_FAILURE: pre-cutoff row after rejected holdout row {path.name}:{row_number}"
                )
            try:
                close = float(row["close"])
            except ValueError as exc:
                raise ExecutionError(f"SOURCE_SCHEMA_FAILURE: {path.name}:{row_number}") from exc
            if not math.isfinite(close) or close <= 0:
                raise ExecutionError(f"SOURCE_SCHEMA_FAILURE: {path.name}:{row_number}")
            sessions.append(session)
            closes.append(close)
    if not sessions:
        raise ExecutionError(f"LOOKBACK_UNAVAILABLE: {path.name}")
    return sessions, closes, post_cutoff_seen


def load_governed_sources(data_root: Path) -> tuple[list[date], dict[str, list[float]], dict[str, Any]]:
    symbols = (*TARGETS, *BREADTH_MEMBERS)
    raw: dict[str, tuple[list[date], list[float]]] = {}
    source_records: list[dict[str, Any]] = []
    for symbol in symbols:
        filename = _source_filename(symbol)
        path = data_root / filename
        sessions, closes, post_cutoff_seen = _load_source_before_cutoff(
            path,
            EXPECTED_SHA256[filename],
        )
        raw[symbol] = (sessions, closes)
        source_records.append(
            {
                "path": filename,
                "sha256": EXPECTED_SHA256[filename],
                "pre_cutoff_first_session": sessions[0].isoformat(),
                "pre_cutoff_last_session": sessions[-1].isoformat(),
                "pre_cutoff_row_count": len(sessions),
                "post_cutoff_rows_rejected_before_analytical_loading": post_cutoff_seen,
            }
        )

    spy_sessions = raw["SPY"][0]
    qqq_sessions = raw["QQQ"][0]
    if spy_sessions != qqq_sessions:
        raise ExecutionError("SOURCE_ORDER_FAILURE: target calendars differ")
    target_calendar = list(spy_sessions)
    if not target_calendar or target_calendar[-1] != DISCOVERY_CUTOFF:
        raise ExecutionError("SOURCE_ORDER_FAILURE: unexpected pre-holdout target endpoint")

    aligned: dict[str, list[float]] = {}
    target_set = set(target_calendar)
    for symbol in symbols:
        sessions, closes = raw[symbol]
        by_session = dict(zip(sessions, closes))
        missing = [session for session in target_calendar if session not in by_session]
        if missing:
            raise ExecutionError(
                f"SOURCE_ORDER_FAILURE: {symbol} missing target session {missing[0].isoformat()}"
            )
        aligned[symbol] = [by_session[session] for session in target_calendar]
        if symbol in TARGETS and set(sessions) != target_set:
            raise ExecutionError(f"SOURCE_ORDER_FAILURE: unexpected target calendar {symbol}")

    metadata = {
        "source_records": sorted(source_records, key=lambda item: item["path"]),
        "target_calendar_first_session": target_calendar[0].isoformat(),
        "target_calendar_last_session": target_calendar[-1].isoformat(),
        "target_calendar_session_count": len(target_calendar),
        "holdout_loaded": False,
    }
    return target_calendar, aligned, metadata


def stage_anchor_indices(
    sessions: Sequence[date],
    *,
    start: date,
    end: date,
    horizon: int,
) -> list[int]:
    eligible = [
        index
        for index, session in enumerate(sessions)
        if start <= session <= end
        and index >= REQUIRED_LOOKBACK - 1
        and index + horizon < len(sessions)
        and sessions[index + horizon] <= end
    ]
    if not eligible:
        return []
    first = eligible[0]
    eligible_set = set(eligible)
    return [
        index
        for index in range(first, eligible[-1] + 1, horizon)
        if index in eligible_set
    ]


def _candidate_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate in candidate_inventory():
        rows.append(
            {
                "candidate_key": candidate.key,
                "predictor": candidate.predictor,
                "target": candidate.target,
                "horizon": candidate.horizon,
                "expected_sign": EXPECTED_SIGNS[candidate.predictor],
                "binary_predictor": candidate.predictor in BINARY_PREDICTORS,
            }
        )
    return rows


def _base_result_row(candidate: Any) -> dict[str, object]:
    return {
        "candidate_key": candidate.key,
        "predictor": candidate.predictor,
        "target": candidate.target,
        "horizon": candidate.horizon,
        "expected_sign": EXPECTED_SIGNS[candidate.predictor],
        "status": "",
        "rankable": False,
        "n": 0,
        "event_n": None,
        "non_event_n": None,
        "beta0": None,
        "beta1": None,
        "se_beta1": None,
        "t_stat": None,
        "raw_p": None,
        "holm_p": None,
        "ci_low": None,
        "ci_high": None,
        "sign_matches": None,
        "development_compatibility_matches": None,
    }


def _evaluate_raw_stage(
    *,
    stage: str,
    stage_range: tuple[date, date],
    sessions: Sequence[date],
    closes: Mapping[str, Sequence[float]],
    predictors: Mapping[str, Mapping[str, Sequence[float | None]]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    outcome_cache = {
        (target, horizon): forward_returns(closes[target], horizon)
        for target in TARGETS
        for horizon in HORIZONS
    }
    for candidate in candidate_inventory():
        row = _base_result_row(candidate)
        anchors = stage_anchor_indices(
            sessions,
            start=stage_range[0],
            end=stage_range[1],
            horizon=candidate.horizon,
        )
        predictor_values = predictors[candidate.target][candidate.predictor]
        outcomes = outcome_cache[(candidate.target, candidate.horizon)]
        x_values: list[float] = []
        y_values: list[float] = []
        for index in anchors:
            x = predictor_values[index]
            y = outcomes[index]
            if x is None or y is None:
                continue
            if not math.isfinite(float(x)) or not math.isfinite(float(y)):
                continue
            x_values.append(float(x))
            y_values.append(float(y))

        failure, n, event_n, non_event_n = support_gate(
            stage,
            candidate.predictor,
            candidate.horizon,
            x_values,
        )
        row.update({"n": n, "event_n": event_n, "non_event_n": non_event_n})
        if failure is not None:
            row["status"] = failure
            rows.append(row)
            continue
        try:
            result = ols_hc3(
                x_values,
                y_values,
                standardize=candidate.predictor not in BINARY_PREDICTORS,
            )
        except Campaign50Error as exc:
            row["status"] = str(exc).split(":", 1)[0]
            rows.append(row)
            continue
        row.update(
            {
                "rankable": True,
                "beta0": result.beta0,
                "beta1": result.beta1,
                "se_beta1": result.se_beta1,
                "t_stat": result.t_stat,
                "raw_p": result.p_value,
                "ci_low": result.ci_low,
                "ci_high": result.ci_high,
                "sign_matches": expected_sign_matches(candidate.predictor, result.beta1),
            }
        )
        rows.append(row)

    rankable_p = {
        str(row["candidate_key"]): float(row["raw_p"])
        for row in rows
        if bool(row["rankable"])
    }
    adjusted = holm_adjust(rankable_p, family_size=24)
    for row in rows:
        if bool(row["rankable"]):
            row["holm_p"] = adjusted[str(row["candidate_key"])]
    return rows


def _classify_stages(
    development_rows: list[dict[str, object]],
    validation_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    development_by_key = {str(row["candidate_key"]): row for row in development_rows}
    for row in development_rows:
        if not bool(row["rankable"]):
            continue
        supported = bool(row["sign_matches"]) and float(row["holm_p"]) <= 0.05
        row["status"] = "DISCOVERY_SUPPORTED" if supported else "DISCOVERY_NOT_SUPPORTED"

    shortlist: list[dict[str, object]] = []
    for row in validation_rows:
        key = str(row["candidate_key"])
        development = development_by_key[key]
        if bool(row["rankable"]) and bool(development["rankable"]):
            compatibility = compatibility_matches(
                float(development["beta1"]),
                float(row["beta1"]),
            )
            row["development_compatibility_matches"] = compatibility
        if development["status"] != "DISCOVERY_SUPPORTED":
            if bool(row["rankable"]):
                row["status"] = "VALIDATION_NOT_ELIGIBLE"
            continue
        if not bool(row["rankable"]):
            continue
        supported = (
            bool(row["sign_matches"])
            and float(row["holm_p"]) <= 0.10
            and bool(row["development_compatibility_matches"])
        )
        row["status"] = "VALIDATION_SUPPORTED" if supported else "VALIDATION_NOT_SUPPORTED"
        if supported:
            shortlist.append(
                {
                    "candidate_key": key,
                    "predictor": row["predictor"],
                    "target": row["target"],
                    "horizon": row["horizon"],
                    "expected_sign": row["expected_sign"],
                    "development_beta1": development["beta1"],
                    "development_holm_p": development["holm_p"],
                    "validation_beta1": row["beta1"],
                    "validation_holm_p": row["holm_p"],
                    "confirmation_authorized": False,
                }
            )
    return development_rows, validation_rows, shortlist


def _serialize_result_rows(rows: Iterable[Mapping[str, object]]) -> bytes:
    serialized: list[dict[str, object]] = []
    for row in rows:
        serialized.append(
            {
                "candidate_key": row["candidate_key"],
                "predictor": row["predictor"],
                "target": row["target"],
                "horizon": row["horizon"],
                "expected_sign": row["expected_sign"],
                "status": row["status"],
                "rankable": _bool_text(bool(row["rankable"])),
                "n": row["n"],
                "event_n": _int_text(row.get("event_n")),
                "non_event_n": _int_text(row.get("non_event_n")),
                "beta0": _format_float(row.get("beta0")),
                "beta1": _format_float(row.get("beta1")),
                "se_beta1": _format_float(row.get("se_beta1")),
                "t_stat": _format_float(row.get("t_stat")),
                "raw_p": _format_float(row.get("raw_p")),
                "holm_p": _format_float(row.get("holm_p")),
                "ci_low": _format_float(row.get("ci_low")),
                "ci_high": _format_float(row.get("ci_high")),
                "sign_matches": _bool_text(row.get("sign_matches")),
                "development_compatibility_matches": _bool_text(
                    row.get("development_compatibility_matches")
                ),
            }
        )
    return canonical_csv_bytes(RESULT_FIELDS, serialized)


def build_artifacts(data_root: Path, repository_head: str, branch: str) -> dict[str, bytes]:
    sessions, closes, source_metadata = load_governed_sources(data_root)
    candidates = candidate_inventory()
    if len(candidates) != 24 or len({candidate.key for candidate in candidates}) != 24:
        raise ExecutionError("SOURCE_SCHEMA_FAILURE: candidate inventory")

    predictors = build_predictors(closes)
    development_rows = _evaluate_raw_stage(
        stage="development",
        stage_range=DEVELOPMENT,
        sessions=sessions,
        closes=closes,
        predictors=predictors,
    )
    validation_rows = _evaluate_raw_stage(
        stage="validation",
        stage_range=VALIDATION,
        sessions=sessions,
        closes=closes,
        predictors=predictors,
    )
    development_rows, validation_rows, shortlist = _classify_stages(
        development_rows,
        validation_rows,
    )

    preflight = {
        "campaign_id": CAMPAIGN_ID,
        "stage_id": STAGE_ID,
        "status": "PASS",
        "branch": branch,
        "repository_commit_sha": repository_head,
        "execution_go_commit_sha": EXECUTION_GO_COMMIT,
        "statistical_specification_commit_sha": STATISTICAL_SPEC_COMMIT,
        "source_universe_commit_sha": SOURCE_UNIVERSE_COMMIT,
        "candidate_count": 24,
        "development_interval": [DEVELOPMENT[0].isoformat(), DEVELOPMENT[1].isoformat()],
        "validation_interval": [VALIDATION[0].isoformat(), VALIDATION[1].isoformat()],
        "holdout_loaded": False,
        "confirmation_enabled": False,
        "method_mutation": False,
        "predictors_generated": True,
        "outcomes_generated": True,
        **source_metadata,
    }

    inventory_fields = (
        "candidate_key",
        "predictor",
        "target",
        "horizon",
        "expected_sign",
        "binary_predictor",
    )
    shortlist_fields = (
        "candidate_key",
        "predictor",
        "target",
        "horizon",
        "expected_sign",
        "development_beta1",
        "development_holm_p",
        "validation_beta1",
        "validation_holm_p",
        "confirmation_authorized",
    )
    shortlist_rows = [
        {
            **row,
            "development_beta1": _format_float(float(row["development_beta1"])),
            "development_holm_p": _format_float(float(row["development_holm_p"])),
            "validation_beta1": _format_float(float(row["validation_beta1"])),
            "validation_holm_p": _format_float(float(row["validation_holm_p"])),
            "confirmation_authorized": "false",
        }
        for row in shortlist
    ]

    artifacts: dict[str, bytes] = {
        "campaign50_preflight.json": canonical_json_bytes(preflight),
        "campaign50_candidate_inventory.csv": canonical_csv_bytes(
            inventory_fields,
            _candidate_rows(),
        ),
        "campaign50_development_results.csv": _serialize_result_rows(development_rows),
        "campaign50_validation_results.csv": _serialize_result_rows(validation_rows),
        "campaign50_shortlist.csv": canonical_csv_bytes(shortlist_fields, shortlist_rows),
    }
    output_hashes = {
        name: {
            "byte_count": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        for name, payload in sorted(artifacts.items())
    }
    manifest = {
        "campaign_id": CAMPAIGN_ID,
        "stage_id": STAGE_ID,
        "status": "PASS",
        "repository_commit_sha": repository_head,
        "execution_go_commit_sha": EXECUTION_GO_COMMIT,
        "statistical_specification_commit_sha": STATISTICAL_SPEC_COMMIT,
        "source_universe_commit_sha": SOURCE_UNIVERSE_COMMIT,
        "source_sha256": {
            name: EXPECTED_SHA256[name]
            for name in sorted(EXPECTED_SHA256)
            if name in {_source_filename(symbol) for symbol in (*TARGETS, *BREADTH_MEMBERS)}
        },
        "development_interval": [DEVELOPMENT[0].isoformat(), DEVELOPMENT[1].isoformat()],
        "validation_interval": [VALIDATION[0].isoformat(), VALIDATION[1].isoformat()],
        "candidate_count": 24,
        "discovery_supported_count": sum(
            row["status"] == "DISCOVERY_SUPPORTED" for row in development_rows
        ),
        "validation_supported_count": len(shortlist),
        "shortlist_count": len(shortlist),
        "predictors_generated": True,
        "outcomes_generated": True,
        "holdout_loaded": False,
        "confirmation_enabled": False,
        "method_mutation": False,
        "canonical_output_files": list(CANONICAL_FILES),
        "output_hashes_excluding_manifest": output_hashes,
        "manifest_self_hash_excluded": True,
    }
    artifacts["campaign50_stage_manifest.json"] = canonical_json_bytes(manifest)
    if tuple(sorted(artifacts)) != tuple(sorted(CANONICAL_FILES)):
        raise ExecutionError("SOURCE_SCHEMA_FAILURE: canonical file set")
    return artifacts


def execute(data_root: Path, output_dir: Path) -> dict[str, object]:
    if output_dir.exists():
        raise ExecutionError(f"SOURCE_IDENTITY_FAILURE: output exists {output_dir}")
    branch, head = _validate_repository_state()
    artifacts = build_artifacts(data_root, head, branch)
    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        for name in CANONICAL_FILES:
            _write_bytes(output_dir / name, artifacts[name])
    except Exception:
        for child in output_dir.iterdir():
            if child.is_file():
                child.unlink()
        output_dir.rmdir()
        raise
    return {
        "candidate_count": 24,
        "confirmation_enabled": False,
        "holdout_loaded": False,
        "outcomes_generated": True,
        "output_dir": output_dir.as_posix(),
        "predictors_generated": True,
        "status": "PASS",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run governed Campaign 50 development and validation only."
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = execute(Path(args.data_root), Path(args.output_dir))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
