# Itera Dynamics Research Promotion Policy

## Purpose

This policy defines how a research idea moves from hypothesis to runtime eligibility. It exists to prevent attractive standalone metrics from being mistaken for portfolio value and to preserve explicit decisions for completed or rejected research.

## Lifecycle states

| State | Meaning |
|---|---|
| HYPOTHESIS | Research question and falsifiable objective are documented before implementation. |
| DISCOVERY | Broad exploratory sweep is running. No candidate claim is allowed. |
| CANDIDATE | A configuration has passed basic out-of-sample validation and is frozen for further testing. |
| VALIDATED | Candidate survives ablation, horizon refinement, robustness, event-count audit, and applicable transfer checks. |
| PORTFOLIO TRIAL | Frozen candidate is tested against the canonical Core portfolio with realistic timing and incremental costs. |
| PRODUCTION | Portfolio trial passes predeclared promotion criteria and runtime implementation is separately reviewed. |
| COMPLETED — NOT PROMOTED | Research question was answered, but portfolio value or runtime criteria were not met. |
| RETIRED | Previously promoted or active research is superseded, invalidated, or no longer supported. |

## Required evidence by stage

### Candidate

- Strictly out-of-sample or expanding walk-forward evaluation
- Reproducible configuration and dataset fingerprints
- Sufficient event and fold support
- No known lookahead or timestamp leakage
- Candidate frozen before targeted confirmation work

### Validated

- Feature-family ablation
- Nearby-horizon and nearby-label robustness
- Fold-level validity audit
- Event-count and top-tail support
- Cross-asset or alternate-market transfer where appropriate
- Explicit WARN/VALID/REJECT grade

### Portfolio Trial

- Canonical Core baseline reproduced exactly
- Signal generated strictly out of sample
- At least one-bar implementation lag where required
- Incremental turnover and transaction costs included
- Baseline and overlays evaluated on identical timestamps
- Promotion criteria declared before results are inspected

### Production

- Portfolio trial passes
- Failure modes and fail-closed behavior documented
- Runtime data contract defined
- State, logging, monitoring, and rollback implemented
- Paper observation period completed
- No research script is permitted to place or route orders

## Default portfolio promotion criteria

A portfolio implementation normally must satisfy all of the following relative to canonical Core:

- Sharpe delta greater than zero
- Calmar delta greater than zero
- Maximum-drawdown delta nonnegative
- CAGR degradation no worse than 0.50 percentage points

A research charter may predeclare stricter or alternative criteria when the hypothesis is specifically defensive, hedging-oriented, or capacity-oriented. Criteria may not be changed after results are observed without labeling the next run exploratory.

## Decision rules

- Strong classifier metrics do not override poor portfolio results.
- A validated signal with a rejected economic mapping is recorded as **COMPLETED — NOT PROMOTED**, not deleted.
- Failed implementations may generate future hypotheses, but each materially different mapping requires a new charter.
- Core remains unchanged unless a candidate passes the full promotion path.
- WARN candidates cannot enter production without resolving the source of the warning.
- Generated artifacts are evidence; documentation records the interpretation and decision.

## Current examples

| Program | Current state | Decision |
|---|---|---|
| Core v1 | PRODUCTION BASELINE | Canonical portfolio remains unchanged. |
| Jump Risk Engine v0 | VALIDATED CANDIDATE | Portfolio trial is the next stage. |
| Trend Persistence Engine v0 | COMPLETED — NOT PROMOTED | Predictive signal validated; tested portfolio mappings rejected. |
