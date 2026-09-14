param(
    [string]$SourceRun
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$sourceArguments = @()
if ($SourceRun) {
    if (-not [System.IO.Path]::IsPathRooted($SourceRun)) {
        $SourceRun = Join-Path (Get-Location).Path $SourceRun
    }
    $sourceArguments = @('--source-run', $SourceRun)
}
$outputPath = Join-Path $codeRoot ("artifacts\fresh_crypto_long_history_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m research.fresh_crypto_long_history --check-data @sourceArguments
    if ($LASTEXITCODE -ne 0) { throw 'Source check failed. Share the printed error, including the checked paths.' }
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_fresh_crypto_long_history.py -q -W error
    if ($LASTEXITCODE -ne 0) { throw 'Fixed-rule correctness checks failed; share the test output.' }
    uv run --locked --python 3.12 --extra dev python -m research.fresh_crypto_long_history @sourceArguments --output-dir $outputPath
    if ($LASTEXITCODE -ne 0) { throw "Long-history run stopped; share the error output. Partial output: $outputPath" }
    Write-Host "Share this long-history results ZIP: $outputPath.zip"
} finally {
    Pop-Location
}
