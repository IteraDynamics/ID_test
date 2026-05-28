#!/usr/bin/env python
"""Compact fast runner for risk-contribution-aware core allocator research.

Use this when the full/fast grid in run_core_allocator_risk_contribution_sweep.py
is too slow or too noisy. It reuses the main implementation but replaces the
fast grid with a compact, focused candidate set and suppresses pandas warning
spam that can make Windows terminals painfully slow.

Research only. No broker/runtime/live execution code is modified.
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

import run_core_allocator_risk_contribution_sweep as base


_ORIGINAL_RUN_POLICY = base._run_policy


def _run_policy_with_policy_column(
    spec: base.RiskContributionSpec,
    prices,
    capital: float,
    fee_bps: float,
):
    """Keep compact-runner summary rows compatible with base reporting.

    The base `_run_policy` stores the strategy name under the dataclass-derived
    `name` field, while the downstream report builder expects a `policy` column.
    Daily equity and weight outputs already use `policy`; this wrapper normalizes
    the summary row too so top-N filtering and CSV generation do not fail late
    with `KeyError: 'policy'` after the sweep has already run.
    """

    daily, weights, row = _ORIGINAL_RUN_POLICY(spec, prices, capital, fee_bps)
    row["policy"] = str(row.get("policy") or row.get("name") or spec.name)
    return daily, weights, row


def _compact_specs(available: list[str], fast: bool, rebalance: str) -> list[base.RiskContributionSpec]:
    """Return a small focused grid around the currently plausible region.

    The broad runner's --fast grid still tests hundreds of combinations. This
    compact runner tests only the shapes we actually care about next:

    - 10% / 12% / 15% target vol
    - 75% / 90% max gross
    - 20% / 25% crypto risk cap
    - 5% / 10% stressed crypto risk cap
    - 10% / 20% minimum defensive allocation
    """

    bases = [
        (
            "bal",
            base._normalize(
                {
                    "BTC-USD": 0.30,
                    "ETH-USD": 0.15,
                    "QQQ": 0.25,
                    "SPY": 0.15,
                    "TLT": 0.075,
                    "GLD": 0.075,
                },
                available,
            ),
        ),
        (
            "def",
            base._normalize(
                {
                    "BTC-USD": 0.20,
                    "ETH-USD": 0.08,
                    "QQQ": 0.20,
                    "SPY": 0.22,
                    "TLT": 0.15,
                    "GLD": 0.15,
                },
                available,
            ),
        ),
        (
            "cl",
            base._normalize(
                {
                    "BTC-USD": 0.16,
                    "ETH-USD": 0.04,
                    "QQQ": 0.30,
                    "SPY": 0.25,
                    "TLT": 0.12,
                    "GLD": 0.13,
                },
                available,
            ),
        ),
    ]

    target_vols = [0.10, 0.12, 0.15]
    max_grosses = [0.75, 0.90]
    crypto_caps = [0.20, 0.25]
    stressed_caps = [0.05, 0.10]
    min_defensive_weights = [0.10, 0.20]

    specs: list[base.RiskContributionSpec] = []
    for base_name, weights in bases:
        if not weights:
            continue
        for target_vol in target_vols:
            for max_gross in max_grosses:
                for crypto_cap in crypto_caps:
                    for stressed_cap in stressed_caps:
                        for min_def in min_defensive_weights:
                            if stressed_cap > crypto_cap:
                                continue
                            name = (
                                f"rca_fast_{base_name}"
                                f"_tv{int(target_vol * 100):02d}"
                                f"_mg{int(max_gross * 100):03d}"
                                f"_crc{int(crypto_cap * 100):02d}"
                                f"_sc{int(stressed_cap * 100):02d}"
                                f"_def{int(min_def * 100):02d}"
                            )
                            specs.append(
                                base.RiskContributionSpec(
                                    name=name,
                                    base_weights=weights,
                                    ma_days=200,
                                    vol_lookback_days=60,
                                    long_vol_lookback_days=180,
                                    target_vol_ann=target_vol,
                                    max_gross=max_gross,
                                    base_crypto_risk_cap=crypto_cap,
                                    stressed_crypto_risk_cap=stressed_cap,
                                    max_asset_weight=0.35,
                                    min_defensive_weight=min_def,
                                    crypto_trend_cut=0.50,
                                    crypto_vol_rising_cut=0.60,
                                    rebalance=rebalance,
                                )
                            )
    return specs


base._run_policy = _run_policy_with_policy_column
base._build_specs = _compact_specs

if __name__ == "__main__":
    base.main()
