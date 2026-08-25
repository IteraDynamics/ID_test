# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

No production or portfolio behavior is authorized unless explicitly stated.

## Most recently closed campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** CLOSED — DEVELOPMENT_NEGATIVE. The governed 2020-2022 hypothesis test completed successfully, failed the frozen development gate, and does not advance to validation.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Campaign #52 objective

Determine whether canonical Core v1 derives material value from authentic chronological alignment of sleeve-level pre-execution signed target exposures.

## Governed records

- planning charter: `8ad9f3aae3dc4b36010ef8f723ae1c88bbf7db9d`
- feasibility inventory: `a86eba5392e57e936d65c4eb46207cb51c03b309`
- family selection: `e2aa9ceafe531e11bea7040fe4309ac9e65b8ab2`
- frozen statistical specification: `14a96b4078eec516570fce0c289baa061398a995`
- source/calendar evidence: `bd2af6c11991a637510122bdb4a3300b9653be14`
- capture/replay adapter: `bf5d7d7d7c18f23ddea6a1c622ce26359ef12393`
- governed-source equivalence PASS: `0db3875d2c181f65b41e06145825f7d5363226e4`
- development procedure: `af30879a0f37b4a635780a9cea5e8cf2b2590e29`
- development helper synthetic PASS: `04b1de5b145a451de38118d6d27562d0bdccfe53`
- governed development runner: `4443496290bdde5762edd8fe0deaf7a523be0c41`
- static-control correction: `98299130ebbc78fc3b0b2d5a98ff3e84ff988d5b`
- timezone and concurrent-pass correction: `c3f9208c3628b6cb4256b28bae0848a4b17c6d9a`
- calendar-compatible permutation amendment: `969cb63032822b57208c3bbcca173c45b0cc6828`
- amended permutation implementation: `752242281e1d079b8821a7510cb066e78e3ac4a9`
- irregular-calendar regression tests: `addfc084d5408b837af32ccb47d9d96f2acb9f68`
- replay-input caching: `abb3262f008d7d0038352cfa8b2bb4562125de6d`
- amendment implementation record: `bae64a8161fbff3a2345bc24ea9abe28494052db`
- development-negative result record: `f566958dc94fdff207355ad8f550720a80aeabb3`
- final interpretation and closure: `bc818fffe33ca5c899140416e1f0dd9588537114`

## Campaign #52 final result

The governed development run completed with:

- status: `PASS`
- classification: `DEVELOPMENT_NEGATIVE`
- development gate passed: `false`
- independent passes: `2`
- controls: `20`
- bootstrap replications per control: `10,000`
- calendar-compatible block permutation: `true`
- validation targets opened: `false`
- canonical strategy invoked: `false`
- runtime, strategy, and weights modified: `false`

Frozen sub-rule outcomes:

- lag rule passed: `false`
- permutation median rule passed: `true`
- static primary wins: `3`

Interpretation:

- canonical beat all three lag controls economically;
- canonical beat the static control on all three primary endpoints;
- canonical beat the permutation median on all three primary endpoints;
- no lag comparison survived Holm adjustment across the full 20-control family;
- Campaign #52 therefore remains a valid confirmatory development negative and validation stays sealed.

## Next campaign

**Status:** CAMPAIGN #53 SELECTED — planning charter recorded; feasibility planning authorized.

**Campaign:** Campaign #53 — Perpetual Funding and Basis Carry

**Charter:** `docs/research/CAMPAIGN_53_FUNDING_CARRY_PLANNING_CHARTER.md`

**Branch:** `claude/research-assessment-feedback-4auusg`

Campaign #53 was selected over a narrower Campaign #52 lag-family follow-up because it
introduces non-price information (funding, basis, open interest) with a documented persistent
premium and a materially higher prior than recent price-derived families. The Campaign #52
lag-family hypothesis remains in the backlog.

Campaign #53 is the first campaign governed by the standing process amendments
(`docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md`): single-document format, mandatory power
analysis, FDR-based discovery with strict confirmation at the untouched holdout.

Standing governance recorded this transition:

- destination charter: `docs/ITERA_DESTINATION_CHARTER.md`
- live benchmark registration: `docs/research/CORE_V1_LIVE_BENCHMARK_REGISTRATION.md`
- live expectation and degradation band: `docs/research/CORE_V1_LIVE_EXPECTATION_AND_DEGRADATION_BAND.md`
- monthly letter series: `docs/letters/`

Authorized now:

