# Core v1 Policy Selector Plan

Research-only planning note.

Branch: `gpt/core-v1-policy-selector`  
Base: merged Core v1 extended-history validation  
Status: hypothesis before implementation

## Purpose

Core v1 now has two repeatedly validated static allocation expressions:

```text
Core v1 official baseline:  40 trend / 35 equity / 15 gold / 10 hedge / 0 MR
Core v1 smoother candidate: 35 trend / 35 equity / 20 gold / 10 hedge / 0 MR
```

The purpose of this branch is to test whether a simple deterministic policy selector can choose between those two already-validated allocation templates in a way that improves portfolio shape enough to justify the added complexity.

This is not confidence sizing.

This is not allocation optimization.

This is a small regime-selection test between two fixed allocation templates.

## Scientific framing

The goal is not to prove that dynamic selection is better.

The goal is to give the selector a fair opportunity to fail.

A selector should be rejected if it adds complexity without materially improving the already-strong static allocations.

## Prior evidence

Extended-history validation established the following 2020-2025 OOS comparison:

| Config | Trend | Equity | Gold | Hedge | CAGR | MaxDD | Sharpe | Calmar | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 0.40 | 0.35 | 0.15 | 0.10 | 18.51 | -17.88 | 1.223 | 1.035 | 42.57 | 25.17 | -8.65 | 28.56 | 24.26 | 5.02 |
| gold20_35_35_20_10 | 0.35 | 0.35 | 0.20 | 0.10 | 17.92 | -17.11 | 1.264 | 1.048 | 39.17 | 22.81 | -8.70 | 27.34 | 24.14 | 7.72 |

Observed pattern:

```text
baseline -> higher upside capture
gold20   -> smoother risk-adjusted expression
```

Validated allocation band:

```text
trend_weight   0.35 to 0.40
equity_weight  0.35
gold_weight    0.15 to 0.20
hedge_weight   0.10
mr_weight      0.00
```

## Selector hypothesis

Hypothesis:

```text
Use baseline when macro/trend state is clearly constructive.
Use gold20 when macro/trend state is degraded, uncertain, or defensive.
```

Economic intuition:

```text
baseline has more trend allocation and should benefit from strong risk-on / trend regimes.
gold20 has more defensive ballast and should help when risk state is weaker, choppier, or late-cycle.
```

## Candidate selectors

### Selector A: Dual-confirmed risk-on

```text
Use baseline only when BTC macro state is constructive AND SPY trend state is constructive.
Otherwise use gold20.
```

Interpretation:

```text
Higher-upside template requires both crypto macro and equity macro confirmation.
```

### Selector B: BTC-led risk-on

```text
Use baseline when BTC macro state is constructive.
Otherwise use gold20.
```

Interpretation:

```text
Core v1 remains crypto-led; equity state is secondary.
```

### Selector C: Defensive override

```text
Default to baseline.
Switch to gold20 when BTC macro state is degraded OR SPY trend state is degraded.
```

Interpretation:

```text
Gold20 acts only as a defensive override.
```

Selector A and Selector C may be logically similar depending on implementation details. The first implementation should keep the rules explicit and audit how often each template is active.

## Required audit outputs

Any selector test must report:

```text
1. stitched portfolio metrics
2. annual returns
3. active template counts by year
4. baseline-active percentage by year
5. gold20-active percentage by year
6. transition count by year
7. explicit BTC state audit remains clean
```

The selector is not credible unless we know when and why it selected each template.

## Acceptance criteria

A selector is only interesting if it improves enough shape to justify complexity.

Minimum bar versus both static allocations:

```text
Sharpe >= max(static baseline Sharpe, static gold20 Sharpe)
Calmar >= max(static baseline Calmar, static gold20 Calmar)
MaxDD <= min absolute drawdown of static baseline/gold20, or very close
CAGR not materially below gold20
No single-year deterioration that is obviously unacceptable
```

For the 2020-2025 extended window, static comparison bars are:

```text
baseline: CAGR 18.51 / MaxDD -17.88 / Sharpe 1.223 / Calmar 1.035
gold20:   CAGR 17.92 / MaxDD -17.11 / Sharpe 1.264 / Calmar 1.048
```

Therefore, a selector should ideally clear:

```text
Sharpe > 1.264
Calmar > 1.048
MaxDD shallower than -17.11, or very close with better CAGR
CAGR near or above 17.92
```

## Rejection criteria

Reject the selector if any of the following occur:

```text
1. It underperforms both static allocations on Sharpe and Calmar.
2. It adds complexity while producing nearly identical results to one static allocation.
3. It improves CAGR only by worsening MaxDD materially.
4. It relies on hindsight-tuned thresholds.
5. It switches excessively and behaves like noise.
6. It cannot be explained in simple regime language.
```

## Guardrails

Do not introduce confidence sizing in this branch.

Do not search large allocation grids in this branch.

Do not promote a selector based on one window.

The first implementation should be simple, auditable, and deterministic.

## Proposed implementation path

```text
1. Inspect existing walk-forward outputs and sleeve equity curves.
2. Build a selector harness that can combine static baseline/gold20 daily or fold-level outputs.
3. Start with yearly/fold-level policy selection if available.
4. Only move to daily/monthly regime switching if the existing artifact structure supports it cleanly.
5. Compare static baseline, static gold20, and candidate selectors on the same 2020-2025 and 2021-2025 windows.
```

## Initial stance

Default expectation:

```text
Static allocations may be hard to beat.
```

That is acceptable.

If the selector fails, the result strengthens the case that Core v1 should remain a simple validated allocation band rather than a dynamic policy system.
