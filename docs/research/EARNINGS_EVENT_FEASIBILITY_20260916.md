# Earnings reaction persistence — feasibility and first-test specification

Decision: continue a bounded data-feasibility test. This is a separate research
branch, research/earnings-event-feasibility-20260916, from active-equity pilot
commit 049c8399b65eff4986d05caf15b10dbba657745c. No performance result exists.
Core and the prospective analyst pilot remain unchanged. User authorized this
parallel track on 2026-09-16. Scope is data audit and first-test specification;
no source purchase, downloads, broker connection, model fitting or trading.

## Hypothesis and strongest alternative

A substantial earnings-related opening gap that survives the first full regular
session may reflect gradual incorporation of business information. A gap that
reverses may reflect an overreaction or conflicting interpretation. Test whether
this distinction predicts subsequent returns beyond ordinary momentum/reversal,
market and sector exposure. Alternatives: generic price behavior, illiquidity,
corporate-action artifacts, timestamp mistakes and selection of surviving issuers.
This is related to earnings drift, not claimed novel and not the prior EPS-surprise
screen. The prior Campaign 59 fetcher is reused as a discovery source, not validated
historical truth. Before any performance work, review prior event-test closures
and record reused observations as development data; calendar splits cannot erase
previous exposure elsewhere in Itera.

## Audit completed on the supplied file

The supplied September 15 ZIP has 15,594 rows and 213 raw tickers. Through
2024-12-31: 13,950 rows, 13,910 distinct ticker/date keys, 37 duplicate groups,
36 conflicting groups. Removing every conflicting key, collapsing exact duplicates
and excluding 60 remaining keys without finite reported EPS leaves 13,814 events
across 206 tickers. Presence of realized EPS helps distinguish reported events from
calendar placeholders; it is not proof of historical availability. No EPS surprise
is used as a signal. The post-2024 1,644 rows are counted but not evaluated.

The original fetcher explicitly drops datetime and timezone. Local per-ticker
caches made by that same script cannot recover the discarded times. Merely
re-fetching a vendor timestamp would not establish first-publication timing or
historical schedule vintage. The source universe was inherited from reconstitution
work and further filtered on existing price files: it is not an unbiased census
of historically eligible equities. Prior September 9 audit identified ticker
identity failures, truncated histories and mixed price-adjustment conventions.
This audit does not supersede those findings.

## Local runner and meaning of its output

Run scripts/local/run_earnings_event_audit.ps1 with the existing data root. It reads
only, requires no data download, and uses the exact canonical TICKER_1D.csv basename
recursively. Missing files are reported; multiple candidate paths remain ambiguous
rather than choosing one. Columns are case-insensitive; ISO dates/datetimes and
Unix second/millisecond daily labels are accepted. Provider date labels are retained;
exchange-calendar semantics still require review. Duplicate/out-of-order dates,
weekend rows and invalid OHLCV make a file structurally unusable. CSV data after
2024 are not used in coverage windows, although complete input bytes are hashed.

Outputs: report.json, price_inventory.json, coverage.csv, event_issues.csv, in one
shareable ZIP. Input files are identified by paths and SHA256; raw market data are
not bundled. Manifest paths/hashes are inventoried, not semantically certified.
A zero process exit means audit completion, not research readiness.

Coverage uses the first observed price date strictly after the event calendar date
as an observation-day proxy, requires 60 prior observed rows, then a following
entry open and open-to-open exit 1, 3 or 5 observed rows later. Counts are upper
bounds: missing exchange sessions, suspensions, historical liquidity and corporate
actions are not resolved. They do NOT establish first-session event counts.
Price files include SPY as a control-input inventory. Sector mapping is still open.
The output deliberately never claims ready_for_backtest.

## Smallest missing information and follow-up decision

For the exact hypothesis, each retained event needs verified first-publication time
(or an evidenced pre-open/after-close session classification), timezone, original
release URL/document, fiscal period, stable issuer/security identity and retrieval
provenance. Record whether an event was actually scheduled before the release; if
unavailable call it a realized-release study, not a scheduled-event strategy.
A filing acceptance time alone is not necessarily the original release time.

