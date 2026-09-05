"""Existing artifact byte contracts, extracted without format normalization.

These helpers do not write files, create directories, repair inputs or catch errors.
Callers retain publication order, path policy and their original digest constructor.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file_v1(path: Path, *, chunk_size: int = 1024 * 1024,
                   factory=hashlib.sha256) -> str:
    """Hash raw binary file bytes using the caller's historical read chunk size."""
    digest = factory()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b''):
            digest.update(chunk)
    return digest.hexdigest()
