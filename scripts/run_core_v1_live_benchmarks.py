"""Governed runner for the pre-registered Core v1 live benchmarks.

Computes Benchmark A (static-weight six-sleeve twin) and Benchmark B
(60% SPY / 40% cash) per docs/research/CORE_V1_LIVE_BENCHMARK_REGISTRATION.md,
writes canonical LF-only artifacts, and verifies replay identity by computing
every artifact twice in-memory and failing closed on any byte difference.

Observation-only: no runtime, strategy, order, NAV, exposure, or production
behavior is read or modified.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.live_benchmarks import (
    BENCHMARK_A_WEIGHTS,
    BENCHMARK_B_WEIGHTS,
    CASH_ASSET,
    DEFAULT_CRYPTO_FEE,
    DEFAULT_EQUITY_FEE,
    REGISTERED_INCEPTION,
    REGISTERED_STARTING_CAPITAL,
    BenchmarkConfig,
    LiveBenchmarkError,
    build_static_benchmark,
    canonical_json_bytes,
    compute_metrics,
    daily_closes_from_hourly,
    load_daily_closes,
    nav_csv_bytes,
    sha256_file,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compute the pre-registered Core v1 live benchmark series.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", default="data/btcusd_3600s_2026-01-01_to_2026-07-31.csv", help="Governed BTC hourly CSV.")
    p.add_argument("--eth-data", default="data/ethusd_3600s_2026.csv", help="Governed ETH hourly CSV.")
    p.add_argument("--spy-data", default="data/SPY_1D.csv", help="Governed SPY daily CSV.")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv", help="Governed QQQ daily CSV.")
    p.add_argument("--gld-data", default="data/GLD_1D.csv", help="Governed GLD daily CSV.")
    p.add_argument("--inception", default=REGISTERED_INCEPTION.isoformat(), help="Registered live inception date.")
    p.add_argument("--end", required=True, help="Last valuation date (inclusive), e.g. the letter period end.")
    p.add_argument("--starting-capital", type=float, default=REGISTERED_STARTING_CAPITAL)
    p.add_argument("--crypto-fee", type=float, default=DEFAULT_CRYPTO_FEE)
    p.add_argument("--equity-fee", type=float, default=DEFAULT_EQUITY_FEE)
    p.add_argument("--out-dir", default="artifacts/core_v1_live_benchmarks")
    return p.parse_args(argv)


def _compute_artifacts(args: argparse.Namespace) -> dict[str, bytes]:
    inception = date.fromisoformat(args.inception)
    end = date.fromisoformat(args.end)

    sources = {
        "BTC": Path(args.btc_data),
        "ETH": Path(args.eth_data),
        "SPY": Path(args.spy_data),
        "QQQ": Path(args.qqq_data),
        "GLD": Path(args.gld_data),
    }
    closes = {
        "BTC": daily_closes_from_hourly(sources["BTC"]),
        "ETH": daily_closes_from_hourly(sources["ETH"]),
        "SPY": load_daily_closes(sources["SPY"]),
        "QQQ": load_daily_closes(sources["QQQ"]),
        "GLD": load_daily_closes(sources["GLD"]),
    }
    fees = {
        "BTC": args.crypto_fee,
        "ETH": args.crypto_fee,
        "SPY": args.equity_fee,
        "QQQ": args.equity_fee,
        "GLD": args.equity_fee,
        CASH_ASSET: 0.0,
    }

    config_a = BenchmarkConfig(
        name="benchmark_a_static_twin",
        weights=BENCHMARK_A_WEIGHTS,
        fees=fees,
        inception=inception,
        end=end,
        starting_capital=args.starting_capital,
    )
    config_b = BenchmarkConfig(
        name="benchmark_b_60_40",
        weights=BENCHMARK_B_WEIGHTS,
        fees=fees,
        inception=inception,
        end=end,
        starting_capital=args.starting_capital,
    )

    result_a = build_static_benchmark(config_a, closes)
    result_b = build_static_benchmark(config_b, {"SPY": closes["SPY"]})

    metrics = {
        "benchmark_a_static_twin": compute_metrics(result_a, args.starting_capital),
        "benchmark_b_60_40": compute_metrics(result_b, args.starting_capital),
    }

    manifest = {
        "registration_document": "docs/research/CORE_V1_LIVE_BENCHMARK_REGISTRATION.md",
        "inception": inception.isoformat(),
        "end": end.isoformat(),
        "starting_capital": args.starting_capital,
        "crypto_fee": args.crypto_fee,
        "equity_fee": args.equity_fee,
        "benchmark_a_weights": dict(BENCHMARK_A_WEIGHTS),
        "benchmark_b_weights": dict(BENCHMARK_B_WEIGHTS),
        "sources": {
            asset: {
                "path": str(path).replace("\\", "/"),
                "sha256": sha256_file(path),
                "daily_sessions_loaded": len(closes[asset]),
            }
            for asset, path in sorted(sources.items())
        },
        "runtime_modified": False,
        "paper_record_modified": False,
    }

    return {
        "benchmark_a_nav.csv": nav_csv_bytes(result_a),
        "benchmark_b_nav.csv": nav_csv_bytes(result_b),
        "benchmark_metrics.json": canonical_json_bytes(metrics),
        "manifest.json": canonical_json_bytes(manifest),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    first_pass = _compute_artifacts(args)
    second_pass = _compute_artifacts(args)
    for name in first_pass:
        if first_pass[name] != second_pass[name]:
            raise LiveBenchmarkError(f"REPLAY_IDENTITY_FAILURE: {name}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print("status: PASS (replay identity verified across two in-memory passes)")
    for name, payload in first_pass.items():
        (out_dir / name).write_bytes(payload)
        print(f"{name}: sha256 {hashlib.sha256(payload).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
