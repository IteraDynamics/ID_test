# Itera Dynamics — CEO Decision Log

_Append-only. Every escalation and its resolution goes here, even quick
ones — this is what makes "brief me" informative over time._

## [date] — [one-line decision title]
- **Raised by:** [seat]
- **The ask:** [one-line choice presented to CEO]
- **CEO decision:** [what was said, verbatim if short]
- **Follow-up:** [any resulting action, and who owns it]

## 2026-09-01 — off-charter alpha-hunt directive; distance-method pairs trading closed
- **Raised by:** CEO, frustrated with the pace and materiality of governed research to date and
  demanding an immediately-testable, genuinely untouched strategy outside the normal
  `charter-campaign` gate sequence — "stop... find the alpha... give me a backtest -- if it
  passes we move to OOS/Monte Carlo," explicitly instructing staff not to reference any prior
  research while picking it.
- **The ask:** produce real, runnable, testable code now, not another gated discussion.
- **What staff did:** built distance-method (Gatev/Goetzmann/Rouwenhorst) pairs trading —
  selected specifically for being mechanistically distinct from everything on the board and
  immediately testable against data already on the CEO's machine, with an automatic negative
  control (random-pair null) and bootstrap baked into the same run rather than offered as a
  follow-up. Flagged plainly, only after the first run, that the pick optimized for novelty and
  testability over prior probability of live edge, and that this doubled as a calibration check
  on the harness itself. Two real infrastructure bugs surfaced and were fixed before the result
  could be trusted: mixed tz-aware/DST-spanning timestamp parsing, and — the dominant one — the
  loader silently mixing US equities with Japanese listings, index tickers, and futures
  contracts on incompatible trading calendars, which had collapsed the eligible universe to
  0-then-2 tickers for over a decade and produced a first-pass result that was an artifact, not
  a finding. Diagnosed via a per-window eligibility diagnostic added specifically to make that
  class of failure visible rather than guessed at. On the corrected single-market universe (265
  tickers, 2003-2026), the result was a clean, well-powered negative: real Sharpe -0.98,
  underperforming **100 of 100** random-pair null repeats, bootstrap P(Sharpe<=0)=100%.
- **CEO decision:** "close it. What's next? My outburst still stands."
- **Follow-up (done):** logged CLOSED_NEGATIVE in `campaign-log.md`, including the two
  infrastructure bugs separately from the strategy verdict since they're reusable findings.
  **Open:** next candidate not yet picked — held to a sharper selection bar going forward
  (novel and testable, *and* a stated structural reason to expect it hasn't already been
  arbitraged away, not novelty/testability alone).

## 2026-09-01 — low-volatility factor closed; two off-charter attempts, two clean negatives
- **Raised by:** CEO, picking staff's second candidate after the pairs closure, with an explicit
  reservation stated before any code was written: "the crowding caveat doesn't make me feel warm
  and fuzzy about it not being arbitraged out... but if it's the best you got, I guess let's
  build it."
- **The ask:** build and test it anyway, given no zero-new-data candidate with a cleaner
  "still-undiscovered" story was available.
- **What staff did:** built the low-volatility factor backtest reusing the pairs campaign's
  already-validated loading infrastructure directly (not re-derived), with the negative control
  and window diagnostic included from the start rather than bolted on after a confusing result.
  Ran clean on the first real-data attempt — no debugging round needed, unlike both prior
  scripts this session.
- **Result:** real Sharpe -0.30, underperforming the random-split null's mean and 86% of its
  repeats, bootstrap P(Sharpe<=0)=92.3%. Clean, well-powered negative, consistent with the CEO's
  own stated crowding concern going in.
