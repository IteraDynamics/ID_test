"""Runtime state persistence — JSON-backed live state for the Argus runtime.

Persists:
- Current position and exposure.
- High-water mark and drawdown governor state.
- Last known NAV and bar timestamp.
- Fill history summary.

Rules:
- Only the runtime layer writes to this file.
- Research/backtest code never touches it.
- Load is fail-safe: missing or corrupt file → fresh state.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path(os.getenv("RUNTIME_STATE_PATH", "runtime/argus/state/live_state.json"))


@dataclass
class RuntimeState:
    """Persisted runtime state.

    Attributes
    ----------
    asset : str
    position_units : float
    cash : float
    nav : float
    exposure_frac : float
    high_water_mark : float | None
    drawdown_governor_halted : bool
    last_bar_timestamp : str
    last_updated : str
    fill_count : int
    meta : dict
    """

    asset: str = "BTC"
    position_units: float = 0.0
    cash: float = 0.0
    nav: float = 0.0
    exposure_frac: float = 0.0
    high_water_mark: float | None = None
    drawdown_governor_halted: bool = False
    last_bar_timestamp: str = ""
    last_updated: str = ""
    fill_count: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    # ── Persistence ────────────────────────────────────────────────────────────

    def save(self, path: Path | str | None = None) -> Path:
        """Persist state to JSON.  Returns the path written."""
        out_path = Path(path or DEFAULT_STATE_PATH)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_updated = datetime.utcnow().isoformat()
        data = asdict(self)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        log.debug("RuntimeState saved to %s", out_path)
        return out_path

    @classmethod
    def load(cls, path: Path | str | None = None) -> "RuntimeState":
        """Load state from JSON.  Returns fresh state if file missing/corrupt."""
        load_path = Path(path or DEFAULT_STATE_PATH)
        if not load_path.exists():
            log.info("No state file at %s — starting fresh.", load_path)
            return cls()
        try:
            with open(load_path, encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: data.get(k, v) for k, v in asdict(cls()).items()})
        except Exception as exc:
            log.warning("Failed to load state from %s: %s — starting fresh.", load_path, exc)
            return cls()

    def update_from_broker(
        self,
        asset: str,
        position_units: float,
        cash: float,
        nav: float,
        exposure_frac: float,
        bar_timestamp: str,
    ) -> None:
        """Update state from a fresh broker snapshot."""
        self.asset = asset
        self.position_units = position_units
        self.cash = cash
        self.nav = nav
        self.exposure_frac = exposure_frac
        self.last_bar_timestamp = bar_timestamp

        if self.high_water_mark is None or nav > self.high_water_mark:
            self.high_water_mark = nav

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