- **Campaign #53 bulk data acquisition and specification execution.** Section 3 and Section 4
  (methodology) of `docs/research/CAMPAIGN_53_FUNDING_CARRY_PLANNING_CHARTER.md` are FROZEN as of
  this transition (frozen 2026-08-20, commit `1e561c3`) — universe (BTC/ETH), venue design
  (Deribit discovery, CDE confirmation), roll policy, candidates, and decision rule (FDR q=0.10,
  confirmation top-3) do not change further. Authorized: acquisition of Deribit's multi-year
  funding history and CDE's native ~13-month funding/candle history for BTC and ETH, per the
  governed acquisition design in the charter's own Section 2.
  **Correction, 2026-08-21: the line below conflated two different things.** Amendment 1's
  power simulation (Section 4) — bootstrap real acquired data, inject a hypothetical effect,
  measure whether the frozen gates would detect it — is methodology calibration explicitly
  required *before* any real decision, not a real predictor/outcome computation itself; it
  produces a probability number, not a candidate ranking or a trading signal. That is authorized
  now that discovery-side data exists (Deribit, acquired 2026-08-21). Still not authorized: real
  predictor/outcome computation against actual candidates for an actual discovery/confirmation
  decision, any economic test, or any runtime/strategy/order/execution/NAV/exposure/dashboard
  change;
  **Correction, 2026-08-21 (second): the power simulation ran** — real result, average power at
  the central IC = 45.4%, below the 50% floor as originally specified (six-hypothesis family,
  top-3 confirmation). A block-width diagnostic confirmed the simulation code itself is correct
  (null width scales with measured autocorrelation as expected); the FAIL is real, not an
  artifact. The charter's §3c/§3d are corrected in place (dated appends, not rewrites): window
  set narrowed `{24h,72h,168h}` → `{24h,72h}` on a mechanistic, effect-independent basis (168h
  windows resampled daily collapse effective sample size regardless of true effect), and
  confirmation narrowed top-3 → top-2 to preserve the original ~33% selectivity ratio against the
  now-6-member (was 9) full family. Full reasoning, including explicit engagement with §4's own
  caution against reopening rejected remedies, is in the charter.
  **Correction, 2026-08-24: the corrected family was re-run — PASS, 56.0% average power** at the
  central IC, clearing the 50% floor (uneven across hypotheses: `funding_persistence_24h` strong
  ~84%, `funding_level_72h` weak ~34%; margin above floor is real but thin at 6 points; effect-size
  grid still uncited and confirmation still approximated against a Deribit split, not real CDE
  data — see charter §4 for the full record). This is Amendment 1's pre-execution gate clearing,
  not execution itself.
  **Correction, 2026-08-24 (second): the operator explicitly authorized real predictor/outcome
  computation** against the four discovered-family candidates on real acquired Deribit data —
  the discovery half of §3d's frozen decision rule (real observed correlation, real empirical
  p-value against the block-bootstrapped null, real BH FDR at q=0.10, real top-2 shortlist by
  |correlation|). This does NOT authorize confirmation against the untouched holdout: per §3a-iii,
  the holdout is CDE's live-forward-accumulated funding rate, logged only since
  `scripts/log_cde_live_funding_rate.py` was deployed (2026-08-21) — a few days of data, nowhere
  near enough to confirm anything, and not backfillable. A discovery result without a confirmed
  holdout is not a trading decision and authorizes no economic/runtime/execution action of any
  kind — still not authorized: any of those, or treating an FDR-discovered candidate as validated
  before it clears the untouched holdout.
  **Correction, 2026-08-24 (third): the first real discovery run put `funding_level_24h`
  (r=0.7075) at the top of the shortlist, and it turned out to be a near-tautology, not a
  discovery** — its 24h candidate window, 24h target horizon, and 24h rebalance interval are
  numerically identical, so its "predictive" correlation collapses to the candidate's own lag-1
  autocorrelation regardless of any real relationship (proven independent of this data — see
  charter §3c). `("funding_level", 24)` is now excluded from the statistical family
  (`EXCLUDED_HYPOTHESES`); the currently-implemented family is three hypotheses, not four. The
  prior discovery result is superseded, not archived as valid-with-caveats.
  **Correction, 2026-08-24 (fourth): re-run on the corrected 3-hypothesis family — all three
  cleared FDR discovery** (q=0.10); top-2 shortlist is `funding_level_72h` (r=0.6347) and
  `funding_persistence_72h` (r=0.1922), with `funding_persistence_24h` (r=0.1586) clearing
  discovery but narrowly missing the shortlist. `funding_level_72h`'s strength was independently
  re-checked against the same artifact-detection method that caught the 24h defect and did not
  reproduce it. This is a real discovery result, still not a confirmed finding or a trading
  signal — confirmation against the CDE live-forward holdout remains blocked on accumulated data
  (see above). Full record: charter §3c "Corrected discovery re-run, 2026-08-24".
  **Correction, 2026-08-24 (fifth): the "logged only since ... deployed (2026-08-21)" line above
  overstated the holdout's actual status.** `scripts/log_cde_live_funding_rate.py` was written
  2026-08-21 but never scheduled — confirmed not running as of this correction. It was actually
  scheduled via cron on the operator's droplet for the first time on 2026-08-24 (root crontab,
  `5 * * * *`, alongside `scripts/log_cde_live_funding_rate_cron.sh`, added without disturbing the
  droplet's existing unrelated cron job for a separate system). First real snapshot logged
  2026-08-24T14:56Z. The holdout's true accumulation start is 2026-08-24, not 2026-08-21 — three
  days later than every prior reference in this document implied. Nothing built on the discovery
  side depended on the wrong date; this only affects how much confirmation data exists when it's
  eventually checked.
  **Correction, 2026-08-24 (sixth): open interest, the campaign's third planned signal, closed
  as a negative finding — not pursued further.** The probe's own success check couldn't actually
  fail (any non-empty result counted as a "win" regardless of whether it was open interest); the
  two endpoints actually named for it returned HTTP 400; external docs are unreachable from this
  environment. Circumstantial evidence (dedicated paid vendors exist specifically to sell this
  data) suggests it isn't natively available. Not economically justified to chase further given
  the campaign's two already-discovered candidates haven't even cleared confirmation yet. Full
  record: charter §3c, "Open interest change... Closed 2026-08-24".
  **Correction, 2026-08-25: first real look at the structural (basis) family** — already fully
  specified since 2026-08-14, never touched. Real CDE data shows tiny basis magnitude (BTC
  ≈−3.2bps, ETH ≈−10bps) and liquidity concentrated almost entirely in the front-month dated
  contract (falls to $0/day beyond the second listed contract). Not favorable in this one
  snapshot, but not yet a verdict — a live ladder logger (`scripts/log_cde_basis_ladder.py`,
  root crontab `10 * * * *`, running alongside the funding logger) now watches this hourly;
  the mark-to-market risk tolerance and roll-timing N stay unset until at least one full roll
  cycle (~1 month) has accumulated. Full record: charter §3a-ii, "First real look, 2026-08-25";
