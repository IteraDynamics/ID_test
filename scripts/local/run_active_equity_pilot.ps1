param(
    [ValidateSet('Init', 'Report', 'Verify')]
    [string]$Mode = 'Init',
    [string]$PilotDir,
    [string]$DataRoot
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
# Resolve caller-relative inputs before changing directory.
foreach ($name in @('PilotDir', 'DataRoot')) {
    $value = Get-Variable -Name $name -ValueOnly
    if ($value -and -not [System.IO.Path]::IsPathRooted($value)) {
        Set-Variable -Name $name -Value (Join-Path (Get-Location).Path $value)
    }
}
if ($DataRoot -and -not (Test-Path -LiteralPath $DataRoot -PathType Container)) {
    throw "DataRoot does not exist: $DataRoot"
}
if (-not $PilotDir) {
    if ($Mode -ne 'Init') { throw 'Report/Verify require -PilotDir for your existing pilot.' }
    $PilotDir = Join-Path $codeRoot ("artifacts\active_equity_pilot_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
}
if ($Mode -eq 'Init' -and (Test-Path -LiteralPath $PilotDir)) {
    throw 'PilotDir already exists. Use -Mode Report to inspect it; initialization never overwrites.'
}
$runArgs = @($Mode.ToLowerInvariant(), '--pilot-dir', $PilotDir)
if ($DataRoot) { $runArgs += @('--data-root', $DataRoot) }
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_active_equity_pilot.py -q -W error
    if ($LASTEXITCODE -ne 0) { throw 'Pilot correctness tests failed; no pilot command was run.' }
    uv run --locked --python 3.12 --extra dev python -m research.active_equity.pilot @runArgs
    if ($LASTEXITCODE -ne 0) { throw 'Pilot command failed. Share the error; no orders were placed.' }
    Write-Host "KEEP PILOT DIRECTORY: $PilotDir"
    Write-Host 'This is the decision-recording pilot, not an investment performance run.'
} finally {
    Pop-Location
}
