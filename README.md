# IteraDynamics

For the current Core v1 / campaign / ML Lab architecture, start with the
[repository map](docs/engineering/REPOSITORY_MAP.md). The original Argus walkthrough
below remains available for its supported historical interfaces.

> Institutional-grade quantitative investment research and execution infrastructure.

Itera Dynamics is building a quantitative investment firm through deterministic research,
reproducible validation, disciplined portfolio construction, explicit risk governance,
controlled execution, and auditable operations.

This repository contains the research-to-runtime platform that supports that objective. The
platform is foundational infrastructure for the firm, not the terminal objective. It maintains
a hard architectural separation between research and execution and is built for correctness,
auditability, and modular extensibility — not for speed or complexity for its own sake.

## Institutional direction and active handoff

- Long-term firm thesis: [`docs/ITERA_FIRM_THESIS.md`](docs/ITERA_FIRM_THESIS.md)
- Authoritative campaign state: [`docs/ITERA_CAMPAIGN_BOARD.md`](docs/ITERA_CAMPAIGN_BOARD.md)
- Research roadmap: [`docs/ITERA_RESEARCH_ROADMAP.md`](docs/ITERA_RESEARCH_ROADMAP.md)

The firm thesis is directional context and does not authorize implementation. The campaign board
is the current project-state and authorization record. Neither document independently authorizes
production, threshold, signal, order, portfolio, NAV, exposure, or runtime changes.

Campaign #43-R1 remains governed exactly by its frozen specification, R1 amendment, and board
acceptance gates. The firm-thesis clarification does not alter Campaign #43 scope or methodology.

---

## Architecture

The system is divided into three mandatory layers. These layers never bleed into each other.

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1 — Regime Engine          (research/regimes/)           │
│  Pure market classification. No I/O, no execution.             │
│  Output: RegimeLabel (TREND_UP, RANGE, HIGH_VOL, ...)          │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2 — Strategy Modules       (research/strategies/)        │
│  Stateless generate_intent(df, ctx) → StrategyIntent            │
│  No broker calls. No file writes. No hidden state.             │
│  Modules: trend_following, volatility_breakout, mean_reversion  │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3 — Runtime / Governance   (runtime/argus/)              │
│  Governors: DrawdownGovernor, ExposureGovernor                  │
│  Allocator: PortfolioAllocator                                  │
│  Brokers:   PaperBroker, StubLiveBroker                        │
│  Orchestrator: Argus — the only place allowed to execute trades │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 1 — Regime Engine

The Regime Engine classifies market context from OHLCV data into discrete
`RegimeLabel` values. It uses:

- **Dual EMA crossover** (fast 21 / slow 55) for trend direction.
- **ATR-as-%-of-close** for volatility level.
- **EMA rate-of-change** as momentum proxy.

Output labels: `TREND_UP`, `TREND_DOWN`, `RANGE`, `VOL_COMPRESSION`,
`VOL_EXPANSION`, `HIGH_VOL`, `UNKNOWN`.

All computation is closed-bar-only, pure-function, and deterministic.

### Layer 2 — Strategy Modules

Each strategy exposes a single function:

```python
generate_intent(df: pd.DataFrame, ctx: StrategyContext, closed_only: bool = True) -> StrategyIntent
```

Three baseline strategies are included:

| Strategy | Sleeve | Logic |
|---|---|---|
| `trend_following` | Core structural | EMA alignment + regime gate |
| `volatility_breakout` | Orthogonal alpha | Vol-compression → breakout |
| `mean_reversion` | Vol smoothing | RSI + Bollinger oversold in RANGE |

Strategies are stateless, side-effect-free, and safe to use in both backtests and runtime.

### Layer 3 — Runtime (Argus)

The runtime layer is the **only** place where trades are executed or live state is persisted.

