# Campaign #58 Phase 1 — Frozen Statistical Specification

## Status

**FROZEN GOVERNING SPECIFICATION for candidate-grid structure, model definitions, folds, targets,
residualization, and decision rules — frozen before any real predictor/outcome value, residual,
or model fit is computed, viewed, inspected, ranked, or interpreted.**

**Correction — independent Red Team review, same day: `CONDITIONAL_PASS`, ten binding
conditions, all applied below.** Full review:
`docs/research/CAMPAIGN_58_PHASE1_SPEC_INDEPENDENT_RED_TEAM_REVIEW.md`. The review independently
verified the hyperparameter freeze, leakage canary, regime-source restriction, grid arithmetic,
and §12c's sourcing against real code and real committed numbers — all confirmed genuine, not
merely claimed. It also found: a filename defect (fixed in §13/§14 below); that the grid-level
power check must cover all three outcome families, not Family R alone (§14, script updated); that
§12b's material-margin threshold was untested and roughly 5× the census's own assumed effect size
(§12b, recalibrated below); that the permutation/lift-null constructions and the best-of-N model
selection needed explicit multiplicity treatment (§12a/§12b, stated below); that §12c's flagged
list needed to be explicitly closed and its "90 clean candidates" claim made conditional (both
done below); and that the charter's own Risk/PM correlation-to-Core-NAV check was dropped rather
than deferred (reinstated in §12d below). Each correction is marked at the section it changes,
per this fund's append-only-correction convention — the original frozen text is not silently
rewritten.

This freezes the design. It does **not** authorize execution. Gates remain open and are stated
explicitly in §12/§13 rather than assumed clear: (1) a grid-level power verification at this
grid's actual family size, across all three outcome families (not yet run — the only power
result that exists, §2, tested a 7-candidate Family-R-only base family; the one grid-scale
attempt so far, `artifacts/campaign58_grid_power_analysis/grid_power_analysis_20260903T152626Z.json`,
was a tiny-file smoke test with `min_trials_per_hypothesis: 0`, not informative), (2) the §12b
material-margin recalibration's own power has not been independently verified, and (3) a new,
explicit CEO authorization for real predictor/outcome computation and model fitting, which the
standing 2026-09-03 authorization did not grant (it authorized specification-freeze work only).
No gate is satisfied by this document.

Campaign #58 Phase 1 remains observation-only. It authorizes no runtime, threshold, regime,
classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or
model-training-for-production change, and no Core v1 or Core v2 change of any kind.

## Governed lineage

- planning charter: `docs/research/CAMPAIGN_58_ITERA_RESIDUAL_PREDICTABILITY_CENSUS_CHARTER.md`
- specification-freeze prerequisites result:
  `docs/research/CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md`
- Recovery Trust retroactive closure:
  `docs/research/RECOVERY_TRUST_GATE_RETROACTIVE_CLOSURE.md`
- independent Red Team review of this specification (`CONDITIONAL_PASS`, 10 conditions, applied):
  `docs/research/CAMPAIGN_58_PHASE1_SPEC_INDEPENDENT_RED_TEAM_REVIEW.md`

## 1. Plain-English question

> After controlling for simple momentum, volatility, Itera's deterministic regime state, and
> Core v1's own trend state, is there stable, genuinely out-of-sample predictive information
> left in BTC/ETH/SPY/QQQ/GLD price-state features that flexible-but-constrained ML extracts
> better than simple statistical models — and does that hold up under a negative control and
> across independent chronological folds?

This is a research-methodology census, not a trading-strategy backtest. A supported result
establishes a research finding only; it triggers no economic claim, no Core v1/v2 comparison, and
no automatic advance to a trading-relevant campaign (§12).

## 2. Governed power result this specification is built on

