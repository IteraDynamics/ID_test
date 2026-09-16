param(
    [string]$DataRoot = 'C:\Dev\IteraDynamics\ID_test\data',
    [string]$BtcCsv,
    [string]$EthCsv,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
# Resolve relative user paths in the invoking shell before changing location.
$DataRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DataRoot)
if ($BtcCsv) { $BtcCsv = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($BtcCsv) }
if ($EthCsv) { $EthCsv = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($EthCsv) }
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_crypto_reversal.py -q -W error
    if ($LASTEXITCODE -ne 0) { throw 'Crypto reversal tests failed.' }
    $runArgs = @('--data-root', $DataRoot, '--output-root', (Join-Path $codeRoot 'artifacts'))
    if ($BtcCsv) { $runArgs += @('--btc-csv', $BtcCsv) }
    if ($EthCsv) { $runArgs += @('--eth-csv', $EthCsv) }
    if ($CheckOnly) { $runArgs += '--check-only' }
    uv run --locked --python 3.12 python -m research.crypto_reversal.run @runArgs
    if ($LASTEXITCODE -ne 0) { throw 'Run failed; share the printed diagnostic ZIP.' }
} finally { Pop-Location }
