# Research-program review — 2026-09-11

Decision: **revise the forecast-to-decision experiment before further model or data search**. Retain the existing negative records. No candidate is eligible for promotion. The review identifies an actual holding-horizon mismatch and restrictive policy design, but finds no evidence that a single broken estimator explains all weak results. A correction is not a promise of profit.

Reviewed repository commit: `34750bc6613988375835e7b6a24b0a4357989372`. Applied the senior-quant-researcher skill. This is a focused review of the ML Lab baseline evidence, ETF development/design/incremental code and records, energy/crop feasibility records, and options preparation/forecast/sizing code and evidence. It is not a full audit of Core, every historical campaign, all raw data, or production execution. No new model fits, strategy backtests, threshold searches, data downloads, or holdout use occurred.

## What survives review

| Research line | Evidence | Defensible conclusion and decision |
|---|---|---|
| Lab 005–013 | Post-012 review and 013 closeout; ranking target implementation inspected | Ridge ranks a volatility-normalized target with positive average IC; it does not establish a net-return strategy. Keep the baseline-increment failure. |
| Three-ETF development | Saved result and corrected development record | Initial neural optimization hit its cap; initial invalid split was corrected and segregated. The early run cannot settle architecture quality. |
| Eight-ETF development/design audit | Breadth and design-audit fitting code, saved metrics and synthetic record | Strong planted linear signal recovery already exists. Rank-target and stopping changes were already tested. Historical means remain a strong control; full-period forecast gains concentrate in 2020. No universal verdict on neural networks. |
| Incremental information | Current fitting, calibration, gating, scheduling, accounting; original review ZIP | Small aggregate forecast gains are unstable. Neither calibrated model meets the stated rules. This supports rejecting these specifications under these rules, not absence of all conditional information. |
| Energy and crops | Feasibility documents and JSON records | Energy stopped before an actual fitted predictive test. Crop learning report explicitly records zero actual-label model fits; its power results are synthetic. These are feasibility findings, not negative market experiments. |
| Dealer geometry/options | Correction document, current preparation/forecast code, dated predictions | Dealer-inventory interpretation and old timing/permutation design are not supported. Corrected augmented model did not pass. Near IV improves the two fitted price-only forecasts descriptively; smaller incremental effects remain unresolved. |
| IV allocation | Sizing code, report, tests | A raw-IV inverse-volatility policy underperformed the RV policy. No fitted ML forecast enters this sizing runner. Retain this policy failure; do not describe it as a general failure to monetize ML or IV. |

The available library of datasets has not been exhaustively tested. File inventory size, repeated exports, and multiple correlated assets are not independent evidence of learnable trading opportunities. This review does not certify every local dataset or select a new one based on filename counts.

## Findings ordered by decision impact

### 1. The ETF forecast horizon and rebalance interval do not consistently match

`research/ml_development/breadth.py::build_panel` labels `open[t+6]/open[t+1]-1`: five trading sessions. `scripts/run_ml_etf_risk_screen.py::weekly_sessions` chooses the last supplied trading session of each calendar week. `portfolio.py::ledger` trades the following session and updates at the next weekly signal's following session.

Using the original incremental forecast dates against the supplied SPY calendar, 64 of 363 consecutive decision intervals are four sessions; 299 are five. Thus approximately 17.6% of intervals can replace the exposure one session before the forecast label matures. Training-label purging is a separate issue and passes the reviewed boundary checks. The ledger is internally consistent; the forecast and decision describe different holding periods on holiday weeks.

Severity: a fixable economic-design defect, not discovered lookahead or evidence of fabricated P&L. Its performance impact has not been measured. It does not invalidate the separately reported five-session forecast-error calculations, and cannot explain every negative research line.

### 2. The cost gate tests an unusually restrictive policy, not marginal trading value

