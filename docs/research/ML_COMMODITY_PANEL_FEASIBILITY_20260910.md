# Broadened physical-fundamentals design — 2026-09-10

Status: AUTHORIZED_DESIGN_EXPANSION; SOURCE_SAMPLE_AVAILABLE; CROP_PRICES_PENDING.
User authorized broadening the design after the single-USO power review. This is a new exploratory design, not a frozen campaign or a claim that additional assets automatically solve power. No model fits or feature/return correlations have been calculated.

## Scope chosen before crop returns

Add corn/CORN, wheat/WEAT and soybeans/SOYB to the feasibility work. Retain crude/USO as a separate energy family. Use BIL as cash comparator. No price substitution with continuous Yahoo futures symbols. No 2025 outcomes. No subscriptions.

Lead new hypothesis: reductions in expected crop availability relative to expected use carry information about the corresponding fund's next 21-session excess return beyond historical mean, seasonality and price-only controls. Stocks/use levels and revisions are distinct predictors. Direction and usefulness remain hypotheses. Revision is not market-consensus surprise. The full-session information delay and 21-session target are retained. Costs and attainable trading sizes must be checked using actual fund liquidity; commodity funds include futures roll and collateral effects.

Crops receive priority because the same official report supplies consistent economic categories across three markets. Crude remains separately specified; do not equate measured oil inventory levels with projected crop ending stocks or concatenate them as interchangeable features. Natural gas is deferred: this session's request to https://ir.eia.gov/ngs/ returned 403, and historical vintage access was not established. No access-control workaround attempted.

## Verified sources, and their limits

USDA ESMIS WASDE publication page describes monthly forecasts of supply and use. The last archive page lists September 17, 1973. January 12, 2024 links a readable text report containing distinct crop-year estimates, current projections, previous/current month columns, units and stock/use fields. These checks establish a promising archive, not complete historical coverage. Some oldest reports are PDF only. Long fundamentals history cannot create tradable fund history before inception.

Teucrium sponsor pages verify CORN, WEAT and SOYB offer futures-based exposure to their corresponding crops. Their currently described contract baskets are not evidence of unchanged historical mandates. Brokerage eligibility, historical fund changes, splits, liquidity and costs remain to be validated. The uploaded local inventory has no matching CORN, WEAT, SOYB or UNG filename rows.

## Construction decisions

1. Acquire release-index metadata and raw reports for a bounded 2005–2024 source window. Preserve actual publication dates, raw hashes, units, commodity, geography, crop year and estimate/projection status. Sample old/middle/recent formats before bulk parsing. Do not infer release dates from month names or overwrite old releases with revised modern datasets.
2. For each commodity, extract U.S. ending stocks and total use from the commodity-specific balance sheet. Total use must include the components specified by that table; do not mix domestic consumption with world total use. Validate accounting and denominators. Global quantities can be a separately named later feature, not silently substituted.
3. Choose the marketing-year projection using a documented report-calendar rule. At new-crop introduction, never subtract new-crop estimates from the previous old-crop year. Revisions require the same commodity, geography, units and crop year across two actual releases. Mark absent matching prior estimates missing.
4. Use earlier reports for seasonal normalization and crop-cycle controls, potentially avoiding loss of five tradable years. Do not simply remove the oil warm-up requirement. Training transformations remain fold-local. Confirm historical table availability before claiming this benefit.
5. Entry is the opening after one complete exchange session strictly after publication date. Exit 21 sessions later; labels ending in 2025 are excluded. All assets from a release stay together in calendar folds. Purge overlapping labels.
6. Compare training-only asset means, seasonality/price controls, a prespecified simple revision rule and a small pooled regularized model. A shared crop coefficient is an assumption to test with leave-one-crop-out diagnostics; asset intercepts cannot substitute for changing information. No neural network or wide parameter search is justified yet.
7. Before fitting, simulate power under plausible incremental effects and observed joint return dependence, using calendar blocks and full cross-asset vectors. Include the actual train/test split, common release shocks, missingness, costs and decision rule. Simulate the no-edge case to check false-positive rates. Do not use observed favorable feature/return correlation to choose the assumed effect size. Report sensitivity rather than a single artificial effective-sample count.
8. Keep time-held-out comparisons primary; leave-one-crop-out is a transfer diagnostic, not independent confirmation. Reserve the strict confirmation design for a later charter review. Existing 2025 reservation and Core freeze remain unchanged.

## Correction to the prior power framing

The prior 96-month calculation was a rough scenario, not a measured effective sample size or proof of infeasibility. A pooled panel can help if commodity-specific variation is informative. Strong shared shocks can eliminate much of that gain. Neither multiplying asset count by month count nor shortening labels solely to increase observations is acceptable.

## Next local input

Run DOWNLOAD_ML_CROP_PRICES.ps1. It uses the existing downloader and creates a new dated ZIP for adjusted CORN, WEAT and SOYB from their available history through 2024. Existing USO/BIL uploads are retained. After receipt: price/liquidity audit, historical WASDE extraction pilot, joint-dependence power simulation, then a concrete experiment charter only if feasible. No need to switch or merge the user's working checkout.

