# 네이버 부동산 조사 포탈 실제 연동 구현 계획

> **에이전트 작업자용:** 구현 시 `superpowers:subagent-driven-development` 또는 `superpowers:executing-plans`를 사용해 체크박스 단위로 진행한다. 이 저장소의 사용자 지침에 따라 테스트·빌드·브라우저 확인·커밋·배포는 반드시 사용자 승인을 받은 뒤 실행한다.

**목표:** 현재 승인된 React/Tailwind 데모 UX를 변경하지 않고, Python 기반 수집기·API·데이터베이스·스케줄러를 연결하여 조사 결과가 영구 저장되고 재접속 시 대시보드와 조사 아파트 페이지에 자동으로 표시되는 웹서비스를 구현한다.

**아키텍처:** React는 FastAPI만 호출하고 네이버 부동산에 직접 접속하지 않는다. FastAPI가 조사 작업을 Redis 큐에 등록하면 Celery Worker가 Playwright Chromium으로 사용자가 입력한 아파트 URL 하나를 수집하고, PostgreSQL에 실행·매물·중개사별 상세·날짜별 스냅샷·변경 이벤트를 저장한다. 정제와 중복 제거는 백엔드의 단일 도메인 로직으로 처리하여 화면과 XLSX가 같은 값을 사용한다.

**기술 스택:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16, Redis 7, Celery 5, Playwright Chromium, openpyxl, React 19, TypeScript, Tailwind CSS, React Router, TanStack Query, Docker Compose

## 전체 제약

- 현재 `frontend/`의 화면 구조, 메뉴, 라우트, 카드·리스트·테이블 보기 방식은 데모 UX 기준으로 유지한다.
- 목업 데이터는 실제 API 연결이 완료될 때까지 개발용 fallback으로만 보존한다.
- 사용자가 입력하는 네이버 URL 하나는 반드시 아파트 단지 하나로 확정되어야 한다.
- `https://fin.land.naver.com/` 이외의 호스트는 조사 대상으로 허용하지 않는다.
- `Npay 부동산에서 보기`가 존재하면 해당 내부 링크만 사용하며 `/out-link-bridge` 외부 링크는 절대 열지 않는다.
- 로그인·CAPTCHA·접근 차단·안티봇 정책을 우회하지 않는다.
- 동일 출처 URL의 동시 수집 수는 1개로 제한하고 화면 이동 사이에 1.5~3초 지연을 둔다.
- 수집 실패와 실제 매물 삭제를 구분한다. 부분 실패 실행은 삭제 판정에 사용하지 않는다.
- DB 시간은 UTC로 저장하고 API는 `Asia/Seoul` ISO 8601 문자열로 반환한다.
- 원본 HTML 전문은 장기 저장하지 않는다. 구조화된 필드, 오류 코드, selector 버전과 내용 해시만 저장한다.
- 1차 운영 범위는 단일 운영 사용자다. 회원가입, 결제, 조직 권한은 별도 범위다.
- 테스트·빌드·개발 서버·브라우저 검증·커밋·배포 명령은 계획에 기록하지만 사용자 승인 전 실행하지 않는다.

---

## 1. 현재 상태와 구현 완료 조건

### 현재 완료된 데모

- `/`: 네이버 URL 입력 및 분석 진행 시뮬레이션
- `/dashboard`: 선택 아파트별 거래유형 평균 호가와 물건 수
- `/apartments`: 조사 아파트 테이블과 XLSX 버튼
- `/apartments/:complexId`: 날짜별 이력, 변경 비교, 카드·리스트·테이블 보기
- `/apartments/:complexId/listings/:listingId`: 중개사별 상세, 금융·세금·교통 정보
- `/schedules`: 조사 스케줄 UX
- 상세 옵션 취합 및 중복 제거 데모 로직

### 실제 서비스 완료 조건

1. 새로고침 또는 재접속 후에도 기존 조사 아파트가 대시보드와 조사 아파트 페이지에 나타난다.
2. URL 분석을 요청하면 실제 작업 ID와 진행 상태가 화면에 표시된다.
3. 대표 매물과 중개사별 개별 매물번호가 분리 저장된다.
4. Npay 매물은 내부 상세 슬라이드를 통해서만 조사된다.
5. 중개사 상세 슬라이드의 구조화 가능한 모든 필드가 저장된다.
6. 옵션·입주일·관리비·융자 정보가 서버에서 정규화되고 중복 제거된다.
7. 날짜별 신규·변경·누락·삭제·재등장 상태를 재현할 수 있다.
8. 사용자가 설정한 주기에 따라 같은 URL을 중복 실행 없이 조사한다.
9. 화면과 XLSX가 동일한 저장 데이터와 동일한 정제 결과를 사용한다.

