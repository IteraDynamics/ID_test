#!/usr/bin/env python
"""Build a crypto composite HMM regime diagnostic.

Research-only utility. Reads BTC/ETH 1H/4H HMM state artifacts and creates a
shadow-mode composite regime language for the crypto sleeve-of-sleeves.

This script does not create strategy gates, exposure rules, allocator inputs, or
production Layer 1 replacements.
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


SURFACES = [
    SurfaceConfig("BTC_1H", "BTC", "1H", Path("artifacts/hmm_regime_v1_btc_1h")),
    SurfaceConfig("BTC_4H", "BTC", "4H", Path("artifacts/hmm_regime_v1_btc_4h")),
    SurfaceConfig("ETH_1H", "ETH", "1H", Path("artifacts/hmm_regime_v1_eth_1h")),
    SurfaceConfig("ETH_4H", "ETH", "4H", Path("artifacts/hmm_regime_v1_eth_4h")),
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
            f"{config.surface.lower()}_state_id": df["hmm_state_id"].astype(int),
            f"{config.surface.lower()}_label": df["hmm_state_label"].astype(str),
        },
        index=df.index,
    )


def _category(label: str) -> str:
    if label in RISK_OFF_LABELS:
        return "RISK_OFF"
    if label in CONSTRUCTIVE_LABELS:
        return "CONSTRUCTIVE"
    return "NEUTRAL"


def _align_surfaces(surface_frames: list[pd.DataFrame]) -> pd.DataFrame:
    start = max(frame.index.min() for frame in surface_frames)
    end = min(frame.index.max() for frame in surface_frames)
    if pd.isna(start) or pd.isna(end) or start >= end:
        raise ValueError(f"No overlapping period across crypto surfaces: start={start}, end={end}")

    aligned = surface_frames[0].loc[start:end]
    for frame in surface_frames[1:]:
        aligned = aligned.join(frame.loc[start:end], how="outer")
    return aligned.sort_index().ffill().dropna()


def _agreement_score(categories: list[str]) -> float:
    if not categories:
        return 0.0
    counts = pd.Series(categories).value_counts()
    return float(counts.max() / len(categories))


def _classify_composite(row: pd.Series) -> str:
    structural = row["structural_category"]
    tactical = row["tactical_category"]
    btc_4h = row["btc_4h_category"]
    eth_4h = row["eth_4h_category"]
    btc_1h = row["btc_1h_category"]
    eth_1h = row["eth_1h_category"]

    if btc_4h == "RISK_OFF" and eth_4h == "RISK_OFF":
        if btc_1h == "CONSTRUCTIVE" or eth_1h == "CONSTRUCTIVE":
            return "STRUCTURAL_RISK_OFF_TACTICAL_REBOUND"
        return "STRUCTURAL_RISK_OFF"

    if btc_4h == "CONSTRUCTIVE" and eth_4h == "CONSTRUCTIVE":
        if btc_1h == "RISK_OFF" or eth_1h == "RISK_OFF":
            return "STRUCTURAL_CONSTRUCTIVE_TACTICAL_PULLBACK"
        return "STRUCTURAL_CONSTRUCTIVE"

    if structural == "MIXED" and tactical == "RISK_OFF":
        return "MIXED_STRUCTURAL_TACTICAL_RISK_OFF"

    if structural == "MIXED" and tactical == "CONSTRUCTIVE":
        return "MIXED_STRUCTURAL_TACTICAL_CONSTRUCTIVE"

    return "MIXED"


def _build_composite(aligned: pd.DataFrame) -> pd.DataFrame:
    out = aligned.copy()
    label_cols = [
        "btc_1h_label",
        "btc_4h_label",
        "eth_1h_label",
        "eth_4h_label",
    ]
    for col in label_cols:
        out[col.replace("_label", "_category")] = out[col].map(_category)

    out["structural_4h_agreement"] = out["btc_4h_category"] == out["eth_4h_category"]
    out["tactical_1h_agreement"] = out["btc_1h_category"] == out["eth_1h_category"]
    out["btc_timeframe_agreement"] = out["btc_1h_category"] == out["btc_4h_category"]
    out["eth_timeframe_agreement"] = out["eth_1h_category"] == out["eth_4h_category"]

    out["structural_category"] = out.apply(
        lambda row: row["btc_4h_category"] if row["structural_4h_agreement"] else "MIXED",
        axis=1,
    )
    out["tactical_category"] = out.apply(
        lambda row: row["btc_1h_category"] if row["tactical_1h_agreement"] else "MIXED",
        axis=1,
    )

    out["any_risk_off"] = (
        (out["btc_1h_category"] == "RISK_OFF")
        | (out["btc_4h_category"] == "RISK_OFF")
        | (out["eth_1h_category"] == "RISK_OFF")
        | (out["eth_4h_category"] == "RISK_OFF")
    )
    out["all_constructive"] = (
        (out["btc_1h_category"] == "CONSTRUCTIVE")
        & (out["btc_4h_category"] == "CONSTRUCTIVE")
        & (out["eth_1h_category"] == "CONSTRUCTIVE")
        & (out["eth_4h_category"] == "CONSTRUCTIVE")
    )
    out["all_risk_off"] = (
        (out["btc_1h_category"] == "RISK_OFF")
        & (out["btc_4h_category"] == "RISK_OFF")
        & (out["eth_1h_category"] == "RISK_OFF")
        & (out["eth_4h_category"] == "RISK_OFF")
    )
    out["structural_tactical_conflict"] = (
        ((out["structural_category"] == "RISK_OFF") & (out["tactical_category"] == "CONSTRUCTIVE"))
        | ((out["structural_category"] == "CONSTRUCTIVE") & (out["tactical_category"] == "RISK_OFF"))
    )

    category_cols = ["btc_1h_category", "btc_4h_category", "eth_1h_category", "eth_4h_category"]
    out["agreement_score"] = out[category_cols].apply(lambda row: _agreement_score(list(row)), axis=1)
    out["composite_regime"] = out.apply(_classify_composite, axis=1)
    return out


def _build_summary(composite: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    regime_summary = (
        composite.groupby("composite_regime")
        .agg(
            count=("composite_regime", "size"),
            agreement_score_avg=("agreement_score", "mean"),
            structural_4h_agreement_pct=("structural_4h_agreement", "mean"),
            tactical_1h_agreement_pct=("tactical_1h_agreement", "mean"),
            btc_timeframe_agreement_pct=("btc_timeframe_agreement", "mean"),
            eth_timeframe_agreement_pct=("eth_timeframe_agreement", "mean"),
            structural_tactical_conflict_pct=("structural_tactical_conflict", "mean"),
            any_risk_off_pct=("any_risk_off", "mean"),
            all_constructive_pct=("all_constructive", "mean"),
            all_risk_off_pct=("all_risk_off", "mean"),
        )
        .reset_index()
    )
    regime_summary["pct"] = regime_summary["count"] / len(composite)
    regime_summary = regime_summary.sort_values("pct", ascending=False)

    overall = pd.DataFrame(
        [
            {
                "bars": int(len(composite)),
                "start": str(composite.index.min()),
                "end": str(composite.index.max()),
                "agreement_score_avg": float(composite["agreement_score"].mean()),
                "structural_4h_agreement_pct": float(composite["structural_4h_agreement"].mean()),
                "tactical_1h_agreement_pct": float(composite["tactical_1h_agreement"].mean()),
                "btc_timeframe_agreement_pct": float(composite["btc_timeframe_agreement"].mean()),
                "eth_timeframe_agreement_pct": float(composite["eth_timeframe_agreement"].mean()),
                "structural_tactical_conflict_pct": float(composite["structural_tactical_conflict"].mean()),
                "all_constructive_pct": float(composite["all_constructive"].mean()),
                "all_risk_off_pct": float(composite["all_risk_off"].mean()),
                "any_risk_off_pct": float(composite["any_risk_off"].mean()),
            }
        ]
    )
    return regime_summary, overall


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


def _write_markdown(out_path: Path, regime_summary: pd.DataFrame, overall: pd.DataFrame) -> None:
    lines = [
        "# HMM Regime v1 — Crypto Composite Diagnostic",
        "",
        "## Status",
        "",
        "Research-only shadow-mode diagnostic for the nested crypto sleeve-of-sleeves: BTC 1H, BTC 4H, ETH 1H, ETH 4H.",
        "",
        "## Overall Summary",
        "",
        _to_markdown_table(overall),
        "",
        "## Composite Regime Summary",
        "",
        _to_markdown_table(regime_summary),
        "",
        "## Interpretation Guardrail",
        "",
        "```text",
        "The composite regime is a descriptive research artifact only.",
        "It is not a trading signal, exposure rule, allocator input, or production Layer 1 replacement.",
        "The intended next use is to evaluate whether composite-regime agreement/disagreement explains sleeve-level performance differences.",
        "```",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/hmm_regime_v1_crypto_composite")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = [_load_probabilities(config) for config in SURFACES]
    aligned = _align_surfaces(frames)
    composite = _build_composite(aligned)
    regime_summary, overall = _build_summary(composite)

    composite.to_csv(out_dir / "crypto_composite_regimes.csv")
    regime_summary.to_csv(out_dir / "crypto_composite_regime_summary.csv", index=False)
    overall.to_csv(out_dir / "crypto_composite_overall_summary.csv", index=False)

    payload = {
        "research_status": "shadow_mode_only",
        "surfaces": [config.surface for config in SURFACES],
        "overall": overall.iloc[0].to_dict(),
        "regime_summary": regime_summary.to_dict(orient="records"),
        "artifacts": {
            "crypto_composite_regimes": str(out_dir / "crypto_composite_regimes.csv"),
            "crypto_composite_regime_summary": str(out_dir / "crypto_composite_regime_summary.csv"),
            "crypto_composite_overall_summary": str(out_dir / "crypto_composite_overall_summary.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {
            "status": "research_only_shadow_mode",
            "next_step": "compare_composite_regimes_against_crypto_sleeve_performance",
            "not_approved": [
                "direct_strategy_gating",
                "exposure_scaling",
                "allocator_integration",
                "production_layer_1_replacement",
            ],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir / "summary.md", regime_summary, overall)

    print("\n=== HMM CRYPTO COMPOSITE DIAGNOSTIC ===")
    with pd.option_context("display.max_columns", None, "display.width", 220, "display.float_format", "{:.4f}".format):
        print("\nOverall Summary:")
        print(overall.to_string(index=False))
        print("\nComposite Regime Summary:")
        print(regime_summary.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
