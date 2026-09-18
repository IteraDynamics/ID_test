param([string]$Python = "3.12")

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo

Write-Host "RRE entry-deferral pre-economic qualification"
Write-Host "No governed market backtest or P&L is executed by this script."

uv sync --locked --python $Python --extra dev
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

uv run --python $Python pytest tests/test_campaign52_target_replay.py tests/test_rre_core_v1_control_qualification.py tests/test_rre_entry_deferral.py -q
if ($LASTEXITCODE -ne 0) { throw "Pre-economic qualification tests failed" }

Write-Host "PASS: synthetic replay/intervention guardrails only."
Write-Host "Economic execution remains blocked pending review."
