# HMM Regime v1 — Research Conclusion

## Status

**Research status:** closed as shadow diagnostic / attribution layer.

**Runtime status:** not approved for Fund v1 runtime integration.

**Governor status:** not approved as an exposure-control governor.

This document summarizes the HMM Regime v1 research track after correcting the artifact/frequency mismatch found during the initial governor tests.

## Executive Verdict

HMM Regime v1 produced coherent, interpretable regime labels across the Itera research universe, and the crypto composite regime language showed real attribution value. However, after correcting the target artifact and enforcing frequency guardrails, the first valid governor test produced only marginal incremental improvement over the existing calibrated crypto sleeve.

The conclusion is:

```text
HMM Regime v1 is useful as a shadow diagnostic and research lens.
It is not currently justified as a Fund v1 runtime governor or replacement regime engine.
```

## What HMM Regime v1 Validated

The research track validated several descriptive properties:

1. **Cross-surface convergence**
   - SPY 1D, QQQ 1D, BTC 1H, BTC 4H, ETH 1H, and ETH 4H all produced usable HMM fits after appropriate iteration settings.

2. **Interpretable state taxonomy**
   - Equity surfaces separated into regimes such as HIGH_VOL, VOL_COMPRESSION, TREND_UP, and RANGE.
   - Crypto surfaces separated into HIGH_VOL, TREND_DOWN, VOL_COMPRESSION, and TREND_UP.

3. **State persistence**
   - Transition and dwell diagnostics showed that states were persistent enough to be interpreted as regimes rather than pure flicker/noise.

4. **Cross-surface alignment**
   - BTC/ETH 4H alignment was strong enough to support a structural crypto regime concept.
   - 1H surfaces were useful as tactical/local diagnostics but noisier than 4H structural surfaces.

5. **Crypto composite regime language**
   - The four crypto surfaces supported a descriptive composite taxonomy:
     - STRUCTURAL_RISK_OFF
     - STRUCTURAL_CONSTRUCTIVE
     - STRUCTURAL_RISK_OFF_TACTICAL_REBOUND
     - STRUCTURAL_CONSTRUCTIVE_TACTICAL_PULLBACK
     - MIXED_STRUCTURAL_TACTICAL_RISK_OFF
     - MIXED_STRUCTURAL_TACTICAL_CONSTRUCTIVE
     - MIXED

## Corrected Attribution Result

After reconciling the correct target artifact, the valid attribution target was confirmed as:

```text
artifacts/fund_equal_cal_4s_2019-03-08_2025-12-31/equity_curves.csv
Target column: portfolio
Frequency: 1H
```

The corrected composite attribution showed that HMM regimes do separate realized forward behavior:

```text
Overall portfolio average: +0.201 bps/hour

STRUCTURAL_CONSTRUCTIVE: +1.058 bps/hour
MIXED_STRUCTURAL_TACTICAL_CONSTRUCTIVE: +0.383 bps/hour
STRUCTURAL_CONSTRUCTIVE_TACTICAL_PULLBACK: +0.122 bps/hour
STRUCTURAL_RISK_OFF: -0.195 bps/hour
STRUCTURAL_RISK_OFF_TACTICAL_REBOUND: -0.238 bps/hour
MIXED_STRUCTURAL_TACTICAL_RISK_OFF: -0.238 bps/hour
MIXED: -0.257 bps/hour
```

Interpretation:

```text
HMM composite regimes have attribution value.
STRUCTURAL_CONSTRUCTIVE is clearly favorable.
STRUCTURAL_RISK_OFF and mixed/risk-off variants are generally unfavorable.
```

## Invalidated Prior Governor Result

An earlier governor test produced extreme and misleading metrics because it used the wrong artifact:

```text
artifacts/four_sleeve_portfolio/equity_curves.csv
Target column: crypto_sleeve
Frequency: 1D
```

