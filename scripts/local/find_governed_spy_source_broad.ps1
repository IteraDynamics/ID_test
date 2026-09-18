param(
    [string]$SearchRoot = "C:\Dev",
    [string]$ExpectedHash = "85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "Searching broader local disk for exact governed SPY source."
Write-Host "Root: $SearchRoot"
Write-Host "Expected: $ExpectedHash"

$exclude = @("\AppData\","\node_modules\","\.git\","\venv\","\.venv\")
$files = Get-ChildItem $SearchRoot -File -Recurse -ErrorAction SilentlyContinue | Where-Object {
    $_.Length -ge 210000 -and $_.Length -le 218000 -and
    -not ($_.FullName -match "\\AppData\\|\\node_modules\\|\\\.git\\|\\venv\\|\\\.venv\\")
}
$checked = 0
foreach ($file in $files) {
    $checked++
    try { $hash = (Get-FileHash $file.FullName -Algorithm SHA256 -ErrorAction Stop).Hash.ToLower() } catch { continue }
    if ($hash -eq $ExpectedHash) {
        Write-Host "FOUND: $($file.FullName)"
        Write-Host "Bytes: $($file.Length)"
        exit 0
    }
}
Write-Host "NOT FOUND. Candidates hashed: $checked"
Write-Host "No file was modified."
exit 2
