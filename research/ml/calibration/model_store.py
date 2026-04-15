"""Persistence layer for PlattCalibrator models.

Models are stored as plain JSON files so they are:
- Auditable and git-diffable (no binary formats).
- Python-version-independent (no pickle).
- Human-readable (A, B are plain floats).

Default storage location: ``artifacts/ml_models/`` relative to the project
root, overridable via the ``ML_MODELS_DIR`` environment variable.

File naming convention:
  ``calibrator_{strategy_id}.json``        (latest version)
  ``calibrator_{strategy_id}_{version}.json``  (versioned snapshot)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from research.ml.calibration.platt_calibrator import PlattCalibrator


# ── Default path ─────────────────────────────────────────────────────────────

def _default_models_dir() -> Path:
    env = os.getenv("ML_MODELS_DIR")
    if env:
        return Path(env)
    # Resolve relative to this file's project root (3 parents up from research/ml/calibration/)
    here = Path(__file__).resolve()
    project_root = here.parent.parent.parent.parent  # research/ml/calibration → project root
    return project_root / "artifacts" / "ml_models"


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _calibrator_to_dict(cal: PlattCalibrator) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "calibration_method": cal.calibration_method,
        "strategy_id": cal.strategy_id,
        "model_version": cal.model_version,
        "A": cal.A,
        "B": cal.B,
        "n_samples": cal.n_samples,
        "is_fitted": cal.is_fitted,
        "trained_at": cal.trained_at,
        "feature_names": cal.feature_names,
        "weights": cal.weights,
        "_isotonic_xs": cal._isotonic_xs,
        "_isotonic_ys": cal._isotonic_ys,
    }


def _calibrator_from_dict(d: dict[str, Any]) -> PlattCalibrator:
    return PlattCalibrator(
        A=float(d.get("A", 1.0)),
        B=float(d.get("B", 0.0)),
        strategy_id=str(d.get("strategy_id", "")),
        model_version=str(d.get("model_version", "")),
        n_samples=int(d.get("n_samples", 0)),
        is_fitted=bool(d.get("is_fitted", False)),
        calibration_method=str(d.get("calibration_method", "platt")),
        trained_at=str(d.get("trained_at", "")),
        feature_names=list(d.get("feature_names", [])),
        weights=list(d.get("weights", [])),
        _isotonic_xs=list(d.get("_isotonic_xs", [])),
        _isotonic_ys=list(d.get("_isotonic_ys", [])),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def save_calibrator(
    calibrator: PlattCalibrator,
    strategy_id: str | None = None,
    version: str | None = None,
    models_dir: Path | str | None = None,
    training_summary: dict[str, Any] | None = None,
) -> Path:
    """Persist a calibrator to JSON.

    Parameters
    ----------
    calibrator :
        Fitted (or unfitted) PlattCalibrator to save.
    strategy_id :
        Overrides ``calibrator.strategy_id`` if provided.
    version :
        Overrides ``calibrator.model_version`` if provided.
    models_dir :
        Directory to write into.  Defaults to ``artifacts/ml_models/``.
    training_summary :
        Optional dict of quality metrics to embed in the JSON for diagnostics.

    Returns
    -------
    Path
        Absolute path of the file written.
    """
    sid = strategy_id or calibrator.strategy_id or "unknown"
    ver = version or calibrator.model_version or "unversioned"
    target_dir = Path(models_dir) if models_dir else _default_models_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    data = _calibrator_to_dict(calibrator)
    if training_summary:
        data["training_summary"] = training_summary

    # Write versioned copy
    versioned_path = target_dir / f"calibrator_{sid}_{ver}.json"
    with open(versioned_path, "w") as f:
        json.dump(data, f, indent=2)

    # Atomically update the "latest" pointer
    latest_path = target_dir / f"calibrator_{sid}.json"
    with open(latest_path, "w") as f:
        json.dump(data, f, indent=2)

    return latest_path


def load_calibrator(
    strategy_id: str,
    version: str = "latest",
    models_dir: Path | str | None = None,
) -> PlattCalibrator | None:
    """Load a calibrator from JSON.

    Returns ``None`` if the model file does not exist — callers should treat
    a ``None`` result as "use passthrough / heuristic confidence."

    Parameters
    ----------
    strategy_id :
        Strategy identifier (matches the name used when saving).
    version :
        ``"latest"`` (default) loads the most recent file; any other string
        loads ``calibrator_{strategy_id}_{version}.json``.
    models_dir :
        Directory to search.  Defaults to ``artifacts/ml_models/``.
    """
    target_dir = Path(models_dir) if models_dir else _default_models_dir()

    if version == "latest":
        path = target_dir / f"calibrator_{strategy_id}.json"
    else:
        path = target_dir / f"calibrator_{strategy_id}_{version}.json"

    if not path.exists():
        return None

    with open(path) as f:
        data = json.load(f)

    return _calibrator_from_dict(data)


def list_model_versions(
    strategy_id: str,
    models_dir: Path | str | None = None,
) -> list[str]:
    """Return a sorted list of version tags available for a strategy."""
    target_dir = Path(models_dir) if models_dir else _default_models_dir()
    if not target_dir.exists():
        return []

    prefix = f"calibrator_{strategy_id}_"
    versions = []
    for p in target_dir.iterdir():
        name = p.name
        if name.startswith(prefix) and name.endswith(".json"):
            ver = name[len(prefix) : -len(".json")]
            versions.append(ver)

    return sorted(versions)
