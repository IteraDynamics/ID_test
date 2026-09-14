"""Close-of-session signals; the engine enforces the next-session boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .data import INDEX, SECTORS


@dataclass(frozen=True)
class Candidate:
    name: str
    family: str
    mode: str = "full"
    lookback: int = 0
    hold: int = 1
    threshold: float = 0.0
    trend_filter: bool = False
    benchmark: bool = False

    def record(self) -> dict:
        return asdict(self)


def registry() -> list[Candidate]:
    candidates = []
    for threshold in (1.5, 2.0):
        for hold in (1, 3, 5):
            for trend in (False, True):
                name = f"shock_z{threshold:g}_h{hold}_trend{int(trend)}"
                candidates.append(Candidate(name, "shock", hold=hold,
                                            threshold=threshold, trend_filter=trend))
    for lookback in (3, 5, 10):
        for hold in (1, 3):
            candidates.append(Candidate(f"sector_residual_l{lookback}_h{hold}",
                                        "sector_residual", lookback=lookback, hold=hold))
    for lookback in (21, 63, 126):
        for mode in ("full", "night"):
            candidates.append(Candidate(f"session_balance_l{lookback}_{mode}",
                                        "session_balance", mode=mode, lookback=lookback))
    candidates.append(Candidate("fixed_equal_ensemble", "ensemble"))
    for name, family, mode in (
        ("cash", "cash", "full"), ("spy_hold", "spy", "hold"),
        ("index_equal", "index", "full"), ("index_sma200", "trend", "full"),
        ("index_night", "index", "night"), ("index_day", "index", "day"),
    ):
        candidates.append(Candidate(name, family, mode=mode, benchmark=True))
    return candidates


def held_events(events: pd.DataFrame, hold: int) -> pd.DataFrame:
    """A trigger holds for h opens; ignore repeat triggers until that tranche expires."""
    result = np.zeros(events.shape)
    remaining = np.zeros(events.shape[1], dtype=int)
    for i, flags in enumerate(events.to_numpy(dtype=bool)):
        new = (remaining == 0) & flags
        remaining[new] = hold
        result[i] = remaining > 0
        remaining = np.maximum(remaining - 1, 0)
    return pd.DataFrame(result, index=events.index, columns=events.columns)


def targets(panel: dict[str, pd.DataFrame], candidate: Candidate) -> pd.DataFrame:
    r = panel["total_return"]
    price = panel["total_index"]
    result = pd.DataFrame(0.0, index=r.index, columns=r.columns)
    family = candidate.family
    if family == "cash":
        return result
    if family == "spy":
        result["SPY"] = 1.0
    elif family == "index":
        result.loc[:, list(INDEX)] = 1 / len(INDEX)
    elif family == "trend":
        result.loc[:, list(INDEX)] = (
            price[list(INDEX)] > price[list(INDEX)].rolling(200).mean()
        ).astype(float) / len(INDEX)
    elif family == "shock":
        # Exclude today's shock from its own volatility denominator.
        vol = r[list(INDEX)].rolling(20).std(ddof=1).shift(1)
        event = r[list(INDEX)] < -candidate.threshold * vol
        if candidate.trend_filter:
            event &= price[list(INDEX)] > price[list(INDEX)].rolling(200).mean()
        result.loc[:, list(INDEX)] = held_events(event, candidate.hold) / len(INDEX)
    elif family == "sector_residual":
        market = r["SPY"]
        variance = market.rolling(60).var(ddof=1)
        residual = pd.DataFrame(index=r.index)
        for symbol in SECTORS:
            # The beta removing today's market shock was estimable yesterday.
            beta = r[symbol].rolling(60).cov(market).div(variance).shift(1)
            residual[symbol] = r[symbol] - beta * market
        score = residual.rolling(candidate.lookback).sum()
        for i in range(len(r)):
            if i % candidate.hold:
                if i:
                    result.iloc[i] = result.iloc[i - 1]
                continue
            row = score.iloc[i]
            if not np.isfinite(row.to_numpy()).all():
                continue
            # Fixed ticker ordering breaks ties; no performance-based membership.
            order = row.sort_values(kind="mergesort").index
            result.loc[r.index[i], list(order[:3])] = 1 / 6
            result.loc[r.index[i], list(order[-3:])] = -1 / 6
        # Equal long/short dollars, not a claim of beta neutrality.
    elif family == "session_balance":
        day = np.log1p(panel["day_return"][list(INDEX)])
        night = np.log1p(panel["night_return"][list(INDEX)])
        score = (day - night).rolling(candidate.lookback).mean()
        result.loc[:, list(INDEX)] = (score > 0).astype(float) / len(INDEX)
    elif family == "ensemble":
        names = ("shock_z1.5_h3_trend0", "sector_residual_l5_h3",
                 "session_balance_l63_full")
        lookup = {c.name: c for c in registry()}
        result = sum((targets(panel, lookup[name]) for name in names)) / 3
    else:
        raise ValueError(f"Unknown family {family}")
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError(f"{candidate.name}: nonfinite targets")
    if (result.abs().sum(axis=1) > 1 + 1e-10).any():
        raise ValueError(f"{candidate.name}: unit gross budget exceeded")
    return result
