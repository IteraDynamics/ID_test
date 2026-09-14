param(
    [string]$DataRoot,
    [switch]$Offline
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $DataRoot) { $DataRoot = Join-Path $codeRoot 'data\fresh_discovery_20260914' }
$dataPath = [System.IO.Path]::GetFullPath($DataRoot)
$outputPath = Join-Path $codeRoot ("artifacts\fresh_discovery_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_fresh_strategy_discovery.py -q
    if ($LASTEXITCODE -ne 0) { throw 'Research correctness checks failed; share the error output.' }
    $arguments = @('run', '--locked', '--python', '3.12', '--extra', 'dev', 'python', '-m',
                   'research.fresh_discovery.run', '--data-root', $dataPath, '--output-dir', $outputPath)
    if (-not $Offline) { $arguments += '--download' }
    & uv @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Discovery run failed; share the error output. Verified downloads remain cached.' }
    Write-Host "Share this results ZIP: $outputPath.zip"
} finally {
    Pop-Location
}
