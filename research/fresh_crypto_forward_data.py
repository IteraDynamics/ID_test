"""Local daily snapshots for the frozen historical forward experiment; no downloads."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd

from research import fresh_crypto_long_history as prior
from research.fresh_discovery.data import sha, write_json

START = pd.Timestamp("2017-01-01", tz="UTC")
FORWARD_START = pd.Timestamp("2025-01-01", tz="UTC")
MIN_END = pd.Timestamp("2025-12-31", tz="UTC")
END_CAP = pd.Timestamp("2026-08-26", tz="UTC")
FIELDS = ["open", "high", "low", "close", "volume"]
FILENAMES = {
    "BTC": "btcusd_86400s_2015-07-15_to_2026-08-26.csv",
    "ETH": "ethusd_86400s_2016-05-13_to_2026-08-26.csv",
}
SOURCE_RUNS = ("fresh_crypto_long_history_20260914_142341_250", *prior.SOURCE_RUNS)


def resolve_source(source: Path | None, root: Path) -> Path:
    if source is not None:
        return prior.resolve_source(source, root)
    checked = []
    for name in SOURCE_RUNS:
        try:
            return prior.resolve_source(root/"artifacts"/name, root)
        except FileNotFoundError as exc:
            checked.append(str(exc))
    raise FileNotFoundError("\n".join(checked))


def columns(path: Path) -> tuple[list[str], str]:
    names = list(pd.read_csv(path, nrows=0).columns)
    normalized = [c.strip().lower().replace(" ", "_") for c in names]
    time_names = [c for c in normalized if c in ("timestamp", "date", "datetime", "time")]
    if len(set(normalized))!=len(normalized) or len(time_names)!=1 or not set(FIELDS)<=set(normalized):
        raise ValueError(f"Need one timestamp and OHLCV columns: {path}")
    return normalized, names[normalized.index(time_names[0])]


def dates_from(labels: pd.Series) -> pd.DatetimeIndex:
    numeric = pd.to_numeric(labels, errors="coerce")
    if numeric.notna().all():
        magnitude = float(numeric.abs().median())
        unit = "s" if 1e9<magnitude<1e10 else "ms" if 1e12<magnitude<1e13 else None
        if unit is None:
            raise ValueError("Unrecognized epoch timestamp units")
        dates = pd.DatetimeIndex(pd.to_datetime(numeric, unit=unit, utc=True, errors="raise"))
    else:
        dates = pd.DatetimeIndex(pd.to_datetime(labels, utc=True, errors="raise", format="mixed"))
    if dates.hasnans:
        raise ValueError("Missing timestamps")
    return dates


def scan(path: Path) -> dict:
    """Inspect headers/date labels and hash bytes before reading price columns."""
    names, time_name = columns(path)
    dates = dates_from(pd.read_csv(path, usecols=[time_name], dtype=str)[time_name])
    eligible = dates[(dates>=START) & (dates<=END_CAP)]
    if (len(eligible)<2 or eligible.has_duplicates or
            not eligible.sort_values().equals(pd.date_range(START, eligible.max(), tz="UTC"))):
        raise ValueError(f"Need complete UTC daily bars from 2017; missing, duplicate or intraday timestamps: {path}")
    if eligible.max()<MIN_END:
        raise ValueError(f"Need complete 2025 coverage; last eligible date {eligible.max().date()}: {path}")
    return dict(path=str(path.resolve()), sha256=sha(path), columns=names,
                source_bar_seconds=86400, source_rows=len(dates),
                eligible_last_date=str(eligible.max().date()),
                rows_after_fixed_cap=int((dates>END_CAP).sum()),
                timestamp_semantics="assumed_UTC_bar_start", vendor_provenance="operator_local_unverified")


def validate_daily(frame: pd.DataFrame, end: pd.Timestamp) -> None:
    if list(frame.columns)!=FIELDS or not frame.index.equals(pd.date_range(START, end, tz="UTC")):
        raise ValueError("Expected the complete aligned UTC daily OHLCV calendar from 2017")
    values = frame.to_numpy()
    if not np.isfinite(values).all() or (values[:,:4]<=0).any() or (values[:,4]<0).any():
        raise ValueError("Invalid price or volume")
    if ((frame.low>frame[["open","close"]].min(axis=1)).any() or
            (frame.high<frame[["open","close"]].max(axis=1)).any() or (frame.low>frame.high).any()):
        raise ValueError("Invalid OHLC range")


def read_daily(path: Path, end: pd.Timestamp) -> pd.DataFrame:
    names, time_name = columns(path)
    raw = pd.read_csv(path, dtype=str)
    dates = dates_from(raw[time_name])
    raw.columns = names
    selected = (dates>=START) & (dates<=end)
    # Prices outside the frozen common window are never converted or evaluated.
    frame = raw.loc[selected, FIELDS].astype(float)
    frame.index = dates[selected]
    frame = frame.sort_index()
    frame.index.name = "timestamp"
    validate_daily(frame, end)
    return frame


def stitch(reviewed: pd.DataFrame, raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    overlap = raw.loc[reviewed.index]
    if not np.allclose(overlap, reviewed, rtol=1e-12, atol=1e-10):
        raise ValueError("Local file disagrees with reviewed 2017-2024 OHLCV history; do not splice different sources")
    differences = {c:float((overlap[c]-reviewed[c]).abs().max()) for c in FIELDS}
    # Preserve the reviewed development values exactly; permit only serialization noise.
    frame = pd.concat([reviewed, raw.loc[FORWARD_START:]])
    validate_daily(frame, raw.index[-1])
    return frame, dict(overlap_rows=len(reviewed), maximum_absolute_difference=differences,
                       tolerance=dict(rtol=1e-12, atol=1e-10), reviewed_values_preserved=True)


def snapshot(source: Path, paths: dict[str, Path], out: Path, run_identity: dict,
             prior_access_2026: str = "unknown") -> dict:
    """Record the common calendar and source identity before inspecting forward OHLCV."""
    if prior_access_2026 not in ("unknown", "already_inspected", "not_known_inspected"):
        raise ValueError("Invalid 2026 prior-access classification")
    reviewed, source_manifest = prior.load_source(source)
    records = {asset:scan(paths[asset]) for asset in FILENAMES}
    end = min(pd.Timestamp(r["eligible_last_date"], tz="UTC") for r in records.values())
    plan = dict(status="INPUT_IDENTITY_LOCKED_BEFORE_FORWARD_PRICE_VALIDATION", **run_identity,
                source=source_manifest, assets=records, first_evaluation_date="2025-01-01",
                last_evaluation_date=str(end.date()), hard_end_cap=str(END_CAP.date()),
                prior_access_2025="already_inspected_in_other_repository_research",
                prior_access_2026=prior_access_2026, globally_pristine_oos_claim=False,
                downloads=0, input_selection="specified_files_then_common_calendar_no_performance_selection")
    write_json(out/"run_plan.json", plan)
    manifests = {}
    for asset in FILENAMES:
        raw = read_daily(paths[asset], end)
        if sha(paths[asset])!=records[asset]["sha256"]:
            raise ValueError("Raw input changed during snapshot preparation")
        frame, overlap = stitch(reviewed[asset], raw)
        name = f"{asset}-USD.csv"
        frame.to_csv(out/name, lineterminator="\n", float_format="%.17g")
        manifests[asset] = dict(file=name, sha256=sha(out/name), **overlap,
                                rows_after_common_end_not_evaluated=int(
                                    (pd.Timestamp(records[asset]["eligible_last_date"],tz="UTC")-end).days))
    source_content = (source/"report.json").read_bytes() if source.is_dir() else None
    if source_content is None:
        import zipfile
        with zipfile.ZipFile(source) as archive:
            source_content = archive.read("report.json")
    (out/"source_report.json").write_bytes(source_content)
    manifest = dict(plan, status="PREPARED_LOCAL_SNAPSHOT_NO_STRATEGY_EVALUATION", inputs=manifests,
                    plan_sha256=sha(out/"run_plan.json"), source_report_sha256=sha(out/"source_report.json"),
                    artifact_sha256={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    write_json(out/"prepared.json", manifest)
    return manifest


def load_prepared(out: Path, current_identity: dict) -> tuple[dict, dict]:
    import json
    prepared = json.loads((out/"prepared.json").read_text())
    if prepared["status"]!="PREPARED_LOCAL_SNAPSHOT_NO_STRATEGY_EVALUATION":
        raise ValueError("Invalid prepared input status")
    for key in ("commit", "code_sha256", "environment", "synthetic_data_used", "protocol"):
        if prepared[key]!=current_identity[key]:
            raise ValueError(f"Prepared identity changed: {key}; prepare a new run")
    for name,digest in prepared["artifact_sha256"].items():
        if Path(name).name!=name or sha(out/name)!=digest:
            raise ValueError(f"Prepared artifact changed: {name}")
    if sha(out/"run_plan.json")!=prepared["plan_sha256"] or sha(out/"source_report.json")!=prepared["source_report_sha256"]:
        raise ValueError("Prepared plan/source report changed")
    end = pd.Timestamp(prepared["last_evaluation_date"], tz="UTC")
    if not MIN_END<=end<=END_CAP:
        raise ValueError("Prepared end date outside frozen bounds")
    frames = {}
    for asset in FILENAMES:
        record = prepared["inputs"][asset]
        path = out/f"{asset}-USD.csv"
        if record["file"]!=path.name or sha(path)!=record["sha256"]:
            raise ValueError("Prepared price snapshot changed")
        raw = pd.read_csv(io.BytesIO(path.read_bytes()), float_precision="round_trip")
        dates = pd.DatetimeIndex(pd.to_datetime(raw.pop("timestamp"), utc=True))
        raw.index = dates
        validate_daily(raw, end)
        frames[asset] = raw
    return frames, prepared
