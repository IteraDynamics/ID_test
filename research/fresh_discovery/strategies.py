"""Three mechanism families; no fitted model, optimizer, or outcome-based selector."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .data import ASSETS, MACRO, PULLBACK, SECTORS

RISK_TARGET = 0.15
WARMUP = 252


@dataclass(frozen=True)
class Policy:
    name: str
    family: str
    lookback: int
    gross_cap: float
    cadence: str
    role: str = "candidate"


def policies() -> list[Policy]:
    result = []
    for cap in (1.0, 1.5):
        suffix = "g100" if cap == 1 else "g150"
        for family, windows, cadence in (
            ("dual_momentum", (63, 126, 252), "monthly"),
            ("sector_reversal", (3, 5, 10), "weekly"),
            ("trend_pullback", (3, 5, 10), "daily"),
        ):
            for window in windows:
                result.append(Policy(f"{family}_{window}_{suffix}", family, window, cap, cadence))
        result.append(Policy(f"fixed_blend_{suffix}", "fixed_blend", 0, cap, "weekly"))
        for family, window, cadence in (
            ("static_macro", 0, "monthly"),
            ("trend_only", 0, "daily"),
            ("raw_sector_reversal", 5, "weekly"),
        ):
            result.append(Policy(f"{family}_{suffix}", family, window, cap, cadence, "control"))
    result.extend([Policy("spy_buy_hold", "spy_buy_hold", 0, 1, "once", "benchmark"),
                   Policy("bil_buy_hold", "bil_buy_hold", 0, 1, "once", "benchmark")])
    return result


class Features:
    def __init__(self, frames: dict[str, pd.DataFrame]):
        self.dates = frames["SPY"].index
        self.close = np.column_stack([frames[a].close for a in ASSETS])
        self.returns = self.close[1:] / self.close[:-1] - 1
        self.covariances = {}
        self.raw_cache = {}

    def covariance(self, t: int) -> np.ndarray:
        if t < WARMUP:
            raise ValueError("Insufficient feature history")
        if t not in self.covariances:
            cov = np.cov(self.returns[t-63:t, :-1], rowvar=False, ddof=1) * 252
            # Fixed diagonal shrinkage, independent of outcomes and candidate identity.
            self.covariances[t] = 0.9 * cov + 0.1 * np.diag(np.diag(cov))
        return self.covariances[t]

    def raw(self, family: str, window: int, t: int) -> np.ndarray:
        key = (family, window, t)
        if key in self.raw_cache:
            return self.raw_cache[key].copy()
        cov = self.covariance(t)
        vol = np.maximum(np.sqrt(np.diag(cov)), 0.01)
        base = np.zeros(len(ASSETS) - 1)
        if family in ("dual_momentum", "static_macro"):
            idx = np.array([ASSETS.index(a) for a in MACRO])
            if family == "dual_momentum":
                cash = self.close[t, -1] / self.close[t-window, -1] - 1
                momentum = self.close[t, idx] / self.close[t-window, idx] - 1 - cash
                # Stable universe-order tie breaking; unfilled top-three slots stay in cash.
                chosen = np.argsort(-momentum, kind="stable")[:3]
                chosen = chosen[momentum[chosen] > 0]
                idx = idx[chosen]
                allocation = len(chosen) / 3
            else:
                allocation = 1.0
            if len(idx):
                inverse = 1 / vol[idx]
                base[idx] = allocation * inverse / inverse.sum()
        elif family in ("sector_reversal", "raw_sector_reversal"):
            idx = np.array([ASSETS.index(a) for a in SECTORS])
            trailing = self.returns[t-63:t]
            market = trailing[:, ASSETS.index("SPY")]
            market_variance = market.var(ddof=1)
            if market_variance <= 1e-16:
                self.raw_cache[key] = base
                return base.copy()
            beta = ((trailing[:, idx] - trailing[:, idx].mean(axis=0)).T
                    @ (market - market.mean()) / (len(market) - 1) / market_variance)
            recent = self.returns[t-window:t]
            excess = recent[:, idx]
            if family == "sector_reversal":
                excess = excess - recent[:, [ASSETS.index("SPY")]] * beta
            score = excess.sum(axis=0) / (vol[idx] * np.sqrt(window / 252))
            rank = np.argsort(score, kind="stable")
            # No artificial long/short trade when the cross section is tied.
            if score.max() - score.min() > 1e-12:
                base[idx[rank[:3]]] = 1 / 6
                base[idx[rank[-3:]]] = -1 / 6
                if family == "sector_reversal":
                    base[ASSETS.index("SPY")] -= float(base[idx] @ beta)
                base /= np.abs(base).sum()
        elif family in ("trend_pullback", "trend_only"):
            idx = np.array([ASSETS.index(a) for a in PULLBACK])
            trend = self.close[t, idx] > self.close[t-199:t+1, idx].mean(axis=0)
            # Equal capital slots prevent a lone surviving asset absorbing the whole book.
            base[idx] = trend / len(idx)
            if family == "trend_pullback":
                move = self.close[t, idx] / self.close[t-window, idx] - 1
                z = move / (vol[idx] * np.sqrt(window / 252))
                base[idx] *= np.clip(-z, 0, 2) / 2
        else:
            raise ValueError(f"Unknown raw policy: {family}")
        self.raw_cache[key] = base.copy()
        return base


def size_target(base: np.ndarray, cov: np.ndarray, cap: float) -> tuple[np.ndarray, float]:
    gross = np.abs(base).sum()
    forecast = float(np.sqrt(max(0.0, base @ cov @ base)))
    # Do not lever up an abstention/pullback signal just because it holds little risk.
    # cap scales the full signal; volatility control only reduces that scale.
    scale = min(cap, RISK_TARGET / forecast) if forecast > 0 else cap
    risky = base * scale
    if gross * scale > cap + 1e-10:
        raise ValueError("Gross target cap breached")
    own_cash = max(0.0, 1.0 - risky.clip(min=0).sum())
    return np.r_[risky, own_cash], forecast * scale


def due(cadence: str, dates: pd.DatetimeIndex, t: int, first: int) -> bool:
    if t == first:
        return True
    if cadence == "once":
        return False
    if cadence == "daily":
        return True
    if cadence == "monthly":
        return dates[t].to_period("M") != dates[t-1].to_period("M")
    if cadence == "weekly":
        return dates[t].to_period("W-FRI") != dates[t-1].to_period("W-FRI")
    raise ValueError(cadence)


def make_schedules(frames: dict[str, pd.DataFrame], first: int):
    features = Features(frames)
    specifications = policies()
    schedules = {p.name: {} for p in specifications}
    rows = []
    # No signal on the final two sessions: the last session is the common liquidation.
    for t in range(first, len(features.dates) - 2):
        for policy in specifications:
            if not due(policy.cadence, features.dates, t, first):
                continue
            if policy.family in ("spy_buy_hold", "bil_buy_hold"):
                target = np.zeros(len(ASSETS))
                target[ASSETS.index("SPY" if policy.family == "spy_buy_hold" else "BIL")] = 1
                risk = None
            elif policy.family == "fixed_blend":
                # Equal standalone sleeve capital, not an outcome-fitted blend. Refresh
                # all three on the weekly blend decision; no future return/correlation fit.
                components = [size_target(features.raw(f, w, t), features.covariance(t),
                                          policy.gross_cap)[0][:-1]
                              for f, w in (("dual_momentum", 126),
                                           ("sector_reversal", 5), ("trend_pullback", 5))]
                base = np.mean(components, axis=0)
                # Component weights are already scaled: do not multiply leverage twice.
                target, risk = size_target(base / policy.gross_cap,
                                           features.covariance(t), policy.gross_cap)
                if np.abs(target[:-1]).sum() > policy.gross_cap + 1e-10:
                    raise ValueError("Blend target cap breached")
            else:
                target, risk = size_target(features.raw(policy.family, policy.lookback, t),
                                           features.covariance(t), policy.gross_cap)
            schedules[policy.name][t] = target
            rows.append(dict(policy=policy.name, signal_date=str(features.dates[t].date()),
                             forecast_risky_vol=risk,
                             **{a: float(target[j]) for j, a in enumerate(ASSETS)}))
    return specifications, schedules, pd.DataFrame(rows)


def registry() -> list[dict]:
    return [asdict(p) for p in policies()]
