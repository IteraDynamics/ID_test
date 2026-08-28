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

**Correction, 2026-08-20: this figure was measured by a script with a bug** (subtracted each
bar's start label instead of its close, and separately averaged in stale re-logs of unchanged
bars — see `docs/engineering/CORE_V1_JUMP_RISK_PAPER_CHARTER.md`'s "Correction, 2026-08-20" for
the full finding and `tests/test_paper_runtime_cadence_audit.py` for the regression tests).
Corrected, restricted to the first cycle each bar was ever observed: **~0.5-0.6 hours**, roughly
constant across timeframes rather than scaling with bar size as originally stated.

**The Sweep table below was scored against the old, wrong 1.5-1.7 figure and has not been
recomputed.** At minimum, the lag/horizon ratios for the two INFEASIBLE 3h rows and the
INFEASIBLE Jump Risk `immediate_any` row would roughly *halve to a third* at the corrected
~0.6h lag (e.g. Trend Persistence immediate: 0.6h/3h ≈ 20% instead of 53.3% — MARGINAL, not
INFEASIBLE outright; Jump Risk `immediate_any`: 0.6h/2h = 30% instead of 80% — still above the
25% INFEASIBLE line but far closer to it). Whether any of these actually re-screen as MARGINAL
or FEASIBLE requires re-running this sweep's own methodology with the corrected number, which
this correction does not do. Treat every verdict in the table below as provisional until that
re-run happens.

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

## Re-run, 2026-08-28 — real corrected-cadence measurement, not a projection

The 2026-08-20 correction above estimated what re-scoring would look like ("~0.6h lag") without
actually re-running this sweep's own methodology. This section does that re-run, against a fresh
live measurement, not the projection.

**Source:** `scripts/run_paper_runtime_cadence_audit.py` (the corrected v2 script, fresh-bar-only
methodology) against paper export `/opt/itera/app/artifacts/core_v1_paper_export/20260828T131010Z`
(cycle 1227, i.e. 2026-08-28 — a new export, not a re-analysis of the old 808-cycle run). Measured
fresh-bar-only medians: BTC_4H_trend/ETH_4H_trend 0.5682h, ETH_1H_trend 0.5646h — consistent with
the ~0.5-0.6h range already cited, now with an exact, dated, sourced figure rather than a range.
A representative lag of **0.5682h** (the higher, more conservative of the two, both crypto assets
Jump Risk/Trend Persistence's immediate-horizon candidates depend on) is used below, matching this
sweep's own original convention of applying one lag figure uniformly rather than per-asset.

| Candidate | Horizon | Lag / horizon (corrected) | Screen (corrected) | Screen (original, 1.6h) |
|---|---:|---:|---|---|
| Trend Persistence — BTC immediate | 3h | 18.94% | **MARGINAL** | INFEASIBLE |
| Trend Persistence — ETH immediate | 3h | 18.94% | **MARGINAL** | INFEASIBLE |
| Trend Persistence — BTC medium | 60h | 0.95% | FEASIBLE | FEASIBLE |
| Trend Persistence — BTC long | 120h | 0.47% | FEASIBLE | FEASIBLE |
| Jump Risk — immediate_any *(retired)* | 2h | 28.41% | **INFEASIBLE** (unchanged, but 80.0%→28.4%) | INFEASIBLE |
| Jump Risk — medium_up *(retired)* | 18h | 3.16% | FEASIBLE | FEASIBLE |
| Campaign #43 A-001 — primary | 24h | 2.37% | FEASIBLE | FEASIBLE |
| Campaign #43 A-001 — secondary | 72h | 0.79% | FEASIBLE | FEASIBLE |
| Campaign #53 funding carry — estimated | ~7d | 0.34% | FEASIBLE | FEASIBLE |

**What actually changed:** Trend Persistence's two 3h "central finding" candidates cross the
MARGINAL/INFEASIBLE boundary (53.3%→18.94%, under the 25% line). Jump Risk's `immediate_any`
narrows sharply (80.0%→28.4%) but does **not** cross the INFEASIBLE line — it remains just above
the 25% threshold, close enough that a small further reduction in measured lag (or a genuinely
independent re-measurement landing lower than 0.5682h) could flip it, but this re-run does not
flip it on its own.

**What this does NOT resolve, per the 2026-08-28 Red Team review of the same source data:**

1. This is fresh data through the *same* audit script as the 2026-08-20 correction — a second
   latent bug in that script would reproduce identically here. It closes the "stale data" gap,
   not the "independent methodology" gap the reopening conditions below still require.
2. BTC has no direct 1H measurement anywhere in this export — its figure remains a proxy through
   the BTC_4H_trend sleeve, unchanged from every prior citation.
3. The fresh-bar-only max for BTC_4H_trend/ETH_4H_trend (3.6747h) does not match the previously
   documented ~12-hour-outage max (3.46h) from the earlier export/window. Red Team flagged this
   as **unverified** — it may be the same known outage recurring in overlapping data, or a new,
   undiagnosed gap — and this has not been checked against the raw `cadence_rows.csv` timestamps.
   Treat the medians above as solid; treat the tails as unconfirmed pending that check.
4. Jump Risk's own model-inference latency has never been logged, because it has never run live
   (T3/T4 in the audit script's own output are explicitly "NOT LOGGED... bounded above by T5, not
   invented"). Even a fully cleared cadence number is silent on whether inference time alone
   would re-consume the narrowing buffer above.

**Disposition:** this re-run does not reopen Trend Persistence or Jump Risk by itself, and does
not authorize any campaign, runtime, or strategy change (see Authorization boundary below,
unchanged). It resolves the "hasn't this sweep been re-run against a stale placeholder" question
with a sourced, dated answer: Trend Persistence's 3h family screens MARGINAL, not INFEASIBLE, as
of this measurement; Jump Risk's `immediate_any` remains screened INFEASIBLE, materially closer
to the line than previously stated. Whether either candidate is worth a real reopening campaign —
including the independence, BTC-proxy, and inference-latency gaps above, none of which this
re-run closes — is a separate, deliberate decision, not a consequence of this arithmetic.

## Authorization boundary

Observation-only. This sweep revises no statistical result, authorizes no campaign, and changes
no runtime, strategy, order, NAV, exposure, or production behavior. It records which existing
candidates may and may not be chartered under Amendment 4.
