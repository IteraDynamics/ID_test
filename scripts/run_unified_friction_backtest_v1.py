"""
Itera Dynamics Unified Friction Backtest v1
Integrates Equity MR Overlay + Crypto Sleeve v2 with full friction modeling.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from research.harness.execution_model import ExecutionConfig, compute_fill
from research.harness.metrics import compute_metrics
import sys
from pathlib import Path

# Identify the project root (one level up from /scripts)
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

# Existing imports from research/harness/ will now resolve correctly
from research.harness.execution_model import ExecutionConfig, compute_fill
from research.harness.metrics import compute_metrics

# --- Configuration ---
EQUITY_TARGETS_PATH = "artifacts/equity_mr_overlay_target_book_v1/equity_mr_overlay_diagnostics.csv"
CRYPTO_TARGETS_PATH = "artifacts/crypto_target_stream_v1/crypto_target_exposure_daily.csv"
CRYPTO_NAV_PATH = "artifacts/fund_tilted_cal_4s_2019-03-08_2025-12-31/equity_curves.csv"

# Cost Assumptions
CRYPTO_CONFIG = ExecutionConfig(
    taker_fee_rate=0.0006, 
    base_slippage_bps=3.0,
    slippage_vol_factor=50.0 
)

# Equity Friction (7.5 bps slippage + 2 bps commission proxy)
EQUITY_CONFIG = ExecutionConfig(
    taker_fee_rate=0.0002, 
    base_slippage_bps=7.5,
    slippage_vol_factor=10.0
)

ALLOCATION_SPLIT = 0.50
REBALANCE_THRESHOLD = 0.05  # 5% Drift Buffer

def run_unified_backtest():
    # 1. Load Data
    eq_df = pd.read_csv(EQUITY_TARGETS_PATH, index_col='timestamp', parse_dates=True)
    cry_df = pd.read_csv(CRYPTO_TARGETS_PATH, index_col='timestamp', parse_dates=True)
    cry_nav = pd.read_csv(CRYPTO_NAV_PATH, index_col='timestamp', parse_dates=True)

    # Calculate Crypto Sleeve Returns from NAV
    cry_returns = cry_nav['portfolio'].pct_change().fillna(0.0)
    
    # 2. Merge and Align
    df = eq_df[['daily_return']].rename(columns={'daily_return': 'eq_return'})
    df = df.join(cry_returns.rename('cry_return'), how='inner')
    
    # 3. Backtest Loop with Friction
    initial_capital = 100000.0
    nav = initial_capital
    eq_val = nav * ALLOCATION_SPLIT
    cry_val = nav * ALLOCATION_SPLIT
    
    equity_curve = []
    total_friction_usd = 0.0
    
    for ts, row in df.iterrows():
        # Mark-to-market
        eq_val *= (1 + row['eq_return'])
        cry_val *= (1 + row['cry_return'])
        nav = eq_val + cry_val
        
        # Check for Rebalance / Drift
        eq_pct = eq_val / nav if nav > 0 else 0
        drift = abs(eq_pct - ALLOCATION_SPLIT)
        
        if drift > REBALANCE_THRESHOLD:
            # Target values
            target_eq = nav * ALLOCATION_SPLIT
            target_cry = nav * ALLOCATION_SPLIT
            
            # Compute trade notional
            eq_trade_notional = abs(target_eq - eq_val)
            cry_trade_notional = abs(target_cry - cry_val)
            
            # Apply Friction
            eq_cost = eq_trade_notional * (EQUITY_CONFIG.base_slippage_bps / 10000 + EQUITY_CONFIG.taker_fee_rate)
            cry_cost = cry_trade_notional * (CRYPTO_CONFIG.base_slippage_bps / 10000 + CRYPTO_CONFIG.taker_fee_rate)
            
            total_friction_usd += (eq_cost + cry_cost)
            nav -= (eq_cost + cry_cost)
            
            # Reset after rebalance
            eq_val = nav * ALLOCATION_SPLIT
            cry_val = nav * ALLOCATION_SPLIT
            
        equity_curve.append(nav)

    # 4. Metric Computation
    curve_series = pd.Series(equity_curve, index=df.index)
    metrics = compute_metrics(curve_series, trades=[], params={"strategy_id": "UNIFIED_FUND_V1", "asset": "COMPOSITE"})
    
    print("\n=== UNIFIED FUND V1 (NET OF FEES) ===")
    print(metrics.to_markdown())
    print(f"\nTotal Friction (Fees + Slippage) Paid: ${total_friction_usd:,.2f}")

if __name__ == "__main__":
    run_unified_backtest()
