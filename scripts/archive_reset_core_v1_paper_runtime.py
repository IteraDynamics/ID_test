#!/usr/bin/env python
"""Archive-and-reset utility for a contaminated Core v1 paper runtime.

The forensic state replay audit (audit_core_v1_state_replay.py) found that
the live state.json cannot be reproduced by a clean replay from initial
capital — the runtime, audit, and dashboard logic may now be fixed, but the
existing state/log history was generated while they weren't, and should not
be treated as a valid observation period going forward.

This script does not decide that for you and does not touch strategy,
execution, runtime, or dashboard logic. It is purely an operator safety
tool: it archives every piece of contaminated evidence to a timestamped,
never-overwritten directory (with a manifest proving exactly what was
archived, including sha256 hashes), and only then — and only if explicitly
told to with --confirm-reset — clears the active runtime/log files so the
next paper-runtime start initializes cleanly from initial capital.

Default mode is a strictly read-only dry run: nothing is created, moved, or
deleted unless --confirm-reset is passed. Even in --confirm-reset mode, an
active file is never removed until its archive copy has been verified
byte-for-byte (via sha256) — if verification fails for any file, the whole
run aborts before anything active is touched.

This script never starts, stops, or restarts any service. It only prints
the systemctl commands an operator should run manually afterward.
"""

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
import os
import shlex
import shutil
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Keep standalone script execution working until the separate packaging migration.


REPO_ROOT = Path(__file__).resolve().parent.parent

RUNTIME_AND_LOG_TARGETS = [
    ("runtime", "state_path"),
    ("runtime", "audit_report_path"),
    ("logs", "signals_path"),
    ("logs", "fills_path"),
    ("logs", "market_data_path"),
    ("logs", "errors_path"),
]
ARTIFACT_TARGET_NAMES = [
    "core_v1_paper_export",
    "core_v1_replay_reports",
    "core_v1_accounting_report.json",
    "core_v1_accounting_report.csv",
    "core_v1_state_replay_audit.json",
    "core_v1_state_replay_audit.csv",
]


def sha256_file(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=hashlib.sha256)


def sha256_dir(path: Path) -> str:
    """A stable, order-independent hash of every file in a directory tree,
    good enough to prove "this archived copy matches this source tree"
    without needing a separate mechanism from the single-file case."""
    h = hashlib.sha256()
    for rel in sorted(str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()):
        h.update(rel.encode("utf-8"))
        h.update(sha256_file(path / rel).encode("utf-8"))
    return h.hexdigest()


def get_git_branch() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def get_git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def get_hostname() -> str | None:
    try:
        return socket.gethostname()
    except Exception:
        return None


def build_targets(args: argparse.Namespace) -> dict[str, Path]:
    state_path = Path(args.state_path)
    logs_dir = Path(args.logs_dir)
    artifacts_dir = Path(args.artifacts_dir)
    return {
        "state_path": state_path,
        "audit_report_path": state_path.parent / "core_v1_audit_report.json",
        "signals_path": logs_dir / "core_v1_signals.jsonl",
        "fills_path": logs_dir / "core_v1_fills.jsonl",
        "market_data_path": logs_dir / "core_v1_market_data.jsonl",
        "errors_path": logs_dir / "core_v1_errors.jsonl",
        **{name: artifacts_dir / name for name in ARTIFACT_TARGET_NAMES},
    }


def describe_entry(category: str, name: str, source: Path, dest_root: Path) -> dict[str, Any]:
    existed = source.exists()
    is_dir = source.is_dir() if existed else None
    entry: dict[str, Any] = {
        "category": category,
        "name": name,
        "source": str(source),
        "existed": existed,
        "is_dir": is_dir,
        "size_bytes": None,
        "sha256": None,
        "destination": None,
        "archived": False,
        "removed_from_active": False,
    }
    if not existed:
        return entry
    dest = dest_root / category / name
    entry["destination"] = str(dest)
    if is_dir:
        total_size = sum(p.stat().st_size for p in source.rglob("*") if p.is_file())
        entry["size_bytes"] = total_size
        entry["sha256"] = sha256_dir(source)
    else:
        entry["size_bytes"] = source.stat().st_size
        entry["sha256"] = sha256_file(source)
    return entry


def resolve_archive_destination(archive_root: Path, timestamp: str) -> Path:
    candidate = archive_root / timestamp
    if not candidate.exists():
        return candidate
    for suffix in range(2, 21):
        candidate = archive_root / f"{timestamp}-{suffix}"
        if not candidate.exists():
            return candidate
    raise SystemExit(f"could not find a free archive destination under {archive_root} for timestamp {timestamp} after 20 attempts")


