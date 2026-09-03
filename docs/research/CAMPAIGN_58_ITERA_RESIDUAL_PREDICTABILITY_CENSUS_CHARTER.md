# Campaign #58 — Itera Residual Predictability Census

## Status

**PLANNING CHARTER — full staff review complete (CIO, Quant Research, independent Red Team,
Risk/PM). Red Team verdict: CONDITIONAL PASS on chartering the research direction itself,
with eight binding conditions below. No statistical specification is frozen by this
document** — per the standing amendment that a spec may not be frozen the same session it is
drafted, and because two of the Red Team's own conditions (an autocorrelation-corrected power
analysis, and a frozen candidate/hyperparameter grid) are prerequisite work for that freeze,
not yet done.

**CEO authorization to proceed to that specification-freeze work is the open item this
charter creates — see "Needs CEO decision" below.** Nothing in this charter authorizes model
training, holdout consumption, predictor/outcome computation, or any runtime, strategy,
threshold, regime, signal, order, execution, portfolio, NAV, exposure, or dashboard change.
This document is research-program design only.

## Origin

The CEO asked Itera's staff to independently evaluate whether a formal, bounded ML research
program is justified given the fund's actual historical experience with machine learning —
explicitly not authorization to deploy ML, modify Core v1, or begin any trading action. This
charter is the output of that review.

## Plain-English question

> Given what has actually happened every other time Itera tried machine learning, is there a
> disciplined, bounded way to ask whether flexible-but-constrained ML extracts real
> information a simple statistical model cannot — separate from whether that information is
> ever worth trading?

## Part 1 — Repo-grounded retrospective (full record; condensed here)

Repo-wide search for actually-fitted learned models (`sklearn`/`xgboost`/`lightgbm`/
`hmmlearn`/`GaussianMixture`/`KMeans` imports, not just files living under a directory named
`ml/`) found exactly two governed research programs and one ungoverned one:

- **Jump Risk Engine v0** (`research/jump_risk_engine/lab.py`; GBM + Logistic Regression).
  Predicted rare jump events at 2h-120h horizons. ROC AUC 0.70-0.80, 5-7.5x top-quintile lift
  on 4 locked BTC candidates; **transferred to ETH without retuning** and retained meaningful
  ranking power (rare, strong evidence). Did not generalize to daily SPY/QQQ/GLD (150/180
  configs INVALID). Portfolio integration: downside-suppression mappings REJECTED (hurt
  Sharpe/Calmar/drawdown); an upside-boost-on-already-aligned-trend mapping PASSED (Sharpe
  1.318→1.400, CAGR +1.09pp, 5/6 OOS years positive). **RETIRED 2026-08-11** — not for a
  modeling reason. 98% of the edge decayed by bar 2 and the then-measured live runtime
  cadence (~1.5-1.7 bars) could not deliver it in time. CLAUDE.md's later correction
  (~0.5-0.6 effective bars) puts this on the edge of the stated reopening threshold on paper,
  but reopening is explicitly a separate, undecided governance act — this charter does not
  make that decision and does not depend on it.

- **Trend Persistence Engine v0** (`research/trend_persistence_engine/`; Logistic Regression
  carried all 4 validated candidates, GBM tried as a baseline and did not validate). Predicted
  continuation vs. reversal. ROC AUC 0.67-0.74, 3.5-5.3x top-5% lift, 93/126 nearby-parameter
  configs VALID, 0 REJECT — real, robust, cross-asset OOS predictive skill. **Every** tested
  portfolio mapping (5 overlays) was REJECTED, degrading Sharpe by 0.12-0.60 and worsening
  drawdown by up to 12pp. Closed with the institutional lesson recorded verbatim: "Out-of-
  sample predictive skill is necessary but insufficient."

