# 네이버 부동산 조사 포탈

## 한국어 안내

네이버 부동산 URL 한 개를 기준으로 아파트 매물 조사 이력, 날짜별 변화, 상세 정보와 XLSX 내보내기를 제공하는 React + FastAPI 프로젝트다. 실행 방식은 로컬 또는 Docker 중에서 선택할 수 있다. 로컬 수집은 별도 전용 프로필로 실행한 일반 Google Chrome에 연결한다.

### 현재 구현 상태

현재 구현된 주요 기능은 다음과 같다.

- 네이버 부동산 URL 한 개를 입력해 아파트 매매·전세·월세 매물을 조사한다.
- 일반 Google Chrome 화면을 탐색하며 `중개사 n곳에서 등록했어요`의 전체 등록 행과 각 물건의 상세 슬라이드를 수집한다.
- Npay 물건은 `Npay 부동산에서 보기` 내부 경로를 우선 사용하고, 불완전한 전수 수집 결과는 저장하지 않는다.
- 중복 등록을 대표 매물로 통합하면서 중개사별 원본, 상세 설명, 옵션, 시세·비용·관리비·단지·입지 정보를 함께 보존한다.
- 조사 날짜별 매물 목록과 신규·변경·미노출·삭제·재노출 이력을 비교한다.
- 대시보드, 조사 아파트 목록, 날짜별 아파트 상세, 개별 매물 상세 화면을 분리해 제공한다.
- 매물 화면은 카드·리스트·테이블 방식과 조사일 간 사양 비교를 지원한다.
- 자동 조사 스케줄, 중개사 상세 수집 여부, Chrome 탐색 속도, 인앱 변경 알림을 설정할 수 있다.
- 아파트·매물·중개사 등록·상세정보·조사이력·변경 이벤트를 XLSX로 내려받을 수 있다.
- 최초 관리자 등록, 로그인, 사용자별 데이터 분리, 사용자·권한 관리 기능을 제공한다.
- Windows 단일 로컬 환경과 Docker Compose 환경을 모두 지원한다.

완료 작업, 검증 근거, 커밋 이력과 남은 작업은 [프로젝트 작업 현황](docs/project-status.md)을 기준으로 확인한다. `docs/superpowers/plans/` 아래 문서는 각 작업을 설계·실행할 당시의 계획 이력이다.

### Docker 없이 로컬 실행

Python 3.12~3.14, Node.js 22 LTS, Google Chrome을 설치한 뒤 PowerShell에서 실행한다.

```powershell
.\scripts\setup-local.ps1
.\scripts\start.ps1 -Mode local
```

`setup-local.ps1`은 Python 3.12~3.14와 Node.js 22를 확인하고 의존성을 설치한다. 최초 관리자 설정용 무작위 token은 `backend/data/bootstrap-token.txt`에 생성되며, 관리자 설정 화면에서 `Get-Content .\backend\data\bootstrap-token.txt`로 확인한다. 수집 브라우저는 설치된 Google Chrome을 사용하므로 별도 Playwright Chromium 바이너리는 설치하지 않는다.

로컬 모드는 `backend/data/wisdom_local.db` SQLite 파일과 단일 백그라운드 작업 실행기를 사용한다. 시작할 때 일반 Chrome을 전용 프로필과 loopback CDP 포트 `42973`으로 자동 실행한다. 사용자 기본 Chrome 프로필은 읽지 않는다. 상태 확인과 종료 명령은 다음과 같다.

```powershell
.\scripts\status.ps1
.\scripts\stop-local.ps1
```

자세한 내용: [로컬 실행 가이드](docs/setup/local-setup.md)

### Windows 수동 로컬 실행

통합 스크립트 대신 API와 포탈을 각각 실행하려면 로컬 환경파일을 준비하고 전용 Chrome, migration, Uvicorn, Vite를 순서대로 실행한다.

```powershell
Copy-Item .\backend\.env.local.example .\backend\.env
. .\scripts\runtime-common.ps1
Set-LocalRuntimeEnvironment
.\scripts\start-naver-browser.ps1
```

전체 명령과 종료 방법은 [로컬 실행 가이드](docs/setup/local-setup.md)의 `수동 로컬 실행`을 따른다. Docker 모드로 전환할 때는 `backend/.env.example`을 다시 복사해 `APP_RUNTIME`과 데이터베이스 URL을 함께 변경한다.

### Docker 실행

Docker Desktop과 WSL 2를 준비하고 환경파일을 만든 뒤 실행한다.

```powershell
Copy-Item .\backend\.env.example .\backend\.env
.\scripts\start.ps1 -Mode docker
```

실행 전에 `backend/.env`의 공개 예시 `AUTH_BOOTSTRAP_TOKEN`을 32바이트 이상 무작위 값으로 반드시 교체한다. 전체 서비스의 공식 구성은 저장소 루트의 `docker-compose.production.yml`이다. 시작 스크립트는 `backend/.env`를 Compose 변수 치환과 컨테이너 환경변수에 함께 사용한다.

Docker에서도 Backend가 브라우저를 직접 실행하지 않는다. 비 root Chrome/Xvfb sidecar가 영속 `chrome_profile` 볼륨을 사용하고, API와 worker는 Compose 내부 주소 `http://chrome:9222`에 CDP로 연결한다. `9222`는 호스트에 공개하지 않는다.

자세한 내용: [Docker 설치·실행 가이드](docs/setup/docker-setup.md)

### 네이버 라이브 E2E

