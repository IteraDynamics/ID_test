from __future__ import annotations

"""Deterministic, read-only provider for frozen Jump Risk replay scores.

The provider loads the historical replay artifact and serves the latest score
whose decision timestamp is not later than the requested runtime timestamp.
It never trains models, writes files, mutates Core state, or creates orders.
"""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from runtime.core_v1.jump_risk_overlay import MODEL_NAMES, ProbabilityInput, SUPPORTED_ASSETS

PROVIDER_VERSION = "core_v1_jump_risk_replay_provider_v1"


def _as_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


@dataclass(frozen=True)
class ReplayLookup:
    asset: str
    requested_at: datetime
    score_decision_at: datetime | None
    probabilities: Mapping[str, ProbabilityInput] | None
    reason_code: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "requested_at": self.requested_at.isoformat(),
            "score_decision_at": self.score_decision_at.isoformat() if self.score_decision_at else None,
            "reason_code": self.reason_code,
            "probabilities": None
            if self.probabilities is None
            else {
                name: {
                    "probability": value.probability,
                    "threshold": value.threshold,
                    "source_bar_ts": value.source_bar_ts.isoformat(),
                    "computed_at": value.computed_at.isoformat(),
                }
                for name, value in self.probabilities.items()
            },
        }


class ReplayProbabilityProvider:
    """Serve deterministic as-of replay probabilities without future leakage."""

    def __init__(self, report: Mapping[str, Any], *, verify_digests: bool = True) -> None:
        self.version = str(report.get("version", ""))
        self.replay_digest = str(report.get("replay_digest", ""))
        self.overlay_config_fingerprint = str(report.get("overlay_config_fingerprint", ""))
        self._rows: dict[str, list[dict[str, Any]]] = {}
        self._times: dict[str, list[datetime]] = {}

        assets = report.get("assets")
        if not isinstance(assets, Mapping):
            raise ValueError("Replay report is missing assets")

        for asset in sorted(SUPPORTED_ASSETS):
            block = assets.get(asset)
            if not isinstance(block, Mapping):
                raise ValueError(f"Replay report is missing asset block: {asset}")
            raw_rows = block.get("decisions")
            if not isinstance(raw_rows, list) or not raw_rows:
                raise ValueError(f"Replay report has no decisions for {asset}")

            normalized: list[dict[str, Any]] = []
            previous: datetime | None = None
            for raw in raw_rows:
                if not isinstance(raw, Mapping):
                    raise ValueError(f"Malformed decision row for {asset}")
                decision_at = _as_utc(str(raw["decision_at"]))
                source_bar_ts = _as_utc(str(raw["source_bar_ts"]))

                # Validate the replay sequence first. A duplicated or regressed
                # decision timestamp is the primary structural defect even when
                # that mutation also makes the associated source bar non-historical.
                if previous is not None and decision_at <= previous:
                    raise ValueError(f"Replay timestamps must be unique and increasing for {asset}")
                if source_bar_ts >= decision_at:
                    raise ValueError(f"Non-historical source bar for {asset} at {decision_at.isoformat()}")
                previous = decision_at

                row = {
                    "decision_at": decision_at,
                    "source_bar_ts": source_bar_ts,
                    "medium_up_probability": float(raw["medium_up_probability"]),
                    "medium_up_threshold": float(raw["medium_up_threshold"]),
                    "extended_up_probability": float(raw["extended_up_probability"]),
                    "extended_up_threshold": float(raw["extended_up_threshold"]),
                }
                normalized.append(row)

            if verify_digests:
                canonical_rows = [
                    {
                        **raw,
                        "decision_at": _as_utc(str(raw["decision_at"])).isoformat(),
                        "source_bar_ts": _as_utc(str(raw["source_bar_ts"])).isoformat(),
                    }
                    for raw in raw_rows
                ]
                expected = str(block.get("decision_digest", ""))
                actual = _digest(canonical_rows)
                if expected and actual != expected:
                    raise ValueError(f"Replay decision digest mismatch for {asset}")

            self._rows[asset] = normalized
            self._times[asset] = [row["decision_at"] for row in normalized]

    @classmethod
    def from_path(cls, path: str | Path, *, verify_digests: bool = True) -> "ReplayProbabilityProvider":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("Replay artifact root must be an object")
        return cls(payload, verify_digests=verify_digests)

    def lookup(self, asset: str, decision_at: datetime) -> ReplayLookup:
        normalized_asset = str(asset).upper().strip()
        requested_at = _as_utc(decision_at)
        if normalized_asset not in SUPPORTED_ASSETS:
            return ReplayLookup(normalized_asset, requested_at, None, None, "UNSUPPORTED_ASSET")

        position = bisect_right(self._times[normalized_asset], requested_at) - 1
        if position < 0:
            return ReplayLookup(normalized_asset, requested_at, None, None, "NO_SCORE_AS_OF_TIME")

        row = self._rows[normalized_asset][position]
        score_at = row["decision_at"]
        if score_at > requested_at:
            raise RuntimeError("Provider selected a future score")

        probabilities = {
            name: ProbabilityInput(
                probability=row[f"{name}_probability"],
                threshold=row[f"{name}_threshold"],
                source_bar_ts=row["source_bar_ts"],
                computed_at=score_at,
            )
            for name in MODEL_NAMES
        }
        return ReplayLookup(normalized_asset, requested_at, score_at, probabilities, "SCORE_FOUND")

    def get(self, asset: str, decision_at: datetime) -> Mapping[str, ProbabilityInput] | None:
        return self.lookup(asset, decision_at).probabilities

    def lookup_digest(self, asset: str, decision_at: datetime) -> str:
        return _digest(self.lookup(asset, decision_at).to_dict())