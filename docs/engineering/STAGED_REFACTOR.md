# Staged structural refactor

## Scope

Authorized by the operator on 2026-09-05, based on
`agent/ml-lab-exploration-20260903` at `83e4e119a2a7954c470a797a590e5d9c8213d353`.
Work branch: `refactor/staged-research-platform-20260905`.

Preserve Core v1 parameters, weights and logic, historical experiment definitions,
CLI entry points, state formats and evidence interpretation. No merge or deployment
is authorized. Experiment 012 remains specified, not implemented or run. No market
data acquisition, holdout access, strategy tuning or historical artifact rewrite
is part of this refactor.

## Stages and gates

1. Map architecture and establish the unchanged baseline in a separate worktree.
2. Extract versioned cross-sectional ML definitions and historical orchestration;
   keep compatibility entry points. Compare baseline and refactor on identical
   synthetic inputs and the same environment, including output bytes.
3. Separate acquisition/evidence helpers and dashboard data/presentation concerns;
   retain historical serialization and rendering behavior.
4. Extract only runtime components whose original behavior can be independently
   compared. Preserve the cycle orchestration and strategy/allocation definitions.
5. Reconcile dependency metadata without upgrading existing locked versions;
   streamline CI and inventory historical scripts without speculative deletion.

Each stage is committed independently. Behavioral defects are recorded separately,
not corrected by these commits. Existing tests remain in place; differential gates
must compare against baseline code, not two callers of the same extracted helper.

## Initial environment finding

`uv sync --locked --extra dev` fails at the unchanged baseline: `pyproject.toml`
declares `lxml>=5.0`, but the lock's project dependency metadata omits it. Baseline
verification initially uses `uv sync --frozen --extra dev`, retaining every locked
version. Dependency reconciliation is a separate stage; this is not evidence that
the original locked environment satisfies all project requirements.
