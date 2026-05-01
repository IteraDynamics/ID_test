#!/usr/bin/env python
"""Analyze HMM regime alignment across related Itera surfaces.

Research-only utility. Reads state probability artifacts produced by
scripts/run_hmm_regime_analysis.py and compares hard state labels across
paired surfaces after time-index alignment.
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


@dataclass(frozen=True)
class PairConfig:
    pair: str
    left: str
    right: str


SURFACES = {
    "SPY_1D": SurfaceConfig("SPY_1D", "SPY", "1D", Path("artifacts/hmm_regime_v1_spy_1d")),
    "QQQ_1D": SurfaceConfig("QQQ_1D", "QQQ", "1D", Path("artifacts/hmm_regime_v1_qqq_1d")),
    "BTC_1H": SurfaceConfig("BTC_1H", "BTC", "1H", Path("artifacts/hmm_regime_v1_btc_1h")),
    "BTC_4H": SurfaceConfig("BTC_4H", "BTC", "4H", Path("artifacts/hmm_regime_v1_btc_4h")),
    "ETH_1H": SurfaceConfig("ETH_1H", "ETH", "1H", Path("artifacts/hmm_regime_v1_eth_1h")),
    "ETH_4H": SurfaceConfig("ETH_4H", "ETH", "4H", Path("artifacts/hmm_regime_v1_eth_4h")),
}

PAIRS = [
    PairConfig("SPY_1D_vs_QQQ_1D", "SPY_1D", "QQQ_1D"),
    PairConfig("BTC_1H_vs_BTC_4H", "BTC_1H", "BTC_4H"),
    PairConfig("ETH_1H_vs_ETH_4H", "ETH_1H", "ETH_4H"),
    PairConfig("BTC_4H_vs_ETH_4H", "BTC_4H", "ETH_4H"),
    PairConfig("BTC_1H_vs_ETH_1H", "BTC_1H", "ETH_1H"),
]

RISK_OFF_LABELS = {"HIGH_VOL", "TREND_DOWN"}
CONSTRUCTIVE_LABELS = {"TREND_UP", "VOL_COMPRESSION"}


def _load_probabilities(config: SurfaceConfig) -> pd.DataFrame:
    path = config.path / "state_probabilities.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing state probabilities artifact: {path}")

    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[~df.index.isna()].sort_index()
    required = {"hmm_state_id", "hmm_state_label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing required columns: {sorted(missing)}")

    return pd.DataFrame(
        {
            f"{config.surface}_state_id": df["hmm_state_id"].astype(int),
            f"{config.surface}_state_label": df["hmm_state_label"].astype(str),
        },
        index=df.index,
    )


def _align_pair(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    start = max(left.index.min(), right.index.min())
    end = min(left.index.max(), right.index.max())
    if pd.isna(start) or pd.isna(end) or start >= end:
        raise ValueError(f"No overlapping period for pair: start={start}, end={end}")

    left = left.loc[start:end]
    right = right.loc[start:end]
    combined = left.join(right, how="outer").sort_index().ffill().dropna()
    return combined


def _category(label: str) -> str:
    if label in RISK_OFF_LABELS:
        return "RISK_OFF"
    if label in CONSTRUCTIVE_LABELS:
        return "CONSTRUCTIVE"
    return "NEUTRAL"


def _analyze_pair(pair: PairConfig, surfaces: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, object]]:
    left_cfg = SURFACES[pair.left]
    right_cfg = SURFACES[pair.right]
    aligned = _align_pair(surfaces[pair.left], surfaces[pair.right])

    left_label_col = f"{pair.left}_state_label"
    right_label_col = f"{pair.right}_state_label"
    aligned["left_category"] = aligned[left_label_col].map(_category)
    aligned["right_category"] = aligned[right_label_col].map(_category)
    aligned["exact_label_match"] = aligned[left_label_col] == aligned[right_label_col]
    aligned["category_match"] = aligned["left_category"] == aligned["right_category"]
    aligned["both_risk_off"] = (aligned["left_category"] == "RISK_OFF") & (aligned["right_category"] == "RISK_OFF")
    aligned["both_constructive"] = (aligned["left_category"] == "CONSTRUCTIVE") & (aligned["right_category"] == "CONSTRUCTIVE")
    aligned["risk_disagreement"] = (
        ((aligned["left_category"] == "RISK_OFF") & (aligned["right_category"] == "CONSTRUCTIVE"))
        | ((aligned["left_category"] == "CONSTRUCTIVE") & (aligned["right_category"] == "RISK_OFF"))
    )

    crosstab = pd.crosstab(aligned[left_label_col], aligned[right_label_col], normalize="all")
    crosstab.index.name = f"{pair.left}_label"
    crosstab.columns.name = f"{pair.right}_label"

    summary = {
        "pair": pair.pair,
        "left": pair.left,
        "right": pair.right,
        "left_asset": left_cfg.asset,
        "right_asset": right_cfg.asset,
        "left_timeframe": left_cfg.timeframe,
        "right_timeframe": right_cfg.timeframe,
        "bars": int(len(aligned)),
        "start": str(aligned.index.min()),
        "end": str(aligned.index.max()),
        "exact_label_match_pct": float(aligned["exact_label_match"].mean()),
        "category_match_pct": float(aligned["category_match"].mean()),
        "both_risk_off_pct": float(aligned["both_risk_off"].mean()),
        "both_constructive_pct": float(aligned["both_constructive"].mean()),
        "risk_disagreement_pct": float(aligned["risk_disagreement"].mean()),
    }

    pair_rows = []
    for (left_label, right_label), count in aligned.groupby([left_label_col, right_label_col]).size().items():
        pair_rows.append(
            {
                "pair": pair.pair,
                "left_label": left_label,
                "right_label": right_label,
                "count": int(count),
                "pct": float(count / len(aligned)),
            }
        )
    details = pd.DataFrame(pair_rows).sort_values(["pair", "pct"], ascending=[True, False])
    return details, summary


def _format_markdown_value(value: object, floatfmt: str = ".4f") -> str:
    if isinstance(value, float):
        return format(value, floatfmt)
    return str(value)


def _to_markdown_table(df: pd.DataFrame, floatfmt: str = ".4f") -> str:
    if df.empty:
        return "_No rows._"
    columns = [str(col) for col in df.columns]
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in df.iterrows():
        values = [_format_markdown_value(row[col], floatfmt=floatfmt) for col in df.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _write_markdown(out_path: Path, pair_summary: pd.DataFrame, pair_details: pd.DataFrame) -> None:
    risk_rank = pair_summary.sort_values("risk_disagreement_pct", ascending=False)
    category_rank = pair_summary.sort_values("category_match_pct", ascending=False)

    lines = [
        "# HMM Regime v1 — Alignment / Disagreement Diagnostics",
        "",
        "## Status",
        "",
        "Research-only shadow-mode diagnostic. This compares HMM labels across related Itera regime surfaces after time-index alignment.",
        "",
        "## Pair Summary",
        "",
        _to_markdown_table(pair_summary),
        "",
        "## Category Alignment Ranking",
        "",
        _to_markdown_table(category_rank[["pair", "category_match_pct", "exact_label_match_pct", "both_risk_off_pct", "both_constructive_pct", "risk_disagreement_pct"]]),
        "",
        "## Risk Disagreement Ranking",
        "",
        _to_markdown_table(risk_rank[["pair", "risk_disagreement_pct", "category_match_pct", "both_risk_off_pct", "both_constructive_pct"]]),
        "",
        "## Most Common Label Pairings",
        "",
        _to_markdown_table(pair_details.groupby("pair", group_keys=False).head(8)),
        "",
        "## Research Decision",
        "",
        "```text",
        "HMM alignment diagnostics are descriptive only.",
        "Next research use: identify whether same-asset multi-timeframe agreement is more useful than individual HMM state labels.",
        "Not approved yet: direct strategy gating, exposure scaling, allocator integration, or production Layer 1 replacement.",
        "```",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/hmm_regime_v1_alignment")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    loaded = {name: _load_probabilities(config) for name, config in SURFACES.items()}

    detail_frames = []
    summaries = []
    for pair in PAIRS:
        details, summary = _analyze_pair(pair, loaded)
        detail_frames.append(details)
        summaries.append(summary)

    pair_summary = pd.DataFrame(summaries)
    pair_details = pd.concat(detail_frames, ignore_index=True)

    pair_summary.to_csv(out_dir / "pair_summary.csv", index=False)
    pair_details.to_csv(out_dir / "label_pair_details.csv", index=False)

    payload = {
        "research_status": "shadow_mode_only",
        "pairs": pair_summary.to_dict(orient="records"),
        "artifacts": {
            "pair_summary": str(out_dir / "pair_summary.csv"),
            "label_pair_details": str(out_dir / "label_pair_details.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {
            "status": "research_only_shadow_mode",
            "next_step": "evaluate_same_asset_multi_timeframe_agreement_as_shadow_signal_quality_diagnostic",
            "not_approved": [
                "direct_strategy_gating",
                "exposure_scaling",
                "allocator_integration",
                "production_layer_1_replacement",
            ],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir / "summary.md", pair_summary, pair_details)

    print("\n=== HMM REGIME ALIGNMENT DIAGNOSTICS ===")
    with pd.option_context("display.max_columns", None, "display.width", 180, "display.float_format", "{:.4f}".format):
        print("\nPair Summary:")
        print(pair_summary.to_string(index=False))
        print("\nRisk Disagreement Ranking:")
        print(pair_summary.sort_values("risk_disagreement_pct", ascending=False).to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
