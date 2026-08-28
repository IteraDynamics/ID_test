# Campaign #55 — COT Speculative Positioning as a Contrarian Timing Signal (S&P 500 / Nasdaq-100)

## 1. Charter

### Status

**PLANNING CHARTER. Nothing frozen.** Gates 0-2 pass. Gate 3 (materiality) and Gate 4 (power)
are drafted below with real numbers, not simulated/frozen — per the charter-campaign skill's
pacing rule, a specification may not be frozen the same session it is first drafted. This
document exists to record today's real evidence and gate results honestly, not to authorize
execution.

No predictor, outcome, ranking, or economic result beyond today's discovery-stage exploration
exists. No holdout has been touched. Nothing here authorizes data acquisition beyond what
already exists locally (CFTC COT data, SPY/QQQ price history), execution, or capital action.

### Question

> Does CFTC-reported speculative (Non-Commercial) positioning in S&P 500 and Nasdaq-100 index
> futures — expressed as net position relative to open interest, ranked against its own recent
> history — predict subsequent SPY/QQQ returns in the contrarian direction (crowded long →
> lower forward return, crowded short → higher forward return), beyond what Core v1's trend
> state already captures?

### Named deficiency

"A single return source" (`docs/ITERA_DESTINATION_CHARTER.md`, Named deficiencies of Core v1):
every Core v1 sleeve harvests trend; there is no carry, value, or mean-reversion component. A
positioning-based contrarian signal is a genuinely different signal type — sentiment/crowding,
not price momentum — not a retune of the SMA trend rule. This would be a **Core v2 sleeve or
overlay on SPY/QQQ exposure, never a modification to Core v1**, which stays frozen regardless
of this campaign's outcome.

### Economic mechanism

Non-Commercial (speculative) futures positioning is a standard, long-documented gauge of crowd
sentiment among leveraged, non-hedging market participants. The mechanism for a contrarian
effect: positioning near a historical extreme reflects a crowded trade with limited fresh
buying (or selling) power left to extend it, making mean-reversion in subsequent price action
more likely than continuation. This is a widely-cited macro-trading heuristic; its existence in
the raw data does not by itself establish either that it is exploitable net of the reporting
lag, or that it survives properly-powered statistical scrutiny (see Gate 4).

### Why this is not already represented in Core v1

Core v1's SPY and QQQ sleeves are pure price-trend (SMA) strategies. They observe only price;
CFTC positioning data is a wholly separate, non-price information source about who holds the
exposure, not what the price has done. Nothing in Core v1's existing state encodes it.

### Falsification

If, on a genuinely untouched holdout (never inspected during discovery), a properly-powered
test finds no forward-return spread between crowded-long and crowded-short positioning
regimes — or a spread with the wrong sign — the hypothesis is rejected and the campaign closes,
the same standard already applied to COT gold (CLOSED 2026-08-25, wrong sign) and
cross-sectional crypto momentum (CLOSED 2026-08-26, collapsed under an outlier-robustness
check) earlier this session.

## 2. Feasibility

### Gate 0 — campaign or tuning?

Passes. Named deficiency stated above ("single return source"); falsification stated above.
Not a retune: it introduces a signal type (positioning/sentiment) that does not exist anywhere
in Core v1's SMA-trend design, applied as a new Core v2 sleeve/overlay, never touching Core v1.

### Gate 1 — horizon feasibility (Amendment 4)

- **Decay horizon**: multi-week. Discovery-stage evidence today shows the clearest, most
  consistent signal at the 12-26 week forward horizon in both markets (4-week showed near-zero
  correlation in both; see Gate 4 for why even the 26-week reading does not survive rigorous
  testing). Take the shorter end, 12 weeks (84 days), as the conservative horizon for this
  feasibility check.
- **Measured runtime cadence**: 0.5-0.6 effective bars (CLAUDE.md Hard Operating Facts,
  correction dated 2026-08-20, `docs/engineering/CORE_V1_JUMP_RISK_PAPER_CHARTER.md`), roughly
  constant across timeframes. For a daily-bar SPY/QQQ execution, this is well under 1 day of
  decision lag.
- **Feasibility margin**: 84 days / ~0.6 days ≈ 140x, vastly clearing the ~4x (25%-of-horizon)
  rule of thumb from `docs/research/CANDIDATE_HORIZON_FEASIBILITY_SWEEP.md`. Even at the
  shortest tested horizon (4 weeks = 28 days): 28 / 0.6 ≈ 47x. This is not a marginal call — the
  effect category (weekly-cadence positioning data feeding a weeks-long forward horizon) is a
  strong structural fit for this infrastructure's actual speed, the same conclusion reached for
  COT gold's identical cadence profile.

**PASS**, comfortably.

### Gate 2 — tradeability (Amendment 5)

- **Exact instrument**: SPY and QQQ — the same ETFs Core v1 already holds in its existing
  sleeves. The COT futures positions are the **signal source only**; nothing about this
  candidate requires trading S&P 500 or Nasdaq-100 futures themselves.
- **Venue**: the operator's existing brokerage, already used for Core v1's SPY/QQQ sleeves. No
  new account, no new approval tier, no new venue investigation — unlike every other idea
  chartered or informally explored this session (CDE derivatives eligibility, options-tier
  approval, IBKR for futures/spreads), this candidate requires **nothing new operationally**.
