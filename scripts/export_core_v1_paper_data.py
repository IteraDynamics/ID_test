#!/usr/bin/env python
"""Export Core v1 paper-runtime observability data for local replay/comparison.

Gathers the exact market data, signals, fills, state, and (if present) audit
report the live paper runtime observed, and writes them to a self-contained
export directory: raw JSONL/JSON copies plus normalized CSVs, alongside a
manifest describing provenance (source paths, row counts, git commit/branch,
runtime version, and any warnings).

This is an observability/export tool only. It does not read or modify
strategy, allocation, or execution logic, and it never fabricates data —
if a required log is missing, the export fails clearly instead of writing
a partial or fake export.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "1.0.0"

REQUIRED_LOGS = ("market_data_log", "signals_log", "fills_log")


def default_paths() -> dict[str, Path]:
    state_path = Path(os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
    signals_log = Path(os.getenv("CORE_V1_SIGNALS_LOG", "/opt/itera/logs/core_v1_signals.jsonl"))
    return {
        "state_path": state_path,
        "signals_log": signals_log,
        "fills_log": Path(os.getenv("CORE_V1_FILLS_LOG", "/opt/itera/logs/core_v1_fills.jsonl")),
        "market_data_log": Path(os.getenv("CORE_V1_MARKET_DATA_LOG", "/opt/itera/logs/core_v1_market_data.jsonl")),
        "errors_log": signals_log.with_name("core_v1_errors.jsonl"),
        "audit_report_path": Path(os.getenv("CORE_V1_AUDIT_REPORT_PATH", str(state_path.with_name("core_v1_audit_report.json")))),
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> int:
    """Write rows to CSV. Nested dict/list values are serialized as JSON text
    so the CSV stays flat and portable. Returns the row count written."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            clean = {}
            for key in fieldnames:
                value = row.get(key)
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, default=str, sort_keys=True)
                clean[key] = value
            writer.writerow(clean)
    return len(rows)


