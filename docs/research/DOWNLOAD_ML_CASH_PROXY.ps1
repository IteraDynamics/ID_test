& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Dev\IteraDynamics\ID_test'
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $out = Join-Path (Get-Location) "artifacts\ml_cash_proxy_$stamp"
    uv run --locked --python 3.12 python -m scripts.download_equity_data `
        --asset BIL --start 2013-12-02 --end 2025-01-01 `
        --auto-adjust --output-dir $out
    if ($LASTEXITCODE -ne 0) { throw 'Cash-proxy download failed. Share the error output.' }
    $files = @()
    foreach ($name in @('BIL_1D.csv','BIL_1D.csv.manifest.json')) {
        $path = Join-Path $out $name
        if (-not (Test-Path -LiteralPath $path)) { throw "Missing expected file: $path" }
        $files += $path
    }
    $zip = "$out.zip"
    Compress-Archive -LiteralPath $files -DestinationPath $zip
    Write-Output "Share this ZIP: $zip"
}
