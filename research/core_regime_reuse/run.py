"""Export isolated BTC/ETH state ledgers; no strategy or trading execution."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import zipfile

import numpy as np
import pandas as pd

from research.harness.resampler import resample_ohlcv
from research.core_regime_reuse.adapter import CoreRegimeReader, validate_frame


def prepare_hourly(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("timestamp"), utc=True))
    validate_frame(df)
    if not (df.index == df.index.floor("h")).all():
        raise ValueError("Expected UTC hour-start timestamps")
    if "volume" in df and (not np.isfinite(df.volume).all() or (df.volume < 0).any()):
        raise ValueError("Invalid volume")
    return df


def completed_frame(hourly: pd.DataFrame, hours: int, asof: pd.Timestamp) -> pd.DataFrame:
    if hours not in (1, 4):
        raise ValueError("This runner supports only 1H and 4H crypto")
    eligible = hourly.loc[hourly.index + pd.Timedelta(hours=1) <= asof]
    if eligible.empty:
        raise ValueError("No completed hourly input")
    bars = eligible.copy() if hours == 1 else resample_ohlcv(eligible, "4h")
    return bars.loc[bars.index + pd.Timedelta(hours=hours) <= asof].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts"))
    parser.add_argument("--btc-csv", type=Path)
    parser.add_argument("--eth-csv", type=Path)
    args = parser.parse_args()
    reader = CoreRegimeReader()
    sources = {
        "BTC": args.btc_csv or args.data_root / "btcusd_3600s_2018-01-01_to_2025-12-31.csv",
        "ETH": args.eth_csv or args.data_root / "ethusd_3600s_2018-01-01_to_2025-12-31.csv",
    }
    # Validate both sources before producing a successful report.
    frames = {asset: prepare_hourly(path) for asset, path in sources.items()}
    out = args.output_root / ("core_regime_reuse_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "research_classifier_reuse_only", "source_lock": reader.source_lock,
        "versions": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "scope": "Full supplied history; not a replay of Core fold resets or live input windows. No P&L computed.",
        "timing": "UTC bucket-start input; state available at bucket end, before any additional vendor/execution latency.",
        "gaps": "Missing hours are not filled; internal partial 4H bins retained as in Core resampler and counted below.",
        "confidence": "Engine heuristic score, not a calibrated probability.",
        "sources": {}, "ledgers": {},
    }
    for asset, hourly in frames.items():
        asof = hourly.index[-1] + pd.Timedelta(hours=1)
        expected = int((hourly.index[-1] - hourly.index[0]) / pd.Timedelta(hours=1)) + 1
        report["sources"][asset] = {
            "path": str(sources[asset].resolve()), "sha256": hashlib.sha256(sources[asset].read_bytes()).hexdigest(),
            "rows": len(hourly), "missing_hours": expected - len(hourly),
            "first": str(hourly.index[0]), "last": str(hourly.index[-1]),
        }
        for hours in (1, 4):
            bars = completed_frame(hourly, hours, asof)
            signals = reader.history(bars)
            # Sample prefix equality against the exact method called by Core paper.
            positions = sorted(set([0, min(59, len(bars)-1), min(60, len(bars)-1), *np.linspace(0, len(bars)-1, 20, dtype=int).tolist()]))
            for i in positions:
                if asdict(signals[i]) != asdict(reader.snapshot(bars.iloc[:i+1])):
                    raise AssertionError(f"Snapshot parity failed: {asset} {hours}H {i}")
            name = f"{asset}_{hours}H"
            rows = [{"bar_start": str(ts), "available_at": str(ts + pd.Timedelta(hours=hours)),
                     "regime": s.label.value, "confidence": s.confidence,
                     "sub_signals": json.dumps(s.sub_signals, sort_keys=True)}
                    for ts, s in zip(bars.index, signals)]
            ledger = pd.DataFrame(rows)
            ledger.to_csv(out / f"{name}.csv", index=False)
            counts = hourly.close.resample(f"{hours}h").count().reindex(bars.index)
            report["ledgers"][name] = {"rows": len(rows), "prefix_checks": len(positions),
                "partial_source_bins": int((counts < hours).sum()),
                "regime_counts": ledger.regime.value_counts().to_dict()}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    archive = out.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(out.iterdir()):
            z.write(path, path.name)
    print(json.dumps(report["ledgers"], indent=2))
    print(f"SHARE RESULTS ZIP: {archive.resolve()}")


if __name__ == "__main__":
    main()