## 2. 전체 데이터 흐름

```text
React/Tailwind Portal
        |
        | HTTPS JSON / XLSX
        v
FastAPI --------------------------> PostgreSQL
        |                              ^
        | enqueue / progress           | transactional save
        v                              |
Redis + Celery Worker ---> Playwright Crawler ---> Naver Pay Real Estate
        ^
        |
Celery Beat Scheduler
```

## 3. 계획된 파일 구조

```text
backend/
  pyproject.toml
  alembic.ini
  docker-compose.yml
  .env.example
  app/
    main.py
    core/
      config.py
      database.py
      locks.py
      logging.py
    api/
      router.py
      routes/
        analyses.py
        dashboard.py
        apartments.py
        listings.py
        schedules.py
        exports.py
    crawler/
      browser.py
      navigation.py
      selectors.py
      types.py
      errors.py
      parsers/
        complex.py
        listing_group.py
        broker_article.py
        market_details.py
    domain/
      url_identity.py
      listing_identity.py
      normalizer.py
      aggregator.py
      comparator.py
    models/
      tracked_source.py
      crawl_run.py
      apartment.py
      listing.py
      broker_article.py
      snapshot.py
      schedule.py
      change_event.py
    schemas/
      analysis.py
      dashboard.py
      apartment.py
      listing.py
      schedule.py
    services/
      analysis_service.py
      persistence_service.py
      query_service.py
      schedule_service.py
      export_service.py
    tasks/
      crawl_tasks.py
      scheduled_tasks.py
  tests/
    fixtures/
    unit/
    integration/

frontend/src/
  api/
    client.ts
    analyses.ts
    apartments.ts
    schedules.ts
    exports.ts
  state/
    AnalysisProvider.tsx
  types/
    api.ts
  components/analysis/
    AnalysisErrorState.tsx
  mocks/
    demoRealEstate.ts
```

---

### 작업 1: Python 백엔드 기반과 로컬 실행 환경

**파일**

- 생성: `backend/pyproject.toml`
- 생성: `backend/.env.example`
- 생성: `backend/docker-compose.yml`
- 생성: `backend/app/main.py`
- 생성: `backend/app/core/config.py`
- 생성: `backend/app/core/database.py`
- 생성: `backend/app/api/router.py`
- 생성: `backend/tests/integration/test_health.py`

**인터페이스**

- 제공: `create_app() -> FastAPI`
- 제공: `GET /api/health`
- 환경 변수: `DATABASE_URL`, `REDIS_URL`, `CRAWLER_HEADLESS`, `CRAWL_CONCURRENCY`, `NAVER_REQUEST_DELAY_MIN`, `NAVER_REQUEST_DELAY_MAX`, `CORS_ORIGINS`

- [ ] `pyproject.toml`에 FastAPI, Uvicorn, Pydantic Settings, SQLAlchemy asyncpg, Alembic, Celery Redis, Playwright, openpyxl, pytest를 고정 버전 범위로 선언한다.
- [ ] `Settings`를 생성하고 `CRAWL_CONCURRENCY=1`, 지연 최소 `1.5`, 최대 `3.0`, 시간대 `Asia/Seoul`을 기본값으로 둔다.
- [ ] `/api/health`가 API, PostgreSQL, Redis 연결 상태를 각각 반환하도록 작성한다.

```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected"
}
```

- [ ] Docker Compose에 `api`, `worker`, `scheduler`, `postgres`, `redis` 서비스를 정의한다.
- [ ] 사용자 승인 후 최소 검증을 실행한다.

```powershell
cd backend
pytest tests/integration/test_health.py -q
```

예상 결과: PostgreSQL과 Redis가 준비된 환경에서 `1 passed`.

---

### 작업 2: 영속 데이터 모델과 마이그레이션

**파일**

- 생성: `backend/app/models/*.py`
- 생성: `backend/alembic/versions/0001_initial_schema.py`
- 생성: `backend/tests/unit/test_model_constraints.py`

**핵심 테이블**

