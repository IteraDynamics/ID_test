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
