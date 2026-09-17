param([string]$DataRoot='C:\Dev\IteraDynamics\ID_test\data')
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
uv sync --locked --python 3.12 --extra dev
if($LASTEXITCODE-ne 0){throw 'Environment sync failed.'}
uv run --locked --python 3.12 --extra dev python -m pytest tests/test_core_regime_reuse.py tests/test_regime_state_compression.py tests/test_conditional_market_behavior.py tests/test_core_pca4_economic_comparison.py -q -W error
if($LASTEXITCODE-ne 0){throw 'Core PCA4 economic comparison tests failed.'}
uv run --locked --python 3.12 python -m research.core_pca4_economic_comparison.run --data-root $DataRoot --output-root (Join-Path $root 'artifacts')
if($LASTEXITCODE-ne 0){throw 'Core PCA4 economic comparison study failed.'}
