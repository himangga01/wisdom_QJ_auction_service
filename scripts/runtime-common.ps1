Set-StrictMode -Version Latest

$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$BackendRoot = Join-Path $RepositoryRoot 'backend'
$FrontendRoot = Join-Path $RepositoryRoot 'frontend'
$RuntimeRoot = Join-Path $RepositoryRoot 'temp\local-runtime'
$BackendDataRoot = Join-Path $BackendRoot 'data'
$LocalDatabasePath = Join-Path $BackendDataRoot 'wisdom_local.db'
$VenvRoot = Join-Path $RepositoryRoot '.venv'
$VenvPython = Join-Path $VenvRoot 'Scripts\python.exe'
$PortalPort = 42880
$ApiPort = 42881
$ChromeCdpPort = 42973
$ChromeCdpUrl = "http://127.0.0.1:$ChromeCdpPort"
$NaverChromeProfilePath = Join-Path $BackendDataRoot 'naver-chrome-profile'
$LocalBootstrapTokenPath = Join-Path $BackendDataRoot 'bootstrap-token.txt'
$ApiPidFile = Join-Path $RuntimeRoot 'api.pid'
$FrontendPidFile = Join-Path $RuntimeRoot 'frontend.pid'
$NaverChromePidFile = Join-Path $RuntimeRoot 'naver-chrome.pid'

function Initialize-LocalRuntimeDirectories {
    New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $BackendDataRoot -Force | Out-Null
}

function Find-InstalledGoogleChrome {
    $candidatePaths = @()
    if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
        $candidatePaths += Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'
    }
    if (-not [string]::IsNullOrWhiteSpace(${env:ProgramFiles(x86)})) {
        $candidatePaths += Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'
    }
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $candidatePaths += Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe'
    }

    foreach ($candidatePath in $candidatePaths) {
        if (Test-Path -LiteralPath $candidatePath -PathType Leaf) {
            return [System.IO.Path]::GetFullPath($candidatePath)
        }
    }
    return $null
}

function Get-LocalDatabaseUrl {
    $normalizedPath = ([System.IO.Path]::GetFullPath($LocalDatabasePath)).Replace('\', '/')
    return "sqlite+aiosqlite:///$normalizedPath"
}

function Ensure-LocalBootstrapToken {
    param(
        [string]$TokenPath = $LocalBootstrapTokenPath
    )

    $resolvedTokenPath = [System.IO.Path]::GetFullPath($TokenPath)
    if (Test-Path -LiteralPath $resolvedTokenPath -PathType Leaf) {
        $storedToken = (Get-Content -LiteralPath $resolvedTokenPath -Raw).Trim()
        if ($storedToken -notmatch '^[a-f0-9]{64}$') {
            throw "$resolvedTokenPath 의 bootstrap token 형식이 올바르지 않습니다."
        }
        return $storedToken
    }

    $tokenDirectory = Split-Path -Parent $resolvedTokenPath
    New-Item -ItemType Directory -Path $tokenDirectory -Force | Out-Null
    $tokenBytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($tokenBytes)
    }
    finally {
        $generator.Dispose()
    }
    $token = [System.BitConverter]::ToString($tokenBytes).Replace('-', '').ToLowerInvariant()
    [System.IO.File]::WriteAllText(
        $resolvedTokenPath,
        $token,
        [System.Text.Encoding]::ASCII
    )
    return $token
}

