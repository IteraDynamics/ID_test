param(
    [string]$DataRoot = "",
    [string]$OutputRoot = "",
    [switch]$ReuseData
)
$ErrorActionPreference = "Stop"
$codeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $DataRoot) { $DataRoot = Join-Path $codeRoot "data\fresh_strategy_lab_20260914" }
if (-not $OutputRoot) { $OutputRoot = Join-Path $codeRoot "artifacts" }
$runId = "fresh_strategy_lab_{0}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff")
$outputPath = Join-Path $OutputRoot $runId
Push-Location $codeRoot
try {
    uv run --locked --python 3.12 python -m unittest discover -s tests -p test_fresh_strategy_lab.py -v
    if ($LASTEXITCODE -ne 0) { throw "Research mechanics tests failed. Share the complete error." }
    $runArgs = @(
        "run", "--locked", "--python", "3.12", "python", "-m", "research.fresh_lab.run",
        "--data-dir", $DataRoot, "--output-dir", $outputPath
    )
    if ($ReuseData) { $runArgs += "--reuse-data" }
    & uv @runArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Research run failed. Share the complete error and the printed progress."
    }
    Write-Host ("Share: {0}.zip" -f $outputPath)
} finally {
    Pop-Location
}
