[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$ManifestPath
)

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repositoryRoot "backend"
$toolPath = Join-Path $backendRoot "tools\import_gpt_reference.py"
$pythonCommand = Join-Path $repositoryRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonCommand -PathType Leaf)) {
    throw "root_virtualenv_missing: $pythonCommand"
}

& $pythonCommand $toolPath `
    --input-path $InputPath `
    --manifest-path $ManifestPath

exit $LASTEXITCODE
