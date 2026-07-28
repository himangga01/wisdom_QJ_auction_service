[CmdletBinding()]
param(
    [ValidateSet('local', 'docker')]
    [string]$Mode = 'local'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'runtime-common.ps1')

if ($Mode -eq 'docker') {
    $dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($null -eq $dockerCommand) {
        $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    }
    if ($null -eq $dockerCommand) {
        throw 'Docker CLI를 찾을 수 없습니다.'
    }
    $composeFile = Join-Path $RepositoryRoot 'docker-compose.production.yml'
    & $dockerCommand.Source compose -f $composeFile ps chrome
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Chrome 상태를 확인하지 못했습니다.'
    }
    $health = Get-ApiHealth
    if ($null -eq $health) {
        Write-Host 'API health: 응답 없음'
    }
    else {
        Write-Host ("API health: {0}, Chrome readiness: {1}" -f $health.status, $health.browser)
    }
    return
}

function Write-ComponentStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string]$PidFile,
        [Parameter(Mandatory = $true)]
        [ValidateSet('api', 'frontend')]
        [string]$Component
    )

    $recordedProcessId = Read-RecordedProcessId -PidFile $PidFile
    if ($null -eq $recordedProcessId) {
        Write-Host ("{0}: 중지됨 (PID 기록 없음)" -f $Label)
        return
    }

    $runningProcess = Get-Process -Id $recordedProcessId -ErrorAction SilentlyContinue
    if ($null -eq $runningProcess) {
        Write-Host ("{0}: 중지됨 (기록된 PID {1} 없음)" -f $Label, $recordedProcessId)
        return
    }

    if (Test-ProjectProcess -ProcessId $recordedProcessId -Component $Component) {
        Write-Host ("{0}: 실행 중 (PID {1})" -f $Label, $recordedProcessId)
        return
    }

    Write-Warning ("{0}: PID {1}이 실행 중이지만 현재 저장소 프로세스인지 확인할 수 없습니다." -f $Label, $recordedProcessId)
}

Write-ComponentStatus -Label '포탈' -PidFile $FrontendPidFile -Component 'frontend'
Write-ComponentStatus -Label 'API' -PidFile $ApiPidFile -Component 'api'

$naverChromeProcessId = Read-RecordedProcessId -PidFile $NaverChromePidFile
if ($null -eq $naverChromeProcessId) {
    Write-Host 'Naver Chrome: 중지됨 (PID 기록 없음)'
}
elseif (Test-NaverChromeAgent -ProcessId $naverChromeProcessId) {
    Write-Host "Naver Chrome: 실행 중 (PID $naverChromeProcessId, CDP $ChromeCdpUrl)"
}
else {
    Write-Warning "Naver Chrome: PID, listener, 전용 프로필 및 /json/version 소유권을 함께 확인할 수 없습니다."
}

$portalPortStatus = if (Test-LocalPortAvailable -Port $PortalPort) { '비어 있음' } else { '사용 중' }
$apiPortStatus = if (Test-LocalPortAvailable -Port $ApiPort) { '비어 있음' } else { '사용 중' }
Write-Host "포탈 포트 $PortalPort`: $portalPortStatus"
Write-Host "API 포트 $ApiPort`: $apiPortStatus"
Write-Host "Naver Chrome CDP 포트 $ChromeCdpPort`: $(if (Test-LocalPortAvailable -Port $ChromeCdpPort) { '비어 있음' } else { '사용 중' })"

try {
    $health = Get-ApiHealth
    if ($null -eq $health) {
        throw 'health unavailable'
    }
    Write-Host ("API health: {0}, Chrome readiness: {1}" -f $health.status, $health.browser)
}
catch {
    Write-Host 'API health: 응답 없음'
}

Write-Host "로그/PID 디렉터리: $RuntimeRoot"
