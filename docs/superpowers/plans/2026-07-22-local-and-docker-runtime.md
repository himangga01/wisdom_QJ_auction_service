# Docker·로컬 선택 실행 구현 계획

> **에이전트 작업자용:** `superpowers:subagent-driven-development` 또는 `superpowers:executing-plans`로 체크박스 단위 구현한다.

**목표:** 같은 포탈을 Docker 운영 모드 또는 Docker 없는 SQLite 로컬 모드로 선택 실행하고, 두 모드 모두 포탈 `42880`, API `42881`을 사용하게 한다.

**아키텍처:** 도메인·API·크롤러 코드는 공유하고 인프라 adapter만 `APP_RUNTIME`으로 선택한다. 로컬 모드는 SQLite, 단일 백그라운드 executor, FastAPI lifespan scheduler, 프로세스 내부 source lock을 사용한다. Docker 모드는 기존 PostgreSQL, Redis, Celery Worker/Beat를 유지한다.

**기술 스택:** Python 3.12+, FastAPI, SQLAlchemy async, SQLite/aiosqlite, PostgreSQL/asyncpg, Alembic, Playwright, PowerShell, React/Vite, Docker Compose

## 전체 제약

- 호스트 포탈 포트는 `42880`, API 포트는 `42881`로 고정한다.
- Docker 내부 포트 `80`, `8000`은 유지한다.
- 로컬 모드는 Uvicorn worker 1개와 crawl concurrency 1개만 지원한다.
- 로컬 SQLite 파일은 `backend/data/wisdom_local.db`에 보존한다.
- 로컬 모드에서 PostgreSQL, Redis, Celery 프로세스를 요구하지 않는다.
- Docker 모드의 기존 데이터·volume·실행 방식을 훼손하지 않는다.
- 포트 점유 프로세스나 기존 DB를 자동 종료·삭제하지 않는다.
- Markdown은 한국어 안내 뒤에 영문 AI 계약을 둔다.
- 커밋·Docker 기동·라이브 크롤링은 수행하지 않는다.
- 확인은 포트 일관성, SQLite migration, adapter 핵심 계약, PowerShell 문법, 프런트 빌드로 제한한다.

---

### 작업 1: 런타임 설정과 SQLite 연결

**파일**

- 수정: `backend/pyproject.toml`
- 수정: `backend/app/core/config.py`
- 수정: `backend/app/core/database.py`
- 수정: `backend/app/api/routes/health.py`
- 생성: `backend/tests/unit/test_runtime_config.py`

**인터페이스**

- 제공: `Settings.app_runtime: Literal["local", "docker"]`
- 제공: `Settings.is_local -> bool`
- 제공: `configure_sqlite_connection(dbapi_connection, connection_record) -> None`
- 로컬 기본 DB: `sqlite+aiosqlite:///./data/wisdom_local.db`

- [ ] `aiosqlite>=0.20,<1`을 backend dependency에 추가한다.
- [ ] `APP_RUNTIME`을 검증하고 local일 때 Redis 연결 없이 실행 가능하게 한다.
- [ ] SQLite engine에 `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`, busy timeout을 연결한다.
- [ ] health 응답에 `redis="not_required"`를 허용하고 local DB 연결만 정상이어도 `status="ok"`로 반환한다.
- [ ] runtime 설정과 health 판정의 최소 단위 테스트를 작성한다.

예상 핵심 코드:

```python
RuntimeMode = Literal["local", "docker"]

class Settings(BaseSettings):
    app_runtime: RuntimeMode = "docker"

    @property
    def is_local(self) -> bool:
        return self.app_runtime == "local"
```

---

### 작업 2: 로컬 작업 실행기와 source lock

**파일**

- 생성: `backend/app/runtime/__init__.py`
- 생성: `backend/app/runtime/local_dispatcher.py`
- 생성: `backend/app/runtime/local_locks.py`
- 수정: `backend/app/api/routes/analyses.py`
- 생성: `backend/tests/unit/test_local_runtime.py`

**인터페이스**

- 제공: `get_crawl_dispatcher() -> CrawlTaskDispatcher`
- 제공: `LocalCrawlTaskDispatcher.enqueue(run_id: UUID) -> None`
- 제공: `LocalCrawlTaskDispatcher.cancel(run_id: UUID) -> None`
- 제공: `LocalSourceLockManager.acquire/release`
- 제공: `shutdown_local_dispatcher() -> None`

