from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_STATUSES = {"CANDIDATE", "CHAMPION", "RETIRED", "REJECTED"}


@dataclass(frozen=True)
class ChampionRecord:
    experiment_id: str
    candidate_id: str
    status: str
    asset: str
    timeframe: str
    target: str
    model: str
    feature_set: str
    horizon_bars: int
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    validation: dict[str, Any]
    source_artifacts: dict[str, str]
    hypothesis: str
    notes: list[str] = field(default_factory=list)
    registered_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    registry_version: str = "v1"

    def canonical_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parameters"] = _normalize(self.parameters)
        payload["metrics"] = _normalize(self.metrics)
        payload["validation"] = _normalize(self.validation)
        payload["source_artifacts"] = _normalize(self.source_artifacts)
        payload["notes"] = _normalize(self.notes)
        return payload

    def digest(self) -> str:
        payload = self.canonical_payload().copy()
        payload.pop("registered_at_utc", None)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


class ChampionRegistry:
    """Append-only filesystem registry for audited research candidates.

    Each candidate is written to an immutable record file. A compact index is
    rebuilt atomically after every registration for easy inspection and future
    dashboard use.
    """

    def __init__(self, root: str | Path = "artifacts/research_engine_v1/registry") -> None:
        self.root = Path(root)
        self.records_dir = self.root / "records"
        self.index_path = self.root / "champion_index.json"

    def register(self, record: ChampionRecord) -> Path:
        if record.status not in VALID_STATUSES:
            raise ValueError(f"Unsupported registry status {record.status!r}; expected one of {sorted(VALID_STATUSES)}")
        if not record.experiment_id.strip() or not record.candidate_id.strip():
            raise ValueError("experiment_id and candidate_id are required")

        self.records_dir.mkdir(parents=True, exist_ok=True)
        path = self.records_dir / f"{_slug(record.experiment_id)}__{_slug(record.candidate_id)}__{record.digest()}.json"
        if path.exists():
            return path

        payload = record.canonical_payload()
        payload["record_digest"] = record.digest()
        _atomic_write_json(path, payload)
        self.rebuild_index()
        return path

    def list_records(self) -> list[dict[str, Any]]:
        if not self.records_dir.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(self.records_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["record_path"] = str(path)
            rows.append(payload)
        return rows

    def rebuild_index(self) -> Path:
        rows = self.list_records()
        rows.sort(key=lambda row: (row.get("experiment_id", ""), row.get("asset", ""), row.get("candidate_id", "")))
        summary = {
            "registry_version": "v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "records": rows,
            "counts": {
                "total": len(rows),
                **{status.lower(): sum(1 for row in rows if row.get("status") == status) for status in sorted(VALID_STATUSES)},
            },
        }
        self.root.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.index_path, summary)
        return self.index_path


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    temp.replace(path)


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _slug(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in cleaned.split("-") if part) or "unnamed"
