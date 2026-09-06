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
