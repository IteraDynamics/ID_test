param(
    [string]$DataRoot = 'C:\Dev\IteraDynamics\ID_test\data'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root

uv sync --locked --python 3.12 --extra dev
if ($LASTEXITCODE -ne 0) { throw 'Environment sync failed.' }

uv run --locked --python 3.12 --extra dev python -m pytest tests/test_campaign52_target_replay.py tests/test_rre_core_v1_control_qualification.py -q
if ($LASTEXITCODE -ne 0) { throw 'Core v1 control qualification tests failed.' }

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$out = Join-Path $root "artifacts\rre_core_v1_control_$stamp"

uv run --locked --python 3.12 python scripts/run_rre_core_v1_control_qualification.py --btc-data (Join-Path $DataRoot 'btcusd_3600s_2018-01-01_to_2025-12-31.csv') --eth-data (Join-Path $DataRoot 'ethusd_3600s_2018-01-01_to_2025-12-31.csv') --spy-data (Join-Path $DataRoot 'SPY_1D.csv') --qqq-data (Join-Path $DataRoot 'QQQ_1D.csv') --bil-data (Join-Path $DataRoot 'BIL_1D.csv') --gld-data (Join-Path $DataRoot 'GLD_1D.csv') --out-dir $out --pass-workers 2
if ($LASTEXITCODE -ne 0) { throw 'Core v1 control qualification failed.' }

Write-Host ""
Write-Host "Share these three small files:"
Write-Host "  $out\share\qualification_manifest.json"
Write-Host "  $out\share\sleeve_inventory.json"
Write-Host "  $out\share\guardrails.json"
