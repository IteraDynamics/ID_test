# State-Confirmed GLD/BIL Allocator — Walk-Forward Review

## Purpose

This review records the chronological and walk-forward validation result for the state-confirmed GLD/BIL defensive destination allocator.

The purpose is to reduce overfit risk before any promotion or runtime implementation decision.

This review does not approve live runtime integration.

---

## Candidate Reviewed

Default fixed rule:

```text
Risk-off when:
  Fund v1 prior-day drawdown <= -18%
  AND BTC prior-day close < BTC SMA200

Release when:
  Fund v1 drawdown recovers to >= -12%
  OR BTC prior-day close >= BTC SMA200

Destination during risk-off:
  50% GLD / 50% BIL

Crypto scale during risk-off:
  0%
```

---

## Walk-Forward Script

```text
scripts/run_defensive_destination_walk_forward.py
```

Output artifacts:

```text
artifacts/defensive_destination_walk_forward/fixed_rule_subperiods.csv
artifacts/defensive_destination_walk_forward/fixed_rule_train_test_splits.csv
artifacts/defensive_destination_walk_forward/rolling_walk_forward.csv
artifacts/defensive_destination_walk_forward/walk_forward_summary.json
artifacts/defensive_destination_walk_forward/walk_forward_summary.md
```

---

## Fixed-Rule Chronological Validation

The fixed rule improved Calmar in all tested subperiods.

| Window | Baseline Calmar | Overlay Calmar | Delta Calmar | Baseline MaxDD | Overlay MaxDD | Delta MaxDD | Risk-Off Days |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019-2020 | 2.909 | 3.881 | 0.972 | -31.33% | -22.49% | 8.84% | 16.1% |
| 2021-2022 | 0.203 | 0.761 | 0.558 | -35.40% | -22.09% | 13.30% | 52.9% |
| 2023-2024 | 1.349 | 1.592 | 0.243 | -25.74% | -21.94% | 3.80% | 20.1% |
| 2025 | -0.404 | 0.146 | 0.550 | -23.90% | -20.42% | 3.47% | 25.7% |

Summary:

```text
Fixed-rule Calmar win rate: 100.0%
Fixed-rule drawdown improvement: 100.0%
```

Interpretation:

The fixed 50/50 GLD/BIL rule shows consistent chronological drawdown and Calmar improvement across the tested subperiods.

This supports the idea that the rule is useful as a defensive overlay.

---

## Rolling Walk-Forward Parameter Selection

The rolling walk-forward selected from a small allowed grid on each training window and then applied the selected rule to the next unseen test window.

Grid:

```text
Triggers: -18%, -20%, -22%
Releases: -8%, -10%, -12%
BTC SMA: 180, 200, 220
Blend weights: 75/25, 50/50, 25/75 GLD/BIL
```

Out-of-sample results:

| Test Window | Selected Trigger | Selected Release | Selected SMA | Selected GLD Weight | Baseline Calmar | Overlay Calmar | Delta Calmar | Baseline MaxDD | Overlay MaxDD | Delta MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022 | -22% | -8% | 220 | 75% | -0.835 | -0.433 | 0.402 | -24.54% | -20.13% | 4.41% |
| 2023 | -18% | -12% | 180 | 25% | 1.930 | 1.881 | -0.049 | -20.67% | -16.94% | 3.73% |
| 2024 | -18% | -12% | 180 | 25% | 1.004 | 0.869 | -0.136 | -25.74% | -27.10% | -1.36% |
| 2025 | -18% | -8% | 200 | 75% | -0.404 | 0.362 | 0.766 | -23.90% | -20.89% | 3.01% |

Summary:

```text
Rolling OOS Calmar win rate: 50.0%
Rolling OOS drawdown improvement rate: 75.0%
```

Interpretation:

Rolling out-of-sample validation is mixed.

The allocator improved drawdown in most unseen windows, but it did not consistently improve Calmar under rolling parameter selection.

The selected parameters also moved across windows, which is a warning against building an adaptive optimizer around this candidate at this stage.

---

## Key Conclusion

```text
WALK-FORWARD REVIEW: PARTIAL PASS
```

The candidate is stronger as a fixed-rule defensive overlay than as a rolling-optimized adaptive allocator.

### Passed

```text
Fixed-rule chronological Calmar improvement
Fixed-rule chronological drawdown improvement
Most rolling OOS windows improved drawdown
Paper replay demonstrated mechanical feasibility
```

### Mixed / Not Passed

```text
Rolling OOS Calmar improvement was only 50%
Rolling-selected parameters were unstable
The candidate is not validated as an adaptive return enhancer
```

---

## Updated Candidate Classification

```text
PARTIAL PASS — fixed-rule defensive overlay candidate
```

More precise classification:

```text
Useful defensive / capital-preservation overlay candidate.
Not a proven independent alpha engine.
Not a production-ready runtime feature.
Not approved for adaptive optimization.
```

---

## Recommended Decision

```text
Retain as a watchlisted defensive overlay candidate.
Do not promote to live runtime.
Do not build an adaptive optimizer around it.
Do not continue tuning parameters right now.
Use the fixed rule as the reference candidate if this is revisited.
```

---

## Next Research Direction

The GLD/BIL allocator answers a defensive question:

```text
Can Itera reduce damage during crypto-hostile regimes?
```

The next research direction should answer a return-engine question:

```text
Can Itera generate better crypto selection or timing alpha inside the BTC/ETH universe?
```

Recommended next candidate:

```text
BTC/ETH relative-strength allocator
```

Reason:

```text
This stays inside Itera's core crypto universe and tests whether capital can be dynamically allocated between BTC and ETH instead of using static exposure.
```

---

## Final Status

```text
GLD/BIL allocator research milestone complete.
Status: PARTIAL PASS / WATCHLISTED DEFENSIVE OVERLAY.
Next: pivot to BTC/ETH relative-strength research.
```