# Experiment 012 integration — 2026-09-08

## Source and scope

The operator supplied local commit `e7c27040543723417fb4466638c53890a54c6adb`
on `review/ml-lab-experiment-012-local-20260908`. It already implements the frozen
Experiment 012. This branch retains that implementation and its historical record,
then adapts it to the verified refactor plus Windows corrections at `58104346`.
The campaign-board append conflict was resolved by retaining both the Campaign 58
closure entry and the Experiment 012 implementation entry. No campaign decision
was changed. No ops file was edited.

The earlier readiness packet's NOT_IMPLEMENTED statement described the published
checkout available then; the operator's unpublished implementation was subsequently
located and supplied. This integration supersedes that implementation-availability
blocker. The original input files are still absent from the remote execution workspace.
No real Experiment 012 fit or result is claimed here.

## Adaptations and review

- Fix the package-qualified test-helper import that blocked local test collection.
- Use package-qualified Experiment 005/009/010 imports and the existing direct-file
  bootstrap. No new unconditional `sys.path` mutation is introduced.
- Delegate file hashing to the existing byte-preserving artifact-I/O primitive.
- Add `--input-root` for the original data/artifact checkout and `--preflight-only`
  for byte validation without loading observations or fitting. The real manifest
  is always read from the new code checkout, not from the supplied input directory.
- Freeze the complete real manifest's parsed values with a canonical JSON digest.
  Manifest checkout whitespace/newlines can differ; input bytes cannot. The raw
  manifest hash is still recorded and checked again before publication.
- Record actual extracted ML and artifact-I/O source hashes in addition to entrypoint
  shims. Hashing only shims would misidentify the code used after refactoring.
- Validate saved target-end dates when present. Experiment 009's original predictions
  omit that column, so the existing reconstructed dates remain supported.
- Extend the exact new-source inventory by one named file, the Experiment 012 runner.
  Existing source byte/AST restrictions, the two named Windows display corrections,
  the 193-case I/O gate, and older ML/runtime comparisons remain active.

The reviewed runner retains the exact 22-feature order, six interactions, alpha 10,
training-only scaling, strict target-end embargo, annual eligibility and fixed
memory choices. It verifies the full saved row inventory and target/anchor metrics
before fitting. Paired comparisons use exact matching anchor sets. The three frozen
disposition branches retain primary-memory precedence and strict-positive/majority
rules. Coefficients are converted back to raw units and predictions reconstructed;
effective slopes use the existing regime definitions. Existing output directories
are rejected and inputs rechecked before staged output publication.

No model, target, feature subset, alpha, universe, holdout boundary, or frozen decision
rule was changed. The two extra diagnostic CSVs in the supplied implementation
expose required annual comparisons and slope summaries. They add no research candidate.

## Verification

The initial adapted implementation passed the supplied 13 tests, including actual
Experiment 009 synthetic reference generation and two complete Experiment 012 runs.
Additional regressions cover fixed manifest values with CRLF checkout formatting,
preflight avoiding observation loading/fitting, and saved target-end corruption.
Replay checks now require exactly 11 CSV artifacts and compare the report bytes too.
The final targeted suite and final-head CI results are recorded in the draft PR.

The 193-case I/O gate with packaging containment passed after integration. The
previous Windows-fix head's branch and PR CI both passed natively on Windows and
Linux; that result is not presented as validation of this new experiment revision.
This is implementation review by the integrating assistant, not external scientific
confirmation or independent Red Team sign-off.

## PowerShell execution from the review worktree

Fetch the integration branch and check it out in the separate review worktree.
Leave the original `ID_test` checkout, local commit, lockfile and private files alone.

```powershell
git fetch origin research/experiment-012-integration-20260908
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git switch --detach FETCH_HEAD
if ($LASTEXITCODE -ne 0) { throw "Checkout failed" }
uv sync --locked --extra dev --python 3.12
if ($LASTEXITCODE -ne 0) { throw "Environment setup failed" }
uv run --locked --python 3.12 python -m pytest tests/test_ml_lab_experiment_012.py -q
if ($LASTEXITCODE -ne 0) { throw "Synthetic verification failed" }
uv run --locked --python 3.12 python -m scripts.run_ml_lab_experiment_012 --input-root ..\ID_test --preflight-only
if ($LASTEXITCODE -ne 0) { throw "Frozen input verification failed; stop here" }
uv run --locked --python 3.12 python -m scripts.run_ml_lab_experiment_012 --input-root ..\ID_test --output-dir ..\ID_test\artifacts\ml_lab_experiment_012
if ($LASTEXITCODE -ne 0) { throw "Experiment failed; retain the diagnostic output" }
```

The hash preflight must verify all 17 inputs. A mismatch is an execution blocker,
not a negative research finding. Do not refresh/substitute inputs, update the frozen
manifest, delete an existing result directory, or tune the candidate to proceed.
An existing output directory requires inspection of its provenance before another run.

On success, the JSON report and 11 CSVs are in the specified original checkout's
`artifacts/ml_lab_experiment_012/` directory. Share the report for interpretation.
Results remain exploratory, discovery-contaminated and non-confirmatory. No merge,
deployment, production access, reserved-2025 use or research promotion is authorized.
