# Itera Dynamics

> Deterministic research-to-runtime infrastructure for systematic crypto fund development.

Itera Dynamics is a Python monorepo for researching, validating, and operating systematic trading strategies with a strict separation between research, allocation, governance, and execution.

The current system is focused on a calibrated multi-sleeve BTC/ETH trend-following fund architecture, live paper-trading validation, and fund-level defensive-governor research.

---

## Current Status

### Fund v1 — active paper-trading baseline

Fund v1 is the current production-candidate paper-trading structure.

- **Strategy:** `trend_following_v8_ecap60_add80`
- **Assets / sleeves:** `BTC_1H`, `BTC_4H`, `ETH_1H`, `ETH_4H`
- **Weights:** equal-weight, 25% each
- **Mode:** calibrated
- **Execution:** realistic fees, slippage, rebalance threshold, and paper-broker accounting
- **Status:** running as the unchanged live/paper baseline while awaiting first full trade cycle

Important operating rule:

> Do not modify Fund v1 runtime behavior until the current paper-trading baseline has completed sufficient validation, including at least one full entry → hold → exit cycle.

### Fund v2 — research candidate

Fund v2 is an emerging architecture candidate built around Fund v1 plus a defensive Layer 3 governor.

- **Candidate:** `DefensiveExposureGovernor`
- **Research profile:** improves drawdown / stress-period behavior with small CAGR drag
- **Status:** researched, cost-adjusted, and unit-tested, but **not deployed** into the active Fund v1 paper trader

### LLM skill system

The repo now includes reusable LLM workflow skills under:

```text
docs/llm_skills/
```

These files standardize how Claude Code, ChatGPT, Codex, or other coding assistants should reason about Itera tasks, conduct research, edit code, review backtests, and protect runtime behavior.

---

## Architecture

Itera is organized around three mandatory layers. These layers should not bleed into each other.

```text
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1 — Regime Engine          (research/regimes/)           │
│  Pure market classification. No I/O, no execution.              │
│  Output: RegimeLabel                                            │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2 — Strategy Modules       (research/strategies/)        │
│  Stateless generate_intent(df, ctx) → StrategyIntent            │
│  No broker calls. No file writes. No hidden state.              │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3 — Runtime / Governance   (runtime/argus/)              │
│  Allocators, governors, brokers, live/paper state, execution.   │
│  This is the only layer allowed to route orders or persist state.│
└─────────────────────────────────────────────────────────────────┘
```

### Layer 1 — Regime Engine

The Regime Engine classifies market context from OHLCV data into discrete `RegimeLabel` values.

Design requirements:

- closed-bar only
- deterministic
- no execution side effects

### Layer 2 — Strategy Modules

Strategy modules expose a deterministic intent interface:

```python
generate_intent(df: pd.DataFrame, ctx: StrategyContext, closed_only: bool = True) -> StrategyIntent
```

Strategy modules must be:

- stateless
- side-effect-free
- safe for both backtests and runtime
- compatible with no-lookahead validation

### Layer 3 — Runtime, Allocation, and Governance

Layer 3 is responsible for translating strategy intent into governed exposure and execution.

Components include:

- `PortfolioAllocator`
- `DrawdownGovernor`
- `ExposureGovernor`
- `DefensiveExposureGovernor` research candidate
- `PaperBroker`
- live/paper runtime state
- dashboard / operator observability

---

## Design Principles

- **Closed-bar only:** signals are generated after a bar closes, never intra-bar.
- **No lookahead:** at bar `i`, only information available through bar `i` may be used.
- **Research/runtime separation:** strategy research must not mutate live state.
- **Fail-closed governance:** uncertain or invalid states should block new risk, not force entries.
- **Cost realism:** fees, slippage, turnover, and transition costs must be considered.
- **Auditability:** decisions, exposures, fills, fees, slippage, and NAV must be explainable.
- **Determinism:** same data + parameters should produce the same result.

---

## Key Research Conclusions

The current research state is intentionally documented because it affects future work:

- **Fund v1 equal-weight calibrated structure remains the baseline.**
- **ETH/BTC external rotation sleeve:** rejected as too beta-coupled to improve Fund v1.
- **ETH/BTC allocator overlay:** rejected because equal-weight Fund v1 performed better.
- **Post-capitulation long:** valid event-overlay idea, but too sparse for permanent sleeve allocation.
- **Defensive exposure overlay:** promoted as a Fund v2 candidate after cost-adjusted testing.

