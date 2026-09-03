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
| Recovery Trust Gate | Retroactively closed — diagnostic negative, never governed | UNESTABLISHED (one ungoverned run) | Never attempted | Not promoted | `RECOVERY_TRUST_GATE_RETROACTIVE_CLOSURE.md` |
| Itera Residual Predictability Census (Campaign #58) | Phase 1 spec frozen, Red Team `CONDITIONAL_PASS` (10 conditions applied); grid-level power test run for real — **FAIL (45.8%)**; CEO fork open. Phase 0 blocked on data access | Not started | Not tested | None | `CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md` |
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

### Recovery Trust Gate

- Real ML infrastructure (~3,000 lines, Logistic/RF/GBM, walk-forward folds) that gated
  Core's own re-risk exposure decisions. Never chartered, never reached a governed artifact.
- Documented outcome: diagnostic negative, not productionized.
- Retroactively closed 2026-09-03 to remove the ungoverned gap before Campaign #58 opened.
- Lifecycle: **RETROACTIVELY CLOSED — not reopened as-is; any future work is a new charter.**

### Itera Residual Predictability Census (Campaign #58)

- Planning charter recorded 2026-09-03 after full staff review (CIO, Quant, independent Red
  Team, Risk/PM) of whether an ML research arm is justified by Itera's actual ML history.
- Independent Red Team: CONDITIONAL PASS on the research direction, eight binding conditions.
- Two tracks proposed: Phase 0 (primary) cross-sectional COT feature-family census; Phase 1
  (secondary) time-series residual census on BTC/ETH/SPY/QQQ/GLD.
- Frozen kill condition: `ML_COMPLEXITY_NOT_JUSTIFIED` if no candidate clears FDR + fold
  stability + permutation-negative-control across the full frozen grid.
- CEO authorized the specification-freeze prerequisites 2026-09-03; staff ran them for real.
  **Phase 0 blocked on data/network access** (no COT data committed, no outbound network access
  in this session — verified), unresolved. **Phase 1: real power result, first pass, FAIL** —
  13.0% average power at the central IC on the base BTC-only price-state family (session-local
  data only). **CEO then ran the same script locally against the real, full BTC/ETH/SPY/QQQ/GLD
  dataset — PASS, 58.3% average power at the central IC**, 2,527 real pooled anchors, headline
  number independently recomputed and confirmed by staff. Not uniform: 5 of 7 candidates clear
  65-75%, two (drawdown, volatility) fall under 50% individually. Leakage canary proven capable
  of failing on synthetic data; regime-source restricted to the causal engine path;
  hyperparameters fixed per model type. Full record:
  `CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md`.
- **Phase 1 statistical specification frozen** (144-candidate grid: 16 feature-variants × 3
  horizons × 3 outcome families R/M/V) and **independently Red-Teamed — `CONDITIONAL_PASS`, 10
  conditions, all applied same day.** Corrections: material-margin threshold recalibrated from an
  untested flat 0.02 to the census's own central-IC-implied effect size (≈0.0042); negative-
  control and lift-FDR tests now explicitly replicate the full model-selection procedure per
  resample; underpowered-feature list explicitly closed; charter's Risk/PM correlation-to-
  Core-NAV check reinstated. Full record: `CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md`,
  `CAMPAIGN_58_PHASE1_SPEC_INDEPENDENT_RED_TEAM_REVIEW.md`.
- **Grid-level power test run for real (all 3 outcome families) — FAIL.** Overall average power
  45.8% against the 50% floor, trial-adequacy confirmed (min 39 ≥ 20 required). Per family: R
  54.9%, M 41.8%, V 40.6%. Independently confirms the Red Team's own concern: a Family-R-only
  calibration would have overstated true grid power by 9.1 points (54.9% false PASS vs. the real
  45.8%). Used as computed, no design element adjusted after seeing it. One honest, explicitly
  post-hoc question raised but not acted on: the calibration's residualized-variant columns are
  numerically identical to raw ones, creating 72 exact-duplicate pairs that may have inflated
  the effective FDR family size beyond what a real run would show — flagged, not used to
  override the FAIL. Full record: `CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md` §15.
- **Real model-fitting remains NOT authorized** under the standing 2026-09-03 CEO authorization,
  independent of the Red Team verdict or this power result.
- Lifecycle: **GRID-LEVEL POWER FAIL (real, 45.8%) — CEO fork open: close the track, or
  independently check the post-hoc duplication concern first. Model-fit not authorized. Phase 0
  still blocked on data/network access.**

## Canonical Research Documents

- `CANDIDATE_HORIZON_FEASIBILITY_SWEEP.md`
- `RESEARCH_STATUS_2026-07-15.md`
- `RESEARCH_PROMOTION_POLICY.md`
- `JUMP_RISK_PORTFOLIO_V0_CHARTER.md`
- `JUMP_RISK_V0_FINAL.md`
- `JUMP_RISK_V0_TIMELINE.md`
- `PROMOTION_DECISION_JUMP_RISK_V0.md`
- `TREND_PERSISTENCE_V0_FINAL.md`
- `RECOVERY_TRUST_GATE_RETROACTIVE_CLOSURE.md`
- `CAMPAIGN_58_ITERA_RESIDUAL_PREDICTABILITY_CENSUS_CHARTER.md`
- `CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md`
- `CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md`
- `CAMPAIGN_58_PHASE1_SPEC_INDEPENDENT_RED_TEAM_REVIEW.md`

## Separation of Responsibilities

Research branches determine whether an idea is supported by evidence. Feature branches operationalize frozen, approved candidates. No feature branch may silently retune a completed research candidate.