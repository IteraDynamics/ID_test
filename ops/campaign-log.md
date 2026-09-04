# Itera Dynamics — Campaign Log

_Append-only. Never rewrite past entries — if a conclusion changes, add a
new entry that references the old one._

## Campaign #[N] — [name]
- **Chartered:** [date] — by [seat], addressing deficiency [1-4 or "n/a"]
- **Status:** OPEN / CLOSED_POSITIVE / CLOSED_NEGATIVE / CLOSED_UNDERPOWERED / BLOCKED
- **Summary:** [what was tested]
- **Result:** [headline stat + backtest ceiling caveat]
- **Red Team verdict:** [pass/fail/conditional + key finding]
- **What killed it / what kept it alive:** [the specific check that decided it]
- **Risk/PM note (if applicable):** [correlation/materiality finding]

## Campaign — Distance-method pairs trading (equity relative-value)
- **Chartered:** 2026-09-01 — off-charter. Built directly on the CEO's request for an
  immediately-testable, previously-untouched mechanism during a live session; never went
  through `charter-campaign`'s standard five-gate sequence (horizon feasibility, tradeability,
  materiality, power, document format) before code was written. Recording that plainly rather
  than backfilling a charter after the fact.
- **Status:** CLOSED_NEGATIVE
- **Summary:** Gatev/Goetzmann/Rouwenhorst distance-method pairs trading — normalized-price-path
  distance selects pairs on a 12-month formation window, trades divergence-from-relationship on
  the following 6-month window, walk-forward across 2003-2026. Built with an automatic
  negative control (identical simulation with randomly-selected pairs) and a bootstrap of the
  real strategy's own window returns baked into the same run, specifically so the verdict
  couldn't be eyeballed off a single flattering point estimate.
- **Result:** Real annualized Sharpe -0.98 (window-level) on the corrected, single-market
  universe (265 US equities/ETFs, 2003-08 through 2026-08, 45 walk-forward windows, 9,762
  trades, 27.2% win rate). Real underperformed **all 100 of 100** random-pair null repeats
  (permutation p=1.0000). Bootstrap: 90% CI [-2.65, -0.45], P(Sharpe<=0)=100%. Not an
  underpowered null — a well-powered, unambiguous negative.
- **Red Team verdict:** FAIL, mechanical (verdict computed by the script itself against
  pre-registered thresholds, not an editorial call). Consistent with the literature's own
  account of why distance-method pairs trading decayed after the 1990s-2000s: the method
  selects pairs with the tightest historical spread variance by construction, which plausibly
  produces trades too small relative to fixed transaction costs, with occasional larger losses
  when a tight historical relationship doesn't hold going forward. Read as informed reasoning,
  not confirmed causally.
- **What killed it / what kept it alive:** Two real infrastructure bugs were found and fixed
  along the way before the result could be trusted — worth recording separately from the
  strategy verdict since they'll recur if not fixed at the source: (1) mixed tz-aware/tz-naive
  and DST-spanning timestamp parsing, and — the dominant one — the
  loader silently mixing US equities with Japanese listings, index tickers, and futures
  contracts on incompatible trading calendars, which had collapsed the eligible universe to
  0-then-2 tickers for over a decade and produced a first-pass result that was an artifact, not
  a finding. Diagnosed via a per-window eligibility diagnostic added specifically to make that
  class of failure visible rather than guessed at. On the corrected single-market universe (265
  tickers, 2003-2026), the result was a clean, well-powered negative: real Sharpe -0.98,
  underperforming **100 of 100** random-pair null repeats, bootstrap P(Sharpe<=0)=100%.
- **Risk/PM note (if applicable):** n/a — closed before reaching a risk/sizing/materiality
  review; the mechanism itself did not clear its own negative control.

## Campaign — Low-volatility factor (cross-sectional equity, vol-sorted long/short)
- **Chartered:** 2026-09-01 — off-charter, same session, CEO's second pick after the pairs
  closure ("if it's the best you got, I guess let's build it," with an explicit crowding
  reservation stated upfront, not discovered after the result).