- [ ] max worker 1인 singleton `ThreadPoolExecutor`에서 `crawl_tasks._run_and_dispose()`를 실행한다.
- [ ] future를 run ID별로 보존하고 완료 callback에서 제거한다.
- [ ] 대기 future만 취소하며 실행 중 작업을 강제 종료하지 않는다.
- [ ] local source lock은 `asyncio.Lock`으로 set 접근을 보호하고 token 일치 시만 해제한다.
- [ ] analyses dependency가 runtime에 따라 local 또는 Celery dispatcher를 반환하게 한다.
- [ ] enqueue가 HTTP 요청을 막지 않는지와 중복 lock을 최소 단위 테스트로 확인한다.

예상 dispatcher 선택:

```python
def get_crawl_dispatcher() -> CrawlTaskDispatcher:
    if get_settings().is_local:
        return get_local_dispatcher()
    return CeleryCrawlTaskDispatcher()
```

---

### 작업 3: FastAPI 내부 로컬 스케줄러

**파일**

- 생성: `backend/app/runtime/local_scheduler.py`
- 수정: `backend/app/main.py`
- 생성: `backend/tests/unit/test_local_scheduler.py`

**인터페이스**

- 제공: `run_local_schedule_cycle() -> dict[str, int]`
- 제공: `local_scheduler_loop(stop_event: asyncio.Event, interval_seconds: float = 60) -> None`

- [ ] local schedule cycle이 `ScheduleService.enqueue_due`에 local lock과 dispatcher를 주입한다.
- [ ] lifespan 시작 시 local 모드에만 scheduler task를 만들고 종료 시 event 설정·task 취소·executor 정리를 수행한다.
- [ ] 첫 실행은 API 시작 직후 한 번 확인하고 이후 60초 condition wait를 사용한다.
- [ ] scheduler 예외는 API 프로세스를 종료시키지 않고 최소 오류 코드로 기록한다.
- [ ] docker 모드에서는 lifespan scheduler를 시작하지 않는 단위 계약을 확인한다.

---

### 작업 4: SQLite용 Alembic migration

**파일**

- 수정: `backend/alembic/env.py`
- 수정: `backend/alembic/versions/0001_initial_schema.py`
- 수정: `backend/alembic/versions/0002_listing_aggregate_source_count.py`
- 수정: `backend/alembic/versions/0003_schedule_weekday_and_source_unique.py`

**인터페이스**

- 입력: `DATABASE_URL=sqlite+aiosqlite:///.../wisdom_local.db`
- 결과: `alembic upgrade head`가 빈 SQLite DB를 현재 head까지 생성

- [ ] Alembic configure에 SQLite일 때 `render_as_batch=True`를 적용한다.
- [ ] 초기 active source unique index에 `sqlite_where`를 추가한다.
- [ ] 0002/0003의 column·constraint 변경을 `batch_alter_table`로 감싼다.
- [ ] downgrade도 batch operation을 사용한다.
- [ ] temp SQLite URL로 migration head를 한 번 실행해 테이블과 version을 확인한다.

---

### 작업 5: 포트와 프런트 proxy 통일

**파일**

- 수정: `frontend/vite.config.ts`
- 수정: `frontend/package.json`
- 수정: `docker-compose.production.yml`
- 수정: `backend/.env.example`
- 수정: `docs/operations/runbook.md`

**인터페이스**

- 포탈: `127.0.0.1:42880`
- API: `127.0.0.1:42881`
- Vite proxy: `/api -> http://127.0.0.1:42881`

- [ ] Vite server/preview host와 port를 고정하고 `/api` proxy를 추가한다.
- [ ] npm dev script가 CLI 기본값을 덮어쓰지 않게 설정한다.
- [ ] Compose host 기본 mapping을 API `42881`, frontend `42880`으로 변경한다.
- [ ] local CORS origin과 운영 런북 주소를 새 포트로 수정한다.
- [ ] 저장소 검색으로 구 host 포트가 호스트 실행 안내에 남지 않았는지 확인한다. 컨테이너 내부 `8000`은 제외한다.

---

### 작업 6: PowerShell 선택 실행기

**파일**