- implementation of the registered Core v1 benchmark series (report-only);
- Core v2 charter drafting (`docs/CORE_V2_CHARTER.md`, DRAFT) — documentation only, no runtime
  or capital.

Closed:

- the Core v1 frozen-parameter sensitivity pass (report-only, no retuning) — CLOSED 2026-08-12,
  `docs/research/CORE_V1_PARAMETER_SENSITIVITY_RESULT.md`;
- **Campaign #54 (crash-short hedge sleeve) — CLOSED 2026-08-20.** Sizing sweep run via
  `scripts/run_campaign_54_sizing_sweep.py` (existing audit harness, already-governed BTC/ETH/SPY
  sources, no new data). `crash_short_v6` included in Core v2's founding composition at **15%
  hedge weight**, chosen as the best combination of risk-adjusted metrics without extrapolating
  past the campaign's own judgment-bound evidentiary base. Full decision:
  `docs/research/CAMPAIGN_54_CRASH_SHORT_PLANNING_CHARTER.md` §7. Closure does not authorize any
  Core v1 change, capital allocation, or a Core v2 runtime/paper account.
- **Defined-risk equity volatility risk premium (SPY/QQQ credit spreads / iron condors) —
  CLOSED 2026-08-25, Gate 2 (tradeability) failure, never chartered as a numbered campaign.**
  Named deficiency (single return source) and horizon feasibility (Gate 0/1) passed. Real
  evidence gathered before the stop: VIX vs. trailing realized SPY volatility, 2014-2026 (3,178
  trading days) — mean VRP +3.53 points, positive 85.1% of days, consistent with published
  estimates; a real-fund proxy (JEPI, options-overlay income ETF) showed Sharpe statistically
  identical to SPY buy-and-hold (1.073 vs 1.072) with max drawdown 44% shallower, concentrated
  specifically in the 2022 bear year (JEPI -3.06% vs SPY -18.65%), not diffused across calm
  years. Stopped at Gate 2: the operator's brokerage does not support multi-leg options spread
  orders — confirmed directly by the operator, not assumed — a capability essentially exclusive
  to Interactive-Brokers-tier accounts among US retail brokers, not a gap specific to this
  account. Per the charter-campaign skill's own rule, this is reported as a clean gate failure,
  not routed around with a workaround (e.g. undefined-risk single-leg premium selling, which
  most brokers do allow at a lower approval tier, but which reopens the exact tail-risk problem
  -- one -47.73-point single-day VRP reading in the same dataset -- that defined-risk structuring
  existed to solve). Two legitimate paths exist if revisited: open a spread-capable brokerage
  account (a real capital/operational commitment, not a research decision, and not made here),
  or accept undefined-risk premium selling with its tail-risk cost fully priced in. Neither
  decided; campaign closed at the gate, not chartered further.

Not authorized:

- Campaign #53 real predictor/outcome computation against actual candidates for an actual
  discovery/confirmation decision, or any economic/runtime action beyond what this transition
  authorizes above (data acquisition and the power simulation's methodology calibration);

- opening Campaign #52 validation targets or outcomes;
- reframing, retesting, or changing Campaign #52 after observing its result;
- implementing or executing a new campaign before its charter and frozen specification are approved;
- changing Core behavior, sources, weights, thresholds, costs, folds, orders, execution, NAV, exposure, runtime, dashboard, or training;
- paper trading, live execution, or economic action.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
