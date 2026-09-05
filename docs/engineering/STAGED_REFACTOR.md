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

## Stage 5 — environment, CI and historical inventory

The lock now includes the already-declared `lxml` dependency (6.1.3). Every
previously locked package retains its version. `uv sync --locked --extra dev`
succeeds. CI uses pinned uv 0.11.33 and the reviewed lock, retains Python 3.11/3.12,
runs the complete suite once per interpreter, and adds independent baseline
migration checks on 3.12. Existing synthetic backtest/paper smoke checks remain.
These baseline gates intentionally protect this migration; a later governed
behavioral change must explicitly supersede its baseline rather than bypass it.

A characterization test records the existing backtest HOLD behavior without fixing
it. `SCRIPT_INVENTORY.md` inventories static code/test/documentation references.
No files are deleted or archived based solely on zero references; external schedules
and operator workflows have not been inspected. Historical evidence and governance
records remain unchanged. Source identity checks protect allocation, strategies,
regimes, resampling and the existing backtest during runtime parity verification.

## Final local verification

- Complete suite after extraction/evidence/lock changes: **775 passed, 89 warnings**
  in 247.37s. The subsequently added HOLD characterization passed separately;
  final test inventory is 776. Boundary tests were rerun after their final edit.
- Final independent ML comparison: all **61 artifacts byte-identical** for the
  baseline/refactor pair. Combined digests vary across invocations because original
  reports include the temporary input paths; comparison within each invocation uses
  identical paths and exact bytes, without normalizing away differences.
- Final independent runtime comparison: **20 accounting cases, three full cycles,
  byte-identical state/logs, and identical chart specifications**.
- `git diff` confirms no changes to canonical strategies, regimes, allocation,
  backtest/resampling, campaign records, ops state, market inputs or old artifacts.
- Historical real-data replay and deployed-runtime validation were not performed;
  operator-local inputs and production are outside this synthetic migration gate.

GitHub CI results are linked in the draft review. No merge or deployment is part
of these commits. Historical cleanup concludes with an inventory; deletion/moves
require evidence about external callers. The known HOLD discrepancy remains open.

## Independent review follow-up — 2026-09-05

The operator supplied a static Red Team review of `1c1663e`: PASS with F1–F4.
This follow-up changes verifiers, regression tests and documentation only.

- **F1:** The error log is written by `main()` after `run_cycle()` raises, not by
  `run_cycle()` itself. Merely adding another direct cycle call would miss the
  handler. The gate now compares `core_v1_errors.jsonl` along with the existing
  outputs, including file presence. After three successful synthetic cycles, it
  corrupts cash only in each temporary state copy and invokes each version's real
  `main()`. A real `sleeve_nav` accounting exception must propagate, create exactly
  one non-empty error record, and produce matching exception type/message, console
  output, state and all five compared files. Regression canaries reject missing,
  empty or changed error logs and suppressed logging. Runtime code is unchanged.
- **F2:** Empty artifact comparisons now fail. Each independent ML execution must
  produce exactly the frozen 61-file inventory before it can be accepted. That
  inventory includes three cached synthetic macro source files; it is not a claim
  that all 61 files are newly generated result outputs. Count and empty-inventory
  regression tests exercise both successful and failing cases.
- **F3:** The baseline chart's drawdown floor is read from its own source declaration
  using AST literal evaluation. No constant is supplied from the candidate or typed
  into the harness. Missing/ambiguous declarations fail; tests demonstrate that a
  different baseline value is actually used without starting Streamlit.
- **F4:** At the reviewed head `1c1663e`, full CI already ran all **776 tests** on each
  interpreter; the earlier local section above records an earlier, split execution.
  Python 3.11: 776 passed in 520.52s. Python 3.12: 776 passed, 89 warnings in 514.01s.
  Independent execution records: [branch CI](https://github.com/IteraDynamics/ID_test/actions/runs/33987435279)
  and [PR CI](https://github.com/IteraDynamics/ID_test/actions/runs/33987458150).
  The review follow-up adds 12 guard tests. A fresh complete local run passed:
  **788 passed, 89 warnings in 238.08s**. Both strengthened differential gates also
  passed against the clean `83e4e11` worktree: exactly 61 byte-identical ML files;
  20 accounting cases, three successful cycles plus one induced failure, identical
  state/log bytes (including a non-empty error log), and identical chart JSON.
  CI results for the follow-up commit are linked in the draft PR.

### Scope clarification and remaining work

This branch completes a bounded extraction/migration phase. It does **not** complete
repository-wide refactoring. Canonical I/O/digest consolidation across the remaining
scripts and making `scripts/` an installable package are separate, unfinished work.
The compatibility shims preserve commands; they do not eliminate repository-wide
`sys.path` manipulation. Those wider changes require their own inventory, migration
plan and evidence-preservation checks. This follow-up does not implement them.

A deploy validation gate is also **not built or executed** here. Before deployment,
a separate plan should define N cycles and acceptance criteria, capture identical
real inputs and immutable snapshots of accumulated state, then run isolated copies
of both versions with every write redirected away from production and compare all
state/log outputs. Running the shadow against a shared writable production state
would invalidate that isolation. Cadence must be re-measured after an explicitly
authorized deployment before using it as an operating/research constraint. Neither
this review nor its PASS authorizes merge, deployment, or reopening retired research.
