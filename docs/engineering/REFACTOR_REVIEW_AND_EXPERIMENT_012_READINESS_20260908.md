# Refactor review and Experiment 012 readiness — 2026-09-08

## Decision

The reviewed stack has green final-revision CI and no newly identified blocking
code defect in this follow-up review. Merge remains an operator decision. This is
a fresh review by the implementing assistant, not an independent Red Team verdict.
The user supplied independent assessments for the extraction and canonical-I/O
rounds earlier in the conversation. No equivalent independent packaging verdict
has been supplied, and GitHub's review collections for #47–#50 were empty at this
check. Independent packaging acceptance therefore remains outstanding.

Experiment 012 is already specified and frozen. The user's current instruction
authorizes proceeding with its implementation and run under that specification;
no additional generic implementation approval is requested. Its real execution
is blocked by missing frozen inputs, not by a need to reapprove the same work.
No runner, model fit, research result or negative research disposition is claimed
by this readiness change.

## Exact revision review packet

| PR | Head | Base | Final revision CI |
| --- | --- | --- | --- |
| #47 | `f332255139b613af0ffa1d227585db47fb8a8fb4` | `agent/ml-lab-exploration-20260903` | [PR run passed](https://github.com/IteraDynamics/ID_test/actions/runs/33990065863); branch run passed |
| #48 | `e75fb88808ed9c7bc45cf2f8bc04a2a9e43ce8d9` | #47 branch | [PR run passed](https://github.com/IteraDynamics/ID_test/actions/runs/33997825272); branch run passed |
| #49 | `15a0938215be59143753e572bac26818155cc887` | #48 branch | [PR run passed](https://github.com/IteraDynamics/ID_test/actions/runs/34000206201); branch run passed |
| #50 | `b343bf0f1bb560a1247af75294725f7830340c0c` | #49 branch | [PR run passed](https://github.com/IteraDynamics/ID_test/actions/runs/34065083896); branch run passed |

The accompanying `REFACTOR_STACK_CI_20260908.json` records both run URLs and their
exact head SHAs from the API. All four PRs remain open, draft, unmerged and reported
mergeable at inspection. Earlier PR descriptions that said a branch run was still
running are superseded by this dated evidence.

Review focused on the four new packaging source files, source normalization and
manifest restrictions, the adapted I/O verifier, package discovery, installed-wheel
checks, compatibility tests and CI composition. The exact-normalization boundary
preserves remaining AST; unlisted pre-existing Python files retain byte equality.
New-source inventory is constrained, while new-source correctness still depends on
review and execution tests. The contract is an engineering regression gate, not a
cryptographic trust root against simultaneous edits to its code and manifest.

Package import and direct-file execution are distinct contracts. The shared helper
retains checkout lookup; aliases preserve implementation identity. Wheel tests
exercise 17 imports/help commands and seven ML aliases, plus actual synthetic
artifact production and paper success/error handling. They do not prove every
historical CLI works with every external resource or argument combination. Existing
resource requirements and nested/embedded compatibility paths remain explicit.

Fresh local verification at #50's source tree:

- `uv run --locked python -m pytest tests/test_scripts_packaging.py tests/test_artifact_io_contracts.py -q`: **43 passed in 22.66s**.
- I/O differential gate with pinned packaging containment: **23 functions, 193 cases, PASS**.
- `research/`, `runtime/` and `uv.lock` match the pre-packaging baseline exactly.
- Experiment 012 specification and input manifest match the original refactor baseline exactly.

The first local gate attempt rejected an old `f332255` worktree containing a tracked
artifact modification. That worktree was left untouched. A new detached clean
worktree at the same pinned SHA was created and used for the successful gate.
No dirty baseline was trusted and no user file was restored or overwritten.
The already-passing final-head CI supplies the full suites and installed-wheel
execution; this follow-up does not relabel the focused run as a full-suite rerun.

## Merge sequence for operator approval

Review/merge #47 into the existing working branch first, then deliberately retarget
and review #48, #49 and #50 in sequence against that updated working branch. Recheck
the resulting base/diff and CI at each step. Preserve the pinned Git baseline
objects used by the migration gates. Do not sweep the underlying working branch's
research history into `main` by changing the first PR's target.

No merge, PR retarget, deployment, live state access or ops-record edit is performed
here. Independent packaging review can use this packet and #49's existing evidence.

## Experiment 012 execution handoff

Use `ML_LAB_EXPERIMENT_012_COMPACT_MACRO_INTERACTIONS.md` unchanged. Its question is
whether the fixed six-interaction, 22-feature Ridge can express the original U.S.
macro benefit. Exactly one new candidate; alpha 10; fixed expanding and trailing-3y
memories; trailing-3y primary. It is exploratory, discovery-contaminated and
non-confirmatory. Experiment 011's transfer failure and Campaign 58 restrictions
remain unchanged.

`EXPERIMENT_012_PREFLIGHT_20260908.json` records every required path, expected byte
count/hash and observed availability. **0 of 17 inputs are available in this
checkout.** The 14 original U.S. ETF daily CSV files and three Experiment 009
reference files must be supplied at their manifest paths, with matching hashes.
Workspace filename searches also found no RSP input or any of the three reference
artifacts. This is not a claim about files on other machines or remote storage.

Do not download replacements, refresh data, regenerate the Experiment 009 references,
substitute synthetic data as real evidence, or silently update the manifest. A
mismatch requires the specification's explicit documented input-version decision.
No observations were loaded, including reserved 2025 observations.

Once the original files are available, the bounded implementation sequence is:

1. Implement an additive Experiment 012 module and CLI with input-hash preflight,
   cutoff before feature/target construction, exact 22-feature order, saved-reference
   row/target/support parity and recomputed anchor-metric validation before fitting.
2. Before real fitting, pass synthetic tests for feature order, training-only scaling,
   embargo, cutoff, missing inputs, duplicates, reference corruption and all disposition
   branches. Run the complete synthetic pipeline twice with byte-identical artifacts.
3. Run exactly the frozen candidate on the permitted U.S. data. Save every required
   output, coefficient/scaler record, effective slope, paired comparison, environment
   version and disposition component; publish success only after all checks complete.
4. Review the result with its discovery limitations. Failure parks this candidate;
   it does not authorize subset searches, altered alpha, new targets or holdout use.

The existing packaging migration gate intentionally rejects arbitrary added Python
files. The experiment implementation must explicitly compose the frozen migration
proof with a reviewed additive experiment boundary, rather than disabling old gates
or placing code outside scanned directories to avoid them. Preserve existing source
bytes and validate the new module with its own specification-focused tests.

Real fitting remains blocked on the exact input files. Independent packaging
sign-off remains open. These are distinct prerequisites, not failed research results.
