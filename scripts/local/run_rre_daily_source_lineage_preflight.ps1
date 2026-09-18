param(
    [string]$Python = "3.12",
    [string]$DataDir = "C:\Dev\IteraDynamics\ID_test\data"
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=(Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo
$stamp=Get-Date -Format "yyyyMMdd_HHmmss_fff"
$out="artifacts/rre_daily_source_lineage_$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null
Write-Host "RRE daily-market source lineage gate - SOURCE ONLY / NO PnL"
uv run --python $Python pytest tests/test_rre_daily_source_lineage.py -q
if ($LASTEXITCODE -ne 0) { throw "Synthetic daily-source lineage tests failed" }
uv run --python $Python python scripts/preflight_rre_daily_source_lineage.py --spy-data (Join-Path $DataDir "SPY_1D.csv") --qqq-data (Join-Path $DataDir "QQQ_1D.csv") --bil-data (Join-Path $DataDir "BIL_1D.csv") --gld-data (Join-Path $DataDir "GLD_1D.csv") --out-dir $out --output "$out\source_lineage.json"
if ($LASTEXITCODE -ne 0) { throw "Daily-source lineage gate failed" }
Write-Host "SOURCE-LINEAGE RESULT DIRECTORY: $out"
Write-Host "No economic run was started."