`docs/research/CAMPAIGN_58_SPECIFICATION_FREEZE_PREREQUISITES_RESULT.md` §11: real, computed,
operator-run power analysis on the full real BTC/ETH/SPY/QQQ/GLD dataset (2018-2025), 2,527
pooled real anchors, central IC 0.065, **average power 58.3% (PASS)** against the base 7-candidate
raw price-state family, using the exact assets, horizons, block size (8 anchors), and central IC
frozen in that run. **Not modified here in response to the observed power profile**, per that
result's own frozen discipline and this task's explicit instruction — every asset, horizon, base
feature definition, block size, and central IC below is identical to what was already tested.

**Materially uneven per-feature power, carried forward as a first-class fact, not smoothed into
an average** (§10 turns this into a binding interpretation rule):

| Base feature | Central-IC power (7-candidate test) | Lag-1 autocorrelation (pooled) |
|---|---:|---:|
| `return_trailing_24h` | 75.4% | -0.030 |
| `return_trailing_72h` | 73.7% | 0.001 |
| `return_trailing_168h` | 70.4% | 0.020 |
| `distance_from_mean_trailing_168h` | 72.4% | 0.001 |
| `range_position_trailing_168h` | 65.4% | 0.007 |
| `drawdown_from_high_trailing_168h` | 31.7% | 0.331 |
| `realized_volatility_trailing_168h` | 19.7% | 0.783 |
| `realized_volatility_trailing_24h` | **not directly tested** — used as the power run's proxy-target stand-in (§11 of the prerequisites result); its own lag-1 autocorrelation as observed in that role was 0.622, closer to the two weak candidates than the five strong ones | 0.622 (as proxy target) |

## 3. Universe (unchanged from the tested design)

BTC, ETH, SPY, QQQ, GLD — the same 5 real OHLCV sources the operator ran §2's power test against.
Native bar cadence inferred per asset exactly as `scripts/run_campaign58_phase1_power_analysis.py`
already does (median inter-row gap in hours); hour-denominated windows below convert to bar
counts per asset the same way. No sixth asset, no substitute asset, no subset — all 5 or the
grid is not this grid.

## 4. Base feature families (unchanged — Campaign #48's own 8, not 7)

The power test in §2 used 7 of Campaign #48's 8 original predictors (the 8th,
`realized_volatility_trailing_24h`, was reserved as that test's proxy-target stand-in and was
never itself tested as a candidate). This specification restores the full 8, because in a real
run there is a genuine forward-looking target (§7) — the "proxy target" expedient was specific to
power calibration and does not apply here:

1. `return_trailing_24h`
2. `return_trailing_72h`
3. `return_trailing_168h`
4. `realized_volatility_trailing_24h`
5. `realized_volatility_trailing_168h`
6. `distance_from_mean_trailing_168h`
7. `range_position_trailing_168h`
8. `drawdown_from_high_trailing_168h`

Formulas are Campaign #48's own (`docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES.md`),
with hour-windows converted to bar counts per asset exactly as
`scripts/run_campaign58_phase1_power_analysis.py` already implements. No new feature family, no
interaction term, no combined multivariate model — every model in §8 is fit on exactly one
feature at a time, matching Campaign #48's own "no interactions" convention.

**Flagged, not concealed:** `realized_volatility_trailing_24h`'s own power was never measured
(§2). Its close resemblance, in the proxy-target role, to the two weakest tested candidates
(autocorrelation 0.622, between `drawdown` at 0.331 and `realized_volatility_trailing_168h` at
0.783) is used in §10 to place it under the same cautious interpretation rule as the two directly
measured weak candidates, rather than assumed adequately powered by default.

## 5. Raw and residualized variants (doubles §4 to 16 feature-variants)

Every one of the 8 base features enters the grid twice: **raw** (as computed in §4) and
**residualized** against known Itera signals (§9). This is the campaign's actual novel content —
"residual predictability after known signals are removed" is the question in the charter's own
title, not something added in reaction to the power result.

