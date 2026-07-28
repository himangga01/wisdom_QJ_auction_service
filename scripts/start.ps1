[CmdletBinding()]
param(
    [ValidateSet('local', 'docker')]
    [string]$Mode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'runtime-common.ps1')

if ([string]::IsNullOrWhiteSpace($Mode)) {
    Write-Host '실행 방식을 선택하세요.'
    Write-Host '  1. local  - Docker 없이 SQLite로 실행'
    Write-Host '  2. docker - PostgreSQL, Redis, Celery로 실행'
    $selection = Read-Host '번호 입력'
    switch ($selection) {
        '1' { $Mode = 'local' }
        '2' { $Mode = 'docker' }
        default { throw '1 또는 2를 입력해야 합니다.' }
    }
}

if ($Mode -eq 'local') {
    & (Join-Path $PSScriptRoot 'start-local.ps1')
    return
}

$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
if ($null -eq $dockerCommand) {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
}
if ($null -eq $dockerCommand) {
    throw 'Docker CLI를 찾을 수 없습니다. docs/setup/docker-setup.md를 따라 Docker Desktop을 설치하세요.'
}

$dockerEnvFile = Join-Path $BackendRoot '.env'
if (-not (Test-Path -LiteralPath $dockerEnvFile -PathType Leaf)) {
    throw 'backend/.env가 없습니다. backend/.env.example을 복사하고 값을 확인한 뒤 다시 실행하세요.'
}
$runtimeSetting = Select-String -LiteralPath $dockerEnvFile -Pattern '^\s*APP_RUNTIME\s*=\s*docker\s*$' -CaseSensitive:$false
if ($null -eq $runtimeSetting) {
    throw 'Docker 실행을 위해 backend/.env에 APP_RUNTIME=docker를 설정하세요.'
}

Assert-LocalPortAvailable -Port $ApiPort -ServiceName 'API'
Assert-LocalPortAvailable -Port $PortalPort -ServiceName '포탈'

Invoke-CheckedCommand `
    -Executable $dockerCommand.Source `
    -Arguments @('info', '--format', '{{.ServerVersion}}') `
    -WorkingDirectory $RepositoryRoot `
    -FailureMessage 'Docker Desktop이 실행 중인지 확인할 수 없습니다.'

$composeFile = Join-Path $RepositoryRoot 'docker-compose.production.yml'
Invoke-CheckedCommand `
    -Executable $dockerCommand.Source `
    -Arguments @(
        'compose',
        '--env-file', $dockerEnvFile,
        '-f', $composeFile,
        'up', '-d', '--build'
    ) `
    -WorkingDirectory $RepositoryRoot `
    -FailureMessage 'Docker Compose 서비스 시작에 실패했습니다.'

Write-Host ''
Write-Host "포탈: http://127.0.0.1:$PortalPort"
Write-Host "API:  http://127.0.0.1:$ApiPort"