`incremental.py::gated` requires expected five-session excess return above `4*cost`, then assigns up to three 25% risky slots. At 10bp per leg, the hurdle is 40bp. This is arithmetically consistent with the stated complete SPY/BIL-style round trip. However, the function takes no current holdings. The same hurdle applies to buying, retaining, and exiting an asset. Retaining an unchanged position has no immediate turnover cost; selling it incurs costs. The rule can therefore liquidate a mildly positive expected-return holding even when retaining it is preferable after marginal costs.

This limitation was already disclosed in the result document. It is not a newly discovered accounting bug. The reviewed policy spends most signal dates in BIL, and the gated historical-mean control is also largely disabled. At 25bp, the 100bp hurdle changes trades as well as fees, so that scenario is not pure cost sensitivity. The earlier ungated top-three rule has the opposite problem: it mechanically imposes a risky budget and can create turnover from tiny ranking changes.

Neither rule optimizes the stated certainty-equivalent objective. A coherent single-period approximation would select weights using `mu' w - (gamma/2) w' Sigma w - C(w-w_current)` under the agreed constraints, with return horizon, covariance horizon, costs, and execution aligned. This is a mathematical description of a decision objective, not evidence that such an optimizer would improve observed performance. Forecast error can make it worse; mean-only and no-change controls must use identical construction.

### 3. The IV economic test does not evaluate the fitted forecasting models

`run_ml_iv_sizing.py::load_data` uses `iv_near` and `sqrt(252*rv_21)`. It does not load `ML_OPTIONS_VARIANCE_OOS_20260911.csv`. Its weights are clipped inverse-volatility weights with scalars calibrated before 2018. All three strategies match 10% training volatility; evaluation volatility differs substantially.

A target-volatility rule and a return-minus-variance objective are distinct. For a single risky asset with deterministic cash and no costs, maximizing `w*mu - gamma*w*w*v/2` gives `w=mu/(gamma*v)` subject to constraints, whereas constant target volatility gives `w=k/sqrt(v)`. Neither is universally preferable. This derivation shows why a forecasting improvement need not improve the chosen sizing rule or its CE score.

Raw IV was the best observed QLIKE benchmark, making a raw-IV sizing diagnostic reasonable. But the policy failure does not test every fitted forecast, the full trading chain, or option trading. It also uses a different eligibility rule: IV/RV availability, whereas the variance comparison requires complete augmented-feature anchors. The record is not a controlled end-to-end attribution of forecast gain to portfolio gain. SPY adjustment provenance remains conditional; hash equality does not certify total-return semantics.

### 4. A general inability to learn is contradicted by work already completed

`design_audit.py::synthetic` runs the production fitting/stopping path against a strong planted linear relationship and shuffled training labels. The saved record reports 99.23%, 97.46%, and 99.13% error reductions for Ridge, GBM, and MLP on the planted case. The incremental test also checks residual-signal recovery and validation-label mutation. These are strong-signal mechanics checks, not realistic small-edge power or an end-to-end economic recovery test.

The rank-target audit and earlier neural-checkpoint audit also already exist. Recommending those again as a fresh reset was an error in maintaining research continuity. The sequence models inspected are small MLPs over flattened lag inputs; this work is not a comprehensive test of representation learning, sequence architectures, or neural networks generally. Conversely, choosing a larger architecture is not justified by these findings alone.

### 5. Positive findings were narrow, and rejection labels compressed different outcomes

The 013 closeout reports trailing-three-year Ridge normalized-target IC 0.05767 versus low-volatility IC 0.08031. On the unscaled forward-return numerator those ICs are 0.00927 and 0.00063. The target is explicitly volatility-normalized in `cross_sectional_v1.py`; a normalized-target spread is not a return spread. These figures do not prove the denominator caused all apparent predictability, but show why early positive scores did not establish a trading opportunity.

In the incremental study, independently recomputed raw Ridge MSE skill is about +1.03% overall and −1.03% excluding 2020; calibrated Ridge about +0.53% and −1.27%. Static GBM can beat its time-varying version. Excluding 2020 is a useful concentration diagnostic, not a universal requirement: a credible crisis-specific hypothesis could legitimately depend on crises. Here no separately specified crisis claim or independent evidence has been established.

