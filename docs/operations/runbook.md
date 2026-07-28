# 네이버 부동산 조사 서비스 운영 런북

## 한국어 운영 가이드

### 1. 문서 목적과 운영 경계

이 문서는 단일 운영자가 등록 URL 1개를 하루 1회 조사하는 초기 파일럿을 안전하게 운영하기 위한 절차다. 첫 2주 동안은 다음 제한을 유지한다.

- 운영 사용자: 1명
- 활성 등록 URL: 최대 1개
- 예약 조사: 하루 최대 1회
- 도메인 동시 브라우저: 1개 (`CRAWL_CONCURRENCY=1`)
- CAPTCHA, 로그인 요구, 접근 제한 또는 robots 정책을 우회하지 않는다.
- 이용약관·robots 정책·수집 데이터 사용 범위의 검토와 승인 기록이 없으면 worker와 scheduler를 시작하지 않는다.

이 저장소의 배포 파일은 준비물일 뿐이다. 빌드, 기동, 마이그레이션, 복구 및 실제 브라우저 인수 확인은 각각 운영 승인 후 실행한다.

### 실행 방식 선택

- Docker 없이 실행할 때는 `APP_RUNTIME=local`과 SQLite를 사용하는 `./scripts/start.ps1 -Mode local`을 실행한다. 상세 준비 절차는 `docs/setup/local-setup.md`를 따른다.
- Docker로 실행할 때는 `APP_RUNTIME=docker`와 PostgreSQL·Redis·Celery를 사용하는 `./scripts/start.ps1 -Mode docker`를 실행한다. 상세 준비 절차는 `docs/setup/docker-setup.md`를 따른다.
- 두 방식 모두 포탈은 `http://127.0.0.1:42880`, API는 `http://127.0.0.1:42881`을 사용한다. 컨테이너 내부 포트 `80`, `8000`은 변경하지 않는다.

### 2. 서비스 구성

| 서비스 | 역할 | 외부 공개 원칙 |
|---|---|---|
| `frontend` | Nginx 정적 파일 제공, SPA fallback, `/api` 프록시 | 기본값은 `127.0.0.1:42880`; 승인된 TLS 프록시를 앞에 둔다. |
| `api` | FastAPI API | 기본값은 `127.0.0.1:42881`; 인터넷에 직접 공개하지 않는다. |
| `worker` | Celery 조사 작업과 Playwright Chromium 실행 | 외부 포트를 열지 않는다. |
| `scheduler` | 매분 예약 대상을 확인하는 Celery Beat | 외부 포트를 열지 않는다. |
| `postgres` | 영속 데이터와 조사 이력 저장 | Compose 내부 네트워크에서만 접근한다. |
| `redis` | Celery broker/backend와 source lock | Compose 내부 네트워크에서만 접근한다. |
| `migrate` | `alembic upgrade head`를 1회 실행 | 정상 종료해야 API·worker·scheduler가 시작된다. |

### 3. 배포 전 승인 체크리스트

아래 항목의 검토자, 검토 일시, 근거 문서 버전을 운영 기록에 남긴다.

- 네이버 이용약관이 이 사용 목적과 접근 방식에 허용되는지 확인했다.
- robots 정책과 자동 접근 제한을 확인했다.
- 수집 대상 필드, 보관 기간, XLSX 제공 범위를 승인했다.
- 공개 중개 정보 안의 전화번호와 상세 설명 처리 근거를 확인했다.
- 차단 신호가 발생할 때 자동 재시도하거나 우회하지 않는다는 점을 승인했다.
- 단일 URL, 하루 1회, 동시 브라우저 1개의 파일럿 제한을 승인했다.
- 백업 위치, 암호화, 보관 기간과 복구 책임자를 지정했다.

하나라도 미완료이면 API와 frontend만 검토 용도로 둘 수 있지만 worker와 scheduler는 시작하지 않는다.

### 4. 환경 설정

`backend/.env.example`을 기준으로 운영 서버에 `backend/.env`를 만들고 비밀 저장소에서 값을 주입한다. `backend/.env`는 형상 관리에 추가하지 않는다.

필수 애플리케이션 변수는 다음과 같다.

