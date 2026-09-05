"""Compare independent baseline/refactor ML CLIs using synthetic inputs only.

Usage: python scripts/verify_refactor_ml_parity.py --baseline-root /path/to/worktree
The baseline must be a checkout of 83e4e11. No market data or network is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

BASELINE_SHA = "83e4e119a2a7954c470a797a590e5d9c8213d353"
SOURCE = "RSP MDY IWM IWD IWF XLB XLE XLF XLI XLK XLP XLU XLV XLY".split()
DESTINATION = "EWA EWC EWG EWH EWI EWJ EWL EWM EWW EWP EWS EWT EWU EWZ".split()


def fixture(root: Path) -> None:
    calendar = pd.bdate_range("2018-01-01", "2022-02-28", tz="UTC", name="timestamp")
    for dirname, tickers, offset in [("source", SOURCE + ["VIX"], 0), ("destination", DESTINATION, 100)]:
        folder = root / dirname
        folder.mkdir(exist_ok=True)
        for i, ticker in enumerate(tickers):
            rng = np.random.default_rng(offset + i)
            close = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.012, len(calendar))))
            pd.DataFrame({"open": close * .999, "high": close * 1.01,
                          "low": close * .99, "close": close,
                          "volume": rng.integers(100_000, 1_000_000, len(calendar))},
                         index=calendar).to_csv(folder / f"{ticker}_1D.csv")
    cache = root / "009/source_cache"
    cache.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(300)
    for i, series in enumerate(("DGS2", "DGS10", "DGS3MO")):
        pd.DataFrame({"DATE": calendar, series: 2 + i + np.cumsum(rng.normal(0, .025, len(calendar)))}).to_csv(cache / f"{series}.csv", index=False)


def check_outputs_equal(before: dict[str, bytes], after: dict[str, bytes]) -> None:
    if before.keys() != after.keys():
        raise AssertionError(f"Artifact inventory changed: {before.keys() ^ after.keys()}")
    changed = [name for name in before if before[name] != after[name]]
    if changed:
        raise AssertionError(f"Artifact bytes changed: {changed}")


def run(repo: Path, root: Path) -> dict[str, bytes]:
    options = {
        5: ["--data-dir", root / "source"],
        6: ["--data-dir", root / "source", "--exp005-dir", root / "005"],
        7: ["--data-dir", root / "source"],
        8: ["--predictions", root / "007/experiment_007_oos_predictions.csv"],
        9: ["--data-dir", root / "source"],
        10: ["--data-dir", root / "source", "--source-dir", root / "009"],
        11: ["--source-data-dir", root / "source", "--destination-data-dir", root / "destination", "--experiment-009-dir", root / "009"],
    }
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONPATH", None)
    for num, args in options.items():
        print(f"{repo.name}: Experiment {num:03}", flush=True)
        script = repo / f"scripts/run_ml_lab_experiment_{num:03}.py"
        result = subprocess.run([sys.executable, str(script), *map(str, args), "--output-dir", str(root / f"{num:03}")], cwd=repo, env=env, capture_output=True, text=True, timeout=300)
        if result.returncode:
            raise RuntimeError(f"{script.name}: {result.stderr}")
    return {str(p.relative_to(root)): p.read_bytes() for n in options for p in sorted((root / f"{n:03}").rglob("*")) if p.is_file()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", required=True, type=Path)
    args = parser.parse_args()
    baseline = args.baseline_root.resolve()
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=baseline, text=True).strip()
    if sha != BASELINE_SHA:
        raise ValueError(f"Expected baseline {BASELINE_SHA}, found {sha}")
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=baseline, text=True).strip():
        raise ValueError("Baseline has tracked modifications")
    # Prove the comparator fails for corruption and missing outputs.
    for broken in ({"x": b"changed"}, {}):
        try:
            check_outputs_equal({"x": b"original"}, broken)
        except AssertionError:
            pass
        else:
            raise AssertionError("Parity canary failed to detect changed output")
    with tempfile.TemporaryDirectory(prefix="itera-refactor-parity-") as temp:
        root = Path(temp)
        fixture(root)
        before = run(baseline, root)
        for n in range(5, 12):
            shutil.rmtree(root / f"{n:03}")
        fixture(root)
        after = run(Path(__file__).resolve().parents[1], root)
        check_outputs_equal(before, after)
        print(json.dumps({"status": "PASS", "baseline": sha, "experiments": list(range(5,12)), "artifacts_byte_identical": len(before), "digest": hashlib.sha256(b"".join(before[k] for k in sorted(before))).hexdigest(), "scope": "Synthetic migration parity only; no historical market inputs"}, indent=2))


if __name__ == "__main__":
    main()
