"""Pure Campaign #52 development-stage transformations and inference helpers.

This module is observation-only.  It contains no governed artifact discovery,
strategy invocation, source loading, replay orchestration, or validation-stage
access.  Callers must supply already-validated synthetic or development-only
records explicitly.
"""

from __future__ import annotations

import hashlib
import math
import os
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from research.harness.campaign52_target_replay import TargetRecord

CONTROL_IDS = (
    "static_dev_mean_target",
    "lag_24h",
    "lag_168h",
    "lag_672h",
    *(f"perm_{i:02d}" for i in range(1, 17)),
)
DEVELOPMENT_FOLDS = ("2020", "2021", "2022")
FORBIDDEN_PATH_TOKENS = ("validation", "2023", "2024", "2025")
BOOTSTRAP_ALGORITHM_VERSION = "moving_block_v1"


class Campaign52DevelopmentError(ValueError):
    """Fail-closed Campaign #52 development helper error."""


def ensure_development_path(path: Path | str) -> Path:
    p = Path(path)
    lowered = p.as_posix().lower()
    if any(token in lowered.split("/") for token in FORBIDDEN_PATH_TOKENS):
        raise Campaign52DevelopmentError("VALIDATION_PATH_FORBIDDEN")
    return p


def validate_development_records(records: Sequence[TargetRecord]) -> None:
    if not records:
        raise Campaign52DevelopmentError("EMPTY_TARGET_STREAM")
    previous: tuple[str, str, pd.Timestamp, int] | None = None
    seen: set[tuple[str, str, pd.Timestamp]] = set()
    for record in records:
        ts = pd.Timestamp(record.timestamp)
        if record.stage != "development" or record.fold not in DEVELOPMENT_FOLDS:
            raise Campaign52DevelopmentError("NON_DEVELOPMENT_RECORD")
        if not math.isfinite(float(record.signed_target_exposure)):
            raise Campaign52DevelopmentError("NON_FINITE_TARGET")
        key = (record.fold, record.sleeve_label, ts)
        if key in seen:
            raise Campaign52DevelopmentError("DUPLICATE_TARGET_ROW")
        seen.add(key)
        order = (record.fold, record.sleeve_label, ts, record.sequence_number)
        if previous is not None and order < previous:
            raise Campaign52DevelopmentError("TARGET_ORDER_FAILURE")
        previous = order


def static_mean_values(records: Sequence[TargetRecord]) -> dict[str, float]:
    validate_development_records(records)
    grouped: dict[str, list[float]] = {}
    for record in records:
        grouped.setdefault(record.sleeve_label, []).append(float(record.signed_target_exposure))
    return {sleeve: math.fsum(values) / len(values) for sleeve, values in sorted(grouped.items())}


def transform_static(records: Sequence[TargetRecord], means: Mapping[str, float] | None = None) -> list[TargetRecord]:
    validate_development_records(records)
    resolved = dict(means or static_mean_values(records))
    if set(resolved) != {r.sleeve_label for r in records}:
        raise Campaign52DevelopmentError("STATIC_SLEEVE_SET_MISMATCH")
    return [replace(r, signed_target_exposure=float(resolved[r.sleeve_label])) for r in records]


def transform_lag(records: Sequence[TargetRecord], lag_hours: int) -> tuple[list[TargetRecord], dict[str, int]]:
    validate_development_records(records)
    if lag_hours not in (24, 168, 672):
        raise Campaign52DevelopmentError("UNAUTHORIZED_LAG")
    by_stream: dict[tuple[str, str], dict[pd.Timestamp, float]] = {}
    for record in records:
        by_stream.setdefault((record.fold, record.sleeve_label), {})[pd.Timestamp(record.timestamp)] = float(record.signed_target_exposure)
    matched = zero_filled = 0
    out: list[TargetRecord] = []
    delta = pd.Timedelta(hours=lag_hours)
    for record in records:
        value = by_stream[(record.fold, record.sleeve_label)].get(pd.Timestamp(record.timestamp) - delta)
        if value is None:
            value = 0.0
            zero_filled += 1
        else:
            matched += 1
        out.append(replace(record, signed_target_exposure=float(value)))
    return out, {"matched_rows": matched, "zero_filled_rows": zero_filled}


