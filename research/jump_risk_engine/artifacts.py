from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def slugify(value: str) -> str:
    cleaned = []
    for ch in value.lower().strip():
        if ch.isalnum():
            cleaned.append(ch)
        elif ch in {"-", "_", "."}:
            cleaned.append(ch)
        else:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-_.")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "run"


def make_run_dir(base_dir: str | Path, experiment: str, cfg: Any, run_name: str | None = None) -> Path:
    """Create a unique run-specific artifact directory.

    Layout:
      artifacts/jump_risk_engine_v0/<experiment>/<timestamp>_<asset>_h<horizon>_<run-name>/

    This intentionally avoids overwriting prior research outputs as the lab
    iterates through feature sets, labels, assets, and horizons.
    """
    base = Path(base_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cfg_dict = asdict(cfg) if is_dataclass(cfg) else dict(getattr(cfg, "__dict__", {}))
    asset = slugify(str(cfg_dict.get("asset", "asset")))
    horizon = cfg_dict.get("horizon_bars", "h")
    suffix_parts = [asset, f"h{horizon}"]
    if run_name:
        suffix_parts.append(slugify(run_name))
    dirname = f"{timestamp}_{'_'.join(suffix_parts)}"
    out = base / slugify(experiment) / dirname
    candidate = out
    for i in range(1, 100):
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            candidate = out.with_name(f"{out.name}_{i:02d}")
    raise FileExistsError(f"Could not create unique artifact directory under {base}")