Components:
- **DrawdownGovernor**: halts new buys when portfolio drawdown exceeds threshold.
- **ExposureGovernor**: caps exposure, enforces minimum notional, blocks low-confidence entries.
- **PortfolioAllocator**: blends sleeve intents with weights → single allocation decision.
- **PaperBroker**: in-memory paper trading with fee/slippage simulation.
- **StubLiveBroker**: exchange adapter skeleton.
- **Orchestrator**: runs the bar-by-bar loop (Layer 1 → Layer 2 → Layer 3 → Broker).

---

## Design Principles

- **Closed-bar only**: signals are generated after a bar closes, never intra-bar.
- **No lookahead**: at bar `i`, only `df.iloc[:i+1]` is visible.
- **Side-effect-free research**: strategy modules have no I/O, no broker calls, no mutations.
- **Fail-closed governance**: uncertain regimes block new buys; sell/exit always passes through.
- **Every decision is auditable**: regime signals, intents, allocations, and fills are all logged.
- **Determinism**: same data + parameters → byte-identical results every time.
- **Investment relevance**: research rigor exists to improve long-term investment reliability, not to maximize novelty or activity.

---

## Installation

**Requirements:** Python 3.11+

```bash
# Clone
git clone https://github.com/iteradynamics/id_test.git
cd id_test

# Install the reviewed dependency versions (Python 3.11 or 3.12 in CI)
python -m pip install uv==0.11.33
uv sync --locked --extra dev

# Copy env config
cp .env.example .env
```

---

## Running a Backtest

Place your OHLCV CSV in the `data/` directory. Expected columns:
`timestamp, open, high, low, close, volume`

```bash
# Single-strategy backtest
uv run --locked python scripts/run_backtest.py --data data/btc_1h.csv --strategy trend_following

# With date range
uv run --locked python scripts/run_backtest.py \
  --data data/btc_1h.csv \
  --strategy trend_following \
  --start 2022-01-01 \
  --end 2023-12-31

# Volatility breakout strategy
uv run --locked python scripts/run_backtest.py --data data/btc_1h.csv --strategy volatility_breakout

# Mean reversion
uv run --locked python scripts/run_backtest.py --data data/btc_1h.csv --strategy mean_reversion

# PowerShell
python scripts\run_backtest.py --data data\btc_1h.csv --strategy trend_following
```

**Output** (in `artifacts/<run_id>/`):
- `equity_curve.csv` — NAV, exposure, regime per bar
- `trades.csv` — all simulated trades with fees and slippage
- `summary.json` — full metrics JSON
- `summary.md` — human-readable metrics table
- `chart.png` — 3-panel diagnostic chart

---

## Running a Portfolio Backtest

```bash
# All three sleeves, default weights 50/30/20
uv run --locked python scripts/run_portfolio.py --data data/btc_1h.csv

# Custom weights (trend/vol/rev)
uv run --locked python scripts/run_portfolio.py --data data/btc_1h.csv --weights "0.6,0.2,0.2"
```

---

## Running Paper Trading

```bash
# Step through a CSV bar-by-bar using the full Argus runtime
uv run --locked python scripts/run_paper.py --data data/btc_1h.csv

# Run 200 cycles with $50k capital
uv run --locked python scripts/run_paper.py --data data/btc_1h.csv --capital 50000 --cycles 200

# With state persistence
uv run --locked python scripts/run_paper.py \
  --data data/btc_1h.csv \
  --state-path runtime/argus/state/live_state.json
```

---

## Running Tests

```bash
# All tests
uv run --locked python -m pytest

# With coverage
uv run --locked python -m pytest --cov=research --cov=runtime --cov-report=term-missing

# Specific suite
uv run --locked python -m pytest tests/unit/test_regime_engine.py -v
uv run --locked python -m pytest tests/unit/test_strategies.py -v
uv run --locked python -m pytest tests/integration/test_backtest_pipeline.py -v
```

---

## Repo Structure

