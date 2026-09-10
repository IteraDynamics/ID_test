param([Parameter(Mandatory=$true)][string]$InputRoot)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$inputPath = (Resolve-Path -LiteralPath $InputRoot).Path
$outputPath = Join-Path $inputPath ("artifacts\ml_options_variance_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 python -m scripts.prepare_ml_options_variance --input-root $inputPath --output-dir $outputPath
    if ($LASTEXITCODE -ne 0) { throw 'Options preparation failed. Share the error output.' }
    $zipPath = "$outputPath.zip"
    Compress-Archive -Path (Join-Path $outputPath '*') -DestinationPath $zipPath -ErrorAction Stop
    Write-Output "Upload this file: $zipPath"
} finally {
    Pop-Location
}