| 변수 | 운영 규칙 |
|---|---|
| `APP_RUNTIME` | Docker Compose에서는 `docker`, Docker 없는 SQLite 실행에서는 `local`을 사용한다. |
| `DATABASE_URL` | Compose 서비스명 `postgres`를 사용한다. PostgreSQL 사용자·DB·비밀번호와 일치해야 한다. |
| `REDIS_URL` | Compose 서비스명 `redis`를 사용한다. 외부 Redis 주소를 사용하지 않는다. |
| `CRAWLER_CDP_URL` | local은 `http://127.0.0.1:42973`, Docker는 `http://chrome:9222`만 허용한다. |
| `CRAWL_CONCURRENCY` | 파일럿 동안 `1`로 고정한다. |
| `NAVER_REQUEST_DELAY_MIN` | 실행별 프리셋이 없을 때 사용하는 fallback 최소값이며 기본 `1.0`초다. |
| `NAVER_REQUEST_DELAY_MAX` | 실행별 프리셋이 없을 때 사용하는 fallback 최대값이며 기본 `2.5`초다. |
| `CORS_ORIGINS` | 승인된 frontend origin만 쉼표로 구분한다. |
| `TIMEZONE` | `Asia/Seoul`을 사용한다. DB 시각은 UTC로 저장한다. |

Compose 치환 변수 `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`를 변경하면 `DATABASE_URL`의 자격 증명과 DB 이름도 반드시 동일하게 변경한다. 비밀번호 안의 예약 문자는 URL 인코딩한다. `IMAGE_TAG`, `API_BIND_ADDRESS`, `API_PORT`, `FRONTEND_BIND_ADDRESS`, `FRONTEND_PORT`는 필요할 때만 배포 환경에서 지정한다.

기본 bind address는 loopback이다. 외부 공개가 필요하면 컨테이너 포트를 직접 공개하는 대신 승인된 TLS reverse proxy를 사용한다.

### 5. 승인 후 배포 순서

다음 명령은 절차 예시이며, 승인 전에는 실행하지 않는다.

```powershell
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d
```

`up`은 먼저 PostgreSQL과 Redis healthcheck를 기다리고, 일회성 `migrate` 서비스에서 현재 Alembic head까지 적용한다. migration이 실패하면 API, worker, scheduler는 시작되지 않는다. 운영 중 schema 변경이 포함된 새 이미지를 올릴 때는 반드시 먼저 백업하고 migration의 하위 호환 여부를 검토한다.

기동 후 운영자가 확인할 대상은 다음과 같다.

```powershell
docker compose -f docker-compose.production.yml ps
Invoke-WebRequest http://127.0.0.1:42881/api/health
Invoke-WebRequest http://127.0.0.1:42880/healthz
```

전체 stack build, 실제 기동, 브라우저 조사 및 인수 확인은 별도 승인 단계다.

### 6. 구조화 로그 규칙

조사 실행 로그는 JSON 한 줄 형식이다. `event` 메타데이터와 다음 허용 필드 외의 실행 컨텍스트를 추가하지 않는다.

| 필드 | 의미 |
|---|---|
| `runId` | 조사 실행 UUID |
| `sourceId` | 등록 source UUID |
| `stage` | `url`, `complex`, `listings`, `brokers`, `details`, `compare`, `save` 중 하나 |
| `count` | 해당 이벤트의 수집 또는 경고 건수 |
| `error` | 안정된 오류 코드이며 예외 메시지가 아니다. |
| `duration` | 실행 시작 이후 밀리초 |

안전한 예시는 다음과 같다.

```json
{"event":"crawl_finished","runId":"2f7399bc-c947-4af5-b44a-8c5298335380","sourceId":"8a179aa5-b076-44b0-bc89-1d53245ce9c1","stage":"save","count":42,"duration":18452}
```

다음 값은 로그, tracing attribute, 오류 메시지, metric label에 넣지 않는다.

- query를 포함한 전체 URL 또는 request target
- 전화번호, 중개사 연락처
- 매물 상세 설명 원문
- HTML 원문, request/response body, ORM 객체 dump
- 자격 증명, cookie, authorization header