| 테이블 | 핵심 필드 | 역할 |
|---|---|---|
| `tracked_sources` | `id`, `source_url`, `normalized_url`, `url_hash`, `naver_complex_id`, `created_at`, `is_active` | 사용자가 등록한 단일 아파트 URL |
| `crawl_runs` | `id`, `source_id`, `status`, `stage`, `progress`, `started_at`, `finished_at`, `error_code`, `selector_version` | 조사 실행과 진행 상태 |
| `apartments` | `id`, `naver_complex_id`, `name`, `address`, `created_at`, `updated_at` | 아파트 단지 식별자 |
| `apartment_snapshots` | `id`, `run_id`, `apartment_id`, `details_json`, `captured_at` | 세대수·주차·난방 등 날짜별 단지 정보 |
| `listing_groups` | `id`, `apartment_id`, `identity_key`, `first_seen_at`, `last_seen_at`, `state`, `missing_count` | 동일 실물 매물의 지속 식별 |
| `listing_snapshots` | `id`, `run_id`, `listing_group_id`, `trade_type`, `price`, `deposit`, `monthly_rent`, `building`, `floor`, `direction`, `supply_area`, `exclusive_area`, `status`, `captured_at` | 대표 매물의 시점별 값 |
| `broker_articles` | `id`, `listing_group_id`, `naver_article_id`, `provider`, `is_npay`, `article_url`, `first_seen_at`, `last_seen_at` | 중개사별 개별 등록 식별 |
| `broker_article_snapshots` | `id`, `run_id`, `broker_article_id`, `details_json`, `description_hash`, `verified_at`, `captured_at` | 상세 슬라이드의 모든 구조화 필드 |
| `listing_aggregates` | `id`, `listing_snapshot_id`, `option_tags_json`, `move_in_summary`, `management_fee_summary`, `room_bath_summary`, `loan_summary`, `warnings_json` | 중복 제거된 추가정보 |
| `market_detail_snapshots` | `id`, `listing_snapshot_id`, `finance_json`, `transactions_json`, `costs_json`, `maintenance_json`, `location_json` | 대출·실거래·세금·교통 등 공통 상세 |
| `change_events` | `id`, `run_id`, `listing_group_id`, `event_type`, `changed_fields_json`, `before_json`, `after_json`, `detected_at` | 신규·변경·삭제 이력 |
| `crawl_schedules` | `id`, `source_id`, `cadence`, `time_of_day`, `timezone`, `enabled`, `next_run_at` | 반복 조사 설정 |

**제약 조건**

- `tracked_sources.url_hash` 유일
- `apartments.naver_complex_id` 유일
- `broker_articles.naver_article_id` 유일
- `listing_snapshots(run_id, listing_group_id)` 유일
- `broker_article_snapshots(run_id, broker_article_id)` 유일
- 금액은 원 단위 `BIGINT`, 면적은 `NUMERIC(10,2)`, 시간은 `TIMESTAMPTZ`

- [ ] 모델과 관계를 작성하고 삭제는 기본적으로 cascade가 아닌 보존 정책을 사용한다.
- [ ] Alembic 초기 마이그레이션을 작성한다.
- [ ] 사용자 승인 후 마이그레이션과 제약 조건 검증을 실행한다.

```powershell
cd backend
alembic upgrade head
pytest tests/unit/test_model_constraints.py -q
```

예상 결과: 모든 테이블 생성 및 중복 제약 테스트 통과.

---

### 작업 3: URL 정규화와 분석 작업 API

**파일**

- 생성: `backend/app/domain/url_identity.py`
- 생성: `backend/app/schemas/analysis.py`
- 생성: `backend/app/services/analysis_service.py`
- 생성: `backend/app/api/routes/analyses.py`
- 생성: `backend/app/tasks/crawl_tasks.py`
- 생성: `backend/tests/unit/test_url_identity.py`

**API**

| 메서드 | 경로 | 반환 |
|---|---|---|
| `POST` | `/api/analyses` | `runId`, `sourceId`, `status` |
| `GET` | `/api/analyses/{runId}` | 상태, 단계, 진행률, 오류 |
| `GET` | `/api/analyses/{runId}/result` | 완료된 아파트 ID와 요약 |
| `POST` | `/api/analyses/{runId}/cancel` | 취소 결과 |

```python
class AnalysisCreate(BaseModel):
    source_url: AnyHttpUrl

class AnalysisStatus(BaseModel):
    run_id: UUID
    source_id: UUID
    status: Literal["queued", "running", "completed", "partial", "failed", "blocked", "cancelled"]
    stage: Literal["url", "complex", "listings", "brokers", "details", "compare", "save"]
    progress: int
    error_code: str | None = None
```

- [ ] HTTPS와 `fin.land.naver.com` 호스트만 허용한다.
- [ ] fragment 제거, query parameter 정렬 후 SHA-256 `url_hash`를 생성한다.
- [ ] 같은 URL의 실행 중 작업이 있으면 새 작업 대신 기존 `runId`를 반환한다.
- [ ] URL이 아파트 하나로 확정되지 않으면 `ambiguous_source` 또는 `complex_not_found`로 종료한다.
- [ ] 사용자 승인 후 URL 계약 테스트를 실행한다.

```powershell
cd backend
pytest tests/unit/test_url_identity.py -q
```

