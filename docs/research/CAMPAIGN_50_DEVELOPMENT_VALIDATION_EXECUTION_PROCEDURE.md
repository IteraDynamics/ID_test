# Campaign #50 — Development/Validation Execution Procedure

## Status

**PROPOSED EXECUTION PROCEDURE — no real development/validation execution is authorized by this document.**

This procedure defines the deterministic, replay-safe process that may be used only after a separate board-recorded development/validation execution GO.

It does not authorize:

- generating real Campaign #50 predictors or forward-return outcomes;
- loading any 2025 row into discovery/validation analytical structures;
- holdout confirmation;
- economic backtesting;
- paper trading;
- runtime, strategy, threshold, order, execution, portfolio, NAV, or exposure changes.

## Governed inputs

Repository:

- `IteraDynamics/ID_test`

Branch:

- `agent/campaign-50-holdout-first-alpha-research-planning`

Frozen statistical specification:

- `docs/research/CAMPAIGN_50_EQUITY_BREADTH_STATISTICAL_SPEC.md`
- commit `36dd499d00740062f10c1c070896f740f55f6808`

Frozen source universe:

- `docs/research/CAMPAIGN_50_EQUITY_SOURCE_UNIVERSE.md`
- commit `f32cac981bf55d0b1799949988df70e5546394e5`

Required source root:

- local `data/`

The exact 16 governed CSV identities must match the frozen SHA-256 values before any analytical construction.

## Authorized analytical interval after future GO

Development:

- `2018-01-02` through `2022-12-30`

Validation:

- `2023-01-03` through `2024-12-31`

Forbidden in the discovery/validation process:

- every session after `2024-12-31`;
- every 2025 observation;
- any alternate or substituted source file;
- any interpolation, fill, repair, resampling, or source mutation.

The discovery/validation loader must reject a post-2024 source row before placing prices into analytical structures.

## Required pre-execution state

Before either replay run:

1. The authoritative campaign board must contain an explicit real development/validation execution GO.
2. The worktree must be on the governed branch.
3. The implementation commit set and statistical specification must be unchanged from the board-recorded identities unless a new pre-outcome governance amendment records the correction.
4. Synthetic tests must pass.
5. Source-only implementation preflight must pass.
6. Both replay output directories must not exist.
7. No prior result artifact may be reused, merged, or overwritten.
8. Confirmation must remain disabled.

Any failure must stop execution before predictor or outcome generation.

## Canonical output directories

Replay run 1:

- `artifacts/campaign50_development_validation_run1/`

Replay run 2:

- `artifacts/campaign50_development_validation_run2/`

The real execution entry point must reject a non-empty or pre-existing output directory.

## Canonical files per replay

Each replay must create exactly these six files:

1. `campaign50_preflight.json`
2. `campaign50_candidate_inventory.csv`
3. `campaign50_development_results.csv`
4. `campaign50_validation_results.csv`
5. `campaign50_shortlist.csv`
6. `campaign50_stage_manifest.json`

No extra analytical, diagnostic, temporary, debug, plot, notebook, cache, or ranking file may be written inside the canonical output directory.

## Proposed execution commands

These commands are documentation only until a separate execution GO enables the real runner.

### 1. Verify repository state

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
```

Expected:

- branch is `agent/campaign-50-holdout-first-alpha-research-planning`;
- no tracked modifications;
- unrelated local untracked files are not added, moved, or committed;
- the exact execution commit is recorded before the run.

### 2. Rerun synthetic validation

```powershell
python -m pytest tests/test_campaign50_equity_breadth.py -q
```

Any test failure is terminal for the proposed execution.

### 3. Rerun source-only preflight

```powershell
python -m scripts.preflight_campaign50_equity_breadth `
  --data-root data `
  --output artifacts/campaign50_implementation_preflight_before_execution.json
```

Required fields:

- `status == "PASS"`
- `candidate_count == 24`
- `confirmation_enabled == false`
- `predictors_generated == false`
- `outcomes_generated == false`

### 4. Confirm clean replay destinations

```powershell
$run1 = ".\artifacts\campaign50_development_validation_run1"
$run2 = ".\artifacts\campaign50_development_validation_run2"

