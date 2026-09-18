param(
    [string]$Python = "3.12",
    [int]$Workers = 6,
    [string]$DataDir = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo

if ([string]::IsNullOrWhiteSpace($DataDir)) {
    $candidates = @(
        (Join-Path $repo "data"),
        "C:\Dev\IteraDynamics\ID_test\data"
    )
    $DataDir = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ([string]::IsNullOrWhiteSpace($DataDir) -or !(Test-Path $DataDir)) { throw "Data directory not found. Pass -DataDir explicitly." }

$btc = Join-Path $DataDir "btcusd_3600s_2018-01-01_to_2025-12-31.csv"
$eth = Join-Path $DataDir "ethusd_3600s_2018-01-01_to_2025-12-31.csv"
$spy = Join-Path $DataDir "SPY_1D.csv"
$qqq = Join-Path $DataDir "QQQ_1D.csv"
$bil = Join-Path $DataDir "BIL_1D.csv"
$gld = Join-Path $DataDir "GLD_1D.csv"
foreach ($p in @($btc,$eth,$spy,$qqq,$bil,$gld)) { if (!(Test-Path $p)) { throw "Required governed source missing: $p" } }

Write-Host "RRE / Core v1 governed BASE economic experiment"
Write-Host "Workers: $Workers"
Write-Host "Governed data directory: $DataDir"

uv run --python $Python pytest tests/test_rre_entry_deferral.py tests/test_rre_frozen_instability.py tests/test_rre_deferral_strategy.py -q
if ($LASTEXITCODE -ne 0) { throw "RRE qualification tests failed" }

$stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$out = "artifacts/rre_core_v1_entry_deferral_$stamp"

uv run --python $Python python scripts/run_rre_core_v1_entry_deferral_economic.py --workers $Workers --cost-case base --out-dir $out --btc-data $btc --eth-data $eth --spy-data $spy --qqq-data $qqq --bil-data $bil --gld-data $gld
if ($LASTEXITCODE -ne 0) { throw "Base economic experiment failed" }

Write-Host "RESULT DIRECTORY: $out"
Write-Host "If BASE_GATE_PASS=false, do not run stress; the frozen mechanism cannot advance."