예상 결과: 허용 URL, 외부 호스트 차단, 동일 URL 정규화 테스트 통과.

---

### 작업 4: 브라우저 수집기와 Npay 안전 탐색

**파일**

- 생성: `backend/app/crawler/browser.py`
- 생성: `backend/app/crawler/navigation.py`
- 생성: `backend/app/crawler/selectors.py`
- 생성: `backend/app/crawler/errors.py`
- 생성: `backend/app/crawler/types.py`
- 생성: `backend/tests/fixtures/complex_page.html`
- 생성: `backend/tests/unit/test_navigation_policy.py`

**핵심 탐색 규칙**

```python
def choose_article_target(*, npay_href: str | None, internal_href: str | None) -> str:
    if npay_href:
        return validate_internal_article_href(npay_href)
    return validate_internal_article_href(internal_href)
```

- `npay_href`가 존재하면 반드시 `/articles/{articleId}` 내부 링크를 선택한다.
- `/out-link-bridge`, 외부 도메인, 새 외부 창은 거부한다.
- Npay가 없을 때만 네이버 내부 `매물 보러가기`를 사용한다.

- [ ] 단지 목록이 준비될 때까지 고정 sleep 대신 명시적 DOM 조건을 기다린다.
- [ ] 가상 스크롤 목록을 끝까지 순회하며 `groupId`와 `articleId`를 중복 제거한다.
- [ ] `중개사 n곳에서 등록했어요`를 열고 표시된 수와 실제 수집된 카드 수를 비교한다.
- [ ] 중개사별 상세를 하나씩 열고 닫으며 동시에 하나의 상세 패널만 유지한다.
- [ ] CAPTCHA, 로그인 요구, 접근 제한은 `blocked`로 종료하고 우회하지 않는다.
- [ ] selector는 `SELECTOR_VERSION = "fin-land-2026-07"`처럼 버전 관리한다.
- [ ] 사용자 승인 후 저장된 fixture로 Npay 선택 정책만 검증한다.

```powershell
cd backend
pytest tests/unit/test_navigation_policy.py -q
```

예상 결과: Npay 우선, 외부 bridge 거부, 일반 내부 링크 fallback 테스트 통과.

---

### 작업 5: 상세 슬라이드 전체 필드 파서

**파일**

- 생성: `backend/app/crawler/parsers/complex.py`
- 생성: `backend/app/crawler/parsers/listing_group.py`
- 생성: `backend/app/crawler/parsers/broker_article.py`
- 생성: `backend/app/crawler/parsers/market_details.py`
- 생성: `backend/tests/fixtures/article_detail.html`
- 생성: `backend/tests/unit/test_broker_article_parser.py`

**중개사별 상세 출력 계약**

```python
class BrokerArticleDetail(BaseModel):
    article_id: str
    provider: str
    is_npay: bool
    advertised_price: int | None
    price_per_3_3m2: int | None
    management_fee: int | None
    loan_description: str | None
    supply_area_m2: Decimal | None
    exclusive_area_m2: Decimal | None
    exclusive_rate: int | None
    floor: str | None
    room_count: int | None
    bathroom_count: int | None
    direction: str | None
    structure: str | None
    move_in_date: str | None
    description: str
    option_tags: list[str]
    verified_at: date | None
    first_published_at: date | None
    realtor: RealtorProfile | None
    warnings: list[str]
```

**공통 상세 수집 범위**

- 대출 한도, LTV, KB시세, 금리, 예상 월 원리금
- 동일면적 호가 범위와 매물 수
- 평균 매매·전세가와 갭
- 2년 최고·최저 및 최근 실거래
- 중개보수, 취득세, 재산세, 종합부동산세
- 기준월·월평균·여름·겨울 관리비
- 단지 세대수, 동 수, 승인일, 주차, 난방, 현관, 용적률, 건폐율, 시공사, 관리사무소
- 개발 예정, 배정학교, 지하철, 버스

- [ ] 화면에 없는 필드는 빈 값으로 저장하고 추정값을 만들지 않는다.
- [ ] 표시 호가와 설명문 가격이 다르면 `price_mismatch` 경고를 추가한다.
- [ ] 전화번호·등록번호는 공개된 중개사 영업 정보로만 저장한다.
- [ ] 사용자 승인 후 fixture 하나에 대한 parser 계약 검증을 실행한다.

```powershell
cd backend
pytest tests/unit/test_broker_article_parser.py -q
```

예상 결과: 107동 표본의 가격, 관리비, 옵션, 입주일, 중개사 정보와 공통 상세 필드가 구조화된다.

---

### 작업 6: 매물 그룹화와 추가정보 정제·중복 제거

