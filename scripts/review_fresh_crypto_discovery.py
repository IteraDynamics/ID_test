"""Audit a supplied fixed crypto screen; no new strategy, model fit, or holdout use.

Run from the repo root with python -m scripts.review_fresh_crypto_discovery
--archive PATH --output-dir NEW_DIRECTORY. Only flat, hashed artifacts are accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from research.fresh_crypto.data import ASSETS, WARMUP, normalize
from research.fresh_crypto.engine import SCENARIOS, metrics, policies, registry, schedules, simulate
from research.fresh_discovery.data import sha, write_json

ROOT = Path(__file__).resolve().parents[1]


def compare(left, right):
    if list(left.columns) != list(right.columns) or left.shape != right.shape:
        raise ValueError("Replay schema/shape mismatch")
    differences = {}
    for column in left:
        a, b = left[column], right[column]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            av, bv = a.to_numpy(dtype=float), b.to_numpy(dtype=float)
            if not np.allclose(av, bv, rtol=2e-10, atol=2e-11, equal_nan=True):
                raise ValueError(f"Replay numerical mismatch: {column}")
            finite = np.isfinite(av) & np.isfinite(bv)
            differences[column] = float(np.max(np.abs(av[finite]-bv[finite]))) if finite.any() else 0.
        elif not a.fillna("").astype(str).equals(b.fillna("").astype(str)):
            raise ValueError(f"Replay metadata mismatch: {column}")
    return differences


def audit(archive, out):
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    source = out / "source"
    source.mkdir()
    with zipfile.ZipFile(archive) as z:
        if len(set(z.namelist())) != len(z.namelist()) or z.testzip() is not None:
            raise ValueError("Duplicate ZIP members or failed CRC")
        for name in z.namelist():
            if Path(name).name != name or "\\" in name or name in (".", ".."):
                raise ValueError("Only flat archive paths are accepted")
            (source / name).write_bytes(z.read(name))
    report = json.loads((source / "report.json").read_text())
    if report["synthetic_data_used"] is not False or report["reserved_2025_used"] is not False:
        raise ValueError("Expected the pre-2025 market development screen")
    if report["candidate_registry"] != registry() or report["scenarios"] != [list(s) for s in SCENARIOS]:
        raise ValueError("Trial registry/scenario mismatch")
    for name, expected in report["files"].items():
        if Path(name).name != name or "\\" in name or sha(source / name) != expected:
            raise ValueError(f"Artifact hash mismatch: {name}")
    code_modes = {}
    for name, expected in report["code_sha256"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Invalid code path")
        content = subprocess.check_output(["git", "show", f"{report['commit']}:{name}"], cwd=ROOT)
        content = content.replace(b"\r\n", b"\n")
        variants = dict(LF=content, CRLF=content.replace(b"\n", b"\r\n"))
        matches = [mode for mode, value in variants.items() if hashlib.sha256(value).hexdigest() == expected]
        if not matches or (ROOT / name).read_bytes().replace(b"\r\n", b"\n") != content:
            raise ValueError(f"Pinned/working code mismatch: {name}")
        code_modes[name] = matches[0]
    if sha(source / "specification.md") != report["code_sha256"]["docs/research/FRESH_CRYPTO_DISCOVERY_20260914.md"]:
        raise ValueError("Archived specification mismatch")
    frames = {a: normalize(pd.read_csv(source / f"{a}-USD.csv", float_precision="round_trip"))[0] for a in ASSETS}
    if not frames["BTC"].index.equals(frames["ETH"].index):
        raise ValueError("Input calendar mismatch")
    for a in ASSETS:
        if sha(source / f"{a}-USD.csv") != report["data"][a]["normalized_sha256"]:
            raise ValueError("Normalized input identity mismatch")
    original = pd.read_csv(source / "daily_ledger.csv", float_precision="round_trip")
    summary = pd.read_csv(source / "metrics.csv", float_precision="round_trip")
    orders, targets = schedules(frames)
    target_differences = compare(targets, pd.read_csv(source / "target_weights.csv", float_precision="round_trip"))
    deltas, identities, deletions = {}, [], []
    for scenario, cost, delay in SCENARIOS:
        for policy in policies():
            saved = original[(original.scenario == scenario) & (original.policy == policy.name)].reset_index(drop=True)
            replay = simulate(frames, orders[policy.name], cost, delay)
            for key, value in compare(replay, saved[replay.columns]).items():
                deltas[key] = max(value, deltas.get(key, 0.))
            r = saved["return"].to_numpy()
            wealth = np.cumprod(1+r)
            if not np.allclose(wealth, saved.nav, rtol=2e-10, atol=2e-11):
                raise ValueError("Independent wealth reconstruction failed")
            if not np.allclose(saved.BTC_pnl+saved.ETH_pnl, r, atol=2e-11, rtol=2e-10):
                raise ValueError("Independent asset P&L identity failed")
            if not np.allclose(saved.BTC_weight+saved.ETH_weight+saved.USD_weight, 1., atol=2e-11):
                raise ValueError("Full-equity weights failed")
            peak = np.maximum.accumulate(np.r_[1., wealth])[1:]
            years = (pd.Timestamp(saved.date.iloc[-1])-pd.Timestamp(saved.date.iloc[0])).days/365.25
            row = summary[(summary.scenario == scenario) & (summary.policy == policy.name) & (summary.period == "full")].iloc[0]
            if not np.isclose(row.cagr, wealth[-1]**(1/years)-1, atol=2e-11):
                raise ValueError("Independent CAGR failed")
            if not np.isclose(row.max_drawdown, (wealth/peak-1).min(), atol=2e-11):
                raise ValueError("Independent drawdown failed")
            for period, subset in (("full", saved), ("through_2020", saved[saved.date < "2021-01-01"]),
                                   ("2021_2024", saved[saved.date >= "2021-01-01"])):
                if len(subset) >= 180:
                    metrics_row = summary[(summary.scenario == scenario) & (summary.policy == policy.name) & (summary.period == period)].iloc[0]
                    for key, value in metrics(subset).items():
                        if not np.isclose(value, metrics_row[key], atol=2e-10, rtol=2e-10, equal_nan=True):
                            raise ValueError(f"Metric reconstruction failed: {key}")
            if policy.family in ("btc_buy_hold", "eth_buy_hold", "mix_buy_hold"):
                weights = dict(btc_buy_hold=[1., 0.], eth_buy_hold=[0., 1.], mix_buy_hold=[.5, .5])[policy.name]
                ratios = np.array([frames[a].open.iloc[-1]/frames[a].open.iloc[WARMUP+2+delay] for a in ASSETS])
                rate = cost/10_000
                expected = float(np.array(weights) @ ratios)*(1-rate)/(1+rate)
                identities.append(dict(policy=policy.name, scenario=scenario, expected=expected,
                                       reported=float(saved.nav.iloc[-1]), residual=float(saved.nav.iloc[-1]-expected)))
                if not np.isclose(saved.nav.iloc[-1], expected, atol=2e-10, rtol=2e-10):
                    raise ValueError("Closed-form buy-and-hold identity failed")
            if scenario == "base":
                for year in sorted(saved.date.str[:4].unique()):
                    remaining = saved[saved.date.str[:4] != year]["return"].to_numpy()
                    sd = remaining.std(ddof=1)
                    deletions.append(dict(policy=policy.name, excluded_year=int(year),
                                          remaining_days=len(remaining), cash_excess_sharpe=float(remaining.mean()/sd*np.sqrt(365)) if sd>1e-12 else np.nan))
        print(f"Verified {scenario}: all 16 ledgers, metrics and benchmark identities", flush=True)
    # The numerical comparison must also detect a deliberately corrupted return.
    probe = pd.DataFrame({"return": [0., .01]})
    corrupt = pd.DataFrame({"return": [0., .011]})
    try:
        compare(probe, corrupt)
    except ValueError:
        pass
    else:
        raise ValueError("Replay corruption canary did not fail")
    pd.DataFrame(deletions).to_csv(out / "leave_one_year_out.csv", index=False, lineterminator="\n", float_format="%.17g")
    pd.DataFrame(identities).to_csv(out / "buy_hold_identities.csv", index=False, lineterminator="\n", float_format="%.17g")
    evidence = dict(status="FIXED_DEVELOPMENT_SCREEN_AUDITED_NOT_OOS", archive_sha256=sha(archive),
                    source_commit=report["commit"], archive_files_verified=len(report["files"]),
                    code_hash_modes=code_modes, source_calendar_days=len(frames["BTC"]),
                    normalized_prices_and_calendars_verified=True, original_full_source_files_available=False,
                    original_vendor_and_acquisition_provenance_independently_verified=False,
                    source_environment=report["environment"], reviewer_environment=dict(python=platform.python_version(),
                    numpy=np.__version__, pandas=pd.__version__), ledgers_replayed=64, daily_rows=len(original),
                    independent_buy_hold_checks=len(identities), metric_reconstruction_passed=True,
                    maximum_replay_differences=deltas, target_replay_differences=target_differences,
                    corruption_canary_passed=True, model_fits=0, new_strategy_variants=0, holdout_evaluations=0,
                    deletion_diagnostic="Historical sensitivity; days are omitted, no refit or Monte Carlo inference")
    write_json(out / "review_audit.json", evidence)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    audit(args.archive, args.output_dir)
    print(f"Audit outputs: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