**Correction — independent Red Team review:** the preceding sentence stated this connection with
more confidence than the charter's actual text supports. The charter's Quant Research design
(Part 2) describes residualization as a step to apply, not unambiguously a parallel raw-vs-
residual comparison axis — a narrower reading (test residualized values only, since raw
predictability was already Campaign #48's job) is equally defensible and was not previously
acknowledged as an alternative. The raw/residual doubling adopted here is one reasonable
interpretation of the charter, chosen because it lets the grid report both "is there raw
predictability" and "is there anything left after removing known signal" side by side (the
research map the charter's own deliverable section asks for), not because it is the only
available reading. Recorded plainly rather than asserted as unambiguous.

## 6. Target families (Campaign #48's own R/M/V, unchanged)

At each horizon `h` in `{24, 72, 168}` (hours, converted to bars per asset exactly as §4):

- **Family R** (directional): `forward_return_h = ln(C_{t+h} / C_t)`
- **Family M** (magnitude): `forward_absolute_return_h = abs(forward_return_h)`
- **Family V** (volatility): `forward_realized_volatility_h = sqrt(sum(r_u^2))` over the `h`
  forward bars

Identical formulas to Campaign #48, extended to each of the 5 assets using their own native
cadence. No new target family, no binary/classification recoding — all three targets are
continuous, matching Campaign #48's own choice not to create a "separate binary up/down label."

## 7. Candidate grid and FDR family structure (Red Team condition 1)

**16 feature-variants × 3 horizons = 48 candidates per outcome family; 3 outcome families (R, M,
V) = 144 total candidates.** Under the 150 cap. Benjamini-Hochberg FDR is applied **separately
within each of the 3 outcome families** (48 candidates each), exactly matching Campaign #48's own
per-family application, not pooled across R/M/V.

This mirrors Campaign #48's 8×3×3=72 structure exactly, doubled only by the raw/residual axis —
not a new structural choice invented after seeing §2's power profile. The grid was going to have
this shape (raw × residual × R/M/V × 3 horizons) regardless of which specific base features
turned out strong or weak; only the base features and their measured power are new information
from §2, and neither changes the grid's shape or the base feature list (§3 above).

## 8. Model types per candidate (naive, simple, and constrained-ML groups)

Every candidate is fit with all six model types, on the **identical** chronological folds and
target definition (§11) — no model type sees a different fold split or a different target than
any other model type for the same candidate:

**Baselines:**

| Model | Definition |
|---|---|
| Naive / unconditional | Predicts the development-partition's own mean target value, ignoring the feature entirely — the floor every other model must clear to be worth reporting at all |
| Simple linear (continuous targets) | `LinearRegression()`, one standardized feature, intercept, no interactions — Campaign #48's own estimator choice for association testing, generalized from OLS+HC3 to plain OLS for a fair train/test comparison against the ML models below (HC3 inference is retained separately for the discovery test in §9's residual-association step, not for the OOS comparison) |

**Constrained ML (Red Team-authorized set only — no neural networks, no hyperparameter search
beyond the single fixed configuration per type):**

| Model | Fixed configuration (unchanged from the prerequisites result, §6 of that document) |
|---|---|
| Ridge | `Ridge(alpha=1.0, random_state=42)` |
| Elastic net | `ElasticNet(alpha=1.0, l1_ratio=0.5, random_state=42)` |
| Shallow random forest | `RandomForestRegressor(n_estimators=100, max_depth=4, min_samples_leaf=20, random_state=42)` |
| Shallow gradient boosting | `GradientBoostingRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)` |

(Regressor variants named explicitly here since all three target families are continuous —
the classifier variants named in the prerequisites result were written generically for a
classification target that this specification does not use.)

Any deviation from these exact configurations in the real run is a new candidate, charged
against the same 48-candidate family it would join.

## 9. Residualization (strictly causal, expanding/walk-forward)

For the **residualized** variant of each base feature (§5), a first-stage model is fit to remove
already-known Itera signal before the feature enters any candidate test:

- **Known-signal inputs:** trailing momentum (the feature's own asset's `return_trailing_24h`,
  always in raw form, as the momentum control), realized volatility (`realized_volatility_trailing_24h`,
  raw), Itera's deterministic regime state (§10 below — one-hot or ordinal encoding of
  `BaselineRegimeEngine.classify_bar`'s output label, nothing else), and Core v1's own SMA175
  trend state (sign of price relative to the frozen SMA175, the same rule Core v1 itself trades
  on, read-only).
- **Explicitly excluded from known-signal inputs:** any not-yet-holdout-confirmed discovery
  candidate — Campaign #53's `funding_level_72h`/`funding_persistence` (FDR-discovery-stage
  only, holdout not cleared), Campaign #57's month-end rebalance signal (VTI/BND confirmation
  not yet run), or any other unconfirmed campaign result. Using an unvalidated signal as a
  "known" control would let unvalidated research quietly anchor this census.