That daily, downstream multi-asset artifact was incorrectly joined to hourly HMM crypto composite regimes. The join used an outer join with forward-fill, effectively repeating daily returns across hourly regime rows.

That produced invalid results such as extremely high Sharpe/CAGR and near-total drawdowns. Those results are discarded.

The scripts were patched to prevent this error class:

```text
scripts/analyze_hmm_crypto_composite_performance.py
scripts/test_hmm_crypto_composite_governor.py
```

Current guardrails:

```text
- explicit --equity-curves required
- explicit --target-series required
- frequency diagnostics printed
- materially mixed-frequency joins refused by default
- inner timestamp join used instead of outer join + forward fill
- frequency diagnostics written to summary.json
```

## Corrected Governor Shadow Test

After the guardrails and correct artifact were used, the valid governor test was modest.

Baseline:

```text
Schedule: baseline_no_governor
Total Return: 212.99%
CAGR: 18.30%
MaxDD: -17.90%
Sharpe: 1.362
Calmar: 1.022
Ann Vol: 12.96%
```

Best first-pass schedule:

```text
Schedule: risk_off_only_light
Rule: STRUCTURAL_RISK_OFF = 0.75, everything else = 1.00
Total Return: 215.98%
CAGR: 18.46%
MaxDD: -17.92%
Sharpe: 1.382
Calmar: 1.031
Ann Vol: 12.86%
```

Delta versus baseline:

```text
Total Return: +2.997 percentage points
CAGR: +0.166 percentage points
Sharpe: +0.020
Calmar: +0.008
Ann Vol: -0.094 percentage points
MaxDD: slightly worse by -0.015 percentage points
```

Interpretation:

```text
The HMM governor effect is small.
It does not justify Fund v1 runtime complexity.
```

## Main Research Interpretation

The modest incremental improvement is likely because the existing calibrated crypto sleeve already embeds meaningful regime awareness, calibration, multi-timeframe diversification, BTC/ETH diversification, and exposure/risk structure.

HMM is not being applied to a naive always-long system. It is being applied on top of an already strong systematic architecture. As a result, HMM mostly confirms regime distinctions the system is already exploiting.

The best interpretation is:

```text
HMM is useful as regime explanation and attribution.
HMM has not demonstrated enough incremental value to become a direct governor.
The existing deterministic/calibrated regime architecture appears strong.
```

## Final Decision

```text
VERDICT: Archive as shadow diagnostic / research lens.
PROMOTE TO RUNTIME: No.
PROMOTE TO GOVERNOR: No.
REPLACE EXISTING REGIME ENGINE: No.
KEEP ARTIFACTS/SCRIPTS: Yes.
```

## Approved Future Uses

HMM Regime v1 may be useful for:

1. Research summaries and regime explanation.
2. Post-trade attribution.
3. Comparing current deterministic regime logic against unsupervised latent regimes.
4. Future out-of-sample / walk-forward research if needed.
5. Diagnostics for future sleeves that have weaker native regime controls.

## Not Approved

HMM Regime v1 is not approved for:

1. Fund v1 paper trading changes.
2. Direct strategy gating.
3. Exposure scaling in runtime.
4. Allocator integration.
5. Production Layer 1 replacement.

## Suggested Next Research Focus

Since HMM produced only marginal incremental governor value, research effort should return to higher expected-value areas:

1. Cross-asset portfolio construction.
2. Allocator robustness.
3. True out-of-sample / walk-forward validation.
4. Sleeve diversification.
5. Tail/drawdown behavior.
6. Capital-efficient deployment mechanics.

## Bottom Line

HMM Regime v1 was not a failure. It was a useful validation exercise.

It showed that the market-state structure inferred by an unsupervised model broadly agrees with the regime-aware behavior already embedded in Itera's calibrated crypto sleeve. The lack of dramatic improvement is evidence that the original regime/filtering design was already strong, not that HMM found nothing.

The correct outcome is to preserve HMM as a shadow diagnostic and close the governor-promotion path for now.
