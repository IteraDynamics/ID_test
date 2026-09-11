# Economic opportunity selection — 11 September 2026

Decision: prioritize a quote-grounded SPY defined-risk option-premium test.
This is the highest-value next investigation, not a finding of positive expected
returns. Stop extending the disappointing ETF exposure ladder. Keep it as a
benchmark. Three existing, unfinished economic hypotheses deserve different
treatment from the failed price-feature models.

## Ranked shortlist

| Priority | Economic opportunity; who pays and why | Evidence actually available | Principal blocker; cheapest discriminating test |
|---|---|---|---|
| 1 | SPY option premium: option buyers may pay for convexity and downside protection; sellers bear adverse moves and volatility risk. A condor also buys insurance, so net compensation is an empirical question. | Historical SPY option Parquets appear in the user's inventory for 2008–2025; only through 2024 is in scope. IV helped variance forecasts. Earlier favorable condor returns used modeled prices, not these quotes. | Audit source timing, actual spreads, contract identities and continuity. Then evaluate one inherited structure on actual quotes and conservative execution assumptions. A modeled premium that disappears at actual spreads kills that implementation. |
| 2 | Calendar rebalancing pressure: constrained investors trade to restore portfolio weights; liquidity suppliers potentially earn compensation for taking the other side. | Campaign 57 found a negative month-end relationship in 476 months. Its independent review judged it conditional, discovery-overlapping evidence; VTI/BND replication remains sealed. | Reconcile source provenance and specify executable legs, timing and economic materiality before opening the existing replication under its charter. A correlation without sufficient net P&L is not a strategy. |
| 3 | BTC/ETH funding carry: leveraged directional demand can pay the opposite side through funding; a spot/perpetual hedge seeks that payment while retaining basis, margin and venue risk. | Campaign 53 has a methodology and Deribit funding discovery history. Later dated findings resolve the previously reported Coinbase derivatives eligibility issue. No verified net carry result is established here. | Reconstruct settlement cash flows and synchronized hedge economics; Deribit observations cannot stand in for Coinbase executable historical funding. Hourly observations labeled `funding_rate_8h` must not simply be summed as hourly payments. |

The ranking is by incremental research value and present feasibility, not expected
CAGR. Month-end has the clearest existing statistical relationship. Options ranks
first because the later quote inventory can directly challenge the main assumption
behind an already explored trading structure. A new neural network would not
resolve that assumption.

## What the inventory supports

The uploaded `itera_data_inventory_20260910_144634.zip` contains 18,526 CSV
inventory records, including generated artifacts. Filtering data folders and
excluding artifacts leaves 649 records; these are not 649 independent assets.
The other-file inventory identifies the annual SPY option Parquets. The quote
files themselves are on the user's machine, not in this checkout.

There is substantial daily and hourly price history, BTC/ETH funding history,
earnings and COT material. That does not establish point-in-time coverage,
independent observations, or realistic fills. No queue/order-book execution dataset
was identified, so client-flow market making is not currently a defensible local
analogue of Goldman's aggregate trading business.

Two corrections matter. Energy and crops were feasibility/power screens with zero
actual predictor-label fits; they were not failed alpha backtests. Conversely,
the options variance and raw-IV sizing studies did not test option-premium P&L.
Neither success nor failure should be transferred between those questions.

## Options: concrete next job

Run `scripts/local/run_options_quote_review.ps1` against the existing data checkout.
It reads five fixed yearly files and exports full original quote columns for
five calm/stress inspection windows, retaining bad quotes and duplicate records.
It includes 0–90 DTE plus malformed expirations, source hashes, schemas and quality
counts. It performs no network data acquisition, model fits or return calculation;
`uv` may fetch the pinned Parquet reader dependency. It never opens a 2025 file.
Missing source files are reported, not replaced by fresh downloads.

