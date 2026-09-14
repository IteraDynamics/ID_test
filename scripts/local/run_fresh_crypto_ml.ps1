param(
    [string]$SourceRun
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $SourceRun) { $SourceRun = Join-Path $codeRoot 'artifacts\fresh_crypto_20260914_110447_621' }
if (-not (Test-Path -LiteralPath $SourceRun)) {
    $zipPath = $SourceRun.TrimEnd([char[]]'\/') + '.zip'
    if (Test-Path -LiteralPath $zipPath -PathType Leaf) {
        $SourceRun = $zipPath
    } else {
        throw "Previous results not found at '$SourceRun' or '$zipPath'. Git does not restore local result files. Restore fresh_crypto_20260914_110447_621.zip to the artifacts folder, or pass its absolute path with -SourceRun. This argument expects the prior results, not the raw data folder."
    }
}
$sourcePath = (Resolve-Path -LiteralPath $SourceRun).ProviderPath
Write-Host "Reusing crypto inputs from: $sourcePath"
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
