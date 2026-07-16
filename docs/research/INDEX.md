# Itera Dynamics Research Index

This index is the front door to Itera Dynamics research. It distinguishes predictive validation, portfolio value, paper candidacy, and runtime status.

| Program | Research status | Predictive evidence | Portfolio result | Runtime status | Primary document |
|---|---|---|---|---|---|
| Core v1 | Complete | Deterministic strategy baseline | Canonical portfolio | Paper runtime active | `RESEARCH_STATUS_2026-07-15.md` |
| Jump Risk Engine v0 | Complete | Validated on BTC; locked transfer validated on ETH | PASS — aligned-upside mapping | Paper candidate pending timing audit | `JUMP_RISK_V0_FINAL.md` |
| Trend Persistence Engine v0 | Complete | Validated continuation ranking | REJECT — tested sleeve mappings hurt Core | Not promoted | `TREND_PERSISTENCE_V0_FINAL.md` |
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
- Downside governors: REJECTED
- BTC + ETH aligned-upside mapping: PASS
- Paper candidacy: APPROVED SUBJECT TO TIMING AUDIT
- Production runtime: NOT APPROVED

### Trend Persistence Engine v0

- Predictive signal: VALIDATED
- Continuous sleeve gating/scaling mappings: REJECTED
- Research lifecycle: COMPLETE — NOT PROMOTED

## Canonical Research Documents

- `RESEARCH_STATUS_2026-07-15.md`
- `RESEARCH_PROMOTION_POLICY.md`
- `JUMP_RISK_PORTFOLIO_V0_CHARTER.md`
- `JUMP_RISK_V0_FINAL.md`
- `JUMP_RISK_V0_TIMELINE.md`
- `PROMOTION_DECISION_JUMP_RISK_V0.md`
- `TREND_PERSISTENCE_V0_FINAL.md`

## Separation of Responsibilities

Research branches determine whether an idea is supported by evidence. Feature branches operationalize frozen, approved candidates. No feature branch may silently retune a completed research candidate.