The windows are deliberately selected for diagnosis, not a representative sample
and not a holdout. This package determines whether a credible full-history study
can be implemented. In particular, midnight dates do not certify closing quotes,
and non-midnight timestamps do not by themselves certify availability either.

If the sources pass, the initial trading comparison inherits the old 35-calendar-day,
16-delta, 2%-wing concept, mapped to listed contracts. The legacy implementation
uses 2% of each short strike for wing distance. Exact contract selection, entry
timing, exits, sizing, commissions and financing must be documented before running
the full comparison; this memo is not a same-session frozen performance charter.
Do not repeat the 60-structure optimization sweep.

Evaluate sellers at bid and buyers at ask as a conservative scenario, with
commissions on every leg. This is not a guarantee of simultaneous fills. Model
timing honestly: a next-session decision cannot use next-session closing deltas
as if known at the open. Verify unadjusted underlying prices, splits/deliverables,
dividends and American-style assignment treatment. If these cannot be established,
label the result a constrained simulation and identify what remains untradeable.

Compare quoted and previously modeled credits/losses, dependence on crisis losses,
turnover and executable costs. Report return on total committed capital including
cash and margin, drawdown, Sharpe and Calmar; do not annualize premium divided by
an arbitrarily small collateral denominator. Non-overlapping cycles are not proof
of independence. Existing inspected years remain discovery data.

Only after an economically credible baseline exists should ML estimate conditional
variance/tail risk or whether premium compensates for that risk. Require additional
net value against the same constant policy at comparable exposure. A high win rate
alone does not establish an attractive business.

## Evidence and interpretation boundaries

- [Prior research review](ML_RESEARCH_REVIEW_20260911.md).
- [Exposure results](ML_TREND_EXPOSURE_RESULTS_20260911.md): additional leverage
  degraded risk-adjusted performance; this review recommends no further scaling.
- [Options correction](ML_OPTIONS_VARIANCE_CORRECTION_20260910.md) and
  [IV sizing](ML_IV_SIZING_20260911.md): useful variance information is distinct
  from profitable allocation or option selling.
- [Old modeled VRP economics](CORE_V2_VRP_OPTIONS_DEGRADATION_BAND.md): modeled
  skew/cost sensitivity can eliminate the favorable result; not actual-quote proof.
- [Campaign 57 independent review](CAMPAIGN_57_INDEPENDENT_RED_TEAM_REVIEW_20260902.md):
  do not call discovery-overlapping history independent confirmation or open sealed
  replication as an exploratory convenience.
- [Campaign 53 dated source findings](CAMPAIGN_53_SOURCE_FEASIBILITY_FINDING.md) and
  [planning charter](CAMPAIGN_53_FUNDING_CARRY_PLANNING_CHARTER.md): use dated updates
  rather than stale eligibility summaries; power simulations are not profits.
- [NBER 33554, Unintended Consequences of Rebalancing](https://www.nber.org/papers/w33554):
  abstract supports institutional rebalancing as a plausible mechanism, not our
  particular implementation or returns. Abstract reviewed, not a full paper replication.
- [BIS Working Paper 1087, Crypto carry](https://www.bis.org/publications/working-paper-1087-crypto-carry):
  public summary links carry to leveraged demand and constrained arbitrage capital.
  Its historical returns are not deployable return estimates for this account.

No sealed replication, new performance backtest, core-runtime change, or live
trade was performed for this selection. Local quote extraction is the next
dependency. If the first idea fails its economic test, move to the second under
its existing charter rather than repeatedly tuning a losing version of the first.

Implementation verification: the extractor passed a synthetic Parquet smoke test
covering duplicate and crossed quotes, zero bids, missing quotes, malformed
expirations, exclusion of out-of-window later rows, missing source reporting,
ZIP inventory and refusal to overwrite an existing output directory. A deliberately
unreadable 2025 file was not opened. The Python command was exercised with the
pinned PyArrow 21.0.0 dependency. PowerShell itself was not executed here.