- **Recovery Trust Gate** (`research/ml/recovery_trust/`; Logistic/RF/GBM, walk-forward
  folds, gates Core's own re-risk exposure increases). Real ML infrastructure (~3,000 lines)
  that never entered governance — no charter, no board entry, no frozen artifact. The only
  trace of its outcome is one line in an unrelated audit doc: "remains a research/diagnostic
  negative result... not productionized." **Retroactively closed** by this campaign's own
  precondition work — see `docs/research/RECOVERY_TRUST_GATE_RETROACTIVE_CLOSURE.md`.

Everything else living under `research/ml/` (`validation/` — historical regime taxonomy,
transition/structure discovery, alpha discovery, alpha surface discovery, drift detection,
event families, walk-forward harness, and Campaign #48's simple BTC price-state baselines;
`regime_clf/` — an empty placeholder; `calibration/` — Platt scaling bolted onto the
deterministic regime engine) contains **no fitted learned models**. It is deterministic,
rule-based, or OLS-based work that happens to share a directory name. The live regime path
(`research/regimes/baseline_engine.py`) is fully deterministic and causal.

**Campaign #48** (72 pre-frozen candidates: 8 simple predictors x 3 outcome families x 3
horizons, plain OLS+HC3, FDR q=0.05, 3 chronological partitions) is the fund's only rigorous,
apples-to-apples census of "is there information in simple price state" — and it deliberately
excluded ML. Result: 15/72 supported, **all 15 in the magnitude/volatility families, zero in
the directional-return family.** A follow-on, **Campaign #51**, tested whether
volatility/drawdown state *conditions* directional return (an interaction hypothesis) — clean
negative, all rankable candidates `DISCOVERY_NOT_SUPPORTED`. Confirmation of Campaign #48's
own findings is separately pending (Campaign #49, passive prospective accumulation,
method-locked, not yet run). **No apples-to-apples simple-vs-ML comparison has ever been run
at Itera** — that gap is what this campaign exists to close.

Cross-cutting pattern: where ML found real signal (Jump Risk, Trend Persistence), it was on
rare, short-horizon, event-level classification using econometrically simple engineered
features — and the added flexibility of GBM/RF was **not** the differentiator (Jump Risk
split 2-2 by lane between GBM and Logistic; Trend Persistence's validated candidates were
carried entirely by Logistic Regression). In both cases, predictive skill was real and
validated but died at the economic-mapping or infrastructure stage, never at the statistical
validation stage. Itera's historical bottleneck has not been "can a model find a pattern" —
it has been "does the pattern survive translation into portfolio exposure, delivered on time."

## Part 2 — Staff seats

### CIO / Head of Research

**An ML research arm is NOT strategically justified as a standing department.** No named
Core v2 structural deficiency (single return source, single-name crypto, no rates/fixed
income) is a modeling-technique gap — all three are return-source gaps, and CLAUDE.md is
explicit that a successor must address a named structural deficiency, not a technique
preference.

**The case against, stated directly:** two of three genuine ML efforts found real OOS
predictive skill and still never reached paper trading, killed downstream of the model
(economics or latency), not by it. Zero times has added model complexity been the
differentiator when something worked. On priors, more ML modeling capacity is not what has
bottlenecked Itera's progress toward capital deployment.

**The case for, narrowly:** Campaign #48 never got an ML arm to compare against, so the fund
has never actually tested — in one pre-registered design, same folds, same targets — whether
constrained ML beats a simple model net of the multiplicity it costs. That is a legitimate,
bounded, one-time research-infrastructure question, not a mandate for ongoing bespoke ML per
idea (which is what actually happened three separate times previously, with no shared
baseline-comparison discipline across them).

**Recommendation:** charter this as a single, narrowly bounded Phase 0/Phase 1 campaign, not
a department. The kill condition (`ML_COMPLEXITY_NOT_JUSTIFIED`) is the mechanism that keeps
it bounded — if it fires, ML is closed as a research direction pending a materially different
dataset, exactly as Jump Risk and Trend Persistence were closed on their own terms, not
reopened with a bigger model.

### Quant Research

**Two tracks, not one, with an explicit priority order and reasoning for it** (the CEO's
brief asked for this comparison if staff disagreed with a single time-series design):

