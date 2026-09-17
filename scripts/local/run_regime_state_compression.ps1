param([string]$DataRoot = 'C:\Dev\IteraDynamics\ID_test\data')
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$DataRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DataRoot)
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_core_regime_reuse.py tests/test_multidimensional_regimes.py tests/test_regime_state_compression.py -q -W error
    if ($LASTEXITCODE -ne 0) { throw 'Compression-study tests failed.' }
    uv run --locked --python 3.12 python -m research.regime_state_compression.run --data-root $DataRoot --output-root (Join-Path $codeRoot 'artifacts')
    if ($LASTEXITCODE -ne 0) { throw 'Compression study failed; share the diagnostic ZIP or error.' }
} finally { Pop-Location }
