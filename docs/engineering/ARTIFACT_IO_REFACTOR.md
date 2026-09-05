# Artifact I/O consolidation — round two

Base: `f332255139b613af0ffa1d227585db47fb8a8fb4` on the previous refactor branch.
This branch is reviewed separately and does not merge or deploy either round.

## Stage 1: frozen inventory and independent baseline

`ARTIFACT_IO_INVENTORY.md` records explicit SHA-256 and JSON serialization calls
across scripts, research and runtime. Regenerate using:

```
python scripts/inventory_artifact_io.py --root ../ID_test_io_baseline --output docs/engineering/ARTIFACT_IO_INVENTORY.md
```

`ARTIFACT_IO_MIGRATIONS.json` fixes 23 migration functions: 17 raw-file digest
routines, four raw-byte digest routines and two identical strict-JSON serializers.
Before changing them, the independent gate passed all 193 differential cases
against the clean pinned baseline. The gate executes original function bodies
with stdlib dependencies, and imports the actual candidate callers separately.
No original comparison function imports the new helper.

Cases include empty/binary/Unicode/CRLF files; 1 MiB boundaries; missing paths and
directories; Unicode JSON, signed zero, small floats, non-finite numbers,
unsupported objects and circular containers. Exact return values and exception
type/message must match. Serialized bytes and digests must match. A source gate
requires every other existing scripts/research/runtime Python file to remain
byte-identical and every non-extracted statement in migrated files to retain
its AST, except an exact documented standalone import bootstrap.

## Contracts to preserve

| Family | Contract | Action |
| --- | --- | --- |
| Raw file SHA-256 | Binary reads, lowercase hex; original 1 MiB or 1 KiB chunk size and error propagation | Consolidate |
| Raw bytes SHA-256 | Hash the supplied bytes without normalization | Consolidate |
| Strict JSON text | Sorted keys, indent 2, UTF-8 characters, reject NaN/Infinity, separators comma and colon-space, final LF | Consolidate the two identical implementations |
| Other JSON | ASCII escaping, compact versus pretty, default=str, finite-tree validation and trailing newline vary | Retain caller-owned policies |
| Composite/directory/replay digests | Path inclusion, ordering, concatenation and truncation belong to individual evidence contracts | Retain unchanged |
| HMAC/authentication and seed/cache identities | Not interchangeable artifact hashes | Retain unchanged |
| CSV and publication | Encoding, newline translation, atomic/direct writes, temporary names and publication order | Retain unchanged |

This round consolidates equivalent primitives. It does not impose a new universal
canonical format. Existing function names/signatures remain as wrappers; passing
each caller's original digest constructor preserves its monkeypatch target.
Standalone scripts lacking a repository import path need a conditional bootstrap
when they acquire this shared dependency. That compatibility cost is explicit;
removing these bootstraps belongs to the separate scripts-packaging migration.
No packaging metadata is changed here.

The raw-file helper in `research/ml_lab/evidence.py` joins the same consolidation;
its NumPy/pandas scalar conversion remains untouched. No Core v1 parameters,
weights, trading logic, research definitions, seeds, source inputs or historical
artifacts are changed. Behavioral corrections remain separate work.

## Deployment and remaining scope

See `CORE_V1_DEPLOY_GATE_CHARTER.md` for the design-only deployment validation
work item. No capture or shadow run has been performed. Scripts packaging and
historical deletions are outside this round. Static zero-reference evidence is
still insufficient grounds for deletion.

## Stage 2: completed migrations and verification

The file-digest extraction passed all 193 independent cases before its commit.
The byte-digest/strict-JSON extraction passed the same gate before its commit.
The common implementation now lives in `research/artifact_io/v1.py`; 23 legacy
functions delegate to it. Raw constructor imports remain where needed to preserve
monkeypatch targets; counting imports is not a count of independent implementations.

Thirty-two new tests cover golden bytes/digests, chunk boundaries, constructor
injection, non-finite rejection, deliberate shared-helper corruption, source-gate
violations and twenty script import contracts outside the checkout. Eighteen
script digest entry points work with repository PYTHONPATH removed; Campaign 50
development validation and Campaign 52 governed equivalence retain their existing
requirement for that import path. These limitations are characterized rather than
silently fixed. Thirteen conditional root bootstraps preserve standalone access to
the new shared dependency; they are temporary packaging debt, not a packaging win.

CI retains both original migration gates against `83e4e11` and adds this round's
193-case gate against `f332255`. Full-suite and end-to-end synthetic ML/runtime
results for the final head are recorded in the draft PR. No historical data or
production state is used in this verification.
