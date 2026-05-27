# Core Allocator Research Track

This research track is intentionally separate from trade-entry modules.

The goal is not to discover another tactical setup. The goal is to build the structural compounding engine for Itera Dynamics: a portfolio-level allocator that decides how much capital belongs in major sleeves across market regimes.

## Thesis

A flagship engine should not depend on one entry/exit pattern becoming magical. It should compound by combining multiple modest edges through:

- regime-aware exposure control
- volatility targeting
- cross-asset capital rotation
- drawdown-aware risk reduction
- structural participation in major risk assets when conditions are favorable
- defensive withholding when conditions degrade

Tactical trade modules remain useful, but they should plug into the allocator as satellites, not masquerade as the core fund engine.

## Candidate Core Engine Types

### 1. Static structural benchmark

A fixed-weight allocator across crypto, equity growth, and defensive/macro assets.

Purpose: establish a simple no-timing baseline.

### 2. Trend-gated structural allocator

Allocates to BTC/ETH/equity risk assets only when each asset is above a long moving average. Otherwise, capital is held in cash or defensive assets.

Purpose: structural participation with crash avoidance.

### 3. Volatility-targeted allocator

Scales exposure based on realized volatility. Higher volatility reduces exposure; lower volatility allows fuller deployment.

Purpose: stabilize drawdowns and reduce dependency on perfect entries.

### 4. Regime rotation allocator

Rotates among crypto, growth equities, macro/commodity assets, and cash based on trend strength, volatility, and relative momentum.

Purpose: make the allocator the source of edge rather than any single trade setup.

### 5. Core + tactical satellite allocator

Combines a structural core portfolio with one or more tactical sleeves, such as the validated trade-idea sleeve.

Purpose: evaluate whether tactical modules improve a robust core rather than carrying the entire fund.

## Validation Standard

A candidate core allocator should be judged using stricter standards than a tactical sleeve:

- full-period metrics
- calendar-year returns
- max drawdown and drawdown duration
- rolling 3/6/12-month returns
- walk-forward / stitched OOS validation
- robustness to costs and slippage where applicable
- allocation turnover
- contribution by asset class
- sensitivity to parameters

## Initial Objective

Build a first-pass research harness that can test structural allocation policies across BTC, ETH, equity growth, and defensive/macro assets, then compare the resulting core allocator against the tactical sleeve finalist.

The first useful answer is not whether the core is perfect. The first useful answer is whether structural allocation produces a more durable compounding engine than isolated tactical entries.
