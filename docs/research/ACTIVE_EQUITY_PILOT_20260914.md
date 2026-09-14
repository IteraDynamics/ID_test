# Active equity pilot v1 — prospective decision research

Status: **STAGE 1 BUILT; NO COHORT OR INVESTMENT PERFORMANCE YET.**
Separate branch: `research/active-equity-pilot-20260914`.
Parent: `5622fb2a3d2c4d74a34f007d52e1e56be7853805`.
Core stays on its independent paper-trading path. No Core parameters, runtime,
paper accounts, live execution or capital authorization change here.

## Decision and hypothesis

Can source-backed AI assessment of durable earnings improvement add useful
investment selection beyond a simple accounting screen? Candidate mechanism:
investors may underreact to the persistence of a business improvement when its
implications require reconciling several disclosures. This is a hypothesis, not
an assertion of current mispricing or novelty. Serious alternatives: ordinary
growth/size/sector exposure, already-priced news, temporary earnings, narrative
overconfidence, or costs eliminating any forecast advantage.

The first deliverable is an auditable workflow and a prospective 20-issuer
research cohort. Twenty companies establish neither alpha nor diversification.
No historical simulation with today's LLM is called pristine OOS: model weights
may encode later events. Subsequent evaluation is based on decisions actually
recorded before executable future prices, with explicit inference latency.

## Frozen scope and experimental controls

- US-listed operating companies' common stock; exclude funds, preferreds, warrants,
  pre-operating shells, and non-common instruments.
- Event-time equity market capitalization $500 million through $10 billion inclusive.
- At least $5 million trailing 20 completed regular-session average dollar volume.
  Use as-of shares/capitalization and preceding completed sessions, not future
  volume or today's shares applied to an earlier event.
- One issuer per cohort, identified by zero-padded 10-digit CIK. Multiple listings
  and repeated releases cannot count as independent companies.
- Long-only proposed targets; cash allowed; no leverage or shorting. Maximum 10%
  target per issuer and 25% per frozen sector. These are transparent proposed
  operating limits, not fitted parameters or guarantees on drifted holdings.
- Research focus: earnings, filed statements and guidance updates. Expected
  investment horizon weeks to two quarters. Each forecast states its own deadline.
- Initial actions: buy/watch/reject; later hold/sell permitted as recorded revisions.
- No inherited Core performance gate, and no prescribed CAGR/Sharpe target.

## Information boundary and enrollment

Initialization freezes this document, the analyst prompt, and runner code. It
does not enroll companies or silently pick a favorable historic window.

Before enrollment starts, register an `enrollment` record identifying the actual
earnings-event feed, its declared coverage, the enumerable universe snapshot and
source packet, and a strictly future UTC start. An earnings calendar feed has not
yet been chosen. This is an explicit prerequisite, not an undisclosed dependency
or an instruction to purchase one. Check existing local coverage first.

After enough events occur, supply a `cohort` record containing **every screened
event in [start,end)** from that declared feed, not just attractive companies.
Sort eligible events by publication instant, CIK, then event_id; choose the first
20 distinct issuers. Log exclusions as well. Unknown eligibility or comparator
inputs must be resolved with sources; never exclude them silently to complete 20.
Full coverage is an operator attestation requiring independent review. The code
cannot prove that omitted companies do not exist. With a limited feed, the claim
is consecutive within that feed, not exhaustive coverage of all US equities.

The cohort is locked before the first decision. Because accumulation takes time,
the pilot includes research delay: no entry is credited at the original earnings
price. All companies receive decisions before the first portfolio proposal.
The later execution stage must use prices strictly after decision/proposal
registration. A market opening exactly simultaneous with a decision is ineligible.

## Evidence and decision record

Sources are captured as immutable content-addressed local snapshots with original
HTTPS URL, publication time, earliest available time, description and SHA-256.
Only supply public materials you are authorized to retain/share. Evidence URLs
are metadata: this tool does not download pages, execute document instructions,
read credentials, or call an LLM. Snapshot content is included in the share ZIP.

Chronology: publication <= availability <= local capture < subsequent decision
registration < possible execution. The CLI stamps registration using its current
UTC clock; no backdated decision timestamp argument exists. Source timestamps and
facts are supplied assertions needing review, not automatically verified truth.

Each decision records thesis, valuation/expectations, counterargument, forecast,
horizon, invalidation, qualitative confidence/reason, model/version visibility,
analyst, source-backed claims, and superseded decision if any. Fact/inference/unknown
are distinct. Source locators are required, but the parser cannot determine whether
the cited section actually supports the claim. Independent evidence review must.

SQLite serializes writes; application commands append only. Hash chaining and
snapshot verification detect accidental edits. They do NOT prevent a database
owner from rewriting the whole history, adjusting a system clock, or removing its
tail. Before prospective performance evaluation, anchor each exported head/hash
and journal in an external timestamped record (e.g. the user's uploaded ZIP and/or
an authorized Git commit). Do not claim that Git history alone proves truthful
publication timestamps or uncontaminated model knowledge. Preserve failed/abstained
analyses and model/prompt changes, not only final successful recommendations.

## Baselines and attribution — frozen design, not implemented returns

Simple comparator: revenue YoY growth > 0 AND operating-margin YoY change > 0,
using comparable filed periods and standardized units. Missing inputs block cohort
registration. This is a deliberately simple accounting screen, not consensus
earnings surprise. All 20 events are reported with comparator pass/fail.

