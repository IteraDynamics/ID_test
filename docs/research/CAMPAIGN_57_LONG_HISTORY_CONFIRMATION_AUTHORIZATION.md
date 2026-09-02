# Campaign #57 — Long-History Historical Confirmation Authorization

**Date:** 2026-09-02

**Status:** AUTHORIZED FOR ONE-SHOT HISTORICAL CONFIRMATION RUN.

**Boundary:** Research-only. This authorization opens exactly one Campaign #57 VFINX/VBMFX historical-confirmation computation under the frozen runner below. It does not authorize VTI/BND outcome inspection, economic strategy backtesting, Core v1/Core v2 composition changes, sizing, portfolio action, paper/live trading, orders, NAV/exposure changes, runtime changes, or capital deployment.

## 1. Preconditions satisfied

Validation Architecture Amendment 2 was adopted before any Campaign #57 VFINX/VBMFX or VTI/BND return, signal, or outcome inspection.

The timestamp-only long-history preflight then established:

- long-history pair: VFINX / VBMFX adjusted daily research series;
- common valid months: 476;
- valid monthly interval: 1987-01 through 2026-08;
- outcomes inspected by preflight: false;
- power simulation seed: 20260957;
- outer simulations per haircut: 500;
- permutations per simulation: 199;
- central effect: 50% of the SPY/AGG sandbox Spearman discovery ceiling;
- central target Spearman: -0.12430628083436716;
- required power floor: 80%;
- observed estimated power at the central effect: **85.2% — PASS**.

Sensitivity power:

- 25% haircut: 37.0%;
- 40% haircut: 69.6%;
- 50% haircut: 85.2%.

Interpretation: the historical-confirmation architecture has adequate pre-outcome power at the frozen central effect. This is a feasibility result, not evidence for or against the hypothesis.

## 2. Frozen confirmation implementation

The one-shot confirmation runner was committed before any VFINX/VBMFX return inspection:

- script: `scripts/run_campaign57_long_history_confirmation.py`
- commit: `1e7942c1dec4b02ce62c49f8fab9f9cf7add2f00`

Primary test:

- final 3 shared trading sessions of each calendar month;
- frozen equity-minus-bond pre-window relative-performance signal;
- frozen equity-minus-bond 3-session month-end relative-performance outcome;
- Spearman rho expected `< 0`;
- 10,000 within-five-year-block signal permutations;
- fixed seed `20260957`;
- one-sided permutation p `<= 0.05`.

Frozen robustness diagnostics determine whether a primary pass is clean or conditional:

1. causal expanding-tercile low-minus-high outcome spread > 0;
2. every eligible decade/era bucket has Spearman rho < 0;
3. every eligible leave-one-calendar-year-out aggregate rho < 0;
4. rho remains < 0 after removing the 10 largest absolute-signal months;
5. actual month-end rho is more negative than each frozen -5/-10/-15-session placebo.

Classification is mechanical:

- primary fails: `HISTORICAL_CONFIRMATION_NEGATIVE`;
- primary passes and all frozen robustness directions pass: `HISTORICAL_CONFIRMATION_POSITIVE`;
- primary passes but at least one frozen robustness direction fails: `HISTORICAL_CONFIRMATION_CONDITIONAL`;
- source/timing defect: `HISTORICAL_CONFIRMATION_INVALID`.

No parameter, window, proxy, threshold, permutation design, robustness rule, or classification rule may be changed after inspecting the output.

## 3. Next authorized action

Run exactly:

`python scripts/run_campaign57_long_history_confirmation.py`

Record the complete output before any additional Campaign #57 outcome work.

## 4. Still sealed

VTI/BND remains unspent predictive evidence. It may be opened only if the long-history historical confirmation passes under Amendment 2 and a subsequent recorded transition authorizes the modern cross-instrument replication.

Future-forward SPY/AGG remains the genuine chronological OOS/final-holdout evidence required before any capital decision.