- **CEO decision:** (pending this session's next turn as of this entry — see `status.md`.)
- **Follow-up:** logged CLOSED_NEGATIVE in `campaign-log.md`. Worth naming plainly rather than
  quietly cycling to a third attempt: this is now two real, well-motivated, correctly-tested
  candidates in one session, both clean negatives, sitting on top of an already-extensive prior
  campaign board where nearly everything that survived its own gates still landed at modest
  ($400-1,500/yr) materiality. That pattern is itself informative and worth surfacing to the CEO
  directly rather than treated as just another data point before immediately trying idea #3.

## 2026-08-30 — charter Campaign #56 (rates/duration trend sleeve)
- **Raised by:** CEO, directing staff to move from idea discussion to real scoping/backtesting
  on the rates/duration sleeve — the pick from the earlier three-idea review, chosen over an FX
  carry basket (lower materiality, unverified venue) and a broadened crypto basket (adds count,
  not genuine independence from existing BTC/ETH sleeves).
- **The ask:** run the idea through the actual `charter-campaign` gates rather than continue
  discussing it informally.
- **What staff did:** Gates 0-3 passed cleanly — named deficiency confirmed still fully open
  (grepped `research/strategies/`, no rates instrument exists); horizon feasibility trivial;
  tradeability close to the cleanest this fund has seen (plain ETF, same brokerage, no new
  approval tier — confirmed by reading `equity_sma175.py`, the exact existing mechanism this
  campaign reuses unmodified); materiality ~$975/yr, consistent with the fund's own standing
  range, stated plainly as not expected to be exciting standalone. **Gate 4 (power) was scoped
  honestly rather than skipped or faked:** flagged upfront, before any data was pulled, that this
  is a single-instrument time-series design with a small number of independent rate regimes in
  reachable history — the same structural limitation Campaign #54 hit with `crash_short_v6` —
  with a planned mitigation (broaden to the SHY/IEI/IEF/TLT maturity curve) named and honestly
  qualified as not true cross-sectional independence.
- **CEO decision:** implicit approval via direction to proceed with scoping.
- **Follow-up (in progress):** `docs/research/CAMPAIGN_56_RATES_DURATION_TREND_PLANNING_CHARTER.md`
  filed, planning charter only — nothing frozen, per Amendment 3's pacing rule (no spec frozen the
  same session it's drafted). **Next executable step, not done this session:** acquire real
  SHY/IEI/IEF/TLT daily history and run the actual regime census + Amendment 1 power simulation.
  Owner: Quant Researcher, on a later session.

## 2026-08-30 — Core v2 Tier 2 risk framework (per-pod leverage/sizing/correlation)
- **Raised by:** Risk/PM, following CEO direction to build Tier 2 with full staff collaboration
  after the pod-degradation-band rule (below) named it as a gap.
- **The ask:** adopt a standing framework governing how much risk/leverage/notional exposure each
  Core v2 pod may hold, independent of whether its edge is currently working (distinct from the
  degradation bands, which ask whether the edge is still real).
- **Process:** three full rounds, each run as genuinely independent parallel reviews (not the same
  context grading its own draft) across three seats — Ops/Compliance, CIO, Red Team:
  - **Round 1** found real, non-overlapping problems: `crash_short_v6`'s exposure figure ignored
    real CDE margin/roll/liquidation mechanics; the VRP sleeve's $553 figure was max theoretical
    loss, not confirmed buying-power reduction; the per-pod template only fit options/futures-style
    sizing, not a trend sleeve's weight-times-signal shape; correlation declarations assumed one
    fixed sign per pod, which breaks for a rates sleeve (2022: bonds and equities fell together);
    the aggregate-cap methodology assumed one universal stress scenario retrofitted to the two
    existing pods; and the correlation-limit rule had a numeric threshold with no enforcement
    mechanism and no defense against a one-way ratchet.
  - **Round 2** (the same three seats verifying their own round-1 findings against the revision)
    surfaced two convergent structural problems found independently from different angles, not
    restatements of each other: (a) Ops/Compliance and Red Team both found the reconciliation-
    cadence enforcement chain is slower than the single-tail-cycle risk the framework exists to
    bound; (b) CIO and Red Team both found pods could dodge the correlation-limit mechanism by
    naming non-overlapping worst-case regimes, with no defined process for when two regimes count
    as "the same" for aggregation. Also found: the natural-hedge fence had no defined confirmation
    bar; the correlation-breach penalty ("halve the most recently added pod") was gameable by
    sequencing; and `crash_short_v6`'s real margin was still unverified with no interim safeguard
    despite being live capital right now.
  - **Round 3** was a rewrite, not a wording pass: the document now states honestly what
    reconciliation-based monitoring can and cannot do (drift/pattern protection only — single-cycle
    protection can only come from a defined-risk structure or a pre-fixed conservative size);
    regime-matching uses an empirical protocol (historical overlap against SPY's existing 175-day
    SMA bear proxy) plus a mandatory common-proxy declaration every pod must report regardless of
    its own named worst case; the natural-hedge fence now requires 2 independent observations, not
    1; the correlation-breach penalty is proportional to each pod's contribution, not sequencing;
    and an interim 30% conservative margin assumption was adopted immediately for the already-live
    `crash_short_v6`, with a 14-day deadline for the real figure.
- **CEO decision:** "Reviewed. Approved."
- **Follow-up (done):** adopted as `docs/CORE_V2_RISK_FRAMEWORK.md`, status changed to ADOPTED.
  **Open, owned by Risk/PM:** confirm `crash_short_v6`'s real CDE margin schedule by **2026-09-13**
  (14-day deadline) — until then the 30% interim working assumption governs all Tier 2 accounting
  for that pod. **Still open CEO decisions, not resolved by this approval and not urgent today:**
  the VRP sleeve's actual risk-budget percentage (staff recommends 2%; moot until its brokerage
  account clears) and whether the quarterly correlation-recompute cadence should be tightened
  against operator time cost (quarterly is the working default).

