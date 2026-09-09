# ML research redesign — monthly equity allocation

**Date:** 2026-09-09. **Status:** DESIGN DRAFT; feasibility unresolved; no model run.
**Owner:** Itera ML Lab. **Branch:** `research/ml-decision-redesign-20260909`.

## Decision and reason for the reset

The operator authorized a change of direction after Experiment 013. End the
sequence of variations on the 14-ETF, price-state, volatility-normalized ranking
task. Experiment 013 closes under its original negative primary rule; changing
the objective now does not rescue that experiment.

The proposed ML job is specific: **once each month, decide which liquid U.S.
stocks to overweight and underweight within a separate, fully invested equity
research sleeve, relative to its equal-weight benchmark.** Judge the resulting
portfolio on incremental returns after costs, subject to a fixed risk budget.
This is an offline research allocation, not a change to Core's existing weights.

The structural question is whether issuer information adds a source of relative
return information beyond price trends. The learning task combines financial
levels, changes, price response and market context across many issuers. This gives
ML a reason to pool information and estimate conditional relationships. Merely
adding a deeper model to the old feature set does not establish that reason.

Working mechanism, not an established finding: heterogeneous attention and
mandate-constrained trading may cause issuer information to enter relative prices
at different rates. Financial changes and the price response already observed
could distinguish incomplete adjustment from information already priced in.
This is a weak prior in competitive liquid equities. If timestamped issuer data
add no value over price-only controls, stop this hypothesis rather than inventing
more interactions. This is not a revival of the closed month-end-flow campaign.

The existing ETFs are useful accounting fixtures only. They are not the new
learning universe, an untouched test set, or evidence that this task is feasible.

## Proposed decision contract

These are concrete design defaults to review before implementation, not selected
backtest winners. No parameter sweep or portfolio-optimizer search is proposed.

| Item | Proposed definition |
| --- | --- |
| Instruments | U.S.-listed nonfinancial operating-company common stocks; exclude funds, preferreds and ADRs using historical security classifications. Nonfinancial restriction makes operating cash flow and margin comparisons interpretable. |
| Universe | At each signal date, top 100 eligible issuers by trailing 60-session median daily dollar volume, at least $10m/day, unadjusted close at least $5, and at least 252 prior sessions. One share class per issuer, chosen by the same liquidity measure. Include securities that subsequently delist. Stable security ID resolves ties. Fewer than 100 is a support failure, not permission to shorten history or loosen filters. |
| Clock | Signal after the last exchange session of each month, using information available by that close. Proposed entry is the following session's open. Next month's entry open ends the holding interval. No same-close fills. |
| Benchmark | Equal weight in that month's exact eligible 100-name universe, with identical execution, dividend, membership and cost conventions. This is an opportunity-set benchmark, not Core v1 or an asserted optimal allocation. |
| Label | Stock total return from entry open to next entry open, minus the contemporaneous equal-weight universe return over the same interval. No volatility denominator and no conversion of the label to ranks. |
| Model output | Expected benchmark-relative return in return units. Use its ordering for a bounded allocation; report calibration as a diagnostic. |
| Risk budget | Long only, fully invested, unlevered. Reallocate 10% of sleeve capital from lower-scored to higher-scored names at each scheduled rebalance. No market-timing or cash-state model. |
| Evaluation | Paired net monthly portfolio return versus every registered simple allocation. IC is diagnostic and cannot determine the result. |

Allocation formula: for N names, let q_i be the average rank of predicted return
minus (N+1)/2. Let Q be the sum of positive q_i. If Q=0, use equal weights.
Otherwise w_i = 1/N + 0.10*q_i/Q. Sum w_i=1 and the positive active weights sum
to 0.10. For a complete untied 100-name ranking, weights range approximately
0.604%–1.396%. Ties can concentrate the allocation: reject any proposed vector
outside [0.5/N, 1.5/N]; use equal weights for that month and record the fallback.
The fallback rule is identical for learned and simple scores. Missing required
prices, security identity, or label outcomes invalidate support; do not turn
those failures into favorable cash returns or drop losing securities.

Financial information requires its actual publication/filing availability and
the version known then. A fiscal period end plus an invented fixed lag is not
enough. Restatements become usable only after their availability time. If only
an availability date exists, make the information usable the next exchange
session. Fit-time snapshots must also prevent later revisions from entering
earlier training folds. Labels may use subsequently realized total returns;
features may not use subsequently revised financial statements.