def seed64(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def permutation_seed(control_id: str) -> int:
    if control_id not in CONTROL_IDS[4:]:
        raise Campaign52DevelopmentError("INVALID_PERMUTATION_CONTROL")
    return seed64(f"campaign52|block28d|perm|{control_id[-2:]}")


def bootstrap_seed(control_id: str) -> int:
    if control_id not in CONTROL_IDS:
        raise Campaign52DevelopmentError("INVALID_CONTROL_ID")
    return seed64(f"campaign52|bootstrap|development|{control_id}")


def fisher_yates(n: int, seed: int) -> list[int]:
    if n < 0:
        raise Campaign52DevelopmentError("NEGATIVE_PERMUTATION_SIZE")
    order = list(range(n))
    rng = np.random.default_rng(seed)
    for i in range(n - 1, 0, -1):
        j = int(rng.integers(0, i + 1))
        order[i], order[j] = order[j], order[i]
    return order


def transform_block_permutation(
    records: Sequence[TargetRecord],
    control_id: str,
    *,
    fold_starts: Mapping[str, pd.Timestamp],
    fold_ends: Mapping[str, pd.Timestamp],
) -> tuple[list[TargetRecord], dict[str, object]]:
    validate_development_records(records)
    seed = permutation_seed(control_id)
    out: list[TargetRecord] = []
    manifest: dict[str, object] = {"control_id": control_id, "seed": seed, "folds": {}}
    for fold in DEVELOPMENT_FOLDS:
        fold_records = [r for r in records if r.fold == fold]
        if not fold_records:
            continue
        start = pd.Timestamp(fold_starts[fold])
        end = pd.Timestamp(fold_ends[fold])
        total_days = int((end.normalize() - start.normalize()).days) + 1
        complete_count = total_days // 28
        permutation = fisher_yates(complete_count, seed)
        fold_info: dict[str, object] = {
            "complete_block_count": complete_count,
            "canonical_order": list(range(complete_count)),
            "permuted_order": permutation,
            "terminal_days": total_days - complete_count * 28,
        }
        for sleeve in sorted({r.sleeve_label for r in fold_records}):
            stream = [r for r in fold_records if r.sleeve_label == sleeve]
            blocks: list[list[TargetRecord]] = [[] for _ in range(complete_count)]
            terminal: list[TargetRecord] = []
            for record in stream:
                block_index = int((pd.Timestamp(record.timestamp) - start) // pd.Timedelta(days=28))
                if 0 <= block_index < complete_count:
                    blocks[block_index].append(record)
                else:
                    terminal.append(record)
            counts = [len(block) for block in blocks]
            if counts and len(set(counts)) != 1:
                raise Campaign52DevelopmentError(f"UNEQUAL_COMPLETE_BLOCK_ROWS:{fold}:{sleeve}")
            destination = [r for block in blocks for r in block]
            source = [r for source_idx in permutation for r in blocks[source_idx]]
            if len(destination) != len(source):
                raise Campaign52DevelopmentError("BLOCK_ROW_COUNT_MISMATCH")
            out.extend(
                replace(dest, signed_target_exposure=float(src.signed_target_exposure))
                for dest, src in zip(destination, source, strict=True)
            )
            out.extend(terminal)
        manifest["folds"][fold] = fold_info
    out.sort(key=lambda r: (r.fold, r.sleeve_label, pd.Timestamp(r.timestamp), r.sequence_number))
    return out, manifest


def daily_eod_nav(hourly_nav: pd.Series) -> pd.Series:
    if not isinstance(hourly_nav.index, pd.DatetimeIndex) or hourly_nav.index.has_duplicates or not hourly_nav.index.is_monotonic_increasing:
        raise Campaign52DevelopmentError("INVALID_NAV_INDEX")
    if hourly_nav.empty or not np.isfinite(hourly_nav.to_numpy(dtype=float)).all() or (hourly_nav <= 0).any():
        raise Campaign52DevelopmentError("INVALID_NAV_VALUES")
    return hourly_nav.resample("1D").last().dropna().rename("nav")


def primary_metrics(daily_nav: pd.Series) -> dict[str, float]:
    nav = daily_eod_nav(daily_nav) if daily_nav.index.freq is None and any(daily_nav.index.time) else daily_nav.astype(float)
    if len(nav) < 2 or (nav <= 0).any() or not np.isfinite(nav.to_numpy()).all():
        raise Campaign52DevelopmentError("INSUFFICIENT_PRIMARY_METRIC_DATA")
    elapsed_days = (nav.index[-1].normalize() - nav.index[0].normalize()).days
    if elapsed_days <= 0:
        raise Campaign52DevelopmentError("ZERO_METRIC_DURATION")
    annual_return = float((nav.iloc[-1] / nav.iloc[0]) ** (365.25 / elapsed_days) - 1.0)
    drawdown = nav / nav.cummax() - 1.0
    max_dd = float(-drawdown.min())
    if max_dd == 0.0:
        calmar = math.inf if annual_return > 0 else (0.0 if annual_return == 0 else -math.inf)
    else:
        calmar = annual_return / max_dd
    return {"annualized_geometric_return": annual_return, "max_drawdown_magnitude": max_dd, "calmar": float(calmar)}


def moving_block_bootstrap(
    paired: Sequence[float] | np.ndarray,
    *,
    seed: int,
    block_length: int = 21,
    replications: int = 10_000,
) -> np.ndarray:
    values = np.asarray(paired, dtype=float)
    if values.ndim != 1 or len(values) < block_length or not np.isfinite(values).all():
        raise Campaign52DevelopmentError("INVALID_BOOTSTRAP_SERIES")
    if replications != 10_000 or block_length != 21:
        raise Campaign52DevelopmentError("FROZEN_BOOTSTRAP_PARAMETER_MISMATCH")
    starts = np.arange(len(values) - block_length + 1)
    blocks_needed = math.ceil(len(values) / block_length)
    rng = np.random.default_rng(seed)
    chosen = rng.choice(starts, size=(replications, blocks_needed), replace=True)
    offsets = np.arange(block_length)
    indices = (chosen[:, :, None] + offsets[None, None, :]).reshape(replications, -1)[:, : len(values)]
    return values[indices]


def bootstrap_summary(paired: Sequence[float] | np.ndarray, control_id: str) -> dict[str, float | int | str]:
    values = np.asarray(paired, dtype=float)
    samples = moving_block_bootstrap(values, seed=bootstrap_seed(control_id))
    means = samples.mean(axis=1)
    observed = float(values.mean())
    return {
        "algorithm": BOOTSTRAP_ALGORITHM_VERSION,
        "seed": bootstrap_seed(control_id),
        "replications": 10_000,
        "block_length": 21,
        "observed_mean": observed,
        "ci_low": float(np.percentile(means, 2.5)),
        "ci_high": float(np.percentile(means, 97.5)),
        "one_sided_p": float((np.count_nonzero(means <= 0.0) + 1) / (len(means) + 1)),
    }


def holm_adjust(raw_p: Mapping[str, float | None]) -> dict[str, float]:
    if set(raw_p) != set(CONTROL_IDS):
        raise Campaign52DevelopmentError("HOLM_FAMILY_MISMATCH")
    ordered = sorted(
        ((1.0 if p is None or not math.isfinite(float(p)) else min(1.0, max(0.0, float(p))), CONTROL_IDS.index(cid), cid) for cid, p in raw_p.items()),
        key=lambda item: (item[0], item[1]),
    )
    adjusted: dict[str, float] = {}
    running = 0.0
    m = len(CONTROL_IDS)
    for rank, (p, _, cid) in enumerate(ordered):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[cid] = running
    return {cid: adjusted[cid] for cid in CONTROL_IDS}


def development_decision(
    canonical: Mapping[str, float],
    controls: Mapping[str, Mapping[str, float]],
    adjusted_p: Mapping[str, float],
) -> dict[str, object]:
    if set(controls) != set(CONTROL_IDS) or set(adjusted_p) != set(CONTROL_IDS):
        raise Campaign52DevelopmentError("DECISION_FAMILY_MISMATCH")
    separated: dict[str, bool] = {}
    for cid in CONTROL_IDS:
        metric = controls[cid]
        separated[cid] = bool(
            canonical["annualized_geometric_return"] > metric["annualized_geometric_return"]
            and (
                metric["max_drawdown_magnitude"] - canonical["max_drawdown_magnitude"] >= 0.01
                or canonical["calmar"] - metric["calmar"] >= 0.10
            )
            and adjusted_p[cid] <= 0.10
        )
    lag_pass = sum(separated[cid] for cid in ("lag_24h", "lag_168h", "lag_672h")) >= 2
    permutation_ids = CONTROL_IDS[4:]
    permutation_pass = all(
        canonical[key] > float(np.median([controls[cid][key] for cid in permutation_ids]))
        for key in ("annualized_geometric_return", "calmar")
    ) and canonical["max_drawdown_magnitude"] < float(
        np.median([controls[cid]["max_drawdown_magnitude"] for cid in permutation_ids])
    )
    static = controls["static_dev_mean_target"]
    static_wins = sum((
        canonical["annualized_geometric_return"] > static["annualized_geometric_return"],
        canonical["max_drawdown_magnitude"] < static["max_drawdown_magnitude"],
        canonical["calmar"] > static["calmar"],
    ))
    passed = bool(lag_pass and permutation_pass and static_wins >= 2)
    return {
        "development_gate_passed": passed,
        "classification": "ADVANCE_TO_VALIDATION_DECISION" if passed else "DEVELOPMENT_NEGATIVE",
        "lag_rule_passed": lag_pass,
        "permutation_median_rule_passed": permutation_pass,
        "static_primary_wins": static_wins,
        "development_separated": separated,
    }


def atomic_promote(temp_root: Path | str, final_root: Path | str) -> None:
    temp = ensure_development_path(temp_root)
    final = ensure_development_path(final_root)
    if not temp.is_dir():
        raise Campaign52DevelopmentError("TEMP_OUTPUT_MISSING")
    if final.exists():
        raise Campaign52DevelopmentError("STALE_OUTPUT_EXISTS")
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp, final)


def clean_temp(path: Path | str) -> None:
    p = ensure_development_path(path)
    if p.exists():
        shutil.rmtree(p)
