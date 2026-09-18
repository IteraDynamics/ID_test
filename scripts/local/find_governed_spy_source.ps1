param(
    [string]$Root = "C:\Dev\IteraDynamics",
    [string]$ExpectedHash = "85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "Searching for exact governed SPY source by SHA-256."
Write-Host "Root: $Root"
Write-Host "Expected: $ExpectedHash"

$extensions = @(".csv", ".bak", ".txt", ".dat")
$candidates = Get-ChildItem $Root -File -Recurse -ErrorAction SilentlyContinue | Where-Object {
    ($extensions -contains $_.Extension.ToLower()) -and ($_.Length -ge 200000) -and ($_.Length -le 225000)
}

$checked = 0
foreach ($file in $candidates) {
    $checked++
    $hash = (Get-FileHash $file.FullName -Algorithm SHA256).Hash.ToLower()
    if ($hash -eq $ExpectedHash) {
        Write-Host "FOUND: $($file.FullName)"
        Write-Host "Bytes: $($file.Length)"
        exit 0
    }
}

Write-Host "NOT FOUND. Candidates hashed: $checked"
Write-Host "No file was created, modified, copied, or downloaded."
exit 2
