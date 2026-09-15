param(
    [ValidateSet('Enroll', 'Collect')]
    [string]$Mode = 'Enroll',
    [Parameter(Mandatory=$true)]
    [string]$PilotDir,
    [string]$SecUserAgent
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not [System.IO.Path]::IsPathRooted($PilotDir)) {
    $PilotDir = Join-Path (Get-Location).Path $PilotDir
}
if (-not (Test-Path -LiteralPath (Join-Path $PilotDir 'ledger.sqlite') -PathType Leaf)) {
    throw "Existing pilot ledger not found: $PilotDir"
}
if (-not $SecUserAgent) {
    $contact = Read-Host 'SEC requests a real contact email for its public-data User-Agent'
    $SecUserAgent = "IteraDynamics research $contact"
}
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 --extra dev python -m pytest tests/test_active_equity_pilot.py tests/test_active_equity_sec_feed.py -q -W error
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; feed command was not run.' }
    $runArgs = @($Mode.ToLowerInvariant(), '--pilot-dir', $PilotDir, '--user-agent', $SecUserAgent)
    uv run --locked --python 3.12 --extra dev python -m research.active_equity.sec_feed @runArgs
    if ($LASTEXITCODE -ne 0) { throw 'SEC feed stopped. Share the error; do not initialize a replacement pilot.' }
} finally {
    Pop-Location
}