Uvicorn access log와 frontend Nginx access log는 비활성화되어 있다. 외부 reverse proxy를 추가할 때도 `$request_uri`, `$args`, query string을 기록하지 말고 query가 제거된 path와 status 같은 최소 정보만 사용한다.

### 7. 운영 지표와 2주 파일럿 판정

다음 오류 코드를 각각 별도 집계한다.

- selector 불일치: `selector_mismatch`
- 접근 차단: `access_blocked`, `login_required`, `captcha_detected`
- 중개사 카드 누락: `broker_count_mismatch`
- 화면 매물 수 불일치: `listing_count_mismatch`
- 기타 상세 수집 누락: `detail_collection_failed`

화면 표시 건수와 실제 수집 건수가 다르면 결과는 `partial`이어야 한다. `partial`, `failed`, `blocked` 실행은 매물의 `missing_count`를 증가시키거나 삭제 판정에 사용하지 않는다.

파일럿 기간에는 매일 다음 집계를 남기되 식별자나 원문 데이터는 운영 보고서에 복사하지 않는다.

- 시작 실행 수와 `completed`, `partial`, `failed`, `blocked` 실행 수
- 차단률: 차단 상태 실행 수 / 전체 시작 실행 수
- 누락 경고율: `broker_count_mismatch` 또는 `listing_count_mismatch`가 발생한 실행 수 / 전체 종료 실행 수
- selector 불일치 건수
- 삭제 판정 검토 건수와 수동 확인된 잘못된 삭제 판정 건수
- p50/p95 `duration`

2주가 끝나도 자동으로 범위를 확대하지 않는다. 차단률, 누락률, 잘못된 삭제 판정률을 검토하고 이용정책 담당자와 운영 책임자가 명시적으로 승인해야 URL 수, 빈도 또는 동시성을 늘릴 수 있다.

### 8. 장애 대응

#### 접근 차단, 로그인 요구, CAPTCHA

1. scheduler를 중지해 추가 예약을 막는다.
2. 실행 상태가 `blocked`이고 오류 코드가 기록되었는지 확인한다.
3. 재시도 횟수를 늘리거나 우회 도구를 사용하지 않는다.
4. 이용정책과 접근 빈도를 다시 검토한 후 재개 승인을 받는다.

#### selector 불일치

1. scheduler를 중지한다.
2. selector 버전과 발생 stage만 기록한다. 페이지 HTML이나 상세 설명을 로그에 복사하지 않는다.
3. 승인된 개발 환경에서 selector 변경을 별도 작업으로 처리한다.
4. fixture 검토와 사용자 승인 후에만 새 이미지를 배포한다.

#### `partial` 또는 카드 누락

1. 해당 결과를 완전한 조사로 간주하지 않는다.
2. UI의 표시 건수와 수집 건수를 수동 비교한다.
3. 삭제 이벤트가 생성되지 않았는지 확인한다.
4. 원인이 해소되기 전 자동 반복 실행을 추가하지 않는다.

#### PostgreSQL 또는 Redis 장애

1. 새 조사와 scheduler를 중지한다.
2. `docker compose ... ps`의 health 상태와 해당 서비스의 최소 오류 로그만 확인한다.
3. PostgreSQL 장애에서는 아래 복구 절차를 따른다.
4. Redis 데이터는 조사 원본 저장소가 아니다. PostgreSQL을 기준으로 작업 상태를 확인한 뒤 queue를 재개한다.

### 9. PostgreSQL 백업

백업 전에 scheduler를 중지하고 실행 중인 worker 작업이 끝났는지 확인한다. 그 다음 API와 worker의 쓰기를 중지한다. 백업 파일은 운영 서버의 암호화된 전용 디렉터리에 저장하며 외부 공유 폴더에 두지 않는다.

승인 후 실행하는 예시는 다음과 같다.

```powershell
docker compose -f docker-compose.production.yml stop scheduler worker api
docker compose -f docker-compose.production.yml exec -T postgres pg_dump -U postgres -d wisdom_auction --format=custom --file=/tmp/wisdom_auction.dump
docker compose -f docker-compose.production.yml cp postgres:/tmp/wisdom_auction.dump .\backups\wisdom_auction.dump
docker compose -f docker-compose.production.yml start api worker scheduler
```

