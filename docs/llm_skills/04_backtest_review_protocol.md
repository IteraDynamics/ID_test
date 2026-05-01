# Itera Backtest Review Protocol (Skill)

## Purpose

Standardize how LLMs review backtests, blends, overlays, and portfolio experiments for Itera Dynamics.

The goal is not to find the prettiest headline number. The goal is to decide whether a candidate improves the fund.

---

## Required first step

Before interpreting results, identify the test type:

```text
Test type: standalone strategy / blend / allocator overlay / defensive governor / execution validation
```

Then identify the correct baseline.

Examples:

- Fund v1 official baseline: calibrated equal-weight 4-sleeve portfolio from `run_fund_portfolio.py --calibrate`
- Research comparison baseline: equal-weight recombination inside a research script
- Sleeve candidate baseline: Fund v1 calibrated equity curve

Do not mix baselines without saying so.

---

## Metrics hierarchy

Primary metrics:

1. Max Drawdown
2. Calmar
3. Sharpe
4. CAGR
5. Ann. Vol
6. Turnover / trade count / cost drag

CAGR matters, but it is not the only decision criterion.

---

## Cost realism

Always ask:

- Are fees included?
- Is slippage included?
- Is additional turnover modeled?
- Are transition costs modeled for overlays/governors?

If transition costs are not modeled, state that the result is signal evidence only, not execution-ready evidence.

---

## Standalone strategy review

A standalone strategy is not automatically useful because it makes money.

Evaluate:

- standalone Sharpe / Calmar
- MaxDD
- trade count and turnover
- costs as % of returns
- behavior in 2022 and other stress periods
- correlation to Fund v1

Reject candidates that only add more long crypto beta without improving portfolio shape.

---

## Blend review

For blends, compare against Fund v1 baseline:

- CAGR delta
- MaxDD delta
- Sharpe delta
- Calmar delta
- daily return correlation

A blend that increases CAGR but worsens MaxDD and Calmar is usually not a fund improvement.

A blend can proceed only if it improves portfolio usefulness, such as:

- lower drawdown
- better Calmar
- better Sharpe
- better stress-period behavior
- meaningfully different return stream

---

## Allocator overlay review

Allocator overlays must improve the existing capital structure, not introduce a new sleeve.

Reject if:

- equal-weight baseline is stronger
- 2022 worsens
- Sharpe/Calmar decline across all schedules
- stronger tilts consistently make results worse

---

## Defensive governor review

A defensive governor may pass even with small CAGR drag if it improves risk-adjusted behavior.

Pass signals:

- MaxDD improves
- Calmar improves or stays flat
- Sharpe stays flat or improves
- stress-period return improves
- transition costs do not erase benefit

Reject signals:

- drawdown improvement is tiny but CAGR drag is large
- only one isolated event explains all improvement
- recovery is materially delayed
- transition costs erase Calmar improvement

---

## Attribution requirement

Before promoting a candidate, request or produce:

- yearly attribution
- worst drawdown window analysis
- stress-period review, especially 2022

Ask:

```text
Did it help repeatedly or just avoid one event?
```

---

## Standard verdict format

Always end with:

```text
VERDICT: proceed / iterate / abandon / archive
ROLE: strategy / sleeve / allocator / governor / event overlay
WHY:
BEST NEXT STEP:
DO NOT:
```

---

## Itera-specific lessons learned

- ETH/BTC external rotation sleeve: rejected as too beta-coupled
- ETH/BTC allocator overlay: rejected because equal-weight Fund v1 was stronger
- Post-capitulation long: archive as event overlay, not permanent sleeve
- A_light defensive overlay: promote as Fund v2 governor candidate