**파일**

- 생성: `backend/app/domain/listing_identity.py`
- 생성: `backend/app/domain/normalizer.py`
- 생성: `backend/app/domain/aggregator.py`
- 생성: `backend/tests/unit/test_aggregator.py`
- 수정: `frontend/src/utils/listingAdditionalInfo.ts`

**대표 매물 키**

```text
complex_id + trade_type + building + exclusive_area(2 decimals) + floor + direction + normalized_price
```

가격 변경 전후에도 같은 매물을 추적할 수 있도록 이전 실행의 article ID 집합과 보조 유사도 키를 함께 사용한다.

**정규화 규칙**

```python
OPTION_ALIASES = {
    "시에": "시스템에어컨",
    "에어컨": "시스템에어컨",
    "식세기": "식기세척기",
    "미세 방충망": "미세방충망",
    "전자 계약": "전자계약",
    "주인 거주": "주인거주",
}
```

- 동일 옵션은 한 번만 반환한다.
- 에어컨 대수가 다르면 `시스템에어컨 3~4대`처럼 범위로 반환한다.
- 입주 조건은 값별 중개사 수로 반환한다: `즉시입주 협의 12곳 · 즉시입주 2곳`.
- 관리비는 최솟값과 최댓값으로 반환한다: `25만원 ~ 33만원`.
- 융자는 `융자 없음`, `정보 표기`, `미표기` 건수를 분리한다.
- 충돌 값은 숨기지 않고 `warnings`에 남긴다.

```python
class AggregatedListingInfo(BaseModel):
    option_tags: list[str]
    move_in_summary: str
    management_fee_summary: str
    room_bath_summary: str
    loan_summary: str
    source_count: int
    warnings: list[str]
```

- [ ] Python 결과를 정식 원본으로 사용하고 TypeScript 유틸리티는 데모 fallback으로만 유지한다.
- [ ] 사용자 승인 후 별칭, 중복, 범위, 충돌 데이터 테스트를 실행한다.

```powershell
cd backend
pytest tests/unit/test_aggregator.py -q
```

예상 결과: 순서가 다른 동일 입력에도 완전히 같은 정제 결과를 반환한다.

---

### 작업 7: 트랜잭션 저장과 날짜별 변경 판별

**파일**

- 생성: `backend/app/domain/comparator.py`
- 생성: `backend/app/services/persistence_service.py`
- 생성: `backend/tests/unit/test_comparator.py`
- 생성: `backend/tests/integration/test_persistence.py`

**상태 규칙**

```text
new -> active
active -> changed -> active
active -> missing(1) -> missing(2) -> removed
missing | removed -> restored
```

- 이전 완전 성공 실행에 없고 현재 있으면 `new`.
- 가격, 보증금, 월세, 관리비, 입주일, 층, 방향, 옵션, 중개사 article 집합이 달라지면 `changed`.
- 현재 실행이 `partial`, `failed`, `blocked`이면 missing 횟수를 증가시키지 않는다.
- 완전 성공 실행에서 연속 2회 누락된 경우에만 `removed`.
- 다시 나타나면 기존 `listing_group_id`를 사용하고 `restored` 이벤트를 생성한다.
- 실행 결과 저장, aggregate 생성, change event 생성을 하나의 DB 트랜잭션으로 처리한다.

```json
{
  "eventType": "changed",
  "changedFields": ["price", "optionTags"],
  "before": {"price": 720000000},
  "after": {"price": 698000000},
  "detectedAt": "2026-07-22T09:48:00+09:00"
}
```

- [ ] 사용자 승인 후 신규·변경·부분 실패·삭제·재등장 케이스만 검증한다.

```powershell
cd backend
pytest tests/unit/test_comparator.py tests/integration/test_persistence.py -q
```

예상 결과: 부분 실패에서 삭제 이벤트가 발생하지 않고, 2회 완전 누락에서만 삭제된다.

---

### 작업 8: 기존 조사 데이터 조회 API

**파일**

- 생성: `backend/app/schemas/dashboard.py`
- 생성: `backend/app/schemas/apartment.py`
- 생성: `backend/app/schemas/listing.py`
- 생성: `backend/app/services/query_service.py`
- 생성: `backend/app/api/routes/dashboard.py`
- 생성: `backend/app/api/routes/apartments.py`
- 생성: `backend/app/api/routes/listings.py`
- 생성: `backend/tests/integration/test_query_api.py`

**조회 API**

