# Windows Docker·로컬 이중 실행 보완 구현계획

> **에이전트 작업자용:** 구현 시 `superpowers:subagent-driven-development`(권장) 또는 `superpowers:executing-plans`를 사용하며, 체크박스 단위로 진행한다.

**목표:** Windows에서 같은 코드베이스를 Docker 운영 모드 또는 Docker 없는 SQLite 로컬 모드로 안정적으로 선택 실행할 수 있도록 기존 구현의 준비 조건·환경파일·문서를 보완한다.

**아키텍처:** `scripts/start.ps1 -Mode local|docker`와 `APP_RUNTIME` 경계는 유지한다. 로컬은 SQLite·내장 작업 실행기·외부 Google Chrome을, Docker는 PostgreSQL·Redis·Celery·Nginx를 계속 사용하며 도메인과 API 코드는 변경하지 않는다.

**기술 스택:** Windows PowerShell, Python 3.12~3.14, Node.js 22, FastAPI, SQLite, React/Vite, Docker Compose

## 전체 제약

- Windows만 지원하며 macOS·Linux 스크립트는 추가하지 않는다.
- 포탈 `42880`, API `42881`, Chrome CDP `42973`을 변경하지 않는다.
- 로컬 시작은 하나의 명령으로 Uvicorn과 Vite를 실행하되 단일 프로세스로 합치지 않는다.
- 로컬 SQLite, Chrome 프로필, Docker volume과 기존 프로세스를 삭제하거나 강제 종료하지 않는다.
- API·크롤러·저장·조회 동작은 변경하지 않는다.
- Markdown은 한국어 안내를 먼저 작성하고 영문 AI 계약을 뒤에 둔다.
- 테스트·빌드·마이그레이션·Docker·브라우저 실행은 별도 사용자 승인 전에는 수행하지 않는다.
- 커밋과 푸시는 별도 요청 전에는 수행하지 않는다.

---

### 작업 1: Windows 로컬 준비 조건 명확화

**파일**

- 수정: `scripts/setup-local.ps1`
- 수정: `frontend/package.json`
- 수정: `frontend/package-lock.json`

**제공 계약**

- 로컬 준비 단계는 Node.js 메이저 버전이 정확히 `22`일 때만 진행한다.
- 로컬 준비 단계는 Python Playwright 패키지는 설치하지만 Playwright 전용 Chromium 바이너리는 설치하지 않는다.

- [x] **1-1. Node.js 22 검사 추가**

`setup-local.ps1`에서 npm 설치 전에 `node.exe` 또는 `node`를 찾고 `--version` 결과가 `v22.`로 시작하는지 확인한다.

```powershell
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
```

- [x] **1-2. 로컬 전용 Chromium 설치 제거**

다음 Playwright 브라우저 바이너리 설치 블록을 `setup-local.ps1`에서 제거한다.

```powershell
Write-Host 'Playwright Chromium을 설치합니다.'
Invoke-CheckedCommand `
    -Executable $VenvPython `
    -Arguments @('-m', 'playwright', 'install', 'chromium') `
    -WorkingDirectory $BackendRoot `
    -FailureMessage 'Playwright Chromium 설치에 실패했습니다.'
```

`pip install -e backend`는 유지하여 Python Playwright 패키지와 CDP 연결 기능을 보존한다.

- [x] **1-3. 프런트엔드 Node.js 지원 범위 선언**

`frontend/package.json` 최상위에 다음 계약을 추가한다.

```json
"engines": {
  "node": ">=22 <23"
}
```

`frontend/package-lock.json`의 루트 패키지에도 같은 `engines.node` 값을 반영해 manifest와 lockfile 계약을 일치시킨다.

---

### 작업 2: 로컬·Docker 환경파일 계약 통일

**파일**

- 생성: `backend/.env.local.example`
- 수정: `backend/.env.example`
- 수정: `scripts/start.ps1`

**제공 계약**

- 수동 로컬 실행 예제는 `APP_RUNTIME=local`과 SQLite·외부 Chrome 설정을 제공한다.
- 공식 Docker 실행은 Compose 변수 치환과 컨테이너 환경변수에 동일한 `backend/.env`를 사용한다.

- [x] **2-1. 로컬 환경설정 예제 생성**