운영 설정에서 사용자나 DB 이름을 변경했다면 명령의 값도 바꾼다. 백업 결과에는 source URL, 연락처, 상세 설명이 포함될 수 있으므로 운영 DB와 같은 등급으로 암호화하고 접근을 제한한다. 백업 성공 여부와 파일 크기, 생성 시각, 담당자만 기록하고 데이터 내용을 로그에 출력하지 않는다.

### 10. PostgreSQL 복구

복구는 기존 DB 내용을 교체하는 파괴적 작업이다. 복구 대상, 백업 파일 checksum, 복구 시점, 중단 시간과 승인자를 확인하고 현재 DB의 추가 백업을 만든 뒤 진행한다.

1. scheduler, worker, API를 중지한다.
2. 승인된 dump를 PostgreSQL 컨테이너의 임시 경로로 복사한다.
3. 기존 DB를 교체하고 dump를 복구한다.
4. `migrate`를 실행해 현재 Alembic head와 맞춘다.
5. API만 먼저 시작해 health를 확인한 뒤 worker와 scheduler를 재개한다.

승인 후 실행하는 예시는 다음과 같다.

```powershell
docker compose -f docker-compose.production.yml stop scheduler worker api
docker compose -f docker-compose.production.yml cp .\backups\wisdom_auction.dump postgres:/tmp/restore.dump
docker compose -f docker-compose.production.yml exec -T postgres dropdb -U postgres --if-exists wisdom_auction
docker compose -f docker-compose.production.yml exec -T postgres createdb -U postgres wisdom_auction
docker compose -f docker-compose.production.yml exec -T postgres pg_restore -U postgres -d wisdom_auction --clean --if-exists /tmp/restore.dump
docker compose -f docker-compose.production.yml run --rm migrate
docker compose -f docker-compose.production.yml start api worker scheduler
```

복구 확인이 끝날 때까지 원본 백업을 삭제하지 않는다. migration downgrade를 자동 rollback 수단으로 사용하지 않는다. application rollback이 schema와 호환되지 않으면 검증된 DB 백업 복구를 우선한다.

### 11. 종료와 롤백

- 정상 중지는 scheduler, worker, API, frontend 순서로 수행하고 PostgreSQL과 Redis는 마지막에 중지한다.
- 새 application image에 문제가 있고 DB schema가 하위 호환이면 이전 `IMAGE_TAG`로 되돌린다.
- schema가 하위 호환이 아니면 이전 이미지만 기동하지 말고 승인된 백업 복구 절차를 사용한다.
- `docker compose down -v`는 영속 데이터를 제거하므로 운영 절차에서 사용하지 않는다.

### 12. Chrome readiness와 장애 복구

- `APP_RUNTIME`만 런타임을 선택한다. local은 `http://127.0.0.1:42973`, Docker는 `http://chrome:9222` 외의 CDP 주소를 허용하지 않는다.
- `/api/health`의 `browser=unavailable`과 `status=degraded`를 먼저 확인한다. API는 브라우저 장애 중에도 상태 응답을 제공한다.
- `browser_unavailable`이면 새 즉시 분석은 생성되지 않고, 예약 실행은 실패 이력을 남긴 뒤 다음 예정 시각으로 이동한다.
- `browser_disconnected`이면 해당 실행은 terminal 실패다. 자동 resume, retry, requeue를 하지 않는다.
- local은 전용 Chrome만 재시작하고 `scripts/status.ps1`로 readiness를 확인한다. Docker는 별도 승인 후 `chrome` 서비스 상태와 `/json/version`을 확인한다.
- 전용 프로필과 `chrome_profile` 볼륨에는 cookie와 세션이 포함될 수 있다. 장애 대응 중 자동 삭제·초기화·복원하지 않으며 별도 승인을 요구한다.
- Chrome 이미지는 기본적으로 빌드 시점의 공식 Stable을 사용한다. 정확한 재현이 필요한 경우에만 공식 저장소에 존재하는 `GOOGLE_CHROME_VERSION`과 `CHROME_IMAGE_TAG`를 함께 지정하고, 승인된 정적 구성 확인 → 이미지 빌드 → `/json/version` → `about:blank` 순서로 확인한다.

