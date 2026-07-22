from __future__ import annotations

"""Portable artifact identifiers and deterministic text output helpers."""

from pathlib import Path


def normalize_artifact_identifier(value: str) -> str:
    """Return a slash-normalized artifact identifier."""
    return str(value).replace("\\", "/")


def stable_artifact_identifier(path: Path, repository_root: Path) -> str:
    """Return a portable repo-relative identifier when the path is inside the repo."""
    resolved_path = path.resolve()
    resolved_root = repository_root.resolve()
    try:
        identifier = resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        identifier = path.as_posix()
    return normalize_artifact_identifier(identifier)


def write_text_lf(path: Path, text: str) -> None:
    """Write UTF-8 text with explicit LF newlines on every supported platform."""
    path.write_text(text, encoding="utf-8", newline="\n")