`backend/.env.local.example`을 다음 값으로 생성한다.

```dotenv
APP_RUNTIME=local
DATABASE_URL=sqlite+aiosqlite:///./data/wisdom_local.db
REDIS_URL=redis://127.0.0.1:6379/0
CRAWLER_HEADLESS=false
CRAWLER_BROWSER_MODE=external_chrome
CRAWLER_CDP_URL=http://127.0.0.1:42973
CRAWL_CONCURRENCY=1
NAVER_REQUEST_DELAY_MIN=1.0
NAVER_REQUEST_DELAY_MAX=2.5
CORS_ORIGINS=http://127.0.0.1:42880,http://localhost:42880
TIMEZONE=Asia/Seoul
```

Redis URL은 설정 모델 호환을 위해 남기지만 `APP_RUNTIME=local`에서는 Redis 연결을 요구하지 않는다.

- [x] **2-2. Docker PostgreSQL 변수 명시**

`backend/.env.example`에서 `APP_RUNTIME=docker` 다음에 다음 값을 추가한다.

```dotenv
POSTGRES_DB=wisdom_auction
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

기존 `DATABASE_URL`의 사용자·비밀번호·DB 이름은 위 세 값과 일치시킨다.

- [x] **2-3. Docker Compose 환경파일 경로 고정**

`scripts/start.ps1`의 Docker Compose 인자를 다음 순서로 변경한다.

```powershell
-Arguments @(
    'compose',
    '--env-file', $dockerEnvFile,
    '-f', $composeFile,
    'up', '-d', '--build'
)
```

Docker CLI·Docker Desktop 검사, 포트 검사와 `backend/.env`의 `APP_RUNTIME=docker` 검사는 그대로 유지한다.

---

### 작업 3: 공식 실행 경로와 수동 실행 문서 정리

**파일**

- 수정: `backend/docker-compose.yml`
- 수정: `README.md`
- 수정: `docs/setup/local-setup.md`
- 수정: `docs/setup/docker-setup.md`
- 수정: `frontend/README.md`

**제공 계약**

- 공식 Docker 구성은 루트 `docker-compose.production.yml` 하나로 안내한다.
- `backend/docker-compose.yml`은 삭제하지 않고 레거시 개발용임을 표시한다.
- 로컬 통합 실행과 수동 실행을 구분해 안내한다.

- [x] **3-1. 레거시 Compose 표시**

`backend/docker-compose.yml` 최상단에 다음 주석을 추가한다.

```yaml
# 레거시 백엔드 개발용 구성입니다.
# 전체 서비스는 저장소 루트의 docker-compose.production.yml을 사용하세요.
# Legacy backend-only development compose. Use ../docker-compose.production.yml for the full service.
```

서비스 정의와 기존 볼륨은 수정하거나 삭제하지 않는다.

- [x] **3-2. 루트 빠른 시작 정리**

`README.md`의 기존 빠른 시작을 유지하면서 다음 내용을 명확히 한다.

- Windows 통합 로컬 실행: `setup-local.ps1`, `start.ps1 -Mode local`
- Windows 수동 로컬 실행: `backend/.env.local.example`을 `backend/.env`로 복사한 뒤 migration·Uvicorn·Vite를 각각 실행
- Docker 실행: `backend/.env.example`을 `backend/.env`로 복사한 뒤 `start.ps1 -Mode docker`
- 공식 Compose: `docker-compose.production.yml`
- 실행 모드 변경 시 `backend/.env`의 `APP_RUNTIME`과 데이터베이스 URL도 함께 변경

- [x] **3-3. 로컬 수동 실행 명령 추가**

`docs/setup/local-setup.md`에 다음 순서를 한국어 영역에 추가하고, 영문 계약에도 같은 의미를 반영한다.

```powershell
Copy-Item .\backend\.env.local.example .\backend\.env
Set-Location .\backend
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 42881 --workers 1
```

별도 PowerShell에서 다음을 실행한다.

```powershell
Set-Location .\frontend
npm run dev -- --host 127.0.0.1 --port 42880 --strictPort
```

수동 실행 전에 `scripts/start-naver-browser.ps1`로 전용 Chrome을 실행해야 함을 함께 명시한다.

- [x] **3-4. Docker 환경파일 설명 수정**

`docs/setup/docker-setup.md`에서 다음을 명시한다.

- `start.ps1 -Mode docker`가 `backend/.env`를 Compose `--env-file`로 사용한다.
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`을 한 파일에서 일치시킨다.
- 루트 `docker-compose.production.yml`만 전체 서비스 공식 구성이다.

