[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactsRoot = Join-Path $repoRoot "artifacts"

$expectedStreams = @(
    "btc_medium_up.csv",
    "btc_extended_up.csv",
    "eth_medium_up.csv",
    "eth_extended_up.csv"
)

function Test-StreamDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.DirectoryInfo]$Directory
    )

    foreach ($name in $expectedStreams) {
        if (-not (Test-Path (Join-Path $Directory.FullName $name) -PathType Leaf)) {
            return $false
        }
    }
    return $true
}

function Find-LatestStreamDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LeafName
    )

    if (-not (Test-Path $artifactsRoot -PathType Container)) {
        return $null
    }

    return Get-ChildItem $artifactsRoot -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq $LeafName -and (Test-StreamDirectory -Directory $_) } |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
}

function Find-LatestRunDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArtifactFolder,

        [Parameter(Mandatory = $true)]
        [string]$RequiredFile
    )

    $root = Join-Path $artifactsRoot $ArtifactFolder
    if (-not (Test-Path $root -PathType Container)) {
        return $null
    }

    return Get-ChildItem $root -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName $RequiredFile) -PathType Leaf } |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
}

$predictionsDirectory = Find-LatestStreamDirectory -LeafName "predictions"
$featuresDirectory = Find-LatestStreamDirectory -LeafName "features"
$evidenceRunDirectory = if ($featuresDirectory) { $featuresDirectory.Parent } else { $null }
$diagnosisRunDirectory = Find-LatestRunDirectory `
    -ArtifactFolder "core_v1_jump_risk_diagnosis_v2" `
    -RequiredFile "jump_risk_diagnosis_v2_summary.json"

Set-Variable -Name repoRoot -Value $repoRoot -Scope Global -Force
Set-Variable -Name artifactsRoot -Value $artifactsRoot -Scope Global -Force
Set-Variable -Name predictionsDir -Value $(if ($predictionsDirectory) { $predictionsDirectory.FullName } else { $null }) -Scope Global -Force
Set-Variable -Name predictionsRun -Value $(if ($predictionsDirectory) { $predictionsDirectory.Parent.FullName } else { $null }) -Scope Global -Force
Set-Variable -Name featuresDir -Value $(if ($featuresDirectory) { $featuresDirectory.FullName } else { $null }) -Scope Global -Force
Set-Variable -Name evidenceRun -Value $(if ($evidenceRunDirectory) { $evidenceRunDirectory.FullName } else { $null }) -Scope Global -Force
Set-Variable -Name diagnosisV2Run -Value $(if ($diagnosisRunDirectory) { $diagnosisRunDirectory.FullName } else { $null }) -Scope Global -Force

Write-Host "Itera Dynamics development session initialized"
Write-Host "Repo root:       $repoRoot"
Write-Host "Artifacts root:  $artifactsRoot"
Write-Host "Predictions dir: $(if ($predictionsDir) { $predictionsDir } else { '<not found>' })"
Write-Host "Features dir:    $(if ($featuresDir) { $featuresDir } else { '<not found>' })"
Write-Host "Diagnosis V2:    $(if ($diagnosisV2Run) { $diagnosisV2Run } else { '<not found>' })"

if (-not $predictionsDir) {
    Write-Warning "No prediction directory containing all four expected Jump Risk streams was found."
}

if (-not $featuresDir) {
    Write-Host "Feature evidence has not been exported yet. Run export_core_v1_jump_risk_evidence.py after predictionsDir is available."
}
