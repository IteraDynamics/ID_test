param(
    [string]$SourceRun
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $SourceRun) { $SourceRun = Join-Path $codeRoot 'artifacts\fresh_crypto_20260914_110447_621' }
if (-not (Test-Path -LiteralPath $SourceRun)) {
    throw 'Source run not found. Supply -SourceRun with your completed fresh_crypto_20260914_110447_621 directory or ZIP.'
}
$sourcePath = (Resolve-Path -LiteralPath $SourceRun).ProviderPath
$outputPath = Join-Path $codeRoot ("artifacts\fresh_crypto_ml_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_fresh_crypto_ml.py -q -W error
    if ($LASTEXITCODE -ne 0) { throw 'ML accounting/leakage checks failed; share the error output.' }
    uv run --locked --python 3.12 --extra dev python -m research.fresh_crypto_ml.run --source-run $sourcePath --output-dir $outputPath
    if ($LASTEXITCODE -ne 0) { throw "ML discovery stopped; share the error output. Partial output: $outputPath" }
    Write-Host "Share this ML results ZIP: $outputPath.zip"
} finally {
    Pop-Location
}