def flatten_signal_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten per-cycle signal events into one row per (cycle, sleeve) decision."""
    rows: list[dict[str, Any]] = []
    for event in events:
        event_ctx = {
            "event_timestamp": event.get("timestamp"),
            "cycle": event.get("cycle"),
            "total_nav": event.get("total_nav"),
            "drawdown_frac": event.get("drawdown_frac"),
        }
        for sig in event.get("signals", []):
            row = dict(event_ctx)
            row.update(sig)
            rows.append(row)
    return rows


def git_info(repo_root: Path) -> tuple[str | None, str | None]:
    """Best-effort git commit/branch lookup. Never fabricates — returns None
    on any failure (not a repo, git unavailable, detached HEAD edge cases)."""
    commit = None
    branch = None
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=10
        ).decode().strip()
    except Exception:
        pass
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=10
        ).decode().strip()
    except Exception:
        pass
    return commit or None, branch or None


def validate_required(paths: dict[str, Path]) -> list[str]:
    missing = []
    for key in (*REQUIRED_LOGS, "state_path"):
        if not paths[key].exists():
            missing.append(f"{key}: {paths[key]}")
    return missing


def build_manifest(
    *,
    export_dir: Path,
    paths: dict[str, Path],
    dest: dict[str, Path],
    row_counts: dict[str, int],
    state: dict[str, Any],
    audit_report: dict[str, Any] | None,
    repo_root: Path,
    warnings: list[str],
) -> dict[str, Any]:
    commit, branch = git_info(repo_root)
    return {
        "export_timestamp": datetime.now(UTC).isoformat(),
        "export_script_version": SCRIPT_VERSION,
        "export_dir": str(export_dir),
        "sources": {key: str(path) for key, path in paths.items()},
        "destinations": {key: str(path) for key, path in dest.items()},
        "row_counts": row_counts,
        "state_snapshot_path": str(dest["state_path"]) if "state_path" in dest else None,
        "audit_report_path": str(dest["audit_report_path"]) if audit_report is not None else None,
        "git_commit": commit,
        "git_branch": branch,
        "runtime_version": state.get("version"),
        "required_logs_present": {key: paths[key].exists() for key in (*REQUIRED_LOGS, "state_path")},
        "optional_logs_present": {
            "errors_log": paths["errors_log"].exists(),
            "audit_report": paths["audit_report_path"].exists(),
        },
        "warnings": warnings,
    }


def run_export(args: argparse.Namespace) -> Path:
    paths = {
        "state_path": Path(args.state_path),
        "signals_log": Path(args.signals_log),
        "fills_log": Path(args.fills_log),
        "market_data_log": Path(args.market_data_log),
        "errors_log": Path(args.errors_log),
        "audit_report_path": Path(args.audit_report_path),
    }

    missing = validate_required(paths)
    if missing:
        raise SystemExit(
            "Core v1 export aborted — required source(s) not found (no export was written):\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    export_dir = Path(args.output_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    dest: dict[str, Path] = {}
    row_counts: dict[str, int] = {}

    market_data_rows = read_jsonl(paths["market_data_log"])
    signals_events = read_jsonl(paths["signals_log"])
    fills_rows = read_jsonl(paths["fills_log"])
    signal_rows = flatten_signal_events(signals_events)

    if not market_data_rows:
        warnings.append("market_data_log exists but contains zero parseable rows")
    if not signals_events:
        warnings.append("signals_log exists but contains zero parseable rows")
    if not fills_rows:
        warnings.append("fills_log exists but contains zero fills recorded yet")

    dest["market_data_jsonl"] = export_dir / "market_data.jsonl"
    shutil.copy2(paths["market_data_log"], dest["market_data_jsonl"])
    dest["signals_jsonl"] = export_dir / "signals.jsonl"
    shutil.copy2(paths["signals_log"], dest["signals_jsonl"])
    dest["fills_jsonl"] = export_dir / "fills.jsonl"
    shutil.copy2(paths["fills_log"], dest["fills_jsonl"])

    dest["market_data_csv"] = export_dir / "market_data.csv"
    row_counts["market_data"] = write_csv(market_data_rows, dest["market_data_csv"])
    dest["signals_csv"] = export_dir / "signals.csv"
    row_counts["signals"] = write_csv(signal_rows, dest["signals_csv"])
    dest["fills_csv"] = export_dir / "fills.csv"
    row_counts["fills"] = write_csv(fills_rows, dest["fills_csv"])

    state = json.loads(paths["state_path"].read_text(encoding="utf-8"))
    dest["state_path"] = export_dir / "state.json"
    shutil.copy2(paths["state_path"], dest["state_path"])

    audit_report: dict[str, Any] | None = None
    if paths["audit_report_path"].exists():
        try:
            audit_report = json.loads(paths["audit_report_path"].read_text(encoding="utf-8"))
            dest["audit_report_path"] = export_dir / "audit_report.json"
            shutil.copy2(paths["audit_report_path"], dest["audit_report_path"])
        except Exception as e:
            warnings.append(f"audit_report_path present but unreadable: {e}")
    else:
        warnings.append("audit_report_path not found — audit report omitted (not fabricated)")

    if paths["errors_log"].exists():
        errors_rows = read_jsonl(paths["errors_log"])
        dest["errors_jsonl"] = export_dir / "errors.jsonl"
        shutil.copy2(paths["errors_log"], dest["errors_jsonl"])
        row_counts["errors"] = len(errors_rows)
    else:
        warnings.append("errors_log not found — omitted (not fabricated)")

    row_counts["market_data_rows_parsed"] = len(market_data_rows)
    row_counts["signals_events_parsed"] = len(signals_events)
    row_counts["signals_rows_flattened"] = len(signal_rows)
    row_counts["fills_rows_parsed"] = len(fills_rows)

    repo_root = Path(__file__).resolve().parent.parent
    manifest = build_manifest(
        export_dir=export_dir,
        paths=paths,
        dest=dest,
        row_counts=row_counts,
        state=state,
        audit_report=audit_report,
        repo_root=repo_root,
        warnings=warnings,
    )
    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")

    return export_dir


def parse_args() -> argparse.Namespace:
    defaults = default_paths()
    p = argparse.ArgumentParser(description="Export Core v1 paper runtime data for local replay/comparison against research backtests")
    p.add_argument("--output-dir", default=str(Path("artifacts/core_v1_paper_export") / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")))
    p.add_argument("--state-path", default=str(defaults["state_path"]))
    p.add_argument("--signals-log", default=str(defaults["signals_log"]))
    p.add_argument("--fills-log", default=str(defaults["fills_log"]))
    p.add_argument("--market-data-log", default=str(defaults["market_data_log"]))
    p.add_argument("--errors-log", default=str(defaults["errors_log"]))
    p.add_argument("--audit-report-path", default=str(defaults["audit_report_path"]))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    export_dir = run_export(args)
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
    print(f"Core v1 paper data exported to {export_dir}")
    print(f"  market data rows: {manifest['row_counts']['market_data_rows_parsed']}")
    print(f"  signal events:    {manifest['row_counts']['signals_events_parsed']} ({manifest['row_counts']['signals_rows_flattened']} sleeve decisions)")
    print(f"  fills:            {manifest['row_counts']['fills_rows_parsed']}")
    print(f"  audit report:     {'included' if manifest['optional_logs_present']['audit_report'] else 'absent'}")
    print(f"  errors log:       {'included' if manifest['optional_logs_present']['errors_log'] else 'absent'}")
    if manifest["warnings"]:
        print("Warnings:", file=sys.stderr)
        for w in manifest["warnings"]:
            print(f"  - {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
