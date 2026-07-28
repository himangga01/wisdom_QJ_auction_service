[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]{1,100}$')]
    [string]$CaseId,

    [Parameter(Mandatory = $true)]
    [ValidateSet('true', 'false')]
    [string]$IncludeDetails,

    [Parameter(Mandatory = $true)]
    [ValidateSet('normal', 'careful', 'very_careful')]
    [string]$DelayProfile,

    [Parameter(Mandatory = $true)]
    [string]$ApprovalPhrase,

    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [Parameter(Mandatory = $true)]
    [string]$ReferencePath,

    [Parameter(Mandatory = $true)]
    [string]$ArtifactDirectory,

    [string]$CdpUrl = 'http://127.0.0.1:42973'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($ApprovalPhrase -cne 'RUN_ONE_APARTMENT') {
    throw 'approval_phrase_mismatch'
}

if ($CdpUrl -cne 'http://127.0.0.1:42973') {
    throw 'cdp_endpoint_invalid'
}

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$backendRoot = Join-Path $repositoryRoot 'backend'
$runnerTool = Join-Path $backendRoot 'tools\run_live_naver_e2e.py'
$pythonCommand = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonCommand -PathType Leaf)) {
    throw 'runner_root_virtual_environment_missing'
}
$manifestFullPath = [System.IO.Path]::GetFullPath($ManifestPath)
$referenceFullPath = [System.IO.Path]::GetFullPath($ReferencePath)
$artifactFullPath = [System.IO.Path]::GetFullPath($ArtifactDirectory)
$repositoryPrefix = $repositoryRoot.TrimEnd('\') + '\'

foreach ($localInputPath in @($manifestFullPath, $referenceFullPath)) {
    if (
        $localInputPath.StartsWith(
            $repositoryPrefix,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw 'runner_local_input_must_be_outside_checkout'
    }
    if (-not (Test-Path -LiteralPath $localInputPath -PathType Leaf)) {
        throw 'runner_local_input_missing'
    }
}

if (
    $artifactFullPath.StartsWith(
        $repositoryPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )
) {
    throw 'artifact_directory_must_be_outside_checkout'
}

New-Item -ItemType Directory -Path $artifactFullPath -Force | Out-Null

Push-Location $backendRoot
try {
    & $pythonCommand $runnerTool `
        --case-id $CaseId `
        --include-details $IncludeDetails `
        --delay-profile $DelayProfile `
        --manifest-path $manifestFullPath `
        --reference-path $referenceFullPath `
        --artifact-directory $artifactFullPath `
        --cdp-url $CdpUrl
    if ($LASTEXITCODE -ne 0) {
        throw "live_e2e_failed:$LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
