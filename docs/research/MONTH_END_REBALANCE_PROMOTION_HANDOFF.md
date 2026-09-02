# Promotion Handoff — Month-End Equity/Bond Rebalancing Pressure

**Date:** 2026-09-02  
**Source:** `docs/research/EXPLORATION_MONTH_END_REBALANCE_PRESSURE_SCREEN.md`  
**Sandbox status:** `SCREEN_POSITIVE`  
**Governance:** promotion only; no runtime, portfolio, Core v1, Core v2, paper, or live authorization.

## Headline

The pre-registered sandbox screen passed its frozen 3-session month-end gate on 275 valid monthly observations from 2003-10 through 2026-08 using adjusted SPY and AGG data.

Primary evidence:

- Spearman(signal, 3-session SPY-minus-AGG outcome) = **-0.2486**;
- one-sided within-5-year-block permutation p = **0.000999**;
- causal expanding-tercile low-signal minus high-signal relative-return spread = **+0.8478%**;
- one-sided permutation p = **0.001998**;
- every eligible leave-one-year-out aggregate Spearman remained negative;
- decade-level Spearman remained negative in the 2000s, 2010s, and 2020s.

The backtest figures above are discovery-contaminated sandbox ceilings, not live expectations.

## Mechanism-specific Red Team placebo

A pre-specified adversarial placebo compared the actual final-3-session month-end window with otherwise analogous 3-session windows ending 5, 10, and 15 sessions before month-end.

Actual month-end:

- rho **-0.2486**;
- low-minus-high spread **+0.8478%**.

Placebos:

- minus 5 sessions: rho -0.0483; spread -0.1490%;
- minus 10 sessions: rho -0.0716; spread +0.2197%;
- minus 15 sessions: rho -0.0181; spread +0.4267%.

Result: `MONTH_END_SPECIFICITY_SURVIVES`. The month-end window was more negative in rank association and larger in causal-tercile spread than all three frozen placebo windows.

This rejects the narrow objection that the sandbox result is merely generic 3-session equity/bond reversal independent of month-end location. It does not by itself prove pension rebalancing is the unique causal source.

## Staff interpretation

### CIO

**PROMOTE TO GOVERNED RESEARCH, subject to CEO authorization to charter a new direction.** The candidate has a structural, non-alpha-maximizing counterparty (policy-weight/risk-budget rebalancing), free tradeable instruments, a multi-decade sample, a strong pre-registered sandbox result, and calendar-location specificity.

Likely structural-deficiency fit: **#2 — single return source (pure trend)**. This candidate is event/calendar/relative-allocation-flow driven rather than another trend transformation. It should not be treated as a Core v2 component merely because it maps to a deficiency.

### Quant Research

A promoted campaign must start fresh. The sandbox sample is discovery-contaminated and cannot serve as untouched confirmation. The campaign should freeze a minimal mechanistic specification before any additional outcome search, including a confirmation design that preserves a truly untouched temporal or independent-market holdout.

### Red Team

Current in-thread review is **CONDITIONAL / non-independent** because this environment cannot spawn a genuinely separate subagent context. The window-specificity placebo passed. Before the candidate is called `ALIVE`, an independent Red Team must still test at minimum:

- rolling rather than expanding state construction;
- robust/trimmed and median-sensitive outcome summaries;
- serial dependence and calendar clustering;
- multiple-comparison history across sandbox ideas and within this candidate;
- whether adjusted ETF total-return data introduce any dividend/ex-date calendar interaction around month-end;
- alternative liquid equity/bond proxies as a mechanism check, not parameter shopping;
- untouched holdout integrity.

### Risk / PM

No sizing or portfolio-fit inference is authorized. If the research survives independent Red Team, the economic object is likely a short-horizon relative equity/bond tilt around month-end, which could interact with existing equity exposure and future rates exposure. Correlation, turnover, implementation costs, and gross/net exposure must be measured later.

### Ops / Compliance

SPY/AGG are accessible plain US ETFs and the horizon is multi-session. No new venue or product approval is implied by the research concept. Execution assumptions remain untested.

### Performance

The +0.8478% low-minus-high historical spread is a selected sandbox backtest ceiling. No realistic live expectation should be assigned until governed confirmation and cost modeling exist.

## Promotion boundary

Per `docs/ITERA_EXPLORATION_SANDBOX.md`, a `SCREEN_POSITIVE` returns to the normal governed pipeline. Chartering this as a new research direction requires CEO approval under the Itera org charter.

**CEO decision required:** authorize or decline promotion of Month-End Equity/Bond Rebalancing Pressure into a normal governed research campaign.

Until that decision:

- no campaign number is assigned;
- no new outcome computation is authorized;
- no holdout is opened or selected post hoc;
- no Core v1/Core v2/runtime/portfolio/paper/live behavior changes.
