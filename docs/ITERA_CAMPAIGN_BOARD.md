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
- **Campaign #55 (COT speculative positioning as a contrarian timing signal, S&P 500/Nasdaq-100
  → SPY/QQQ) — PLANNING CHARTER, 2026-08-26, gates 0-2 pass, gate 4 underpowered as narrowly
  tested.** Named deficiency: "single return source" (a sentiment/positioning signal, not a
  retune of Core v1's trend rule); would be a Core v2 sleeve/overlay on existing SPY/QQQ
  exposure, never a Core v1 change. Gate 0/1 pass cleanly (multi-week horizon vs. sub-1-bar
  measured runtime cadence, ~140x margin). Gate 2 passes cleanly — the strongest tradeability
  result of any idea this session: SPY/QQQ are already-held Core v1 instruments, same brokerage,
  no new venue/account/approval needed, and the COT-futures-data-vs-ETF-execution mismatch needs
  no cross-venue basis check since both track the same underlying index. Gate 3 materiality: a
  rough IC-based heuristic gives ≈$607/yr at full $100k notional, ≈$202/yr at a more realistic
  ~1/3 allocation — the same modest range every edge this session has landed in. Gate 4 (power),
  the substantive finding: today's informal 2-market × 3-horizon × 2-statistic look was
  Bonferroni-corrected (only S&P 500 26w survives, p≈0.0004 at raw n) and then autocorrelation-
  adjusted (effective n ≈ raw n / holding-period-in-weeks, the same category of correction
  Campaign #53's own `inject_ic` bug exists to enforce) — the sole survivor collapses to p≈0.51,
  indistinguishable from noise. No combination tested today would survive a properly-powered
  confirmatory test. Not closed as a null (the earlier structural robustness checks — no
  single-point domination, Spearman not collapsing relative to Pearson — rule out the specific
  artifact mechanisms that killed COT gold and crypto momentum); closed as **underpowered given
  the current design**, with Amendment 1's own prescribed remedy identified: a cross-sectional
  design across the broad universe of liquid CFTC-tracked futures markets, not more calendar
  time on the same two weekly-cadence time series. No specification frozen (pacing rule; also
  moot given gate 4). Full record: `docs/research/CAMPAIGN_55_COT_INDEX_POSITIONING_CONTRARIAN_CHARTER.md`.
  **Correction, 2026-08-27: the prescribed cross-sectional remedy was built and run — CLOSED as a
  clean null, not underpowered.** `scripts/probe_cot_cross_sectional_universe.py` enumerated the
  live CFTC universe directly (`scripts/list_cot_market_names.py`, no names assumed from memory)
  and resolved markets by exact name after catching a real mismatch bug (a substring match had
  paired British Pound positioning with a EUR/GBP cross-rate price series). Two genuine, permanent
  gaps surfaced in the process: British Pound and Copper have no live COT name (both, along with
  the entire Treasury complex, were retired by a CFTC mass-renaming on 2022-02-01 with no
  successor under any name) — the Treasury gap means this design still cannot address the "no
  rates or fixed income" deficiency. 35 of 37 candidate markets cleared both gates. A
  pre-registered design (`scripts/run_cot_cross_sectional_discovery.py`, committed before any
  result: primary horizon 12w, primary statistic Spearman, contrarian direction negative, BH-FDR
  q=0.10, 40% holdout held out by fixed seed `20260826`, staged discovery/confirmation execution
  verified to never let discovery touch holdout markets) tested 21 discovery-stage markets. Real
  result: mean rho +0.0116 (wrong sign for the contrarian hypothesis), negative in only 8/21
  markets, t-test p=0.582, Wilcoxon p=0.517 — no signal at the primary horizon, and the 4w/26w
  secondary horizons were no better (p=0.691, p=0.443). Effective breadth came back at only 5.1
  independent markets out of 21 (mean pairwise forward-return correlation +0.155) — a real,
  measured number, not assumed, and itself an explanation for why the original 2-market version
  could never have carried power. 10/21 markets nominally survived FDR at q=0.10, but 6 of the 10
  had the WRONG sign (Euro FX, Cotton, Sugar, Brazilian Real, Coffee, Wheat HRW — a
  softs/grains-heavy cluster consistent with momentum/CTA-trend dominance rather than contrarian
  positioning extremes), leaving only 4 correct-sign survivors (VIX, Canadian Dollar, Natural Gas,
  S&P 500); reading "10 survive FDR" without the sign split would have been misleading. This is a
  clean null on its own pre-registered terms, not an underpowered one: the design achieved real,
  measured cross-sectional breadth (5.1 effective markets, a genuine improvement over the original
  2) and still failed. The 40%, 14-market holdout stays untouched — there is no confirmatory value
  in spending a one-shot strict-standard test on a discovery result that already failed. COT
  speculative-positioning-as-contrarian-timing is closed as a line of research; reopening it would
  need a different signal construction, not another pass at this one.

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
  **Correction, 2026-08-26: Gate 2 status has changed and real Gate 3/4 evidence now exists.**
  The operator is opening an Interactive Brokers account (supports multi-leg spreads) — Gate 2
  is PENDING an external, clock-bound approval, not failed, so build-bound research resumed per
  the destination charter's own build-bound/clock-bound distinction. A real options-payoff
  backtest (`scripts/analyze_vrp_defined_risk_backtest.py`) priced a SPY iron condor (16-delta
  short strikes, 2% wings, 35 DTE, held to expiration) via Black-Scholes using VIX as the
  implied-vol input, against 12.7 years of real SPY closes (2013-2026, 127 non-overlapping
  cycles — genuinely independent, unlike every other time-series test this session, so a plain
  one-sample t-test is legitimate here). Fair-value result: 88.2% win rate, mean $103.52/cycle,
  t=6.07, p<0.000001. Losing cycles spread across nearly every year (2015-2025), not clustered
  in one event; excluding the single worst cycle barely moves the mean ($103.52→$111.16);
  VIX-at-entry correlates positively with cycle P&L (+0.18, the theoretically expected
  direction); the backtest independently recovers the real Feb 2018 "Volmageddon" VIX spike
  exactly where and how it should appear (entered at an extremely complacent VIX=9.2). A cost
  sensitivity sweep (three explicitly labeled, honestly-uncertain spread assumptions — no
  verified historical SPY-options bid-ask dataset exists here — plus a commission assumption
  flagged as recalled with moderate, not certain, confidence) found the result survives tight
  ($88.92/cycle net, p<0.00001) and moderate ($68.92/cycle net, p=0.00009) cost assumptions
  comfortably, and only fails significance under a genuinely pessimistic wide/crisis-period
  assumption ($20.92/cycle net, p=0.22) — informative, not a failure, since SPY options are
  among the most liquid options products that exist and "wide" is a stress scenario, not the
  everyday case. Caught and fixed one real bug along the way: an early version multiplied
  commission by the per-contract share multiplier on top of spread cost, silently inflating
  $0.65/contract into $65 — not caught by the first unit test (its own expected value mirrored
  the same wrong formula), only by reading the actual output and independently re-deriving the
  expected cost by hand. This is the strongest single-candidate result of the entire session:
  a well-documented effect (the volatility risk premium; CBOE's own PUT/BXM benchmark indices
  exist because of it), not a lone anomaly, showing up correctly in an independently-built,
  first-principles backtest, surviving realistic cost assumptions where every other idea today
  either had the wrong sign, collapsed under an outlier-robustness check, or was underpowered.
  Still open before this goes near Gate 5: volatility skew is unmodeled (flat-vol pricing likely
  misprices both legs, direction of net effect unknown without real skew data — the single
  biggest remaining unknown); only one structure/parameter choice has been tested, no robustness
  sweep across nearby DTE/delta/wing-width choices yet; and Gate 2 itself is still pending the
  actual IBKR account. Not frozen, not re-chartered as a numbered campaign yet — recorded here
  as real, load-bearing progress on an idea previously closed at the gate.
  **Correction, 2026-08-26 (second): skew's direction resolved — it REDUCES the edge, not an
  unknown-direction risk.** Added an illustrative skew-steepness sweep (linear-in-log-moneyness,
  no verified historical per-strike SPY skew dataset exists, same discipline as the cost sweep)
  to `analyze_vrp_defined_risk_backtest.py`, re-running the full 127-cycle backtest under each
  assumption. Moderate skew: mean $103.52→$94.33/cycle (still p<0.000001). Steep skew: mean
  →$73.82/cycle (still p=0.000078 — highly significant even in the worst tested skew case).
  Mechanism: skew pushes the delta-targeted put strike further OTM to hold the same 16-delta
  target under locally elevated vol, costing more credit than the corresponding call-side
  reduction gives back — verified directly (the found strike's local, skew-adjusted delta
  matches the target exactly, and moves further OTM than the flat-vol strike, as expected).
  Combining (approximately — skew and cost were swept independently, not jointly simulated)
  the more representative assumptions (moderate skew + tight/moderate costs, since SPY is
  about as liquid as options get and steep skew is more a crisis-specific regime than a
  persistent baseline) leaves the edge comfortably positive, ~$60-80/cycle net. The genuinely
  pessimistic tail combination (steep skew + wide costs) flips it negative
  (~$73.82-$82.60≈-$8.78/cycle) — a normal, healthy shape for a real edge (robust to realistic
  conditions, not bulletproof against the worst case on every axis simultaneously), not a red
  flag. Remaining before Gate 5: a joint skew+cost simulation rather than an additive
  approximation, a robustness sweep across nearby DTE/delta/wing-width structure choices, and
  the IBKR account itself.
  **Correction, 2026-08-26 (third): both remaining research gaps closed. The premium is now
  UNDERSTOOD, and the binding constraint is execution quality, not signal.**
  (a) *Tension resolved.* The structure sweep's dose-response control showed a constant-vol
  break-even near +3 to +4 vol points, awkwardly close to the +3.53pt mean real-world VRP, which
  left the strongly profitable backtest unexplained. `scripts/analyze_vrp_premium_distribution.py`
  (no options pricing involved, so independent of every backtest modeling assumption; forward
  realized vol, not trailing) resolved it: over the same 127 non-overlapping windows, mean
  premium +3.15pt but MEDIAN +4.59pt (gap +1.44), premium skew -4.395, positive in 80.3% of
  windows, p10 only -3.05. The typical window pays well above break-even; the mean is dragged
  down by rare catastrophes (worst: 2020-02-12, VIX 13.7 vs 76.0 realized, -62.2pt). A
  held-to-expiry seller collects the typical case, not the average case. The hypothesis was
  pre-registered with an explicit falsification and all three verdict branches were proven
  reachable on synthetic data before the real run. This also confirms the risk is real and
  concentrated in the tail — and that the defined-risk cap works as intended: that COVID cycle
  lost $455 against ~$553 max risk, where an undefined-risk seller would have been destroyed.
  (b) *Structure robustness.* `scripts/run_vrp_structure_robustness_sweep.py`, 60 structures
  (5 DTE x 4 delta x 3 wing) under joint skew+cost application, comparability handled via
  annualized return on max risk. Under representative assumptions (moderate skew, moderate
  cost): 52/60 cells (87%) positive, median return-on-risk +64.9%/yr, and the originally-chosen
  35d/0.16delta/2% structure sits at the 77th percentile — no cherry-pick warning fired, so the
  headline reflects the structure family rather than a lucky point. Honest qualifier: 77th is
  upper-middle and the original's +112.6%/yr is ~1.7x the family median, so the headline is
  somewhat flattering even though it is not an outlier. Face-validity patterns emerged that were
  not designed in: 1% wings consistently poor (the fixed per-cycle cost is constant regardless
  of wing width, so it consumes a small credit), and shorter DTE beats 60-day (faster theta
  capture per unit time).
  (c) *The binding constraint, and the most important finding of the day.* Under pessimistic
  assumptions (steep skew + wide/crisis cost applied to every cycle): **0 of 60 cells are
  significant and positive** — not the original cell failing, the entire family. That scenario
  is a stress test rather than a base case (it charges crisis-level spreads across all 12.7
  years), but the implication is real and actionable: **this edge lives or dies on execution
  quality, not on signal.** Obtaining fills near mid on 4-leg spreads is the make-or-break
  variable, which is an operational question about the pending IBKR account, not a research one.
  Caveat recorded: the "25/60 significant at p<0.05" figure under representative assumptions is
  NOT 25 independent confirmations — the cells share underlying data and overlapping structures,
  so no clean multiplicity story applies.
  Status unchanged: not frozen, not re-chartered as a numbered campaign, no capital or runtime
  authorized. Remaining before any Gate 5 work: real IBKR commission/fill verification against
  their actual rate sheet (the $0.65/contract/leg assumption is still recalled, not verified),
  and the account itself.
  **Correction, 2026-08-26 (fifth): the "essentially exclusive to Interactive-Brokers-tier
  accounts" claim recorded above (2026-08-25) is almost certainly WRONG and should not be relied
  on.** It originated in an operator remark ("almost no one has that except for interactive
  brokers") that was written into this record as established fact without being challenged —
  exactly the failure mode the append-only convention exists to catch. Multi-leg defined-risk
  spreads are a mainstream retail options capability, not an IBKR-specific one: tastytrade (built
  by the thinkorswim founders specifically around premium-selling strategies of this kind),
  Schwab/thinkorswim, E*TRADE, Fidelity and TradeStation are all believed to support them. The
  actual gate is the options APPROVAL LEVEL (spreads sit above covered calls / long options in
  most brokers' tiering) and that tier is applied for at any broker. What the operator hit on
  Coinbase was that Coinbase does not offer that tier at all — a Coinbase fact, not an industry
  fact. Stated from general knowledge, NOT verified this session; treat as strongly believed and
  worth a short check, not settled. Practical consequence: the campaign is not IBKR-dependent,
  and since fill quality is the binding constraint (see correction (c) above), broker choice
  bears directly on the make-or-break variable — order routing and the ability to work a 4-leg
  order near mid vary by platform, so the broker decision should be made on execution quality
  rather than on an assumed monopoly.
  **Correction, 2026-08-26 (sixth): the lower-approval-tier fallback was tested and FAILS. There
  is no viable substitute for the defined-risk structure, which makes the options-approval
  question load-bearing rather than a formality.** Motivated by the operator's concern that
  spread-level approval might not be granted, `scripts/analyze_vrp_cash_secured_put.py` tested
  cash-secured SPY put selling — the LOWEST options approval tier, and positioned on the put
  side where the VRP is richest. Real result over the same 127 non-overlapping cycles, same data,
  same period, net of the same moderate execution cost (and charged only 1 leg rather than 4):
  **not one delta in the 0.10/0.16/0.20/0.30 grid reaches significance** (p = 0.92, 0.61, 0.40,
  0.12 respectively), against the condor's p<0.000001 on identical cycles. Like-for-like at
  0.16 delta: the CSP earns 48% of the condor's mean per cycle, with **8.6x the worst-case loss**
  (-$7,642 vs -$894) and **58x the capital committed** ($32,047 collateral vs $553 at risk). At
  realistic full size on a $100k book a single bad cycle costs **-22.9% with no floor**, versus
  the condor's hard-capped -5.0%. Median far exceeds mean at every delta (e.g. $115 vs $33 at
  0.16), i.e. the same right-skew found in the premium itself — but here the rare disasters are
  large enough to swamp the mean entirely rather than merely drag it.
  This is not a result discarded because it was unwelcome: the falsifiable skew prediction
  registered in the script BEFORE running held exactly (credit $1.636 -> $1.790 -> $1.976 across
  flat/moderate/steep skew, net P&L rising with it, and both the fixed-strike and fixed-delta
  framings checked in advance to disentangle a real confound). The machinery is correct; the
  structure is simply inferior.
  It also converts a prudential judgment into a measurement. The 2026-08-25 entry rejected
  undefined-risk premium selling because it "reopens the exact tail-risk problem that
  defined-risk structuring existed to solve." That was reasoning at the time; it is now
  quantified. The long wing is not a refinement of this candidate — it is what makes it work.
  Strategic consequence: spread-level approval is now a genuine gate on this entire line of
  work, with no lower-tier path around it. If approval is unavailable, VRP is blocked rather
  than degraded, and that should inform how the broker/approval question is prioritized.
  **Correction, 2026-08-26 (fourth): Gate 3 materiality re-sized on the measured representative
  case — this is the first candidate that is not marginal.** Using the real moderate-skew,
  moderate-cost figures ($59.73 net/cycle/contract, 10.4 cycles/yr, $553 hard-bounded max loss
  per contract per cycle): at a 2% risk budget ≈ $1,869/yr (1.9% of book); at 5% ≈ $5,606/yr
  (5.6%); at 10% ≈ $11,212/yr (11.2%). Against CLAUDE.md's own standing note that every edge
  examined here lands at ~$400-1,500/yr, and against Campaign #55's $202-607/yr, this is an
  order of magnitude more material — which is what justifies paper infrastructure rather than
  filing it as merely statistically interesting.
  Two caveats recorded with it. (i) The bound is per CYCLE, not per year: 15 of 127 cycles lost,
  so a bad year can stack several losers; the defined-risk cap bounds each cycle independently,
  not the annual outcome. (ii) **Tail correlation with existing Core v1 sleeves, raised here for
  the first time:** short-vol and long-equity lose together. The 2020-02-12 cycle lost precisely
  while equities collapsed — the same moment Core v1's SPY/QQQ trend sleeves would have been
  hurting. So while this genuinely addresses the named "single return source" deficiency
  (premium harvesting, not trend), it does NOT supply crash diversification and arguably
  concentrates it. Not disqualifying (Campaign #54's crash-short sleeve partly covers that
  role), but it belongs in any Core v2 composition/weighting decision from the start rather
  than being discovered afterwards.
- **CFTC COT gold speculative-positioning contrarian signal (GLD) — CLOSED 2026-08-25, clean
  discovery-stage null, never chartered as a numbered campaign.** Candidate: Non-Commercial net
  position as a percentage of open interest, CFTC Legacy Futures-Only report for "GOLD -
  COMMODITY EXCHANGE INC.", ranked as a causal percentile against forward GLD returns at
  4/12/26-week horizons (report-release lag of 3 days applied throughout to avoid lookahead;
  full data acquisition via `scripts/fetch_cot_legacy_futures_history.py`, analysis via
  `scripts/analyze_cot_gold_positioning.py`). First real run used an EXPANDING (since-1986)
  percentile and looked promising (corr +0.15/+0.29/+0.28 across the three horizons) — but the
  quintile split it produced was 46% top / 12.6% bottom, not the ~20% a real quintile split
  implies, exposing a real methodological bug: ranking recent readings against 40 years of a
  structurally growing market mechanically inflates recent percentiles regardless of whether
  positioning is actually extreme for the market's current scale. Fixed by bounding the rank to
  a 156-week trailing rolling window (still strictly causal) with a runtime canary that would
  warn if quintile shares stayed skewed. Re-run: quintile shares recovered to 26.6%/24.5%/48.8%
  (canary did not fire), and the correlations collapsed to +0.016/+0.045/+0.067 — an order of
  magnitude smaller, with quintile mean forward returns (-0.42%, -0.98%, -0.82%) bunched within
  a fraction of a standard deviation of the full-sample mean (-0.76%, std ~7.5% at 12 weeks). A
  coincidental-looking repeated median (-5.93%) across both extreme quintiles and across the two
  runs was checked directly (1125/1866 distinct forward-return values — normal for heavily
  overlapping weekly windows) and traced to the sample's own right-skew (median -4.78% vs. mean
  -0.76%), not a bug. No formal significance test was needed to reach this verdict: the spread
  between quintiles is too small, relative to the return distribution's own noise, for any test
  to plausibly rescue it. The promising first read was entirely the expanding-percentile
  artifact; the corrected result is a clean null. Not pursued further. The percentile-computation
  fix itself (rolling-window bias correction, quintile-balance canary) is retained in the script
  as a real, reusable methodological lesson independent of this specific idea's outcome.
- **Campaign #56 (rates/duration trend sleeve, TLT/IEF via `equity_sma175.py`'s existing,
  unmodified SMA175 mechanism) — PLANNING CHARTER, 2026-08-30, gates 0-3 pass.** Named
  deficiency: "no rates or fixed income exposure," the fourth and last of Core v1's named
  deficiencies, confirmed still fully unaddressed (`research/strategies/` has no rates
  instrument). Gate 1 (horizon) passes trivially — daily-bar regime signal against ~0.5-0.6
  effective bars measured cadence. Gate 2 (tradeability) is close to the cleanest this fund has
  seen: TLT is a plain, unlevered, already-liquid ETF on the same brokerage already executing
  SPY/QQQ/GLD, no new venue, no derivatives/options approval tier — only unconfirmed detail is a
  one-line check that TLT specifically is enabled on the live account. Gate 3 materiality: ~$975/yr
  at a Core-v1-sleeve-sized allocation, sourced from published time-series-momentum Sharpe
  estimates (~0.4-0.6 for a single uncorrelated instrument) — squarely inside this fund's
  repeated $400-1,500/yr range, stated plainly as not expected to move returns materially on its
  own. **Gate 4 (power) is scoped, not run, and flags its own risk before any data exists:** this
  is structurally a single-instrument time-series design with a small number of genuinely
  independent multi-year rate regimes in reachable history (TLT itself only launched 2002) — the
  same shape of power limitation Campaign #54 hit with `crash_short_v6`. Planned mitigation:
  broaden to the Treasury maturity curve (SHY/IEI/IEF/TLT) under the identical mechanism, honestly
  noted as not true cross-sectional independence (curve maturities move together) but a real
  improvement over n=1. Next executable step: acquire SHY/IEI/IEF/TLT daily history and run the
  actual regime census + Amendment 1 power simulation — not done this session. Full record:
  `docs/research/CAMPAIGN_56_RATES_DURATION_TREND_PLANNING_CHARTER.md`.
- **Cross-sectional crypto momentum (Coinbase spot) — CLOSED 2026-08-26, clean discovery-stage
  null, never chartered as a numbered campaign.** Named deficiency: "single-name crypto" (Core
  v1's only crypto exposure is BTC 4H / ETH 1H+4H, both single-name trend-following). Gate 0/1
  passed cleanly (multi-week horizon, wide feasibility margin against measured runtime cadence).
  Gate 2 cleared on real evidence: the operator confirmed broad, current Coinbase spot access
  (50+ names, screenshots), and `scripts/probe_coinbase_spot_momentum_universe.py` measured real
  per-coin history depth (0.8y-11.1y, 0 failures). Point-in-time eligible-universe design (a coin
  only ranks once it has real trailing history after its OWN listing date) via
  `scripts/analyze_crypto_cross_sectional_momentum.py`, formation/holding horizon grid (2w/4w/12w
  x 1w/4w/12w) declared before any result was seen.
  First real run showed a striking shape — small positive spread at short formation, sharply
  negative at 84d formation/84d holding (-5.69%) — that turned out to be almost entirely an
  artifact: individual per-rebalance spreads of -313%/-287%/-256% (only possible with a 3-name
  tercile) all clustered in Dec 2020-Mar 2021 (the crypto alt-season), exactly when the eligible
  universe was near the too-low `MIN_ELIGIBLE_UNIVERSE=10` threshold. Fixed by raising the
  threshold to 25 (7-name minimum tercile) — decided on its own structural merits before
  re-examining results, same discipline as the COT gold percentile-window fix. The reversal
  story vanished entirely on the corrected data; a smaller, mostly-positive pattern remained
  (+0.15% to +2.02% across cells, 50-60% win rates).
  A second, distinct artifact surfaced next: `--explain-date` on 2025-08-18 showed a real
  ZEC-USD move (+1377.59% over 84 days, an actual 2025 privacy-coin speculative rally) alone
  contributing ~98 of a 14-coin leg's +73.39-percentage-point mean — proof that MIN_ELIGIBLE_
  UNIVERSE (a breadth fix) doesn't protect against one coin dominating a MEAN once crypto's
  fat-tailed return distribution puts a 10-15x move on the table, essentially impossible in
  equities. Added median-based leg aggregation alongside mean, verified on synthetic data to be
  immune to exactly this failure mode while still recovering a real planted effect. Under
  median aggregation, **6 of 9 grid cells flipped negative and every win rate collapsed to
  46.4%-51.8%** — a coin flip. The three cells that stayed positive (all 84-day holding) were
  weak (+0.32% to +1.97%) at win rates indistinguishable from chance.
  Verdict: the mean-based "momentum" pattern was not a broad, repeatable cross-sectional
  tendency — it was a small number of extreme, idiosyncratic single-coin events landing in one
  leg or the other by chance, amplified by averaging. No execution-cost modeling was run: there
  is no point checking whether a pattern survives trading costs when it does not survive basic
  outlier-robustness. Not pursued further. The fixes made along the way (point-in-time
  eligibility design, the `MIN_ELIGIBLE_UNIVERSE` breadth correction, median-vs-mean leg
  aggregation, and the `--explain-date`/`--dump-*` diagnostics) are retained in the scripts as
  reusable methodology, independent of this idea's outcome — the same pattern as the COT gold
  percentile fix.

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

## Correction — 2026-09-02: Campaign #57 authorized

**Campaign #57 — Month-End Equity/Bond Rebalancing Pressure** is CHARTERED by explicit CEO authorization on 2026-09-02 following a `SCREEN_POSITIVE` sandbox result and a separately frozen month-end-specificity placebo that returned `MONTH_END_SPECIFICITY_SURVIVES`.

Governing charter: `docs/research/CAMPAIGN_57_MONTH_END_REBALANCE_PRESSURE_CHARTER.md`.

The sandbox SPY/AGG sample is discovery-contaminated and cannot serve as an untouched confirmation holdout. The charter freezes VTI/BND as the untouched historical confirmation pair and requires future-forward SPY/AGG evidence before any eventual capital decision.

**Authorized now:**

- untouched VTI/BND adjusted-data source/calendar feasibility without predictive outcome inspection;
- deterministic source manifests and replay/fail-closed checks;
- pre-outcome power simulation under the charter's frozen 3-session design, with at least 80% power required for the joint confirmation gate at the central injected effect;
- the central injected effect may not exceed 50% of the sandbox discovery ceiling absent separately documented external justification.

**Not authorized yet:**

- real VTI/BND signal/outcome computation or any confirmation verdict;
- alternate windows, proxy pairs, thresholds, or quarter-end subsets after seeing confirmation outcomes;
- economic strategy/backtest selection, sizing, portfolio weights, Core v2 composition, paper/live trading, orders, NAV/exposure changes, or any runtime change;
- any change to Core v1, which remains frozen.

A genuinely independent Red Team review remains mandatory before this candidate may be called `ALIVE`; Risk/PM and explicit CEO approval remain mandatory before any Core v2 composition/weight or capital decision.

## Correction — 2026-09-02: independent Red Team verdict on the long-history confirmation

The mandatory independent Red Team review (run as a genuinely separate subagent context, withheld the prior
non-independent in-thread review until after forming its own verdict) is complete. Verdict:
`CONDITIONAL_PASS_TO_VTI_BND_REPLICATION`. Full record: `docs/research/CAMPAIGN_57_INDEPENDENT_RED_TEAM_REVIEW_20260902.md`.

No defect was found fatal to the primary result — the lookahead-clean design, the correct null calibration, and the
pre-outcome power claim were each independently reproduced or tested by the reviewer, not merely re-read. Two
material corrections were made to the existing record without re-running or re-gating anything: (1) the VFINX/VBMFX
long-history sample overlaps the original SPY/AGG discovery sample by 57.8% of its months, and the genuinely new
pre-2003 portion is not independently significant on its own — this is a long-history consistency check with a weak
new-evidence tail, not an independent confirmation; (2) Amendment 2's stated reason for weakening the statistical
gate (claimed ~17% power for the original dual-primary test) is wrong at the actual long-history sample size — that
gate would have had ~75.5% power at n=476, not 16-18%. The 1990s era weakness is reclassified as largely
uninformative (the diagnostic that flagged it had only ~51.5% chance of passing even under a perfectly real,
correctly-sized effect) rather than either "harmless" or "a fatal instability."

**Newly authorized:** none. VTI/BND remains sealed. The Red Team pass is conditional on closing artifact/provenance
gaps (no raw JSON/source data survived this session; network access to every reachable price source was blocked)
and pre-registering a quantitative VTI/BND expectation band (rho in [-0.32, -0.10], not a bare sign check) before
any VTI/BND return is read. Full conditions in the linked record.

**Still not authorized:** VTI/BND return/signal/outcome computation, any `ALIVE` classification, Risk/PM review
(gated on Red Team, which has now passed but with the above conditions unmet), Core v2 composition/weight decisions,
economic materiality analysis has not yet been performed for this campaign, and all standing Core v1/runtime/
portfolio/paper/live/capital prohibitions remain unchanged.

## Correction — 2026-09-03: Campaign #58 — Itera Residual Predictability Census (ML research program)

Following a CEO-initiated staff review of whether a formal ML research arm is justified, full staff
(CIO, Quant Research, independent Red Team, Risk/PM) evaluated the question against a repo-grounded
retrospective of Itera's actual prior ML work. **PLANNING CHARTER recorded, gates not yet run.**

Governing charter: `docs/research/CAMPAIGN_58_ITERA_RESIDUAL_PREDICTABILITY_CENSUS_CHARTER.md`.

Retrospective (full record in the charter): exactly two governed fitted-ML programs exist in this
repo's history — Jump Risk Engine v0 (GBM/Logistic, validated predictively, cross-asset transferred
untuned, RETIRED on runtime-latency grounds not modeling grounds) and Trend Persistence Engine v0
(Logistic/GBM, validated predictively, every portfolio mapping REJECTED). A third, Recovery Trust
Gate (Logistic/RF/GBM gating Core's own re-risk decisions), was real research infrastructure that
never entered governance — retroactively closed by this same review:
`docs/research/RECOVERY_TRUST_GATE_RETROACTIVE_CLOSURE.md`. Everything else living under
`research/ml/` is deterministic/OLS-based despite the directory name — no fitted models. Campaign
#48 (72-candidate OLS census) is the fund's only rigorous simple-baseline study and never got an ML
comparator; it found signal only in volatility/magnitude, none in direction.

Independent Red Team verdict: **CONDITIONAL PASS** on chartering the research direction, with eight
binding conditions (frozen candidate grid sized to autocorrelation-corrected power; frozen, not
searched, hyperparameters; strictly walk-forward residualization with a provable leakage canary;
regime control restricted to the causal `baseline_engine.py` path only; cross-sectional tracks must
measure real effective breadth before any power claim; `ML_COMPLEXITY_NOT_JUSTIFIED` as the
pre-registered default, not a fallback; Recovery Trust closed first — done; any surviving signal
re-enters the full Gate 0-4 sequence before trading relevance). Absent all eight, FAIL.

Staff recommendation: two tracks, not one — Phase 0 (primary) a cross-sectional feature-family
census on the COT futures universe (the only dataset with independently measured, non-trivial
effective breadth: 5.1/21 markets, Campaign #55); Phase 1 (secondary, smaller) a time-series
residual census on BTC/ETH/SPY/QQQ/GLD, given every single-instrument design this fund has run has
hit a low-effective-N ceiling. CIO recommends this as a single bounded research-infrastructure
campaign, explicitly not a standing ML department — no named Core v2 structural deficiency is a
modeling-technique gap. Risk/PM: plausible orthogonality only if scoped to non-price-history/
cross-sectional features; unlikely if scoped to price-history features on Core's own instruments
(both prior rigorous ML efforts reduced to trend/vol timing on Core's own exposure, not a new
return source).

**Authorized now:** this planning charter and the Recovery Trust retroactive closure (both
complete; documentation-only, no new data touched).

**Not authorized yet (superseded in part below):** the specification-freeze prerequisites
(autocorrelation-corrected power analysis, frozen candidate/hyperparameter grid) pending
explicit CEO authorization per the staff escalation rule (chartering a new research direction
is not a routine staff call); any predictor, feature, residual, or outcome computation; any
model training; any implementation code; any inspection of any sealed holdout for any purpose;
any strategy/signal/threshold/regime/order/execution/portfolio/NAV/exposure/dashboard/runtime
change; any Core v1 change under any circumstance; any Core v2 composition/weight/capital
decision.

## Correction — 2026-09-03: CEO authorizes Campaign #58 specification-freeze prerequisites

Explicit CEO authorization, intentionally narrow, recorded in full in `ops/decisions.md`.

**Newly authorized:** the autocorrelation-corrected power analysis; the Phase 0 cross-
sectional effective-breadth measurement; construction and commitment of the complete
candidate grid; exact fixed hyperparameters for every permitted model type; chronological
fold and target definitions; the strictly causal expanding/walk-forward residualization
specification; leakage-canary design and proof that the canary can fail; exact causal
regime-state source/function identification; the multiplicity/FDR family definition; and
Phase 0 (plus Phase 1, only if independently supportable by power) statistical-specification
drafting and freeze. All eight binding independent Red Team conditions are adopted as-is.
The default campaign outcome remains `ML_COMPLEXITY_NOT_JUSTIFIED`, restated by the CEO: ML
does not earn continuation merely by producing statistically nonzero predictions — it must
materially and reproducibly improve untouched chronological OOS information versus naive and
simple statistical baselines under the same data, folds, targets, and multiplicity budget.
Priority restated: Phase 0 (cross-sectional/non-price-information census) before Phase 1.

**Still not authorized:** fitting real ML models against real predictor/outcome data;
predictor/outcome computation for a Campaign #58 decision; consuming any untouched holdout;
broad hyperparameter search; neural networks; strategy optimization; Sharpe optimization;
economic trading-rule construction; portfolio mapping; Core v2 composition or weights; any
Core v1 change; runtime, threshold, order, execution, NAV, exposure, paper/live, or capital
changes.

Staff reports the proposed frozen design and power result back for the next governed
transition before any real Campaign #58 model fit is run.

## Correction — 2026-09-03: Campaign #58 specification-freeze prerequisites result — neither track freezes today

Full record: `docs/research/CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md`.

**Phase 0 (cross-sectional COT census): BLOCKED on data/network access, not a decision.** This
session's environment has no outbound network access to any market-data source (verified: a
proxy-level 403 on `cftc.gov`, `deribit.com`, and generic internet hosts alike — organization
policy, not transient), and no COT positioning history is committed to this repo. Red Team
condition 5's required effective-breadth measurement could not be run for Campaign #58's own
proposed universe; reusing Campaign #55's old 5.1/21 figure would not satisfy it (different
universe, different session, exactly the shortcut that condition exists to forbid). Same class
of blocker as Campaign #57's VTI/BND data-access gap, logged the same way — blocked, not routed
around.

**Phase 1 (time-series residual census): real, computed result — FAIL at the power gate.** A
power analysis was run for real against the one multi-year dataset available in this session
(Campaign #48's own committed, replay-verified 403-anchor BTC price-state inventory), reusing
Campaign #53's governed block-bootstrap `inject_ic` methodology verbatim
(`scripts/run_campaign58_phase1_power_analysis.py`). Result: **average power at the central IC
(0.065) = 13.0%, against the 50% floor — FAIL** — on the base 7-candidate family alone, before
Phase 1's actual proposed grid adds further multiplicity (which would only push power lower, not
higher). BTC-only; no real ETH/SPY/QQQ/GLD data was available to test the full proposed scope.
Per the CEO's own explicit conditional ("Phase 1... only if independently supportable by
power"), **Phase 1 does not qualify for specification freeze at this time.** This result is used
as computed, not adjusted after seeing it fail, per Red Team condition 6.

**Completed regardless of either track's data situation:** the leakage canary (Red Team
condition 3) was built and proven capable of failing on synthetic data — clean expanding-window
residualization showed a first-half leak-correlation of 0.0064 (no false positive), a
deliberately leaky full-sample residualization showed 0.6923 (leak clearly detected). The
regime-state source is identified and restricted to `research/regimes/baseline_engine.py`'s
causal `classify_bar`/`classify_dataframe` path only, explicitly excluding the
`historical_regime_*` discovery tools (Red Team condition 4). Fixed hyperparameters per model
type (Red Team condition 2) and the fold/target/FDR-family methodology (not yet data-sized) are
recorded in the result document.

