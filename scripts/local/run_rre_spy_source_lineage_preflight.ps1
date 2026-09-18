param(
    [string]$Python = "3.12",
    [string]$DataDir = "C:\Dev\IteraDynamics\ID_test\data"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo=(Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo

$spy=Join-Path $DataDir "SPY_1D.csv"
$qqq=Join-Path $DataDir "QQQ_1D.csv"
if (!(Test-Path $spy)) { throw "SPY source missing: $spy" }
if (!(Test-Path $qqq)) { throw "QQQ source missing: $qqq" }

$stamp=Get-Date -Format "yyyyMMdd_HHmmss_fff"
$out="artifacts/rre_spy_source_lineage_$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null

Write-Host "RRE SPY source-lineage gate - SOURCE ONLY / NO PnL"
uv run --python $Python pytest tests/test_rre_spy_source_lineage.py -q
if ($LASTEXITCODE -ne 0) { throw "Synthetic source-lineage tests failed" }

uv run --python $Python python scripts/preflight_rre_spy_source_lineage.py --spy-data $spy --qqq-data $qqq --normalized-spy "$out\SPY_1D_RRE_AMENDED.csv" --output "$out\source_lineage.json"
if ($LASTEXITCODE -ne 0) { throw "SPY source-lineage gate failed" }

Write-Host "SOURCE-LINEAGE RESULT DIRECTORY: $out"
Write-Host "No economic run was started."
