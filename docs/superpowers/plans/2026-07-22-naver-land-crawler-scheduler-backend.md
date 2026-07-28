# 네이버 부동산 수집·스케줄링 백엔드 구현계획서

> **작업자 안내:** 이 문서는 실제 크롤러, 데이터베이스, 배치 스케줄러를 구현하기 위한 계획이다. 현재 React 데모 UX에는 실제 수집 기능을 연결하지 않는다.

**목표:** 사용자가 등록한 네이버 부동산 URL을 주기적으로 조사하고, 아파트·대표 매물·중개사 등록 상세를 날짜별로 저장하며 신규·변경·삭제 매물을 안정적으로 판별한다.

**권장 구조:** React는 FastAPI의 작업 API만 호출한다. FastAPI는 수집 작업을 Redis 큐에 넣고, Celery Worker가 Playwright 기반 수집기를 실행한다. PostgreSQL에는 원본 실행 기록, 정규화된 매물, 시점별 스냅샷과 변경 이벤트를 분리해 저장한다.

**기술 스택:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, Redis 7, Celery 5, Playwright Chromium, Pydantic 2, Docker Compose

## 공통 원칙

- 사용자가 직접 등록한 `https://fin.land.naver.com/` URL만 수집 대상으로 허용한다.
- 로그인 우회, 보안 장치 우회, 과도한 병렬 요청은 구현하지 않는다.
- 네이버 이용약관, robots 정책, 접근 제한을 운영 전 확인한다.
- 한 도메인 동시 실행은 기본 1개, 페이지 이동 간격은 1.5~3초 범위의 제한을 둔다.
- 수집 실패와 실제 매물 삭제를 구분한다.
- 개별 매물은 네이버 매물번호를 1차 식별자로 사용한다.
- 대표 매물 묶음과 중개사별 등록 원문을 별도 엔터티로 저장한다.
- 날짜와 시간은 DB에 UTC로 저장하고 API에서 `Asia/Seoul` 기준 ISO 8601로 반환한다.

---

## 1. 백엔드 프로젝트 기반

**생성 파일**

