param(
    [string]$DataRoot,
    [string]$BtcCsv,
    [string]$EthCsv,
    [string]$SourceLabel = 'operator_local_unverified',
    [switch]$DownloadMissing
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $DataRoot) { $DataRoot = Join-Path $codeRoot 'data' }
$dataPath = [System.IO.Path]::GetFullPath($DataRoot)
if ($BtcCsv) { $BtcCsv = [System.IO.Path]::GetFullPath($BtcCsv) }
if ($EthCsv) { $EthCsv = [System.IO.Path]::GetFullPath($EthCsv) }
$outputPath = Join-Path $codeRoot ("artifacts\fresh_crypto_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_fresh_crypto_discovery.py -q
    if ($LASTEXITCODE -ne 0) { throw 'Crypto research correctness checks failed; share the error output.' }
    $arguments = @('run', '--locked', '--python', '3.12', '--extra', 'dev', 'python', '-m',
                   'research.fresh_crypto.run', '--data-root', $dataPath, '--output-dir', $outputPath,
                   '--source-label', $SourceLabel)
    if ($BtcCsv) { $arguments += @('--btc-csv', $BtcCsv) }
    if ($EthCsv) { $arguments += @('--eth-csv', $EthCsv) }
    if ($DownloadMissing) { $arguments += '--download-missing' }
    & uv @arguments
    if ($LASTEXITCODE -ne 0) { throw "Run stopped; share the printed data-check ZIP or error. Output: $outputPath" }
    Write-Host "Share this results ZIP: $outputPath.zip"
} finally {
    Pop-Location
}
