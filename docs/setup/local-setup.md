# Docker 없는 로컬 실행 가이드

## 한국어 안내

### 1. 준비물

- Windows PowerShell
- Python 3.12 이상 3.15 미만
- Node.js 22 LTS와 npm
- Google Chrome

Docker, PostgreSQL, Redis, Celery 프로세스는 필요하지 않다. PowerShell 실행 정책 때문에 스크립트가 차단되면 현재 창에서만 다음 명령을 적용할 수 있다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### 2. 최초 한 번 준비

저장소 루트에서 실행한다.

```powershell
.\scripts\setup-local.ps1
```

이 스크립트는 `.venv` 생성, 백엔드 패키지와 Playwright Chromium 설치, npm 패키지 설치, `backend/data` 준비와 SQLite 마이그레이션을 순서대로 수행한다. Python, Node.js, Google Chrome 자체는 설치하지 않는다.

### 3. 시작·상태·종료

```powershell
.\scripts\start.ps1 -Mode local
.\scripts\status.ps1
.\scripts\stop-local.ps1
```

- `start.ps1 -Mode local`은 API보다 먼저 일반 Google Chrome을 전용 프로필로 실행한다.
- Chrome CDP는 `127.0.0.1:42973`에만 열리며 외부 주소에서는 접근할 수 없다.
- 전용 프로필은 `backend/data/naver-chrome-profile`에 저장한다. 사용자의 기본 Chrome 프로필·쿠키·로그인 상태를 읽지 않는다.
- 일반 Chrome 창이 화면에 보이는 것이 정상이다. 수집기는 이 창의 기본 context에 새 탭을 만들고, 수집이 끝나면 자신이 만든 탭과 CDP 연결만 닫는다.
- `status.ps1`은 포탈/API와 함께 전용 Chrome의 PID, 포트, 프로필 소유권을 확인한다.
- `stop-local.ps1`은 저장소가 시작한 전용 Chrome임을 확인한 경우에만 종료한다.

- 포탈: `http://127.0.0.1:42880`
- API: `http://127.0.0.1:42881`
- API 문서: `http://127.0.0.1:42881/docs`

시작 스크립트는 두 포트가 비어 있는지 확인한 후 API와 Vite를 숨김 프로세스로 실행한다. 다른 프로세스가 포트를 사용 중이면 그 프로세스를 종료하지 않고 중단한다.

### 4. Chrome만 별도로 시작

라이브 E2E처럼 포탈/API 없이 수집용 Chrome만 필요하면 저장소 루트에서 실행한다.

```powershell
.\scripts\start-naver-browser.ps1
.\scripts\status.ps1
```

Chrome 136 이상은 기본 프로필에 대한 원격 디버깅을 제한하므로 `--user-data-dir`이 필요하다. 시작 스크립트가 전용 프로필, `--remote-debugging-address=127.0.0.1`, `--remote-debugging-port=42973`을 자동 적용한다. 포트가 이미 사용 중이거나 Chrome을 찾지 못하면 임의 프로세스를 종료하지 않고 오류로 중단한다.

### 5. 데이터와 로그

- SQLite: `backend/data/wisdom_local.db`
- 수집용 Chrome 전용 프로필: `backend/data/naver-chrome-profile/`
- PID와 로그: `temp/local-runtime/`

`stop-local.ps1`은 기록된 PID와 명령행에 현재 저장소 경로가 모두 확인된 프로세스만 종료한다. SQLite 파일과 로그는 삭제하지 않는다.

### 6. 로컬 모드 제한

로컬 모드는 개인 개발·데모용이며 Uvicorn worker와 크롤링 동시 실행 수를 각각 1개로 제한한다. 여러 사용자, 여러 서버 또는 장시간 운영에는 Docker 모드를 사용한다. 실제 조사 시 네이버 이용약관, robots 정책과 접근 제한을 준수하고 CAPTCHA나 로그인 제한을 우회하지 않는다.

### 7. 네이버 수집 동작 원칙

- 수집기는 일반 외부 Chrome UI와 loopback CDP만 사용한다. 네이버 API 및 네이버에 대한 직접 HTTP 호출은 사용하거나 추가하지 않는다.
- Chrome이 일반 페이지 navigation으로 필요한 리소스를 로드하고, 수집기는 열린 페이지의 DOM만 클릭·스크롤·조회한다.
- production 전수 수집은 스크롤 횟수, 목록 그룹, 물건 수에 고정 상한을 두지 않는다. 표시된 매물 건수에 미달하거나 물건별 `중개사 n곳` 지연 로딩 행을 끝까지 확보하지 못하면 불완전 데이터를 저장하지 않고 fail-closed 처리한다.
- 물건마다 중개사 행을 모두 펼친 뒤 각 물건의 상세 슬라이드를 저장한다. 스냅샷의 `BrokerArticleSnapshot.details_json`은 중첩 `market_details`를 포함하며, 과거 스냅샷의 해당 값은 `None`이다.
- React 등록 카드와 XLSX 중개사등록 시트는 이 물건별 상세 정보를 사용한다. 25개 그룹 제한은 sampled E2E 테스트에만 적용된다.

---

# AI Local Runtime Contract (English)

Prerequisites are Windows PowerShell, Python `>=3.12,<3.15`, Node.js 22 LTS, and Google Chrome. `setup-local.ps1` creates `.venv`, installs backend/browser/frontend dependencies, and migrates the SQLite database. It does not install Python, Node, or Chrome.

Run `start.ps1 -Mode local`, inspect with `status.ps1`, and stop with `stop-local.ps1`. Local startup first launches ordinary Chrome with a dedicated profile at `backend/data/naver-chrome-profile` and loopback-only CDP `127.0.0.1:42973`; it never reuses the user's default profile. Use `start-naver-browser.ps1` when only the crawler Chrome is required. The portal/API ports are `42880/42881`. Local state is stored in `backend/data/wisdom_local.db`; process metadata and logs are stored under `temp/local-runtime/`. Never stop a PID unless its command line identifies this repository and the expected component. Local mode is single-process with crawl concurrency one.

## Naver Collection Contract

Naver collection uses only ordinary external Chrome UI and loopback CDP; direct Naver APIs and direct HTTP calls are forbidden. Chrome loads resources through normal page navigation, while the collector operates only on the open page DOM. Full production collection has no fixed scroll, group, or article cap. If displayed counts are short or any lazy-loaded `중개사 n곳` broker-detail rows remain unavailable, it fails closed and does not persist incomplete data. Every broker row is expanded and every article detail slide is saved. `BrokerArticleSnapshot.details_json` contains nested per-article `market_details`, and legacy snapshots deserialize that field as `None`. React registration cards and the XLSX broker-registration sheet consume this per-article detail. The 25-group limit applies only to sampled E2E tests.
