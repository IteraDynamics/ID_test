# Campaign #57 — Validation Architecture Amendment 2

**Date:** 2026-09-02

**Status:** ADOPTED by explicit CEO authorization after the first historical-validation power architecture failed pre-outcome. This amendment supersedes Campaign #57 charter Sections 4.2A, 4.3–4.5, 5, 6, and 11 only where they conflict with this document. All Core v1/runtime/portfolio/paper/live prohibitions remain unchanged.

## 1. Why this amendment exists

The first Campaign #57 validation architecture was frozen before VTI/BND outcome inspection and split 232 valid common months into 116 development, 58 chronological OOS, and 58 final holdout months. A timestamp-only preflight then estimated joint-gate power at the central 50% selection-bias haircut:

- OOS power: 16.2%;
- final-holdout power: 18.0%;
- required floor: 80% for each.

No VTI/BND close, return, signal, or outcome was read by that preflight. Therefore this was a design-power failure, not evidence about the hypothesis.

The failure is structural: the central haircutted effect is Spearman approximately -0.1243, while two independent ~58-month tests cannot plausibly attain 80% power, especially when burdened by a second co-primary statistic and leave-one-year-out requirements.

The CEO explicitly authorized a validation-architecture redesign while VTI/BND returns remain sealed.

## 2. Evidentiary architecture

Campaign #57 now uses four distinct evidence roles.

### A. Discovery — already spent

SPY/AGG sandbox history, 2003–2026. Fully discovery-contaminated. It may define the frozen mechanism and effect-size ceiling but can never be a historical confirmation holdout.

### B. Long-history historical confirmation — new one-shot test

Primary proposed source pair: **VFINX / VBMFX** adjusted total-return series, subject to source/calendar feasibility only.

Economic mapping:

- VFINX: broad large-cap US equity index-fund proxy;
- VBMFX: broad US investment-grade total-bond-market index-fund proxy.

The pair is chosen before any Campaign #57 outcome inspection because it extends materially earlier than BND and can potentially provide the ~400+ monthly observations required for an adequately powered one-shot historical confirmation at the conservatively haircutted effect.

This pair is not assumed usable merely because the tickers exist. Before any return is read for Campaign #57, a timestamp-only source/calendar preflight must establish:

- adjusted-price source availability;
- common valid monthly support;
- deterministic month-end calendar construction;
- sufficient simulated power under Section 4.

If the proposed pair is unavailable, malformed, or underpowered, the campaign stops and records that source/architecture failure. No alternate pair may be substituted after any Campaign #57 long-history return outcome is inspected.

### C. VTI/BND — modern cross-instrument replication, still sealed

The already-downloaded VTI/BND files remain unspent: no Campaign #57 close, return, signal, or outcome has been inspected.

VTI/BND is no longer partitioned into 50/25/25 blocks. That architecture is formally retired as underpowered.

VTI/BND instead serves as a **modern cross-instrument replication** only after the long-history historical confirmation passes. It is not called an independent temporal holdout because its calendar events overlap the long-history US equity/bond sample.

Its role is transportability/modernity: determine whether the same frozen rule has the expected direction and comparable effect shape in the ETF era using different instruments.

### D. Future-forward SPY/AGG — genuine chronological OOS/final holdout

The only genuinely new market-event evidence is future data observed after the specification freeze. A prospective SPY/AGG ledger remains the final chronological OOS evidence before any capital decision.

No amount of overlapping historical proxy replication substitutes for this forward record.

## 3. Frozen historical-confirmation hypothesis

For each valid calendar month:

1. anchor = final common session of the prior month;
2. cutoff = close immediately before the final three common trading sessions;
3. signal = equity adjusted-total-return performance from anchor to cutoff minus bond adjusted-total-return performance over the same interval;
4. outcome = equity adjusted-total-return performance from cutoff to month-end minus bond adjusted-total-return performance over the same interval.

Expected relationship: **negative monotonic association** between signal and outcome.

The final-three-session window remains frozen. No 1-day, 5-day, quarter-end-only, threshold, alternate-window, or alternate-sign variant may rescue a failure.

## 4. Historical-confirmation statistical gate

