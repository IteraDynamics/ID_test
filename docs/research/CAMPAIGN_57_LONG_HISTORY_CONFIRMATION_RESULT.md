# Campaign #57 — Long-History Historical Confirmation Result

**Date:** 2026-09-02

**Classification:** `HISTORICAL_CONFIRMATION_CONDITIONAL`

**Boundary:** Campaign #57 historical confirmation only. No Core v1/Core v2/runtime/portfolio/paper/live/capital action authorized.

## Primary result

The frozen VFINX/VBMFX long-history confirmation primary test passed:

- valid months: 476, 1987-01 through 2026-08;
- Spearman rho: `-0.15244871334829863`;
- one-sided within-five-year-block permutation p: `0.00039996000399960006`;
- primary gate: PASS.

The long-history preflight had estimated 85.2% power at the frozen central 50%-haircut target effect (rho approximately -0.1243063), so this was an adequately powered one-shot historical confirmation rather than an exploratory look.

## Frozen robustness diagnostics

Expected-direction checks that passed:

- causal expanding-tercile low-minus-high spread: `+0.005032946769806541`;
- all eligible leave-one-year-out aggregate rhos negative;
- rho after removing the 10 largest absolute-signal months: `-0.11824842187148416`;
- actual month-end rho more negative than all frozen -5/-10/-15-session placebos;
- placebo rhos: -5 sessions `+0.0100114`, -10 sessions `-0.0796748`, -15 sessions `-0.0353594`.

The sole frozen robustness concern was era consistency. Decade-level Spearman:

- 1980s (36 months): `-0.3441441`;
- 1990s (120 months): `+0.0286548`;
- 2000s (120 months): `-0.1744913`;
- 2010s (120 months): `-0.2986666`;
- 2020s (80 months): `-0.0990155`.

Because the 1990s decade had the wrong sign, the runner correctly classified the result `HISTORICAL_CONFIRMATION_CONDITIONAL` under Validation Architecture Amendment 2 rather than promoting it as clean confirmation.

## Interpretation

The primary historical confirmation succeeded strongly and the result is not driven by one year, the largest signal months, or generic nearby three-session reversal. However, the 1990s sign reversal is a real regime-consistency weakness and must not be waved away post hoc.

Per `docs/research/CAMPAIGN_57_VALIDATION_ARCHITECTURE_AMENDMENT_2.md`, a primary pass accompanied by a severe robustness failure must go to genuinely independent Red Team before any further promotion. This environment cannot supply the required independent subagent context.

VTI/BND remains sealed. It may not be opened unless independent Red Team explicitly determines that the conditional long-history result is sufficient to proceed to the modern transportability replication under the frozen Amendment 2 role.

## Source identities

- VFINX adjusted CSV SHA256: `5d2d54350f18ce221132607102dad0639e51fd4714d5ada29d88b37516639049`
- VBMFX adjusted CSV SHA256: `ee4c45356d3ca4d9cfe6a7cc02a0815797e6fe16274223bfb0aa5f45636aeb1c`

## Next gate

**Independent Red Team review required.** No additional Campaign #57 outcome inspection is authorized before that review.