## Sources checked

- https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates
- https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates?page=70
- https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates?page=3
- https://esmis.nal.usda.gov/sites/default/release-files/3t945q76s/m613pj64v/n296zk13z/wasde0124.txt
- https://teucrium.com/corn
- https://teucrium.com/weat
- https://teucrium.com/soyb

## Crop upload and source audit update — 2026-09-10

Current status supersedes the earlier pending-price status: CROP_PRICES_RECEIVED; XML_EXTRACTION_PILOT_COMPLETE; TRADEABILITY_AND_FULL_POWER_UNRESOLVED. No predictive model has been fitted. The price-only correlation diagnostic and synthetic known-signal planning exercise below are not feature/return discovery or evidence for a profitable strategy.

The uploaded `ml_crop_prices_20260910_104514.zip` contains adjusted CORN, WEAT and SOYB daily prices and request manifests. All stop at 2024-12-31 and pass duplicate-date, finite-value, positive-price and OHLC consistency checks. CORN has 3,666 rows beginning 2010-06-09; WEAT and SOYB each have 3,343 beginning 2011-09-19. WEAT has seven zero-volume sessions and SOYB nineteen, concentrated in early history. Retain these records but never assume an executable fill on a zero-volume session. Historical adjusted price times reported volume is not an established historical dollar-liquidity measure without adjustment-factor validation. Spread and execution-cost data remain absent.

### Source coverage and fail-closed extraction

The 2005–2024 archive index contains 249 entries across formats, including announcements, supplements and multiple versions. It is not 249 independent forecast releases. There are 175 XML entries, all now downloaded with URL, byte count and SHA-256 preserved. The XML collection begins July 2010; older text/PDF availability does not mean the extraction pilot covers 2005 onward. Earlier text samples were inspected but no complete text parser is claimed.

The pilot accepts 172 XML files, yielding 6,192 selected cells from October 2010 through December 2024. Three July–September 2010 files fail the corn-table unit check: matrix2 contains metric-ton unit descriptors rather than the required bushel marker. They remain quarantined, with no guessed conversion or unit override. The accepted data pass 2,022 supply-minus-use-minus-ending-stocks checks at a two-million-bushel rounding tolerance. Forty-two groups contain missing values and are excluded from that arithmetic check; NA remains missing, never zero. There are no accepted-cell report-month/date mismatches or incomplete three-field groups.

Two December 2018 XML versions and three November 2019 versions have identical selected-cell digests within each month. This supports deduplicating these selected fields, not claiming entire reports are identical or establishing intraday publication timing. The index retains every source. October 2013 and January 2019 have no entries in the bounded index; no release is manufactured for either month. Crop years and forecast months remain separate. Source parsing is not yet the final vintage-aware predictor builder.

Five targeted parser tests pass: crop-year separation, missing-value preservation, rejection of duplicate semantic cells, acceptance of the observed `{wasde}` namespace, and rejection of unknown namespaces. Dated probes live under `scripts/research_probes/`; they are explicit feasibility tools, not production runners. The downloader expects the recorded all-format index under `artifacts/ml_crop_feasibility_20260910/`. Raw market/source data remain outside Git.

### Dependence and preliminary planning

Across 143 monthly returns in 2013–2024, crop pair correlations are 0.49–0.71. Three funds therefore cannot be counted as three independent histories. These are calendar-month price diagnostics, not release-aligned predictive correlations or an effective-sample-size estimate.

A separate known-signal simulation uses 82 eligible 2018–2024 release events, joint three-asset return vectors, three-/six-month circular blocks, and synthetic persistent predictors with varying common components. It does not fit a model or implement costs. At injected standardized effect 0.10, rejection rates range 13.5–34.6%; at 0.15 they range 27.3–66.9%. Null rejection ranges 3.8–5.3% on 1,000 evaluation draws per scenario, separate from threshold calibration. These are sensitivity scenarios, not empirically estimated alpha, not full model power, and not a pass/fail campaign decision. In particular, learned coefficients, feature persistence, actual folds, missingness and trade thresholds still need to enter the mandatory power analysis. No neural-network or broad model search has begun.

### Concrete next requirements

The supplied prices are sufficient for the current source pilot; no replacement download is requested. Next, record the operator's equity broker and confirmed access to CORN, WEAT, SOYB and BIL. This is required by the repository's tradeability-before-specification amendment; public price availability and U.S. residency are insufficient. No account numbers or credentials are needed. Capital scale in CLAUDE is approximately $100,000, but no allocation is authorized by this audit.

Once broker access is established, complete the same-crop-year feature builder and release deduplication, validate historical fund adjustments/mandates and realistic execution scenarios, and run the full null/injected-signal learning-and-trading simulation. Only then draft a campaign for a later freeze review. The prior 2025 reservation and frozen Core remain intact. The purpose of broadening is to test a distinct physical-supply hypothesis across related markets, not to keep searching price-only models until one looks good.

