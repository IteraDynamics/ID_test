param([Parameter(Mandatory=$true)][string]$InputRoot)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$inputPath = (Resolve-Path -LiteralPath $InputRoot).Path
$outputPath = Join-Path $inputPath ("artifacts\options_condor_panel_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --with pyarrow==21.0.0 python -m scripts.prepare_options_condor_panel --input-root $inputPath --output-dir $outputPath
    if ($LASTEXITCODE -ne 0) { throw 'Contract lifecycle extraction failed. Share the error output.' }
} finally {
    Pop-Location
}
