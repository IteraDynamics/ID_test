"""Core v1 live benchmark engine.

Implements the pre-registered live comparators of
``docs/research/CORE_V1_LIVE_BENCHMARK_REGISTRATION.md``:

- Benchmark A: static-weight six-sleeve twin of canonical Core v1;
- Benchmark B: 60% SPY / 40% cash (0% accrual).

The engine is deterministic, stdlib-only, observation-only, and fail-closed. It
computes benchmark NAV series from governed daily and hourly close sources and
serializes canonical LF-only artifacts. It never touches the paper runtime, the
live NAV record, orders, or production behavior.

Frozen measurement details implemented here are recorded in the registration
document's implementation record and may not be changed after governed
benchmark results have been generated.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

EXPECTED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")

CASH_ASSET = "CASH"

BENCHMARK_A_WEIGHTS: Mapping[str, float] = {
    "BTC": 0.15,
    "ETH": 0.20,
    "SPY": 0.175,
    "QQQ": 0.275,
    "GLD": 0.20,
}

BENCHMARK_B_WEIGHTS: Mapping[str, float] = {
    "SPY": 0.60,
    CASH_ASSET: 0.40,
}

# Fee assumptions match scripts/export_core_v1_canonical_sleeve_matrix.py defaults.
DEFAULT_CRYPTO_FEE = 0.0006
DEFAULT_EQUITY_FEE = 0.0001

DEFAULT_FEES: Mapping[str, float] = {
    "BTC": DEFAULT_CRYPTO_FEE,
    "ETH": DEFAULT_CRYPTO_FEE,
    "SPY": DEFAULT_EQUITY_FEE,
    "QQQ": DEFAULT_EQUITY_FEE,
    "GLD": DEFAULT_EQUITY_FEE,
    CASH_ASSET: 0.0,
}

# Assets whose fresh close defines an eligible rebalance session.
EQUITY_FAMILY_ASSETS = ("SPY", "QQQ", "GLD")

REGISTERED_INCEPTION = date(2026, 7, 7)
REGISTERED_STARTING_CAPITAL = 100_000.0

ANNUALIZATION_DAYS = 365.25


class LiveBenchmarkError(ValueError):
    pass


@dataclass(frozen=True)
class BenchmarkConfig:
    name: str
    weights: Mapping[str, float]
    fees: Mapping[str, float]
    inception: date
    end: date
    starting_capital: float

    def validate(self) -> None:
        if self.end < self.inception:
            raise LiveBenchmarkError("CONFIG_FAILURE: end precedes inception")
        if self.starting_capital <= 0:
            raise LiveBenchmarkError("CONFIG_FAILURE: non-positive starting capital")
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-9:
            raise LiveBenchmarkError(f"CONFIG_FAILURE: weights sum to {total!r}, not 1.0")
        for asset, weight in self.weights.items():
            if weight <= 0:
                raise LiveBenchmarkError(f"CONFIG_FAILURE: non-positive weight for {asset}")
            if asset not in self.fees:
                raise LiveBenchmarkError(f"CONFIG_FAILURE: missing fee for {asset}")
        if self.fees.get(CASH_ASSET, 0.0) != 0.0:
            raise LiveBenchmarkError("CONFIG_FAILURE: cash fee must be zero")


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    dates: tuple[date, ...]
    nav: tuple[float, ...]
    rebalance_dates: tuple[date, ...]
    total_fees: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def canonical_csv_bytes(fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fieldnames), lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    return stream.getvalue().encode("utf-8")


def parse_timestamp(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise LiveBenchmarkError(f"SOURCE_SCHEMA_FAILURE: invalid timestamp {raw!r}") from exc


def _read_rows(path: Path) -> Iterable[tuple[int, datetime, float]]:
    if not path.exists():
        raise LiveBenchmarkError(f"SOURCE_IDENTITY_FAILURE: missing {path.name}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise LiveBenchmarkError(f"SOURCE_SCHEMA_FAILURE: {path.name}")
        for row_number, row in enumerate(reader, start=2):
            stamp = parse_timestamp(row["timestamp"])
            try:
                close = float(row["close"])
            except ValueError as exc:
                raise LiveBenchmarkError(f"SOURCE_SCHEMA_FAILURE: {path.name}:{row_number}") from exc
            if not math.isfinite(close) or close <= 0:
                raise LiveBenchmarkError(f"SOURCE_SCHEMA_FAILURE: {path.name}:{row_number}")
            yield row_number, stamp, close


def load_daily_closes(path: Path) -> dict[date, float]:
    """Load a normalized daily OHLCV CSV into an ordered date -> close mapping."""
    closes: dict[date, float] = {}
    previous: date | None = None
    for row_number, stamp, close in _read_rows(path):
        session = stamp.date()
        if previous is not None and session <= previous:
            raise LiveBenchmarkError(f"SOURCE_ORDER_FAILURE: {path.name}:{row_number}")
        closes[session] = close
        previous = session
    if not closes:
        raise LiveBenchmarkError(f"SOURCE_SCHEMA_FAILURE: {path.name}: no rows")
    return closes


def daily_closes_from_hourly(path: Path) -> dict[date, float]:
    """Derive daily closes from a governed hourly source.

    The daily close for a UTC day is the close of the last hourly bar observed
    within that day. Days are only present when at least one bar exists; no
    interpolation, filling, or repair is performed.
    """
    closes: dict[date, float] = {}
    previous_stamp: datetime | None = None
    for row_number, stamp, close in _read_rows(path):
        if previous_stamp is not None and stamp <= previous_stamp:
            raise LiveBenchmarkError(f"SOURCE_ORDER_FAILURE: {path.name}:{row_number}")
        closes[stamp.date()] = close
        previous_stamp = stamp
    if not closes:
        raise LiveBenchmarkError(f"SOURCE_SCHEMA_FAILURE: {path.name}: no rows")
    return closes


def _last_close_on_or_before(
    closes: Mapping[date, float], session: date, asset: str
) -> float:
    price = None
    for known, value in closes.items():
        if known > session:
            break
        price = value
    if price is None:
        raise LiveBenchmarkError(f"VALUATION_FAILURE: no {asset} close on or before {session.isoformat()}")
    return price


def build_static_benchmark(
    config: BenchmarkConfig,
    closes_by_asset: Mapping[str, Mapping[date, float]],
) -> BenchmarkResult:
    """Compute a static-weight benchmark NAV series under the frozen rules.

    Rules (frozen in the registration document's implementation record):

    - initial positions are bought at inception-date closes; each non-cash
      sleeve deploys weight * capital as traded notional plus fee, i.e.
      ``notional = weight * capital / (1 + fee)``;
    - the valuation calendar is the union of all asset session dates within
      ``[inception, end]``; assets without a fresh close on a valuation date
      are carried at their last known close;
    - the benchmark rebalances to target weights at the first session of each
      later calendar month on which every equity-family asset in the benchmark
      has a fresh close; trades execute at that session's closes with fees on
      absolute turnover notional, targets sized against fee-adjusted NAV.
    """
    config.validate()
    risk_assets = [asset for asset in config.weights if asset != CASH_ASSET]
    for asset in risk_assets:
        if asset not in closes_by_asset:
            raise LiveBenchmarkError(f"SOURCE_IDENTITY_FAILURE: no close series for {asset}")
        if config.inception not in closes_by_asset[asset]:
            raise LiveBenchmarkError(
                f"VALUATION_FAILURE: no {asset} close on inception {config.inception.isoformat()}"
            )

    calendar = sorted(
        {
            session
            for asset in risk_assets
            for session in closes_by_asset[asset]
            if config.inception <= session <= config.end
        }
    )
    if not calendar or calendar[0] != config.inception:
        raise LiveBenchmarkError("VALUATION_FAILURE: inception missing from valuation calendar")

    equity_members = [asset for asset in risk_assets if asset in EQUITY_FAMILY_ASSETS]

    units: dict[str, float] = {}
    total_fees = 0.0
    cash = config.weights.get(CASH_ASSET, 0.0) * config.starting_capital
    for asset in risk_assets:
        gross = config.weights[asset] * config.starting_capital
        fee_rate = config.fees[asset]
        notional = gross / (1.0 + fee_rate)
        price = closes_by_asset[asset][config.inception]
        units[asset] = notional / price
        total_fees += notional * fee_rate

    dates: list[date] = []
    nav_series: list[float] = []
    rebalance_dates: list[date] = []
    rebalanced_months: set[tuple[int, int]] = {(config.inception.year, config.inception.month)}

    for session in calendar:
        prices = {
            asset: _last_close_on_or_before(closes_by_asset[asset], session, asset)
            for asset in risk_assets
        }
        nav = cash + sum(units[asset] * prices[asset] for asset in risk_assets)

        month = (session.year, session.month)
        equities_fresh = all(session in closes_by_asset[asset] for asset in equity_members)
        if month not in rebalanced_months and (equities_fresh or not equity_members):
            fee_estimate = 0.0
            for asset in risk_assets:
                naive_target_units = config.weights[asset] * nav / prices[asset]
                fee_estimate += abs(naive_target_units - units[asset]) * prices[asset] * config.fees[asset]
            deployable = nav - fee_estimate
            if deployable <= 0:
                raise LiveBenchmarkError(f"VALUATION_FAILURE: NAV exhausted at {session.isoformat()}")
            fee_paid = 0.0
            for asset in risk_assets:
                target_units = config.weights[asset] * deployable / prices[asset]
                fee_paid += abs(target_units - units[asset]) * prices[asset] * config.fees[asset]
                units[asset] = target_units
            cash = nav - fee_paid - sum(units[asset] * prices[asset] for asset in risk_assets)
            total_fees += fee_paid
            rebalanced_months.add(month)
            rebalance_dates.append(session)
            nav = cash + sum(units[asset] * prices[asset] for asset in risk_assets)

        dates.append(session)
        nav_series.append(nav)

    return BenchmarkResult(
        name=config.name,
        dates=tuple(dates),
        nav=tuple(nav_series),
        rebalance_dates=tuple(rebalance_dates),
        total_fees=total_fees,
    )


def compute_metrics(result: BenchmarkResult, starting_capital: float) -> dict[str, object]:
    final_nav = result.nav[-1]
    cumulative_return = final_nav / starting_capital - 1.0
    elapsed_days = max((result.dates[-1] - result.dates[0]).days, 1)
    annualized_return = (final_nav / starting_capital) ** (ANNUALIZATION_DAYS / elapsed_days) - 1.0

    peak = -math.inf
    max_drawdown = 0.0
    for value in result.nav:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, 1.0 - value / peak)

    calmar = annualized_return / max_drawdown if max_drawdown > 0 else None

    returns = [
        result.nav[index] / result.nav[index - 1] - 1.0 for index in range(1, len(result.nav))
    ]
    sharpe = None
    if len(returns) >= 2:
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        if variance > 0:
            sharpe = mean / math.sqrt(variance) * math.sqrt(ANNUALIZATION_DAYS)

    return {
        "benchmark": result.name,
        "start_date": result.dates[0].isoformat(),
        "end_date": result.dates[-1].isoformat(),
        "observations": len(result.nav),
        "starting_capital": starting_capital,
        "final_nav": round(final_nav, 6),
        "cumulative_return": round(cumulative_return, 8),
        "annualized_return": round(annualized_return, 8),
        "max_drawdown": round(max_drawdown, 8),
        "calmar": round(calmar, 8) if calmar is not None else None,
        "sharpe_zero_benchmark": round(sharpe, 8) if sharpe is not None else None,
        "rebalance_count": len(result.rebalance_dates),
        "rebalance_dates": [session.isoformat() for session in result.rebalance_dates],
        "total_fees": round(result.total_fees, 6),
    }


def nav_csv_bytes(result: BenchmarkResult) -> bytes:
    rows = [
        {"date": session.isoformat(), "nav": f"{value:.6f}"}
        for session, value in zip(result.dates, result.nav)
    ]
    return canonical_csv_bytes(("date", "nav"), rows)
