# Frozen crypto forward result: audit and research decision

## Decision

**Reject promotion of this version as a standalone return strategy.** Retain the
fixed state rule as a defensive crypto allocation benchmark. Do not resume the
learned allocator, tune these thresholds on the forward period, or move directly
to paper/live use. Monte Carlo is not the next qualification step for this version.

The rule outperformed buy-and-hold and matched plain trend in this historical forward
window. Preserve that relative benefit. However, the absolute return/risk trade-off
is weak: state-40 earned 2.15% CAGR with 28.52% drawdown and 0.212 Sharpe; state-20 was
slightly negative. Both lose money under higher costs and an additional day of delay.
These observations do not meet this exercise's objective of attractive adjusted
returns with restrained drawdown. No old charter performance threshold is used.

The useful result is a tested defensive baseline and evidence about its limitations.
The next research direction should target an additional, economically distinct return
source rather than another model choosing between the same two crypto portfolios.
That is a new research design; none is implemented or evaluated in this record.
No operator rerun is required for the supplied forward ZIP.

## Source, scope and audit

Source: `fresh_crypto_forward_20260914_153208_047.zip`, 5,232,905 bytes.
SHA-256: `732c57691d966577183ab147081fd92b3464667cb8ec2415fb1452b908acdc2a`.
Source commit: `85a98b3e0acfc93645036578cf61ee46805c96a4`.

All 17 artifact hashes, all 20 consumed code/specification hashes, six prepared-artifact
hashes and the archived specification/candidate freeze verify. Code hashes match Git
under uniform Windows CRLF conversion. Both normalized inputs contain 3,525 UTC daily
rows from January 1, 2017 through August 26, 2026. Their 2,922 development rows match
the separately supplied, hash-pinned long-history source exactly after parsing.

All 20 policies across four scenarios were replayed: 80 ledgers, 603 evaluation
rows per ledger and 48,240 total daily rows. Features and mixture decisions reproduce
exactly. The largest numeric ledger difference is below 1.18e-14; the largest metric
difference is below 2.67e-14. Independent compounded wealth and 240 period-statistic
rows verify, as do 12 closed-form buy-and-hold price/fee identities. The deliberately
changed-return canary is rejected.

Audit code: `scripts/review_fresh_crypto_forward.py`. Aggregate evidence:
[`evidence/fresh_crypto_forward_20260914/market_review/`](evidence/fresh_crypto_forward_20260914/market_review/).
The original strategies, forward runner, thresholds and specification remain unchanged.
Raw prices and complete ledgers remain in local result artifacts rather than tracked
evidence. Reproduction from the research checkout, using a new output directory:

```powershell
uv run --locked --python 3.12 --extra dev python -m scripts.review_fresh_crypto_forward --archive '.\artifacts\fresh_crypto_forward_20260914_153208_047.zip' --development-source '.\artifacts\fresh_crypto_long_history_20260914_142341_250.zip' --output-dir '.\artifacts\fresh_crypto_forward_review_local'
```

This is locked historical forward validation, not globally pristine final OOS.
2025 was used by earlier repository research; the operator's 2026 prior-access status
is unknown. The audit replays only the supplied window, introduces no new strategy
variant, fits no model and runs no Monte Carlo. After this inspection, any redesign
using these outcomes must count this period as development evidence.

The raw Windows source files were not supplied, so their recorded raw-file hashes
could not be independently recomputed. The normalized snapshots, preparation chain
and development overlap were checked. Vendor/acquisition provenance and executable
venue equivalence remain unverified.

## Full historical forward results

January 1, 2025 through liquidation at the August 26, 2026 open. Each portfolio starts
from cash; expert features and the weekly state choice carry their original schedule.
There is no inventory reset at January 1, 2026. Base costs are 30 bps one way, including
entry and final exit. Active portfolios below use the same 2% band. Spot is unlevered;
residual USD earns zero. Risk settings are forecast targets, not realized-volatility
guarantees.

| Policy | Total return | CAGR | Sharpe | Maximum drawdown |
|---|---:|---:|---:|---:|
| State rule 20 | -0.37% | -0.23% | 0.063 | -18.48% |
| Plain trend 20 | -1.76% | -1.07% | 0.008 | -18.22% |
| Allocation 20 | -6.43% | -3.95% | -0.075 | -33.68% |
| Fixed blend 20 | -3.91% | -2.39% | -0.048 | -26.21% |
| State rule 40 | 3.57% | 2.15% | 0.212 | -28.52% |
| Plain trend 40 | -7.32% | -4.51% | -0.056 | -28.82% |
| Allocation 40 | -20.40% | -12.93% | -0.102 | -57.04% |
| Fixed blend 40 | -11.92% | -7.41% | -0.079 | -43.87% |
| BTC buy-and-hold | -16.38% | -10.29% | -0.027 | -53.08% |
| ETH buy-and-hold | -27.10% | -17.45% | 0.084 | -67.60% |
| Initial 50/50 buy-and-hold | -21.74% | -13.82% | -0.007 | -60.04% |
| Zero-yield USD cash | 0.00% | 0.00% | undefined | 0.00% |