## 2026-08-30 — pre-registered pod degradation bands (Tier 1 addition)
- **Raised by:** Risk/PM, following a CEO gut-check on why every pod is bound by the same
  governance rules and whether the existing rule set (One Rule + standing research amendments)
  was strong enough as written.
- **The ask:** adopt a standing rule requiring every Core v2 pod to pre-register a live
  expectation and degradation band before going live, closing a gap Core v1 already had covered
  (`CORE_V1_LIVE_EXPECTATION_AND_DEGRADATION_BAND.md`) but no successor pod did.
- **Process:** Risk/PM drafted the rule; Red Team ran two independent adversarial passes (not the
  same context that drafted it). Round 1 found five real defects (no forced consequence on a
  trigger; individually-compliant pods can mask aggregate correlated risk; unenforceable
  self-graded correlation-drift triggers; silent retroactivity defaulting to grandfathering the
  two pods that most needed it; a vacuous seniority clause plus no pacing floor plus no technical
  enforcement). Round 2 verified the revision: 3 of 5 genuinely fixed, 1 correctly scoped as
  unchanged (aggregate risk was never this rule's job — the fix there was to stop the document
  implying it was covered), 1 still broken (correlation-drift), plus 3 new loopholes introduced by
  the fixes themselves (unlimited override use; self-attested funding tie-in with no independent
  ledger; no consequence for a missed backfill deadline). A third round of targeted fixes reused
  existing fund infrastructure (git-commit-before-funding as the ledger, an override cap, treating
  a missed deadline as itself a breach, named-benchmark-at-drafting for correlation triggers)
  rather than inventing new discretionary mechanisms.
- **CEO decision:** "Approved. Proceed."
- **Follow-up (done):** committed as a dated append to `docs/ITERA_DESTINATION_CHARTER.md`
  ("Refinement to the One Rule — pre-registered pod degradation bands (2026-08-30)"). The
  aggregate cross-pod risk cap remains a separate, not-yet-chartered item — explicitly named as
  open in the adopted rule itself, not implied solved by it.
  **Backfill complete, same day:** `docs/research/CORE_V2_CRASH_SHORT_DEGRADATION_BAND.md` and
  `docs/research/CORE_V2_VRP_OPTIONS_DEGRADATION_BAND.md` filed 2026-08-30, both well inside the
  2026-09-29 deadline. Real, quantified triggers grounded in each pod's own campaign record (cost
  breakpoints straight from the VRP campaign's own cost-sensitivity sweep, tail-correlation and
  win-rate thresholds, an operational-integrity trigger for each mirroring Core v1's T4) rather
  than generic placeholders.
  **Correction, same day:** the line above calling the equity-options sleeve "near live" overstates
  its status — it is not live, not chartered as a numbered campaign, and remains blocked on Gate 2
  (brokerage approval); its filing above is prospective, not a backfill. Caught while drafting its
  degradation band; recorded here rather than silently fixed.

