param(
    [string]$Python = "3.12",
    [int]$Workers = 6
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo

Write-Host "RRE / Core v1 governed BASE economic experiment"
Write-Host "Workers: $Workers"

uv run --python $Python pytest tests/test_rre_entry_deferral.py tests/test_rre_frozen_instability.py tests/test_rre_deferral_strategy.py -q
if ($LASTEXITCODE -ne 0) { throw "RRE qualification tests failed" }

$stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$out = "artifacts/rre_core_v1_entry_deferral_$stamp"

uv run --python $Python python scripts/run_rre_core_v1_entry_deferral_economic.py --workers $Workers --cost-case base --out-dir $out
if ($LASTEXITCODE -ne 0) { throw "Base economic experiment failed" }

Write-Host "RESULT DIRECTORY: $out"
Write-Host "If BASE_GATE_PASS=false, do not run stress; the frozen mechanism cannot advance."
