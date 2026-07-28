[CmdletBinding()]
param(
    [switch]$PassThru
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'runtime-common.ps1')

Initialize-LocalRuntimeDirectories

if (Test-Path -LiteralPath $NaverChromePidFile -PathType Leaf) {
    $recordedProcessId = Read-RecordedProcessId -PidFile $NaverChromePidFile
    if ($null -eq $recordedProcessId) {
        throw "$NaverChromePidFile 의 PID 값이 올바르지 않습니다. 파일을 직접 확인해 주세요."
    }

    $runningProcess = Get-Process -Id $recordedProcessId -ErrorAction SilentlyContinue
    if ($null -eq $runningProcess) {
        Remove-Item -LiteralPath $NaverChromePidFile -Force
    }
    elseif (Test-NaverChromeAgent -ProcessId $recordedProcessId) {
        if ($PassThru) {
            [pscustomobject]@{ StartedByThisInvocation = $false }
        }
        else {
            Write-Host "Naver Chrome이 이미 준비되어 있습니다. PID: $recordedProcessId"
        }
        return
    }
    else {
        throw "기록된 PID $recordedProcessId 와 CDP listener, 전용 Chrome 프로필 및 /json/version 소유권을 함께 확인할 수 없습니다."
    }
}

Assert-LocalPortAvailable -Port $ChromeCdpPort -ServiceName 'Naver Chrome CDP'

$chromeExecutable = Find-InstalledGoogleChrome
if ($null -eq $chromeExecutable) {
    throw '설치된 Google Chrome을 찾을 수 없습니다. Program Files 또는 LocalAppData 설치 경로를 확인하세요.'
}

New-Item -ItemType Directory -Path $NaverChromeProfilePath -Force | Out-Null
$chromeProcess = $null
try {
    $chromeProcess = Start-Process `
        -FilePath $chromeExecutable `
        -ArgumentList @(
            '--remote-debugging-address=127.0.0.1',
            "--remote-debugging-port=$ChromeCdpPort",
            "--user-data-dir=$NaverChromeProfilePath",
            '--no-first-run',
            '--no-default-browser-check'
        ) `
        -PassThru

    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    while ([DateTime]::UtcNow -lt $deadline) {
        $listenerProcessId = Get-NaverChromeListenerProcessId
        if ($null -ne $listenerProcessId -and $listenerProcessId -ne $chromeProcess.Id) {
            throw "CDP 포트 $ChromeCdpPort 의 listener 소유 PID $listenerProcessId 가 이번에 시작한 Chrome PID $($chromeProcess.Id)와 일치하지 않습니다."
        }

        if (Test-NaverChromeAgent -ProcessId $chromeProcess.Id) {
            Write-RecordedProcessId `
                -PidFile $NaverChromePidFile `
                -ProcessId $chromeProcess.Id
            if ($PassThru) {
                [pscustomobject]@{ StartedByThisInvocation = $true }
            }
            else {
                Write-Host "Naver Chrome이 준비되었습니다. PID: $($chromeProcess.Id), CDP: $ChromeCdpUrl"
            }
            return
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Naver Chrome이 제한 시간 안에 PID, listener 및 /json/version 소유권을 확인하지 못했습니다."
}
catch {
    if ($null -ne $chromeProcess) {
        Stop-StartedNaverChromeProcess -ProcessId $chromeProcess.Id | Out-Null
    }
    throw
}
