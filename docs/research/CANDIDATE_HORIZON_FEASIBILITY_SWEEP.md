# Candidate Horizon Feasibility Sweep — 2026-08-11

## Purpose

Amendment 4 of `docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md` requires that a hypothesised
effect's decay horizon comfortably exceed the achievable decision lag before a campaign is
chartered. That rule did not exist when the current candidate inventory was built.

This sweep applies it retroactively, so that no future effort is spent on candidates that were
never reachable on this infrastructure. It is observation-only: it generates no new research
outcome and revises no existing statistical result.

## Measured decision lag

From `artifacts/paper_runtime_cadence_audit` (2026-08-10, 808 cycles): the runtime observes and
decides approximately **1.5-1.7 bar periods** after bar close, consistently across timeframes.
For hourly-derived signals this is **~1.6 hours**.

## Feasibility bands

Applied to the ratio of decision lag to expected effect horizon:

- **FEASIBLE** — lag consumes ≤10% of the horizon
- **MARGINAL** — 10% to 25%; requires an explicit lag-sensitivity test before chartering
- **INFEASIBLE** — >25%; must not be chartered without a runtime cadence change

The bands are a screening heuristic, not a substitute for a lag-sensitivity test. Jump Risk's
`medium_up` scores FEASIBLE in isolation yet the mapping still failed, because the *mapping*
combined it with the 2h `immediate` family and because measured decay is the authority, not the
nominal horizon. A FEASIBLE screen permits chartering; it does not predict success.

## Sweep

| Candidate | Horizon | Lag / horizon | Screen |
|---|---:|---:|---|
| Trend Persistence — BTC immediate | 3h | 53.3% | **INFEASIBLE** |
| Trend Persistence — ETH immediate | 3h | 53.3% | **INFEASIBLE** |
| Trend Persistence — BTC medium | 60h | 2.7% | FEASIBLE |
| Trend Persistence — BTC long | 120h | 1.3% | FEASIBLE |
| Jump Risk — immediate_any *(retired)* | 2h | 80.0% | **INFEASIBLE** |
| Jump Risk — medium_up *(retired)* | 18h | 8.9% | FEASIBLE |
| Campaign #43 A-001 — primary | 24h | 6.7% | FEASIBLE |
| Campaign #43 A-001 — secondary | 72h | 2.2% | FEASIBLE |
| Campaign #53 funding carry — estimated | ~7d | 1.0% | FEASIBLE |

## Findings

### 1. The feasibility filter inverts the Trend Persistence ranking

`TREND_PERSISTENCE_V0_FINAL.md` names the independent 3-hour BTC/ETH continuation signal as
"the central finding," and it carries the programme's strongest ranking metrics (BTC ROC AUC
0.7399, ETH 0.7137). Those are precisely the candidates this infrastructure cannot act on: a
1.6h lag consumes over half the horizon.

The candidates that survive the screen — BTC medium (60h) and BTC long (120h) — are the ones
with weaker ranking metrics and, in the long case, a WARN audit grade.

Recorded as a general lesson: **ranking strength and operational reachability are unrelated,
and this firm has been selecting on the former.**

### 2. Trend Persistence is retired, on two independent grounds

Trend Persistence v0 was already `COMPLETE — NOT PROMOTED`: every tested mapping degraded the
canonical portfolio at research lag, before any latency penalty. From
`TREND_PERSISTENCE_V0_FINAL.md`:

| Mapping | Result | CAGR | Core CAGR |
|---|---|---:|---:|
| BTC immediate gate | REJECT | 18.14% | 19.93% |
| BTC medium scaling | REJECT | 17.58% | 19.93% |
| BTC + ETH immediate gates | REJECT | 11.43% | 19.93% |

This sweep adds a second, independent reason: its strongest signals are operationally
unreachable regardless of mapping. A future remapping campaign built on the 3h candidates
would be chartered against a horizon this runtime cannot serve.

**Disposition: Trend Persistence Engine v0 is RETIRED**, not merely unpromoted. Any future work
on this family must be (a) restricted to the 60h+ candidates, and (b) chartered as new research
with its own economic case — not framed as a rescue of the 3h "central finding."

### 3. Campaign #53 clears the screen comfortably

Perpetual funding settles on an 8-hour cadence and funding persistence is measured in days to
weeks. Against a ~1.6h decision lag the consumed fraction is on the order of 1%. Campaign #53
is horizon-feasible by a wide margin, and this is the first campaign in the inventory that can
say so from evidence rather than assumption.

The Campaign #53 charter must still record its own decay-horizon estimate, cited cadence, and
feasibility margin per Amendment 4 before its specification is frozen. The estimate above is
provisional and not a substitute for that.

### 4. Campaign #43 A-001 remains screenable

The 24h and 72h horizons clear the screen. A-001's binding constraint remains what Campaign #44
recorded — only five independent event families in the severe subset — which is a support
problem, not a latency problem. Unchanged by this sweep.

## Authorization boundary

Observation-only. This sweep revises no statistical result, authorizes no campaign, and changes
no runtime, strategy, order, NAV, exposure, or production behavior. It records which existing
candidates may and may not be chartered under Amendment 4.
