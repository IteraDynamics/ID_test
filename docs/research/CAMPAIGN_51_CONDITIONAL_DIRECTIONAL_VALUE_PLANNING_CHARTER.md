# Campaign #51 — Conditional Directional Value of Supported BTC Movement States

## Status

**PLANNING CHARTER ONLY — hypothesis-family inventory and design work authorized; implementation and outcome generation prohibited.**

Campaign #51 begins after the final closure of Campaign #50. It builds from the completed Campaign #48 evidence without changing, extending, or reinterpreting Campaign #48 after the fact.

This charter authorizes no predictive computation, candidate testing, historical outcome generation, economic backtest, Core v1 comparison, paper trading, runtime change, threshold change, signal change, strategy change, order generation, portfolio construction, NAV work, exposure change, dashboard change, or model training.

## Governed antecedents

### Campaign #48 positive research baseline

Campaign #48 tested eight prespecified BTC price-state predictors against directional return, absolute return, and realized volatility at 24-, 72-, and 168-hour horizons.

It produced 15 supported associations, all concentrated in:

- recent realized-volatility persistence into future absolute return;
- recent realized-volatility persistence into future realized volatility;
- deeper drawdown from the trailing 168-hour high associating with higher future realized volatility.

No directional-return candidate was supported.

Campaign #48 therefore established that simple BTC volatility and drawdown state contains reproducible information about the magnitude and volatility of subsequent movement, but not unconditional direction under that frozen design.

Campaign #48 closure:

- commit `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`.

Campaign #48 canonical publication:

- commit `fd7ee01`.

### Campaign #50 negative research baseline

Campaign #50 tested a separate equity-breadth family against future SPY and QQQ returns. No candidate passed development discovery, and the shortlist was empty.

Campaign #50 final closure:

- `docs/research/CAMPAIGN_50_FINAL_CLOSURE.md`.

Campaign #51 is not a rescue or redesign of Campaign #50.

## Planning question

> Do BTC volatility and drawdown states already supported by Campaign #48 identify conditions under which a separately defined, pre-existing directional signal has materially different forward directional value?

The distinction is essential:

- Campaign #51 will not ask volatility or drawdown state to predict direction by itself;
- it will ask whether those states condition the reliability or effect size of a directional variable defined independently of Campaign #48 outcomes;
- it will not authorize a strategy or economic mapping.

## Research rationale

A state variable can be valuable without carrying directional sign. Recent volatility or drawdown may identify when directional information is more consequential, noisier, more persistent, or less reliable.

The proposed family therefore studies interaction or stratification effects between:

1. a small frozen set of independently justified directional variables; and
2. a small frozen set of Campaign #48-supported movement-state variables.

The design must remain narrow enough to avoid an uncontrolled interaction search.

## Planning constraints

Before any implementation GO, Campaign #51 must freeze all of the following:

- exact governed source files and hashes;
- exact source fields permitted in calculations;
- exact development, validation, and untouched holdout intervals;
- exact directional-variable inventory;
- exact movement-state inventory derived from Campaign #48 definitions;
- exact conditioning construction: interaction, stratification, or both;
- exact forward directional outcomes and horizons;
- exact candidate count;
- expected signs or directional hypotheses where economically justified;
- chronological anchor construction and overlap treatment;
- minimum total and state-specific support gates;
- estimator and covariance choice;
- multiplicity family and correction;
- development, validation, shortlist, and confirmation rules;
- deterministic failure precedence;
- canonical output schema;
- mechanical holdout isolation;
- deterministic replay requirements.

No outcome may be generated before these decisions are committed.

## Candidate-budget constraint

The final frozen candidate family should be deliberately small.

Planning target:

- preferably 6 to 12 candidates;
- hard planning ceiling of 18 candidates unless a separate pre-outcome board decision justifies a larger family.

The candidate budget must be allocated before any outcome generation. Candidate count may not expand after results are observed.

## Directional-variable eligibility

A directional variable may enter Campaign #51 planning only if it is:

- already present in the repository or mechanically derivable from a governed price source;
- defined without reference to Campaign #51 outcomes;
- interpretable before testing;
- distinct from the Campaign #48 movement-state variable used to condition it;
- available with enough historical support for development, validation, and untouched confirmation;
- not introduced as a runtime or strategy modification.

Possible categories for inventory review include:

- recent signed return or momentum state;
- long-horizon trend state;
- price-location or breakout state;
- existing research-only directional intent or score already stored in deterministic artifacts.

This list is an inventory scope, not authorization to test every category.

## Movement-state eligibility

Campaign #51 may consider only movement-state constructions directly traceable to Campaign #48's supported families during initial planning:

- trailing 24-hour realized volatility;
- trailing 168-hour realized volatility;
- drawdown from the trailing 168-hour high.

Planning must decide whether to use continuous interactions, precommitted state bins, or one selected construction. No threshold optimization is authorized.

## Required first deliverable

The next governed deliverable is a source-and-variable feasibility inventory that contains no Campaign #51 forward outcomes.

It must report:

- candidate directional variables already available in the repository;
- their exact source lineage and formulas;
- Campaign #48 movement-state variables available on the same calendar;
- common date coverage;
- missing-data and cadence constraints;
- calendar-only maximum sample counts by proposed horizon and partition;
- potential leakage or duplication concerns;
- a recommended narrow family for later board selection.

The inventory must not calculate:

- forward returns;
- directional accuracy;
- coefficients;
- p-values;
- rankings;
- candidate support outcomes;
- economic performance.

## Mandatory stage separation

1. Planning charter — **authorized and opened by this document**.
2. Source and variable feasibility inventory — **authorized next**.
3. Hypothesis-family selection and statistical specification — **not yet authorized beyond planning**.
4. Implementation and synthetic testing — **not authorized**.
5. Development and validation outcome execution — **not authorized**.
6. Untouched historical confirmation — **not authorized**.
7. Economic-value testing — **not authorized**.
8. Forward paper trading — **not authorized**.
9. Limited-live-capital review — **not authorized**.

Passing one stage does not authorize the next.

## Fail-closed requirements

Campaign #51 work must preserve:

- deterministic outputs;
- chronological and leakage-safe construction;
- replay-safe execution;
- explicit source identity;
- observation-only feasibility work before outcome authorization;
- mechanical holdout isolation;
- no source substitution or repair without prior governance;
- no post-outcome threshold, candidate, sign, support, or method changes.

Any ambiguity in source identity, timestamp ordering, calendar alignment, stage containment, or authorization must stop work before outcome generation.

## Current authorization

Authorized now:

- inspect existing repository research variables and source lineage;
- inspect Campaign #48 governed definitions and artifacts;
- inventory candidate directional variables without generating Campaign #51 outcomes;
- inspect timestamp coverage, schemas, hashes, and calendar-only support;
- draft a family-selection memo based only on economic rationale and non-outcome feasibility;
- update the campaign board with planning evidence.

Not authorized:

- generating any Campaign #51 forward directional outcome;
- fitting any Campaign #51 model;
- examining conditional directional performance;
- ranking or selecting variables based on outcomes;
- changing Core v1 or any runtime surface;
- economic testing, portfolio work, or paper trading.

## Immediate sequence

1. Preserve Campaign #50 final closure.
2. Inventory exact repository directional variables and source lineage.
3. Reconcile those variables with Campaign #48 movement-state definitions and calendar coverage.
4. Produce a non-outcome source-and-variable feasibility record.
5. Select one narrow hypothesis family under a separate board decision.
6. Freeze the complete statistical specification before any implementation or outcome generation.