- **Status:** CLOSED_NEGATIVE
- **Summary:** Ang/Hodrick/Xing/Zhang-style low-volatility anomaly (a close cousin of
  Frazzini/Pedersen's beta-neutral "Betting Against Beta") — rank the universe by trailing
  12-month realized volatility each formation window, long the lowest-vol quintile / short the
  highest-vol quintile, hold 3 months, walk forward 2003-2026. Reused the pairs campaign's
  already-validated loading infrastructure directly (import, not re-derivation), with the
  same automatic negative control (random long/short split of the same universe) and bootstrap
  baked into the same run. Window diagnostic included from the start this time rather than
  bolted on after a confusing result.
- **Result:** Real annualized Sharpe -0.30 across 82/90 valid windows (only the earliest 8
  windows, 2004-2005, skipped for a thin universe — the same organic early-history pattern as
  the pairs campaign, not a data artifact; confirmed clean on the first run, no debugging round
  needed). Real underperformed the random-split null's mean and 86% of its 100 repeats
  (permutation p=0.8614). Bootstrap: 90% CI [-0.62, +0.05], P(Sharpe<=0)=92.3%.
- **Red Team verdict:** FAIL, mechanical. Consistent with the CEO's own stated reservation
  before the build: this factor is not undiscovered — it's one of the most widely traded in
  finance (billion-dollar ETFs built on it) — and a clean negative here is exactly what
  substantial crowding since its academic documentation would look like, though the specific
  simplified construction used (realized-volatility sort, not full beta-neutral leverage
  adjustment; quarterly full-turnover rebalance) could independently account for some of the
  gap. Not disentangled here — read as informed reasoning, not a confirmed cause.
- **What killed it / what kept it alive:** The negative control and bootstrap, run automatically
  in the same pass — no separate debugging phase was needed this time because the reused
  infrastructure (ticker-pattern market filter, tz/DST-safe parsing) had already been proven
  clean on the same universe by the pairs campaign.
- **Risk/PM note (if applicable):** n/a — closed before reaching a risk/sizing/materiality
  review; the mechanism itself did not clear its own negative control.

## Exploration screen — Index-options dealer gamma pressure
- **Screened:** 2026-09-02 under `docs/ITERA_EXPLORATION_SANDBOX.md`; no campaign number.
- **Status:** SCREEN_NEGATIVE
- **Mechanism:** aggregate SPY option gamma/open-interest geometry was tested as a proxy for compelled dealer hedging pressure. The frozen directional story expected low signed GEX to produce more trend continuation than high signed GEX after a conservative one-trading-day source lag.
- **Result:** frozen signed-GEX continuation gate failed at all three horizons: 1d difference -0.000739, p=0.8982; 2d -0.001868, p=0.9621; 5d -0.004451, p=1.0000. The supplemental reversed call/put sign convention produced the opposite relationship and was nominally significant at 2d (p=0.0339) and 5d (p=0.0020), therefore contradicting rather than rescuing the primary dealer-sign story. The tested panel contains 3,024 usable state rows from 2013-12-02 through 2025-12-12; earlier option history was source-validation evidence only because the local SPY outcome file begins later.
- **Control / artifact findings:** raw total-gamma level separated future absolute movement at 1d/2d/5d (one-sided permutation p≈0.0020/0.0040/0.0279), but this does not earn promotion. Its causal expanding-tercile states were severely imbalanced (2,173 low vs 372 high), later-year high/low comparisons largely disappeared, raw total gamma grows with the secular size of the options market, and gamma itself is mechanically related to volatility and time-to-expiry. Treating that side result as alpha would be outcome-informed salvage and likely scale/volatility confounding. Gamma-concentration movement also failed its frozen expected direction at all horizons (p=1.0).
- **What killed it:** the pre-outcome directional gate failed cleanly, and the reversed sign convention performed better. Open interest does not identify dealer inventory direction, so the observed reverse-sign relationship cannot be interpreted as validating the same mechanism under a preferred convention.
- **Boundary:** closed as a sandbox negative. No Core v1/Core v2/runtime/portfolio/paper/live implication. Any future gamma-related screen must be a genuinely new pre-specified hypothesis rather than a retune of this result.

## Exploration screen — Month-end equity/bond rebalancing pressure
- **Screened:** 2026-09-02 under `docs/ITERA_EXPLORATION_SANDBOX.md`; no campaign number.
- **Status:** SCREEN_POSITIVE — PROMOTED TO CAMPAIGN #57 BY CEO AUTHORIZATION 2026-09-02.
- **Mechanism:** mandate-driven balanced portfolios, pensions, target-risk programs, and other allocators restore equity/bond policy weights after monthly relative moves. The frozen hypothesis expected SPY-minus-AGG pre-window relative performance to reverse during the final 3 shared trading sessions of the month.
- **Result:** on 275 valid months from 2003-10 through 2026-08, the frozen primary 3-session Spearman was -0.2486 with one-sided within-5-year-block permutation p=0.000999. The causal expanding-tercile low-signal minus high-signal SPY-minus-AGG outcome spread was +0.8478% with p=0.001998. Every eligible leave-one-year-out aggregate Spearman remained negative; decade-level Spearman remained negative in the 2000s (-0.318), 2010s (-0.267), and 2020s (-0.121). The 1-session and 5-session descriptive windows independently pointed in the same direction but were not needed to pass the gate. These figures are discovery-contaminated sandbox ceilings, not live expectations.
- **Red Team / placebo:** in-thread Red Team is explicitly non-independent in this environment. A pre-specified mechanism-specific placebo compared otherwise analogous 3-session windows ending 5, 10, and 15 sessions before month-end. Month-end rho (-0.2486) was more negative than all placebos (-0.0483, -0.0716, -0.0181) and the month-end low-minus-high spread (+0.8478%) exceeded all placebos (-0.1490%, +0.2197%, +0.4267%). Status: `MONTH_END_SPECIFICITY_SURVIVES`. This rejects generic 3-session reversal as the narrow explanation but does not prove pension rebalancing is uniquely causal.
- **What kept it alive:** it passed the pre-outcome sandbox gate and the separately frozen calendar-location placebo. The effect is multi-decade and not removed by deleting any one calendar year from the aggregate rank test.
- **Promotion boundary:** the sandbox sample is discovery-contaminated and cannot be reused as untouched confirmation. Campaign #57 now governs the next work. A genuine independent Red Team review is mandatory before `ALIVE`, and Risk/PM plus CEO approval remain mandatory before any Core v2 composition/weight or capital decision.

## Campaign #57 — Month-End Equity/Bond Rebalancing Pressure
- **Chartered:** 2026-09-02 — explicit CEO authorization following the sandbox promotion recommendation; addresses structural deficiency #2 (single return source) through a mandate/calendar-flow mechanism rather than trend.
- **Status:** OPEN — PLANNING / FEASIBILITY / PRE-OUTCOME POWER ONLY.
- **Summary:** governed confirmation of whether pre-window equity-versus-bond relative performance predicts opposite-signed relative performance during the final three trading sessions of the month. Sandbox SPY/AGG history is sealed as discovery-contaminated. The untouched historical confirmation pair is frozen as VTI/BND, with a future-forward SPY/AGG ledger required before any eventual capital decision.
- **Current authorization:** source/calendar feasibility for adjusted VTI/BND daily data, deterministic source manifests, and pre-outcome power simulation. No real VTI/BND signal/outcome computation is authorized yet.
- **Frozen confirmation gate:** 3-session window only; Spearman rho < 0 with one-sided block-permutation p<=0.05; causal expanding-tercile low-minus-high spread > 0 with p<=0.05; every eligible leave-one-year-out rho < 0; source/replay validation must pass. No alternate windows, proxy pairs, thresholds, or quarter-end subsets may rescue a failure.
- **Power gate:** at least 80% estimated power for the joint confirmatory gate at a central injected effect no larger than 50% of the sandbox discovery ceiling absent separate external justification. If underpowered, stop before inspecting VTI/BND outcomes.
- **Red Team verdict:** not yet eligible. The sandbox placebo was an in-thread adversarial check, not an independent Red Team review. Genuine independent review remains mandatory before `ALIVE`.
- **Risk/PM note:** deferred until after valid confirmation and independent Red Team. No Core v2 composition, sizing, or capital inference is authorized.

## Campaign #57 correction — VTI/BND 50/25/25 historical validation architecture underpowered
- **Recorded:** 2026-09-02 after metadata-only/calendar-only preflight; no VTI/BND close, return, signal, or outcome values were read.
- **Status:** HISTORICAL_ARCHITECTURE_UNDERPOWERED; hypothesis remains unresolved.
- **Source/calendar:** 232 valid common months from 2007-05 through 2026-08. Frozen chronological partitioning produced 116 development months (2007-05 to 2016-12), 58 OOS months (2017-01 to 2021-10), and 58 sealed final-holdout months (2021-11 to 2026-08).
- **Power result:** at the frozen central 50%-haircut effect, joint-gate power was only 16.2% for OOS and 18.0% for final holdout versus the required 80%. At 40% haircut, OOS/holdout power was 14.4%/9.0%; at 25% haircut, 8.0%/7.6%.
- **Interpretation:** this is a design failure, not an alpha failure. The VTI/BND history remains fully unspent as predictive evidence. The frozen charter prohibits enlarging, merging, or date-shifting these partitions after source acquisition to rescue power. A redesigned validation architecture requires a new pre-outcome authorization; until then no VTI/BND outcomes may be inspected.

## Campaign #57 — independent Red Team review of the long-history confirmation
- **Reviewed:** 2026-09-02, as a genuinely independent subagent context (separate from CIO/Quant), per the mandatory
  gate in `.claude/skills/itera-staff/agents/red-team.md`. Withheld the prior in-thread (non-independent) staff
  review until after forming its own verdict, so it could not anchor on the existing interpretation.
- **Verdict:** `CONDITIONAL_PASS_TO_VTI_BND_REPLICATION`. Not a rubber stamp and not a kill: the reviewer actively
  tried to break the result — independently reproducing the 85.2%/69.6%/37.0% power figures from the frozen seed and
  calendar alone, proving the primary test lookahead-clean with a corruption canary, and empirically verifying the
  block-permutation null is correctly sized (5.7% Type-I error against a nominal 5% under deliberately severe
  synthetic era heterogeneity) — and found no defect fatal to the primary result.
- **Material corrections recorded, nothing re-run or re-gated:** (1) the VFINX/VBMFX long-history sample overlaps
  the original SPY/AGG sandbox discovery sample by 57.8% of its months (275/476); VFINX tracks the same index as
  SPY and VBMFX the same universe as AGG, so this is closer to a long-history consistency check on largely the same
  market events than an independent confirmation — the genuinely new pre-2003 portion (n=201) does not reach
  significance on its own under any plausible assumption. (2) Amendment 2's stated reason for replacing the dual
  co-primary statistical gate with a single primary test — that the joint gate was infeasible with available
  history — is wrong at the long-history sample size: independently re-run, the dual gate has ~75.5% power at
  n=476, not the 16-18% that actually killed the earlier, differently-partitioned 50/25/25 architecture. (3) three
  of the five frozen robustness diagnostics (LOYO, top-10 trim, tercile-spread sign) had ~99-100% chance of passing
  regardless of whether the mechanism is real, and are not meaningful confirmatory evidence on their own; the
  era-consistency diagnostic that actually failed (the 1990s) had only ~51.5% power to pass even under a perfectly
  real, correctly-sized effect, so its failure is reclassified as largely uninformative rather than either
  "harmless" or "a fatal instability" — though the full era sequence (1980s strongest, 2020s second-weakest) does
  not match the campaign's own stated growth-in-rebalancing-AUM mechanism story and that mismatch is recorded
  plainly rather than rationalized away.
- **Newly authorized:** none. VTI/BND remains sealed. The pass is conditional on: closing artifact/provenance gaps
  (no raw JSON or source CSVs survived this session — `artifacts/*`/`data/*.csv` are gitignored and every reachable
  price-data source, Yahoo/Vanguard/SEC EDGAR, returned HTTP 403 through this environment's proxy when checked);
  pre-registering a quantitative VTI/BND expectation band (rho in [-0.32, -0.10], not a bare sign check, since
  VTI/BND's span sits entirely inside the long-history sample against near-identical assets and a sign-only check
  would be ~98% likely to pass regardless of real transportability) before any VTI/BND return is read; and adding
  unit tests to the Campaign #57 code matching the practice already established by Campaigns #50-53.
- **Not authorized by this review:** any `ALIVE` classification, Risk/PM review, Core v2 composition/weight
  decisions, economic materiality analysis (not yet performed for this campaign at all), or any Core v1/runtime/
  portfolio/paper/live/capital action.
- **Full record:** `docs/research/CAMPAIGN_57_INDEPENDENT_RED_TEAM_REVIEW_20260902.md`.

## Campaign #58 Phase 1 — Itera Residual Predictability Census (time-series track)
- **Chartered:** 2026-09-03 — under Campaign #58 planning charter / CEO authorization for specification-freeze prerequisites; addresses research-program design (ML residual predictability), not a Core v1 named deficiency by itself.
- **Status:** CLOSED_UNDERPOWERED (CEO 2026-09-04)
- **Summary:** Phase 1 time-series residual-predictability census on BTC/ETH/SPY/QQQ/GLD. Frozen 144-candidate grid (16 feature-variants × 3 horizons × 3 outcome families R/M/V) independently Red-Teamed (`CONDITIONAL_PASS`, 10 conditions applied). Grid-level power analysis at central IC 0.065 failed the 50% floor at **45.8%** overall average power (Family R 54.9%, M 41.8%, V 40.6%). Post-hoc duplication concern independently reviewed: verdict `ORIGINAL_POWER_FAIL_VALID`; 45.8% binding.
- **Result:** CLOSED at the power gate before any authorized real model fit. Default campaign outcome language `ML_COMPLEXITY_NOT_JUSTIFIED` for this track is consistent with underpowered closure — no claim that ML is justified or unjustified from fitted models, because fitting was never authorized.
- **Red Team / independent review:** Phase 1 spec `CONDITIONAL_PASS` (10 conditions applied); power-calibration duplication review `ORIGINAL_POWER_FAIL_VALID`.
- **What killed it / what kept it alive:** Binding grid-level power FAIL below the pre-registered 50% floor; independent review rejected the post-hoc calibration-duplication rescue path. Closed by CEO sign-off 2026-09-04.
- **Scope note:** Does **not** close Campaign #58 Phase 0 (cross-sectional COT census), which remains OPEN and blocked on data/network access. No Core v1/runtime/capital implication. ML Lab Experiment 012 remains a separate exploratory thread.
- **Full records:** `docs/research/CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md` §15; `docs/research/CAMPAIGN_58_GRID_POWER_CALIBRATION_IMPLEMENTATION_REVIEW.md`; `ops/decisions.md` (2026-09-04).

