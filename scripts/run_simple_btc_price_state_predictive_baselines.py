#!/usr/bin/env python3
"""Governed runner for Campaign #48 BTC price-state predictive baselines."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.ml.validation.simple_btc_price_state_predictive_baselines import (  # noqa: E402
    DEFAULT_CONTRACT,
    OUTPUT_FILENAMES,
    build_output_texts,
    json_text,
    load_source,
    preflight,
    sha256_file,
    validate_output_directory,
    write_lf,
)

DEFAULT_OUTPUT_DIR = Path("artifacts/simple_btc_price_state_predictive_baselines")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(DEFAULT_CONTRACT.source_path))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    return parser.parse_args()


def _terminal(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def _publish_atomic(stage: Path, destination: Path, replace_existing: bool) -> None:
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()) and not replace_existing:
        raise RuntimeError("refusing to overwrite nonempty canonical directory without --replace-existing")
    backup: Path | None = None
    try:
        if destination.exists():
            backup = destination.with_name(destination.name + ".replacement-backup")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(destination, backup)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, destination)
        if backup is not None:
            shutil.rmtree(backup)
    except Exception:
        if destination.exists() and backup is not None:
            shutil.rmtree(destination)
        if backup is not None and backup.exists():
            os.replace(backup, destination)
        raise


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    output_dir = args.output_dir.resolve()
    try:
        preflight_payload = preflight(source)
        if args.preflight_only:
            _terminal(preflight_payload)
            return 0

        source_before = sha256_file(source)
        frame = load_source(source)
        texts = build_output_texts(source, frame)
        if tuple(texts) != OUTPUT_FILENAMES:
            raise RuntimeError("canonical output ordering mismatch")

        output_dir.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.stage-", dir=output_dir.parent))
        try:
            for name in OUTPUT_FILENAMES:
                write_lf(stage / name, texts[name])
            validate_output_directory(stage)
            if sha256_file(source) != source_before:
                raise RuntimeError("governed source bytes changed during generation")
            _publish_atomic(stage, output_dir, args.replace_existing)
        finally:
            if stage.exists():
                shutil.rmtree(stage)

        _terminal({
            "status": "PASS",
            "output_dir": str(args.output_dir.as_posix()),
            "canonical_file_count": len(OUTPUT_FILENAMES),
            "predictive_outcomes_generated": True,
            "source_sha256": source_before,
        })
        return 0
    except Exception as exc:
        _terminal({
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "predictive_outcomes_generated": False if args.preflight_only else None,
        })
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
