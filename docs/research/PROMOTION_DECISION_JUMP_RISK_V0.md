# Promotion Decision — Jump Risk Engine v0

**Decision date:** 2026-07-16  
**Research branch:** `research/jump-risk-portfolio-v0`

## Decision

**Research status:** COMPLETE  
**Predictive validation:** PASS  
**Portfolio integration:** PASS  
**Paper-trading candidacy:** APPROVED SUBJECT TO TIMING AUDIT  
**Production runtime:** NOT APPROVED

## Approved Candidate

`btc_eth_aligned_upside`

Frozen center parameters:

- risk quantile: 0.95
- boost scale: 1.15x
- incremental overlay cost assumption: 6 bps
- effective probability lag: one hourly bar
- direction source: canonical Core only

Jump Risk may increase existing aligned BTC and ETH trend participation. It may not create standalone directional exposure.

## Evidence

Relative to canonical Core:

| Metric | Core | Candidate | Delta |
|---|---:|---:|---:|
| CAGR | 19.93% | 21.02% | +1.09 pp |
| Sharpe | 1.318 | 1.400 | +0.082 |
| Calmar | 1.208 | 1.347 | +0.139 |
| Maximum drawdown | -16.50% | -15.60% | +0.90 pp |

Additional evidence:

- improved five of six OOS calendar years,
- 18/18 nearby tested configurations passed the predeclared portfolio gates,
- BTC and ETH both contributed positive incremental P&L,
- intervention frequency was sparse,
- performance degraded coherently under higher costs.

## Rejected Implementations

The following are not approved:

- BTC downside exposure governor,
- BTC + ETH downside exposure governor,
- combined asymmetric governor using downside suppression.

These mappings degraded risk-adjusted performance and drawdown behavior.

## Mandatory Pre-Integration Condition

The candidate's benefit decays sharply after the first implementation bar. Before paper activation, engineering must verify:

1. source bar close timestamp,
2. feature-completion timestamp,
3. model-inference timestamp,
4. signal availability timestamp,
5. portfolio decision timestamp,
6. executable order timestamp,
7. the exact return interval governed in research.

Paper integration is blocked unless the runtime can reproduce the research timing without using information unavailable at the decision point.

## Engineering Guardrails

Operational work must:

- use frozen research parameters,
- default the module to disabled,
- preserve the existing Core baseline path,
- run baseline and candidate in parallel,
- emit signal, threshold, scale, timing, cost, and attribution telemetry,
- prevent Jump Risk from creating standalone direction,
- support immediate rollback,
- avoid modifying live capital or production execution behavior.

## Final Classification

`PAPER_TRADING_CANDIDATE_PENDING_TIMING_VERIFICATION`

This document approves engineering work only. It does not approve live deployment or replacement of canonical Core v1.