## Accounting and costs come before fitting

Maintain one continuous, self-financing portfolio ledger for each comparator.
Compute trades against drifted pretrade holdings, not last month's target
weights. Charge all buys and sells, including membership changes, entry and final
liquidation. Solve post-cost position sizing against the available NAV. Dividends,
splits, mergers, suspensions and delistings need explicit auditable treatment.
Report total-return convention and any dividend reinvestment assumptions.

For feasibility, use 10 basis points per dollar traded as the primary cost
scenario and 25 basis points as adverse-cost sensitivity. These are research
assumptions, not verified broker quotes or evidence of attainable fills. Cost is
c*sum(abs(trade_notional))/pretrade_NAV, with the same convention for every model.
Do not silently halve it using a one-way turnover convention. Both comparator
legs pay their own costs. Record gross and net returns, turnover and break-even
cost; subtracting identical constant costs from every model would miss the point.

Verify adjusted-open consistency and cash distributions before building labels.
Do not mix unadjusted opens with adjusted closes. A price-only return series may
exercise plumbing, but cannot be presented as the proposed economic outcome.
Corporate actions and total returns must reconcile on known event examples.

No production allocation system is reused as the return ledger. In particular,
the historical HOLD/exposure caveat identified in `CLAUDE.md` must not be inherited
silently by a new allocation test. Core's accounting and record stay untouched.

## Information and model comparison

Before outcomes, lock a data dictionary with formulas, units, availability rules,
source identity, security joins, missingness treatment and allowed transformations.
The intended issuer block is modest: profitability, cash-flow profitability,
accruals, leverage, revenue growth and changes in operating margin. Use four
reported quarters where needed; each contributing observation needs its own
availability record. No analyst-revision or fund-flow feature is assumed available.

Use a compact price/liquidity context block: 20/60/120-session returns, 60-session
volatility, 20/60 volatility ratio, 120-session drawdown and 60-session dollar
volume. Retain economically meaningful levels and within-date relative values;
fit clipping, imputation and scaling only on training data. Missing financials
need a preregistered indicator/imputation policy, not future backfill or an
outcome-dependent exclusion. Sector-relative transforms require historical sector
labels. No ticker-specific free parameters or manually chosen interactions.

One bounded comparison, four learned candidates:

1. Regularized linear regression, price/liquidity context only.
2. The same linear family with issuer information added.
3. Shallow gradient boosting, price/liquidity context only.
4. The same boosting family with issuer information added.

This separates the value of information from the value of nonlinear modeling.
Simple allocation controls are equal weight, low 60-session volatility, high
120-session momentum, and a fixed financial-quality score. The quality score is
the equal-weight mean of within-date ranks of trailing-four-quarter net income /
latest assets and operating cash flow / latest assets, minus the rank of total
liabilities / latest assets. Its timing and missingness use the same data contract.
Apply the same allocation mapping and costs to every nonconstant control.

Exact estimators, regularization values, boosting capacity and seed belong in
the executable contract after feature support is known, before the first model
fit. Permit one setting per family, shared across the two information blocks.
Do not choose those settings from test results. No neural network, model ensemble,
automated feature search or additional training-window search in this screen.

## Chronology, success and stopping

Proposed history: training anchors from 2005, annual walk-forward evaluation
2010–2024, using the preceding five years of eligible monthly anchors at each
annual refit. Require label exit before fit/decision availability. Preprocessing
and model fitting share that purge. Month-end portfolio intervals do not overlap;
stocks within each month are dependent. Never split stocks randomly across
train/test and call the result chronological validation.

Annual fitting occurs at the year's first monthly signal, using only labels
already complete then and the prior five calendar years' signal anchors. Feature
warmup may require source history before 2005. Every label and executed holding
interval must exit by 2024-12-31: omit the December 2024 signal, whose exit would
be in January 2025. The proposed January 2010–November 2024 signal schedule has
179 monthly intervals, with a partial final year, not 180 complete intervals.
Declare that endpoint mechanically before evaluating any returns.

All pre-2025 history remains exploratory given earlier research and design choices.
Report 2010–2019, 2020–2024 and every year without selecting a favorable period.
The entire 2025 interval and later data are excluded from this screen. Campaign
#50's reserved holdout is not ours to spend, and changing the stock universe does
not authorize using it. No historical interval is relabeled untouched.

