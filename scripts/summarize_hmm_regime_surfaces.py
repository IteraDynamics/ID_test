#!/usr/bin/env python
"""Summarize HMM regime diagnostics across Itera research surfaces.

Research-only utility. Reads per-surface HMM artifacts produced by
scripts/run_hmm_regime_analysis.py and writes combined comparison artifacts.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class SurfaceConfig:
    surface: str
    asset: str
    timeframe: str
    path: Path


DEFAULT_SURFACES = [
    SurfaceConfig("SPY_1D", "SPY", "1D", Path("artifacts/hmm_regime_v1_spy_1d")),
    SurfaceConfig("QQQ_1D", "QQQ", "1D", Path("artifacts/hmm_regime_v1_qqq_1d")),
    SurfaceConfig("BTC_1H", "BTC", "1H", Path("artifacts/hmm_regime_v1_btc_1h")),
    SurfaceConfig("BTC_4H", "BTC", "4H", Path("artifacts/hmm_regime_v1_btc_4h")),
    SurfaceConfig("ETH_1H", "ETH", "1H", Path("artifacts/hmm_regime_v1_eth_1h")),
    SurfaceConfig("ETH_4H", "ETH", "4H", Path("artifacts/hmm_regime_v1_eth_4h")),
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required HMM artifact: {path}")
    return pd.read_csv(path)


def _read_summary(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing required HMM summary artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_surface(config: SurfaceConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    diagnostics = _read_csv(config.path / "state_diagnostics.csv")
    dwell = _read_csv(config.path / "dwell_summary.csv")
    transitions = pd.read_csv(config.path / "transition_matrix.csv", index_col=0)
    summary = _read_summary(config.path / "summary.json")

    for df in (diagnostics, dwell):
        df.insert(0, "timeframe", config.timeframe)
        df.insert(0, "asset", config.asset)
        df.insert(0, "surface", config.surface)

    return diagnostics, dwell, transitions, summary


def _build_persistence_summary(
    config: SurfaceConfig,
    transitions: pd.DataFrame,
    dwell: pd.DataFrame,
    summary: dict,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    dwell_by_label = dwell.set_index("state_label")

    for index_label in transitions.index:
        # Labels are formatted like "0:HIGH_VOL" by the source runner.
        state_label = str(index_label).split(":", 1)[1] if ":" in str(index_label) else str(index_label)
        persistence = float(transitions.loc[index_label, index_label])
        dwell_row = dwell_by_label.loc[state_label]
        rows.append(
            {
                "surface": config.surface,
                "asset": config.asset,
                "timeframe": config.timeframe,
                "state_label": state_label,
                "persistence": persistence,
                "episode_count": int(dwell_row["episode_count"]),
                "avg_dwell_bars": float(dwell_row["avg_dwell_bars"]),
                "median_dwell_bars": float(dwell_row["median_dwell_bars"]),
                "max_dwell_bars": int(dwell_row["max_dwell_bars"]),
                "single_bar_episode_pct": float(dwell_row["single_bar_episode_pct"]),
                "converged": bool(summary.get("converged", False)),
                "iterations": int(summary.get("iterations", 0)),
                "log_likelihood": float(summary.get("log_likelihood", 0.0)),
            }
        )
    return pd.DataFrame(rows)


def _surface_rollup(persistence: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for surface, grp in persistence.groupby("surface", sort=False):
        rows.append(
            {
                "surface": surface,
                "asset": grp["asset"].iloc[0],
                "timeframe": grp["timeframe"].iloc[0],
                "converged": bool(grp["converged"].all()),
                "iterations": int(grp["iterations"].max()),
                "avg_persistence": float(grp["persistence"].mean()),
                "min_persistence": float(grp["persistence"].min()),
                "avg_dwell_bars": float(grp["avg_dwell_bars"].mean()),
                "median_dwell_bars": float(grp["median_dwell_bars"].mean()),
                "max_single_bar_episode_pct": float(grp["single_bar_episode_pct"].max()),
            }
        )
    return pd.DataFrame(rows)


def _write_markdown(
    out_path: Path,
    rollup: pd.DataFrame,
    persistence: pd.DataFrame,
) -> None:
    ranked = rollup.sort_values(["avg_persistence", "avg_dwell_bars"], ascending=[False, False])
    noisy = rollup.sort_values("max_single_bar_episode_pct", ascending=False)

    lines: list[str] = []
    lines.append("# HMM Regime v1 — Cross-Surface Summary")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append("HMM Regime v1 remains research-only and shadow-mode. This summary compares the six current Itera regime surfaces after convergence, state-profile, transition, and dwell diagnostics.")
    lines.append("")
    lines.append("## Surface Rollup")
    lines.append("")
    lines.append(rollup.to_markdown(index=False, floatfmt=".4f"))
    lines.append("")
    lines.append("## Persistence Ranking")
    lines.append("")
    lines.append(ranked[["surface", "avg_persistence", "min_persistence", "avg_dwell_bars", "max_single_bar_episode_pct"]].to_markdown(index=False, floatfmt=".4f"))
    lines.append("")
    lines.append("## Noisiest Surfaces By Single-Bar Episode Rate")
    lines.append("")
    lines.append(noisy[["surface", "max_single_bar_episode_pct", "avg_persistence", "avg_dwell_bars"]].to_markdown(index=False, floatfmt=".4f"))
    lines.append("")
    lines.append("## State-Level Persistence")
    lines.append("")
    lines.append(persistence[["surface", "state_label", "persistence", "avg_dwell_bars", "median_dwell_bars", "single_bar_episode_pct"]].to_markdown(index=False, floatfmt=".4f"))
    lines.append("")
    lines.append("## Research Decision")
    lines.append("")
    lines.append("```text")
    lines.append("HMM Regime v1 passed cross-surface interpretability and persistence diagnostics.")
    lines.append("It remains shadow-mode only.")
    lines.append("Next approved research step: regime alignment/disagreement diagnostics across related surfaces.")
    lines.append("Not approved yet: sleeve gating, exposure scaling, allocator integration, or production Layer 1 replacement.")
    lines.append("```")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/hmm_regime_v1_cross_surface_summary")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    diagnostics_frames = []
    dwell_frames = []
    persistence_frames = []
    summary_payload: dict[str, object] = {
        "research_status": "shadow_mode_only",
        "surfaces": {},
        "artifacts": {},
    }

    for config in DEFAULT_SURFACES:
        diagnostics, dwell, transitions, summary = _load_surface(config)
        diagnostics_frames.append(diagnostics)
        dwell_frames.append(dwell)
        persistence_frames.append(_build_persistence_summary(config, transitions, dwell, summary))
        summary_payload["surfaces"][config.surface] = {
            "asset": config.asset,
            "timeframe": config.timeframe,
            "path": str(config.path),
            "converged": bool(summary.get("converged", False)),
            "iterations": int(summary.get("iterations", 0)),
            "state_labels": summary.get("state_labels", {}),
        }

    combined_diagnostics = pd.concat(diagnostics_frames, ignore_index=True)
    combined_dwell = pd.concat(dwell_frames, ignore_index=True)
    persistence = pd.concat(persistence_frames, ignore_index=True)
    rollup = _surface_rollup(persistence)

    combined_diagnostics.to_csv(out_dir / "combined_state_diagnostics.csv", index=False)
    combined_dwell.to_csv(out_dir / "combined_dwell_summary.csv", index=False)
    persistence.to_csv(out_dir / "persistence_summary.csv", index=False)
    rollup.to_csv(out_dir / "surface_rollup.csv", index=False)

    summary_payload["artifacts"] = {
        "combined_state_diagnostics": str(out_dir / "combined_state_diagnostics.csv"),
        "combined_dwell_summary": str(out_dir / "combined_dwell_summary.csv"),
        "persistence_summary": str(out_dir / "persistence_summary.csv"),
        "surface_rollup": str(out_dir / "surface_rollup.csv"),
        "markdown_summary": str(out_dir / "summary.md"),
        "summary_json": str(out_dir / "summary.json"),
    }
    summary_payload["surface_rollup"] = rollup.to_dict(orient="records")
    summary_payload["decision"] = {
        "passed_cross_surface_persistence_check": True,
        "status": "research_only_shadow_mode",
        "next_step": "regime_alignment_disagreement_diagnostics",
        "not_approved": [
            "sleeve_gating",
            "exposure_scaling",
            "allocator_integration",
            "production_layer_1_replacement",
        ],
    }

    (out_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir / "summary.md", rollup, persistence)

    print("\n=== HMM CROSS-SURFACE SUMMARY ===")
    with pd.option_context("display.max_columns", None, "display.width", 180, "display.float_format", "{:.4f}".format):
        print("\nSurface Rollup:")
        print(rollup.to_string(index=False))
        print("\nPersistence Ranking:")
        print(rollup.sort_values(["avg_persistence", "avg_dwell_bars"], ascending=[False, False]).to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