- [x] **3-5. 프런트엔드 README 교체**

`frontend/README.md`를 다음 구조로 교체한다.

1. 한국어 프로젝트 설명
2. 권장 통합 실행 명령
3. 프런트 단독 실행 명령
4. 포트 `42880`과 `/api` → `42881` proxy 계약
5. Docker에서는 Nginx가 `/api`를 내부 API로 전달한다는 설명
6. 영문 AI frontend runtime contract

---

### 작업 4: 별도 승인 후 집중 확인

**파일**

- 기존 확인 대상: `scripts/*.ps1`
- 기존 테스트: `backend/tests/unit/test_runtime_config.py`
- 기존 테스트: `backend/tests/unit/test_local_runtime.py`
- 기존 테스트: `backend/tests/unit/test_local_scheduler.py`

**승인 조건**

- 이 작업은 코드 수정 완료 후 사용자가 테스트 실행을 별도로 승인한 경우에만 수행한다.

- [x] **4-1. PowerShell 구문 확인**

각 스크립트 내용을 `[scriptblock]::Create()`로 파싱하고 프로세스·Docker·브라우저는 실행하지 않는다.

- [x] **4-2. 상수 정적 확인**

`42880`, `42881`, `42973`, `APP_RUNTIME`, `--env-file`이 스크립트·Compose·문서에서 동일한지 검색한다.

- [x] **4-3. 로컬 런타임 집중 테스트**

```powershell
Set-Location .\backend
..\.venv\Scripts\python -m pytest `
  tests/unit/test_runtime_config.py `
  tests/unit/test_local_runtime.py `
  tests/unit/test_local_scheduler.py -q
```

프런트 빌드, Docker 기동, migration 실행과 라이브 네이버 조사는 이 확인에 포함하지 않는다.

---

# Windows Dual Runtime Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the existing Windows runtime selector so the same repository reliably supports Docker and Docker-free SQLite execution.

**Architecture:** Preserve `scripts/start.ps1 -Mode local|docker` and the existing `APP_RUNTIME` infrastructure boundary. Local mode continues to use SQLite, one in-process dispatcher and scheduler, and installed Google Chrome over loopback CDP; Docker mode continues to use PostgreSQL, Redis, Celery, FastAPI, and Nginx.

**Tech Stack:** Windows PowerShell, Python 3.12–3.14, Node.js 22, FastAPI, SQLite, React/Vite, Docker Compose

## Global Constraints

- Windows only; do not add macOS or Linux launchers.
- Preserve portal `42880`, API `42881`, and Chrome CDP `42973`.
- Do not merge Uvicorn and Vite into one process.
- Do not alter domain, crawler, persistence, query, export, or API behavior.
- Do not delete data, profiles, volumes, or unrelated processes.
- Keep Markdown Korean-first with an English AI contract afterward.
- Do not run tests, builds, migrations, Docker, browsers, or live crawling without separate approval.
- Do not commit or push without a separate request.

## Task Map

### Task 1: Local prerequisites

- Modify `scripts/setup-local.ps1` to require Node.js major version 22.
- Remove the local Playwright Chromium binary installation while retaining the Python package.
- Add `"engines": {"node": ">=22 <23"}` to `frontend/package.json` and its root package entry in `frontend/package-lock.json`.

### Task 2: Runtime environment examples

- Create `backend/.env.local.example` with local SQLite and external-Chrome values.
- Add PostgreSQL Compose variables to `backend/.env.example`.
- Pass `--env-file backend/.env` in the canonical Docker Compose invocation.

### Task 3: Canonical runtime documentation

- Mark `backend/docker-compose.yml` as legacy backend-only development configuration without deleting it.
- Update root, local, Docker, and frontend documentation with canonical and manual Windows commands.
- Keep `docker-compose.production.yml` as the only documented full-service Compose file.

### Task 4: Approval-gated verification

- Parse PowerShell scripts without running services.
- Search runtime constants for static consistency.
- Run only the three focused backend local-runtime test modules after explicit user approval.
