# Itera Dynamics Research Index

This index is the front door to Itera Dynamics research. It distinguishes predictive validation, portfolio value, paper candidacy, and runtime status.

| Program | Research status | Predictive evidence | Portfolio result | Runtime status | Primary document |
|---|---|---|---|---|---|
| Core v1 | Complete | Deterministic strategy baseline | Canonical portfolio | Paper runtime active | `RESEARCH_STATUS_2026-07-15.md` |
| Jump Risk Engine v0 | Complete — retired | Validated on BTC; locked transfer validated on ETH; timing provenance verified | PASS at research lag; REJECT at achievable lag | RETIRED — not deployable at runtime cadence | `JUMP_RISK_V0_FINAL.md` |
| Trend Persistence Engine v0 | Complete — retired | Validated continuation ranking; 3h candidates operationally unreachable | REJECT — tested sleeve mappings hurt Core | RETIRED — not promoted; 3h family infeasible at runtime cadence | `TREND_PERSISTENCE_V0_FINAL.md` |
| Research Engine v1 | Active platform capability | Reproducibility, caching, auditing, registry | Infrastructure, not a portfolio signal | Research only | `RESEARCH_STATUS_2026-07-15.md` |
| Volatility Expansion Engine | Planned | Not started | Not tested | None | — |
| Liquidity Compression Engine | Planned | Not started | Not tested | None | — |
| Cross-Asset Leadership Engine | Planned | Not started | Not tested | None | — |
| Learned Regime / Representation Research | Future | Not started | Not tested | None | — |

## Lifecycle Vocabulary

- **Discovery:** initial hypothesis and broad experiment generation.
- **Validated signal:** predictive evidence survives walk-forward, ablation, robustness, and required audits.
- **Portfolio trial:** frozen signal is mapped into actions against canonical Core.
- **Paper candidate:** portfolio trial passes, but operational timing and implementation remain unproven.
- **Production:** live promotion approved after engineering validation and paper observation.
- **Completed — not promoted:** research answered its question but did not improve Core under the tested mapping.

See `RESEARCH_PROMOTION_POLICY.md` for formal gates.

## Current Decisions

### Jump Risk Engine v0

- Predictive engine: VALIDATED
- BTC-to-ETH transfer: VALIDATED
- Timing provenance (2026-08-10): VERIFIED — no lookahead
- Downside governors: REJECTED
- BTC + ETH aligned-upside mapping at research lag: PASS
- Live runtime cadence (2026-08-10): ~1.5-1.7 effective bars
- Mapping at achievable lag (2026-08-11): REJECT — 98% of the edge expires by bar 2
- Paper candidacy: **WITHDRAWN**
- Lifecycle: **RETIRED — sound research, not reachable on this infrastructure**
- Production runtime: NOT APPROVED

### Trend Persistence Engine v0

- Predictive signal: VALIDATED
- Continuous sleeve gating/scaling mappings: REJECTED (all tested mappings degraded Core)
- Horizon feasibility (2026-08-11): 3h "central finding" candidates INFEASIBLE — a ~1.6h
  decision lag consumes 53% of the horizon; 60h/120h candidates remain feasible
- Research lifecycle: **RETIRED** on two independent grounds — mapping economics and
  operational reachability
- Any future work: restricted to 60h+ candidates, chartered as new research, not as a rescue
  of the 3h finding

## Canonical Research Documents

- `CANDIDATE_HORIZON_FEASIBILITY_SWEEP.md`
- `RESEARCH_STATUS_2026-07-15.md`
- `RESEARCH_PROMOTION_POLICY.md`
- `JUMP_RISK_PORTFOLIO_V0_CHARTER.md`
- `JUMP_RISK_V0_FINAL.md`
- `JUMP_RISK_V0_TIMELINE.md`
- `PROMOTION_DECISION_JUMP_RISK_V0.md`
- `TREND_PERSISTENCE_V0_FINAL.md`

## Separation of Responsibilities

Research branches determine whether an idea is supported by evidence. Feature branches operationalize frozen, approved candidates. No feature branch may silently retune a completed research candidate.