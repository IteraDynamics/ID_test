# Active equity pilot — stage 1 engineering verification

Implementation status: evidence/decision registration only. No enrolled real
companies, investment decisions, fills, NAV, return metrics, or model calls.
No Core/runtime files or shared dependencies were changed.

Executed on Linux, Python 3.12.14, pytest 9.0.3, using the existing locked uv
environment:

```text
uv run --locked --python 3.12 --extra dev python -m pytest tests/test_active_equity_pilot.py tests/test_core_v1_runtime_identity.py -q -W error
70 passed in 2.16s
```

- 68 new tests: synthetic mechanics, timestamp eligibility, finite numeric input,
  source registration, attachment hashing, prospective enrollment, deterministic
  unique-issuer cohort selection, exclusions, no missing-data imputation,
  complete-review requirement, explicit decision revisions, concentration/cash
  constraints, stale decisions, SQLite append protection, concurrent append
  serialization, hash/snapshot/specification corruption canaries, output honesty,
  and no imports of runtime, broker, LLM or HTTP execution clients.
- 2 existing Core runtime-identity tests passed, including byte-identical state
  across independent frozen-input runs. This is not a full Core revalidation.
- CLI `init`, `verify`, and `report` executed successfully on a fresh scratch
  artifact directory. Repeated reports kept the same one-entry journal head.
- `compileall` completed successfully. `git diff --check` passed.

The initial default Python did not have pytest; the repository's declared uv
environment was used successfully. No dependency files were edited.

PowerShell was reviewed but not executed: no Windows/PowerShell runtime was
available in this environment. The wrapper resolves relative inputs before
changing directories, checks native-command exit codes, refuses reinitialization
of existing pilots, and restores the caller's directory with `finally`.

First operator run should report `AWAITING_ENROLLMENT`, with `performance=null`,
`performance_status=NOT_RUN`, zero model calls/downloads, and execution disabled.
An optional local filename/size inventory is a coverage lead, not validation of
data contents, vendor quality, fundamental fields, or point-in-time availability.

Current limitations requiring subsequent work are explicit in the frozen design:
choose and verify event-feed coverage before prospective enrollment, collect
real source packets and analyst decisions, externally anchor the journal, and
freeze/implement an independently tested accounting and execution protocol before
any investment performance claim. Local hashes do not supply trusted timestamps.
