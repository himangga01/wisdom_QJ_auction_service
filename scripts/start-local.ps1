[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'runtime-common.ps1')

Initialize-LocalRuntimeDirectories
Assert-NoActiveRecordedProcess -PidFile $ApiPidFile -Component 'api'
Assert-NoActiveRecordedProcess -PidFile $FrontendPidFile -Component 'frontend'
Assert-LocalPortAvailable -Port $ApiPort -ServiceName 'API'
Assert-LocalPortAvailable -Port $PortalPort -ServiceName '포탈'

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    throw '.venv가 준비되지 않았습니다. 먼저 .\scripts\setup-local.ps1 을 실행하세요.'
}

$viteEntry = Join-Path $FrontendRoot 'node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $viteEntry -PathType Leaf)) {
    throw '프런트엔드 패키지가 준비되지 않았습니다. 먼저 .\scripts\setup-local.ps1 을 실행하세요.'
}

$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if ($null -eq $nodeCommand) {
    throw 'Node.js를 찾을 수 없습니다. Node.js 22 LTS를 설치한 뒤 다시 실행하세요.'
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$apiOutLog = Join-Path $RuntimeRoot "api-$timestamp.out.log"
$apiErrorLog = Join-Path $RuntimeRoot "api-$timestamp.err.log"
$frontendOutLog = Join-Path $RuntimeRoot "frontend-$timestamp.out.log"
$frontendErrorLog = Join-Path $RuntimeRoot "frontend-$timestamp.err.log"
$apiStarted = $false
$frontendStarted = $false
$naverChromeStartedHere = $false

try {
    $naverChromeStart = & (Join-Path $PSScriptRoot 'start-naver-browser.ps1') -PassThru
    $naverChromeStartedHere = [bool]$naverChromeStart.StartedByThisInvocation

    Set-LocalRuntimeEnvironment
    Write-Host 'SQLite 데이터베이스 마이그레이션을 확인합니다.'
    Invoke-CheckedCommand `
        -Executable $VenvPython `
        -Arguments @('-m', 'alembic', 'upgrade', 'head') `
        -WorkingDirectory $BackendRoot `
        -FailureMessage 'SQLite 마이그레이션에 실패했습니다.'

    $apiProcess = Start-Process `
        -FilePath $VenvPython `
        -ArgumentList @(
            '-m', 'uvicorn', 'app.main:app',
            '--host', '127.0.0.1',
            '--port', "$ApiPort",
            '--workers', '1',
            '--no-access-log'
        ) `
        -WorkingDirectory $BackendRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $apiOutLog `
        -RedirectStandardError $apiErrorLog `
        -PassThru
    $apiStarted = $true
    Write-RecordedProcessId -PidFile $ApiPidFile -ProcessId $apiProcess.Id

    if (-not (Wait-LocalPortOpen -Port $ApiPort -TimeoutSeconds 20)) {
        throw "API가 제한 시간 안에 포트 $ApiPort 을(를) 열지 못했습니다. 로그: $apiErrorLog"
    }
    $apiProcess.Refresh()
    if ($apiProcess.HasExited) {
        throw "API 프로세스가 시작 직후 종료되었습니다. 로그: $apiErrorLog"
    }

    $quotedViteEntry = '"' + $viteEntry + '"'
    $frontendProcess = Start-Process `
        -FilePath $nodeCommand.Source `
        -ArgumentList @(
            $quotedViteEntry,
            '--host', '127.0.0.1',
            '--port', "$PortalPort",
            '--strictPort'
        ) `
        -WorkingDirectory $FrontendRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frontendOutLog `
        -RedirectStandardError $frontendErrorLog `
        -PassThru
    $frontendStarted = $true
    Write-RecordedProcessId -PidFile $FrontendPidFile -ProcessId $frontendProcess.Id

    if (-not (Wait-LocalPortOpen -Port $PortalPort -TimeoutSeconds 20)) {
        throw "포탈이 제한 시간 안에 포트 $PortalPort 을(를) 열지 못했습니다. 로그: $frontendErrorLog"
    }
    $frontendProcess.Refresh()
    if ($frontendProcess.HasExited) {
        throw "포탈 프로세스가 시작 직후 종료되었습니다. 로그: $frontendErrorLog"
    }

    Set-Content -LiteralPath (Join-Path $RuntimeRoot 'api.stdout.path') -Value $apiOutLog -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $RuntimeRoot 'api.stderr.path') -Value $apiErrorLog -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $RuntimeRoot 'frontend.stdout.path') -Value $frontendOutLog -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $RuntimeRoot 'frontend.stderr.path') -Value $frontendErrorLog -Encoding UTF8

    Write-Host ''
    Write-Host "포탈: http://127.0.0.1:$PortalPort"
    Write-Host "API:  http://127.0.0.1:$ApiPort"
    Write-Host '상태 확인: .\scripts\status.ps1'
    Write-Host '종료: .\scripts\stop-local.ps1'
}
catch {
    if ($frontendStarted) {
        Stop-RecordedProjectProcess -PidFile $FrontendPidFile -Component 'frontend' | Out-Null
    }
    if ($apiStarted) {
        Stop-RecordedProjectProcess -PidFile $ApiPidFile -Component 'api' | Out-Null
    }
    if ($naverChromeStartedHere) {
        Stop-RecordedNaverChromeProcess | Out-Null
    }
    throw
}