## 2026-08-28 — "Portfolio NAV" dashboard section: fix now vs. bundle into Phase 2
- **Raised by:** Chief of Staff (synthesizing Performance / CIO / Risk/PM / Red Team design review)
- **The ask:** do the four honesty fixes to the NAV chart now, or hold the whole section and rebuild it as part of Phase 2 item 11 (degradation band + benchmark panel)?
- **CEO decision:** "I agree with the staff, do fixes 1-4 now."
- **Follow-up (done, branch `claude/research-assessment-feedback-4auusg`, not deployed):**
  1. equity curve reframed as % return vs. $100k inception baseline (fill anchored at 0);
  2. full since-inception daily-resampled record instead of the ~33-day hourly window;
  3. drawdown panel on a fixed −40%…+2% scale;
  4. `LIVE · PAPER` tag + inception date on the section.
  Implemented via new pure `nav_history()` in `scripts/core_v1_dashboard_health.py` (7 unit tests).
  Still deferred to Phase 2 item 11 (governed artifacts only): benchmark overlay, Sharpe/Calmar,
  −26%/−35% band as drawn reference lines. Logged separately as a candidate panel, not folded in:
  per-sleeve equity curves.

## 2026-08-28 — deploy the dashboard redesign + reconcile the prod runtime branch
- **Raised by:** Ops/Compliance (the "Needs-CEO item" in `docs/engineering/CORE_V1_DASHBOARD_REDESIGN.md`)
- **The ask:** (1) how to deploy Phase 0 to `dashboard.iteradynamics.com`; (2) the live paper
  runtime + dashboard run from `/opt/itera/app` on `gpt/core-v1-paper-runtime`, a branch nobody
  in this thread reviewed — merge everything to `main` and repoint prod (Option 1), or cherry-pick
  just the 2 commits onto the stale branch (Option 2)?
- **CEO decision:** "option 1" — after staff showed the runtime-behavior delta between the two
  branches is the +64-line identity sidecar and nothing else (frozen `allocation.py` and the
  strategies/regimes are byte-identical; the rest of the 9.9k-line delta is research modules the
  runner never imports).
- **Follow-up (done):**
  - PR #45 merged `claude/research-assessment-feedback-4auusg` → `main` (`298ab63`), CI green.
  - `/opt/itera/app` repointed `gpt/core-v1-paper-runtime` → `main`, fast-forwarded, tree clean.
  - `itera-core-v1-paper.service` restarted 19:37 UTC — one off-cadence cycle 1234 (NAV
    $108,168.09 = cycle 1233, 0 fills), resumes hourly. Sidecar `core_v1_runtime_identity.json`
    now written each cycle (`main @ 298ab63`, not dirty). `state.json` byte-shape unchanged.
  - `itera-core-v1-dashboard.service` restarted onto `main`. Live dashboard shows real provenance.
  - Preview (`itera-dash-preview.service` on :8510, `dashboard-preview.moonwire.app`) torn down.
  - The design doc's "Needs-CEO item" is now marked RESOLVED. Prod tracks the reviewed mainline.
  - Paper record integrity unaffected — parity / shadow-runtime gates prove the sidecar write is
    byte-neutral for `state.json` / `fills.jsonl` / NAV / fill count.

## 2026-09-02 — promote month-end rebalancing into Campaign #57
- **Raised by:** CIO / Chief of Staff after the month-end equity/bond rebalancing sandbox screen passed its frozen gate and the separately frozen -5/-10/-15-session placebo test returned `MONTH_END_SPECIFICITY_SURVIVES`.
- **The ask:** authorize promotion of Month-End Equity/Bond Rebalancing Pressure from `SCREEN_POSITIVE` into the normal governed research pipeline as a new campaign.
- **CEO decision:** "Authorize promotion".
- **Follow-up (done):** Campaign #57 chartered in `docs/research/CAMPAIGN_57_MONTH_END_REBALANCE_PRESSURE_CHARTER.md`; authoritative campaign board updated; campaign history and current status updated. Sandbox SPY/AGG evidence is explicitly discovery-contaminated and may not be reused as confirmation. Authorized next step is limited to untouched VTI/BND source/calendar feasibility and a pre-outcome deterministic power simulation. No VTI/BND predictive outcome computation, economic backtest, Core v2 composition/weight, capital, paper/live action, or Core v1 change is authorized by this decision.

