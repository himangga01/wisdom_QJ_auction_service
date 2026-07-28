[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'runtime-common.ps1')

Initialize-LocalRuntimeDirectories

$frontendStopped = Stop-RecordedProjectProcess -PidFile $FrontendPidFile -Component 'frontend'
$apiStopped = Stop-RecordedProjectProcess -PidFile $ApiPidFile -Component 'api'
$naverChromeStopped = Stop-RecordedNaverChromeProcess

if (-not $frontendStopped -or -not $apiStopped -or -not $naverChromeStopped) {
    throw '저장소 소유 여부를 확인하지 못한 프로세스는 종료하지 않았습니다. 경고 내용을 확인하세요.'
}

Write-Host '로컬 서비스를 종료했습니다. SQLite 데이터와 로그는 유지됩니다.'