| 메서드 | 경로 | 화면 |
|---|---|---|
| `GET` | `/api/dashboard?sourceId=` | 대시보드 선택 아파트 요약 |
| `GET` | `/api/apartments?query=&page=` | 조사 아파트 목록 |
| `GET` | `/api/apartments/{complexId}` | 단지 상세와 조사 날짜 목록 |
| `GET` | `/api/apartments/{complexId}/history` | 날짜별 거래유형 수와 변화량 |
| `GET` | `/api/apartments/{complexId}/listings?runId=&tradeType=&status=` | 선택 날짜 매물 |
| `GET` | `/api/listings/{listingGroupId}` | 대표 매물, aggregate, 중개사별 상세, 공통 상세 |

**초기 진입 규칙**

- `/dashboard`는 가장 최근 조사한 아파트를 기본 선택한다.
- `/apartments`는 저장된 모든 조사 아파트를 최근 조사 순으로 반환한다.
- 저장 데이터가 없을 때만 현재 `DatasetRequired` 빈 상태를 보여준다.
- 새로고침해도 API를 다시 호출하여 기존 조사 결과를 복구한다.
- URL별 최근 성공 결과와 최근 실패 결과를 분리해 표시한다.

- [ ] cursor 또는 page 기반 페이지네이션을 적용한다.
- [ ] 선택 날짜는 `runId`를 기준으로 고정하여 화면을 보는 중 새 작업이 끝나도 결과가 바뀌지 않게 한다.
- [ ] 사용자 승인 후 조회 API의 데이터 존재·빈 상태만 검증한다.

```powershell
cd backend
pytest tests/integration/test_query_api.py -q
```

예상 결과: 재접속 시 최근 아파트, 날짜별 매물, 상세 중개사 정보가 동일하게 반환된다.

---

### 작업 9: React 데모 상태를 실제 API 상태로 교체

**파일**

- 생성: `frontend/src/api/client.ts`
- 생성: `frontend/src/api/analyses.ts`
- 생성: `frontend/src/api/apartments.ts`
- 생성: `frontend/src/api/schedules.ts`
- 생성: `frontend/src/api/exports.ts`
- 생성: `frontend/src/types/api.ts`
- 생성: `frontend/src/state/AnalysisProvider.tsx`
- 수정: `frontend/src/main.tsx`
- 수정: `frontend/src/pages/AnalysisPage.tsx`
- 수정: `frontend/src/pages/DashboardPage.tsx`
- 수정: `frontend/src/pages/ApartmentsPage.tsx`
- 수정: `frontend/src/pages/ApartmentDetailPage.tsx`
- 수정: `frontend/src/pages/ListingDetailPage.tsx`
- 수정: `frontend/src/components/analysis/DatasetRequired.tsx`

**프런트엔드 상태 계약**

```ts
type AnalysisRunStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'blocked'
  | 'cancelled'

interface AnalysisProviderValue {
  recentApartments: ApartmentSummary[]
  selectedApartmentId: string | null
  startAnalysis(sourceUrl: string): Promise<string>
  selectApartment(complexId: string): void
  refreshRecentApartments(): Promise<void>
}
```

- [ ] TanStack Query를 설치하고 서버 상태를 React Context 내부 객체 복사 대신 query key로 관리한다.
- [ ] 앱 시작 시 `GET /api/apartments`를 호출하여 저장된 아파트를 복구한다.
- [ ] URL 분석은 `POST /api/analyses` 후 상태 API를 1초 간격으로 polling하고 완료 즉시 관련 query를 invalidate한다.
- [ ] 현재 라우트와 UX는 유지하고 `demoRealEstate.ts`는 `VITE_USE_DEMO_DATA=true`일 때만 사용한다.
- [ ] 카드·리스트·테이블과 중개사 접기·펼치기는 API 데이터에서도 동일하게 동작하게 한다.
- [ ] `loading`, `empty`, `partial`, `blocked`, `failed` 상태를 한국어로 표시한다.
- [ ] 사용자 승인 후 최소 프런트 계약 검증을 실행한다.

```powershell
cd frontend
npm run test -- src/tests/App.test.tsx
```

예상 결과: 기존 데이터 초기 로드와 분석 완료 후 query 갱신 시나리오 통과.

---

### 작업 10: 조사 스케줄러와 실행 이력

**파일**

- 생성: `backend/app/core/locks.py`
- 생성: `backend/app/services/schedule_service.py`
- 생성: `backend/app/api/routes/schedules.py`
- 생성: `backend/app/tasks/scheduled_tasks.py`
- 생성: `backend/tests/unit/test_schedule_service.py`
- 수정: `frontend/src/pages/SchedulePage.tsx`

**API**