def copy_and_verify(entry: dict[str, Any], source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if entry["is_dir"]:
        shutil.copytree(source, dest)
        verified_hash = sha256_dir(dest)
    else:
        shutil.copy2(source, dest)
        verified_hash = sha256_file(dest)
    if verified_hash != entry["sha256"]:
        raise SystemExit(
            f"ARCHIVE VERIFICATION FAILED for {source} -> {dest}: source sha256={entry['sha256']} but archived copy sha256={verified_hash}. "
            "Aborting before touching any active file — nothing has been deleted."
        )


def remove_active(source: Path, is_dir: bool) -> None:
    if is_dir:
        shutil.rmtree(source)
    else:
        source.unlink()


def build_reset_command(args: argparse.Namespace) -> str:
    parts = [sys.executable, str(Path(__file__).resolve()), "--confirm-reset"]
    if args.reason:
        parts += ["--reason", shlex.quote(args.reason)]
    if args.phantom_nav is not None:
        parts += ["--phantom-nav", str(args.phantom_nav)]
    parts += ["--archive-root", shlex.quote(str(args.archive_root))]
    parts += ["--state-path", shlex.quote(str(args.state_path))]
    parts += ["--logs-dir", shlex.quote(str(args.logs_dir))]
    if str(args.artifacts_dir) != str(REPO_ROOT / "artifacts"):
        parts += ["--artifacts-dir", shlex.quote(str(args.artifacts_dir))]
    return " ".join(parts)


def run(args: argparse.Namespace) -> int:
    warnings: list[str] = []
    targets = build_targets(args)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    if args.confirm_reset:
        archive_dest = resolve_archive_destination(Path(args.archive_root), timestamp)
    else:
        archive_dest = Path(args.archive_root) / timestamp

    entries: list[dict[str, Any]] = []
    for category, key in RUNTIME_AND_LOG_TARGETS:
        entries.append(describe_entry(category, targets[key].name, targets[key], archive_dest))
    for name in ARTIFACT_TARGET_NAMES:
        entries.append(describe_entry("artifacts", name, targets[name], archive_dest))

    existing_runtime_log_entries = [e for e in entries if e["category"] in ("runtime", "logs") and e["existed"]]
    existing_artifact_entries = [e for e in entries if e["category"] == "artifacts" and e["existed"]]
    reset_cmd = build_reset_command(args)

    if not args.confirm_reset:
        print_dry_run(entries, existing_runtime_log_entries, archive_dest, reset_cmd)
        return 0

    if not existing_runtime_log_entries and not existing_artifact_entries:
        warnings.append("nothing found to archive at any configured path — reset would be a no-op")

    archive_dest.mkdir(parents=True, exist_ok=False)
    for sub in ("runtime", "logs", "artifacts"):
        (archive_dest / sub).mkdir(parents=True, exist_ok=True)

    for entry in entries:
        if not entry["existed"]:
            continue
        source = Path(entry["source"])
        dest = Path(entry["destination"])
        copy_and_verify(entry, source, dest)
        entry["archived"] = True

    for entry in entries:
        if entry["category"] not in ("runtime", "logs") or not entry["archived"]:
            continue
        source = Path(entry["source"])
        try:
            remove_active(source, bool(entry["is_dir"]))
            entry["removed_from_active"] = True
        except Exception as e:
            warnings.append(f"archived {source} successfully but could not remove it from the active path: {e}")

    manifest = {
        "archive_timestamp": timestamp,
        "git_branch": get_git_branch(),
        "git_commit": get_git_commit(),
        "hostname": get_hostname(),
        "reset_reason": args.reason,
        "suspected_phantom_nav": args.phantom_nav,
        "mode": "executed",
        "archive_root": str(args.archive_root),
        "archive_destination": str(archive_dest),
        "entries": entries,
        "warnings": warnings,
    }

    # Write once so "manifest exists" is actually true when validate_reset
    # checks for it, then rewrite with the validation results included.
    manifest_path = archive_dest / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")

    validation = validate_reset(entries, archive_dest, targets)
    manifest["validation"] = validation
    warnings.extend(validation["warnings"])
    manifest["warnings"] = warnings
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")

    print_executed(entries, archive_dest, manifest_path, validation)
    return 0 if validation["ok"] else 2


def validate_reset(entries: list[dict[str, Any]], archive_dest: Path, targets: dict[str, Path]) -> dict[str, Any]:
    val_warnings: list[str] = []
    archived_ok = True
    for entry in entries:
        if not entry["archived"]:
            continue
        dest = Path(entry["destination"])
        if not dest.exists():
            archived_ok = False
            val_warnings.append(f"expected archived copy missing: {dest}")

    active_clear = True
    for key in ("state_path", "audit_report_path", "signals_path", "fills_path", "market_data_path", "errors_path"):
        path = targets[key]
        if path.exists():
            active_clear = False
            val_warnings.append(f"active file still present after reset: {path}")

    manifest_path = archive_dest / "manifest.json"
    manifest_present = manifest_path.exists()

    ok = archived_ok and active_clear
    return {
        "ok": ok,
        "archived_files_verified": archived_ok,
        "active_runtime_and_logs_clear": active_clear,
        "manifest_written": manifest_present,
        "warnings": val_warnings,
    }


def print_dry_run(entries: list[dict[str, Any]], existing_runtime_log_entries: list[dict[str, Any]], archive_dest: Path, reset_cmd: str) -> None:
    print("DRY RUN ONLY — nothing has been created, moved, or deleted.")
    print()
    print("Files that would be archived")
    print("-" * 50)
    any_existing = False
    for entry in entries:
        if entry["existed"]:
            any_existing = True
            kind = "dir " if entry["is_dir"] else "file"
            print(f"  [{kind}] {entry['source']}  ({entry['size_bytes']} bytes)")
        else:
            print(f"  [missing, skipped] {entry['source']}")
    if not any_existing:
        print("  (nothing found at any configured path)")
    print()
    print("Files that would be removed from active runtime")
    print("-" * 50)
    if existing_runtime_log_entries:
        for entry in existing_runtime_log_entries:
            print(f"  {entry['source']}")
    else:
        print("  (none found)")
    print()
    print("Archive destination")
    print("-" * 50)
    print(f"  {archive_dest}")
    print()
    print("Exact command to execute reset")
    print("-" * 50)
    print(f"  {reset_cmd}")


def print_executed(entries: list[dict[str, Any]], archive_dest: Path, manifest_path: Path, validation: dict[str, Any]) -> None:
    print("ARCHIVE COMPLETE")
    print("RESET COMPLETE" if validation["ok"] else "RESET INCOMPLETE — see warnings below")
    print()
    print("Archive path")
    print("-" * 50)
    print(f"  {archive_dest}")
    print(f"  manifest: {manifest_path}")
    print()
    print("Files archived")
    print("-" * 50)
    archived = [e for e in entries if e["archived"]]
    if archived:
        for entry in archived:
            print(f"  {entry['source']} -> {entry['destination']}")
    else:
        print("  (none)")
    print()
    print("Files removed from active runtime")
    print("-" * 50)
    removed = [e for e in entries if e["removed_from_active"]]
    if removed:
        for entry in removed:
            print(f"  {entry['source']}")
    else:
        print("  (none)")
    if validation["warnings"]:
        print()
        print("Warnings")
        print("-" * 50)
        for w in validation["warnings"]:
            print(f"  - {w}")
    print()
    print("Next suggested commands:")
    print("  systemctl restart itera-core-v1-paper.service")
    print("  systemctl restart itera-core-v1-audit.service")
    print("  systemctl restart itera-core-v1-dashboard.service")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Archive contaminated Core v1 paper runtime evidence and, with --confirm-reset, reset it to a clean genesis state.")
    p.add_argument("--confirm-reset", action="store_true", help="Actually archive and reset. Without this flag, the script only prints what it would do.")
    p.add_argument("--reason", default=None, help="Free-text reason recorded in the manifest (e.g. why this reset is being performed).")
    p.add_argument("--phantom-nav", type=float, default=None, help="Suspected phantom NAV amount from the state replay audit, recorded in the manifest for the record.")
    p.add_argument("--archive-root", default=os.getenv("CORE_V1_ARCHIVE_ROOT", "/opt/itera/archive/core_v1_paper_runtime"))
    p.add_argument("--state-path", default=os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
    p.add_argument("--logs-dir", default=os.getenv("CORE_V1_LOGS_DIR", "/opt/itera/logs"))
    p.add_argument("--artifacts-dir", default=os.getenv("CORE_V1_ARTIFACTS_DIR", str(REPO_ROOT / "artifacts")))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
