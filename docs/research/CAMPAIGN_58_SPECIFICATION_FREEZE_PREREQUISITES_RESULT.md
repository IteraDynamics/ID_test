# Campaign #58 — Specification-Freeze Prerequisites: Result

## Status

**PRE-EXECUTION PREREQUISITES RESULT — not a frozen governing specification.** Produced under
the CEO's 2026-09-03 authorization (`ops/decisions.md`) to proceed from Campaign #58's planning
charter to the specification-freeze prerequisites. This document reports what that work found,
including one real, computed, negative power result and one real, structural data-access block.
Per the CEO's own explicit conditional language ("Phase 1... only if independently supportable
by power") and the charter's own Red Team conditions, **neither Phase 0 nor Phase 1 supports a
specification freeze today.** No predictor/outcome computation, model fit, or holdout access
occurred. Two pieces of real computation did occur, both explicitly authorized as pre-execution
methodology calibration, not outcome generation: a power simulation against already-committed
data, and a leakage-canary proof against synthetic data.

## 1. Data and network access — verified, not assumed

This session's environment has **no outbound network access to any market-data source**:
`cftc.gov`, `deribit.com`, and even generic internet hosts (`www.google.com`) all return a
proxy-level `403 CONNECT tunnel failed` — organization policy, confirmed via the proxy's own
status endpoint, not a transient failure. This repo's `data/` directory, per its own governed
convention (CLAUDE.md: "Data lives locally on the operator's machines... `data/*.csv` is
gitignored"), holds only a partial 2026 BTC file (`btcusd_3600s_2026-01-01_to_2026-07-31.csv`,
7 months). No COT positioning history, no funding-rate history, and no multi-year ETH/SPY/QQQ/
GLD history are present or reachable in this session.

The one piece of real, multi-year, already-committed, already-governed data available is
Campaign #48's own canonical anchor inventory
(`artifacts/simple_btc_price_state_predictive_baselines/price_state_anchor_inventory.csv`) —
403 real anchors, 2018-2025, 168h-spaced, 8 real BTC-derived predictor columns, replay-verified
when originally produced. This is the only dataset in this session that any real computation
below could honestly be run against.

## 2. Phase 0 (cross-sectional COT census) — BLOCKED on data access

**No effective-breadth measurement was possible.** Red Team condition 5 requires measuring real
effective breadth (mean pairwise forward-return correlation, Campaign #55's own method) for
Campaign #58's specific proposed Phase 0 universe before any power claim. That requires real COT
positioning and price history, none of which is present or reachable in this session. Citing
Campaign #55's historical 5.1/21 figure would not satisfy this — it was measured for a different
(2026-08-26) discovery-stage universe and design, not Campaign #58's own proposed feature-family
census, and reusing an old number without re-deriving it is exactly the shortcut Red Team
condition 5 exists to forbid.

**This is a data-availability gap, not a negative finding about the idea.** It is the same class
of blocker Campaign #57's own session hit acquiring VTI/BND data (logged plainly as "blocked on
a future session with data access, not a decision" — `ops/status.md`, 2026-09-02 entry). Per
that precedent, this is reported as blocked, not routed around, worked around with a substitute
universe, or estimated from an old number.

**Consequently:** the candidate grid, hyperparameter sizing, and specification freeze for Phase 0
cannot proceed until a future session with real COT/price data access re-runs the effective-
breadth measurement and the corresponding power analysis.

## 3. Phase 1 (time-series residual census) — real result: FAIL at the power gate

A power analysis was run for real, against real committed data, adapting Campaign #53's own
governed block-bootstrap `inject_ic` methodology
(`scripts/run_campaign58_phase1_power_analysis.py`, reusing Campaign #53's block-bootstrap,
empirical-null, and BH-FDR functions verbatim). Full artifact:
`artifacts/campaign58_phase1_power_analysis/phase1_power_analysis_20260903T141959Z.json`.

**This result is BTC-only.** No real ETH, SPY, QQQ, or GLD multi-year history is present in this
session, so this cannot speak to the full BTC/ETH/SPY/QQQ/GLD scope the charter proposed for
Phase 1 — it bounds the BTC leg only, the same category of proxy caveat CLAUDE.md's own cadence
entries already carry between BTC and ETH. The "target-like" series used to calibrate realistic
null/injection structure is a real Campaign #48 predictor column
(`realized_volatility_trailing_24h`) used as a stand-in for realistic marginal/autocorrelation
properties — not a literal forward-return outcome, since the committed CSV holds fitted summary
statistics, not raw outcome values. Both caveats are recorded in the artifact itself, not just
here.

**Result: average power at the central IC (0.065) = 0.130 (13.0%), against a 50% floor. FAIL.**
Per-candidate power at the central IC ranged 7.3%–19.3% across the 7-member real BTC price-state
family (`return_trailing_{24h,72h,168h}`, `realized_volatility_trailing_168h`,
`distance_from_mean_trailing_168h`, `range_position_trailing_168h`,
`drawdown_from_high_trailing_168h`). This is the power of the base 7-candidate family alone,
under the SAME FDR/confirmation gate Campaign #53 used (BH q=0.10, top-2 confirmation shortlist)
— before Phase 1's actual proposed design adds its own further multiplicity (multiple feature
families beyond these 8, multiple horizons, multiple model types including the constrained-ML
set). Adding that multiplicity would not improve this number; the FDR correction gets stricter
as the family grows, so a design that already fails at 13% power on its narrowest sub-family
cannot be rescued by widening it.