### Primary test — exactly one

Spearman rank correlation between monthly signal and 3-session relative outcome.

Requirements:

- observed rho < 0;
- one-sided permutation p <= 0.05;
- permutation shuffles signal within five-year calendar blocks while outcomes remain fixed;
- fixed seed and permutation count are committed before outcome inspection.

This single primary test replaces the former dual co-primary significance gate. The change is made solely because the pre-outcome power study demonstrated that the redundant joint gate made meaningful confirmation impossible with available history. The economic hypothesis itself is unchanged.

### Required robustness diagnostics — not additional significance gates

All must be reported and have the expected qualitative direction, but they do not each require p <= 0.05:

- causal expanding-tercile low-signal minus high-signal outcome spread > 0;
- decade/era Spearman diagnostics;
- leave-one-calendar-year-out aggregate rho distribution, with any sign reversal explicitly reported;
- top absolute-signal months and outlier sensitivity;
- actual month-end rho compared descriptively with the already-frozen -5/-10/-15-session placebo construction.

A primary pass accompanied by a severe robustness failure is `HISTORICAL_CONFIRMATION_CONDITIONAL`, not `CONFIRMED`, and must go to independent Red Team before any further promotion.

## 5. Pre-outcome power gate for long-history confirmation

Before any VFINX/VBMFX Campaign #57 return is read:

- use timestamps/calendar only;
- central injected effect = 50% of the SPY/AGG sandbox Spearman ceiling, i.e. approximately -0.1243063;
- sensitivity haircuts = 25%, 40%, 50% of the sandbox Spearman ceiling;
- 500 outer simulations per haircut;
- 199 within-five-year-block permutations per simulation;
- fixed seed = 20260957;
- power floor = 80% for the single primary historical-confirmation test at the central 50% haircut.

If power < 80%, do not inspect historical-confirmation outcomes. Record `LONG_HISTORY_CONFIRMATION_UNDERPOWERED`.

The prior 50/25/25 VTI/BND power result remains archived and is not rerun or reinterpreted.

## 6. VTI/BND modern replication gate

Only if the long-history historical confirmation passes may VTI/BND be opened.

Because VTI/BND shares calendar events with the long-history confirmation, it is not given a second nominal p-value-based confirmation role. Instead it is a transportability check under the already-frozen rule.

Required:

- Spearman rho < 0;
- causal expanding-tercile low-minus-high spread > 0;
- no implementation/timing/source defect;
- effect-size estimate and confidence interval reported against the long-history estimate and the original SPY/AGG discovery ceiling.

Failure is evidence against transportability/modern persistence and blocks any claim that the mechanism is currently alive, even if the longer historical sample passes.

## 7. Monte Carlo / bootstrap

Monte Carlo begins only after the long-history historical confirmation passes.

Before VTI/BND is opened, Monte Carlo may use only the legitimately opened long-history confirmation event series. After VTI/BND is opened, it may incorporate that replication series only with explicit treatment of overlapping calendar events; the two proxy pairs may not be naively pooled as independent observations.

Monte Carlo/bootstrapping is for uncertainty, finite-sample path dispersion, and later economic implementation risk. It never substitutes for the prospective SPY/AGG holdout.

## 8. Current authorization

Authorized now:

1. acquire VFINX/VBMFX adjusted daily research data using the existing zero-dollar downloader;
2. inspect timestamp/calendar metadata only;
3. run the frozen long-history pre-outcome power simulation under Section 5;
4. write deterministic manifests/hashes and record the feasibility/power result.

Not authorized yet:

- any Campaign #57 VFINX/VBMFX return, signal, or outcome computation;
- any VTI/BND return, signal, or outcome computation;
- economic backtesting;
- Core v2 composition/sizing;
- paper/live trading or capital deployment;
- any Core v1 change.

## 9. Governance interpretation

The first 50/25/25 architecture is not silently rewritten or erased. It remains a documented `HISTORICAL_ARCHITECTURE_UNDERPOWERED` result. This amendment is a CEO-authorized, pre-outcome redesign responding to a statistical feasibility failure while all prospective validation returns remain sealed.
