param(
    [string]$DataRoot,
    [string]$SourceRun,
    [string]$BtcCsv,
    [string]$EthCsv,
    [ValidateSet('unknown', 'already_inspected', 'not_known_inspected')]
    [string]$PriorAccess2026 = 'unknown'
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$inputArguments = @('--prior-access-2026', $PriorAccess2026)
foreach ($entry in @(
    @{ Name = '--data-root'; Value = $DataRoot },
    @{ Name = '--source-run'; Value = $SourceRun },
    @{ Name = '--btc-csv'; Value = $BtcCsv },
    @{ Name = '--eth-csv'; Value = $EthCsv }
)) {
    if ($entry.Value) {
        $resolved = $entry.Value
        if (-not [System.IO.Path]::IsPathRooted($resolved)) {
            $resolved = Join-Path (Get-Location).Path $resolved
        }
        $inputArguments += @($entry.Name, $resolved)
    }
}
$outputPath = Join-Path $codeRoot ("artifacts\fresh_crypto_forward_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m research.fresh_crypto_forward --prepare @inputArguments --output-dir $outputPath
    if ($LASTEXITCODE -ne 0) { throw 'Data preparation failed. Share the printed data-check ZIP and error.' }
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_fresh_crypto_forward.py tests/test_fresh_crypto_long_history.py -q -W error
    if ($LASTEXITCODE -ne 0) { throw "Correctness checks failed. Share the test output. Prepared inputs: $outputPath" }
    uv run --locked --python 3.12 --extra dev python -m research.fresh_crypto_forward --evaluate-prepared --output-dir $outputPath
    if ($LASTEXITCODE -ne 0) { throw "Forward run stopped; share the error. Partial output: $outputPath" }
    Write-Host "Share this forward results ZIP: $outputPath.zip"
} finally {
    Pop-Location
}