**This result is used as computed, not adjusted after seeing it fail.** Per Red Team condition 6
and the charter's own frozen success/failure criteria, widening the grid, changing the anchor
spacing, or picking a different proxy-target column now — after seeing this result — would
itself be exactly the kind of post-hoc multiplicity laundering this campaign exists to prevent.
Campaign #48's own 168h anchor spacing is the best-precedented, already-governed choice for this
family; a finer-grained redesign was not proposed or justified before this result was seen, so
none is adopted now to rescue it.

**Per the CEO's own explicit conditional ("Phase 1... only if independently supportable by
power"): Phase 1 does not qualify for specification freeze at this time.**

## 4. Leakage canary — designed, and proven capable of failing (Red Team condition 3)

Built and run against synthetic data only, per CLAUDE.md's own standing lesson ("a check that
cannot fail is not evidence"). Full script:
`scripts/prove_campaign58_residualization_leakage_canary.py`. Artifact:
`artifacts/campaign58_leakage_canary_proof/canary_proof_20260903T142148Z.json`.

**Construction:** a synthetic known-signal `K_t ~ N(0,1)` and a target `Y_t` whose true
dependence on `K_t` has a regime shift (`beta=1.0` for the first half of the sample, `beta=3.0`
for the second half) — a fully known, fabricated ground truth. Two residualization pipelines are
compared on the identical data: a **clean, strictly expanding/walk-forward** fit (row `t`'s
first-stage coefficient uses only rows `< t`) versus a **leaky, full-sample** fit (one OLS
coefficient estimated on the whole sample, including future rows, applied to every row). The
canary metric is `|correlation(residual, K_t)|` restricted to the first half of the sample — the
period whose true beta a leaky full-sample fit could not have legitimately known yet.

**Result:** clean pipeline first-half correlation `0.0064` (no false positive); leaky pipeline
first-half correlation `0.6923` (leak clearly detected). The canary is proven capable of both
not crying wolf on an honest pipeline and catching a real leak. Campaign #58's eventual real
residualization step adopts the same expanding-window-only construction, with this canary
metric as a standing pre-flight check before any real residual is computed or inspected.

## 5. Regime-state source — identified (Red Team condition 4)

The only authorized control for "Itera's deterministic regime state" in any future Campaign #58
specification is `research/regimes/baseline_engine.py`'s `BaselineRegimeEngine.classify_bar` (or
`classify_dataframe`, which calls it per-row) — verified causal by direct inspection: each call
uses `df.iloc[:bar_idx+1]` before computing any indicator, and the method's own docstring states
"Only uses data at positions 0..bar_idx — no lookahead." **Explicitly prohibited:** any tool
under `research/ml/validation/historical_regime_*` (`historical_regime_taxonomy.py`,
`historical_regime_structure_discovery.py`, `full_historical_regime_state_sequence.py`) — these
are full-sample offline discovery tools by design and purpose, not per-bar causal signals; using
one as a per-bar "control" would silently leak full-sample information into every row, exactly
the landmine Red Team's independent review flagged from the two tools' similar names and shared
directory.

## 6. Fixed hyperparameters per model type (Red Team condition 2)

Single fixed values, not ranges, chosen before any real predictor/outcome data is touched.
Reused and adapted from this fund's own prior governed precedent (Recovery Trust's
`_make_model`, `research/ml/recovery_trust/model.py`) rather than invented fresh, per this
fund's convention of not re-deriving an already-reasoned choice from scratch. Any deviation from
these exact values in a future real run is a new candidate, charged against the same FDR family.