| 메서드 | 경로 | 동작 |
|---|---|---|
| `GET` | `/api/schedules` | 스케줄 목록과 다음 실행 |
| `POST` | `/api/schedules` | URL별 스케줄 생성 |
| `PATCH` | `/api/schedules/{id}` | 주기·시각·활성 상태 변경 |
| `DELETE` | `/api/schedules/{id}` | 비활성화 후 삭제 |
| `GET` | `/api/schedules/{id}/runs` | 최근 실행 이력 |

- [ ] `daily`, `weekdays`, `weekly`와 `Asia/Seoul` 시각을 지원한다.
- [ ] Celery Beat가 매분 실행 대상을 찾고 Redis 락 `crawl:source:{source_id}`를 획득한 경우에만 작업을 등록한다.
- [ ] 수동 조사와 예약 조사가 같은 URL에서 동시에 실행되지 않게 한다.
- [ ] 실패 시 다음 예약은 유지하고 최근 실패 상태를 화면에 표시한다.
- [ ] 사용자 승인 후 다음 실행 시각과 중복 락 검증을 실행한다.

```powershell
cd backend
pytest tests/unit/test_schedule_service.py -q
```

예상 결과: 일간·평일·주간 시각 계산과 중복 실행 방지가 통과한다.

---

### 작업 11: 서버 XLSX 생성과 다운로드

**파일**

- 생성: `backend/app/services/export_service.py`
- 생성: `backend/app/api/routes/exports.py`
- 생성: `backend/tests/integration/test_export.py`
- 수정: `frontend/src/components/export/ExcelDownloadButton.tsx`
- 수정: `frontend/src/utils/exportWorkbook.ts`

**API**

```text
GET /api/exports/{sourceId}.xlsx?from=2026-07-01&to=2026-07-31
```

**시트**

1. `아파트요약`
2. `매물현황`
3. `중개사등록`
4. `추가정보`
5. `상세지표`
6. `조사이력`
7. `변경이벤트`

- [ ] 화면과 동일한 aggregate 레코드를 사용해 옵션, 입주일, 관리비, 융자 요약을 출력한다.
- [ ] 숫자 금액 열과 한국어 표시 열을 함께 제공한다.
- [ ] 파일명은 `naver-land-{complexId}-{YYYYMMDD-HHmm}.xlsx`로 생성한다.
- [ ] 대용량 데이터는 메모리 전체 복사 대신 write-only workbook으로 생성한다.
- [ ] 프런트의 SheetJS 데모 생성은 fallback으로만 유지한다.
- [ ] 사용자 승인 후 시트명과 핵심 열만 검증한다.

```powershell
cd backend
pytest tests/integration/test_export.py -q
```

예상 결과: 7개 시트와 숫자형 금액 셀이 포함된 XLSX 응답 반환.

---

### 작업 12: 운영 안전장치와 배포 준비

**파일**

- 생성: `backend/app/core/logging.py`
- 생성: `backend/Dockerfile`
- 생성: `frontend/Dockerfile`
- 생성: `docker-compose.production.yml`
- 생성: `docs/operations/runbook.md`
- 생성: `docs/operations/data-policy.md`

**운영 규칙**

- 로그에 URL 전체 query, 전화번호, 상세 설명 원문을 기록하지 않는다.
- 실행 로그에는 `runId`, `sourceId`, 단계, 수집 수, 오류 코드, 소요시간만 남긴다.
- 단지 화면 표시 건수와 실제 수집 건수가 다르면 실행을 `partial`로 기록한다.
- selector 불일치, 접근 차단, 중개사 카드 누락을 별도 지표로 집계한다.
- DB 백업과 복구 절차를 문서화한다.
- 운영 전에 네이버 이용약관, robots 정책, 데이터 사용 범위를 검토하고 허용 범위를 확정한다.

**파일럿 제한**

- 운영 사용자 1명
- 등록 URL 1개
- 하루 1회 예약 조사
- 도메인 동시 브라우저 1개
- 2주간 차단률, 누락률, 잘못된 삭제 판정률 확인 후 확대

- [ ] 사용자 승인 후 전체 스택 빌드와 브라우저 인수 확인을 별도 단계로 실행한다.

```powershell
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d
```

예상 결과: API, Worker, Scheduler, PostgreSQL, Redis, Frontend가 독립 컨테이너로 실행된다.

---

## 4. 구현 순서와 승인 게이트

| 마일스톤 | 작업 | 사용자에게 확인받을 결과 |
|---|---|---|
| M1 | 작업 1~3 | API 기반, DB 스키마, URL 작업 생성 |
| M2 | 작업 4~6 | 단일 URL의 중개사·상세 수집 및 정제 결과 |
| M3 | 작업 7~8 | 날짜별 저장, 변경 판별, 기존 데이터 조회 |
| M4 | 작업 9 | 현재 데모 UX에 실제 API 연결 |
| M5 | 작업 10~11 | 예약 조사와 서버 XLSX |
| M6 | 작업 12 | 제한된 운영 배포 준비 |