For the initial selection-only comparison, allocate 1/20 initial NAV to each
screen pass, retaining the balance in cash; apply the same 5% slot to each initial
AI buy. If a sector's proposed weights exceed 25%, scale that sector proportionally
down to 25% and retain the difference in cash. Keep rejects/watch decisions at
zero. No repeated searching for a winning comparator.

The separate discretionary portfolio uses AI complete-target proposals subject
to the 10%/25% caps. This separates selection from sizing/cash/revision effects.
Predeclared event-outcome horizons: 21, 63 and 126 trading sessions from the same
eligible post-decision execution reference; initial recommendation is never
overwritten by later analysis. These are design choices, not independent tests.

Reference assets for the later accounting stage: IWM (size-oriented comparison),
SPY (broad equity), and measured cash opportunity return. Disclose sector, growth,
size and beta mismatches instead of treating either ETF as a perfect factor match.
For Core comparison, use only the common prospective dates and identical reporting
conventions; do not compare this pilot to Core's selected historical headline.

No fill/NAV evaluator is implemented in stage 1. Before any simulated position:
freeze the accessible price/calendar source, real execution time rule, capital
denominator/participation limits, explicit fees/spreads/slippage base and stress
cases, and the cash-yield convention. Do not silently import crypto costs, assume
free cash financing, or claim fills from completed-bar information. Splits,
dividends, delistings, suspensions, missing/stale prices, and terminal holdings
must be handled and independently reconciled in that next stage. All returns,
CAGR, Sharpe, drawdown, and Monte Carlo fields therefore remain NOT_RUN/null now.

## Pilot decision criteria

Stop or revise for unsupported numbers, hindsight-dependent cohort selection,
unresolvable coverage, omitted rejects, stale source packets, inconsistent rules,
or lack of analysis beyond the simple screen. Review these process defects before
outcomes can reward persuasive storytelling. Do not promote on a few profitable
weeks or reject merely for a noisy month. Later paired net comparisons need
dependence-aware uncertainty and economic materiality, with beta/sector, influential
events, turnover, cash and research/API cost attribution. No fixed sample count
or Sharpe gate is represented as a universal proof standard.

## Local operator workflow

Use a separate Git worktree. From its root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_active_equity_pilot.ps1 -DataRoot 'C:\Dev\IteraDynamics\ID_test\data'
```

This runs correctness tests, initializes a NEW pilot, takes a filename/size-only
inventory (no data contents copied), and prints a readiness ZIP. AWAITING_ENROLLMENT
is the expected first state, not an error. No market data is downloaded and no
stocks are selected. The normal uv environment setup may fetch missing software
dependencies. No API key is required.

Retain the printed pilot directory; do not create a new pilot for every update.
Re-export an existing pilot from any shell working directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_active_equity_pilot.ps1 -Mode Report -PilotDir 'ABSOLUTE_PATH_TO_EXISTING_PILOT'
```

The analyst supplies real input records later; placeholders are not investments.
Record one source, then enrollment, then source packets/cohort, decisions, proposals:

```powershell
uv run --locked --python 3.12 --extra dev python -m research.active_equity.pilot append --pilot-dir 'PILOT' --input 'SOURCE.json' --attachment 'PUBLIC_DOCUMENT.html'
uv run --locked --python 3.12 --extra dev python -m research.active_equity.pilot append --pilot-dir 'PILOT' --input 'ENROLLMENT.json'
uv run --locked --python 3.12 --extra dev python -m research.active_equity.pilot verify --pilot-dir 'PILOT'
```

Minimal source JSON fields: `kind=source`, `source_id`, `url`, `description`,
`published_at`, `available_at`. Snapshot and content hash are computed, never
trusted from input. Enrollment fields: `kind=enrollment`, `feed_name`,
`coverage_statement`, `universe_definition`, `source_ids`, `window_start`.

Cohort: `kind=cohort`, `window_start`, `window_end`, `source_ids`,
`complete_for_declared_feed=true`, `events`. Each event: `event_id`, `cik`,
`ticker`, `sector`, `published_at`, `eligibility_asof`, `eligibility_explanation`,
`market_cap_usd`, `adv20_usd`, `us_listed`, `operating_company`, `common_stock`,
`revenue_yoy`, `operating_margin_yoy_change`, `source_ids`. Growth and margin
changes are decimal fractions. Sector vocabulary is frozen in `pilot.SECTORS`.

Decision: `kind=decision`, `decision_id`, `event_id`, `action`, `source_ids`,
`thesis`, `valuation_case`, `strongest_counterargument`, `invalidation`, `forecast`,
`horizon_end`, `model_id`, `model_version_status`, `analyst`, `confidence`,
`confidence_reason`, `supersedes` (null initially), `claims`. Each claim:
`statement`, `classification` (fact/inference/unknown), `source_locator`, `source_ids`.

Proposal: `kind=proposal`, `proposal_id`, `not_before`, `rationale`, `cash_weight`,
`targets` (complete portfolio list of `decision_id` and decimal `weight`).
An empty list with cash_weight=1 records staying in cash. Proposals are not fills,
holdings, or broker orders; omission of a prior target is not an executed sale.

## Implemented / remaining

Implemented: isolated registration CLI, frozen spec/prompt/code snapshots, serialized
append-only journal, evidence snapshots, deterministic cohort selection, comparator
classification, complete-review/target-risk checks, audit, and portable share ZIP.

Remaining: independently review/select the prospective feed and enrollment universe;
collect actual 20-company evidence; run analyst decisions; externally anchor records;
implement/test the separately frozen execution/accounting protocol. No autonomous
monitoring or model service has been enabled. Code correctness is not alpha evidence.
