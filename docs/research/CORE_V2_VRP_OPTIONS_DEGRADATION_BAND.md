# Core v2 — Equity Options Premium-Selling Sleeve (SPY Defined-Risk Iron Condor VRP)
## Live Expectation and Degradation Band

## Status

**PROSPECTIVE — drafted 2026-08-30**, under `docs/ITERA_DESTINATION_CHARTER.md`'s "Refinement to
the One Rule — pre-registered pod degradation bands (2026-08-30)".

**This sleeve is not live.** Per `docs/ITERA_CAMPAIGN_BOARD.md`'s own status line, it is "not
frozen, not re-chartered as a numbered campaign yet," blocked at Gate 2 pending an external,
clock-bound brokerage (IBKR) approval, with real Gate 5 work — commission/fill verification
against the account's actual rate sheet — also still open. **Correction to this rule's own
adoption record:** the 2026-08-30 decision log (`ops/decisions.md`) described this sleeve as
"near live," which overstates its status; it remains gated behind an account that does not yet
exist. Filing this document now is not a backfill — nothing is being caught up on — but it
satisfies the rule's item 4 (frozen before inception, minimum 24-hour gap) and item 5
(git-committed before the funding action) cleanly by construction, since funding cannot occur
before the account itself clears. **Before funding, re-read this document and confirm nothing
material in the underlying backtest has since been revised; if it has, file a dated append first.**

## Honest statement of the evidentiary base

The strongest single-candidate result of any idea this fund has examined to date, and the
weaknesses are stated with equal weight, per this repo's standing convention.

**Strength:** 127 genuinely independent, non-overlapping 35-DTE cycles (2013-2026, 12.7 years) —
unlike nearly every other time-series test this fund has run, non-overlap here is real, so a plain
one-sample t-test is legitimate. Fair-value result: 88.2% win rate, mean $103.52/cycle,
t=6.07, p<0.000001. The backtest independently recovered the real Feb 2018 "Volmageddon" VIX spike
exactly where it should appear. A 60-structure robustness sweep (5 DTE × 4 delta × 3 wing) found
52/60 (87%) positive under representative assumptions, with the originally-chosen structure at the
77th percentile — not a cherry-picked outlier. A defined-risk alternative (cash-secured puts) was
tested and decisively rejected: 8.6x the worst-case loss, 58x the capital committed, for 48% of
the mean P&L.

**Weaknesses, stated plainly:**
- Skew and cost assumptions are illustrative sweeps, not verified historical market data — no
  verified SPY options bid-ask or per-strike skew dataset exists in this repo.
- Under the pessimistic stress case (steep skew + wide/crisis cost applied to every cycle),
  **0 of 60 structures are significant and positive.** The campaign's own conclusion: this edge
  lives or dies on execution quality, not on signal — an operational question, not a research one.
- **Tail correlation with Core v1's equity sleeves, flagged in the campaign record and not yet
  resolved:** the worst backtested cycle (2020-02-12, VIX 13.7→76.0 realized, -$455 against a
  ~$553 max risk) landed exactly when equities collapsed — the same moment Core v1's SPY/QQQ
  trend sleeves would be hurting. This sleeve does **not** supply crash diversification and
  arguably concentrates tail risk alongside existing equity exposure.
- Zero live confirmation of fill quality exists — there is no account yet.

## Live expectation range

Per this repo's standing convention, the backtest is a ceiling, never an expectation. Using the
moderate-skew, moderate-cost combined estimate (~$60-80/cycle net per contract, ~10.4 cycles/yr,
$553 hard-bounded max risk per contract per cycle) as the working range, materiality at a stated
risk budget:

- 2% risk budget: ≈$1,869/yr (1.9% of a $100k book)
- 5% risk budget: ≈$5,606/yr (5.6%)
- 10% risk budget: ≈$11,212/yr (11.2%)

**These figures assume moderate skew and moderate execution cost. Under the pessimistic stress
case, the expected value could be zero or negative** — this is the single largest open uncertainty
before any capital is committed, and this document does not resolve it; only real fills will.

## Re-evaluation triggers

Each trigger is a checkable number and window per the adopted rule's item 2. Non-operational
triggers force the default action per item 3 unless overridden once with a dated written reason;
**a second consecutive firing of the same trigger executes the default action with no override
available.**

**Default action (T1, T3, T4):** halve position size (contracts per cycle) within 5 trading days.

- **T1 — Fill-cost breach.** Realized average net P&L per cycle, averaged over any 3 consecutive
  cycles, falls below **$20.92** — the campaign's own wide/crisis-cost backtest threshold, the
  specific value at which the edge stopped being statistically distinguishable from noise
  (p=0.22). This is not an invented number; it is the campaign's own pre-computed breakpoint.
- **T3 — Tail-correlation worsening.** Restricted to cycles with a realized net loss, the trailing
  Pearson correlation between this sleeve's cycle P&L and Core v1's combined SPY+QQQ trend-sleeve
  daily P&L over the same dates, computed on a rolling 8-cycle window (~9 months at 10.4
  cycles/yr), falls below **-0.8** for 2 consecutive rolling windows. Instrument: SPY+QQQ trend
  sleeves. Statistic: Pearson correlation of P&L, loss-cycles only. This checks whether the
  already-flagged concentration risk has gotten materially worse than the single COVID
  observation showed — not a restatement of the known, accepted risk.
- **T4 — Win-rate collapse.** Trailing 20-cycle win rate falls below **65%** (backtested 88.2%;
  win rate was stable and load-bearing across all 60 structures in the robustness sweep, so a
  material drop signals a real regime or execution shift, not sampling noise).

**T2 — Defined-risk breach (operational integrity, immediate, no override, takes precedence over
all other considerations).** Any single cycle loses more than its structurally-defined max risk
(~$553 per contract at the tested 2%-wing structure, recalculated against the actual live strikes
each cycle). The entire point of this structure is a hard cap; a loss beyond it means the
structure itself failed — an assignment, early exercise, or execution/margin failure — not an
ordinary bad cycle.

## What a re-evaluation authorizes

A triggered re-evaluation authorizes exactly:

1. a documented review comparing live behavior against this document;
2. a written finding: within-plan / degraded / operationally compromised;
3. if degraded or compromised — a decision among: continue with explicit acknowledgment, reduce
   or suspend position size, or close the sleeve.

A re-evaluation never authorizes retuning the structure's DTE/delta/wing parameters against live
results without a new governed campaign — that is exactly the retuning-on-live-draws trap this
repo's culture exists to guard against — nor retroactive restatement of the record.

## Within-plan outcomes (recorded to prevent future panic)

An occasional losing cycle, including one of crisis magnitude (the 127-cycle backtest showed
15/127 losing cycles, one at -$455 against $553 max risk during COVID) is within plan, provided
the loss stays within the structurally-defined max risk — that is T2's entire job, and a bounded
loss is the structure working as designed, not failing. A losing cycle that coincides with an
equity-sleeve drawdown is expected and already acknowledged; it is not itself a trigger unless
T3's specific threshold is met.

## Authorization boundary

This document authorizes monitoring, reporting, and the re-evaluation procedure above, once and
if the sleeve goes live. It does **not** authorize opening or funding a brokerage account,
beginning execution, or any capital, runtime, or production change — those remain gated exactly as
recorded in `docs/ITERA_CAMPAIGN_BOARD.md` (Gate 2 brokerage approval, Gate 5 fill/commission
verification), unchanged by this filing.
