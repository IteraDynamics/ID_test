# Trend exposure mapping: fixed exploratory specification

2026-09-11. Preserve the completed trend signals, monthly dates, relative risky
weights and source identities. No model fits, new signals, or return target.
Not an independently held-out or formally frozen campaign.

Scale each original post-risk-limit risky target by1,1.5,2,2.5,3,4. BIL receives
max(0,1-sum risky weights); borrowing finances excess risky exposure. Never borrow
to buy BIL. Also show2x with risky exposure capped at100%, retaining relative
weights. These multipliers change capital exposure, not the signal's timing.
The original10% forecast risk ceiling consequently scales; do not silently
rescale targets back to10%. Peak scheduled gross risky exposure cannot exceed
3x equity at4x scaling, before drift.

Primary financing assumption:8% annual on actual outstanding debit balance,
ACT/365 over calendar days, paid before the next open. Sensitivities4%,12%.
These are transparent fixed hypothetical financing scenarios, not historical
broker quotes or a verified financing arrangement. Positive idle balances buy
BIL; observed fund returns are retained. Costs10bps per dollar bought/sold;
stress25bps, and one-session additional order delay at10bps/8% financing.
Self-financing targets are fractions of equity AFTER trading fees. Reconcile
overnight and intraday P&L, fees, financing and net equity each session.

Margin safety assumption: equity/gross market value below30% at a daily open
triggers full liquidation and cessation of trading for the remaining simulation.
Terminal cash then earns zero; this is a conservative stylized stop, not a broker
margin model. Daily data cannot resolve intraday calls or fill availability.
Report breach count, date, maximum realized gross, and debit. Ruin fails loudly.

Compute CAGR, volatility, drawdown, longest time below a high-water mark,
recovered-episode durations and unrecovered terminal duration, turnover, financing
paid per initial dollar, yearly returns and ex2020 moments. All paths use the
same primary start and terminal dates; delayed orders share the terminal date.
Verify1x reproduces the existing cost10 trend path.

Additional deterministic diagnostics (not probabilities or reconstructed markets):
replay the primary daily asset contribution and financing mechanics under doubled
risky close-to-open and open-to-close percentage price moves, keeping historical
signal targets fixed. Rebuild synthetic prices consistently through each day's
open/close sequence; BIL unchanged. This conditions on original decisions and
cannot capture a model's response to a different history. Report separately.
Also compute instantaneous equity losses under simultaneous10%/20% risky-asset
price gaps at the maximum observed gross exposure; no predicted maximum loss.

Show the entire ladder, not an optimized winner. The question is whether net
return increases materially with exposure and where financing/stress fragility
changes the decision. User drawdown tolerance remains undecided. No capital,
borrowing, broker, execution or live-risk authorization is inferred.