## 2026-09-03 — evaluate whether Itera should create a formal ML research arm

- **Raised by:** CEO — explicit instruction that this was research-program design evaluation
  only, not authorization to deploy ML, modify Core v1, change runtime behavior, alter
  portfolio weights, or begin live/paper trading.
- **The ask:** given Itera's actual historical experience with ML, is there a justified,
  bounded ML research program that complements existing deterministic research rather than
  recreating past overfitting/weak-OOS problems? Repo-grounded retrospective required before
  any proposal; full independent staff review (CIO, Quant Research, Red Team, Risk/PM)
  required; preferred initial concept to evaluate was an "Itera Residual Predictability
  Census" with a hard kill condition (`ML_COMPLEXITY_NOT_JUSTIFIED`).
- **Staff finding:** exactly two governed fitted-ML programs exist in this repo's history
  (Jump Risk Engine v0, Trend Persistence Engine v0) — both found real, validated OOS
  predictive skill and both died downstream of the model (economic mapping or runtime
  latency), never at statistical validation. A third, real but ungoverned ML program
  (Recovery Trust Gate) ran to a diagnostic negative and was abandoned outside governance
  entirely. Everything else living under `research/ml/` is deterministic/OLS-based despite
  the directory name. No apples-to-apples simple-vs-ML comparison has ever been run at Itera.
- **Independent Red Team verdict:** `CONDITIONAL PASS` on chartering the research direction,
  run as a genuinely separate subagent with no visibility into the in-thread staff draft, per
  the itera-staff skill's independence requirement. Eight binding conditions attach (frozen,
  power-sized candidate grid; frozen not searched hyperparameters; provably-causal
  residualization with a leakage canary; regime control restricted to the deterministic
  engine's causal path; cross-sectional tracks must measure real effective breadth first;
  `ML_COMPLEXITY_NOT_JUSTIFIED` as the pre-registered default; Recovery Trust closed first;
  any surviving signal re-enters the full Gate 0-4 sequence). Absent all eight, FAIL.
- **Staff recommendation:** charter a single bounded Phase 0/Phase 1 research-infrastructure
  campaign (Campaign #58), not a standing ML department — no named Core v2 structural
  deficiency is a modeling-technique gap. Two tracks: Phase 0 (primary) cross-sectional COT
  feature-family census (the only dataset with independently measured non-trivial effective
  breadth); Phase 1 (secondary, smaller) time-series residual census on
  BTC/ETH/SPY/QQQ/GLD as originally proposed.
- **Actions taken within staff's routine authority (no CEO input required):**
  1. Retroactively closed Recovery Trust Gate as a governance-documentation action
     (`docs/research/RECOVERY_TRUST_GATE_RETROACTIVE_CLOSURE.md`) — an already-existing
     negative result, not new research.
  2. Recorded Campaign #58 as a **planning charter** (not a frozen specification, per the
     standing amendment against freezing a spec the same session it is drafted):
     `docs/research/CAMPAIGN_58_ITERA_RESIDUAL_PREDICTABILITY_CENSUS_CHARTER.md`.
  3. Updated `docs/ITERA_CAMPAIGN_BOARD.md` and `docs/research/INDEX.md`.
- **CEO decision:** PENDING — whether to authorize staff to proceed to the specification-
  freeze prerequisites (autocorrelation-corrected power analysis, frozen candidate/
  hyperparameter grid) is logged as a 🔴 Needs-CEO item in `ops/status.md`, per the staff
  escalation rule that chartering a new research direction is not a routine staff call.

## 2026-09-03 — CEO authorizes Campaign #58 specification-freeze prerequisites

