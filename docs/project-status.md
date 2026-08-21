# 프로젝트 작업 현황

## 한국어 기록

### 1. 기준 정보

- 기준일: 2026-08-21 (Asia/Seoul)
- 기준 브랜치: `main`
- 문서 작성 전 기준 커밋: `aff231e03a0fd61e7e6df7fc04eb1185524c91e7`
- 최신 기능 커밋: `aff231e fix: track Chrome CDP listener process`
- 최신 기능 커밋 CI: [GitHub Actions 실행 31246217215](https://github.com/himangga01/wisdom_QJ_auction_service/actions/runs/31246217215) 성공
- 사용자 소유 `temp/`는 프로젝트 기록·커밋 대상에서 제외한다.

이 문서는 현재 `main`의 구현 상태와 다음 작업의 기준 문서다. `docs/superpowers/plans/` 아래 문서는 설계와 구현 당시의 계획 이력으로 보존하며, 오래된 기준 커밋이나 이미 완료된 체크박스를 포함할 수 있다.

### 2. 지금까지 완료한 작업

#### 2.1 사용자 포털과 화면 구성

- 메인 화면은 네이버 부동산 URL 한 개를 입력해 아파트 한 곳의 분석을 요청한다.
- 분석 요청 후 진행 단계·진행률·오류·취소 상태를 입력 화면 아래에서 표시한다.
- 대시보드는 현재 선택한 아파트 한 곳의 최근 조사 시각과 매매·전세·월세 평균 호가 및 매물 수를 보여준다.
- 기존에 조사한 아파트를 선택해 대시보드 대상을 전환할 수 있다.
- 조사 아파트 페이지는 아파트명·주소 검색, 서버 페이지 이동, 페이지당 20·50·100개 표시를 지원한다.
- 아파트 상세 페이지는 조사 날짜와 비교 기준일을 선택해 동일 매물을 나란히 비교한다.
- 신규·변경·미노출·삭제·재노출 상태와 달라진 가격·면적·층·방향·옵션·관리비·입주 조건을 강조한다.
- 선택 조사일의 매물은 카드·리스트·테이블 보기 방식으로 전환할 수 있다.
- 개별 매물 상세 페이지는 단지 기본정보, 대표 매물, 정제된 추가정보와 중개사별 등록 내용을 제공한다.
- `중개사 n곳에서 등록했어요` 영역은 기본적으로 접혀 있고 사용자가 펼쳐 중개사별 상세를 확인한다.

#### 2.2 Chrome 기반 네이버 수집

- 네이버 수집은 네이버 데이터 API나 직접 HTTP 수집 대신 일반 Google Chrome UI와 CDP 연결을 사용한다.
- 로컬 환경은 설치된 Chrome을 전용 프로필과 `127.0.0.1:42973` CDP 포트로 실행한다.
- Docker 환경은 비 root Chrome/Xvfb sidecar와 내부 전용 `chrome:9222` CDP 주소를 사용한다.
- Playwright는 외부 Chrome에 `connect_over_cdp()`로 연결하며 자체 Chromium 실행 fallback은 사용하지 않는다.
- 매매·전세·월세 탭의 지연 로딩 목록을 끝까지 탐색하며 운영 전수 수집에는 고정 매물·그룹 상한이 없다.
- 모든 `중개사 n곳에서 등록했어요` 그룹을 펼치고 표시된 중개사 행을 전부 확인한다.
- 중개사별 물건을 클릭해 상세 슬라이드를 읽으며, Npay 물건은 `Npay 부동산에서 보기` 경로를 우선 사용한다.
- 표시 매물·중개사 수와 실제 수집 수가 일치하지 않으면 불완전 데이터를 저장하지 않는 fail-closed 정책을 적용한다.
- 로그인 요구, CAPTCHA, 선택자 불일치, 브라우저 연결 실패와 불완전 수집을 구분된 오류로 처리한다.

#### 2.3 수집 옵션과 데이터 정제

- 사용자는 분석 및 스케줄에서 중개사별 추가 상세정보 수집 여부를 선택할 수 있다.
- Chrome 화면 탐색 속도는 `매우 빠름 0.5초`, `빠름 0.7~1.2초`, `기본 1~2.5초`, `신중 2~5초`, `매우 신중 3~7초`를 지원한다.
- 대표 매물에는 거래 유형, 가격, 보증금, 월세, 동·층, 공급·전용면적, 방향과 관측 시각을 저장한다.
- 중개사별 원본에는 물건번호, 제공업체, Npay 여부, 가격, 관리비, 융자, 면적, 방·욕실, 방향, 구조, 입주일, 설명, 옵션과 중개사 정보를 저장한다.
- 상세 슬라이드의 금융·거래·비용·관리비·단지·입지·추가 필드를 구조화해 저장한다.
- 동일 실제 매물의 중개사 중복 등록을 대표 매물 하나로 통합하고 중개사별 원본은 별도로 보존한다.
- 시스템에어컨, 중문, 식기세척기 등 옵션과 입주일·관리비·융자 내용을 정제하고 중복 값을 제거한다.

#### 2.4 조사 이력, 비교, 스케줄과 알림

- 아파트·대표 매물·중개사 원본·상세정보를 조사 실행별 스냅샷으로 저장한다.
- 첫 미관측은 `missing`, 완료된 조사에서 연속 두 번째 미관측은 `removed`, 다시 관측되면 `restored`로 기록한다.
- 가격과 주요 사양 변경 필드를 비교해 `changed` 이벤트를 생성한다.
- 매일·평일·매주 특정 요일과 실행 시각을 설정하는 자동 조사 스케줄을 제공한다.
- 로컬 환경은 단일 프로세스 작업 실행기와 내부 스케줄러, Docker 환경은 Redis·Celery worker/beat를 사용한다.
- 신규·변경·삭제·재노출별 인앱 알림 설정, 안 읽은 알림 필터, 개별·전체 읽음 처리와 상세 화면 이동을 지원한다.

#### 2.5 XLSX 내보내기

- 선택한 조사 출처의 데이터를 `.xlsx` 파일로 다운로드한다.
- 아파트 요약, 매물 현황, 정제 추가정보, 중개사 등록정보, 상세정보, 조사이력, 변경 이벤트 시트를 생성한다.
- 중개사별 상세 수집 여부와 금융·거래·비용·관리비·단지·입지 필드를 반영한다.
- 날짜 범위를 지정한 서버 내보내기를 지원한다.

#### 2.6 인증, 사용자 분리와 운영 기반

- 최초 관리자 bootstrap, 이메일·비밀번호 로그인, 로그아웃과 비밀번호 변경을 구현했다.
- 조사 출처, 분석, 조회, 스케줄, 알림과 내보내기를 사용자 소유권 기준으로 분리한다.
- 관리자는 사용자 생성, 검색, 권한 변경, 활성화·비활성화와 임시 비밀번호 설정을 할 수 있다.
- Windows 로컬 모드는 SQLite, 단일 Uvicorn과 전용 Chrome을 사용한다.
- Docker 모드는 PostgreSQL, Redis, Celery, FastAPI, Nginx와 Chrome sidecar를 사용한다.
- 로컬 포트는 Portal `42880`, API `42881`, Chrome CDP `42973`으로 고정했다.
- PowerShell 설치·기동·상태·종료 스크립트와 로컬·Docker 실행 가이드를 작성했다.
- Chrome이 자식 프로세스에서 CDP listener를 소유하는 경우 실제 listener PID를 기록하고 안전하게 종료하도록 수정했다.

### 3. 검증 및 안정화 기록

#### 3.1 자동 CI

- `cbcbaa6`에서 PostgreSQL Alembic version 칼럼 길이, Frontend Node/jsdom 이식성, 삭제 매물 분류와 Live workflow 정의 오류를 수정했다.
- `2171c8a`에서 실제 CDP 연결 구조와 플랫폼 환경에 맞게 Backend 테스트 fixture를 정렬했다.
- `aff231e` 자동 CI 실행 `31246217215`가 성공했다.
- CI에는 Backend 비라이브 테스트, 임시 PostgreSQL migration, Frontend lint/test/build와 Docker Compose 계약 검사가 포함된다.

#### 3.2 Windows 로컬 무수집 스모크

2026-08-08에 네이버 분석 요청 없이 다음 항목을 확인했다.

- Portal 프로세스와 포트 `42880` 실행
- API 프로세스와 포트 `42881` 실행
- 전용 Chrome과 CDP 포트 `42973` 실행
- API `/api/health`: `status=ok`, Chrome readiness `ready`
- Portal 응답: HTTP `200`
- 종료 스크립트로 Portal, API와 전용 Chrome 종료
- 종료 후 세 포트가 모두 비어 있고 PID 기록이 남지 않음

#### 3.3 최근 커밋 이력

| 커밋 | 기록 |
|---|---|
| `45470ff` | React/FastAPI 포털, Chrome 수집, 스냅샷·비교·스케줄·XLSX와 로컬/Docker 기반 초기 구현 |
| `917ac53` | 날짜별 아파트 이력·비교 UX, 목록 페이지 이동, Windows 이중 실행 환경 강화 |
| `a1b4308` | 인증·사용자 격리·알림, 외부 Chrome 보안 계약, CI와 보호형 Live E2E 기반 구현 |
| `cbcbaa6` | PostgreSQL migration과 CI 이식성, Frontend 상태 분류, Live workflow 정의 수정 |
| `2171c8a` | Backend fixture와 실제 런타임 계약 정렬 |
| `aff231e` | Chrome 자식 CDP listener PID 인식 및 회귀 테스트 추가 |

### 4. 남은 작업

현재 알려진 필수 코드 차단 문제는 없다. 다음 작업은 외부 환경 검증, 실제 사이트 접근, 운영 안정화와 후속 스키마 정리이며 각 단계는 별도 승인과 선행 조건을 요구한다.

#### P1. Windows Docker 전체 스택 무수집 점검

상태: 코드와 Compose 구성은 구현됐지만 현재 저장소 기준 실제 Windows Docker 전체 기동 검증은 완료되지 않았다.

선행 조건과 완료 기준:

- 사용자가 WSL 2와 Docker Desktop을 설치하고 실행한다.
- `docker-compose.production.yml`로 PostgreSQL, Redis, migration, API, worker, scheduler, Portal과 Chrome sidecar를 기동한다.
- 네이버 URL을 제출하지 않고 Compose 상태, API health와 Portal health만 확인한다.
- `down -v`를 사용하지 않고 데이터와 Chrome profile 볼륨을 보존한 채 종료한다.

#### P1. 보호형 네이버 Live E2E 한 곳 실행

상태: opt-in 테스트 코드와 GitHub workflow는 구현됐지만 현재 `main`으로 보호된 Windows runner에서 실제 한 곳을 끝까지 비교하는 실행은 남아 있다.

선행 조건과 완료 기준:

- GitHub Environment `naver-live-e2e`와 required reviewer를 구성한다.
- `self-hosted`, `windows`, `naver-e2e` label의 전용 Windows runner를 준비한다.
- checkout 밖에 테스트 case manifest와 30분 이내 최신 GPT reference를 준비한다.
- 대상 아파트 한 곳과 실제 네이버 접속을 사용자가 실행 직전에 다시 승인한다.
- CAPTCHA, 로그인 요구, 403/429 또는 접근 제한이면 우회 없이 즉시 중단한다.
- 성공 artifact에는 전체 URL, 연락처, 주소, 등록번호, 쿠키, raw HTML과 장문 설명을 넣지 않는다.

#### P2. 단일 사용자 운영 파일럿

상태: 운영 runbook과 데이터 정책은 작성됐지만 실제 운영 파일럿은 시작하지 않았다.

선행 조건과 완료 기준:

- 일반 CI, Windows Docker 무수집 점검과 보호형 Live E2E가 먼저 성공한다.
- 허용 수집 필드, 보존 기간, 백업·복구 책임자와 운영 승인을 기록한다.
- 단일 사용자·단일 URL·동시성 1·하루 최대 1회로 14일 운영한다.
- completed/partial/failed/blocked, 수집 수 불일치, 선택자 오류, 오삭제 판정과 실행시간을 개인정보 없이 집계한다.

#### P3. 레거시 전역 매물 상태 칼럼 제거

상태: `SourceListingState`가 출처별 생명주기의 기준이지만 `ListingGroup`의 전역 상태 칼럼은 호환 목적으로 남아 있다.

선행 조건과 완료 기준:

- 최소 한 번의 green release, 14일 파일럿과 데이터 백업을 완료한다.
- 별도 Alembic revision에서 `first_seen_at`, `last_seen_at`, `state`, `missing_count`를 제거한다.
- migration downgrade와 PostgreSQL CI를 포함해 별도 커밋으로 검증한다.
- 이 작업은 운영 데이터에 영향을 줄 수 있으므로 명시적 스키마 변경 승인을 받은 뒤 진행한다.

### 5. 다음 작업 수행 원칙

- 우선순위는 Docker 무수집 점검 → 보호형 Live E2E → 운영 파일럿 → 레거시 스키마 정리 순서다.
- 실제 네이버 접속, Docker 기동, 운영 배포, 데이터 backup/restore와 destructive migration은 각각 사용자 승인을 받은 뒤 수행한다.
- 네이버 데이터 API 직접 호출, 직접 HTTP 수집, CAPTCHA 우회, stealth, fingerprint 조작과 proxy rotation은 사용하지 않는다.
- `temp/`, 비밀정보, 전체 네이버 URL과 중개사 개인정보를 Git에 추가하지 않는다.
- 새 기능·수정·검증 결과가 `main`에 반영되면 이 문서의 기준 커밋, 완료 기록과 남은 작업을 함께 갱신한다.

---

# AI Continuation Record (English)

## 1. Baseline

- Status date: 2026-08-21, Asia/Seoul.
- Branch before this documentation update: `main`.
- Baseline commit: `aff231e03a0fd61e7e6df7fc04eb1185524c91e7`.
- Latest baseline CI: GitHub Actions run `31246217215`, conclusion `success`.
- Never inspect, modify, stage, commit, or delete the user-owned untracked `temp/` directory.
- This file is the current status source. Files under `docs/superpowers/plans/` are historical plans and can contain stale baselines or unchecked tasks that have since been completed.

## 2. Implemented System

- React 19, TypeScript, Tailwind CSS, React Query and Recharts provide the portal UI.
- FastAPI, async SQLAlchemy and Alembic provide the API and persistence layer.
- A single Naver Land URL represents one tracked apartment source.
- Acquisition uses an ordinary external Google Chrome session through Playwright CDP only. No direct Naver data API or direct HTTP acquisition is allowed.
- Full production collection has no fixed listing, group, or scroll limit. It expands every broker group and optionally collects each broker article detail slide.
- Npay listings prefer the internal `Npay 부동산에서 보기` target.
- Count reconciliation is fail-closed: incomplete displayed listing or broker-row coverage is not persisted as a valid complete result.
- Data includes apartment, listing group, broker article, market detail, run snapshot, source-specific lifecycle state and change event records.
- The UI provides URL analysis, selected-apartment dashboard, paginated apartment research, date-based history, side-by-side listing comparison, card/list/table modes, individual listing detail, schedules, notifications, XLSX export, authentication and administration.
- Runtime modes are Windows local with SQLite/in-process jobs and Docker Compose with PostgreSQL/Redis/Celery/Chrome sidecar.

## 3. Verified Evidence

- Baseline CI run `31246217215` passed Backend non-live tests, ephemeral PostgreSQL migrations, Frontend lint/test/build and Compose contract validation.
- A no-acquisition Windows local smoke on 2026-08-08 observed API status `ok`, browser readiness `ready`, Portal HTTP `200`, then stopped Portal/API/dedicated Chrome and confirmed ports `42880`, `42881`, and `42973` were free.
- Commit `aff231e` fixed Chrome installations where the CDP listener is owned by a child Chrome PID and added a Windows regression contract test.

## 4. Remaining Work Order

1. **P1 Windows Docker no-acquisition smoke**
   - Requires user-installed and running WSL 2 plus Docker Desktop.
   - Start the production Compose stack, verify service/API/Portal health without submitting a Naver URL, and stop without `down -v`.
2. **P1 protected one-apartment live E2E**
   - Requires the protected GitHub environment, a dedicated labeled Windows runner, runner-local case/reference files, a fresh reference, and explicit approval immediately before real Naver access.
   - Stop on CAPTCHA, login requirement, 403/429, or access restriction. Never bypass.
3. **P2 single-user production pilot**
   - Requires green CI, Docker smoke, live E2E, policy approval, backup ownership and explicit deployment approval.
   - Run one user, one URL, concurrency one, no more than once daily for 14 days, then produce a sanitized aggregate report.
4. **P3 legacy global listing lifecycle cleanup**
   - Only after a green release, the 14-day pilot and a verified backup.
   - Remove `ListingGroup.first_seen_at`, `last_seen_at`, `state`, and `missing_count` in a separately approved Alembic migration. `SourceListingState` remains authoritative.

## 5. Mandatory Continuation Constraints

- Required order: Docker smoke → protected live E2E → pilot → schema cleanup.
- Obtain separate user authorization before starting Docker services, accessing live Naver, deploying, backing up/restoring production data, or running a destructive migration.
- Keep local ports Portal `42880`, API `42881`, Chrome CDP `42973`; keep Docker CDP internal at `chrome:9222`.
- Do not use direct Naver APIs, direct HTTP acquisition, stealth, fingerprint modification, CAPTCHA solving, or proxy rotation.
- Do not commit secrets, full Naver URLs, broker personal data, live artifacts, profiles, cookies, or `temp/`.
- Update this document whenever a new implementation or verification milestone reaches `main`.
