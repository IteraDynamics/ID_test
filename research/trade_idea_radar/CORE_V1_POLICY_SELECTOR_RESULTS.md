# Core v1 Policy Selector Results

Research-only result note.

Branch: `gpt/core-v1-policy-selector`  
Harness: `scripts/run_core_v1_policy_selector.py`  
Window: `2020-01-01` to `2025-12-31`  
Artifacts: `artifacts/core_v1_policy_selector/extended_2020_2025`

## Purpose

This test evaluated whether simple deterministic regime rules can switch between two already-validated Core v1 allocation templates:

```text
baseline_40_35_15_10: 40 trend / 35 equity / 15 gold / 10 hedge / 0 MR
gold20_35_35_20_10:   35 trend / 35 equity / 20 gold / 10 hedge / 0 MR
```

The goal was not to prove that dynamic selection is superior.

The goal was to give simple selectors a fair chance to outperform the static validated allocation band.

## Method

The first-pass harness combines daily returns from two completed static portfolio NAV streams:

```text
artifacts/extended_history_2020_2025/baseline_40_35_15_10/stitched_oos_nav.csv
artifacts/extended_history_2020_2025/gold20_35_35_20_10/stitched_oos_nav.csv
```

The selector uses yesterday's regime signal to choose today's template return, avoiding same-day close lookahead.

This is a post-portfolio policy harness, not a full sleeve-level rerun.

## Static reference

The harness computes metrics from daily NAV streams, so Sharpe values are not expected to match the canonical WFO runner's reported Sharpe exactly. Comparisons within this result note are apples-to-apples within the harness.

| Config | CAGR | MaxDD | Sharpe | Calmar |
|---|---:|---:|---:|---:|
| baseline_40_35_15_10 | 18.50 | -17.81 | 1.017 | 1.039 |
| gold20_35_35_20_10 | 17.91 | -17.04 | 1.051 | 1.051 |

## Selector results

| Selector | Rule summary | CAGR | MaxDD | Sharpe | Calmar | Baseline active | Transitions |
|---|---|---:|---:|---:|---:|---:|---:|
| dual_confirmed_risk_on | baseline when BTC>SMA175 and SPY>SMA175 | 18.24 | -17.79 | 1.018 | 1.026 | 58.61% | 56 |
| btc_led_risk_on | baseline when BTC>SMA175 | 18.47 | -17.79 | 1.023 | 1.039 | 62.59% | 48 |
| btc_long_horizon_risk_on | baseline when BTC>SMA365 | 18.40 | -17.89 | 1.017 | 1.028 | 74.92% | 28 |
| equity_confirmed_or_btc_long | baseline when BTC>SMA365 OR BTC>SMA175 and SPY>SMA175 | 18.37 | -17.89 | 1.013 | 1.027 | 77.43% | 32 |

## Interpretation

The first-pass selectors did not clear the acceptance bar.

Observed pattern:

```text
1. Selectors mostly interpolate between baseline and gold20.
2. None beats gold20 on Sharpe or Calmar.
3. None meaningfully improves MaxDD versus gold20.
4. None improves CAGR enough versus baseline to justify added complexity.
5. Selector switching adds complexity without producing a better risk-adjusted profile.
```

The strongest selector by CAGR was `btc_led_risk_on`:

```text
CAGR   18.47 vs baseline 18.50
MaxDD -17.79 vs baseline -17.81
Sharpe 1.023 vs baseline 1.017
Calmar 1.039 vs baseline 1.039
```

This is effectively baseline-like behavior with added switching. It does not justify promotion.

The best static risk-adjusted shape remains gold20 under the harness metric basis:

```text
gold20 Sharpe 1.051
gold20 Calmar 1.051
gold20 MaxDD -17.04
```

## Decision

Reject the first-pass daily policy selectors.

Do not promote dynamic switching between baseline and gold20 based on these rules.

Current stance remains:

```text
Core v1 official baseline:   40 trend / 35 equity / 15 gold / 10 hedge
Core v1 smoother candidate:  35 trend / 35 equity / 20 gold / 10 hedge
```

The static allocation band remains more attractive than a simple dynamic selector:

```text
trend_weight   0.35 to 0.40
equity_weight  0.35
gold_weight    0.15 to 0.20
hedge_weight   0.10
mr_weight      0.00
```

## Next research implication

This result argues against adding a policy selector at this stage.

Recommended next direction:

```text
1. Keep Core v1 static and simple.
2. Preserve gold20 as a documented smoother candidate.
3. Do not add confidence sizing or selector complexity yet.
4. If dynamic policy is revisited, require a stronger economic signal and test across multiple windows before implementation.
```

## Scientific read

This is a useful negative result.

The selector hypothesis was given a simple, pre-declared chance to improve the portfolio. It did not.

That strengthens the case that Core v1's validated static allocation band is already doing most of the useful work.
