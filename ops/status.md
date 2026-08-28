# Itera Dynamics — Status

_Overwrite this file each session. This is a snapshot, not a log — history
lives in campaign-log.md and decisions.md._

**Last updated:** 2026-08-28 (first populated snapshot — prior file was an
unfilled template; campaign-log.md and decisions.md below are still
unfilled and need historical backfill from docs/research/ and
docs/ITERA_CAMPAIGN_BOARD.md — not done in this pass)

## 🔴 Needs CEO decision
- [ ] Broker choice for options-spread approval (VRP candidate): continue
      the in-flight IBKR application, or apply elsewhere (tastytrade,
      Schwab, etc.) if execution/fill quality on 4-leg spreads looks
      better there — this is the single make-or-break variable for the
      session's most material candidate. Raised by: Ops/Compliance.
- [ ] Sign off on drafting a combined Core v1+v2 Portfolio Construction
      Policy (drawdown ceiling for the combined book + a rule for when a
      candidate's tail-correlation with an existing sleeve disqualifies
      it or caps it) before Campaign #54's 15% hedge weight is treated as
      final and before VRP is ever sized. Raised by: Risk/PM.
- [ ] Approve formally chartering the defined-risk equity VRP candidate
      (SPY iron condors) as a numbered campaign — it's the most material
      candidate found this session (~$1,869-$11,212/yr vs. $400-1,500/yr
      for everything else) but has never been run through the standing
      gate process as a numbered campaign. Raised by: CIO.

## 🟡 Blocked (no action available from CEO)
- Campaign #53 funding-carry confirmation — blocked on the CDE live-forward
  funding holdout accumulating enough data (started 2026-08-24, a few days
  in as of 2026-08-28; not backfillable). Owner: CIO/Quant Researcher.
- Campaign #53 basis/structural leg — blocked on ~1 month (one full roll
  cycle) of live ladder-logger accumulation. Owner: CIO/Quant Researcher.
- VRP options-spread approval itself (once broker is chosen above) — an
  external, clock-bound approval with no stated ETA. Owner: Ops/Compliance.
- Track record duration for due-diligence-grade reporting (T2/T3
  degradation triggers, a meaningfully-powered Jensen's alpha) — needs
  ~12+ months of live NAV; only ~7-8 weeks exist. Pure calendar clock, no
  work item. Owner: Performance.

## 🟢 In motion (no action needed)
- Core v1 paper runtime running unattended since 2026-07-07, no manual
  intervention required, replay-identity verified on all governed runs.
- Monthly letter series — Letter #003 (first proper month-end letter,
  through 2026-08-31) due once August closes.
- Independent re-measurement of the corrected runtime-cadence finding
  (direct BTC 1H, not proxied through 4H) needed before Jump Risk /
  Trend Persistence reopening can be formally decided — flagged by
  Ops/Compliance, not yet a CEO decision point.

## Fund constraints (keep current)
- Jurisdiction: US — Binance (451) and Bybit (403) unreachable. Reachable:
  Deribit, OKX (~92-day cap), Hyperliquid, dYdX, Coinbase.
- Execution venue(s): Coinbase Derivatives Exchange (CDE) for crypto
  perpetual-style futures — derivatives eligibility approved 2026-08-14.
  Coinbase (spot) has no equity-options capability; an IBKR (or
  equivalent) account is separately in progress for options spreads.
- Capital scale: ~$100k (not yet deployed anywhere — Core v1 is paper-only,
  Core v2 has no runtime or paper account at all).
- Runtime cadence: ~0.5-0.6 effective bars behind bar close (corrected
  2026-08-20; previous ~1.5-1.7 figure was a measurement-script bug).
  ETH figure is a direct hourly measurement; BTC figure is still proxied
  through the 4H sleeve, no direct BTC 1H measurement exists.

## Open deficiencies (Core v2, per the One Rule)
1. Structurally long-only — addressed by Campaign #54 (`crash_short_v6`),
   included in Core v2's founding composition at 15% hedge weight, but
   the weight is judgment-bound on one clean crisis episode (2018); 2022
   is plausibly circular, 2020 fired but was unprofitable. Placeholder,
   not final — pending the Portfolio Construction Policy above.
2. Single return source — addressed by Campaign #53 (funding/basis carry,
   discovery-clean, confirmation pending the clock-bound holdout above)
   and, informally, by the not-yet-chartered VRP candidate.
3. No rates/fixed-income exposure — OPEN. Zero raw material exists in the
   repo. The Campaign #55 cross-sectional COT remedy also confirmed the
   CFTC Treasury complex was permanently retired in 2022, closing off
   that specific path to this deficiency.
4. Single-name crypto concentration — addressed by Campaign #53's
   cross-sectional CDE design (BTC/ETH in scope now; 8 more names
   deferred pending longer native CDE history).
