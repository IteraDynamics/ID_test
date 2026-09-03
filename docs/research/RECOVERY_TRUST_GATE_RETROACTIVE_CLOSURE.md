# Recovery Trust Gate — Retroactive Governance Closure

## Status

**RETROACTIVELY CLOSED — DIAGNOSTIC NEGATIVE, NEVER CHARTERED, NEVER PROMOTED.**

This document formally closes a research program that was built and run without ever
entering Itera's governed campaign process. It creates no new evidence and authorizes no
new work. It exists because the independent Red Team review of the proposed ML research
arm (`docs/research/CAMPAIGN_58_ITERA_RESIDUAL_PREDICTABILITY_CENSUS_CHARTER.md`) named
this gap as a precondition: a new bounded ML program should not open while an old,
materially larger one sits abandoned outside governance.

## What was built

`research/ml/recovery_trust/` — a five-module pipeline (`candidate_detector.py`,
`feature_builder.py`, `labeler.py`, `model.py`, `scaler.py`; 1,139 lines) plus two diagnostic
runner scripts (`scripts/run_recovery_trust_experiment.py`,
`scripts/run_recovery_trust_segmentation.py`; 1,827 lines) — roughly 3,000 lines in total,
larger than either Jump Risk's or Trend Persistence's core research module.

The design: detect "candidate re-risk events" — bars where a Core sleeve's strategy proposes
a significant exposure increase (`+10pp` minimum, to `>=25%` new exposure) after a defensive
period — label each as a genuine recovery or a fake rebound using forward price performance
(`+5%`/`-10%` drawdown thresholds, 60-day horizon), build a leakage-safe feature matrix from
data available only up to the candidate timestamp, and train a walk-forward (expanding
chronological folds) logistic regression / random forest / gradient boosting classifier to
gate how much of the proposed exposure increase Core is allowed to take
(`>=0.70` confidence → full size, `0.50-0.70` → half, `0.35-0.50` → quarter, `<0.35` → block).
The stated invariant — ML never blocks exits, only scales entries — mirrors the discipline
Jump Risk's final mapping used (never create standalone direction, only modulate an
already-Core-determined action).

This is real, competently structured ML research infrastructure. It was never a toy.

## What happened to it

It never received a campaign charter, a board entry, a frozen specification, a promotion
decision, or a closure record anywhere under `docs/`. The only trace of its outcome in the
entire repository is one sentence in an unrelated document
(`research/trade_idea_radar/CROSS_ASSET_STATE_AUDIT.md`, "ML status" section):

> "The recovery-trust ML gate remains a research/diagnostic negative result. It is not
> productionized by this branch."

No governed artifact records the fold-by-fold AUC, precision/recall, sample sizes, or which
sleeve(s) it was tested against. `run_recovery_trust_experiment.py`'s own header labels it
"DIAGNOSTIC MODE ONLY... no portfolio comparison" — it was never brought to Jump Risk's or
Trend Persistence's standard of robustness sweep, cross-asset transfer test, or economic
portfolio-mapping trial before being abandoned.

## Why this matters, and why it is closed now rather than re-run

Two things are true at once, and this closure does not try to resolve the tension by
re-running anything:

1. **The one negative documented result is credible as far as it goes** — it is consistent
   with Jump Risk's and Trend Persistence's own experience (predictive skill, where it
   existed at Itera, has consistently been on rare/short-horizon event classification with
   econometrically simple features, not on gating a specific sleeve's re-risk decisions from
   a `equity_sma175_v3`-style feature set).
2. **The negative result was never resourced to a standard that could distinguish "no real
   information here" from "under-built research that stopped early."** No robustness sweep,
   no cross-asset check, no FDR-controlled multi-candidate design, no replay-verified
   artifact. Unlike Campaign #48's volatility-clustering null (rigorously established: 72
   pre-frozen candidates, FDR-controlled, chronologically partitioned, replay-verified) or
   Trend Persistence's portfolio-mapping rejection (5 mappings tested against a reconciled
   52,374-row canonical sleeve matrix), Recovery Trust's negative is a single diagnostic run
   with no governed evidence trail.

Re-running it now would be new research, not closure, and is explicitly out of scope for this
document (per the standing instruction that no new model training or holdout consumption is
authorized without a charter that says so). This closure instead does what governance can do
without new data: **make the historical record accurate.**

## Closure determination

| Dimension | Determination |
|---|---|
| Predictive evidence | UNESTABLISHED — one ungoverned diagnostic run, not independently verified |
| Governance status | NEVER CHARTERED — retroactively logged as closed, not reopened |
| Portfolio integration | NEVER ATTEMPTED |
| Production/paper promotion | NOT APPROVED |
| Reopening path | Only as a new, narrowly chartered campaign under the standing research process
amendments (power analysis, FDR, pre-registered holdout) — not a resumption of this branch's
code as-is. Any reopening should explicitly decide, before writing new code, whether it
duplicates scope with the Itera Residual Predictability Census (Campaign #58) rather than
running in parallel with unclear ownership. |

## Institutional lesson

Itera's deterministic statistical campaigns (Campaign #48 and onward) have never shipped a
result — positive or null — without a frozen spec, a replay-verified artifact, and a board
entry. Both of the fund's genuinely rigorous ML programs (Jump Risk, Trend Persistence)
eventually met that same bar, but only because they were escalated all the way to portfolio
integration. Recovery Trust shows the gap: a research program can be built, run, and
abandoned entirely inside the informal layer, with no governance trigger forcing it to either
close properly or be pursued further. Campaign #58's charter adopts an explicit rule to close
this gap going forward: **any ML program that reaches a model-fit stage receives the same
freeze-before-outcome, replay, and closure discipline as a deterministic statistical campaign,
regardless of whether the result is positive or negative.**
