# Equity Book v1 — Research Plan

## Status

**Branch:** `research/equity-book-v1`

**Research status:** initialized.

**Runtime status:** no paper-trading, broker, execution, or live allocation changes approved.

## Purpose

Equity Book v1 is a separate research program from Crypto Fund v1/v2.

The goal is not to dilute the crypto strategy for diversification optics. The goal is to determine whether SPY/QQQ-based systematic equity exposure is independently worth running as its own book.

## Core Framing

Crypto and equities should be evaluated as separate books:

```text
Crypto Book:
  BTC/ETH multi-timeframe trend-following system.
  Fund v1 and Fund v2 paper trade side-by-side.

Equity Book:
  SPY/QQQ daily strategy research.
  Goal is to build an independently credible systematic equity sleeve/book.
```

Firm-level reporting may later combine the books, but the research should not force one allocator to govern everything prematurely.

## Initial Research Questions

1. What equity artifacts already exist and which are valid?
2. What were the strongest SPY-only and QQQ-only profiles?
3. Does an SPY/QQQ book improve risk-adjusted performance versus passive SPY/QQQ benchmarks?
4. Is the right equity mandate trend participation, capital preservation, or defensive overlay?
5. Are any prior defensive-overlay / Fund v2 results worth preserving?
6. Does adding T-bill or defensive exposure improve the equity book, or does it dilute performance?

## Phase 1 — Artifact Recovery

Before building new strategies, recover known-good equity work.

Audit candidate artifacts such as:

```text
artifacts/*spy*/equity_curves.csv
artifacts/*qqq*/equity_curves.csv
artifacts/*fund_v2*/equity_curves.csv
artifacts/*defensive*/equity_curves.csv
artifacts/*overlay*/equity_curves.csv
```

Normalize all candidate curves to a common metric set:

```text
Total Return
CAGR
MaxDD
Sharpe
Sortino
Calmar
Annualized volatility
Worst 90D return
Worst 180D return
Yearly returns
Time underwater
Max time underwater
```

Benchmark candidates against:

```text
SPY buy-and-hold
QQQ buy-and-hold
SPY/QQQ 50/50 daily rebalanced
```

## Phase 2 — Baseline Equity Book

Test simple book constructions before overlays:

```text
SPY-only strategy
QQQ-only strategy
SPY/QQQ equal weight
SPY/QQQ risk-weighted
SPY/QQQ trend-gated
```

Primary benchmark question:

```text
Does the equity book improve drawdown-adjusted returns versus passive SPY/QQQ exposure?
```

## Phase 3 — Mandate Selection

Choose one equity mandate before adding complexity.

Possible mandates:

```text
Equity Trend Book:
  Participate in SPY/QQQ uptrends and reduce exposure in downtrends.

Defensive Equity Book:
  Lower-return, lower-drawdown capital preservation sleeve.

Balanced Equity Book:
  Moderate participation with materially lower drawdown than buy-and-hold.
```

Do not mix these mandates until the base book is understood.

## Phase 4 — Overlay Tests

Only after the baseline book is measured, test overlays:

```text
Cash / T-bill proxy
SGOV / BIL / SHV short-duration Treasury proxy
Volatility target
Drawdown governor
Regime filter
Risk-off overlay
```

Overlay rule:

```text
An overlay must improve the mandate-specific objective.
It should not be added merely to make the book look diversified.
```

## Current Guardrails

```text
No broker changes.
No paper-trading changes.
No live allocation changes.
No crypto runtime changes.
No global allocator changes.
No forcing equities into the crypto book.
```

## First Deliverable

Add and run:

```text
scripts/audit_equity_book_artifacts.py
```

The script should produce:

```text
artifacts/equity_book_v1_audit/
  performance_summary.csv
  benchmark_capture_summary.csv
  yearly_returns.csv
  normalized_equity_curves.csv
  summary.json
  summary.md
```

## Initial Data Commands

Use the existing Yahoo Finance research downloader:

```powershell
python scripts\download_equity_data.py --symbol SPY --start 2005-01-01 --out data\SPY_1D.csv
python scripts\download_equity_data.py --symbol QQQ --start 2005-01-01 --out data\QQQ_1D.csv
```

## Decision Criteria

An Equity Book v1 candidate should be interesting only if it can show at least one of the following:

```text
1. Better Calmar than passive SPY/QQQ.
2. Better Sortino than passive SPY/QQQ.
3. Materially lower drawdown with acceptable CAGR.
4. Distinct return profile from the Crypto Book.
5. Operational simplicity suitable for later paper-trading.
```

## Bottom Line

Equity Book v1 should start by recovering and measuring existing SPY/QQQ research, not by inventing a new sleeve.

The first research task is artifact audit and benchmark normalization.