**Not authorized and not done:** any candidate-grid sizing or specification freeze for either
track (both are blocked — one on data, one on a real negative power result); any real
predictor/outcome computation; any model fit.

**Open fork for the CEO, not resolved by staff:** whether to resource a future session with real
multi-year ETH/SPY/QQQ/GLD data to re-test Phase 1's power across the full proposed instrument
set, or accept the BTC-only result as a clean FAIL and close the time-series track. Full
reasoning: `docs/research/CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md` §10.

## Correction — 2026-09-03 (same day): fork resolved — real multi-asset Phase 1 power result is PASS

The CEO resolved the fork above directly by running the (same-day generalized) power analysis
script locally against the real, full BTC/ETH/SPY/QQQ/GLD dataset. Full record:
`docs/research/CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md` §11.

**Result: average power at the central IC (0.065) = 58.3%, against the 50% floor — PASS.** 2,527
real pooled anchors across all 5 proposed instruments. Staff independently recomputed the
headline number from the printed intermediate values (matches to four decimals) and the pooled
anchor count (matches exactly) — real, internally consistent output. The underlying CSVs
themselves were not independently inspected by staff (no access to the operator's local data).

**Not uniform across the family:** 5 of 7 candidates individually clear 65-75% power;
`drawdown_from_high_trailing_168h` (31.7%) and `realized_volatility_trailing_168h` (19.7%, the
weakest) fall under the 50% floor individually — the latter explained by its much higher lag-1
autocorrelation (0.78 vs. -0.03 to 0.33 for the rest) widening its null distribution. The 58.3%
average is real but is not carried evenly by the family.

**What changes:** Phase 1's power gate, at the base 7-candidate level, is cleared on the real,
full proposed instrument scope — the BTC-only FAIL recorded above is superseded, not retracted
(both results are real; they tested different scopes). **What does not yet change:** this is the
base family's power, not the actual charter-scoped grid's (Red Team condition 1's hard-capped
≤150-candidate family, spanning multiple feature families, raw and residualized targets, and all
six permitted model types) — a larger family applies a stricter FDR threshold, and whether it
still clears 50% is real, undone work. Phase 1 is now **eligible to proceed** to grid
construction and grid-level power testing, per the CEO's own conditional — this is the next
authorized specification-freeze step, not a new CEO decision.

**Not authorized and not done, still:** any real predictor/outcome computation for a Campaign
#58 decision; any model fit; consuming any holdout; the actual frozen grid's own power test
(next step); Phase 0 remains blocked on data/network access, unchanged by this result.

## Correction — 2026-09-03 (same day): Phase 1 candidate grid frozen, independently Red-Teamed (CONDITIONAL_PASS, 10 conditions applied), model-fit authorization NOT yet granted

**Verification performed first (task order matters here):** the CEO-reported power run
(2,527 pooled anchors, central IC 0.065, average power 0.583, PASS, per-feature lag-1
autocorrelations ≈0.783 for `realized_volatility_trailing_168h` and ≈0.331 for
`drawdown_from_high_trailing_168h`) was cross-checked against the already-committed §11 record
above — every number matches exactly, confirming no drift or post-hoc alteration. Of the
charter's 8 binding Red Team conditions, only condition 1 (grid sized to a real power result)
remained open at this stage; conditions 2, 3, 4, 7 were already satisfied and condition 6 is a
standing rule carried into the frozen spec below, not a one-time checkpoint.

**Frozen specification produced:**
`docs/research/CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md`. 144-candidate grid (16
feature-variants — 8 base features × raw/residualized — × 3 target horizons × 3 outcome
families R/M/V, BH-FDR q=0.10 within each 48-candidate family), naive/simple baselines, four
fixed-hyperparameter constrained-ML models (ridge, elastic net, shallow RF, shallow GBM),
identical chronological folds/targets across every model type, causal expanding-window
residualization restricted to already-confirmed known signals only, the regime-state source
restricted to `research/regimes/baseline_engine.py`'s causal path, the leakage canary, a
four-part "does ML materially beat simple" decision rule (margin, FDR-on-the-lift, block-
permutation negative control, fold stability), and a binding pre-registered rule for how the
three already-identified underpowered features may (and may not) be interpreted if they return
a null.

**Independent Red Team review of the frozen specification:** `CONDITIONAL_PASS`, ten binding
conditions — `docs/research/CAMPAIGN_58_PHASE1_SPEC_INDEPENDENT_RED_TEAM_REVIEW.md`. Run as a
genuinely separate subagent context with no visibility into the specification's drafting. It
independently verified the hyperparameter freeze, leakage canary, regime-source restriction,
grid arithmetic, and §12c's sourcing directly against real code and real committed numbers — all
confirmed genuine. It also found and required correction of: a filename defect; that the
grid-level power check must cover all three outcome families, not Family R alone (the original
R-only justification conflated whether a true effect exists with how autocorrelated a series is,
which is what actually drives this methodology's power); that the §12b material-margin threshold
(originally a flat 0.02 absolute R²) was untested and roughly 5× the census's own central-IC-
implied effect size (R² ≈ IC² ≈ 0.0042) — recalibrated to that implied size; that the
permutation and lift-FDR null constructions needed to explicitly replicate the full best-of-
model-selection procedure at each resample, not fix the model choice from the real run; that the
§12c flagged-feature list needed to be explicitly closed (no future addition without a new
Red-Team-reviewed amendment) and its "90 clean candidates" claim made conditional on the
outstanding grid-level power check; and that the charter's own Risk/PM realized-correlation-to-
Core-NAV check had been dropped from the decision rules rather than deferred — reinstated. All
ten conditions are applied as dated corrections directly in the frozen specification.

**Companion tool updated to match:** `scripts/run_campaign58_grid_power_analysis.py` now
simulates all three outcome families (144 hypotheses total, not 48), and refuses to report a
clean PASS/FAIL headline if any hypothesis falls below a minimum trial count — closing the
under-sampling gap the review found in the tool's own first smoke test. Not yet run for real
(requires the operator's local multi-asset data, same as before).

**Authorization determination (task explicitly required this to stop here if a new CEO decision
is needed, rather than proceed):** the first real Campaign #58 predictor/outcome model-fit
experiment is **NOT authorized** under the standing 2026-09-03 CEO authorization, independent of
the Red Team verdict above. That authorization's own "not authorized yet" list, verified verbatim
against `ops/decisions.md`, explicitly excludes "fitting real ML models against real predictor/
outcome data" and "predictor/outcome computation for a Campaign #58 decision." A new, explicit
CEO decision is required before either occurs, regardless of specification quality.

**Staff does not recommend bringing that decision to the CEO yet.** Two prerequisite technical
gates remain, both cheap and neither requiring new CEO input: (1) the grid-level power
verification, now scoped to all three outcome families, has not been run for real — only a
tiny-file smoke test exists; (2) the leakage canary has been proven on synthetic data but not
re-proven against the real residualization implementation (which does not exist yet). Staff's
recommended next action is for the operator to run the updated
`scripts/run_campaign58_grid_power_analysis.py` locally against the real multi-asset data before
any authorization request is made — asking for execution authorization ahead of knowing whether
the grid itself clears power would be asking the CEO to decide on a foundation staff has not
yet finished checking.

## Correction — 2026-09-03 (same day): real grid-level power result is FAIL

The operator ran the updated `scripts/run_campaign58_grid_power_analysis.py` locally against the
real, full multi-asset dataset (2,522 pooled real anchors). Trial-adequacy guard cleared (minimum
39 trials/hypothesis, ≥ the required 20) — this is a trustworthy result, not an under-sampled
artifact. **Overall average power across all 144 hypotheses at the central IC: 45.8%, against
the 50% floor — FAIL.** Per outcome family: R 54.9%, M 41.8%, V 40.6%. Full record:
`docs/research/CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md` §15.

**This independently confirms the independent Red Team's own concern was correct in practice, not
just in principle.** Family R alone reports 54.9% — a Family-R-only calibration (the tool's
original, pre-correction scope) would have overstated the true blended grid power by 9.1 points
and returned a false PASS. Used as computed, per the standing discipline and the CEO's own
explicit instruction not to adjust assets, horizons, feature definitions, the proxy target, block
size, candidate family, or central IC after seeing a power result — none of those elements
changed in response to this result.

**One honest, explicitly post-hoc methodological question, raised but not acted on
unilaterally.** The grid-power script's residualized-variant columns are numerically identical to
their raw counterparts (a disclosed approximation, since real residualization isn't implemented
yet). Only after seeing this FAIL did staff notice this creates 72 exact-duplicate pairs within
the 144-hypothesis family — and Benjamini-Hochberg's threshold tightens with family size
regardless of whether added hypotheses are genuinely independent or exact copies, which a real
run (where residualized values would differ numerically from raw ones) would not reproduce. This
is flagged explicitly as a post-hoc observation, not used to discount, override, or trigger an
unauthorized re-run of this FAIL — the same discipline that prohibits adjusting the design after
seeing a result applies to adjusting the calibration tool for the same reason. Full reasoning:
`docs/research/CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md` §15.

**What this means:** the grid-level power gate (§13 item 1) is resolved, negatively. Per the
specification's own standing discipline, real predictor/outcome computation is not treated as
responsible while this result stands — moot, in any case, since the standing CEO authorization
still does not cover it. **Two forks put to the CEO, neither resolved by staff:** (1) accept this
as a real FAIL and close or deprioritize the Phase 1 time-series track, consistent with how
underpowered designs have been closed elsewhere in this fund's history; or (2) treat the
post-hoc duplication concern as worth an independent (Red-Team, not staff-unilateral) check on
whether the calibration tool itself has a fixable defect before treating 45.8% as final — and
only if that check concludes the tool understated real power, consider a corrected calibration
re-run, itself subject to a fresh independent review before being trusted. Staff does not
recommend between these.

## Correction — 2026-09-03 (same day): independent review resolves fork (2) — `ORIGINAL_POWER_FAIL_VALID`

Per the CEO's explicit instruction, a genuinely independent statistical implementation review
(separate subagent, not told which outcome — defect or valid — was preferred) tested the
duplication concern empirically rather than accepting or dismissing it on argument. Full record:
`docs/research/CAMPAIGN_58_GRID_POWER_CALIBRATION_IMPLEMENTATION_REVIEW.md`.

**Verdict: `ORIGINAL_POWER_FAIL_VALID`.** Using this repo's own real simulator primitives, the
reviewer built a synthetic experiment comparing exact-duplicate fillers (mirroring the real
calibration script) against independently-drawn, distribution-matched fillers, at the frozen
central IC and FDR. Result: **paired mean power difference = 0.0000 ± 0.0009 across 8 seeds** — no
measurable distortion from duplication. A positive control confirmed the harness is genuinely
sensitive to family size (an 8→16-hypothesis increase produced a real, consistent ~32% relative
power drop across all 8 seeds), ruling out "the test can't detect this" as an explanation for the
null finding. The reviewer also noted the concern was self-reportedly post-hoc — visible in the
code before the run, raised only after seeing the FAIL — and does not survive empirical test even
when given full-faith consideration.

**The 45.8% grid-level power result is recorded as binding, not provisional.** The duplication
concern is considered and independently rejected, not left open for further chasing. No rerun of
the grid power calibration occurred or is warranted — pursuing one now, absent a demonstrated
defect, would carry the hallmarks of post-hoc redesign rather than instrument repair, exactly the
pattern this campaign's discipline exists to prevent.

**Recommended governed disposition, put to the CEO for sign-off, not decided unilaterally by
staff:** close Campaign #58 Phase 1's time-series track as underpowered at its frozen central IC
and full 144-candidate scope — consistent with this fund's precedent for closing underpowered
designs (the original two-market COT design, closed at the power gate before its cross-sectional
remedy). This does not close Campaign #58 as a whole: Phase 0 (cross-sectional COT census)
remains a separate, still-open track, currently blocked on data/network access, not on a power
result.

**Still not authorized, unchanged:** any real Campaign #58 predictor/outcome computation; any
model fit; any Core v1/Core v2/runtime/portfolio/paper/live/capital action.

## 2026-09-04 — Separate ML Lab: Experiment 011 closed; Experiment 012 specified

**Scope:** the exploratory branch `agent/ml-lab-exploration-20260903`, under
`docs/research/ML_LAB_EXPLORATION_CHARTER.md`. This is not Campaign #58 and does not
reopen or supersede its binding power failure or governed restrictions above.

**Experiment 011: CLOSED — EXPLORATORY_TRANSFER_FAILURE.** The operator's actual
Windows run completed at code commit `e512ee7ef1ec2535f59f6dec38a3069fc6b9eaf3`.
All 144 source-parity checks passed (maximum absolute score delta
`5.440092820663267e-15`, tolerance `1e-10`). However, macro GBM minus price GBM was
negative on destination mean IC and target spread in all four memory/period cells.
No destination fitting or reserved 2025 holdout use occurred.

- result and closure: `docs/research/ML_LAB_EXPERIMENT_011_RESULTS.md`;
- exact report snapshot: `docs/research/evidence/ML_LAB_EXPERIMENT_011_REPORT.json`;
- frozen design retained: `docs/research/ML_LAB_EXPERIMENT_011_CROSS_UNIVERSE_TRANSFER.md`.

The U.S. results from Experiments 009–010 remain exploratory observations confined
to that original cross-section; portability of the frozen model is unsupported.
Do not rescue 011 by changing its destination universe, retraining there, changing
the feature block, or tuning the model. The closure is exploratory, not a formal
universal null or a trading conclusion.

**Experiment 012: SPECIFICATION_FROZEN — NOT_IMPLEMENTED / NOT_RUN.** The operator
authorized recording 011 and specifying a bounded simplification test before
further fitting, with the documentation update pushed to GitHub.

- specification: `docs/research/ML_LAB_EXPERIMENT_012_COMPACT_MACRO_INTERACTIONS.md`;
- frozen existing-input hashes: `docs/research/evidence/ML_LAB_EXPERIMENT_012_INPUT_MANIFEST.json`.

Exactly one new candidate is specified: `compact_macro_ridge`, the existing
StandardScaler + Ridge(alpha=10.0) with the 12 price features, four macro main
effects, and six interaction products already named in Experiment 009's results
(22 features). Same U.S. universe, target, folds, embargo, and two memory schemes;
trailing-3y remains primary. Compare against the four saved Experiment 009 models.
The specification fixes descriptive outcomes and stops subset/model search after
a negative primary result. This is a separate U.S. simplification question, not a
new international transfer attempt or independent confirmation.

**Completed in this transition:** documentation, evidence snapshot, and input
fingerprints only. No Experiment 012 implementation, model fit, or result exists.
**Next scoped work:** implement the frozen 012 specification and prove its full
synthetic replay/fail-closed checks before a separately requested real run; do not
treat specification completion as an executed experiment.

All ML Lab results remain discovery-contaminated and non-confirmatory. No Core,
runtime, threshold, order, execution, NAV, exposure, portfolio, paper/live, capital,
or reserved-holdout change is authorized by this transition.
