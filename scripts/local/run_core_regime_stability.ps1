param([string]$DataRoot = 'C:\Dev\IteraDynamics\ID_test\data')
$ErrorActionPreference='Stop'
$codeRoot=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$DataRoot=$ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DataRoot)
Push-Location $codeRoot
try {
 uv run --locked --python 3.12 --extra dev python -m pytest tests/test_core_regime_reuse.py tests/test_multidimensional_regimes.py tests/test_regime_state_compression.py tests/test_latent_state_trajectories.py tests/test_latent_transition_geometry.py tests/test_core_regime_stability.py -q -W error
 if($LASTEXITCODE-ne 0){throw 'Core stability tests failed.'}
 uv run --locked --python 3.12 python -m research.core_regime_stability.run --data-root $DataRoot --output-root (Join-Path $codeRoot 'artifacts')
 if($LASTEXITCODE-ne 0){throw 'Core stability study failed.'}
} finally {Pop-Location}
