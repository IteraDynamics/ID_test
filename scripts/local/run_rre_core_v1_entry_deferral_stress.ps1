param(
    [Parameter(Mandatory=$true)][string]$OutDir,
    [string]$Python = "3.12",
    [int]$Workers = 6
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo

$baseSummary = Join-Path $OutDir "base\summary.json"
if (!(Test-Path $baseSummary)) { throw "Base summary not found: $baseSummary" }
$base = Get-Content $baseSummary -Raw | ConvertFrom-Json
if (-not $base.base_gate_pass) { throw "Base gate is false. Frozen mechanism cannot advance; stress run is intentionally blocked." }

Write-Host "Base gate remains eligible. Running frozen 2x execution-cost stress."
uv run --python $Python python scripts/run_rre_core_v1_entry_deferral_economic.py --workers $Workers --cost-case stress --out-dir $OutDir
if ($LASTEXITCODE -ne 0) { throw "Stress economic experiment failed" }

Write-Host "STRESS COMPLETE: $OutDir"
