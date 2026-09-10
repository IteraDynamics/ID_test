# Eight-ETF breadth and neural training development

Recorded before fitting, 2026-09-10. Continues the authorized development program.
Prior results unchanged. No Core, runtime, capital or reserved-2025 use.

SPY, QQQ, GLD plus adjusted IWM, EFA, EEM, IEF, TLT. Require manifests and matching
2013-12-02 through 2024-12-31 calendars, finite positive OHLC, nonnegative volume,
unique ordered dates. Permit only OHLC-envelope rounding within 1e-10 times close,
without altering values. Preserve source hashes. Adjusted units are synthetic.

Keep original eight candidates, five-session next-open target, weekly validation,
daily training, two inner years and seven outer years 2018–2024. Expand identity
flags to eight. Preserve training-label and inner-label New Year purges.

Neural epoch selection uses final 52 training dates as a stopping segment,
weekly stopping observations, training labels ending before the segment starts.
Scaler fits only on the preceding training segment. Adam .001, alpha .1,
batch128, seed17, original widths16/(32,16). Shuffle training rows only.
Inspect loss every five epochs, maximum200, patience25 epochs, improvement1e-10
return-squared units. Record all inspected losses and cap hits. Reinitialize and
refit all admissible training rows for the selected epoch count. Outer outcomes
never choose epochs. No random validation split.

Budget:168 candidate evaluations =84 ordinary fits +84 neural epoch-selection
fits +84 neural refits =252 optimizer fits. No extra seed or size search.
Synthetic tests do not inspect market outcomes. Failed real attempts count.
Select on row-weighted inner MSE with deterministic name tie break. Keep all
candidates and zero/per-ETF past-mean controls visible. Report errors, curves,
selections and hashes. Breadth and training change together: no causal attribution
of differences versus version1. One seed cannot settle an architecture comparison.

All years are inspected development data. Correlated assets and overlapping labels
are not independent samples. No significance, economic or production claim.
Portfolio construction remains a separate module, not an automatic forecast mapping.

Preflight before any fits: 126 stopping dates left insufficient early-fold history.
Use52 dates for every stopping segment, preserving at least252 fitting dates.