- **Research data source vs. execution venue**: these differ (CFTC public COT data vs. the
  operator's equity brokerage), but unlike the CDE funding/basis work this is not a
  cross-venue carry trade requiring a basis check — S&P 500 futures and SPY both track the same
  underlying S&P 500 Index (same for Nasdaq-100 futures and QQQ); the signal is a leading/
  contemporaneous read on institutional positioning in the *same* index SPY/QQQ already track,
  not a separate instrument whose premium might not transfer. No cross-venue basis check
  applies here.

**PASS**, cleanly — the strongest Gate 2 result of any idea explored this session.

### Gate 3 — economic materiality

Real numbers, computed today, from the actual discovery-stage results (see
`scripts/analyze_cot_positioning_signal.py` output, 2026-08-26):

- IC proxy: average |Pearson r| at the 12-week horizon across both markets = (0.0587 +
  0.0837) / 2 ≈ **0.071**.
- std(percentile signal) = std of a uniform[0,1] variable = 1/√12 ≈ **0.289**.
- std(12-week forward return), averaged across both markets ≈ **6.8%**.
- Rough active-return heuristic (single-signal adaptation of the standard IC × signal-std ×
  return-std form; not a rigorous derivation, ignores costs and turnover): 0.071 × 0.289 ×
  0.068 ≈ 0.140% per 12-week period → annualized (×52/12) ≈ **0.61%/year**.
- At $100k full-book notional: **≈$607/yr**. At a more realistic allocation (SPY+QQQ are 2 of
  Core v1's 6 sleeves, ≈1/3 of a comparable Core v2 book): **≈$202/yr**.

Stated plainly, without softening, per the skill's own instruction: this lands squarely in the
same $400-1,500/yr range every other edge examined this session has landed in (or below it, at
the more realistic allocation). Materiality alone is not a reason to stop — but it is not a
reason for urgency either.

### Gate 4 — power (Amendment 1), with multiplicity correction

Today's exploration looked at 2 markets × 3 horizons × 2 correlation statistics (Pearson,
Spearman) without correction — this must not be allowed to stand in for a real result.

**Multiplicity.** Treating Pearson as the primary statistic at each of the 6 (market, horizon)
combinations (Spearman as a robustness companion, not an independent additional test) and
applying a conservative Bonferroni correction (α = 0.05/6 ≈ 0.0083): only **S&P 500 at 26
weeks** survives (p ≈ 0.00040 at raw n = 767). Every other combination — including Nasdaq-100's
12-week reading (p ≈ 0.019), the one that looked most interesting in the earlier informal
read — fails even this raw-n multiplicity check.

**Autocorrelation.** The one survivor does not survive the next check. With weekly rebalancing
and a 26-week (k=26) holding period, each observation overlaps roughly 25 others — raw n=767
vastly overstates the effective independent sample size. Using effective n ≈ raw n / k ≈ 29.5
(the same category of correction this session's own `inject_ic` power-analysis bug, fixed
earlier in Campaign #53, exists to enforce): S&P 500 26-week collapses from t=-3.55 (p=0.00040)
to **t=-0.67 (p=0.51)** — indistinguishable from noise.

Verified by direct computation, not asserted:

```
=== Naive (raw n) ===
S&P 500      26w   r=-0.1274  n=767  t=-3.553  p=0.00040   <- only Bonferroni survivor
Nasdaq-100   12w   r=-0.0837  n=781  t=-2.344  p=0.01931   <- fails Bonferroni

=== Autocorrelation-adjusted (n_eff = raw n / holding weeks) ===
S&P 500      26w   n_eff=29.5   t=-0.674  p=0.5062
Nasdaq-100   12w   n_eff=65.1   t=-0.667  p=0.5071
```

**None of today's six (market, horizon) combinations would survive a properly-powered,
multiplicity- and autocorrelation-corrected test.** This does not contradict the earlier
robustness checks (no single-point domination, Spearman not collapsing relative to Pearson) —
those checks rule out specific artifact mechanisms; they do not establish statistical
significance, and were never claimed to.

**What this means, per Amendment 1's own remedy ("more data, a broader cross-section, fewer
gates, or abandonment"):** the failure here is structural, not a verdict on the underlying
economic hypothesis. A single time series (even two, SPY and QQQ) rebalanced weekly with
multi-week holding periods fundamentally cannot generate enough *effective* observations from
16 years of history — the same overlap problem that has recurred all session (COT gold,
cross-sectional crypto momentum). The skill's own stated preference — "prefer cross-sectional
designs to time-series ones... a cross-section of N instruments buys power that no amount of
history buys" — points at the right redesign: test the same positioning-contrarian hypothesis
across the broad cross-section of liquid CFTC-tracked futures markets simultaneously (dozens
exist beyond gold, S&P 500, and Nasdaq-100 — currencies, other index futures, Treasuries,
agricultural and energy commodities), which would (a) buy real power per unit of calendar time
instead of waiting years for more weekly SPY/QQQ-specific rows, and (b) naturally support
FDR-controlled discovery across the cross-section with a genuinely untouched holdout subset for
confirmation, the design Amendment 2 requires and that today's narrow two-market test cannot
provide.

**Verdict: underpowered as narrowly tested today. Not abandoned — redesign required before any
further specification work.** Continuing to accumulate more weekly SPY/QQQ-only history is not
the fix; broadening the cross-section is.

## 3. Frozen specification

**Not written.** Per the pacing rule, a specification may not be frozen the same session it is
drafted, and per Gate 4 above, the current (narrow, two-market, time-series) design would be
underpowered regardless. Any future specification work should start from the cross-sectional
redesign named in Gate 4, not from extending today's SPY/QQQ-only design.