---

# AI Operations Contract (English)

## Scope

Operate a two-week, single-user pilot with one active source URL, at most one scheduled crawl per day, and one browser process for the Naver domain. Do not expand any limit automatically.

## Approval Gate

Do not build, start, migrate, restore, or run a browser acceptance crawl until the operator explicitly approves that action. The legal/policy review must record the reviewer, date, evidence version, allowed fields, retention, and export purpose. Never bypass login, CAPTCHA, robots rules, access blocks, or anti-bot controls.

## Runtime Topology

```yaml
runtime_services:
  - api
  - worker
  - scheduler
  - postgres
  - redis
  - frontend
  - chrome
startup_gate:
  service: migrate
  command: alembic upgrade head
external_ports:
  frontend: 127.0.0.1:42880
  api: 127.0.0.1:42881
  postgres: none
  redis: none
  chrome_cdp: none
```

The non-root Chrome/Xvfb sidecar exposes CDP `9222` only to the internal Compose control network and persists its dedicated profile in `chrome_profile`. The worker waits for Chrome health; API startup does not, so health remains available during browser outages. The frontend proxies `/api` to the API service.

## Environment Contract

Use `backend/.env` for `APP_RUNTIME`, `DATABASE_URL`, `REDIS_URL`, `CRAWLER_CDP_URL`, `CRAWL_CONCURRENCY`, `NAVER_REQUEST_DELAY_MIN`, `NAVER_REQUEST_DELAY_MAX`, `CORS_ORIGINS`, and `TIMEZONE`. `APP_RUNTIME` is the sole runtime selector: local permits only `http://127.0.0.1:42973`, Docker only `http://chrome:9222`. Keep crawl concurrency one.

## Browser Recovery Contract

`browser_unavailable` prevents immediate run persistence and records a failed scheduled history. `browser_disconnected` is terminal and must not auto-resume, retry, or requeue. Treat both local and Docker dedicated profiles as sensitive session storage. Never reset, delete, restore, or export them without separate approval. Never add sandbox bypasses, host CDP publication, stealth, fingerprint spoofing, proxy rotation, or CAPTCHA bypass.

## Logging Contract

Run events are one-line JSON objects. Apart from the stable `event` metadata, the only permitted context keys are:

```yaml
allowed_context:
  runId: uuid
  sourceId: uuid
  stage: [url, complex, listings, brokers, details, compare, save]
  count: non_negative_integer
  error: stable_error_code
  duration: non_negative_milliseconds
forbidden_everywhere:
  - full URL or request target containing query data
  - phone number or contact data
  - original listing description
  - raw HTML or request/response body
  - cookies, authorization headers, credentials, ORM or payload dumps
```

Never log exception text from a crawl. Count `selector_mismatch`, access-block codes, `broker_count_mismatch`, and `listing_count_mismatch` separately. Uvicorn and Nginx access logs remain disabled. Any upstream proxy must log a query-free path, never `$request_uri` or `$args`.

## State Safety

- A visible/listed count mismatch must produce `partial`.
- `partial`, `failed`, and `blocked` runs must never advance listing absence counters.
- Stop scheduling on `access_blocked`, `login_required`, `captcha_detected`, or `selector_mismatch`.
- Do not add retries or bypasses while responding to a block.

## Backup and Restore Contract

Before a backup, stop the scheduler, let active work finish, and stop API/worker writes. Use `pg_dump --format=custom`; encrypt the artifact and treat it as production data. Before a restore, require explicit destructive-action approval, preserve a fresh backup, verify the selected dump checksum, stop all writers, replace the target database, run `alembic upgrade head`, start API first, and resume worker/scheduler only after health review. Never use an automatic Alembic downgrade as the primary rollback strategy.

## Pilot Exit Gate

After 14 days, report aggregate run outcomes, block rate, missing-count warning rate, selector mismatches, manually confirmed false-removal decisions, and p50/p95 duration. Do not include source URLs, phone numbers, listing descriptions, or record-level personal data in the report. Expansion requires explicit operations and policy approval.