Draft economic hurdle: at least **2 percentage points per year** of annualized
arithmetic net active return versus equal weight at primary costs, positive net
active return in both fixed periods and in at least 9/15 evaluation years, annualized
monthly tracking error at most 5%, and maximum drawdown no more than 5 percentage
points worse than equal weight. Also require positive full-period paired net
increment versus every simple allocation and positive active return versus equal
weight under adverse costs. Show compounded NAV/CAGR separately; arithmetic active
return is not CAGR. A later pre-fit contract must encode all these rules exactly.

For an issuer-information candidate to earn follow-up, its paired net increment
over the same-family price-only candidate must be positive in both fixed periods.
Boosting earns preference over linear only if its paired net increment is positive
in both periods. Otherwise prefer the passing linear model. If both pass, the
default shortlist is one issuer-information candidate, selected by these rules,
not whichever backtest Sharpe is largest. A price-only success cannot rescue the
issuer-information hypothesis; record it without silently changing the question.

These are deliberately concrete **screening defaults**, not significance claims
or promises. Report all candidates, including failures. For any apparent winner,
report every security/year contribution and a descriptive subtraction of the
largest positive contributor. If removing one security or one year flips pooled
net active return negative, label the screen inconclusive for concentration.
This subtraction is an attribution stress, not a refitted exclusion strategy.

Materiality must also work in dollars: 2pp is $2,000/year on a hypothetical $100k
sleeve, $1,000 on $50k, and $400 on $20k, before fixed data/operating costs. No such
capital is allocated. Record a realistic separate-sleeve capital scenario and
annual data/operating cost before committing to the data pipeline; reject a plan
that cannot plausibly leave at least $1,000/year after those fixed costs at the
central effect. Existing total account capital is not automatically available
sleeve capital. This hurdle is a proposed research-effort filter for operator
review, not an assumption about the operator's budget.

Effort budget: one working session for source/access feasibility; stop with a
specific missing item if unresolved. After feasibility, one fixed four-candidate
screen: one fit per candidate per annual fold, 60 fits for the proposed 15 years,
plus one identical replay for reproducibility. No tuning jobs or model-selection
cross-validation search are proposed. One implementation-error repair/replay is allowed, labeled
invalid first; model disappointment is not an implementation error. A valid
negative closes this task. Insufficient support is inconclusive, not evidence
against ML. Any new universe, target, data block or second search budget requires
a new recorded rationale; another numbered diagnostic is not the default.

## Feasibility findings and immediate handoff

Repository review completed at parent `d0971a3`; the following are actual findings,
not passed gates inferred from source filenames.

| Requirement | Evidence now | Next concrete check |
| --- | --- | --- |
| Point-in-time stock universe, including dead securities | Absent from reviewed ML Lab inputs; 14 fixed ETFs are a different dataset | Identify one licensed source or existing operator export with stable IDs, historical security type, issuer identity, listing/delisting and sector history. A current constituent list fails. |
| Execution prices and distributions | Campaign #50 inventory has OHLCV; adjustment semantics are not established there. `ohlcv_v1.py` retains only OHLCV. | Obtain provider field definitions plus event examples and validate consistent open-to-open total returns, split factors and terminal delisting outcomes. Do not infer semantics from the presence of a `close` column. |
| Issuer information available at each decision | No issuer financials or publication-version history in the reviewed input set | Obtain a small multi-issuer sample spanning filings and revisions, with period, actual availability, version and stable ID. Reject a latest-restated-history-only source. |
| Historical support | Existing 902 ETF anchors do not measure new stock support | Count eligible issuer-months and complete monthly calendars from metadata; show every gap and annual breadth. Target 179 completed evaluation intervals under the cutoff above; do not manufacture 17,900 independent observations from 100 stocks/month. |
| Tradability and costs | Operator's equity brokerage, fractional-share support and access to this universe are not verified in the reviewed records | Record actual broker/account capability and indicative commission/spread/minimum-ticket constraints. U.S. residence alone is not verification. No paid source or account subscription is ordered. |
| Decision availability | Proposed monthly effect horizon and next-open deadline; no current timing measurement for these new sources | Measure close-to-feature-ready and feature-to-order-ready latency. Require the 95th percentile to meet the next-open deadline and a horizon/decision-lag margin of at least 10 using trading-time units. Historical Core cadence is not a current audit of this path. |
| Sample suitability | Hundreds of correlated securities may add issuer variation, not independent market years | Count months, issuer coverage and concentration before fitting. A broad cross-section is not a guarantee of predictive information or power. |
| Confirmation path | None newly allocated; 2025 remains reserved elsewhere | Before promotion, identify a genuinely unexamined lawful dataset or prospectively accumulated interval and estimate time/cost to meaningful evidence. One reserved year is not assumed sufficient. |

