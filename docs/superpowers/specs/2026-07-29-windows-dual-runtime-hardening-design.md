# Windows Docker·로컬 이중 실행 보완 설계

## 한국어 설계

### 1. 목표

기존 Windows 실행 구조를 유지하면서 사용자가 같은 코드베이스를 다음 두 방식으로 안정적으로 선택 실행할 수 있게 보완한다.

- `local`: Docker 없이 Python, Node.js, Google Chrome과 SQLite로 실행
- `docker`: Docker Desktop에서 PostgreSQL, Redis, Celery, FastAPI, Nginx로 실행

기존 포탈·API·크롤러·저장·조회 계약은 변경하지 않는다. macOS와 Linux 실행 스크립트, React와 FastAPI의 단일 프로세스 패키징은 이번 범위에서 제외한다.

### 2. 유지할 실행 구조

- 통합 진입점은 `scripts/start.ps1 -Mode local|docker`로 유지한다.
- `-Mode`를 생략하면 기존 선택 메뉴를 표시한다.
- 로컬 모드는 `APP_RUNTIME=local`, SQLite, 단일 내장 작업 실행기와 FastAPI 내부 스케줄러를 사용한다.
- Docker 모드는 `APP_RUNTIME=docker`, PostgreSQL, Redis, Celery worker·beat를 사용한다.
- 호스트 포트는 포탈 `42880`, API `42881`, 로컬 Chrome CDP `42973`을 유지한다.
- 로컬 시작 명령 한 번이 API와 Vite를 모두 실행하지만 두 프로세스를 하나로 합치지는 않는다.

### 3. 보완 항목

#### Windows 로컬 준비

- `setup-local.ps1`에서 Node.js 설치 여부뿐 아니라 메이저 버전이 22인지 확인한다.
- `frontend/package.json`에도 지원 Node.js 범위를 명시해 스크립트 밖에서 설치할 때 동일한 조건을 확인할 수 있게 한다.
- 로컬 수집은 설치된 Google Chrome에 CDP로 연결하므로 `setup-local.ps1`에서 사용하지 않는 Playwright Chromium 바이너리 설치를 제거한다. Python Playwright 패키지는 CDP 연결에 필요하므로 유지한다.
- `backend/.env.local.example`을 제공해 PowerShell 통합 실행기 없이 백엔드를 직접 실행할 때 필요한 로컬 환경변수를 명확히 한다.

#### Docker 환경파일

- Docker Compose 변수 치환과 컨테이너 환경변수 모두 `backend/.env`를 동일하게 사용하도록 `start.ps1`에서 `--env-file`을 명시한다.
- `backend/.env.example`에 `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`를 추가해 Compose 기본값을 변경할 때 `DATABASE_URL`과 함께 한 파일에서 관리하게 한다.
- 공식 Docker 실행 파일은 루트 `docker-compose.production.yml`임을 명시한다.
- `backend/docker-compose.yml`은 삭제하지 않고 파일 상단에 레거시 개발용 구성임을 표시하여 데이터 삭제나 기존 작업 흐름 변경을 피한다.

#### 문서

- 루트 README와 Windows 로컬·Docker 가이드에 자동 실행 및 수동 실행 경로를 구분한다.
- `frontend/README.md`의 Vite 기본 안내를 프로젝트 전용 포트·실행 방식·API proxy 설명으로 교체한다.
- 모든 Markdown은 한국어 안내를 먼저 두고 영문 AI 계약을 뒤에 둔다.

### 4. 오류 처리와 안전

- Python, Node.js 22, npm 또는 Chrome이 없으면 한국어 오류로 시작을 중단한다.
- 포트가 점유된 경우 점유 프로세스를 종료하지 않는다.
- 로컬 SQLite 파일, Chrome 전용 프로필, Docker volume을 자동 삭제하지 않는다.
- Docker CLI 또는 Docker Desktop이 준비되지 않았으면 로컬 실행에는 영향을 주지 않고 Docker 모드만 중단한다.
- 구형 Compose 파일은 삭제하거나 자동 변환하지 않는다.

### 5. 완료 조건

- Windows에서 `start.ps1`이 로컬과 Docker 실행을 명시적으로 선택할 수 있다.
- 로컬 준비 단계가 Node.js 22가 아닌 환경을 명확히 거부한다.
- 로컬 직접 실행에 필요한 환경변수가 예제 파일과 문서에 모두 존재한다.
- Docker 실행 시 Compose 변수와 컨테이너가 동일한 `backend/.env` 값을 사용한다.
- 공식 Compose와 레거시 Compose의 용도가 문서와 파일에서 구분된다.
- 기존 포트, API 계약, 데이터 위치, 크롤링 동작은 바뀌지 않는다.

### 6. 확인 범위

코드 수정 후 별도 사용자 승인을 받은 경우에만 다음 집중 확인을 실행한다.

1. PowerShell 스크립트 구문 확인
2. 환경파일·포트 상수의 정적 일치 확인
3. 로컬 런타임 관련 기존 단위 테스트

프런트 전체 빌드, Docker 이미지 빌드·기동, 마이그레이션 실행, 실제 네이버 크롤링은 별도 승인이 없으면 수행하지 않는다.

---

# Windows Dual Runtime Hardening Design

## AI Runtime Contract

### Objective

Preserve the existing Windows-only runtime selector while closing prerequisite, environment-file, and documentation gaps:

- `local`: Python, Node.js 22, installed Google Chrome, SQLite, in-process dispatcher and scheduler
- `docker`: Docker Desktop, PostgreSQL, Redis, Celery worker/beat, FastAPI and Nginx

macOS/Linux launchers and single-process frontend/backend packaging are explicitly out of scope.

### Runtime Boundaries

- Keep `scripts/start.ps1 -Mode local|docker` as the canonical entry point.
- Keep host ports `42880` for the portal, `42881` for the API, and loopback CDP `42973`.
- Local startup launches one Uvicorn process and one Vite process from one command.
- Domain, crawler, persistence, query, export and API contracts remain shared and unchanged.

### Required Changes

- Enforce Node.js major version 22 in `setup-local.ps1` and declare the range in `frontend/package.json`.
- Do not install a Playwright-owned Chromium binary during local setup; retain the Python Playwright package for external Chrome CDP attachment.
- Add `backend/.env.local.example` for direct local backend execution.
- Pass `--env-file backend/.env` to the canonical Docker Compose invocation.
- Add PostgreSQL Compose variables to `backend/.env.example`.
- Mark `backend/docker-compose.yml` as a legacy development-only file without deleting it.
- Replace the default frontend README with project-specific local/Docker and proxy instructions.
- Keep all documentation Korean-first, followed by an English AI contract.

### Safety

Never terminate port owners, delete SQLite data, remove the dedicated Chrome profile, delete Docker volumes, or install Docker/Python/Node/Chrome automatically. Missing prerequisites must fail with a clear message limited to the selected runtime.

### Verification Gate

Do not run tests, builds, migrations, Docker, browsers, or live crawling without separate user approval. After approval, limit checks to PowerShell syntax, static port/environment consistency, and focused local-runtime tests.
