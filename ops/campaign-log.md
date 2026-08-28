# Itera Dynamics — Campaign Log

_Append-only. Never rewrite past entries — if a conclusion changes, add a
new entry that references the old one._

_Backfilled 2026-08-28 from `docs/ITERA_CAMPAIGN_BOARD.md` on first use of
this log — entries below predate the ops/ tracking infrastructure itself,
so dates and detail come from the campaign board and each campaign's own
document, not from a decision made through this log._

## Campaign #52 — Core v1 Chronological State Value
- **Chartered:** ~2026-08 — by CIO/Quant Researcher, addressing deficiency n/a (methodology check on Core v1, not a Core v2 deficiency)
- **Status:** CLOSED_NEGATIVE (DEVELOPMENT_NEGATIVE)
- **Summary:** Tested whether canonical Core v1 derives material value from authentic chronological alignment of sleeve-level pre-execution signed target exposures, via a governed lag/static/permutation control family.
- **Result:** Canonical beat static and permutation-median controls on all three primary endpoints, but no lag comparison survived Holm adjustment across the full 20-control family. Backtest ceiling caveat: this is a robustness check on Core v1's existing backtest, not a new return claim.
- **Red Team verdict:** n/a (methodology/robustness campaign, not a new-alpha candidate)
- **What killed it / what kept it alive:** Frozen lag rule failed under Holm correction — development gate did not pass. Validation stays sealed; Core v1 unaffected either way.

## Campaign #54 — Macro-Confirmed Crash-Short Hedge Sleeve (`crash_short_v6`)
- **Chartered:** 2026-08-13 — by CIO, addressing deficiency 1 (structurally long-only)
- **Status:** CLOSED_POSITIVE
- **Summary:** Evaluated `crash_short_v6` (existing, uncoded-into-Core-v1, seven-gate short entry with cross-asset SPY confirmation) as a genuine diversifying return source for Core v2, run via a 0-25% hedge-weight sizing sweep — no perturbation of the strategy itself.
- **Result:** Sharpe 1.206, Calmar 1.094, MaxDD -15.75% at 15% hedge weight. Backtest ceiling caveat: thin evidentiary base — one clean payoff (2018), one plausibly-circular payoff (2022, strategy's own gate was built examining this episode), one correctly-fired-but-unprofitable case (2020).
- **Red Team verdict:** Adversarial review (2026-08-14) found the 2022 evidence plausibly circular (hindsight pattern-match risk); 2018 is the one uncontaminated observation and the campaign's real evidentiary anchor.
- **What killed it / what kept it alive:** Sizing sweep was monotonic with no visible peak across 0-25% — chose 15% deliberately rather than chasing the still-climbing curve past what one clean crisis observation supports.
- **Risk/PM note:** Included in Core v2's founding composition at 15% hedge weight — **this is a Core v2 composition/weight decision; escalation matrix requires CEO approval for this category. No verbatim CEO sign-off exists in this log** — the decision predates `ops/decisions.md`. Flagging for CEO awareness now rather than treating it as quietly settled.

## Campaign #53 — Perpetual Funding and Basis Carry
- **Chartered:** 2026-08-20 (planning), frozen spec 2026-08-20 — by CIO, addressing deficiencies 2 (single return source) and 4 (single-name crypto, partially — narrowed to BTC/ETH 2026-08-14)
- **Status:** OPEN
- **Summary:** Delta-neutral funding-rate harvesting on Coinbase Derivatives Exchange (CDE), BTC/ETH. Discovery on Deribit's multi-year funding history (CDE's own history is only ~13 months), confirmation against CDE's native live-forward-accumulated data. Split into a statistical family (funding level/persistence) and a structural family (basis/calendar-spread).
- **Result (interim, discovery only):** 3-hypothesis statistical family (after excluding `funding_level_24h` as a near-tautology) all cleared FDR discovery (q=0.10). Top-2 shortlist: `funding_level_72h` (r=0.6347), `funding_persistence_72h` (r=0.1922). Basis family: tiny real magnitude (BTC ≈-3.2bps, ETH ≈-10bps), liquidity concentrated in front-month only. **No confirmed finding yet** — holdout accumulation only began 2026-08-24 (statistical) / 2026-08-25 (basis ladder), nowhere near enough data.
- **Red Team verdict:** Not yet run — confirmation-stage gate, pending sufficient holdout accumulation.
- **What killed it / what kept it alive:** Still open; power simulation cleared at 56.0% average power (2026-08-24) after two corrections to the original design (window set and confirmation shortlist both narrowed on mechanistic, effect-independent grounds).