- **Fit procedure:** for each asset independently, an expanding-window OLS regresses the raw
  feature on the known-signal inputs using only rows strictly before the current row (the exact
  clean pipeline proven in the leakage canary, §10 below) — never a full-sample fit. The
  residual is the raw feature minus this causal fitted value. A fixed warmup (matching Campaign
  #48's own support-gate convention: at least 90 candidate-complete pooled rows, at least 25 per
  chronological partition) applies before any residualized value is defined for a row.
- **Pre-flight requirement before any real residual is computed:** the leakage canary (§10) must
  be re-run and must reproduce its proven result (near-zero first-half correlation under the
  clean pipeline, clear detection under a deliberately leaky one) using the SAME code path this
  specification's real residualization will use — not merely cited as previously proven on a
  different, standalone synthetic script. This closes the gap between "the concept is proven"
  and "this specific implementation is proven."

## 10. Regime-state source and leakage canary (Red Team conditions 3 and 4, restated as binding)

- **Regime-state source:** `research/regimes/baseline_engine.py`'s `BaselineRegimeEngine.classify_bar`
  (or `classify_dataframe`, which calls it per-row) — verified causal by direct inspection
  (`df.iloc[:bar_idx+1]` before any indicator computation). **Explicitly prohibited:** any tool
  under `research/ml/validation/historical_regime_*` — full-sample offline discovery tools, not
  per-bar causal signals. Using one as a control here is a stop condition, not a style choice.
- **Leakage canary:** proven capable of failing on synthetic data
  (`scripts/prove_campaign58_residualization_leakage_canary.py`; clean pipeline 0.0064 first-half
  leak-correlation, leaky pipeline 0.6923, clearly detected). §9 requires this proof to be
  re-demonstrated against the real implementation's own code path before any real residual is
  computed — the existing proof establishes the METHOD works, not that the real implementation
  faithfully uses it.

## 11. Chronological folds (identical across every model type, Campaign #48's own convention)

For each asset independently: 3 contiguous, near-equal chronological partitions of that asset's
candidate-complete anchors (not random split, not shuffle, not cross-sectional fold, not
bootstrap split). Partition 1 develops partition 2's evaluation; partitions 1+2 develop partition
3's evaluation; all candidate-complete rows form the pooled fit — exactly Campaign #48's own
three-tier structure. Pooling across the 5 assets happens **after** each asset's own partitions
are assigned (partition-1 rows from all 5 assets together form the pooled partition-1 sample,
etc.) — the same per-asset-then-pool structure already used and proven in §2's grouped block
bootstrap, so folds and the power test's own resampling units are structurally consistent with
each other.

Every one of the 6 model types in §8 is fit and evaluated on these **identical** partitions for a
given candidate — no model type gets its own fold split.

## 12. Decision rules — frozen before any real result exists

### 12a. Discovery (does the raw or residualized feature associate with the target at all)

