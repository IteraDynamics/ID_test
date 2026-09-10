# Read existing files only. No checkout, download, or model run required.
& {
    $ErrorActionPreference = 'Stop'
    $repo = 'C:\Dev\IteraDynamics\ID_test'
    $files = @()
    foreach ($ticker in @('IWM','EFA','EEM','IEF','TLT')) {
        $csv = Join-Path $repo "data\${ticker}_1D.csv"
        if (-not (Test-Path -LiteralPath $csv)) { throw "Missing expected file: $csv" }
        $files += $csv
        $manifest = "$csv.manifest.json"
        if (Test-Path -LiteralPath $manifest) { $files += $manifest }
    }
    $destination = Join-Path $repo ("ml_breadth_inputs_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.zip')
    Compress-Archive -LiteralPath $files -DestinationPath $destination
    Write-Output "Share this ZIP: $destination"
}