각 마일스톤 종료 시 다음 단계로 넘어가기 전에 사용자에게 결과를 보고하고 승인을 받는다. 테스트·빌드·브라우저 확인은 해당 마일스톤의 사용자 승인 후 필요한 최소 명령만 실행한다.

## 5. 이번 계획에서 제외하는 범위

- 네이버 로그인 자동화
- CAPTCHA 또는 접근 차단 우회
- 외부 중개 플랫폼으로 이동하여 추가 수집
- 회원가입, 소셜 로그인, 결제, 조직·권한 관리
- 모바일 네이티브 앱
- AI 가격 예측 또는 투자 추천
- 실시간 알림 채널 연동

---

# AI Execution Contract (English)

## Objective

Keep the approved React/Tailwind UX unchanged and replace its in-memory demo state with a persistent Python service that crawls one user-supplied Naver Pay Real Estate apartment URL, stores dated snapshots, aggregates broker details, detects changes, schedules recurring runs, and exports XLSX files.

## Required Worker Skill

Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` when this plan is approved for execution. Do not run tests, builds, browser checks, commits, or deployments until the user explicitly approves that action.

## System Boundaries

- Frontend: existing React 19, TypeScript, Tailwind CSS and current routes/components.
- API: FastAPI with Pydantic v2.
- Persistence: PostgreSQL 16, SQLAlchemy 2, Alembic.
- Queue: Redis 7 and Celery 5.
- Browser worker: Playwright Chromium, one concurrent crawl per source.
- Export: openpyxl server-side streaming workbook.
- Time: store UTC; serialize `Asia/Seoul` ISO 8601.
- MVP deployment is single-user. Authentication and billing are out of scope.

## Non-Negotiable Navigation Policy

```text
if Npay internal link exists:
    click only /articles/{articleId}
    never click /out-link-bridge
else:
    click the Naver-internal article link
```

Do not bypass login, CAPTCHA, access restrictions, robots policy, or anti-bot controls.

## Canonical Data Contracts

- `TrackedSource`: one normalized Naver URL mapped to exactly one complex.
- `CrawlRun`: one immutable execution record and progress state.
- `ApartmentSnapshot`: dated complex metadata.
- `ListingGroup`: stable physical-listing identity across runs.
- `ListingSnapshot`: listing-group values for one run.
- `BrokerArticle`: stable Naver article identity.
- `BrokerArticleSnapshot`: every structured detail field for one run.
- `AggregatedListingInfo`: deduplicated options and summarized move-in, fee, room/bath and loan values.
- `MarketDetailSnapshot`: finance, transactions, taxes, maintenance, school, transit and development details.
- `ChangeEvent`: auditable before/after delta.

## Run State Machine

```text
queued -> running -> completed | partial | failed | blocked | cancelled
```

## Listing State Machine

```text
new -> active
active -> changed -> active
active -> missing(1) -> missing(2) -> removed
missing | removed -> restored
```

A partial, failed, or blocked run never advances `missing_count`.

## Frontend Hydration Contract

1. App startup fetches `/api/apartments`.
2. Dashboard selects the most recently crawled apartment by default.
3. Apartments page displays every persisted complex ordered by latest successful run.
4. `DatasetRequired` is shown only when the database has no stored apartment.
5. Analysis completion invalidates dashboard, apartment, history and listing queries.
6. Existing card/list/table modes and broker accordions consume API responses without layout redesign.
7. Demo data is allowed only behind `VITE_USE_DEMO_DATA=true`.

## Delivery Order

1. Backend bootstrap and persistent schema.
2. URL identity and analysis-run API.
3. Browser navigation and full detail parsers.
4. Deterministic grouping, normalization and aggregation.
5. Transactional snapshots and change detection.
6. Query APIs and frontend persistence hydration.
7. Scheduler and distributed locks.
8. Server XLSX export.
9. Operational safeguards and limited pilot deployment.

## Acceptance Criteria

- Reloading the portal restores previously researched apartments.
- One submitted URL resolves to exactly one Naver complex.
- Every visible broker registration is collected or the run is marked partial.
- Npay records use only internal Naver article detail URLs.
- Structured detail fields and their capture timestamps are persisted.
- Duplicate option names are canonicalized once; conflicting values remain visible as summaries or warnings.
- Deletion requires two consecutive complete absences.
- Dashboard, apartment list, listing details and XLSX use the same backend records.
- Concurrent manual and scheduled crawls for the same source are deduplicated.
- No implementation, verification, commit, or deployment step proceeds without the user's approval gate.