- 생성: `scripts/runtime-common.ps1`
- 생성: `scripts/setup-local.ps1`
- 생성: `scripts/start-local.ps1`
- 생성: `scripts/stop-local.ps1`
- 생성: `scripts/status.ps1`
- 생성: `scripts/start.ps1`

**인터페이스**

- 실행: `.\scripts\start.ps1` 또는 `.\scripts\start.ps1 -Mode local|docker`
- 로컬 준비: `.\scripts\setup-local.ps1`
- 종료: `.\scripts\stop-local.ps1`
- 상태: `.\scripts\status.ps1`

- [ ] 공통 스크립트에 저장소 절대경로, `42880/42881`, PID/log 경로, 포트 검사 함수를 둔다.
- [ ] setup이 `.venv`, editable backend dependency, Playwright Chromium, npm dependency, `backend/data`, SQLite migration을 준비한다.
- [ ] start-local이 사전조건·포트를 검사하고 API와 Vite를 `-WindowStyle Hidden`으로 시작하며 PID를 기록한다.
- [ ] 시작 실패 시 이번 실행에서 시작한 프로젝트 프로세스만 정리한다.
- [ ] stop-local이 PID와 command line의 저장소 경로를 확인한 뒤에만 해당 PID를 종료한다.
- [ ] status가 PID/포트/API health를 읽기 전용으로 표시한다.
- [ ] start가 mode 미지정 시 선택 메뉴를 제공하고 docker 선택 시 Docker 상태와 env를 확인한 뒤 Compose를 실행한다.
- [ ] PowerShell parser API로 6개 스크립트 문법을 확인한다.

---

### 작업 7: 실행 가이드와 저장 제외 정책

**파일**

- 생성: `.gitignore`
- 생성: `README.md`
- 생성: `docs/setup/docker-setup.md`
- 생성: `docs/setup/local-setup.md`

- [ ] SQLite DB, `.venv`, `.env`, PID, log, temp runtime 파일을 root `.gitignore`에 추가한다.
- [ ] README 한국어 첫 화면에 local/docker 선택 명령과 `42880/42881` 주소를 표시한다.
- [ ] Docker 문서에 WSL 2/Docker Desktop, env, start/stop/log/volume 위치와 포트를 기록한다.
- [ ] 로컬 문서에 Python/Node, setup/start/stop/status, SQLite 위치, 단일 worker 제한을 기록한다.
- [ ] 각 문서의 한국어 섹션 뒤에 영문 AI 실행 계약을 추가한다.

---

### 작업 8: 승인된 최소 확인

**파일**

- 생성: `scripts/check-runtime-ports.ps1`

- [ ] 정적 검사로 Compose, Vite, scripts, docs의 host port가 `42880/42881`인지 확인한다.
- [ ] 현재 TCP listener에서 두 포트가 비어 있는지 확인한다.
- [ ] SQLite migration head를 실행한다.
- [ ] runtime/dispatcher/lock/scheduler의 지정 단위 테스트만 실행한다.
- [ ] 모든 PowerShell 스크립트를 parser로 확인한다.
- [ ] `npm run build`를 한 번 실행한다.
- [ ] Docker build/up과 라이브 네이버 크롤링은 실행하지 않는다.

---

# AI Execution Contract (English)

## Goal

Implement selectable `local` and `docker` runtimes with identical portal/API behavior. Use host ports `42880` and `42881` everywhere.

## Required Task Order

1. Add `APP_RUNTIME`, aiosqlite and SQLite engine pragmas.
2. Implement singleton local dispatcher and process-local source locks.
3. Add the FastAPI lifespan scheduler for local mode only.
4. Make all Alembic revisions executable against SQLite.
5. Change host ports and add the Vite API proxy.
6. Add safe PowerShell setup/start/stop/status/runtime selector scripts.
7. Add Korean-first setup documentation followed by English contracts.
8. Run only the explicitly approved focused checks.

## Safety Contract

- Never kill a process by port alone.
- Never delete SQLite data, PostgreSQL volumes or existing `.env` files.
- Local runtime is single-process and max crawl concurrency 1.
- Docker runtime retains PostgreSQL, Redis, Celery Worker and Celery Beat.
- Internal container ports remain unchanged.
- No commit, Docker startup, or live crawl is authorized by this plan.

