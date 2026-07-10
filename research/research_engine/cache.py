from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd


@dataclass(frozen=True)
class CacheKey:
    namespace: str
    asset: str
    timeframe: str
    dataset_fingerprint: str
    parameters: dict[str, Any]
    version: str = "v1"

    def canonical_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parameters"] = _normalize(self.parameters)
        return payload

    def digest(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    def slug(self) -> str:
        return f"{_slug(self.asset)}_{_slug(self.timeframe)}_{self.digest()}"


class ResearchCache:
    """Filesystem cache for deterministic research datasets and metadata.

    Cache entries are immutable by key. A changed dataset fingerprint, parameter,
    namespace, timeframe, asset, or version produces a new location.
    """

    def __init__(self, root: str | Path = "artifacts/research_engine_v1/cache") -> None:
        self.root = Path(root)

    def entry_dir(self, key: CacheKey) -> Path:
        return self.root / _slug(key.namespace) / key.slug()

    def data_path(self, key: CacheKey) -> Path:
        return self.entry_dir(key) / "frame.parquet"

    def metadata_path(self, key: CacheKey) -> Path:
        return self.entry_dir(key) / "metadata.json"

    def exists(self, key: CacheKey) -> bool:
        return self.data_path(key).exists() and self.metadata_path(key).exists()

    def load_frame(self, key: CacheKey) -> pd.DataFrame:
        if not self.exists(key):
            raise FileNotFoundError(f"Research cache miss: {key.namespace}/{key.slug()}")
        return pd.read_parquet(self.data_path(key))

    def store_frame(
        self,
        key: CacheKey,
        frame: pd.DataFrame,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        entry = self.entry_dir(key)
        entry.mkdir(parents=True, exist_ok=True)
        data_path = self.data_path(key)
        metadata_path = self.metadata_path(key)

        if data_path.exists() or metadata_path.exists():
            raise FileExistsError(
                f"Refusing to overwrite immutable research cache entry: {entry}"
            )

        frame.to_parquet(data_path)
        payload = {
            "cache_key": key.canonical_payload(),
            "cache_digest": key.digest(),
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "index_name": frame.index.name,
            "metadata": _normalize(metadata or {}),
        }
        _atomic_write_json(metadata_path, payload)
        return entry

    def get_or_build_frame(
        self,
        key: CacheKey,
        builder: Callable[[], pd.DataFrame],
        metadata: dict[str, Any] | None = None,
    ) -> tuple[pd.DataFrame, bool]:
        if self.exists(key):
            return self.load_frame(key), True
        frame = builder()
        self.store_frame(key, frame, metadata=metadata)
        return frame, False


def fingerprint_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
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