| Model type | Fixed configuration |
|---|---|
| Logistic / linear regression (simple baseline) | scikit-learn defaults; `LogisticRegression(C=1.0, max_iter=1000, random_state=42)` for classification targets, `LinearRegression()` for continuous targets |
| Ridge | `Ridge(alpha=1.0, random_state=42)` |
| Elastic net | `ElasticNet(alpha=1.0, l1_ratio=0.5, random_state=42)` |
| Shallow random forest | `RandomForestClassifier(n_estimators=100, max_depth=4, min_samples_leaf=20, class_weight="balanced", random_state=42)` (regressor variant analogous for continuous targets) — depth and leaf-size match Recovery Trust's own already-reasoned shallow configuration |
| Shallow gradient boosting | `GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)` (regressor variant analogous) — identical to Recovery Trust's own configuration |

Explicitly excluded, per the charter and both CEO authorizations: neural networks of any kind,
and any hyperparameter search — grid, random, or Bayesian — beyond this single fixed set per
model type.

## 7. Chronological fold and target definitions (methodology, not yet data-bound)

Reuses Campaign #48's own already-governed convention rather than inventing a new one:

- **Folds:** contiguous, near-equal chronological partitions (not random split, not shuffle, not
  cross-sectional fold, not bootstrap split) — partition 1 develops partition 2's evaluation;
  partitions 1+2 develop partition 3's evaluation; all candidate-complete rows form the pooled
  fit. Any standardization or first-stage residualization parameter is fit on development rows
  only, applied forward, never fit on the evaluation partition itself.
- **Targets:** each track defines its own target family before any candidate value is computed
  (Phase 0: cross-sectional forward return/rank at each rebalance point within the COT universe;
  Phase 1: forward return/magnitude/volatility at fixed horizons, mirroring Campaign #48's own R/
  M/V family structure) — frozen at the same time as the candidate grid, not adjusted afterward.

This is a methodology commitment, not yet applied to real data for either track, since neither
track currently has the breadth/power inputs needed to size or freeze an actual grid.

## 8. FDR / multiplicity family structure (Red Team condition 1)

Structure, not yet sized: every feature family × horizon × target × model-type (simple and ML)
combination forms one candidate, enumerated and frozen before any data is touched, hard-capped
at 150 total candidates. Benjamini-Hochberg FDR applied within each track's family (mirroring
Campaign #48's per-outcome-family application), sized to whatever real effective n and power
result an eventual real data-backed power analysis supports. **This cannot be sized today** —
Phase 0 has no breadth number, and Phase 1's own base family already fails power before any
grid-widening multiplicity is added, so no candidate count for either track can be responsibly
frozen against a power target that has not itself cleared 50%.

## 9. What this means for the campaign

Neither track supports a specification freeze today. This is not a failure of the prerequisite
work — it is the prerequisite work doing its job: Red Team condition 6 named
`ML_COMPLEXITY_NOT_JUSTIFIED` as "the pre-registered default outcome, not a fallback," and the
same discipline applies one step earlier, at the power gate, exactly as it did for Campaign #55's
original two-market COT design before its cross-sectional remedy. A specification frozen without
a real, clearing power result would be exactly the kind of ungoverned optimism this campaign's
own charter was written to prevent.

**What is durable and carries forward regardless of which track eventually gets a supportable
power result:** the leakage canary (proven), the regime-state source restriction (identified),
and the fixed hyperparameter set (chosen) do not depend on which track's data becomes available
first — they apply to whichever track is eventually specified.

## 10. Recommended next actions (staff recommendation, not a decision made here)

1. **Phase 0 is blocked on a future session with real COT and price-history network/data
   access** — the same class of gap Campaign #57 hit and logged, not a judgment call available
   to resolve from here. Once resolved, re-run the effective-breadth measurement for Campaign
   #58's actual proposed universe, then the power analysis, before any grid is sized.
2. **Phase 1, as scoped, does not clear the power gate on the one real dataset available in this
   session (BTC-only, 13% average power at the central IC).** Two honest paths, neither decided
   here: (a) a future session with real multi-year ETH/SPY/QQQ/GLD data could re-run this power
   analysis across the full proposed instrument set — pooling more real assets could plausibly
   raise effective n, the same logic Campaign #53 used pooling BTC+ETH funding; or (b) accept
   this as a clean, cheap FAIL and close the time-series track without further resourcing,
   consistent with how underpowered designs have been closed elsewhere in this fund's history.
   Staff does not recommend between these here — it is exactly the kind of fork that should go
   back to the CEO rather than be resolved unilaterally, since it is a resourcing decision
   (whether to spend a future session acquiring more data) rather than a routine research call.
