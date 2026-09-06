from __future__ import annotations

"""Generate deterministic human- and machine-readable taxonomy reports."""

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import json
import sys
from pathlib import Path

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

from research.ml.validation.historical_regime_artifact_io import (
    stable_artifact_identifier,
    write_text_lf,
)
from research.ml.validation.historical_regime_taxonomy_report import (
    build_report_model,
    render_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report Core v1 Jump Risk historical regime taxonomy.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--taxonomy-summary",
        default=(
            "artifacts/core_v1_jump_risk_historical_regime_taxonomy/"
            "btc_extended_up_taxonomy_summary.json"
        ),
    )
    parser.add_argument(
        "--classified-episodes",
        default=(
            "artifacts/core_v1_jump_risk_historical_regime_taxonomy/"
            "btc_extended_up_classified_episodes.json"
        ),
    )
    parser.add_argument(
        "--episode-signatures",
        default=(
            "artifacts/core_v1_jump_risk_recovery_subtypes/"
            "btc_extended_up_episode_signatures.csv"
        ),
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/core_v1_jump_risk_historical_regime_taxonomy",
    )
    parser.add_argument("--stream", default="btc_extended_up")
    parser.add_argument("--top-features", type=int, default=5)
    return parser.parse_args()


def _write_outputs_atomically(
    json_path: Path,
    json_text: str,
    markdown_path: Path,
    markdown_text: str,
) -> None:
    json_temp = json_path.with_suffix(json_path.suffix + ".tmp")
    markdown_temp = markdown_path.with_suffix(markdown_path.suffix + ".tmp")
    try:
        write_text_lf(json_temp, json_text)
        write_text_lf(markdown_temp, markdown_text)
        json_temp.replace(json_path)
        markdown_temp.replace(markdown_path)
    finally:
        for temporary in (json_temp, markdown_temp):
            if temporary.exists():
                temporary.unlink()


def main() -> None:
    args = parse_args()
    summary_path = Path(args.taxonomy_summary)
    episodes_path = Path(args.classified_episodes)
    signatures_path = Path(args.episode_signatures)
    for path in (summary_path, episodes_path, signatures_path):
        if not path.exists():
            raise FileNotFoundError(path)

    taxonomy_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    episode_records = json.loads(episodes_path.read_text(encoding="utf-8"))
    if not isinstance(episode_records, list):
        raise ValueError("classified episode artifact must contain a list")

    classified = pd.DataFrame(episode_records)
    signatures = pd.read_csv(signatures_path, index_col="episode_id")
    report = build_report_model(
        classified,
        signatures,
        taxonomy_summary,
        top_features=args.top_features,
        source_artifacts={
            "taxonomy_summary": stable_artifact_identifier(
                summary_path, REPOSITORY_ROOT
            ),
            "classified_episodes": stable_artifact_identifier(
                episodes_path, REPOSITORY_ROOT
            ),
            "episode_signatures": stable_artifact_identifier(
                signatures_path, REPOSITORY_ROOT
            ),
        },
    )
    report_json = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    report_markdown = render_markdown(report)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{args.stream}_taxonomy_report.json"
    markdown_path = out_dir / f"{args.stream}_taxonomy_report.md"
    _write_outputs_atomically(
        json_path,
        report_json,
        markdown_path,
        report_markdown,
    )

    print()
    print("Core v1 Jump Risk historical regime taxonomy report complete")
    print(f"Episodes:        {report['episode_count']}")
    print(f"Taxonomy digest: {report['source_taxonomy_digest_sha256']}")
    print(f"Report digest:   {report['report_digest_sha256']}")
    print(f"JSON report:     {json_path}")
    print(f"Markdown report: {markdown_path}")
    print("Observation only: no Core state, NAV, orders, thresholds, or exposure were changed.")


if __name__ == "__main__":
    main()