function Set-LocalRuntimeEnvironment {
    param(
        [string]$BootstrapTokenPath = $LocalBootstrapTokenPath
    )

    $env:APP_RUNTIME = 'local'
    $env:DATABASE_URL = Get-LocalDatabaseUrl
    $env:CORS_ORIGINS = 'http://127.0.0.1:42880,http://localhost:42880'
    $env:CRAWLER_CDP_URL = $ChromeCdpUrl
    $env:VITE_API_BASE_URL = '/api'
    $env:AUTH_BOOTSTRAP_TOKEN = Ensure-LocalBootstrapToken `
        -TokenPath $BootstrapTokenPath
}

function Test-LocalPortAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        $Port
    )
    try {
        $listener.Start()
        return $true
    }
    catch [System.Net.Sockets.SocketException] {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

function Assert-LocalPortAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    if (-not (Test-LocalPortAvailable -Port $Port)) {
        throw "$ServiceName 포트 $Port 을(를) 이미 다른 프로세스가 사용 중입니다. 해당 프로세스를 확인한 뒤 다시 실행하세요."
    }
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [string]$FailureMessage = '명령 실행에 실패했습니다.'
    )

    Push-Location $WorkingDirectory
    try {
        & $Executable @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$FailureMessage (종료 코드: $LASTEXITCODE)"
        }
    }
    finally {
        Pop-Location
    }
}

function Get-ProjectProcessCommandLine {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )

    try {
        $record = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
        if ($null -eq $record) {
            return $null
        }
        return [string]$record.CommandLine
    }
    catch {
        return $null
    }
}

function Test-ProjectProcess {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,
        [Parameter(Mandatory = $true)]
        [ValidateSet('api', 'frontend')]
        [string]$Component
    )

    try {
        Get-Process -Id $ProcessId -ErrorAction Stop | Out-Null
    }
    catch {
        return $false
    }

    $commandLine = Get-ProjectProcessCommandLine -ProcessId $ProcessId
    if ([string]::IsNullOrWhiteSpace($commandLine)) {
        return $false
    }
    if ($commandLine.IndexOf($RepositoryRoot, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return $false
    }

    if ($Component -eq 'api') {
        return $commandLine.IndexOf('app.main:app', [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    }

    return $commandLine.IndexOf('vite', [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Read-RecordedProcessId {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PidFile
    )

    if (-not (Test-Path -LiteralPath $PidFile -PathType Leaf)) {
        return $null
    }

    $rawValue = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    $recordedProcessId = 0
    if (-not [int]::TryParse($rawValue, [ref]$recordedProcessId)) {
        return $null
    }
    return $recordedProcessId
}

function Write-RecordedProcessId {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PidFile,
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )

    Set-Content -LiteralPath $PidFile -Value $ProcessId -Encoding ASCII
}

function Test-NaverChromeProcess {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )

    try {
        Get-Process -Id $ProcessId -ErrorAction Stop | Out-Null
    }
    catch {
        return $false
    }

    $commandLine = Get-ProjectProcessCommandLine -ProcessId $ProcessId
    if ([string]::IsNullOrWhiteSpace($commandLine)) {
        return $false
    }

    $profilePath = [System.IO.Path]::GetFullPath($NaverChromeProfilePath)
    return (
        $commandLine.IndexOf('chrome.exe', [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $commandLine.IndexOf($profilePath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $commandLine.IndexOf('--remote-debugging-address=127.0.0.1', [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $commandLine.IndexOf("--remote-debugging-port=$ChromeCdpPort", [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}

function Get-NaverChromeListenerProcessId {
    try {
        $listeners = @(
            Get-NetTCPConnection `
                -LocalAddress '127.0.0.1' `
                -LocalPort $ChromeCdpPort `
                -State Listen `
                -ErrorAction Stop
        )
        if ($listeners.Count -ne 1) {
            return $null
        }
        return [int]$listeners[0].OwningProcess
    }
    catch {
        return $null
    }
}

function Test-NaverChromeCdpReady {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ExpectedProcessId
    )

    $listenerProcessId = Get-NaverChromeListenerProcessId
    if ($null -eq $listenerProcessId -or $listenerProcessId -ne $ExpectedProcessId) {
        return $false
    }

    try {
        $version = Invoke-RestMethod -Uri "$ChromeCdpUrl/json/version" -TimeoutSec 3 -ErrorAction Stop
        $product = [string]$version.Browser
        $webSocketUrl = [string]$version.webSocketDebuggerUrl
        $webSocketUri = [System.Uri]$webSocketUrl
        return (
            $product.StartsWith('Chrome/', [System.StringComparison]::OrdinalIgnoreCase) -and
            $webSocketUri.Scheme -eq 'ws' -and
            $webSocketUri.Host -eq '127.0.0.1' -and
            $webSocketUri.Port -eq $ChromeCdpPort
        )
    }
    catch {
        return $false
    }
}

function Test-NaverChromeAgent {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )

    if (-not (Test-NaverChromeProcess -ProcessId $ProcessId)) {
        return $false
    }

    $listenerProcessId = Get-NaverChromeListenerProcessId
    if ($null -eq $listenerProcessId -or $listenerProcessId -ne $ProcessId) {
        return $false
    }

    return Test-NaverChromeCdpReady -ExpectedProcessId $ProcessId
}

function Stop-StartedNaverChromeProcess {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )

    if (-not (Test-NaverChromeProcess -ProcessId $ProcessId)) {
        return $false
    }

    Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    Wait-Process -Id $ProcessId -Timeout 10 -ErrorAction SilentlyContinue
    return $true
}

function Stop-RecordedNaverChromeProcess {
    if (-not (Test-Path -LiteralPath $NaverChromePidFile -PathType Leaf)) {
        Write-Host 'Naver Chrome PID 기록이 없습니다.'
        return $true
    }

    $recordedProcessId = Read-RecordedProcessId -PidFile $NaverChromePidFile
    if ($null -eq $recordedProcessId) {
        Write-Warning "$NaverChromePidFile 의 PID 값이 올바르지 않아 Chrome을 종료하지 않았습니다."
        return $false
    }

    if (-not (Get-Process -Id $recordedProcessId -ErrorAction SilentlyContinue)) {
        Remove-Item -LiteralPath $NaverChromePidFile -Force
        Write-Host 'Naver Chrome은 이미 종료되어 있습니다.'
        return $true
    }

    if (-not (Test-NaverChromeAgent -ProcessId $recordedProcessId)) {
        Write-Warning "PID $recordedProcessId 와 CDP listener, 전용 Chrome 프로필, /json/version 소유권을 함께 확인할 수 없어 종료하지 않았습니다."
        return $false
    }

    Stop-Process -Id $recordedProcessId -Force -ErrorAction Stop
    Wait-Process -Id $recordedProcessId -Timeout 10 -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $NaverChromePidFile -Force
    Write-Host "Naver Chrome 프로세스(PID $recordedProcessId)를 종료했습니다."
    return $true
}

function Assert-NoActiveRecordedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PidFile,
        [Parameter(Mandatory = $true)]
        [ValidateSet('api', 'frontend')]
        [string]$Component
    )

    if (-not (Test-Path -LiteralPath $PidFile -PathType Leaf)) {
        return
    }

    $recordedProcessId = Read-RecordedProcessId -PidFile $PidFile
    if ($null -eq $recordedProcessId) {
        throw "$PidFile 의 PID 값이 올바르지 않습니다. 파일을 직접 확인해 주세요."
    }

    $runningProcess = Get-Process -Id $recordedProcessId -ErrorAction SilentlyContinue
    if ($null -eq $runningProcess) {
        Remove-Item -LiteralPath $PidFile -Force
        return
    }

    if (Test-ProjectProcess -ProcessId $recordedProcessId -Component $Component) {
        throw "$Component 프로세스(PID $recordedProcessId)가 이미 실행 중입니다."
    }

    throw "기록된 PID $recordedProcessId 가 현재 저장소의 $Component 프로세스인지 확인할 수 없습니다. PID 파일을 직접 확인해 주세요."
}

function Stop-RecordedProjectProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PidFile,
        [Parameter(Mandatory = $true)]
        [ValidateSet('api', 'frontend')]
        [string]$Component
    )

    if (-not (Test-Path -LiteralPath $PidFile -PathType Leaf)) {
        Write-Host "$Component PID 기록이 없습니다."
        return $true
    }

    $recordedProcessId = Read-RecordedProcessId -PidFile $PidFile
    if ($null -eq $recordedProcessId) {
        Write-Warning "$PidFile 의 PID 값이 올바르지 않아 프로세스를 종료하지 않았습니다."
        return $false
    }

    $runningProcess = Get-Process -Id $recordedProcessId -ErrorAction SilentlyContinue
    if ($null -eq $runningProcess) {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "$Component 프로세스는 이미 종료되어 있습니다."
        return $true
    }

    if (-not (Test-ProjectProcess -ProcessId $recordedProcessId -Component $Component)) {
        Write-Warning "PID $recordedProcessId 의 명령행에서 현재 저장소와 $Component 실행 정보를 확인할 수 없어 종료하지 않았습니다."
        return $false
    }

    Stop-Process -Id $recordedProcessId -Force -ErrorAction Stop
    Wait-Process -Id $recordedProcessId -Timeout 10 -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "$Component 프로세스(PID $recordedProcessId)를 종료했습니다."
    return $true
}

function Wait-LocalPortOpen {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [int]$TimeoutSeconds = 20
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $client = [System.Net.Sockets.TcpClient]::new()
        try {
            $client.Connect('127.0.0.1', $Port)
            return $true
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
        finally {
            $client.Dispose()
        }
    }
    return $false
}

function Get-ApiHealth {
    try {
        return Invoke-RestMethod `
            -Uri "http://127.0.0.1:$ApiPort/api/health" `
            -TimeoutSec 3 `
            -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function Wait-ApiHealth {
    param(
        [int]$TimeoutSeconds = 20
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $health = Get-ApiHealth
        if ($null -ne $health) {
            return $health
        }
        Start-Sleep -Milliseconds 250
    }
    return $null
}