State-20/state-40 realized annual volatility of 15.51%/26.44%, with average risky
exposure of 25.91%/41.64%. Both spent 378 calendar days in their longest underwater
spell. State-40's Calmar is 0.075. These costs and drawdowns are substantial relative
to the small positive compounded return. Cash has zero modeled return and risk;
no interest-bearing cash instrument or yield is credited.

The positive Sharpe alongside negative CAGR in some rows is not an accounting
contradiction: Sharpe uses mean daily arithmetic returns while CAGR compounds them.
All metrics reproduce independently.

## What changed across years

The 2026 column covers January 1 through August 26 only. Figures below are cumulative
period returns, not annualized projections. Year slices use continuous inventory;
when a 2026 extension exists, 2025 does not include a fictional final liquidation.

| Policy | 2025 total return | 2026 through August 26 |
|---|---:|---:|
| State rule 20 | 2.41% | -2.72% |
| Plain trend 20 | 0.99% | -2.72% |
| State rule 40 | 5.78% | -2.10% |
| Plain trend 40 | -5.34% | -2.10% |
| Allocation 40 | -6.39% | -14.96% |
| Fixed blend 40 | -5.14% | -7.15% |
| BTC buy-and-hold | -6.55% | -10.52% |

The state rule's incremental benefit occurred in 2025. Every eligible 2026 state
signal selects the trend expert. For both risk profiles and all four scenarios,
state and matched plain-trend daily returns in 2026 agree within 4.45e-16. Thus 2026
shows the protective behavior of trend exposure, but supplies no additional evidence
that the state selector improves on trend in that regime.

The relative gain is also concentrated within 2025. State-40 returned 23.76% in July
versus plain trend's 12.72%. That month accounts for **84.10% of the full-period
relative log-wealth gain**; for state-20, July accounts for 104.42%, with the remaining
months collectively offsetting some of the gain. The percentage uses additive
log-relative wealth contributions, not a sum of monthly percentage-return differences.

Omitting July from the saved base returns leaves state-20 with -10.52% compounded
return and -0.384 Sharpe, and state-40 with -16.32% and -0.309. State-40 retains a
small relative advantage over trend in that diagnostic; state-20 does not. These
are post hoc influence diagnostics, not revised tradable backtests, confidence
intervals, significance tests or another holdout.

## Costs, execution delay and incremental value

| Candidate and scenario | CAGR | Sharpe | Maximum drawdown |
|---|---:|---:|---:|
| State 20, frictionless | 1.61% | 0.180 | -17.22% |
| State 20, base 30 bps | -0.23% | 0.063 | -18.48% |
| State 20, 75 bps stress | -2.92% | -0.113 | -20.34% |
| State 20, extra-day delay | -3.57% | -0.156 | -19.86% |
| State 40, frictionless | 4.68% | 0.305 | -27.12% |
| State 40, base 30 bps | 2.15% | 0.212 | -28.52% |
| State 40, 75 bps stress | -1.54% | 0.073 | -30.58% |
| State 40, extra-day delay | -4.99% | -0.058 | -29.89% |

Extra-day delay lowers state-40 CAGR by 7.14 percentage points. Frictionless outcomes
are already modest, so fees alone do not explain the weak absolute opportunity.
Exact-execution state-20/state-40 earn -0.37%/1.70% base CAGR, confirming that the
2% execution band is not hiding a strong exact-rebalancing result.

There is still incremental value relative to plain trend. State-20's full-period
base CAGR advantage is 0.84 percentage points; state-40's is 6.66 points. Their
frictionless advantages are 0.59/6.64 points. Unlike the development cost attribution,
the larger forward state-40 relative gain is predominantly associated with different
exposure timing, not lower fees. Annual one-way turnover savings are 0.89/0.63 times
NAV, with 0.27/0.19 percentage points of annual arithmetic fee drag saved. Those
arithmetic fee figures are not additive decompositions of compounded CAGR.

Both candidates retain higher full-period CAGR than matched plain trend and BTC in
all four scenarios. State-20 nevertheless has slightly deeper drawdown than matched
trend in each scenario; state-40's drawdown improvement over trend is small. The
large drawdown reduction is relative to persistent crypto exposure.

## Consequence for research

The development state-40 headline of 30.29% CAGR and 0.921 Sharpe did not persist;
the fixed historical forward figures are 2.15% and 0.212. Different market conditions
and a relatively short forward window limit inference about long-run performance,
but cannot turn these observations into evidence of a robust high-return strategy.

Preserve the candidate definition, all scenarios, the unsuccessful absolute result
and its genuine relative benefits. Do not discard this period or optimize around July
2025 and call the resulting fit OOS. The simple state rule remains useful as a
defensive benchmark against which a new return source must demonstrate contribution.

A Monte Carlo study could describe conditional risk of these saved returns. It is
not needed to establish the current research decision, and simulated paths cannot
supply missing independent regimes or repair poor observed economics. No such study,
new strategy implementation or paper/live change is made here.
