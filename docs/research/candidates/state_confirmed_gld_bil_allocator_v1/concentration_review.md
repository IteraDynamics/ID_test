# State-Confirmed GLD/BIL Allocator — Concentration Review

## Purpose

This review evaluates whether the current state-confirmed defensive allocator candidate is overly dependent on one or two major contribution windows.

The comparison covers:

- Fund v1 baseline
- GLD-only risk-off destination
- 50% GLD / 50% BIL risk-off destination

## Candidate Rule

```text
Risk-off when:
  Fund v1 prior-day drawdown <= -18%
  AND BTC prior-day close < BTC SMA200

Release when:
  Fund v1 drawdown recovers to >= -12%
  OR BTC recovers above SMA200

Crypto scale during risk-off:
  0%
```

## Exclusion Windows

```text
2022:
  2022-01-01 -> 2022-12-31

late_2025:
  2025-11-01 -> 2025-12-30

exclude_all_specified:
  both windows removed
```

## Results

| Scenario | Label | CAGR | MaxDD | Sharpe | Calmar | dCalmar vs Baseline |
|---|---|---:|---:|---:|---:|---:|
| full_sample | baseline | 32.91% | -35.42% | 1.068 | 0.929 | 0.000 |
| full_sample | gld_only | 42.68% | -26.48% | 1.325 | 1.612 | 0.682 |
| full_sample | gld_bil_blend | 38.41% | -22.49% | 1.250 | 1.708 | 0.778 |
| exclude_2022 | baseline | 32.91% | -34.80% | 1.079 | 0.946 | 0.000 |
| exclude_2022 | gld_only | 42.68% | -23.04% | 1.345 | 1.853 | 0.906 |
| exclude_2022 | gld_bil_blend | 38.40% | -22.49% | 1.255 | 1.708 | 0.761 |
| exclude_late_2025 | baseline | 35.06% | -35.42% | 1.111 | 0.990 | 0.000 |
| exclude_late_2025 | gld_only | 42.32% | -26.48% | 1.309 | 1.598 | 0.608 |
| exclude_late_2025 | gld_bil_blend | 38.68% | -22.49% | 1.246 | 1.720 | 0.730 |
| exclude_all_specified | baseline | 35.06% | -34.80% | 1.122 | 1.007 | 0.000 |
| exclude_all_specified | gld_only | 42.31% | -23.04% | 1.329 | 1.837 | 0.828 |
| exclude_all_specified | gld_bil_blend | 38.68% | -22.49% | 1.252 | 1.720 | 0.712 |

## Episode Attribution

| Label | Wins | Losses | Win Rate | Sum Delta | Median Delta |
|---|---:|---:|---:|---:|---:|
| gld_only | 10 | 4 | 71.43% | 40.24% | 1.37% |
| gld_bil_blend | 10 | 4 | 71.43% | 18.37% | 0.86% |

## Interpretation

The concentration review supports the candidate rather than weakening it.

Even after removing both the 2022 stress window and the late-2025 contribution window, the 50/50 GLD/BIL blend still materially beats the baseline on Calmar:

```text
Baseline Calmar excluding both windows: 1.007
50/50 GLD/BIL Calmar excluding both windows: 1.720
Delta: +0.712
```

GLD-only remains the higher-return and higher episode-delta variant, while the 50/50 GLD/BIL blend remains the better risk-adjusted portfolio shape.

## Current Read

```text
50/50 GLD/BIL:
  Current risk-adjusted leader.
  Strong Calmar advantage persists after excluding major contribution windows.

GLD-only:
  Higher-return alternative.
  Higher episode sum delta.
  More destination-specific reliance on GLD.

BIL-only:
  Conservative benchmark / fallback.
```

## Methodological Caveat

The exclusion review removes return observations inside the specified windows and then recomputes metrics on the remaining equity path. This is useful as a contribution-dependency check, but it is not the same as a fully separate out-of-sample walk-forward validation.

A future robustness step should test the candidate across independent chronological subperiods and nearby parameter clusters.

## Status

```text
CONCENTRATION REVIEW PASSED — not promoted; proceed to robustness and deployability review.
```
