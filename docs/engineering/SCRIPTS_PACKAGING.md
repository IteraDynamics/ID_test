# Scripts packaging — round three

Base: `e75fb88808ed9c7bc45cf2f8bc04a2a9e43ce8d9`, stacked on the artifact-I/O
refactor. No merge, deployment, real-data research replay or production access.

## Supported execution contracts

- Install the locked development environment with `uv sync --locked --extra dev`.
  `scripts` is included in the distribution alongside `research` and `runtime`.
- Installed module commands use `python -m scripts.<command>` from any directory,
  with explicit input/output paths when the command needs them. Importing the
  package must not start a CLI, fetch data or mutate `sys.path`.
- Existing `python scripts/<command>.py` checkout commands remain supported.
  Direct-file execution has a different Python import path from package execution;
  one shared `_checkout_bootstrap.py` preserves that compatibility. The bootstrap
  runs only when the entry point has no package context.
- ML Lab alias modules must retain implementation-module identity and monkeypatch
  compatibility. No command is relocated or removed.
- Installing code does not install private data, historical artifacts, repository
  governance documents or Git history. Commands that consume those resources
  retain those requirements. Verifiers remain checkout tools.

## Stage 1

Add an inert `scripts/__init__.py`, include `scripts*` in package discovery and
introduce the shared direct-file compatibility helper. Build and inspect the
wheel to require every script Python source file, with no cached bytecode.
The project version and locked dependency versions remain unchanged.

## Stage 2: contained import migration

111 existing script files replace their top-level checkout path adjustments with
the shared compatibility prelude and/or qualify six sibling import statements.
Research/runtime files remain byte-identical to the pinned baseline. The prelude
runs before project imports, fixing the two previously characterized Campaign
50/52 direct-file failures. Their existing tests now require successful digests.

`SCRIPTS_PACKAGING_MIGRATIONS.json` fixes the changed-file inventory. The new source
gate checks 330 pre-existing Python files. It permits only exact recognized path
statements, the exact shared prelude and the enumerated sibling-import conversions;
all remaining AST must match. Unlisted existing files must match bytes. Exactly
four new source files are permitted; missing or unexpected additions fail closed.
The narrowly adapted I/O verifier is separately pinned by its reviewed file hash
in the manifest, rather than silently excluded from containment.

The I/O gate retains its original `f332255` boundary check against the clean pinned
intermediate tree `e75fb88`, then checks packaging containment from that tree to the
candidate. Its 193 differential cases still execute the actual candidate callers
against the original independent function bodies. Both older `83e4e11` ML/runtime
gates are retained. No original comparison is waived to make packaging pass.

Package imports perform no path mutations. One direct-file helper remains by
design. A nested compatibility path in `replay_core_v1_export.py` and four embedded
subprocess-program path statements remain unchanged: they are distinct execution
contexts, not top-level package-import bootstraps. Literal historical statements
in verifiers and comments also mean grep counts are not executable-mutation counts.

The built-wheel checks require a complete, non-empty script inventory, install the
local wheel with `uv pip --no-deps --no-index` into a temporary target, and run from
outside the checkout with checkout import paths removed. They check 17 installed
imports, 17 fresh-process module help commands, seven ML alias identities, no
package-import path mutation, and successful Campaign 50/52 digest calls. A separate
`-I -S` subprocess verifies a bare checkout command without site-packages at all.