The next source audit should use a deterministic outcome-blind sample: sort clean
covered events by SHA256(ticker + '|' + date), inspect the first 30, report every
success and failure. This sample tests timestamp/source retrieval, not alpha or
representativeness. Do not replace inconvenient failures with later names.
No mass acquisition is warranted before this check. If adequate timing cannot be
recovered, the exact first-session hypothesis remains untested.

A date-only delayed variant is feasible in principle: observe the first full
session strictly after the listed date, enter the next open. This changes the
question for pre-open reports and must be separately named before inspecting
returns. It does not repair erroneous calendar dates or issuer selection.

## First empirical test, specified before outcomes

Conditional on audited prices, corporate actions and event timing:

- Restrict initial economic test to positive overnight earnings gaps; long/cash
  only, no assumed stock borrow. Negative gaps may receive descriptive analysis
  later but do not get credited as short returns.
- Verified pre-open release: reaction day is that session. Verified after-close
  release: next exchange session. Exclude intraday releases and ambiguous boundary
  times from this first design. Use the real exchange calendar, including holidays
  and early closes, not a weekday rule.
- Large gap: reaction open / previous close - 1 >= max(3%, 2 * sigma), with sigma
  trailing 60-session close-to-close standard deviation ending BEFORE reaction day.
  Use consistently adjusted OHLC and exclude unresolved action/distribution windows.
- Held: reaction close >= reaction open. Reversed: reaction close <= prior close.
  Intermediate events are reported separately, not silently assigned to either.
  Prices and volume of the completed reaction day become usable after its close.
- Enter at the following regular-session open with explicit adverse execution cost.
  Primary exit: open three sessions after entry. One and five sessions are declared
  sensitivity checks, not three opportunities to select the winner.
- Compare held versus reversed, all large positive earnings gaps, and non-earnings
  large-gap sessions matched on prior volatility, gap size, liquidity, market regime
  and sector. Define matching bins and exclusions using development data only.
  Include identical holding/reversal rules on those non-event controls: this isolates
  incremental event conditioning, rather than generic intraday momentum alone.
- Report raw and contemporaneous SPY/sector-relative outcomes. Benchmark subtraction
  is a diagnostic, not automatically tradable hedged P&L. A hedge needs its own trades
  and costs if promoted to a portfolio.
- Assumed total round-trip execution costs: 10, 30 and 60 bps (both legs combined),
  plus one-session delayed entry with a fixed holding horizon. These are sensitivity
  assumptions, not observed fills. Use properly adjusted prices/dividends and record
  halts/delistings; do not silently drop events whose exits are unavailable.
- Initial development description: 2019-2021; chronological robustness: 2022-2024.
  Both remain exploratory because Itera has previously used these years. No 2025+
  outcome inspection or OOS claim in this task. Timestamp coverage may necessitate a
  documented design revision before any outcomes, not a hindsight-selected subset.
- Report sample attrition, company/year concentration, event-level effect sizes and
  dependence-aware uncertainty (issuer clustering and calendar-block resampling).
  Correlated earnings dates and overlapping holding periods are not independent
  observations. Do not annualize average trade returns into a fictitious CAGR.

Continue only if the held-versus-reversed difference is economically material,
recurs across development subperiods and adds to matched non-event behavior after
costs. Otherwise reject or label underpowered, with the reason recorded. Any
portfolio follow-up must model overlapping positions, capital limits and unfilled
orders before reporting Sharpe/drawdown. ML and Monte Carlo are later questions;
resampling biased input cannot validate an edge.

## Validation

Focused synthetic tests cover conflicting keys, missing realized EPS, unsafe
symbols, price ordering/duplicates, OHLC validity, weekend bars, horizon boundaries,
ambiguous price paths, timestamp units and refusal to certify event timing.
Real uploaded earnings data are audited without any stock-return computation.
PowerShell is reviewed but not executable in this Linux environment.

Executed: seven tests passed under Python 3.12.14 / pytest 9.0.3. The full CLI
completed on the uploaded earnings CSV and generated the four-file ZIP. That
upload contains no stock prices; local price coverage is pending, not zero.
Audit evidence: evidence/earnings_event_feasibility_20260916.json.
