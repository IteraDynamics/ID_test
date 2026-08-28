# Itera Dynamics — Status

_Overwrite this file each session. This is a snapshot, not a log — history
lives in campaign-log.md and decisions.md._

**Last updated:** 2026-08-28

## 🔴 Needs CEO decision
- [ ] **Charter VRP (defined-risk SPY/QQQ options premium) as a formal numbered campaign now, or hold it pre-charter until the IBKR account is live?** It's the strongest single-candidate result of the session (88.2% win rate, p<0.000001, survives realistic cost+skew stress, ~$1.9k-$11k/yr depending on risk budget — an order of magnitude above every other candidate this session). The research is essentially done (premium mechanism understood, structure robustness swept, skew/cost sensitivity resolved); what's left is account-gated, not research-gated. Chartering now vs. waiting doesn't change what work happens next, but it does change whether this is tracked as a real campaign number or stays an unnumbered side-investigation — worth your call rather than staff defaulting one way.

## 🟡 Blocked (no action available from CEO)
- Campaign #53 statistical family (funding level/persistence) confirmation — owner: Quant Researcher — blocked on CDE live-forward holdout accumulation, logging since 2026-08-24 (~4 days in as of today; nowhere near enough to confirm anything, not backfillable). Passive, no CEO action.
- Campaign #53 structural family (basis/calendar-spread) — owner: Quant Researcher — blocked on ~1 full roll cycle (~1 month) of live basis-ladder data, logging since 2026-08-25.
- VRP Gate 2 (options approval tier) — owner: Operator (external, already in motion) — IBKR account opening in progress; also needs real commission/fill-rate verification against IBKR's actual rate sheet once open (current $0.65/contract/leg figure is recalled, not verified).
- Campaign #53 rates/fixed-income gap — no live CFTC COT name exists for the Treasury complex (retired 2022-02-01, no successor). No path identified yet; not actively being chased.

## 🟢 In motion (no action needed)
- Campaign #49 passive prospective accumulation continuing under locked method (`9203b6f2...`).
- Campaign #53 discovery-side work is otherwise complete for BTC/ETH (3-hypothesis statistical family cleared FDR discovery; top-2 shortlist `funding_level_72h`, `funding_persistence_72h`).
- Core v2 charter remains DRAFT per the one-day pacing rule — no action needed until next review.

## ✅ Since last time (baseline — first briefing under this ops setup)
- Campaign #55 (COT index positioning, contrarian) — CLOSED, clean null on a pre-registered cross-sectional redesign (2026-08-27).
- Campaign #54 (crash-short hedge) — CLOSED POSITIVE, `crash_short_v6` included in Core v2's founding composition at 15% hedge weight (2026-08-20).
- Campaign #52 (Core v1 chronological state value) — CLOSED, DEVELOPMENT_NEGATIVE; validation stays sealed (2026-08-19/20).
- CFTC COT gold contrarian signal — CLOSED, clean null after a real percentile-window bug was caught and fixed (2026-08-25).
- Cross-sectional crypto momentum (Coinbase spot) — CLOSED, clean null after two real artifacts (universe-breadth threshold, mean-vs-median outlier sensitivity) were caught and fixed (2026-08-26).
- Defined-risk equity VRP — extensive real backtest work (2026-08-25/26), not yet chartered as a numbered campaign; see 🔴 above.

## Fund constraints (keep current)
- Jurisdiction: US — Binance (451) and Bybit (403) unreachable; Deribit, OKX (~92-day cap), Hyperliquid, dYdX, Coinbase reachable.
- Execution venue: Coinbase Derivatives Exchange (CDE) — distinct from Coinbase International (INTX). Derivatives eligibility approved 2026-08-14.
- Capital scale: ~$100k. Every edge examined to date lands ~$400-1,500/yr, except VRP (~$1.9k-$11k/yr depending on risk budget).
- Runtime cadence: ~0.5-0.6 effective bars behind bar close (corrected 2026-08-20; supersedes the earlier ~1.5-1.7 bar figure, which came from a buggy audit script).

## Open deficiencies (Core v2, per the One Rule)
1. Structurally long-only — **addressed**: Campaign #54 (`crash_short_v6`, 15% hedge weight, CLOSED 2026-08-20).
2. Single return source — **in progress**, two threads: Campaign #53 (funding carry, discovery done, confirmation pending holdout) and VRP (options premium, research done, pending Gate 2/account).
3. No rates/fixed-income exposure — **open**, unaddressed. No live venue path found (CFTC Treasury complex has no successor name post-2022 retirement).
4. Single-name crypto concentration — **open**. Campaign #53 originally scoped cross-sectionally but narrowed to BTC/ETH only (2026-08-14, CDE history depth); cross-sectional crypto momentum idea closed as a null (2026-08-26).
