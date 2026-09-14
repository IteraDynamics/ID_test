"""Load only the two exact pre-2025 inputs already reviewed; no download path."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

from research.fresh_crypto.data import normalize
from research.fresh_discovery.data import sha, write_json
from .design import EXPECTED_INPUTS, SOURCE_COMMIT


def load_source(source: Path, out: Path):
    names = ["report.json", *EXPECTED_INPUTS]
    if source.is_dir():
        contents = {name: (source/name).read_bytes() for name in names}
        identity = dict(source_path=str(source.resolve()), source_report_sha256=sha(source/"report.json"))
    elif source.is_file():
        with zipfile.ZipFile(source) as archive:
            if len(set(archive.namelist()))!=len(archive.namelist()) or archive.testzip() is not None:
                raise ValueError("Duplicate ZIP members or corrupt source archive")
            contents = {name: archive.read(name) for name in names}
        identity = dict(source_path=str(source.resolve()), source_archive_sha256=sha(source))
    else:
        raise FileNotFoundError("Supply the completed fresh_crypto_20260914_110447_621 directory or ZIP")
    report = json.loads(contents["report.json"])
    if report.get("synthetic_data_used") is not False or report.get("commit")!=SOURCE_COMMIT:
        raise ValueError("Expected the reviewed market screen at commit 62cc0f1")
    if report.get("reserved_2025_used") is not False:
        raise ValueError("Source report crosses the development boundary")
    frames = {}
    for name, expected in EXPECTED_INPUTS.items():
        if hashlib.sha256(contents[name]).hexdigest()!=expected or report["files"].get(name)!=expected:
            raise ValueError(f"Input differs from the reviewed research snapshot: {name}")
        asset = name.split("-")[0]
        frame, _ = normalize(pd.read_csv(io.BytesIO(contents[name]), float_precision="round_trip"))
        if str(frame.index[0].date())!="2017-01-01":
            raise ValueError("Expected the full reviewed 2017-2024 input window")
        frames[asset] = frame
        (out/name).write_bytes(contents[name])
    (out/"source_report.json").write_bytes(contents["report.json"])
    identity.update(source_commit=SOURCE_COMMIT, normalized_input_sha256=EXPECTED_INPUTS,
                    original_vendor_provenance="operator_local_unverified", downloads=0,
                    price_window="2017-01-01 through 2024-12-31")
    write_json(out/"input_manifest.json", identity)
    return frames, identity