---

## Installation

**Requirements:** Python 3.11+

```bash
git clone https://github.com/IteraDynamics/ID_test.git
cd ID_test

python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

Copy environment configuration if needed:

```bash
cp .env.example .env
```

---

## Running Tests

```bash
# All tests
python -m pytest

# Defensive governor unit tests
python -m pytest tests/test_defensive_exposure_governor.py -q

# With coverage
python -m pytest --cov=research --cov=runtime --cov-report=term-missing
```

---

## Fund Research Commands

### Calibrated 4-sleeve Fund v1 backtest

```powershell
python scripts\run_fund_portfolio.py `
  --btc-data "data\btcusd_3600s_2019-01-01_to_2025-12-30.csv" `
  --eth-data "data\ethusd_3600s_2019-01-01_to_2025-12-30.csv" `
  --calibrate
```

### Defensive overlay research

```powershell
python scripts\run_fund_defensive_overlay.py `
  --btc-data "data\btcusd_3600s_2019-01-01_to_2025-12-30.csv" `
  --eth-data "data\ethusd_3600s_2019-01-01_to_2025-12-30.csv" `
  --strategy trend_following_v8_ecap60_add80 `
  --calibrate `
  --fee 0.0006 `
  --base-slippage 3 `
  --slippage-vol-factor 50 `
  --rebalance-threshold 0.05
```

Optional harsher overlay slippage stress test:

```powershell
python scripts\run_fund_defensive_overlay.py `
  --btc-data "data\btcusd_3600s_2019-01-01_to_2025-12-30.csv" `
  --eth-data "data\ethusd_3600s_2019-01-01_to_2025-12-30.csv" `
  --strategy trend_following_v8_ecap60_add80 `
  --calibrate `
  --fee 0.0006 `
  --base-slippage 3 `
  --slippage-vol-factor 50 `
  --rebalance-threshold 0.05 `
  --overlay-slippage-bps 10
```

---

## LLM-Assisted Development Workflow

This repo is intentionally designed to support LLM-assisted development while preserving system discipline.

Use the skills in `docs/llm_skills/` at the start of Claude Code / ChatGPT / Codex sessions.

Example:

```text
Read and follow:
- docs/llm_skills/01_itera_architecture_context.md
- docs/llm_skills/02_research_protocol.md
- docs/llm_skills/07_prompt_execution_template.md

Task role:
Backtest review

Goal:
Evaluate whether this candidate should proceed as a Fund v2 component.
```

Core rule:

> LLMs may generate code, but they must operate within explicit architecture, research, code-change, and runtime-safety contracts.

---

## Repo Structure

```text
IteraDynamics/
├── data/                         # OHLCV CSV data (usually gitignored)
├── artifacts/                    # Backtest/research artifacts (usually gitignored)
├── docs/
│   ├── llm_skills/               # Reusable LLM workflow skills
│   └── architecture.md           # Architecture notes, if present
├── research/                     # Layer 1 + Layer 2 research code
│   ├── regimes/                  # Regime engine
│   ├── strategies/               # Strategy modules
│   ├── harness/                  # Backtest harness, metrics, artifacts
│   └── diagnostics/              # Charts and analysis helpers
├── runtime/                      # Layer 3 runtime, governance, execution
│   └── argus/
│       ├── allocators/
│       ├── brokers/
│       ├── governors/
│       ├── state/
│       └── apex_core/
├── scripts/                      # CLI research/runtime scripts
├── tests/                        # Unit and integration tests
├── pyproject.toml
└── README.md
```

---

## Runtime Safety Notes

The active Fund v1 paper trader should remain unchanged while it is validating baseline behavior.

Any future runtime integration of the defensive governor must be:

- feature-gated, or
- deployed as a separate Fund v2 paper-trading run

Do not silently merge research behavior into active Fund v1 execution.

---

## Status Summary

Itera Dynamics is currently a live paper-traded, calibrated multi-sleeve crypto trend-fund architecture with a validated Fund v2 defensive-governor candidate and a reusable LLM skill system for governed AI-assisted development.