기본 비활성인 표본 라이브 E2E의 안전 정책과 결과 해석은 [네이버 라이브 E2E 가이드](docs/testing/naver-live-e2e.md)를 참고한다.

```powershell
.\scripts\start-naver-browser.ps1
Set-Location .\backend
$env:RUN_LIVE_NAVER_E2E = "1"
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -m live_naver -q
```

### 네이버 수집 범위와 데이터

- 네이버 수집은 일반 외부 Google Chrome의 UI와 loopback CDP만 사용한다. 네이버 API 또는 직접 HTTP 호출은 금지한다.
- Chrome이 정상 페이지 navigation으로 리소스를 로드하며, collector는 페이지 안의 DOM만 조작한다.
- production 전수 수집에는 스크롤 횟수, 그룹 수, 물건 수의 고정 상한이 없다. 표시 건수를 채우지 못하거나 `중개사 n곳`의 상세 행을 모두 확보하지 못하면 불완전 결과를 저장하지 않고 fail-closed 처리한다.
- 각 물건에서 지연 로딩되는 중개사 행을 끝까지 펼치고, 물건별 상세 슬라이드를 읽어 저장한다. `BrokerArticleSnapshot.details_json`에는 물건별 `market_details` 중첩 구조가 저장되며, 기존 스냅샷은 `None`으로 역직렬화된다.
- React 등록 카드와 XLSX 중개사등록 시트는 물건별 상세 데이터를 반영한다. 표본 E2E의 25개 그룹 제한은 테스트 전용이며 production 전수 수집에는 적용하지 않는다.
- 실제 네이버 라이브 E2E는 기본 비활성 상태이며, 명시적 승인과 보호된 실행 환경이 준비된 경우에만 아파트 1곳을 대상으로 실행한다.

### 접속 주소

- 포탈: `http://127.0.0.1:42880`
- API: `http://127.0.0.1:42881`
- API 문서: `http://127.0.0.1:42881/docs`

`start.ps1`에서 `-Mode`를 생략하면 로컬 또는 Docker 실행 방식을 선택하는 메뉴가 표시된다.

---

# AI Runtime Reference (English)

This repository supports two explicit runtime modes while preserving the same frontend and API contract.

- `local`: `APP_RUNTIME=local`, SQLite at `backend/data/wisdom_local.db`, one Uvicorn worker, one in-process crawl executor and scheduler.
- `docker`: `APP_RUNTIME=docker`, PostgreSQL, Redis, Celery worker/beat, FastAPI and Nginx through Docker Compose.
- `APP_RUNTIME` is the only runtime selector. Local attaches to `http://127.0.0.1:42973`; Docker attaches to `http://chrome:9222`.
- Both modes use `playwright.chromium.connect_over_cdp()` only. There is no Playwright-owned browser launch fallback.
- Docker runs a non-root Chrome/Xvfb sidecar with the persistent `chrome_profile` volume. CDP port `9222` is internal-only and is never published to the host.
- No stealth, fingerprint alteration, CAPTCHA solver, proxy rotation, or direct Naver data API is used.
- Host ports are fixed to frontend `42880` and API `42881`. Docker-internal ports remain `80` and `8000`.
- Use `scripts/setup-local.ps1` once, then `scripts/start.ps1 -Mode local`; use `scripts/stop-local.ps1` only for local processes.
- Local setup generates the first-admin secret at `backend/data/bootstrap-token.txt`; treat it as a password and enter it only in the bootstrap form.
- For manual local startup, copy `backend/.env.local.example` to `backend/.env`, dot-source `scripts/runtime-common.ps1`, call `Set-LocalRuntimeEnvironment`, start the dedicated Chrome, then run Alembic, Uvicorn, and Vite separately.
- Local setup validates Node.js 22 and uses the installed Google Chrome without installing a Playwright-owned Chromium binary.
- The canonical full-service Docker file is `docker-compose.production.yml`; `start.ps1` passes `backend/.env` through Compose `--env-file`.
- Docker startup requires replacing the rejected example `AUTH_BOOTSTRAP_TOKEN` with a cryptographically random value of at least 32 bytes.
- Docker setup never installs Docker automatically and never deletes volumes.

## Naver Collection Contract

- Naver acquisition uses only ordinary external Chrome UI and loopback CDP. Direct Naver APIs and direct HTTP calls are forbidden.
- Chrome loads page resources through ordinary navigation; the collector manipulates only the in-page DOM.
- Full production collection has no fixed scroll, group, or article limit. It fails closed instead of persisting data when displayed counts or lazy-loaded broker-detail rows are incomplete.
- The collector expands every `중개사 n곳` row and stores the detail slide for every article. `BrokerArticleSnapshot.details_json` holds nested per-article `market_details`; legacy snapshots deserialize it as `None`.
- React registration cards and the XLSX broker-registration sheet expose per-article detail. The 25-group sampled boundary is test-only and never constrains full production collection.
- The current live-test scope is one apartment, run separately under explicit user direction.

## Naver Live E2E

See the [Naver Live E2E guide](docs/testing/naver-live-e2e.md) for safety rules and result interpretation. The sampled run is opt-in:

```powershell
.\scripts\start-naver-browser.ps1
Set-Location .\backend
$env:RUN_LIVE_NAVER_E2E = "1"
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -m live_naver -q
```

## Project Status

The authoritative record of implemented capabilities, verification evidence, commit history, and remaining work is [docs/project-status.md](docs/project-status.md). Files under `docs/superpowers/plans/` are historical design and execution plans and may contain baselines that predate the current `main` branch.
