# SPY condor quote accounting — 11 September 2026

**Decision: reject this fixed monthly condor as the next strategy to develop.**
Adverse-side accounting loses money before commissions, and even the midpoint
counterfactual is negative. Further leverage or an ML filter is not justified by
this baseline. The conclusion applies to this specific implementation.

## Actual input and scope

Uploaded `options_condor_panel_20260911_155041.zip`, SHA-256
`92ded2805d762c74f868dd81be6fd49708eb7dadeba9c16575c7918436edcd17`.
Both CSV hashes matched their manifest. No duplicate contract-day keys were found.
The extractor inspected 204 calendar-month candidates, 2008–2024, and selected
137. The other 67 had no eligible geometry under the declared rule. **There are
no selected positions in 2008 or 2009 and only five in 2010–2012.** This does not
establish survival through the global financial crisis.

One contract per leg, standard 100-share multiplier assumed. Contracts are selected
on the first observed session, entered at the next observed session, and scheduled
for exit at the first observed session with seven or fewer calendar days remaining
before expiration. Expiry nearest 35 DTE within 30–45; absolute short delta nearest
.16 within .05; wings nearest 2% of each short strike. No tuning was run.

## Results from 137 accounted positions

| Quantity | Result |
|---|---:|
| Entry/exit bid-ask P&L before commissions | -$4,620.00 |
| After $0.65 per contract per side fee reserve | **-$5,332.40** |
| Midpoint-entry/midpoint-exit counterfactual before fees | -$2,735.50 |
| Mean net per position | -$38.92 |
| Median net per position | +$15.80 |
| Positive net positions | 80 / 137 (58.39%) |
| Worst individual net position | -$583.20 |
| Best individual net position | +$181.80 |
| Put-spread component, after half the fees | +$549.80 |
| Call-spread component, after half the fees | -$5,882.20 |

These are aggregate dollars for one condor per eligible candidate, not percentages
on a specified capital allocation. No capital base, cash yield or financing was
invented. The midpoint result assumes unavailable price improvement; its negative
sign shows that quoted spreads alone do not explain the result. The small positive
put component is a retrospective decomposition, not an independently validated
put-only strategy or permission to pivot to one without a new design.

Net totals at per-contract/per-side fee assumptions of $0, $0.65, $1 and $2 are
-$4,620, -$5,332.40, -$5,716 and -$6,812 respectively. Fees here are explicit
sensitivity assumptions, not a verified broker quote. Other exchange fees and
assignment costs are not included.

## Important accounting correction, preserved explicitly

The initial strict pass required positive displayed size for every exit leg.
It accounted for only 78 positions and excluded 59. Those exclusions were not
missing contracts: 57 were zero-bid/zero-size long options and two had a one-cent
long bid with zero size. Excluding them would condition the sample on exit liquidity
and cannot support a strategy result.

The revised **zero-recovery accounting scenario** buys back both shorts at ask
with positive ask size. A long with zero displayed bid size receives zero recovery,
without claiming an executable sale. Residual positive optionality is discarded;
remaining long-option handling is not modeled. The full eight-fill $5.20 reserve
is still charged, making this fee treatment conservative. All 137 positions then
have accounted exits. Ordinary zero-bid long options are not treated as missing
contract histories. The initial strict report is retained separately as a diagnostic,
not used as the strategy verdict.

Daily liquidation marks are exported. One position (September 2021) has a missing
qualifying daily mark even in the revised scenario. No missing mark is replaced
with zero. An exact continuous drawdown or Sharpe is therefore not reported.
Worst individual position loss is not maximum portfolio drawdown.

## Limits and comparison with earlier claims

This is retrospective quote accounting, not independently confirmed OOS performance
or an executable broker simulation. Source session dates do not independently
verify exchange calendars, actual quote arrival time or simultaneous fills.
American exercise/assignment, dividends, contract deliverables, intraday risk and
partial fills remain unmodeled. The source's unusable `in_the_money` field is not
used. Midpoints are computed from bid/ask, not the vendor `mark` field.

The older favorable modeled-price condor study used different cadence/exit and
pricing assumptions. This study is not a controlled attribution proving that
replacing synthetic prices alone caused the performance change. Its narrower
conclusion is sufficient: the actual-quote implementation tested here provides
no economic basis for scaling or model optimization.

## Reproduce and verify

```
python -m scripts.account_options_condor_panel --bundle <uploaded.zip> --output-dir <new-directory> --zero-salvage-longs
```

Omitting the last flag reproduces the incomplete strict-size diagnostic. Outputs:
trade ledger, daily liabilities, annual dollar totals and JSON report. Two executed
synthetic tests verify credit/debit signs, midpoint arithmetic, zero recovery for
unsellable longs, and rejection of missing contracts or unavailable short closes.
The trade totals and separate put/call cash flows reconcile to within numerical
precision. Raw input hashes and reports are recorded; no annual source files were
independently rehashed in this environment.

Next research priority remains the existing month-end rebalancing-pressure
hypothesis and its unresolved trading economics, subject to its sealed-replication
charter. This options result does not change live/Core v1 positions or rules.