- **Phase 0 (primary): cross-sectional feature-family census on the COT futures universe.**
  Campaign #55 already *measured* real effective breadth there — 5.1 independent markets out
  of 21 nominal ones (mean pairwise forward-return correlation +0.155) — the only dataset in
  the shop with a directly measured, non-trivial breadth number. A single-asset time-series
  census on BTC/ETH/SPY/QQQ/GLD inherits the same shape of problem every single-instrument
  idea here has hit (crash-short n=1 regime history, TLT n=1 rate-regime history, Campaign
  #48's 403 heavily-overlapping 168h-spaced anchors).
- **Phase 1 (secondary, smaller scope, complementarity check): time-series residual census**
  on BTC/ETH/SPY/QQQ/GLD, as originally proposed — worth doing once, cheaply, alongside Phase
  0, but explicitly not the flagship given the known power ceiling.
- **Not proposed:** re-running cross-sectional crypto momentum (Coinbase spot) as a feature
  source — already closed as a clean discovery-stage null (single-coin outlier artifact, not
  real breadth) and re-litigating it inside a differently-framed census without new data is
  not a fresh test.

**Design (both tracks, pending the specification freeze this charter does not itself do):**
baselines in the same design/folds/targets — naive/unconditional, simple linear/logistic,
then the constrained ML set (ridge/elastic net, logistic/linear, shallow RF, shallow GBM; no
neural networks, no broad hyperparameter search). Residualize against momentum, realized
volatility (reusing Campaign #48's own predictor definitions rather than redefining them),
Itera's deterministic regime state (`research/regimes/baseline_engine.py`'s causal per-bar
path only — see Red Team condition 4), and Core v1's own SMA175 trend state. **Explicitly
excluded from "known signals" available for residualization: any not-yet-holdout-confirmed
discovery candidate** (Campaign #53's `funding_level_72h`/`funding_persistence`, Campaign
#57's month-end signal) — treating an unconfirmed result as a control would let unvalidated
research quietly anchor the census.

### Independent Red Team

**Verdict: CONDITIONAL PASS.** Full independent record: this document's Part 3. The review
ran as a genuinely separate subagent context with no visibility into the CIO/Quant/Risk-PM
drafts above, per the itera-staff skill's independence requirement — it built its own repo
inventory from scratch and reached materially the same retrospective conclusions
independently, plus found two things the in-thread review missed: Campaign #51's negative
interaction test, and the specific regime-engine naming-collision landmine (condition 4
below). Eight binding conditions attach to any Phase 0 implementation GO; **absent all eight,
this should be read as FAIL**, not a soft caution.

### Risk / PM

**Question answered: could this plausibly produce an orthogonal return source, or would it
repackage trend/volatility/beta Itera already holds?** No sizing or capital discussion, per
the CEO's own scoping.

All three genuine ML efforts at Itera targeted variants of trend/momentum/volatility timing
conditioned on Core's own price history and Core's own signals — Jump Risk's only validated
mapping explicitly amplifies Core's existing trend direction; Trend Persistence detects the
same continuation phenomenon Core's SMA engine already trades, with a different technique;
Recovery Trust gates Core's own re-risk decisions. **None targeted a different economic
mechanism.** By contrast, every genuinely orthogonal return source this fund has found
(funding/basis carry, COT positioning extremes, the volatility risk premium) came from
choosing a different economic mechanism via deterministic/statistical methods, not from
applying ML to price history.

**Verdict: PLAUSIBLE orthogonality only if scoped to non-price-history, cross-sectional/
positioning/carry-type feature families (the COT track) — UNLIKELY if scoped to price-history
features on Core's own instruments**, which would reproduce the same pattern both prior
rigorous ML efforts fell into. This directly supports Quant's Phase 0/Phase 1 priority order
above. Additional requirement for the eventual deliverable: "residualized against known
Itera signals" is necessary but not sufficient for orthogonality — a feature can be
uncorrelated with Core's signals today while still proxying Core's beta. Any candidate the
census flags as supported gets a simple realized-correlation-to-Core-NAV check before being
described as orthogonal, even at the observation-only stage.

## Part 3 — Independent Red Team review (verbatim conditions)

The subagent's full inventory and reasoning independently corroborate Part 1 and add:
Campaign #51's clean negative interaction test; the likely identity of Recovery Trust's
target (`equity_sma175_v3`'s partial de-risk branch, the one strategy CLAUDE.md flags as the
backtest engine's sole `HOLD`-intent exception); Jump Risk's own locked hyperparameters
(`RandomForestClassifier(n_estimators=250, max_depth=5, min_samples_leaf=25)`,
`GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.04)`) as
precedent for how much implicit hyperparameter search this fund's own prior ML work has
carried without being charged against a stated multiplicity budget; and a **governance-
discipline asymmetry** between ML and statistical work as an independent, un-prompted
finding — Itera's deterministic campaigns have never shipped a result without freeze/replay/
closure discipline, but both prior fitted-ML programs only met that bar when escalated all
the way to portfolio integration (Jump Risk), while the one that stopped early (Recovery
Trust) simply disappeared from governance. That asymmetry, not literal Core v1 mutation, is
identified as the real mechanism by which an ML arm could become "retuning at larger scale in
disguise" — a ranked list of "surviving signal" from an ungoverned or loosely-governed census
is exactly the kind of artifact a future session could be tempted to wire toward Core v2
without re-running the standard gate sequence.

**Binding conditions, with teeth**, required before any Phase 0 implementation GO:

1. **Freeze the full candidate grid before any residual or fit is computed** — every feature
   family x horizon x target x model-type (simple and ML) combination enumerated and
   committed, Campaign-#48-style, hard-capped (recommended ≤150 candidates), sized to what a
   power analysis using **autocorrelation-corrected effective n** (Campaign #53's
   `inject_ic`-fixed methodology, not raw row counts) can support at ≥50% power per Amendment
   1.
2. **Freeze exact hyperparameters per model type as single fixed values**, not a search
   range, before any data is touched; any deviation is a new candidate charged against the
   same FDR family.
3. **Residualization must be strictly expanding/walk-forward** (known-signals model fit on
   rows ≤t only), with a pre-registered leakage canary proven capable of failing — inject a
   synthetic leak, confirm the census's own detector catches it — before any real residual is
   computed.
4. **Regime-state control sourced only from `research/regimes/baseline_engine.py`'s causal
   per-bar path**, named by exact function reference in the frozen spec, explicitly
   prohibited from using any tool under `research/ml/validation/historical_regime_*` (those
   are full-sample offline discovery tools; using one as a per-bar "control" would silently
   leak full-sample information into every row).
5. **Any cross-sectional track must open by measuring real effective breadth** (mean pairwise
   forward-return correlation across its universe, Campaign #55's method) before any power
   claim is made for that specific universe — do not assume cross-sectional beats single-asset
   without re-deriving it.
6. **`ML_COMPLEXITY_NOT_JUSTIFIED` is the pre-registered default outcome**, not a fallback —
   this fund's only two completed fitted-ML programs show flexible models have not reliably
   beaten simple logistic regression on the same targets; the census tests whether that
   pattern holds, and is not designed to be surprised if it does.
7. **Recovery Trust closed first** — done by this charter's own precondition work; see
   `docs/research/RECOVERY_TRUST_GATE_RETROACTIVE_CLOSURE.md`.
8. **Any surviving signal re-enters the standard charter-campaign gate sequence (Gates 0-4)
   in full** before it is trading-relevant — the census confers no shortcut past horizon
   feasibility, tradeability, materiality, or power, and under no circumstance authorizes a
   Core v1 or Core v2 change directly.

## Part 4 — Scope

### Explicitly allowed now

- This planning charter itself, and the Recovery Trust retroactive closure it depends on
  (both complete as of this document).
- Future work, **only after CEO authorization**, on the specification-freeze prerequisites
  Red Team condition 1 and 2 require: an autocorrelation-corrected power analysis (reusing
  Campaign #53's fixed `inject_ic` methodology) and an enumerated, hard-capped candidate grid
  with frozen hyperparameters — both are design work, not outcome generation, and produce no
  predictor/outcome values.

### Explicitly NOT authorized yet

- Any predictor, feature, residual, or outcome computation on real data, for either track.
- Any model training or fitting, of any model type (simple or ML).
- Any implementation code, runner code, or test beyond what a future frozen specification and
  implementation handoff separately authorize, mirroring Campaign #48's own two-stage
  freeze-then-handoff-then-GO structure.
- Any inspection of the CDE live-forward funding holdout, the VTI/BND holdout, or any other
  campaign's sealed holdout, for any purpose connected to this campaign.
- Any strategy, signal, threshold, regime, order, execution, portfolio, NAV, exposure,
  dashboard, or runtime change of any kind.
- Any Core v1 change, under any staff consensus, at any confidence level.
- Any Core v2 composition, weighting, or capital decision.
- Treating any output of this campaign, present or future, as validated, tradeable, or
  economically material without separately clearing Gates 0-4 in a follow-on campaign.

## Part 5 — Frozen success/failure criteria (fixed now, before any experiment exists)

A feature-family x horizon cell is a **supported ML lift** only if all three hold:

1. OOS lift of the best-performing constrained-ML model over the matched simple baseline
   survives family-wise FDR correction across the full frozen grid (Red Team condition 1) —
   not evaluated cell-by-cell.
2. The lift is stable in sign and rough magnitude across at least two independent
   chronological folds/regimes, not concentrated in one (the same discipline that caught the
   COT window-bias artifact and the crypto-momentum outlier artifact).
3. The lift survives a label-permutation negative control: shuffle the target, refit under
   the identical frozen grid — if ML beats the simple baseline on shuffled labels too, that is
   model/infrastructure artifact, not signal, and the cell does not count regardless of (1)
   and (2).

**If zero cells in the frozen grid clear all three**, across both Phase 0 and Phase 1, the
campaign closes with verdict `ML_COMPLEXITY_NOT_JUSTIFIED` — a complete, legitimate,
governed answer, not a prompt to widen the grid or try a larger model. Any widening after
seeing this result would itself be exactly the kind of post-hoc multiplicity this charter
exists to prevent.

**If any cell clears all three**, the campaign closes as a supported research association
(Campaign #48's own vocabulary) and is handed to the standard charter-campaign gate sequence
for Gates 0-4 before any economic-value or Core v1/v2-relevant claim is made — this campaign
itself makes no such claim under any outcome.

## Part 6 — Needs CEO decision

Chartering a new research direction is a CEO-level decision under the staff escalation rule,
not a routine call staff makes unilaterally. Framed as one choice:

**Authorize staff to proceed with the specification-freeze prerequisites (autocorrelation-
corrected power analysis + frozen candidate/hyperparameter grid, Red Team conditions 1-2),
or hold this at planning-charter stage?**

Recovery Trust's retroactive closure (Red Team condition 7) is done regardless of this
decision — it is a documentation-only action within staff's routine authority (closing a
program on an already-existing negative result, not new research), not contingent on
authorizing the new campaign.

## Part 7 — One next action staff recommends

Nothing beyond this charter and the Recovery Trust closure should happen without the CEO
decision in Part 6. If authorized, the single next action is the autocorrelation-corrected
power analysis (Red Team condition 1) — it is cheap, touches no new data (reuses Campaign
#53's `inject_ic` methodology and each track's already-acquired history), and determines
whether either track can even support a hard-capped candidate grid at ≥50% power before any
further design work is worth doing. If that power analysis fails, as several prior
single-instrument and even the original two-market COT design did, this campaign should close
at that gate exactly as Campaign #55's COT idea did before its cross-sectional remedy — cheaply,
before any specification is frozen.