```
IteraDynamics/
├── data/                        # OHLCV CSV data (gitignored except .gitkeep)
├── artifacts/                   # Backtest output artifacts (gitignored)
├── debug/                       # Debug logs (gitignored)
├── docs/                        # Architecture and design docs
│
├── research/                    # Layer 1 + Layer 2 — pure research code
│   ├── regimes/                 # Layer 1: Regime Engine
│   │   ├── contracts.py         # RegimeLabel, RegimeSignal
│   │   ├── baseline_engine.py   # BaselineRegimeEngine
│   │   └── regime_series.py     # compute_regime_series()
│   ├── strategies/              # Layer 2: Strategy Modules
│   │   ├── contracts.py         # Action, StrategyContext, StrategyIntent
│   │   ├── trend_following.py
│   │   ├── volatility_breakout.py
│   │   └── mean_reversion.py
│   ├── harness/                 # Research harness
│   │   ├── data_loader.py       # OHLCV CSV loader + validator
│   │   ├── backtest_engine.py   # Deterministic backtest loop
│   │   ├── metrics.py           # BacktestMetrics computation
│   │   └── artifacts.py        # CSV, JSON, MD, PNG output
│   ├── portfolio/
│   │   └── blend.py             # Multi-strategy portfolio backtest
│   └── diagnostics/
│       └── charts.py            # Standalone chart utilities
│
├── runtime/                     # Layer 3 — execution and governance
│   └── argus/
│       ├── apex_core/
│       │   ├── signal_generator.py   # Layer 1 + 2 bridge
│       │   └── orchestrator.py       # Main runtime loop
│       ├── brokers/
│       │   ├── base.py               # BaseBroker interface
│       │   ├── paper_broker.py       # In-memory paper trading
│       │   └── stub_live_broker.py   # Live exchange skeleton
│       ├── allocators/
│       │   └── portfolio_allocator.py
│       ├── governors/
│       │   ├── drawdown_governor.py
│       │   └── exposure_governor.py
│       ├── state/
│       │   └── runtime_state.py      # JSON-persisted live state
│       └── run_live.py               # Paper/live CLI entry point
│
├── scripts/
│   ├── run_backtest.py          # Backtest CLI
│   ├── run_portfolio.py         # Portfolio backtest CLI
│   └── run_paper.py             # Paper trading CLI
│
├── tests/
│   ├── unit/                    # Fast, isolated unit tests
│   ├── integration/            # End-to-end pipeline tests
│   └── fixtures/                # Synthetic data factory
│
├── .github/workflows/ci.yml     # GitHub Actions CI
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Extending IteraDynamics

### Adding a new strategy

1. Create `research/strategies/my_strategy.py`.
2. Implement `generate_intent(df, ctx, closed_only=True) -> StrategyIntent`.
3. Register in `research/strategies/__init__.py` REGISTRY.
4. Add to `scripts/run_backtest.py` CLI choices.
5. Write unit tests in `tests/unit/test_strategies.py`.

### Adding a new asset

1. Provide an OHLCV CSV in `data/`.
2. Pass `--asset ETH` (or your asset label) to the CLI scripts.
3. The regime engine and all strategy modules are asset-agnostic.

### Adding a live broker

1. Subclass `BaseBroker` in `runtime/argus/brokers/`.
2. Implement: `get_balance`, `get_position`, `get_nav`, `submit_market_order`,
   `get_fill`, `cancel_order`.
3. Set credentials via `.env` variables.
4. Pass your broker instance to the `Orchestrator`.

---

## Key Commands (Quick Reference)

```bash
# Backtest
uv run --locked python scripts/run_backtest.py --data data/btc_1h.csv --strategy trend_following

# Portfolio
uv run --locked python scripts/run_portfolio.py --data data/btc_1h.csv

# Paper run
uv run --locked python scripts/run_paper.py --data data/btc_1h.csv --cycles 500

# Tests
uv run --locked python -m pytest

# Tests with coverage
uv run --locked python -m pytest --cov=research --cov=runtime
```
