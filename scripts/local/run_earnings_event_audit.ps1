param(
    [string]$DataRoot = 'C:\Dev\IteraDynamics\ID_test\data',
    [string]$EarningsCsv
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
# Resolve user paths before changing working directory.
$DataRoot = (Resolve-Path -LiteralPath $DataRoot).Path
if ($EarningsCsv) { $EarningsCsv = (Resolve-Path -LiteralPath $EarningsCsv).Path }
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_earnings_event_audit.py -q -W error
    if ($LASTEXITCODE -ne 0) { throw 'Audit tests failed.' }
    $runArgs = @('--data-root', $DataRoot, '--output-dir', (Join-Path $codeRoot 'artifacts'))
    if ($EarningsCsv) { $runArgs += @('--earnings-csv', $EarningsCsv) }
    uv run --locked --python 3.12 python -m research.earnings_event.audit @runArgs
    if ($LASTEXITCODE -ne 0) { throw 'Audit failed; share the error.' }
} finally { Pop-Location }
