# Itera ML Lab — Exploratory Research Boundary

**Branch:** `agent/ml-lab-exploration-20260903`

**Base branch:** `claude/itera-ml-research-evaluation-fqr8rb`

**Status:** EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY

## Purpose

This branch exists to let the CEO and research assistant explore machine-learning ideas quickly and iteratively without confusing exploratory findings with governed Itera evidence.

It deliberately inherits all Campaign #58 work and prior ML context from the Claude branch, but it is not Campaign #58 and does not reopen, rewrite, or supersede Campaign #58's governed conclusions.

## Boundary

Everything produced on this branch is exploratory unless and until a finding is separately promoted into the governed Itera research process.

Allowed here:

- fit and compare exploratory ML/statistical models;
- inspect feature importance, SHAP-style explanations, partial dependence, residual structure, fold behavior, nonlinear interactions, and cross-asset transfer;
- iterate on features, targets, models, and diagnostics;
- use chronological train/test splits and walk-forward designs as good research hygiene without claiming they create an untouched institutional holdout;
- follow interesting exploratory findings and simplify them into candidate economic hypotheses;
- kill ideas quickly when they are clearly uninteresting.

Not authorized here:

- any change to Core v1 parameters, weights, logic, runtime, thresholds, or orders;
- any Core v2 composition or weighting decision;
- paper/live trading, NAV, exposure, capital, or execution changes;
- treating an exploratory backtest or model metric as confirmatory evidence;
- calling a candidate ALIVE, VALIDATED, production-ready, or capital-ready;
- consuming any holdout explicitly reserved by another governed campaign.

## Promotion rule

If exploratory work produces a genuinely interesting, repeatable finding, the branch should first answer:

1. What did the model actually learn?
2. Is the effect simpler than the model?
3. Is there a plausible economic mechanism or at least a stable empirical structure?
4. Does it survive basic chronological and cross-asset checks?

Only then should the finding be translated into a frozen candidate and sent through independent validation / Red Team / normal Itera governance on a separate governed branch.

## Research philosophy

Machine learning is treated here as a research methodology, not an investment thesis.

The objective is not to maximize backtest Sharpe. The objective is to discover whether nonlinear or higher-dimensional modeling reveals stable structure that simple baselines miss, and to understand that structure well enough to decide whether it deserves governed follow-up.

Complexity must earn its place, but simplicity is not presumed correct by default.

## Initial experiment

Start with a deliberately small, interpretable nonlinear-structure probe rather than another large census.

Question:

> On a compact, causally available feature set, can a shallow nonlinear model produce stable chronological out-of-sample predictive lift over a linear baseline, and if so, what interaction is responsible?

Initial constraints:

- one target family at a time;
- one asset or tightly coherent asset pair at a time;
- approximately 8–15 features;
- chronological / walk-forward evaluation;
- naive baseline;
- linear or logistic baseline;
- one shallow gradient-boosted model;
- optionally one shallow random-forest comparator;
- no broad hyperparameter search;
- no production interpretation.

The first success criterion is not a specific Sharpe or p-value. It is whether nonlinear lift is persistent enough across chronological folds to justify investigating what the model learned.
