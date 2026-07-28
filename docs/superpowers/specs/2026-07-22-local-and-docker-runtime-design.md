# Docker·로컬 선택 실행 설계

## 한국어 설계

### 1. 목표

사용자가 같은 포탈 코드를 다음 두 방식 중 하나로 실행할 수 있게 한다.

- `local`: Docker 없이 Python, Node.js만 사용한다.
- `docker`: 기존 PostgreSQL, Redis, Celery, 컨테이너 구성을 사용한다.

화면과 API 계약은 실행 방식과 무관하게 동일하게 유지한다. 로컬 모드는 개인 개발·데모용 단일 프로세스 구성이고 Docker 모드는 장시간 운영과 다중 서비스 구성을 위한 방식이다.

### 2. 확정 포트

흔히 사용되는 `5173`, `8000`, `8080`을 피하고 다음 포트를 모든 실행 방식의 호스트 포트로 사용한다.

| 용도 | 호스트 포트 | 주소 |
|---|---:|---|
| React 포탈 | `42880` | `http://127.0.0.1:42880` |
| FastAPI | `42881` | `http://127.0.0.1:42881` |

2026-07-22 현재 로컬 TCP 리스닝 상태에서 두 포트가 비어 있음을 확인했다. 시작 스크립트는 매 실행 전에 다시 포트 점유 여부를 검사하고, 점유 중이면 기존 프로세스를 종료하지 않고 사용자가 확인할 수 있는 오류를 반환한다.

Docker 컨테이너 내부 포트 `80`, `8000`은 이미지 계약이므로 유지하고 호스트 매핑만 `42880`, `42881`로 변경한다.

### 3. 실행 모드 설정

백엔드 설정에 `APP_RUNTIME=local|docker`를 추가한다.

| 항목 | local | docker |
|---|---|---|
| 데이터베이스 | SQLite + aiosqlite | PostgreSQL + asyncpg |
| 조사 작업 | 단일 내장 작업 실행기 | Celery Worker |
| 예약 조사 | FastAPI 내부 60초 주기 루프 | Celery Beat |
| 중복 락 | 프로세스 내부 source 락 | Redis source 락 |
| 포탈 | Vite `42880` | Nginx `42880` |
| API | Uvicorn `42881` | Uvicorn host mapping `42881` |

설정 선택은 실행 스크립트와 환경변수에서만 담당한다. 크롤러, 정제, 저장, 조회, XLSX 서비스 코드는 양쪽 모드가 함께 사용한다.

### 4. 로컬 데이터베이스

- 파일: `backend/data/wisdom_local.db`
- URL: `sqlite+aiosqlite:///.../backend/data/wisdom_local.db`
- SQLite foreign key를 연결마다 활성화한다.
- 동시 쓰기 충돌을 줄이기 위해 WAL 모드를 적용한다.
- 기존 Alembic 마이그레이션을 SQLite에서도 실행할 수 있도록 batch migration과 SQLite partial index를 적용한다.
- 로컬 설정 스크립트와 시작 스크립트가 `alembic upgrade head`를 실행한다.
- DB 파일은 Git에 포함하지 않는다.

### 5. 로컬 작업 실행과 스케줄러

로컬 실행기는 크롤링 작업을 최대 한 개만 처리하는 단일 `ThreadPoolExecutor`를 사용한다. API의 분석 요청은 즉시 `runId`를 반환하고 실제 Playwright 작업은 백그라운드 스레드에서 실행한다. 대기 중 작업 취소는 해당 future를 취소하고 DB 상태를 기존 API 계약대로 갱신한다.

FastAPI lifespan에서 로컬 스케줄 루프를 시작한다. 60초마다 예약 대상을 조회하고 프로세스 내부 source 락을 획득한 경우에만 같은 로컬 실행기에 작업을 등록한다. 앱 종료 시 스케줄 루프와 executor를 정리한다.

로컬 모드는 Uvicorn worker 1개만 지원한다. 다중 worker, 여러 PC, 고가용성 운영은 프로세스 내부 락을 공유할 수 없으므로 Docker 모드를 사용한다.

### 6. 실행 스크립트

`scripts/`에 다음 PowerShell 스크립트를 제공한다.

- `setup-local.ps1`: `.venv` 생성, Python 패키지 설치, Playwright Chromium 설치, npm 설치, 로컬 환경파일 준비, SQLite migration 실행
- `start.ps1`: 인자가 없으면 `local` 또는 `docker` 선택 메뉴 제공, `-Mode local|docker` 지원
- `start-local.ps1`: 포트 검사 후 API와 Vite를 숨김 프로세스로 시작하고 PID·로그 저장
- `stop-local.ps1`: PID 파일에 기록된 이 프로젝트 프로세스만 종료
- `status.ps1`: 두 포트, PID, API health 상태 표시

로컬 로그와 PID는 `temp/local-runtime/`에 저장하고 Git에 포함하지 않는다. 종료 스크립트는 PID와 실행 경로를 확인하여 다른 서비스 프로세스를 종료하지 않는다.

