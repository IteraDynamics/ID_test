param(
    [string]$Root = "C:\Dev",
    [string]$ExpectedHash = "34867c2b2da4aece23892b8e035e528f547173f3bc137cbe33b1295af0c1ff7b"
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
Write-Host "Searching for exact governed QQQ source by SHA-256."
Write-Host "Root: $Root"
Write-Host "Expected: $ExpectedHash"
$files=Get-ChildItem $Root -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Length -ge 190000 -and $_.Length -le 260000 -and -not ($_.FullName -match "\\AppData\\|\\node_modules\\|\\\.git\\|\\venv\\|\\\.venv\\") }
$checked=0
foreach($file in $files){
$checked++
try{$hash=(Get-FileHash $file.FullName -Algorithm SHA256 -ErrorAction Stop).Hash.ToLower()}catch{continue}
if($hash -eq $ExpectedHash){Write-Host "FOUND: $($file.FullName)";Write-Host "Bytes: $($file.Length)";exit 0}
}
Write-Host "NOT FOUND. Candidates hashed: $checked"
Write-Host "No file was modified."
exit 2