### Initial source check — completed 2026-09-09

Two primary-source documentation checks narrow the acquisition work; neither is
a source acceptance or a purchase recommendation:

- [Norgate's coverage tables](https://norgatedata.com/data-content-tables.php)
  describe delisted-stock access in its higher U.S. stock packages. Its
  [data FAQ](https://norgatedata.com/data-package-faq.php) documents stable asset IDs
  but only current fundamental values, and no explicit delisting-return field.
  It could supply part of the price/security history, but does not alone satisfy
  this contract. A valid issuer/CIK join and terminal-event treatment remain open;
  current ticker equality is insufficient. Do not use the final historical bar
  as a liquidation signal unless that information was actually available then.
- [SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
  provides public filing histories and aggregated XBRL facts without an API key.
  It dates the initial XBRL requirement to 2009 and describes the frames endpoint
  as choosing last-filed facts. Therefore neither 2005 financial coverage nor a
  point-in-time panel is established by downloading CompanyFacts/frames. A
  filing-version reconstruction, issuer/security mapping and earlier-history
  solution would be necessary for the proposed schedule. Free raw access does
  not mean low engineering cost.

**Source-feasibility disposition: unresolved.** Do not build a broad acquisition
pipeline from these descriptions alone. The bounded next action is to check any
existing operator data entitlement/export against the contract, or obtain a
provider sample and a concrete total cost. If the proposed pre-2010 training
history cannot be supported, revise dates and support requirements once before
outcomes, explicitly reducing the evidence claim, or stop. No automatic switch
back to the old ETF experiment is permitted.

First implementation, only after those checks: a separate monthly return ledger
and benchmark/control run. Verify cash conservation, drifted weights, distributions,
cost monotonicity, membership turnover, tie fallback and deliberate future-data
canaries before connecting estimators. Prove an intentionally late filing and an
overlapping training label are rejected. Never make a replay pass by comparing
two outputs generated from the same faulty timing assumption.

Then lock the feature/estimator contract and run the four candidates once. Store
input manifests, availability joins, fold support, OOS predictions, target and
executed weights, trades/costs, daily NAV, monthly paired returns, attribution,
screen disposition and replay hashes in a new artifact directory. Nothing here
requires modifying any Experiment 005–013 implementation or frozen artifact.

## Evidence standard and authority

This is a proposed ML Lab sandbox task under
[the exploration charter](ML_LAB_EXPLORATION_CHARTER.md) and
[the sandbox protocol](../ITERA_EXPLORATION_SANDBOX.md). Amendment 6 explicitly
does not require campaign-level power or a later-day freeze for a cheap screen;
we are not using those requirements to delay permitted exploratory work. The
current blockers are missing data/access/economic-feasibility evidence, not an
invented approval gate. Design documentation is complete; feasibility is not.

Screen results, when executed, use only SCREEN_NEGATIVE, SCREEN_INCONCLUSIVE,
SCREEN_POSITIVE or SCREEN_INVALID. A positive screen earns a governed evaluation,
not deployment. Before that evaluation, simulate the *complete* decision process
at plausible annual net-active effects of 1/2/3pp, retaining time blocks and
cross-asset dependence. The central 2pp case must have at least 50% estimated power
under the final gates, selection rule and confirmation multiplicity, as required
by [the research amendments](../ITERA_RESEARCH_PROCESS_AMENDMENTS.md). Report
uncertainty in that estimate. If support is inadequate, redesign once before
outcomes or stop; do not call an underpowered null a scientific negative.

No screen or draft authorizes changes to Core v1/Core v2, live or paper portfolios,
runtime, exposure, capital or another campaign's holdout. No new model training,
source purchase, acquisition, execution or data-feasibility pass is claimed here.
Append feasibility, the locked contract, execution and closure to this document
instead of opening a chain of additional planning documents.
