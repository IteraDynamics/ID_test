# Core v1 deployment validation charter

Status: design only. No production access, capture, shadow execution, deployment,
merge or cadence claim is authorized by this document. The operator approved
writing this charter alongside the artifact-I/O refactor on 2026-09-05.

## Purpose and evidence boundary

Before a proposed release drives the live paper process, establish that its
state transitions and outputs match the deployed revision on accumulated state
and observed market inputs. Synthetic parity remains a prerequisite, not a
substitute. Freeze the actual deployed commit, candidate commit, environment,
configuration and initial state digest in the run manifest; do not assume the
currently deployed commit is the original refactor baseline.

## Proposed run

1. Through a separately authorized capture operation, obtain a consistent,
   immutable snapshot of state and relevant initial logs, plus the deployed
   configuration. Record hashes without copying secrets into evidence.
2. Capture at least 24 consecutive scheduled real cycles, including a UTC date
   boundary. Record the market-loader inputs/outputs, timestamps, clock reads and
   any observed provider errors so both engines consume exactly the same values.
   Separate network requests from the two engines are not equivalent inputs.
3. Execute isolated copies of both revisions with independent copies of the
   snapshot. Replay captured inputs, forbid network, and constrain every write to
   separate temporary output roots. Reject symlinks or paths escaping those roots.
   Never run either shadow against a shared writable production state file.
4. After each cycle compare return/exception outcomes, state and all four log
   streams: signals, fills, market data, errors. Compare presence, inventory,
   record order and exact bytes. Replay append behavior from the captured initial
   logs. Account explicitly for any additional write targets discovered during
   implementation; an unaccounted write is a failure.
5. Require zero differences, unchanged snapshot hashes and no writes outside the
   isolated roots. Missing input/cycle/output inventory fails closed. Freeze a
   manifest and machine-readable per-cycle comparison report for review.

Twenty-four cycles is the proposed minimum, not evidence that every trading path
occurred. Record actual event coverage; do not claim fill/error coverage if none
occurred. Keep existing synthetic buy/sell/error cases as complementary evidence.
Extend the observation window if a required operating event has not occurred.
Any normalization of timestamps, paths or messages requires an explicit contract
and raw outputs retained alongside it; do not silently normalize a discrepancy.

## Release and rollback boundary

Review the shadow evidence before separately approving a release. Prepare rollback
against the actual deployed revision and preserve pre-release state/log snapshots.
No parity result itself authorizes deployment or a research reopening.

After an explicitly approved deployment, measure at least 24 consecutive scheduled
cycles with wall-clock start/end, source-bar availability and effective decision
lag. Report the distribution, maximum lag and missed cycles against the previous
measurement method. Do not reuse the earlier approximately 0.5–0.6-bar figure.
Whether the result satisfies a research reopening threshold remains a separate
research decision; this charter does not declare one.

## Work remaining

Implement the capture/replay contract, write isolation, inventory enforcement,
corruption canaries and report generator. Review the 24-cycle minimum and event
coverage requirements against the actual deployment schedule before capture.
Execution and production access require a separate explicit operator instruction.
