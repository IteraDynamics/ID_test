# Cash-permitted portfolio diagnostic — next module

Operator approved cash permitted with explicit risk limits on2026-09-10.
Research-only, separate from frozen Core. No return or drawdown guarantee.

Use all twelve design-audit forecast/control series without choosing an ex-post
winner. Use a common rank allocation rule so rank predictions are not falsely
interpreted as calibrated expected returns. Weekly signal at close, execute next
session open, maintain continuous holdings between rebalances. Return targets
remain five sessions while holiday weeks have different rebalance lengths; the
ledger must use actual holding intervals, not concatenate overlapping labels.

Proposed fixed rule: allocate25% to each of the top3 ranked ETFs, total75% risky
budget. At the selection boundary distribute tied slots equally across tied
assets. Remaining weight goes to a separately modeled BIL holding as an investable
cash proxy, not assumed brokerage interest. Maximum25% per risky ETF at rebalance,
no leverage/shorting. Estimate252-session close-return covariance with fixed
50% diagonal shrinkage. Scale risky weights down, never up, to a10% annualized
forecast-volatility ceiling. Risk control determines cash allocation; rank sign
cannot tell us whether absolute expected returns are positive.

Include passive equal-weight75% risky/25% BIL and simple60-session momentum ranking
with the same risk rule. Forecast comparisons share identical dates, risk forecasts,
execution and10bp each-way notional trading costs including BIL trades;25bp and
one-extra-session-delay diagnostics. Include initial purchase and terminal sale.
Mark daily NAV and cost-ledger reconciliation. No simulated borrowing to pay costs.
Zero-interest residual settlement cash. BIL is an ETF position with price/distribution
risk and transaction costs, not a riskless cash-account promise. Pre2025 only.

Report CAGR, volatility, drawdown, turnover, cash-proxy allocation, annual results,
relative results versus past-mean and passive controls, excluding2020 diagnostics.
This evaluates a predefined mapping; a negative result does not rule out every
possible portfolio mapping. No search over risk targets, caps, top-k or cost rates.

Input prerequisite: adjusted BIL OHLCV plus download manifest covering2013-12-02
through2024-12-31. Inventory lists an existing BIL CSV but no adjustment manifest;
no BIL content was supplied in available sample bundles. Request an explicit
adjusted download to a new folder; do not overwrite local historical files.
Once input passes, implement ledger tests before economic evaluation.

## Implementation details recorded before economic evaluation

2026-09-10: BIL adjusted upload received. Include BIL in the nine-asset covariance
and scale risky weights against total estimated portfolio volatility. If BIL alone
exceeds the ceiling, fail rather than silently imply riskless cash.252 complete
close-to-close returns through signal close;50% diagonal covariance shrinkage.
Passive75/25 control is unscaled. The zero-score control yields equal risky weights
with risk scaling, providing the matched risk-managed passive comparison. Fourteen
policies*three fixed scenarios=42 ledgers, no model fits. Initial fundingNAV1,
first eligible next-open purchase, last eligible signal's next open liquidation.
Exclude-year diagnostics report annualized mean/variance and CE=mean-1.5*variance
(annualized;gamma3), not stitched CAGR or drawdown. No economic selection threshold
or winner promotion; report all variants and comparisons. Weight/forecast-volatility
limits apply at scheduled rebalances, not guaranteed intraperiod realized limits.