if (Test-Path $run1) { throw "RUN1_OUTPUT_ALREADY_EXISTS" }
if (Test-Path $run2) { throw "RUN2_OUTPUT_ALREADY_EXISTS" }
```

Directories may be created only by the authorized runner after all preflight checks pass.

### 5. Proposed replay run 1

```powershell
python -m scripts.run_campaign50_development_validation `
  --data-root data `
  --output-dir artifacts/campaign50_development_validation_run1
```

### 6. Proposed replay run 2

```powershell
python -m scripts.run_campaign50_development_validation `
  --data-root data `
  --output-dir artifacts/campaign50_development_validation_run2
```

The proposed runner does not exist or is not enabled under the current HOLD. It may be added or enabled only under a board-recorded execution GO.

## Required runner behavior after future GO

The real runner must:

1. validate exact source hashes and ordered schemas;
2. validate strictly increasing unique sessions;
3. reject every row after `2024-12-31` before analytical construction;
4. validate the exact common calendar through `2024-12-31`;
5. construct exactly the frozen 24 candidates;
6. calculate only development and validation predictors/outcomes;
7. use only frozen formulas, horizons, anchors, support gates, OLS/HC3 inference, Holm correction, sign checks, and magnitude compatibility;
8. produce only the six canonical files;
9. use canonical UTF-8 and LF-only serialization;
10. fail closed on any unexpected state;
11. leave confirmation disabled and inaccessible.

## Replay identity verification

After both runs complete, compare exact file names, sizes, and SHA-256 values:

```powershell
$run1 = Resolve-Path .\artifacts\campaign50_development_validation_run1
$run2 = Resolve-Path .\artifacts\campaign50_development_validation_run2

$files1 = Get-ChildItem $run1 -File | Sort-Object Name
$files2 = Get-ChildItem $run2 -File | Sort-Object Name

if (($files1.Name -join "|") -ne ($files2.Name -join "|")) {
  throw "REPLAY_FILESET_MISMATCH"
}

$comparison = foreach ($file1 in $files1) {
  $file2 = Join-Path $run2 $file1.Name
  [pscustomobject]@{
    name = $file1.Name
    run1_length = $file1.Length
    run2_length = (Get-Item $file2).Length
    run1_sha256 = (Get-FileHash $file1.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    run2_sha256 = (Get-FileHash $file2 -Algorithm SHA256).Hash.ToLowerInvariant()
  }
}

$comparison | Format-Table -AutoSize

if ($comparison | Where-Object {
  $_.run1_length -ne $_.run2_length -or
  $_.run1_sha256 -ne $_.run2_sha256
}) {
  throw "REPLAY_IDENTITY_FAILURE"
}
```

All six corresponding files must be byte-identical.

## Manifest requirements

`campaign50_stage_manifest.json` must record at least:

- campaign identifier;
- stage identifier;
- repository commit SHA;
- statistical-specification commit SHA;
- source-universe commit SHA;
- exact source SHA-256 identities;
- exact development and validation intervals;
- candidate count `24`;
- canonical output file SHA-256 identities;
- predictors generated `true`;
- outcomes generated `true`;
- holdout loaded `false`;
- confirmation enabled `false`;
- method mutation `false`;
- deterministic status.

No wall-clock timestamp, machine-specific absolute path, random UUID, nondeterministic ordering, or environment-specific value may affect canonical artifact bytes.

## Human review boundary

After replay identity passes, review may inspect only:

- the six canonical run-1 artifacts;
- the replay hash comparison;
- the execution console log;
- repository and source identities.

Run 2 exists solely as replay evidence and must not be used as a second analytical trial.

No method, threshold, predictor, horizon, expected sign, support gate, covariance choice, multiplicity rule, or shortlist criterion may be changed in response to the results.

## Proposed post-run governance sequence

After a future authorized execution:

1. verify byte-identical replay;
2. inspect deterministic development and validation statuses;
3. commit one canonical result set and its manifest;
4. commit the frozen shortlist, including an empty shortlist if no candidate passes;
5. update the campaign board with execution evidence;
6. return to HOLD;
7. require a separate historical-confirmation GO before any 2025 source row is loaded analytically.

Development/validation success does not authorize holdout confirmation, economic testing, paper trading, or production behavior.

## Current decision

**HOLD.**

This procedure is prepared for review. Real Campaign #50 predictor and outcome generation remains prohibited until the authoritative campaign board records a separate execution GO.