Near IV's 15.0%/20.6% QLIKE improvements in the two fitted comparisons are actual exploratory positives. Crop sensitivities are not actual negatives. Portfolio profits versus BIL or passive exposure, predictive improvement, scientific structure, and readiness for capital are separate decisions. Keep those distinctions in the research ledger rather than aggregating every non-promotion into “ML failed.”

### 6. Fixed gates and reproducibility do not establish a well-chosen objective

The IV sizing joint threshold combines 0.5pp CE improvement, a positive block lower bound, year wins, volatility and drawdown constraints; the report acknowledges economic power was not calibrated. The crop power report is conditional on its injected DGP and amplitude, not measured market effect plausibility. It is reasonable to refuse strong null claims from weak tests. It is not reasonable to treat feasibility stops as proof that no signal exists.

The same 2018–2024 development period has repeatedly informed redesign. Chronological folds are necessary but cannot erase that selection history. Dealer work already inspected 2025, so “2025 untouched” cannot be a global claim across the research program. Current runners excluding 2025 are a narrower, verifiable statement. No additional date range was opened in this review.

## Verification actually performed

A new read-only audit runner, `scripts/research_probes/review_ml_evidence_20260911.py`, verified all seven recorded incremental CSV hashes in the original package; independently recomputed pooled MSE for all seven forecasts on full/excluding-2020 scopes (maximum delta zero); checked 42 recorded fit boundaries; reconciled compounded NAV and annual CE for all 30 saved ledgers (maximum CE difference 6.94e-18); counted the calendar/horizon mismatch; and verified the saved options prediction hash and independently recalculated all eight mean QLIKE metrics (maximum delta zero). Results: `ML_RESEARCH_REVIEW_CHECKS_20260911.json`.

Twelve existing options/sizing unittest tests were rerun and passed. A broader pytest invocation could not start because pytest is absent from the current runtime; it is not reported as passing. No new dependencies were installed, no old models independently refitted, and no full raw-options-chain/vendor audit performed. Earlier test counts in result documents remain historical reports, not new executions in this review.

## One next action and a stopping rule

**Prepare a bounded corrected decision-layer experiment using the existing eight-ETF data and the same two residual predictors.** The named deficiency is the mismatch between a five-session forecast and its decision, plus a cost rule that ignores existing holdings. The purpose is to determine whether the decision layer materially changes the conclusion, not to restart alpha discovery or search until profitable.

Before any new fit, make the decision contract executable on synthetic cases: use every-fifth-session decisions so the existing five-session training label exactly matches the scheduled holding period; apply next-session-open execution; use current drifted holdings and marginal trading costs in one fixed constrained objective. Keep historical-mean and equal-weight controls, add a no-change control, and retain the existing fixed-gate mapping as an ablation on the new common schedule. Keep raw and calibrated forecasts visible. Freeze the risk-aversion and cost scenarios in the revised record; they are research assumptions, not operator preferences inferred from past simulations. Demonstrate that no-change has zero turnover, that enough forecast advantage causes a trade, and that future-label mutation cannot change an earlier action.

Only then repeat the same bounded two-model annual protocol on the aligned schedule, with no new features, model classes, hyperparameter search, seed selection, or 2025 access. Because schedule and decision changes are consequential, record a new exploratory revision and compare all policies on the same observations. Do not silently replace the old files or call the revision independent confirmation. This review does not execute that experiment.

Success would justify investigating the resulting decision effect further; it would not validate a new alpha source or capital use. If the corrected decision layer still does not improve on identically constructed historical-mean/no-change controls after costs, close this daily-summary/five-session ETF allocation line. Do not return to another architecture sweep on this dataset. That is a finite diagnostic with a specific failure to repair, not an open-ended promise to find an edge.