- `backend/pyproject.toml`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/database.py`
- `backend/app/api/router.py`
- `backend/alembic.ini`
- `backend/docker-compose.yml`

**구현 내용**

1. FastAPI 애플리케이션과 `/api/health` 엔드포인트를 생성한다.
2. 환경 변수는 `DATABASE_URL`, `REDIS_URL`, `CRAWLER_HEADLESS`, `CRAWL_CONCURRENCY`, `NAVER_REQUEST_DELAY_MIN`, `NAVER_REQUEST_DELAY_MAX`만 정의한다.
3. SQLAlchemy 비동기 세션과 Alembic 마이그레이션을 연결한다.
4. Docker Compose에 API, Worker, Scheduler, PostgreSQL, Redis 서비스를 정의한다.
5. API와 Worker가 동일한 설정 및 모델 패키지를 사용하도록 구성한다.

**완료 기준**

- API가 PostgreSQL 및 Redis 연결 상태를 구분하여 응답한다.
- API, Worker, Scheduler 프로세스를 각각 독립 실행할 수 있다.

## 2. 영속 데이터 모델

**생성 파일**

- `backend/app/models/tracked_source.py`
- `backend/app/models/crawl_run.py`
- `backend/app/models/apartment.py`
- `backend/app/models/listing.py`
- `backend/app/models/snapshot.py`
- `backend/app/models/schedule.py`
- `backend/app/models/change_event.py`
- `backend/alembic/versions/0001_initial_schema.py`

**테이블 정의**

| 테이블 | 핵심 필드 | 목적 |
|---|---|---|
| `tracked_sources` | `id`, `source_url`, `url_hash`, `created_at`, `is_active` | 사용자가 등록한 조사 URL |
| `crawl_runs` | `id`, `source_id`, `status`, `started_at`, `finished_at`, `error_code`, `raw_item_count` | 조사 실행 단위와 성공·실패 기록 |
| `apartments` | `id`, `naver_complex_id`, `name`, `address`, `metadata_json` | URL에서 발견한 아파트 |
| `listings` | `id`, `apartment_id`, `naver_article_id`, `representative_key`, `trade_type`, `first_seen_at`, `last_seen_at`, `state` | 매물의 지속 식별 정보 |
| `listing_snapshots` | `id`, `run_id`, `listing_id`, `price`, `deposit`, `monthly_rent`, `area`, `floor`, `direction`, `description_hash`, `captured_at` | 조사 시점별 매물 정보 |
| `broker_registrations` | `id`, `snapshot_id`, `article_id`, `realtor_name`, `provider`, `description`, `article_url` | 중개사별 등록 상세 |
| `crawl_schedules` | `id`, `source_id`, `cadence`, `time_of_day`, `timezone`, `enabled`, `next_run_at` | 반복 조사 설정 |
| `change_events` | `id`, `run_id`, `listing_id`, `event_type`, `before_json`, `after_json`, `detected_at` | 신규·변경·삭제 이벤트 |

**제약 조건**

- `tracked_sources.url_hash`는 유일해야 한다.
- `apartments.naver_complex_id`는 유일해야 한다.
- `listings(apartment_id, naver_article_id)`는 유일해야 한다.
- `listing_snapshots(run_id, listing_id)`는 유일해야 한다.
- 금액은 원 단위 `BIGINT`, 시간은 `TIMESTAMPTZ`를 사용한다.

## 3. URL 검증과 조사 작업 API

**생성 파일**

- `backend/app/schemas/analysis.py`
- `backend/app/services/source_service.py`
- `backend/app/api/routes/analyses.py`
- `backend/app/tasks/crawl_tasks.py`

**API**

| 메서드 | 경로 | 동작 |
|---|---|---|
| `POST` | `/api/analyses` | URL 검증 후 수집 작업 생성 |
| `GET` | `/api/analyses/{run_id}` | 실행 상태와 진행률 조회 |
| `GET` | `/api/analyses/{run_id}/result` | 완료된 아파트 및 요약 결과 조회 |
| `POST` | `/api/analyses/{run_id}/cancel` | 대기 중인 작업 취소 |

**처리 규칙**

1. URL 스킴은 HTTPS, 호스트는 `fin.land.naver.com`만 허용한다.
2. URL fragment를 제거하고 query parameter 순서를 정규화한 뒤 SHA-256 해시를 생성한다.
3. 동일 URL의 실행 중 작업이 있으면 기존 `run_id`를 반환한다.
4. 작업 상태는 `queued → running → completed | failed | cancelled` 순서로 관리한다.
5. 진행률은 `URL 확인`, `단지 발견`, `매물 목록`, `중개사 상세`, `변경 비교`, `저장 완료` 단계로 제공한다.

## 4. Playwright 수집기

**생성 파일**

- `backend/app/crawler/browser.py`
- `backend/app/crawler/navigation.py`
- `backend/app/crawler/parsers/apartment.py`
- `backend/app/crawler/parsers/listing.py`
- `backend/app/crawler/parsers/broker_registration.py`
- `backend/app/crawler/types.py`
- `backend/app/crawler/errors.py`

**수집 흐름**

1. URL을 Chromium에서 열고 지도 결과가 준비될 때까지 명시적 DOM 조건으로 대기한다.
2. 가상 스크롤 목록을 끝까지 순회하면서 중복 단지와 매물 ID를 제거한다.
3. 각 대표 매물의 `중개사 n곳에서 등록했어요` 컨트롤을 열고 중개사 등록 상세를 순회한다.
4. 단지 ID, 단지명, 주소, 거래 유형, 동, 층, 방향, 면적, 호가, 설명, 매물번호, 중개사, 제공처, 확인일, 원문 URL을 구조화한다.
5. DOM selector는 한 파일에 버전별로 모아 변경 시 parser 로직과 분리한다.
6. 브라우저 원문 HTML 또는 JSON 응답 전문은 장기 저장하지 않고, 오류 분석에 필요한 최소 메타데이터와 해시만 남긴다.

**실패 처리**

- CAPTCHA, 접근 차단, 로그인 요구는 `blocked` 오류로 종료하고 자동 우회를 시도하지 않는다.
- 일부 단지 실패 시 실행 상태를 `partial`로 기록하며 해당 단지는 삭제 판정에서 제외한다.
- 네트워크 타임아웃은 최대 2회만 지수 백오프로 재시도한다.
- selector 불일치는 별도 오류 코드로 기록해 화면 구조 변경을 식별한다.

## 5. 정규화와 대표 매물 그룹화

**생성 파일**

- `backend/app/domain/normalizer.py`
- `backend/app/domain/identity.py`
- `backend/app/domain/grouping.py`

**대표 매물 키**

```text
complex_id + trade_type + building + exclusive_area_rounded + price + floor_band
```

**규칙**

- 개별 중개사 등록은 `naver_article_id`로 식별한다.
- 동일 주택으로 판단되는 중개사 등록은 대표 매물 키 아래에 묶는다.
- 면적은 소수점 둘째 자리, 금액은 원 단위로 정규화한다.
- 층 정보가 정확하지 않으면 저층·중층·고층 구간을 별도 보조 키로 사용한다.
- 그룹화 결과에는 원본 매물번호 목록을 반드시 보존한다.

## 6. 신규·변경·삭제 판별

**생성 파일**

- `backend/app/domain/comparator.py`
- `backend/app/services/snapshot_service.py`
- `backend/app/services/change_event_service.py`

**판별 규칙**

- 이전 성공 실행에 없고 현재 실행에 있으면 `new`.
- 가격, 보증금, 월세, 설명, 동·층·방향 중 추적 필드가 달라지면 `changed`.
- 이전 성공 실행에 있고 현재 성공 실행에 없으면 우선 `missing`.
- 같은 매물이 연속 2회의 완전 성공 실행에서 보이지 않으면 `removed`로 확정한다.
- 부분 실패 실행은 `missing` 횟수에 포함하지 않는다.
- 다시 나타난 매물은 `restored` 이벤트를 생성하고 기존 `listing_id`를 재사용한다.

**UI 전달 값**

```json
{
  "status": "changed",
  "detectedAt": "2026-07-22T09:48:00+09:00",
  "changedFields": ["price"],
  "before": { "price": 720000000 },
  "after": { "price": 698000000 }
}
```

## 7. 스케줄러와 중복 실행 방지

**생성 파일**

- `backend/app/api/routes/schedules.py`
- `backend/app/services/schedule_service.py`
- `backend/app/tasks/scheduled_tasks.py`
- `backend/app/core/locks.py`

**API**

| 메서드 | 경로 | 동작 |
|---|---|---|
| `POST` | `/api/schedules` | URL별 스케줄 생성 |
| `PATCH` | `/api/schedules/{id}` | 주기, 시각, 활성화 상태 변경 |
| `DELETE` | `/api/schedules/{id}` | 스케줄 비활성화 및 삭제 |
| `GET` | `/api/schedules` | 현재 스케줄과 다음 실행 시각 조회 |
| `GET` | `/api/schedules/{id}/runs` | 최근 실행 내역 조회 |

**실행 규칙**

- Celery Beat는 매분 실행 대상 스케줄을 조회한다.
- Redis 분산 락 키는 `crawl:source:{source_id}`를 사용한다.
- 동일 URL은 한 번에 하나의 실행만 허용한다.
- 실행 완료 후 DB 트랜잭션 안에서 `next_run_at`을 계산한다.
- 기본 시간대는 `Asia/Seoul`이며 일광절약시간 변경에도 안전한 timezone 객체를 사용한다.

## 8. 조회 API와 React 연결

**백엔드 생성 파일**

- `backend/app/api/routes/dashboard.py`
- `backend/app/api/routes/apartments.py`
- `backend/app/api/routes/listings.py`
- `backend/app/api/routes/exports.py`

**프런트엔드 수정 파일**

- `frontend/src/api/client.ts`
- `frontend/src/api/analyses.ts`
- `frontend/src/api/apartments.ts`
- `frontend/src/api/schedules.ts`
- `frontend/src/state/DemoAnalysisContext.tsx`

**조회 API**

- `GET /api/dashboard?sourceId=`: 아파트 수와 단지별 거래 유형 평균 호가·매물 수
- `GET /api/apartments?sourceId=&query=&page=`: 조사 아파트 목록
- `GET /api/apartments/{id}?runId=`: 단지 기본 정보와 선택 회차 요약
- `GET /api/apartments/{id}/history`: 날짜별 매물 수와 변화량
- `GET /api/apartments/{id}/listings?runId=&tradeType=&status=`: 회차별 매물 목록
- `GET /api/listings/{id}`: 매물 및 중개사 등록 상세
- `GET /api/exports/{sourceId}.xlsx`: 서버에서 생성한 전체 조사 결과 파일

**연결 순서**

1. React 타입을 OpenAPI 스키마에서 생성한다.
2. Demo Context를 API Query 상태로 교체한다.
3. URL 조사 완료 전후의 현재 라우팅과 화면 구조를 유지한다.
4. 페이지별 loading, empty, partial failure, blocked 상태를 추가한다.
5. Excel 다운로드를 서버 스트리밍 방식으로 교체한다.

## 9. 최소 검증 범위

- URL 정규화 및 허용 호스트 검증 단위 테스트
- 저장된 HTML fixture 한 종류로 parser 계약 테스트
- 두 스냅샷 비교 시 `new`, `changed`, `missing`, `removed`, `restored` 판별 테스트
- 부분 실패 실행에서 삭제 이벤트가 생성되지 않는 테스트
- 동일 URL 중복 실행 방지 테스트
- 스케줄 `next_run_at` 계산 테스트
- API에서 아파트 상세, 날짜별 이력, Excel 응답을 확인하는 통합 테스트

## 10. 구현 순서와 배포 기준

1. 기반 프로젝트와 DB 스키마
2. 수동 실행 API와 단일 URL 수집기
3. 정규화 및 대표 매물 그룹화
4. 스냅샷 저장과 변경 판별
5. 대시보드·아파트·매물 조회 API
6. React 데모 데이터를 실제 API로 교체
7. 스케줄러와 분산 락
8. Excel 서버 내보내기
9. 접근 제한·부분 실패·재시도 운영 처리

운영 전에는 사용자 한 명, URL 한 개, 하루 1회 스케줄로 제한된 파일럿을 실행한다. 차단률, 평균 실행 시간, 단지별 수집 누락률, 잘못된 삭제 판정률을 확인한 뒤 URL 수와 실행 빈도를 단계적으로 확대한다.

---

# AI Execution Contract (English)

## Objective

Implement a production backend that crawls user-supplied Naver Land URLs, stores apartment/listing/broker snapshots, detects listing changes across successful runs, and schedules recurring crawls.

## Required Boundaries

- Frontend: existing React/Vite application.
- API: FastAPI with Pydantic v2 schemas.
- Persistence: PostgreSQL with SQLAlchemy 2 and Alembic.
- Queue and scheduling: Redis, Celery Worker, Celery Beat.
- Browser collection: Playwright Chromium with explicit DOM waits and strict rate limiting.
- Time: persist UTC, serialize Asia/Seoul ISO 8601.
- Do not bypass login, CAPTCHA, access controls, or anti-bot systems.

## Core State Machine

```text
queued -> running -> completed | partial | failed | blocked | cancelled
```

## Listing State Machine

```text
new -> active -> changed -> active
active -> missing -> removed
missing -> restored
removed -> restored
```

`removed` requires absence from two consecutive fully successful runs. A partial run never advances the missing counter.

## Delivery Order

1. Bootstrap backend, database, queue, and migrations.
2. Implement URL validation and crawl-run APIs.
3. Implement Playwright navigation and parsers using stored fixtures.
4. Normalize identities and persist snapshots transactionally.
5. Implement deterministic comparison and change events.
6. Add dashboard, apartment, listing, history, and export APIs.
7. Replace demo React state with generated OpenAPI clients.
8. Add schedules, distributed locks, run history, and operational limits.

## Acceptance Criteria

- A valid source URL creates one crawl run and returns progress.
- Apartments, representative listings, and broker registrations are persisted separately.
- Every snapshot records an exact capture timestamp.
- Dashboard responses contain only apartment count and per-complex sale/jeonse/monthly average asking price and count.
- Apartment detail responses expose chronological counts and per-listing statuses.
- New, changed, missing, removed, and restored events are deterministic and auditable.
- Concurrent runs for the same source URL are rejected or deduplicated.
- XLSX export contains apartment summary, listings, broker registrations, and crawl history sheets.
