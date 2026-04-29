#!/usr/bin/env python
"""
Itera Dynamics — Fund Defensive Overlay Research Runner

Purpose:
    Evaluate defensive exposure scaling overlays applied to the calibrated
    Fund v1 multi-sleeve portfolio (BTC_1H, BTC_4H, ETH_1H, ETH_4H).

Classification:
    Research-only. This script does NOT modify runtime execution or paper trading.

What this script does:
    - Runs Fund v1 sleeves at full notional capital (optionally calibrated)
    - Applies a post-allocation defensive exposure scale (governor-style)
    - Compares multiple schedules (light / medium / strong)
    - Reports both no-cost and cost-adjusted results
    - Produces yearly attribution and worst drawdown window analysis

Key constraints:
    - Closed-bar only; no lookahead
    - Realistic fees and slippage for sleeve execution
    - Overlay transition costs are estimated (not full order-level routing)
    - Results are portfolio-level approximations (signal evidence), not final live PnL

Design goal:
    Improve risk-adjusted behavior (MaxDD / Calmar / stress periods)
    with minimal impact to Sharpe and acceptable CAGR drag.

Output artifacts:
    artifacts/fund_defensive_overlay_<date_range>/
        - equity_curves.csv
        - defensive_scales.csv
        - yearly_attribution.csv
        - drawdown_windows.csv
        - summary.json

Interpretation guidance:
    - Prefer improvements in MaxDD and Calmar
    - Small CAGR drag is acceptable if Sharpe/Calmar are preserved or improved
    - Validate under cost stress (e.g., higher overlay slippage)

Status in Itera workflow:
    - Used to validate DefensiveExposureGovernor (Fund v2 candidate)
    - Not wired into live/paper runtime (Fund v1 must remain unchanged during validation)

Example (PowerShell):
    python scripts\run_fund_defensive_overlay.py `
      --btc-data "data\btcusd_3600s_2019-01-01_to_2025-12-30.csv" `
      --eth-data "data\ethusd_3600s_2019-01-01_to_2025-12-30.csv" `
      --strategy trend_following_v8_ecap60_add80 `
      --calibrate `
      --fee 0.0006 `
      --base-slippage 3 `
      --slippage-vol-factor 50 `
      --rebalance-threshold 0.05
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s — %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("fund_defensive_overlay")

import numpy as np
import pandas as pd

from research.harness.backtest_engine import BacktestResult, run_backtest
from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.harness.resampler import align_equity_curves, resample_ohlcv
from research.strategies import REGISTRY as STRATEGY_REGISTRY

DEFAULT_STRATEGY = "trend_following_v8_ecap60_add80"


@dataclass(frozen=True)
class SleeveConfig:
    label: str
    asset: str
    timeframe: str
    data_path: str
    calibrated: bool = False


@dataclass(frozen=True)
class DefensiveSchedule:
    name: str
    lookback_h: int
    dd_trigger: float
    dd_release: float
    trend_ema_h: int
    min_scale: float
    confirm_h: int
    release_confirm_h: int


SCHEDULES: list[DefensiveSchedule] = [
    DefensiveSchedule("A_light_dd20_trend", 90 * 24, 0.20, 0.12, 200 * 24, 0.75, 24, 48),
    DefensiveSchedule("B_medium_dd15_trend", 90 * 24, 0.15, 0.08, 200 * 24, 0.60, 24, 72),
    DefensiveSchedule("C_strong_dd12_trend", 90 * 24, 0.12, 0.06, 200 * 24, 0.40, 12, 96),
]
COST_ADJUST_SCHEDULES = {"A_light_dd20_trend", "B_medium_dd15_trend"}
ATTRIBUTION_NAMES = ["A_light_dd20_trend_costed", "B_medium_dd15_trend_costed"]

# (rest of file unchanged)
