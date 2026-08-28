"""Download price series for exactly the markets the cross-sectional COT probe included.

Reads `artifacts/cot_cross_sectional_universe_probe.json` and downloads each INCLUDED ticker via
the existing, already-proven `scripts/download_equity_data.py` rather than reimplementing the
fetch. Driving the download from the probe's own artifact -- instead of a hand-typed list of 35
tickers -- means the downloaded set is by construction the set that was probed and validated.
That matters here specifically: this session has already produced one silently mismatched
COT-market/ticker pair (sterling positioning against a EUR/GBP cross-rate), and a transcription
slip across 35 tickers would reintroduce exactly that class of error where nothing downstream
would catch it.

Skips tickers already downloaded unless --overwrite is passed. Reports per-ticker success and
failure and never leaves a partial set unreported.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOWNLOADER = REPO_ROOT / "scripts" / "download_equity_data.py"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--probe-json", default="artifacts/cot_cross_sectional_universe_probe.json")
    p.add_argument("--out-dir", default="data")
    p.add_argument("--start", default="2005-01-01")
    p.add_argument("--end", default=None, help="Defaults to today.")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="List what would be downloaded, fetch nothing.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    probe_path = Path(args.probe_json)
    if not probe_path.exists():
        print(f"Probe artifact not found: {probe_path}")
        print("Run scripts/probe_cot_cross_sectional_universe.py first -- the universe must be")
        print("established and validated before any price data is fetched against it.")
        return 1

    payload = json.loads(probe_path.read_text(encoding="utf-8"))
    included = [r for r in payload.get("results", []) if r.get("included")]
    if not included:
        print("Probe artifact lists no included markets. Nothing to download.")
        return 1

    from datetime import date
    end = args.end or date.today().isoformat()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Probe artifact: {probe_path}")
    print(f"Generated: {payload.get('generated_at_utc')}")
    print(f"{len(included)} included markets to fetch, {args.start} -> {end}\n")

    todo, already = [], []
    for r in included:
        ticker = r["ticker"]
        expected = out_dir / f"{ticker.upper()}_1D.csv"
        (already if expected.exists() and not args.overwrite else todo).append((r, expected))

    for r, path in already:
        print(f"  SKIP {r['ticker']:<8} ({r['label']}) -- {path.name} exists; --overwrite to refetch")
    if already:
        print()

    if args.dry_run:
        print(f"DRY RUN: would fetch {len(todo)} ticker(s): " + ", ".join(r["ticker"] for r, _ in todo))
        return 0
    if not todo:
        print("Everything already downloaded. Nothing to do.")
        return 0

    def build_cmd(ticker: str) -> list[str]:
        cmd = [sys.executable, str(DOWNLOADER), "--asset", ticker,
               "--start", args.start, "--end", end, "--output-dir", str(out_dir)]
        if args.overwrite:
            cmd.append("--overwrite")
        return cmd

    # Pre-flight: confirm the downloader actually accepts these flags BEFORE looping. An earlier
    # version passed --out-dir (the real flag is --output-dir) and failed 34 times identically
    # before the operator interrupted it. A wrong invocation should fail once, not once per
    # ticker, and the argparse error is a usage bug in this script rather than a data problem --
    # worth separating loudly.
    help_proc = subprocess.run([sys.executable, str(DOWNLOADER), "--help"],
                               capture_output=True, text=True, cwd=str(REPO_ROOT))
    if help_proc.returncode != 0:
        print(f"Could not run {DOWNLOADER.name} --help; aborting before fetching anything.")
        return 1
    for flag in ("--asset", "--start", "--end", "--output-dir"):
        if flag not in help_proc.stdout:
            print(f"{DOWNLOADER.name} does not accept {flag} -- this script's invocation is wrong.")
            print("Aborting before the fetch loop rather than failing once per ticker.")
            return 1

    ok, failed = [], []
    for i, (r, _path) in enumerate(todo, 1):
        ticker, label = r["ticker"], r["label"]
        print(f"[{i}/{len(todo)}] {ticker} ({label}) ...", flush=True)
        proc = subprocess.run(build_cmd(ticker), capture_output=True, text=True, cwd=str(REPO_ROOT))
        if proc.returncode == 0:
            ok.append(ticker)
        else:
            tail = (proc.stderr or proc.stdout).strip().splitlines()
            message = tail[-1] if tail else "unknown error"
            failed.append((ticker, label, message))
            print(f"    FAILED: {message[:110]}")
            # An argparse usage error is this script's fault and will repeat for every ticker;
            # stop rather than burning through the rest of the universe producing the same line.
            if "unrecognized arguments" in message or "error: argument" in message:
                print("\nThat is a usage error in this script, not a data problem -- it will repeat")
                print("for every remaining ticker. Stopping now.")
                break

    print(f"\n{'='*70}")
    print(f"{len(ok)} downloaded, {len(already)} already present, {len(failed)} failed "
          f"(of {len(included)} included markets)")
    print(f"{'='*70}")
    if failed:
        print("Failures (a market without prices cannot enter the cross-section):")
        for ticker, label, err in failed:
            print(f"  {ticker} ({label}): {err[:100]}")
        print("\nThese must be either resolved or explicitly dropped from the universe before the")
        print("analysis runs -- silently proceeding with a smaller set than the probe validated")
        print("would make the recorded universe and the tested universe disagree.")
    else:
        print("All included markets have price data. The cross-section is ready to build against.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
