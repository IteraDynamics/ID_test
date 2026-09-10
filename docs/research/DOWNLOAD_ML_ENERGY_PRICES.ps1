& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Dev\IteraDynamics\ID_test'
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $out = Join-Path (Get-Location) "artifacts\ml_energy_prices_$stamp"
    if (Test-Path $out) { throw "Output already exists: $out" }
    foreach ($asset in @('USO', 'BIL')) {
        uv run --locked --python 3.12 python -m scripts.download_equity_data --asset $asset --start 2009-01-01 --end 2025-01-01 --auto-adjust --output-dir $out
        if ($LASTEXITCODE -ne 0) { throw "Download failed: $asset" }
        $csv = Join-Path $out ($asset + '_1D.csv')
        $manifest = $csv + '.manifest.json'
        if (!(Test-Path $csv) -or !(Test-Path $manifest)) { throw "Missing output: $asset" }
        $rows = @(Import-Csv $csv)
        if ($rows.Count -lt 1000 -or !($rows[0].PSObject.Properties.Name -contains 'close')) { throw "Invalid price CSV: $asset" }
        $meta = Get-Content $manifest -Raw | ConvertFrom-Json
        if ($meta.request.auto_adjust -ne $true) { throw "Prices are not adjusted: $asset" }
    }
    $zip = $out + '.zip'
    Compress-Archive -Path (Join-Path $out '*') -DestinationPath $zip
    Write-Host "Share this ZIP: $zip"
}