For each of the 144 candidates, the **best-performing** of the 6 models (by partition-3
out-of-sample R²) is used to determine whether the candidate clears family-wise BH-FDR at
`q=0.10` (matching Campaign #53's own threshold) within its 48-candidate outcome family (§7), and
whether its association direction is consistent across the pooled fit and both partition-2 and
partition-3 evaluations (directional consistency, Campaign #48's own convention).

**Correction — independent Red Team review (condition 5):** selecting the best of 6 models per
candidate is itself a source of multiplicity beyond the between-candidate FDR correction above,
and this was previously unaddressed. It is corrected the same way as 12b's own selection
multiplicity below (§12b's amended condition 2): **the empirical null reference each candidate's
p-value is measured against (§2's `build_null_reference`-style construction) must itself apply
the identical best-of-6-models selection at every null resample**, not compare a real best-of-6
statistic against a null built from a single fixed model. This makes the comparison like-for-like
— the selection procedure is baked symmetrically into both the real statistic and its null
reference, rather than only inflating the real side. No additional FDR correction factor is
applied for the model-selection step itself; matching the null construction to the real
procedure is the correction.

### 12b. Does ML materially beat simple (the campaign's actual research question)

For any candidate that clears 12a, compare the **best constrained-ML model's** partition-3 OOS R²
against the **best of {naive, simple linear}'s** partition-3 OOS R². ML "wins" for that candidate
only if **all** of the following hold:

1. **Material margin — corrected, independent Red Team review (condition 3):** the original
   `0.02` absolute figure was untested and had no derivation; at the census's own central IC
   (0.065), the implied effect size is R² ≈ IC² ≈ `0.0042` — the 0.02 figure was roughly 5× that,
   an unjustified and effectively near-unfalsifiable bar. **Corrected margin: the ML model's OOS
   R² must exceed the best baseline's OOS R² by at least `0.0042` (= the central-IC-implied R²,
   rounded to no fewer significant figures than the IC itself carries) — i.e., ML must add at
   least one central-effect-size unit of incremental information beyond what the simple baseline
   already captures.** This ties the materiality bar to the same yardstick the power analysis
   itself is calibrated against, rather than an arbitrary round number, and is still a
   deliberately non-trivial bar (a real, whole additional unit of the census's own assumed
   effect, not a fraction of one) consistent with the charter's instruction that ML must be
   "materially better, not merely numerically higher."
2. **Survives family-wise FDR on the lift itself:** the ML-vs-baseline R² improvement, treated as
   its own 48-candidate-family test (one p-value per candidate, from a block-bootstrap null of
   the lift itself, block size 8 anchors matching §2), clears BH-FDR at `q=0.10` within the same
   outcome family. **Correction (condition 4):** the null reference for this test must be
   constructed by re-running the **full best-of-4-ML/best-of-2-baseline selection** at each null
   resample (matching 12a's own correction above) — not by fixing the model choice selected on
   real data and only resampling that one pair's difference, which would understate the true
   null variability of the actual "pick best of 4, pick best of 2" statistic used on real data.
3. **Survives the negative/permutation control — corrected, independent Red Team review
   (condition 4):** the best ML model is re-fit against a block-permuted target (target values
   shuffled in contiguous 8-anchor blocks per asset, preserving each asset's own within-block
   structure, ≥100 permutation resamples) on the identical folds and feature. **At each
   permutation resample, the full best-of-4-ML/best-of-2-baseline selection is re-run on the
   permuted data — the model choice is not fixed from the real run.** The real lift must exceed
   the 95th percentile of this permutation-null lift distribution. A candidate whose real lift
   does not clear this bar is **not** counted as an ML win regardless of 1-2, since a lift that
   beats simple baselines even on a permuted (informationless) target is a model/infrastructure
   artifact, not signal. **Flagged asymmetry (independent Red Team review):** 8-anchor block
   permutation is more reliable at destroying spurious lift for **residualized** variants (which
   have had slow macro/regime drift explicitly removed) than for **raw** variants, where a raw
   feature and a raw target sharing a slow multi-year macro co-movement could retain some
   spurious block-permuted "lift" that this granularity does not fully eliminate. Any raw-variant
   candidate that clears 12b.3 narrowly (real lift only modestly above the permutation-null 95th
   percentile) should be reported with this caveat attached, not treated as equivalent-strength
   evidence to a residualized-variant candidate clearing the same bar by the same margin.
4. **Fold-stable:** the sign of the ML-vs-baseline lift is the same in both the partition-2 and
   partition-3 evaluations independently, not only in the pooled fit — a lift driven by one
   partition alone does not count.

### 12c. Explicit treatment of uneven power (binding interpretation rule, not a footnote)

Any candidate whose **base feature** is one of the three flagged in §2 as inadequately powered —
`realized_volatility_trailing_168h` (19.7% measured), `drawdown_from_high_trailing_168h` (31.7%
measured), or `realized_volatility_trailing_24h` (never directly measured, presumptively weak per
§4) — is classified `UNDERPOWERED_INCONCLUSIVE` if it fails 12a or 12b, **not** counted as
evidence toward `ML_COMPLEXITY_NOT_JUSTIFIED` and not counted as a clean null. This applies
identically to that feature's raw and residualized variants, across all three horizons and all
three outcome families — 3 features × 2 variants × 3 horizons × 3 outcomes = 54 of the 144
candidates carry this flag from the start, before any real result is seen. A pass under 12a/12b
from one of these candidates is still a real, reportable discovery — the flag only constrains how
a **negative** result on these specific candidates may be interpreted, per the same discipline
CLAUDE.md's own retirement notes for Jump Risk and Trend Persistence apply to distinguishing "not
reachable given real constraints" from "disproven."

**Correction — independent Red Team review (condition 6):** this list of three features is
**closed**. No feature may be added to it after seeing any real result, on any rationale, without
a new Red-Team-reviewed amendment to this specification recorded as a dated correction to this
document — the same discipline that applies to every other frozen element here. This exists
specifically to prevent an inconvenient future null on an adequately-powered feature from being
relabeled "underpowered" after the fact.

The remaining 90 candidates (5 adequately-powered base features × 2 variants × 3 horizons × 3
outcomes) may have their null results counted as genuine evidence toward the overall verdict.

**Correction — independent Red Team review (condition 7):** the preceding sentence is
**conditional, not unconditional**, on §13 item 1's outstanding grid-level power verification —
covering all three outcome families per the §14 correction below — actually confirming these 90
candidates individually clear 50% power at the true 48-candidate-family FDR stringency, using
real (not proxy) targets. The 58.3%-average, unevenly-distributed result these 90 candidates'
"adequately powered" label currently rests on was measured at a 7-candidate family with a proxy
target, not at this specification's true scale. Until that check is done, treat the 90-candidate
set as **provisionally** adequately powered, not confirmed.

### 12d. Orthogonality check on any supported candidate (charter Part 2, Risk/PM — reinstated)

**Correction — independent Red Team review (condition 8):** the charter's own Risk/PM condition
was absent from this specification's decision rules and is reinstated here rather than left
dropped. Any candidate that clears 12a and 12b must additionally be checked, before it is
described anywhere as "residual," "orthogonal," or "independent information," for realized
correlation between that candidate's own real feature series (raw or residualized, whichever
variant cleared) and Core v1's own real NAV series over the same real evaluation window. This is
a simple, deterministic, observation-only check — it makes no capital or sizing claim — and its
result is reported alongside any supported candidate, not deferred to a later Risk/PM gate.
"Residualized against known signals" is necessary but not sufficient for orthogonality: a feature
can be uncorrelated with Core's signals today while still being a noisier proxy for Core's beta.

### 12e. Campaign verdict

**`ML_COMPLEXITY_NOT_JUSTIFIED`** if none of the 90 adequately-powered candidates clears 12b. This
is the pre-registered default outcome, not a fallback — this fund's only two completed fitted-ML
programs (Jump Risk, Trend Persistence) never showed constrained ML categorically beating simple
models on the same target, and this design is built to test whether that pattern holds, not to be
surprised if it does.

A supported result (any candidate clearing 12a and 12b, among the 90 adequately-powered
candidates) is a research finding only. It authorizes no strategy, no threshold, no Core v1/v2
comparison, and no advance past this campaign's own scope — any such candidate must separately
clear the standard charter-campaign Gates 0-4 before it is trading-relevant, exactly as this
campaign's planning charter already states.

## 13. What remains before real execution (stated plainly, not glossed over)

1. **Grid-level power verification, not yet run at full scope.** §2's power result covers a
   7-candidate, Family-R-only family; this specification's actual FDR families are 48 candidates
   each, across three outcome families (R, M, V). BH-FDR's threshold tightens as family size
   grows for a fixed single injected effect, so this specification's own power at the frozen
   central IC (0.065) has **not** been demonstrated at its true scale and must be checked — using
   the identical assets, central IC, and block size already frozen — before real predictor/
   outcome computation is responsible. Companion script
   `scripts/run_campaign58_grid_power_analysis.py` (corrected filename; built alongside this
   specification) is ready for the operator to run locally for this purpose; see §14.
   **Correction — independent Red Team review (condition 2):** the script as first built covered
   Family R only, on the reasoning that Campaign #48 found no directional association there
   (implying it's the "hardest" family). The review correctly identified this as conflating
   whether a true effect exists (irrelevant to injected-IC power calibration) with how
   autocorrelated a series is (what actually drives this methodology's power) — if forward
   volatility/magnitude targets are as persistent as this fund's own price-state features
   already measured are, Family M/V power could be *lower* than Family R's, meaning an R-only
   result could **overstate**, not lower-bound, the real grid's power. The script (§14) is
   updated to simulate all three outcome families; a Family-R-only result no longer satisfies
   this item.
2. **Residualization re-proof against the real implementation's own code**, per §9's own
   requirement, not yet done.
3. **The §12b material-margin recalibration's own power has not been independently verified** —
   it is now tied to the census's own central-IC-implied effect size rather than an arbitrary
   number, but no power simulation has tested how often a real material-margin-clearing effect
   of that size would actually be detected under 12b's full four-part test. Not a blocker to
   freezing the specification's design, but a real, undone check before any real result from
   12b is treated as conclusive.
4. **A new, explicit CEO authorization for real predictor/outcome computation and model
   fitting** — the standing 2026-09-03 authorization covered specification-freeze work only and
   explicitly excluded "fitting real ML models against real predictor/outcome data" and
   "predictor/outcome computation for a Campaign #58 decision." This specification does not
   change that; it is a design document, not an execution authorization.
5. **Independent Red Team review of this specification itself** — complete.
   `docs/research/CAMPAIGN_58_PHASE1_SPEC_INDEPENDENT_RED_TEAM_REVIEW.md`, `CONDITIONAL_PASS`,
   ten conditions, all applied in this document as dated corrections.

## 14. Companion tool for item 1 (built, updated per independent Red Team review, not yet run for real)

`scripts/run_campaign58_grid_power_analysis.py` extends the already-proven block-bootstrap
methodology (§2) to simulate power at this specification's actual 48-candidate-per-family scale,
**across all three outcome families (R, M, V)**, using the same real multi-asset data the
operator already has locally. It is a power/methodology calibration tool only — like §2's own
script, it does not compute any real predictor/outcome value or fit any real model against real
data; it estimates whether the frozen gates (§12) would detect a real effect of the central
assumed size, at the family size and scope this specification actually freezes.

**Correction — independent Red Team review (condition 9):** the script's own resample-adequacy
check is strengthened. Its own smoke test produced `min_trials_per_hypothesis: 0` and degenerate
0.0/1.0 per-hypothesis power estimates at a low `--n-power-total` — a real run must use a budget
large enough that every hypothesis receives a meaningful number of trials, and the script must
refuse to report a clean PASS/FAIL headline if any hypothesis's trial count falls below a stated
floor, rather than silently averaging over unreliable per-hypothesis estimates.
