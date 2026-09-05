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

## Stage 2 — ML package verification

- Unchanged baseline: 762 tests passed (89 warnings), Python 3.12.13, 242.41s.
- Experiment 005–011 definitions/orchestration moved into `research/ml_lab`.
  Historical scripts alias their implementation modules, preserving import and
  patching identity as well as direct-script commands. Shared definitions are
  explicitly versioned; experiment-specific metrics/tie handling remain distinct.
- Existing Experiment 011 synthetic/replay tests: 5 passed.
- Import/CLI, embargo and parity-failure checks: 10 passed.
- Independent baseline/current CLI comparison: **61 artifact files byte-identical**
  across Experiments 005–011, on identical synthetic inputs and environment.
  `scripts/verify_refactor_ml_parity.py` reproduces this check, including corruption
  canaries for the output comparator. No historical market data was available or used.

## Stage 3 — acquisition and evidence helpers

Macro acquisition/parsing is now separate from macro feature computation. Existing
Experiment 009 cache-miss acquisition semantics remain available through aliases;
transfer still reads saved macro state. File hashes and NumPy/pandas JSON scalar
conversion share an implementation. Output names, CSV/JSON options and publication
order are unchanged. Cache-hit/no-refresh, failed-acquisition and serialization
checks pass. Atomic multi-file publication would change historical failure behavior
and is intentionally not retrofitted into frozen runners.

## Stage 4 — dashboard and runtime extractions

Dashboard snapshot loading, formatting and chart construction are importable
without launching Streamlit. Existing trust rules and rendering remain in place.
Core v1 accounting and JSON persistence moved verbatim into dedicated modules;
cycle orchestration, clock use, market-data logic, strategies and allocation remain
unchanged. Structural comparison confirms every extracted and retained runtime
function has its original AST.

Verification: 30 existing dashboard/runtime tests pass. The independent baseline
comparison passes 20 fill/accounting cases, state migration, cash-yield replay,
three complete synthetic cycles (including a price shock), and chart JSON parity.
Cycle events match; state, signal, fill and market-data logs match byte-for-byte.
Runtime identity sidecars intentionally identify their actual checkout and are not
compared as accounting evidence. Reproduce with
`scripts/verify_refactor_runtime_parity.py --baseline-root <baseline-worktree>`.
