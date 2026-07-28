[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'runtime-common.ps1')

Initialize-LocalRuntimeDirectories

if ($null -eq (Find-InstalledGoogleChrome)) {
    throw 'Google Chrome이 필요합니다. 공식 설치 프로그램으로 Chrome을 설치한 뒤 다시 실행하세요.'
}

$launcher = Get-Command py.exe -ErrorAction SilentlyContinue
$launcherArguments = @('-3')
if ($null -eq $launcher) {
    $launcher = Get-Command python.exe -ErrorAction SilentlyContinue
    $launcherArguments = @()
}
if ($null -eq $launcher) {
    throw 'Python 3.12~3.14가 필요합니다. Python을 설치한 뒤 다시 실행하세요.'
}

$versionCheckArguments = $launcherArguments + @(
    '-c',
    'import sys; raise SystemExit(0 if (3, 12) <= sys.version_info[:2] < (3, 15) else 1)'
)
Invoke-CheckedCommand `
    -Executable $launcher.Source `
    -Arguments $versionCheckArguments `
    -WorkingDirectory $RepositoryRoot `
    -FailureMessage '지원하는 Python 버전은 3.12 이상 3.15 미만입니다.'

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    Write-Host '로컬 Python 가상환경을 생성합니다.'
    Invoke-CheckedCommand `
        -Executable $launcher.Source `
        -Arguments ($launcherArguments + @('-m', 'venv', $VenvRoot)) `
        -WorkingDirectory $RepositoryRoot `
        -FailureMessage 'Python 가상환경 생성에 실패했습니다.'
}

Write-Host '백엔드 패키지를 설치합니다.'
Invoke-CheckedCommand `
    -Executable $VenvPython `
    -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip') `
    -WorkingDirectory $RepositoryRoot `
    -FailureMessage 'pip 업데이트에 실패했습니다.'
Invoke-CheckedCommand `
    -Executable $VenvPython `
    -Arguments @('-m', 'pip', 'install', '-e', $BackendRoot) `
    -WorkingDirectory $RepositoryRoot `
    -FailureMessage '백엔드 패키지 설치에 실패했습니다.'

$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if ($null -eq $nodeCommand) {
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
}
if ($null -eq $nodeCommand) {
    throw 'Node.js 22 LTS가 필요합니다. Node.js를 설치한 뒤 다시 실행하세요.'
}

$nodeVersion = (& $nodeCommand.Source --version).Trim()
if ($LASTEXITCODE -ne 0 -or $nodeVersion -notmatch '^v22\.') {
    throw "지원하는 Node.js 버전은 22 LTS입니다. 현재 버전: $nodeVersion"
}

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($null -eq $npmCommand) {
    $npmCommand = Get-Command npm -ErrorAction SilentlyContinue
}
if ($null -eq $npmCommand) {
    throw 'npm을 찾을 수 없습니다. Node.js 22 LTS를 다시 설치한 뒤 실행하세요.'
}

Write-Host '프런트엔드 패키지를 설치합니다.'
Invoke-CheckedCommand `
    -Executable $npmCommand.Source `
    -Arguments @('install') `
    -WorkingDirectory $FrontendRoot `
    -FailureMessage '프런트엔드 패키지 설치에 실패했습니다.'

Set-LocalRuntimeEnvironment
Write-Host 'SQLite 데이터베이스 마이그레이션을 적용합니다.'
Invoke-CheckedCommand `
    -Executable $VenvPython `
    -Arguments @('-m', 'alembic', 'upgrade', 'head') `
    -WorkingDirectory $BackendRoot `
    -FailureMessage 'SQLite 마이그레이션에 실패했습니다.'

Write-Host ''
Write-Host '로컬 실행 준비가 완료되었습니다.'
Write-Host "최초 관리자 설정용 bootstrap token 파일: $LocalBootstrapTokenPath"
Write-Host "확인 명령: Get-Content -LiteralPath '$LocalBootstrapTokenPath'"
Write-Host '다음 명령: .\scripts\start.ps1 -Mode local'