3. Recovery Trust's closure, the leakage canary proof, the regime-source restriction, and the
   fixed hyperparameter set are complete and do not need to be revisited when either track's
   data situation resolves.

## 11. Correction, 2026-09-03 (same day): real multi-asset Phase 1 power result — PASS

The CEO resolved item 2 above directly, by running §3's script locally against the full real
BTC/ETH/SPY/QQQ/GLD dataset (2018-2025, ~70k hourly BTC/ETH rows, ~3,200-5,500 daily SPY/QQQ/GLD
rows) — the option this document declined to recommend between. This section records the real
result on the generalized multi-asset script
(`scripts/run_campaign58_phase1_power_analysis.py`, revised same day to accept operator-supplied
OHLCV paths instead of the BTC-only committed artifact §3 used).

**Provenance:** this result is the operator's own terminal output, run on their local machine
where the full data lives — not independently re-executed by staff, since staff has no access to
that data (§1's network/access constraints are unchanged in this session). Staff DID
independently recompute the reported headline number from the printed intermediate values
(central-IC linear interpolation between the IC=0.05 and IC=0.08 grid points, per candidate,
then averaged) and it matches the reported `0.583` to four decimal places (`0.5834`), and the
reported pooled anchor count (`2527`) matches the sum of the five per-asset anchor counts printed
(`417+417+456+456+781`). This is real, internally consistent output, not garbled or fabricated in
transit — but the underlying CSVs themselves have not been independently inspected by staff.

**Result: average power at the central IC (0.065) = 58.3%, against the 50% floor — PASS.** 2,527
real pooled anchors across all 5 proposed instruments (BTC 417, ETH 417, SPY 456, QQQ 456, GLD
781 — daily assets contributed more anchors per unit of history since their native cadence,
correctly inferred, gives finer 7-bar rather than 168-bar anchor spacing). This clears the base
7-candidate family's power gate on the FULL proposed Phase 1 instrument scope — the gap this
document's §3 and §10-item-2 explicitly left open (BTC-only, 13.0%, FAIL) is closed.

**Not uniform across the family — worth recording precisely rather than only the average.** At
the central IC, 5 of 7 candidates individually clear 65-75% power: `return_trailing_24h` 75.4%,
`return_trailing_72h` 73.7%, `return_trailing_168h` 70.4%, `distance_from_mean_trailing_168h`
72.4%, `range_position_trailing_168h` 65.4%. **Two candidates fall well under the 50% floor
individually:** `drawdown_from_high_trailing_168h` at 31.7%, and `realized_volatility_trailing_168h`
at only 19.7% — the weakest by a wide margin. The volatility candidate's weakness has a clear,
sensible explanation rather than looking like a defect: it has by far the highest lag-1
autocorrelation in the pooled data (0.7826, vs. -0.03 to 0.33 for the other six), giving it a
correspondingly wider empirical null distribution (null median |r| 0.0282 vs. 0.0118-0.0185 for
the rest) — a noisier candidate needs a larger true effect to detect at a fixed power level,
exactly the mechanism this whole methodology exists to surface rather than paper over with a
simple average. **The 58.3% headline is real, but it is carried by the return- and
position-style candidates, not evenly by the whole family** — this matters for how the eventual
full grid is sized (see below): a grid weighted toward volatility-style features specifically
should not assume it inherits this session's average power.

**What this does and does not yet establish, stated plainly:**

- It establishes that the real, pooled, five-asset dataset itself carries enough independent
  information for the base 7-candidate price-state family to be worth taking further — a
  genuine, data-grounded green light for Phase 1 that did not exist before this run.
- It does **not** yet establish that the actual charter-scoped grid (multiple feature families
  beyond these 7, both raw and residualized target versions, multiple horizons, and all six
  permitted model types compared against each other and against simple baselines — Red Team
  condition 1's hard-capped ≤150-candidate family) clears power. A family that large applies a
  stricter Benjamini-Hochberg threshold than this 7-candidate test did; whether it still clears
  50% is real, undone work, not a formality.
- Per the CEO's own conditional ("Phase 1... only if independently supportable by power"),
  Phase 1 is now **eligible to proceed** to actual grid construction and grid-level power
  testing — the fork this document logged in ops/status.md ("resource a re-test, or close the
  track") is resolved: the re-test happened and passed. **The remaining fork is a new, narrower
  one — proceed to size and test the real frozen grid, which is itself the next authorized
  specification-freeze step, not a new CEO decision.**

Full artifact (operator's machine, not committed — `artifacts/` is gitignored per repo
convention): `artifacts\campaign58_phase1_power_analysis\phase1_power_analysis_multiasset_20260903T150203Z.json`.
