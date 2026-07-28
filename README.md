# 네이버 부동산 조사 포탈

## 한국어 안내

네이버 부동산 URL 한 개를 기준으로 아파트 매물 조사 이력, 날짜별 변화, 상세 정보와 XLSX 내보내기를 제공하는 React + FastAPI 프로젝트다. 실행 방식은 로컬 또는 Docker 중에서 선택할 수 있다. 로컬 수집은 별도 전용 프로필로 실행한 일반 Google Chrome에 연결한다.

### Docker 없이 로컬 실행

Python 3.12~3.14, Node.js 22 LTS, Google Chrome을 설치한 뒤 PowerShell에서 실행한다.

```powershell
.\scripts\setup-local.ps1
.\scripts\start.ps1 -Mode local
```

로컬 모드는 `backend/data/wisdom_local.db` SQLite 파일과 단일 백그라운드 작업 실행기를 사용한다. 시작할 때 일반 Chrome을 전용 프로필과 loopback CDP 포트 `42973`으로 자동 실행한다. 사용자 기본 Chrome 프로필은 읽지 않는다. 상태 확인과 종료 명령은 다음과 같다.

```powershell
.\scripts\status.ps1
.\scripts\stop-local.ps1
```

자세한 내용: [로컬 실행 가이드](docs/setup/local-setup.md)

### Docker 실행

Docker Desktop과 WSL 2를 준비하고 환경파일을 만든 뒤 실행한다.

```powershell
Copy-Item .\backend\.env.example .\backend\.env
.\scripts\start.ps1 -Mode docker
```

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
- 이번 실제 테스트 범위는 사용자 지시에 따라 아파트 1곳을 별도 실행하는 것으로 한정한다.

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
- Local collection defaults to `CRAWLER_BROWSER_MODE=external_chrome` and attaches to an ordinary Google Chrome at `http://127.0.0.1:42973`, launched with the dedicated `backend/data/naver-chrome-profile`.
- Docker retains the Playwright-owned browser fallback. No stealth, fingerprint alteration, CAPTCHA solver, proxy rotation, or direct Naver data API is used.
- Host ports are fixed to frontend `42880` and API `42881`. Docker-internal ports remain `80` and `8000`.
- Use `scripts/setup-local.ps1` once, then `scripts/start.ps1 -Mode local`; use `scripts/stop-local.ps1` only for local processes.
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
