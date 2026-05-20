#!/usr/bin/env python
"""Generate an Itera Research Radar context pack.

This script gathers local repo state into a Markdown context pack that can be
used by the agentic research radar cycle. It does not call an LLM, does not use
network access, and does not modify runtime or trading behavior.

Primary output:
    artifacts/research_radar/context_pack.md

Optional JSON output:
    artifacts/research_radar/context_pack.json
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path("artifacts/research_radar")
DEFAULT_RESEARCH_DOCS = [
    Path("docs/research/itera_research_operating_model.md"),
    Path("docs/research/itera_research_radar.md"),
    Path("docs/research/itera_research_expansion_framework.md"),
]
DEFAULT_ARTIFACT_SUMMARIES = [
    Path("artifacts/state_confirmed_candidate_diagnostic/candidate_diagnostic.md"),
    Path("artifacts/state_confirmed_candidate_diagnostic/candidate_summary.csv"),
    Path("artifacts/state_confirmed_candidate_diagnostic/episode_attribution_summary.csv"),
    Path("artifacts/state_confirmed_candidate_diagnostic/risk_off_episodes.csv"),
    Path("artifacts/state_confirmed_risk_off_sweep/state_confirmed_sweep_summary.md"),
    Path("artifacts/state_confirmed_risk_off_sweep/state_confirmed_sweep_summary.csv"),
    Path("artifacts/risk_off_trigger_sweep/sweep_summary.md"),
    Path("artifacts/risk_off_trigger_sweep/sweep_summary.csv"),
    Path("artifacts/risk_off_destination_matrix/summary.md"),
    Path("artifacts/risk_off_destination_matrix/summary.csv"),
    Path("artifacts/fund_v1_plus_qqq_research/summary.md"),
    Path("artifacts/equity_sleeve_research/summary.md"),
]


@dataclass(frozen=True)
class FileSummary:
    path: str
    exists: bool
    size_bytes: int | None = None
    line_count: int | None = None
    preview: str | None = None


@dataclass(frozen=True)
class DataFileSummary:
    path: str
    size_bytes: int
    first_timestamp: str | None
    last_timestamp: str | None
    rows: int | None
    columns: list[str]


def _safe_run(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_context() -> dict[str, str | None]:
    return {
        "branch": _safe_run(["git", "branch", "--show-current"]),
        "head": _safe_run(["git", "rev-parse", "--short", "HEAD"]),
        "status_short": _safe_run(["git", "status", "--short"]),
        "recent_commits": _safe_run(["git", "log", "--oneline", "-8"]),
    }


def _read_text(path: Path, max_chars: int) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[truncated]"


def _file_summary(path: Path, max_chars: int) -> FileSummary:
    if not path.exists() or not path.is_file():
        return FileSummary(path=str(path), exists=False)
    text = _read_text(path, max_chars=max_chars)
    line_count = None if text is None else len(text.splitlines())
    return FileSummary(
        path=str(path),
        exists=True,
        size_bytes=path.stat().st_size,
        line_count=line_count,
        preview=text,
    )


def _discover_files(root: Path, patterns: list[str], limit: int) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(root.glob(pattern)))
    unique = []
    seen = set()
    for file in files:
        if file.is_file() and file not in seen:
            unique.append(file)
            seen.add(file)
    return unique[:limit]


def _summarize_csv(path: Path) -> DataFileSummary | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            rows = 0
            first_ts = None
            last_ts = None
            ts_idx = 0
            lower = [h.strip().lower() for h in header]
            for candidate in ("timestamp", "datetime", "date", "time"):
                if candidate in lower:
                    ts_idx = lower.index(candidate)
                    break
            for row in reader:
                if not row:
                    continue
                rows += 1
                ts = row[ts_idx] if ts_idx < len(row) else None
                if ts and first_ts is None:
                    first_ts = ts
                if ts:
                    last_ts = ts
    except OSError:
        return None
    return DataFileSummary(
        path=str(path),
        size_bytes=path.stat().st_size,
        first_timestamp=first_ts,
        last_timestamp=last_ts,
        rows=rows,
        columns=header,
    )


def _data_file_summaries(data_dir: Path, limit: int) -> list[DataFileSummary]:
    if not data_dir.exists():
        return []
    summaries: list[DataFileSummary] = []
    for path in sorted(data_dir.glob("*.csv"))[:limit]:
        summary = _summarize_csv(path)
        if summary is not None:
            summaries.append(summary)
    return summaries


def _script_inventory(limit: int) -> list[str]:
    script_paths = _discover_files(
        Path("scripts"),
        patterns=[
            "run_*research*.py",
            "run_*sweep*.py",
            "run_*diagnostic*.py",
            "generate_research_radar_context.py",
        ],
        limit=limit,
    )
    return [str(p) for p in script_paths]


def _candidate_dirs() -> list[str]:
    root = Path("docs/research/candidates")
    if not root.exists():
        return []
    return [str(path) for path in sorted(root.iterdir()) if path.is_dir()]


def _extract_top_rows_from_csv(path: Path, n: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            return [row for _, row in zip(range(n), reader)]
    except OSError:
        return []


def _top_result_tables() -> dict[str, list[dict[str, Any]]]:
    return {
        "state_confirmed_sweep_top_rows": _extract_top_rows_from_csv(
            Path("artifacts/state_confirmed_risk_off_sweep/state_confirmed_sweep_summary.csv"), 10
        ),
        "risk_off_destination_matrix_top_rows": _extract_top_rows_from_csv(
            Path("artifacts/risk_off_destination_matrix/summary.csv"), 12
        ),
        "candidate_summary": _extract_top_rows_from_csv(
            Path("artifacts/state_confirmed_candidate_diagnostic/candidate_summary.csv"), 3
        ),
        "episode_attribution_summary": _extract_top_rows_from_csv(
            Path("artifacts/state_confirmed_candidate_diagnostic/episode_attribution_summary.csv"), 3
        ),
    }


def _build_context(args: argparse.Namespace) -> dict[str, Any]:
    research_docs = [_file_summary(p, max_chars=args.max_doc_chars) for p in DEFAULT_RESEARCH_DOCS]
    artifact_summaries = [_file_summary(p, max_chars=args.max_artifact_chars) for p in DEFAULT_ARTIFACT_SUMMARIES]
    candidate_files = [
        _file_summary(p, max_chars=args.max_doc_chars)
        for p in _discover_files(Path("docs/research/candidates"), ["**/*.md"], args.max_candidate_files)
    ]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git": _git_context(),
        "research_docs": [asdict(x) for x in research_docs],
        "candidate_dirs": _candidate_dirs(),
        "candidate_files": [asdict(x) for x in candidate_files],
        "artifact_summaries": [asdict(x) for x in artifact_summaries],
        "top_result_tables": _top_result_tables(),
        "data_files": [asdict(x) for x in _data_file_summaries(Path(args.data_dir), args.max_data_files)],
        "research_script_inventory": _script_inventory(args.max_scripts),
    }


def _md_escape_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _write_file_summary_section(lines: list[str], title: str, summaries: list[dict[str, Any]]) -> None:
    lines.append(f"## {title}\n")
    for summary in summaries:
        status = "present" if summary["exists"] else "missing"
        lines.append(f"### `{summary['path']}` — {status}\n")
        if not summary["exists"]:
            continue
        lines.append(f"- Size: `{summary['size_bytes']}` bytes")
        lines.append(f"- Preview line count: `{summary['line_count']}`\n")
        preview = summary.get("preview") or ""
        if preview:
            lines.append("```text")
            lines.append(preview.rstrip())
            lines.append("```\n")


def _write_top_table(lines: list[str], title: str, rows: list[dict[str, Any]]) -> None:
    lines.append(f"### {title}\n")
    if not rows:
        lines.append("No rows found.\n")
        return
    keys = list(rows[0].keys())[:12]
    lines.append("| " + " | ".join(keys) + " |")
    lines.append("|" + "|".join(["---"] * len(keys)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(_md_escape_cell(row.get(k)) for k in keys) + " |")
    lines.append("")


def _render_markdown(context: dict[str, Any]) -> str:
    lines: list[str] = []
    git = context["git"]
    lines.append("# Itera Research Radar Context Pack\n")
    lines.append("This context pack is generated from local repository state. It is intended to seed an agentic research-radar update. It is not a trading signal.\n")
    lines.append("## Generation Metadata\n")
    lines.append(f"- Generated UTC: `{context['generated_at_utc']}`")
    lines.append(f"- Branch: `{git.get('branch')}`")
    lines.append(f"- HEAD: `{git.get('head')}`\n")
    lines.append("### Git Status\n")
    lines.append("```text")
    lines.append(git.get("status_short") or "clean")
    lines.append("```\n")
    lines.append("### Recent Commits\n")
    lines.append("```text")
    lines.append(git.get("recent_commits") or "n/a")
    lines.append("```\n")

    _write_file_summary_section(lines, "Research Docs", context["research_docs"])

    lines.append("## Candidate Directories\n")
    if context["candidate_dirs"]:
        for path in context["candidate_dirs"]:
            lines.append(f"- `{path}`")
    else:
        lines.append("No candidate directories found.")
    lines.append("")

    _write_file_summary_section(lines, "Candidate Files", context["candidate_files"])
    _write_file_summary_section(lines, "Research Artifact Summaries", context["artifact_summaries"])

    lines.append("## Top Result Tables\n")
    for title, rows in context["top_result_tables"].items():
        _write_top_table(lines, title.replace("_", " ").title(), rows)

    lines.append("## Available Data Files\n")
    data_files = context["data_files"]
    if not data_files:
        lines.append("No data CSVs found.\n")
    else:
        lines.append("| Path | Rows | First Timestamp | Last Timestamp | Columns |")
        lines.append("|---|---:|---|---|---|")
        for row in data_files:
            columns = ", ".join(row["columns"][:8])
            lines.append(
                f"| `{row['path']}` | {row['rows']} | {_md_escape_cell(row['first_timestamp'])} | "
                f"{_md_escape_cell(row['last_timestamp'])} | {_md_escape_cell(columns)} |"
            )
        lines.append("")

    lines.append("## Research Script Inventory\n")
    if context["research_script_inventory"]:
        for script in context["research_script_inventory"]:
            lines.append(f"- `{script}`")
    else:
        lines.append("No research scripts found.")
    lines.append("")

    lines.append("## Suggested Radar Update Prompt\n")
    lines.append("```text")
    lines.append(
        "Using this context pack, update docs/research/itera_research_radar.md. "
        "Preserve the rule: agentic idea generation, deterministic validation, human promotion decision, deterministic runtime. "
        "Do not create trade instructions. Rank research priorities across crypto, macro/cross-asset, equity/factor, sector, volatility/risk, portfolio construction, and execution/cost lanes. "
        "Update active candidates, validation queue, backlog, archived ideas, and highest-value next tests."
    )
    lines.append("```\n")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Itera Research Radar context pack")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--max-doc-chars", type=int, default=6000)
    parser.add_argument("--max-artifact-chars", type=int, default=6000)
    parser.add_argument("--max-candidate-files", type=int, default=30)
    parser.add_argument("--max-data-files", type=int, default=80)
    parser.add_argument("--max-scripts", type=int, default=80)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    context = _build_context(args)
    md = _render_markdown(context)

    md_path = out_dir / "context_pack.md"
    json_path = out_dir / "context_pack.json"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(context, indent=2, default=str), encoding="utf-8")

    print("=" * 96)
    print("  ITERA RESEARCH RADAR CONTEXT PACK")
    print("=" * 96)
    print(f"  Markdown: {md_path}")
    print(f"  JSON    : {json_path}")
    print("  Runtime impact: none")
    print("  Trading impact: none")
    print("=" * 96)


if __name__ == "__main__":
    main()
