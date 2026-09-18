param([string]$Python = "3.12")

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo

Write-Host "RRE / Core v1 economic preflight — NO market backtest / NO P&L"

uv run --python $Python pytest tests/test_rre_entry_deferral.py tests/test_rre_frozen_instability.py -q
if ($LASTEXITCODE -ne 0) { throw "RRE frozen-component tests failed" }

uv run --python $Python python scripts/run_rre_entry_deferral_preflight.py
if ($LASTEXITCODE -ne 0) { throw "RRE economic preflight failed" }

Write-Host "PASS: frozen allocation/model/intervention identity. Economic run not started."
