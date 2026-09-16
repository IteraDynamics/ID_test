param(
    [string]$DataRoot = 'C:\Dev\IteraDynamics\ID_test\data',
    [string]$BtcCsv,
    [string]$EthCsv
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$DataRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DataRoot)
if ($BtcCsv) { $BtcCsv = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($BtcCsv) }
if ($EthCsv) { $EthCsv = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($EthCsv) }
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_core_regime_reuse.py -q -W error
    if ($LASTEXITCODE -ne 0) { throw 'Regime reuse tests failed.' }
    $runArgs = @('--data-root', $DataRoot, '--output-root', (Join-Path $codeRoot 'artifacts'))
    if ($BtcCsv) { $runArgs += @('--btc-csv', $BtcCsv) }
    if ($EthCsv) { $runArgs += @('--eth-csv', $EthCsv) }
    uv run --locked --python 3.12 python -m research.core_regime_reuse.run @runArgs
    if ($LASTEXITCODE -ne 0) { throw 'Regime reuse export failed; share the error.' }
} finally { Pop-Location }
