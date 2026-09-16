# Crypto reversal initial result — 2026-09-16

**Reject this fixed specification for OOS/Monte Carlo or paper-trading promotion.**
Implementation and the four full scenarios completed on the user's supplied BTC
and ETH hourly snapshots. No strategy rules were changed after inspecting returns.
This is a negative research result, not a rejection of all reversal strategies.

## Observed primary result

Initial 50/50 capital allocation to independent BTC and ETH spot/cash sleeves;
2020-01-01 through 2025-12-31 00:00 UTC. The primary rule is a 4h shock followed
by a 4h stabilization bar, a 1h processing delay, and a 24h hold.

| Scenario | CAGR | Daily zero-cash Sharpe | Hourly max drawdown |
|---|---:|---:|---:|
| Frictionless | 7.70% | 0.58 | -22.02% |
| Base: 30bp each side | 1.43% | 0.17 | -26.04% |
| Stress: 75bp each side | -7.23% | -0.45 | -46.69% |
| Base costs, 2h processing delay | 4.33% | 0.36 | -24.20% |

Base mean risky exposure is approximately 2.69% of total capital. This low average
exposure reflects occasional concentrated positions, not a continuous 2.69% risk
budget. It does not excuse the 26% portfolio drawdown or justify dividing CAGR by
exposure to advertise an adjusted return. The hindsight exposure-matched buy-hold
control has 0.65% CAGR, 0.33 Sharpe and -4.26% drawdown. Its allocation is determined
from the whole sample and is not deployable; it illustrates how different the risk
paths are even at the same average exposure.

Immediate dip buying and an unfiltered one-bar wait lose 14.69% and 16.36% annually
at base costs for the same 4h/24h setting. Stabilization avoids much of those losses,
but avoiding a poor comparator's losses is insufficient evidence of an attractive
standalone strategy. A longer execution delay happens to improve this sample; that
is reported, not used to replace the primary rule.

## All six predefined candidates, base costs

| Timeframe / hold | CAGR | Sharpe | Max drawdown |
|---|---:|---:|---:|
| 4h / 24h (primary) | 1.43% | 0.17 | -26.04% |
| 4h / 6h | -4.44% | -0.93 | -27.84% |
| 4h / 48h | -0.78% | 0.04 | -28.72% |
| 1h / 24h | -12.54% | -0.52 | -60.45% |
| 1h / 6h | -20.42% | -1.68 | -74.60% |
| 1h / 48h | 1.51% | 0.20 | -50.65% |

The primary executed 50 BTC and 65 ETH trades. Per-sleeve geometric break-even
one-way cost is approximately 2.97bp BTC and 56.72bp ETH; these diagnostic figures
exclude cash yield and market impact beyond the flat cost assumption. ETH's result
does not establish a robust combined opportunity or authorize selecting ETH alone
after seeing the outcomes. There was one held stale hourly mark in the ETH primary
run and no deferred primary exits. Missing prices can obscure drawdown within gaps.

## Verification and reproduction

14 focused tests passed on Python 3.12.14. The full run produced 2,808 summary rows,
43,908 single-asset trade rows and 87,816 fills across all policies and scenarios.
Each individual run passed P&L reconciliation and independent fill replay. Counts
include repeated trades across assumptions, not independent statistical samples.
PowerShell itself was not executed in this Linux environment; the Python CLI and
its input/output packaging were executed successfully.

The [compact evidence](evidence/crypto_reversal_initial_20260916.json) records all
six candidates across assets/cost scenarios, primary/control period breakdowns,
source identities, code hashes and verification metadata. The
[design and command](CRYPTO_REVERSAL_20260916.md) reproduce the full ZIP locally.
The recorded local git commit differs from the GitHub commit because publication
uses the GitHub API; source-file hashes identify the exact executed implementation.
The verification run was executed before the implementation commit (dirty working
tree recorded), following the separately committed frozen design.

No Core ledger was joined, so no measured diversification benefit is claimed.
All examined years are exploratory. Further optimization of this small family
would be a new, outcome-informed research iteration, not validation. Stop this
specification here; no vendor request, new data purchase, OOS label or Monte Carlo
exercise is justified by these observed economics.
