#!/usr/bin/env python
"""Generate Core v1 robustness grid commands.

This helper writes a PowerShell command file for the canonical walk-forward runner
and a manifest describing the configs. It does not implement a new backtest
engine; every experiment uses scripts/run_multi_strategy_walkforward.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_RUNNER = ROOT / "scripts" / "run_multi_strategy_walkforward.py"


@dataclass(frozen=True)
class GridConfig:
    name: str
    trend_weight: float
    equity_weight: float
    gold_weight: float
    hedge_weight: float
    mr_weight: float = 0.0
    description: str = ""


CONFIGS = (
    GridConfig("baseline_40_35_15_10", 0.40, 0.35, 0.15, 0.10, description="Blessed Core v1 baseline"),
    GridConfig("gold20_35_35_20_10", 0.35, 0.35, 0.20, 0.10, description="Lower trend, higher gold"),
    GridConfig("eq30_gold20_40_30_20_10", 0.40, 0.30, 0.20, 0.10, description="Shift equity into gold"),
    GridConfig("trend45_eq30_45_30_15_10", 0.45, 0.30, 0.15, 0.10, description="Higher trend, lower equity"),
    GridConfig("hedge05_45_35_15_05", 0.45, 0.35, 0.15, 0.05, description="Half hedge, trend-funded"),
    GridConfig("hedge00_50_35_15_00", 0.50, 0.35, 0.15, 0.00, description="No hedge, trend-funded"),
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate Core v1 robustness grid commands")
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--spy-data", required=True)
    p.add_argument("--qqq-data", required=True)
    p.add_argument("--bil-data", required=True)
    p.add_argument("--gld-data", required=True)
    p.add_argument("--data-start", default="2019-01-01")
    p.add_argument("--oos-start", default="2021-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--workers", type=int, default=5)
    p.add_argument("--out-dir", default="artifacts/core_v1_grid")
    p.add_argument("--python", default=sys.executable)
    return p.parse_args()


def _ps_quote(value: str) -> str:
    if not value:
        return "''"
    if any(ch.isspace() for ch in value):
        return "'" + value.replace("'", "''") + "'"
    return value


def _command(args: argparse.Namespace, cfg: GridConfig, cfg_out: Path) -> list[str]:
    return [
        args.python,
        str(CANONICAL_RUNNER),
        "--btc-data", args.btc_data,
        "--eth-data", args.eth_data,
        "--spy-data", args.spy_data,
        "--qqq-data", args.qqq_data,
        "--bil-data", args.bil_data,
        "--gld-data", args.gld_data,
        "--data-start", args.data_start,
        "--oos-start", args.oos_start,
        "--oos-end", args.oos_end,
        "--trend-weight", str(cfg.trend_weight),
        "--equity-weight", str(cfg.equity_weight),
        "--gold-weight", str(cfg.gold_weight),
        "--hedge-weight", str(cfg.hedge_weight),
        "--mr-weight", str(cfg.mr_weight),
        "--workers", str(args.workers),
        "--out-dir", str(cfg_out),
    ]


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "runner": str(CANONICAL_RUNNER),
        "data_start": args.data_start,
        "oos_start": args.oos_start,
        "oos_end": args.oos_end,
        "workers": args.workers,
        "configs": [asdict(cfg) for cfg in CONFIGS],
    }
    (out_dir / "grid_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = [
        "$ErrorActionPreference = 'Stop'",
        "",
    ]
    for cfg in CONFIGS:
        cfg_out = out_dir / cfg.name
        lines.append(f"Write-Host 'Running {cfg.name}'")
        lines.append(" ".join(_ps_quote(part) for part in _command(args, cfg, cfg_out)))
        lines.append("")
    (out_dir / "run_grid.ps1").write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {out_dir / 'grid_manifest.json'}")
    print(f"Wrote {out_dir / 'run_grid.ps1'}")
    print("Run the generated PowerShell file to execute the grid.")


if __name__ == "__main__":
    main()