- **Raised by:** Staff (Campaign #58 planning charter, ML research arm review) — CEO decision
  logged as pending in `ops/status.md`.
- **CEO decision:** "AUTHORIZED: proceed from PLANNING CHARTER to the specification-freeze
  prerequisites for Campaign #58 — Itera Residual Predictability Census. This authorization is
  intentionally narrow."
- **Authorized now:** autocorrelation-corrected power analysis; effective-breadth measurement
  for the proposed Phase 0 cross-sectional universe; construction and commitment of the
  complete candidate grid; exact fixed hyperparameters for every permitted model type;
  chronological fold and target definitions; strictly causal expanding/walk-forward
  residualization specification; leakage-canary design and proof that the canary can fail;
  exact causal regime-state source/function identification; multiplicity/FDR family
  definition; Phase 0 and, if independently supportable by power, Phase 1 statistical-
  specification drafting and freeze. All eight binding independent Red Team conditions from
  the planning charter are adopted as-is. Default campaign outcome remains
  `ML_COMPLEXITY_NOT_JUSTIFIED` — CEO restated explicitly: ML does not earn continuation
  merely by producing statistically nonzero predictions; it must materially and reproducibly
  improve untouched chronological OOS information versus naive and simple statistical
  baselines under the same data, folds, targets, and multiplicity budget. Priority restated:
  Phase 0 (cross-sectional/non-price-information census) before Phase 1 (time-series
  residual-predictability census, only if pre-execution power/specification work supports
  it).
- **Not authorized yet:** fitting real ML models against real predictor/outcome data;
  predictor/outcome computation for a Campaign #58 decision; consuming any untouched holdout;
  broad hyperparameter search; neural networks; strategy optimization; Sharpe optimization;
  economic trading-rule construction; portfolio mapping; Core v2 composition or weights; Core
  v1 changes of any kind; runtime, threshold, order, execution, NAV, exposure, paper/live, or
  capital changes.
- **Required before the next transition:** once the specification-freeze prerequisites are
  complete, staff reports the proposed frozen design and power result back for the next
  governed transition before any real Campaign #58 model fit is run.
- **Follow-up (in progress):** staff proceeding to the power analysis, effective-breadth
  measurement, candidate grid, hyperparameter freeze, fold/target definitions, residualization
  spec, leakage-canary proof, regime-source identification, and FDR family definition per this
  authorization.

## 2026-09-03 — Campaign #58 specification-freeze prerequisites: result

- **Follow-up to the 2026-09-03 CEO authorization above.** Full record:
  `docs/research/CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md`.
- **Phase 0 (cross-sectional COT census): BLOCKED, not a decision.** This session's environment
  has no outbound network access to any market-data source (verified: proxy-level 403 on
  `cftc.gov`, `deribit.com`, and generic internet hosts alike), and no COT data is committed to
  this repo. The Red Team's required effective-breadth measurement for Campaign #58's own
  proposed universe cannot be run. Same class of gap as Campaign #57's VTI/BND block.
- **Phase 1 (time-series residual census): real, computed result — FAIL.** Power analysis run
  for real against the one multi-year dataset available (Campaign #48's committed BTC anchor
  inventory), reusing Campaign #53's governed block-bootstrap methodology verbatim
  (`scripts/run_campaign58_phase1_power_analysis.py`). Average power at the central IC (0.065)
  = 13.0% against the 50% floor, on the base 7-candidate family alone (before Phase 1's actual
  proposed grid adds further multiplicity, which would only lower this). BTC-only — no real
  ETH/SPY/QQQ/GLD data available this session. Result used as computed, not adjusted after
  seeing it fail, per Red Team condition 6.
- **Completed regardless of either track's data situation:** leakage canary built and proven
  capable of failing on synthetic data (`scripts/prove_campaign58_residualization_leakage_canary.py`
  — clean pipeline 0.0064 first-half leak-correlation, no false positive; leaky pipeline 0.6923,
  clearly detected); regime-state source identified and restricted to
  `research/regimes/baseline_engine.py`'s causal path, excluding the full-sample discovery
  tools; fixed hyperparameters chosen per model type (single values, not ranges); fold/target/
  FDR-family methodology recorded, not yet data-sized.
- **No specification frozen for either track** — per the CEO's own explicit conditional
  ("Phase 1... only if independently supportable by power") and the charter's Red Team
  conditions, neither track's inputs support a freeze today.
- **CEO decision:** PENDING — logged as a 🔴 item in `ops/status.md`: resource a future session
  to re-test Phase 1's power on the full BTC/ETH/SPY/QQQ/GLD scope, or accept the BTC-only
  result as a clean FAIL and close the time-series track. Staff does not recommend between
  these — a resourcing decision, not a routine research call.