## Campaign #55 — COT Speculative Positioning as Contrarian Timing Signal (SPY/QQQ)
- **Chartered:** 2026-08-26 — by CIO, addressing deficiency 2 (single return source)
- **Status:** CLOSED_NEGATIVE (clean null, not underpowered)
- **Summary:** Original 2-market x 3-horizon design was underpowered (Gate 4). Rebuilt as a cross-sectional design across the live CFTC universe (35/37 candidate markets resolved by exact name after fixing a substring-match bug), pre-registered discovery/confirmation split with a 40% untouched holdout.
- **Result:** Mean rho +0.0116 at the primary horizon — wrong sign for the contrarian hypothesis. Effective breadth only 5.1 independent markets out of 21 (measured, not assumed). 4 of 10 FDR "survivors" had the correct sign; the rest were a softs/grains momentum cluster. Untouched 40% holdout never spent.
- **Red Team verdict:** n/a (killed on its own pre-registered terms before reaching a candidate Red Team would review)
- **What killed it / what kept it alive:** Wrong-sign mean effect at the primary pre-registered horizon and statistic — closed as a line of research; reopening needs a different signal construction, not another pass at this one.

## Non-numbered candidates (screened, never chartered)

### Defined-risk equity VRP (SPY/QQQ iron condors)
- **Screened:** 2026-08-25/26 — addressing deficiency 2 (single return source)
- **Status:** OPEN (pre-charter) — strongest single-candidate result of the session
- **Summary:** SPY iron condor (16-delta, 2% wings, 35 DTE, held to expiration), Black-Scholes priced against 12.7 years (127 non-overlapping cycles) of real SPY closes and VIX.
- **Result:** 88.2% win rate, mean $103.52/cycle, p<0.000001. Survives moderate skew+cost ($59.73 net/cycle) and steep-skew-only stress; fails only under the joint pessimistic (steep skew + wide/crisis cost) case, which is a stress scenario, not a base case. Materiality: ~$1.9k-$11k/yr depending on risk budget (2%-10%) — an order of magnitude above every other candidate this session. Backtest ceiling caveat: flat historical backtest against a hypothetical held-to-expiry seller; real fills, real skew data, and IBKR-specific costs are not yet verified.
- **Red Team verdict:** Not yet formally run as an independent gate; the sensitivity/robustness work (skew sweep, structure sweep, cash-secured-put fallback test) was done by the same research thread that built the candidate. **Should go through independent Red Team before being called "alive," per the mandatory-gate rule** — has not happened yet.
- **What's keeping it from Gate 5:** Gate 2 (options approval tier) pending IBKR account opening (in progress, operator-owned); real commission/fill verification against IBKR's rate sheet; cash-secured-put fallback (lower approval tier) tested and fails outright (not one delta reaches significance) — spread-level approval is a hard gate, no lower-tier path around it.

### CFTC COT gold speculative positioning (GLD)
- **Screened:** 2026-08-25 — addressing deficiency 2
- **Status:** CLOSED_NEGATIVE (clean null)
- **Summary:** Non-Commercial net position percentile vs. forward GLD returns, 3-day report-release lag applied.
- **Result:** First run (expanding since-1986 percentile) looked promising but had a real methodological bug (quintile shares 46%/12.6%, not ~20%). Fixed via 156-week trailing rolling window; corrected correlations collapsed an order of magnitude (+0.016/+0.045/+0.067).
- **Red Team verdict:** n/a — self-caught methodological artifact, closed before reaching candidate status.
- **What killed it:** Quintile spread too small relative to return-distribution noise for any significance test to plausibly rescue.

### Cross-sectional crypto momentum (Coinbase spot)
- **Screened:** 2026-08-26 — addressing deficiency 4 (single-name crypto concentration)
- **Status:** CLOSED_NEGATIVE (clean null)
- **Summary:** Point-in-time eligible-universe cross-sectional momentum, formation/holding horizon grid (2w/4w/12w x 1w/4w/12w).
- **Result:** First run's negative-spread pattern was almost entirely an artifact of a too-low universe-breadth threshold clustered in the 2020-21 alt-season. Fixed threshold revealed a smaller positive pattern — which itself collapsed under median-based leg aggregation (immune to single-coin outlier domination): 6 of 9 grid cells flipped negative, all win rates fell to coin-flip range.
- **Red Team verdict:** n/a — self-caught outlier-domination artifact (one coin's +1377% move drove ~98% of a leg's mean).
- **What killed it:** Not a broad repeatable tendency — a small number of idiosyncratic single-coin events amplified by mean aggregation.