## Authorized testing update — 2026-09-10

The user does not yet know their execution broker and explicitly requested proceeding with testing. Broker access is not a blocker for source, leakage or synthetic-label feasibility tests. It remains unresolved for executable-strategy claims. This update supersedes the earlier ordering that placed all further feature work behind broker confirmation.

Built `crop_learning_test_20260910.py`: 507 vintage-aware crop feature rows, of which 456 rows form 152 complete three-crop price events. The annual expanding evaluation covers 82 releases in 2018–2024; the first eligible entry is 2012-01-17 and the last exit is 2024-12-12. Forty-five feature rows have missing revisions, explicitly flagged and zero-filled only for the numerical model input. The ratio compares U.S. projected ending stocks to projected total use. Select the latest projected crop year; no substitution of an older valid year when the latest projection is missing. Revisions require that same crop year in the previous usable vintage within 62 days. May's new crop cannot be subtracted from April's old crop. Differing same-month versions fail; identical selected-field versions retain the earliest date. Intraday publication availability is not asserted.

Feature construction passed future-release truncation and adversarial future-value tests. Price controls use information through release-day close; entry waits until the open after one full subsequent common trading session. Labels span 21 sessions. Annual folds train only on labels whose exit precedes the first test release, keeping each release's three assets together. No 2025 prices are accessed.

The learner is fixed Ridge alpha 10 with training-only scaling and an unpenalized intercept. Baseline controls are asset identity, seasonal sine/cosine, 21-/63-session momentum and 63-session volatility. The augmented learner adds stocks/use, same-year revision and a missing-revision indicator. Its linear prediction operator matches an independent scikit-learn implementation to numerical tolerance. No real-label model fits, observed feature/return correlations, strategy returns or break-even costs have been calculated.

### Synthetic incremental-signal results

Noise consists of centered, scaled actual joint three-crop return vectors, resampled in three-/six-event calendar blocks. The synthetic linear shortage signal is formed from stocks/use and revision, residualized against nuisance controls and standardized using the full design matrix solely to define the data-generating process. This global calibration never supplies model training transforms. Thus the injected information is additional to the baseline, rather than mostly asset or seasonal differences. Effect 0.05 is the central planning amplitude, motivated by the repository's small-effect research guidance; it is not an estimated market correlation. Effects 0.02–0.20 are sensitivity cases; 0.50 and 0.80 are deliberately unrealistic implementation canaries.

For each block setting, 1,000 null draws calibrate a one-sided 95% threshold for out-of-sample squared-error improvement, floored at zero; disjoint 1,000 draws estimate detection. Every draw uses the actual annual training/test structure. A separate known-signal score test directly observes the injected signal and estimates no coefficients; it is an optimistic comparator, not an executable strategy or a universal upper bound.

| Injected amplitude | Learned incremental model detection | Known-signal comparator detection |
| --- | --- | --- |
| 0 (null) | 4.8–5.3% | 4.2–4.9% |
| 0.02 | 5.5–5.9% | 8.5–8.7% |
| 0.05 (central) | 7.5–8.5% | 18.9–19.7% |
| 0.10 | 21.5% | 44.4–46.8% |
| 0.15 | 43.4–44.2% | 74.4–75.0% |
| 0.20 | 68.1–69.6% | 91.5–91.7% |
| 0.50 / 0.80 (canaries) | 100% | 100% |

These are simulation frequencies with 1,000 evaluation draws per setting, not confidence levels on a real strategy. The synthetic strong-signal check and independent implementation comparison argue against a grossly broken learner. They do not establish optimal model design. Both the available sample and the need to estimate the relationship limit detection under the stated assumptions.

Ten targeted tests passed. A second deterministic run reproduced all three output artifacts byte-for-byte. Raw inputs are hash-checked against the prior audit, and parsed-cell/cash-file hashes accompany this result. Outputs are `crop_features.csv`, `crop_panel.csv`, and `learning_power_report.json` under `artifacts/ml_crop_learning_test_20260910/`. The small JSON result is retained in Git; data remain local.

### Consequence for real-outcome testing

Status: NECESSARY_PREDICTIVE_POWER_GATE_FAILED_UNDER_TESTED_DGP. This is not a negative crop-alpha result. The model would usually miss an injected modest effect. Amendment 1's approximately 50% power requirement therefore prevents advancing this design to a real-outcome campaign. Adding transaction-cost and economic gates cannot improve the probability of passing this same necessary predictive gate as part of a conjunction, though this is not a universal statement about every possible alternative objective or design.

Cost scenarios and break-even friction were not computed because doing so would require real fitted trading outcomes after this failed prerequisite. Do not increase the central assumed effect to 0.20 merely to pass, shorten labels merely to inflate observations, or interpret the three assets as independent. The next design decision is whether to invest in a substantially broader economic panel/longer tradable history, or explicitly change the research objective to a descriptive pilot that cannot establish a modest edge. No broker choice, price re-download, neural-network sweep or Core change solves the measured limitation by itself.
