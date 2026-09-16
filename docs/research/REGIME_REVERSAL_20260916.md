# Frozen regime-conditioning experiment

Implement on the existing isolated regime-reuse branch. No pre-existing source
files are changed. Core and original reversal execution are imported read-only.

Question: does the unchanged Core classifier partition the previously fixed
reversal mechanism into economically different outcomes? This is descriptive
and developmental, not a new OOS claim or proof of causation.

Freeze before inspecting conditional outcomes:
- Only the previously designated primary: stabilized 4H shock, 24-hour hold.
  The other five candidates and immediate/wait ablations are not searched.
- Original source hashes, 2020 start / 2025-12-31 terminal open, sigma window,
  shock, stabilization, position rules, and simulator remain unchanged.
- Four original scenarios: zero cost; 30 bps each way; 75 bps each way;
  30 bps each way with two-hour rather than one-hour processing delay.
- BTC and ETH remain independent 50% initial-capital sleeves, no rebalance.
- Use own-asset 4H classifier on full supplied history. Freeze label at signal
  completion, not entry or exit. Compare ALL against each of the seven original
  labels, including empty buckets. No thresholds, combinations, score cutoffs,
  or automatic selection are tuned.
- Original-trade attribution keeps the original trade sequence. State-only
  reruns apply filters to eligible orders and execute the unchanged simulator.
  Removing trades can free capital for later signals; those are different
  counterfactual paths, not just a subtraction of original trade returns.
- Report every year and both 2020–2022 / 2023–end blocks separately. Both blocks
  are already exposed development data. Entry-year attribution differs from
  mark-to-market portfolio year returns for trades crossing year boundaries.
- Causal gap sensitivity rejects signals with missing hourly observations in
  the preceding 240 hours (60 classifier bars, also covering the original
  volatility window). This does not remove all EWM influence from older gaps.
  Never screen entries using future missing prices. Existing deferred-exit,
  missing-entry, and stale-mark diagnostics remain reported.

Failure conditions: apparent benefit disappears under costs or delay; depends
on one asset/year or a few trades; sparse groups cannot support a conclusion;
gap sensitivity changes the conclusion. A better in-sample bucket alone is not
promotion evidence. No formal significance claim is made for overlapping,
dependent observations or the seven inspected labels. A surviving candidate
requires a frozen forward test on genuinely unseen data and portfolio testing.

Outputs: full/annual portfolio metrics, per-asset diagnostics and top-five
concentration, original-trade state attribution by entry year, counterfactual
trades and fills, daily NAV, input fingerprints and source lock. CSV summary
Sharpe uses zero cash return, as in the original experiment. Portfolio metrics
come from rerun ledgers, never from averaging trade bucket returns.

Run `scripts/local/run_regime_reversal.ps1` in the isolated research checkout.
No market data download and no Core runtime invocation. PowerShell itself is
not executable in the Linux validation environment; its Python entrypoint is.