Docker 선택 시 `backend/.env` 존재 여부와 Docker CLI 상태를 확인한 뒤 `docker compose -f docker-compose.production.yml up -d --build`를 실행한다. 자동 설치는 하지 않는다.

### 7. 프런트엔드 연결

Vite 개발 서버 포트를 `42880`으로 고정하고 `/api`를 `http://127.0.0.1:42881`로 proxy한다. 프런트 코드는 계속 `VITE_API_BASE_URL=/api`를 사용하므로 local과 docker 사이에서 API 호출 코드를 바꾸지 않는다.

Docker의 Nginx는 기존과 같이 `/api`를 내부 `api:8000`으로 전달한다.

### 8. 헬스 상태와 오류 처리

로컬 모드의 `/api/health`는 SQLite 연결이 정상이고 Redis가 필요하지 않음을 구분해 반환한다. Docker 모드는 PostgreSQL과 Redis 연결을 모두 확인한다.

다음 경우 시작을 중단하고 명확한 한국어 메시지를 출력한다.

- `42880` 또는 `42881` 포트가 이미 사용 중
- `.venv` 또는 Node 의존성이 준비되지 않음
- SQLite migration 실패
- Docker 모드인데 Docker Desktop이 실행되지 않음

기존 프로세스, DB 파일 또는 Docker volume을 자동 삭제하지 않는다.

### 9. 문서

- `docs/setup/docker-setup.md`: Docker Desktop·WSL 2 준비, 환경파일, 실행·중지·로그·데이터 위치
- `docs/setup/local-setup.md`: Python·Node 요구사항, setup/start/stop/status, SQLite와 제한사항
- 루트 `README.md`: 두 실행 방식의 빠른 선택 안내

모든 Markdown 문서는 한국어를 먼저 작성하고 뒤에 AI 작업자를 위한 영문 계약을 분리한다.

### 10. 최소 확인 범위

사용자 지침에 따라 광범위 검증은 하지 않는다. 다음 핵심 항목만 확인한다.

1. `42880`, `42881` 포트 상수가 Docker Compose, Vite, 스크립트, 문서에 일치한다.
2. 로컬 설정에서 SQLite migration이 실행된다.
3. 로컬 dispatcher가 요청을 백그라운드로 등록하고 동일 source 동시 작업을 재사용한다.
4. 로컬 scheduler의 source 락이 중복 등록을 막는다.
5. PowerShell 스크립트 문법을 파싱한다.
6. 프런트 production build를 한 번 실행한다.

실제 네이버 크롤링, Docker 이미지 빌드, Docker 컨테이너 기동은 별도 승인 없이는 실행하지 않는다.

---

# AI Runtime Contract (English)

## Objective

Support two explicitly selectable runtimes without changing the portal or API contract:

- `local`: Python + Node.js, SQLite, in-process task runner and scheduler, no Docker/PostgreSQL/Redis.
- `docker`: the existing PostgreSQL, Redis, Celery worker/beat and container topology.

## Fixed Host Ports

- Portal: `42880`
- API: `42881`

Both modes must expose the same host ports. Container-internal ports remain `80` and `8000`. Startup must fail safely when either host port is occupied and must never terminate the occupying process.

## Runtime Boundary

Use `APP_RUNTIME=local|docker`. Runtime selection may change infrastructure adapters only. Crawling, parsing, normalization, persistence, query and export domain services remain shared.

## Local Infrastructure

- SQLite URL via `sqlite+aiosqlite`.
- Persistent file at `backend/data/wisdom_local.db`.
- Foreign keys enabled and WAL journaling applied.
- Alembic migrations made SQLite-compatible with batch operations where required.
- One background crawl executor with max concurrency 1.
- One FastAPI lifespan scheduler loop polling every 60 seconds.
- Process-local source locks.
- Uvicorn must run with one worker in local mode.

## Docker Infrastructure

Preserve PostgreSQL 16, Redis 7, Celery worker, Celery Beat, migration service, API and Nginx frontend. Change only the default host mappings to `42880` and `42881`.

## Scripts

- `scripts/setup-local.ps1`
- `scripts/start.ps1 [-Mode local|docker]`
- `scripts/start-local.ps1`
- `scripts/stop-local.ps1`
- `scripts/status.ps1`

Store project-owned PIDs and logs under `temp/local-runtime/`. Before stopping a process, validate both the recorded PID and project command path. Never kill processes by port number alone.

## Frontend

Vite listens on `127.0.0.1:42880` and proxies `/api` to `127.0.0.1:42881`. Keep `VITE_API_BASE_URL=/api` in both runtimes.

## Safety and Acceptance

- No automatic installation of Docker Desktop, WSL, Python or Node.
- No automatic deletion of SQLite data, PostgreSQL volumes or unrelated processes.
- Local mode reports Redis as not required; Docker mode requires PostgreSQL and Redis health.
- Documentation is Korean-first, followed by an explicit English AI contract.
- Verification is limited to port consistency, SQLite migration, local adapter behavior, PowerShell syntax and one frontend build. Live crawling and Docker startup remain separate approval gates.

