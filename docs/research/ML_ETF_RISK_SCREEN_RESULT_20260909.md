# ETF risk-allocation screen — SCREEN_NEGATIVE

2026-09-09. Completed the fixed Amendment 6 exploration screen recorded in
[the screen card](ML_ETF_RISK_SCREEN_20260909.md). No predictor, model, exposure,
cost or classification threshold was selected after seeing the result. Exactly
14 annual fits: logistic regression and histogram GBM, 2018–2024. No additional
fits during cached replay. Close this hypothesis; no performance-driven rescue.

## What was tested

Predict a 5% loss from next-session adjusted open to any of the next 21 adjusted
closes. Translate each ETF probability into exposure clip(1-p, 0.25, 1), within
its fixed one-third portfolio budget. Compare with five controls under the same
continuous, self-financing accounting: constant 100%, 75%, 50%, SMA200 trend, and
10% volatility target. Primary criterion is annual certainty equivalent (CE),
252*mean(daily net return) - 1.5*252*sample variance; this is a research utility
proxy, not a return or the operator's preferred utility function.

All SPY/QQQ/GLD files have matching auto_adjust=True manifests and 2,789 identical
sessions from 2013-12-02 through 2024-12-31. No duplicate dates, invalid OHLC,
nonfinite values, negative volume or zero-volume rows in that interval. All
later rows were quarantined before features and economic use. Input hashes are
recorded in report.json. Features use 200 prior closes. Annual training excludes
any label whose end reaches the year's first weekly signal. One-hot identity
and eight price-derived predictors follow the card.

361 weekly forecast dates (1,083 ETF forecast rows), 2018-01-05–2024-11-29;
360 holding intervals, 2018-01-08 open through 2024-12-02 open. The last eligible
weekly signal liquidates the portfolio; its forecast is still scored. Its full
21-session label fits inside 2024. Delay sensitivity shifts all entries and the
final exit one actual session, ending December 3. Daily labels overlap and ETF
outcomes are correlated: rows and positive-label runs are support diagnostics,
not independent trials. Fold support lists those runs per ETF/year.

## Forecast results

Negative Brier skill means worse squared probability error than the ETF-specific
past-frequency forecast fitted from identical training rows.

| Model | 2018–2020 Brier skill | 2021–2024 Brier skill | Full Brier skill |
|---|---:|---:|---:|
| Primary logistic | -11.04% | -1.14% | -5.23% |
| Secondary GBM | -1.39% | -0.07% | -0.62% |

Full Brier scores: past frequency 0.154584; logistic 0.162667; GBM 0.155535.
Neither learned model improved Brier skill in either half. Fixed five-bin
calibration, log loss, annual and per-ETF diagnostics are included in the CSVs.

## Allocation results at 10bp per traded notional

Synthetic adjusted-price units; cash earns zero; initial purchases and final
liquidation charged. CAGR and CE use 252-session annualization. Constant 100%
is a weekly equal-weight rebalanced control, not a never-rebalanced buy-and-hold.

| Policy | Net CAGR | Annual CE | Annual volatility | Max drawdown | Average exposure |
|---|---:|---:|---:|---:|---:|
| Constant 100% | 14.92% | 11.48% | 15.61% | -23.15% | 99.94% |
| Constant 75% | 11.22% | 9.27% | 11.70% | -17.71% | 74.99% |
| Constant 50% | 7.49% | 6.62% | 7.80% | -12.03% | 50.02% |
| SMA200 trend | 12.09% | 10.10% | 11.44% | -17.36% | 82.17% |
| Volatility target | 8.00% | 6.99% | 8.42% | -14.59% | 65.82% |
| Primary logistic | 10.76% | 8.80% | 11.96% | -20.09% | 83.74% |
| Secondary GBM | 11.69% | 9.55% | 12.30% | -19.57% | 82.53% |

Logistic's full CE lift over the best of five controls is **-2.68 percentage
points**, against a required **greater than +0.50 points**. It also trails the
best control in each half: -3.86 and -1.78 points. The constant-75% control has
both higher CE and a shallower drawdown than logistic in this sample. Reducing
market exposure alone explains some risk reduction; learned timing has not
established incremental value.

At 25bp costs the full CE lift is -2.83 points; with an extra-session execution
delay it is -2.37 points. Excluding 2020 it remains -1.97 points. Excluding each
other calendar year also leaves a negative full CE lift (range across all seven
exclusions: -3.77 to -1.97 points). No crisis-year exclusion rescues this result.
Exclusions remove observations from the continuous original ledger; they do
not refit, restart or stitch a fictitious investment path. Therefore exclusion
rows intentionally omit CAGR/drawdown. Per-ETF contributions are additive daily
return contributions including allocated fees, not standalone asset CE.

## Decision and limits

**SCREEN_NEGATIVE.** Both primary forecast and economic hurdles fail. GBM is a
secondary diagnosis and cannot rescue the primary screen; it also falls short
of the full-period CE hurdle. This closes the specified price-only ETF
risk-timing hypothesis. It does not establish that ML in general cannot work.
No Core v1, runtime, paper portfolio, weights or capital changes.

The sample is short, historically inspected, and uses retrospectively selected
funds. Costs are assumptions; adjusted units embody provider reinvestment;
zero cash return is a research proxy. No significance, causal, live-tradeability
or independent validation claim. An interest-bearing cash treatment was reserved
for any apparent positive result; none occurred. Do not spend the reserved 2025
holdout on this failed candidate.

## Verification and files

26 tests passed: 12 temporal/accounting/input tests plus 14 packaging checks.
Synthetic tests caught and corrected a cash-accounting defect before any real
fits. All seven artifact hashes verified. Cached prediction replay reproduced
forecast metrics, calibration, all 21 policy/scenario daily ledgers and economic
metrics byte-for-byte; classification and checks matched exactly. Zero replay
fits. This is implementation verification, not independent scientific review.

Small outputs are committed under
`docs/research/evidence/ml_etf_risk_screen_20260909/`. The complete download ZIP
also includes the 7MB daily ledger, executed runner, test source and screen card.
Raw market files remain local. Source provenance records the parent commit plus
the exact executed runner hash because the result was generated before this
implementation commit was published.

No local action is needed. Any further ML work needs a new decision problem and
an incremental information hypothesis, rather than adding features or retuning
this closed screen.

For reproduction only, from the implementation checkout with existing daily
CSVs and matching manifests in data/ (choose a new output directory):

```powershell
uv run --locked --python 3.12 python -m scripts.run_ml_etf_risk_screen --input-root data --output-dir artifacts/ml_etf_risk_screen_reproduction
```

That command performs 14 fresh fits; the completed review did not require an
operator rerun or any new download.
