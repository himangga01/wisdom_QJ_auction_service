# 중개사 등록 물건 추가 상세정보 선택 수집 구현계획

> **실행 담당 AI 필수 사항:** 이 문서는 구현 순서와 계약을 고정하는 계획서다. 실제 코드 수정, 테스트 실행, 실사이트 접속은 사용자의 별도 실행 승인 범위 안에서만 진행한다.

## 한국어

### 1. 문서 목적

사용자가 네이버 부동산 URL 분석을 요청할 때 각 중개사가 등록한 물건의 추가 상세 슬라이드까지 수집할지 선택할 수 있도록 한다.

- 기본값은 기존 동작을 유지하는 `수집함`이다.
- `수집 안 함`을 선택해도 모든 매물 그룹과 모든 중개사 등록 물건은 끝까지 수집한다.
- `수집 안 함`일 때만 각 중개사 물건의 추가 상세 슬라이드를 열지 않는다.
- 즉시 분석과 자동 조사 스케줄 모두 동일한 선택값을 지원한다.
- 조사 실행, 매물 상세 화면, 변경 이력, XLSX에 실제 수집 여부가 일관되게 남아야 한다.

승인된 상세 설계는 다음 문서를 기준으로 한다.

- `docs/superpowers/specs/2026-07-28-optional-broker-detail-collection-design.md`

### 2. 기술 구성

- 백엔드: Python 3.12+, FastAPI, Pydantic, SQLAlchemy async, Alembic
- 수집기: 사용자의 Chrome을 CDP로 제어하는 Playwright UI 수집기
- 작업 실행: 로컬 dispatcher 또는 Celery가 `run_id`를 전달
- 프런트엔드: React 19, TypeScript, Vite, Tailwind CSS
- 엑셀: 백엔드 `openpyxl`, 데모 모드 브라우저 `xlsx`
- 저장소: 현재 SQLAlchemy/Alembic 데이터베이스 구조 유지

### 3. 구현 중 고정할 규칙

1. 네이버 부동산 API 또는 직접 HTTP 수집을 추가하지 않는다.
2. 수집 옵션이 꺼져도 매물 그룹, 중개사 등록 행, 네이버 매물번호의 전수 수집과 건수 검증을 생략하지 않는다.
3. 옵션이 켜져 있을 때의 기존 Chrome UI 상세 수집 경로는 그대로 유지한다.
4. 기존 데이터에 새 필드가 없으면 이전 동작과 호환되도록 `true`로 해석한다.
5. 상세 미수집은 값이 삭제된 상태가 아니므로 허위 변경 이력을 만들지 않는다.
6. 구현 범위 밖의 리팩터링, 새 크롤링 방식, 우회 기능은 추가하지 않는다.
7. 사용자가 요청한 기능 구현을 먼저 마친 뒤 승인된 집중 테스트만 실행한다.
8. 전체 테스트 스위트, 무관한 테스트, 추가 실사이트 검증은 임의로 실행하지 않는다.
9. Git commit은 만들지 않는다.

### 4. 최종 데이터 흐름

```text
URL 입력 + 추가 상세 수집 선택
  -> POST /api/analyses
  -> CrawlRun에 선택값 저장
  -> dispatcher는 기존처럼 run_id만 전달
  -> 작업자가 DB에서 URL과 선택값을 다시 조회
  -> CrawlScope에 선택값 전달
  -> 모든 매물 그룹 및 중개사 등록 행 수집
     -> ON: 각 중개사 물건 상세 슬라이드 수집
     -> OFF: 상세 슬라이드는 열지 않고 행의 기본 정보로 최소 객체 생성
  -> 스냅샷에 detail_collected 저장
  -> 조회 API, React 상세 카드, XLSX에 실제 상태 표시
```

---

## 5. 단계별 구현계획

### 작업 1. 데이터베이스와 핵심 도메인 필드 추가

**대상 파일**

- 생성: `backend/alembic/versions/0004_optional_broker_detail_collection.py`
- 수정: `backend/app/models/entities.py`
- 수정: `backend/app/crawler/types.py`

**구현 내용**

1. 새 Alembic migration을 만든다.

```python
revision = "0004_optional_broker_detail_collection"
down_revision = "0003_schedule_weekday_and_source_unique"
```

2. 다음 두 컬럼을 추가한다.

```text
crawl_runs.collect_broker_details
crawl_schedules.collect_broker_details
```

두 컬럼의 계약은 다음과 같다.

```python
sa.Column(
    "collect_broker_details",
    sa.Boolean(),
    nullable=False,
    server_default=sa.true(),
)
```

3. downgrade에서는 위 두 컬럼만 역순으로 제거한다.
4. `CrawlRun`과 `CrawlSchedule` SQLAlchemy 모델에 다음 필드를 추가한다.

```python
collect_broker_details: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    default=True,
    server_default=true(),
)
```

5. `BrokerArticleDetail`에 기본값이 있는 필드를 추가한다.

```python
detail_collected: bool = True
```

6. `BrokerArticleDetail.model_dump(mode="json")`의 기존 저장 경로를 이용해 `BrokerArticleSnapshot.details_json`에 `detail_collected`가 함께 저장되도록 한다. 별도 JSON 컬럼은 추가하지 않는다.

**완료 조건**

- 새 실행과 새 스케줄의 기본값이 모두 `true`다.
- 기존 DB 행과 이전 스냅샷은 상세 수집 실행으로 호환 해석할 수 있다.
- 스냅샷 JSON이 물건별 상세 수집 여부를 보존한다.

---

### 작업 2. 즉시 분석 API와 실행 생성 계약 확장

**대상 파일**

- 수정: `backend/app/schemas/analysis.py`
- 수정: `backend/app/services/analysis_service.py`
- 수정: `backend/app/api/routes/analyses.py`

**구현 내용**

1. `AnalysisCreate`에 다음 필드를 추가한다.

```python
collect_broker_details: bool = True
```

Pydantic의 기존 camelCase alias 설정을 사용해 JSON에서는 `collectBrokerDetails`로 받는다.

2. `AnalysisAccepted`에 다음 필드를 추가한다. 이를 상속하는 `AnalysisStatus`에도 같은 값이 포함된다.

```python
collect_broker_details: bool
```

3. `AnalysisService.create` 계약을 다음과 같이 바꾼다.

```python
async def create(
    self,
    source_url: str,
    *,
    collect_broker_details: bool = True,
) -> tuple[CrawlRun, bool]:
```

4. 새 `CrawlRun` 생성 시 선택값을 저장한다.
5. 같은 URL에 활성 실행이 있을 때 다음 규칙을 적용한다.

- 기존 실행의 값과 요청값이 같음: 기존 실행 재사용
- 기존 실행의 값과 요청값이 다름: `AnalysisOptionConflictError` 발생

6. 예외는 안정적인 오류 코드를 가진다.

```python
class AnalysisOptionConflictError(RuntimeError):
    code = "analysis_option_conflict"
```

7. 동시에 실행 생성이 충돌해 기존 활성 실행을 재조회하는 경로에서도 같은 옵션 비교를 반드시 다시 적용한다.
8. `POST /api/analyses`는 `payload.collect_broker_details`를 서비스에 전달한다.
9. `AnalysisOptionConflictError`는 HTTP 409와 `analysis_option_conflict` 응답으로 변환한다.
10. 분석 생성 응답과 상태 조회 응답에는 DB의 실제 `run.collect_broker_details`를 반환한다. 요청값을 그대로 복사하지 않는다.

**API 결과 계약**

```json
{
  "sourceUrl": "https://fin.land.naver.com/map?...",
  "collectBrokerDetails": false
}
```

**완료 조건**

- 필드를 생략한 기존 클라이언트는 기존과 동일하게 상세정보를 수집한다.
- 같은 URL과 같은 옵션의 중복 요청은 기존 실행을 재사용한다.
- 같은 URL과 다른 옵션의 동시 실행 요청은 409로 명확히 거절된다.
- 클라이언트가 현재 실행에 실제 적용된 값을 응답으로 확인할 수 있다.

---

### 작업 3. 작업자와 수집 범위에 실행 옵션 전달

**대상 파일**

- 수정: `backend/app/tasks/crawl_tasks.py`
- 수정: `backend/app/crawler/scope.py`

**구현 내용**

1. `CrawlScope`에 기본값이 있는 필드를 추가한다.

```python
collect_broker_details: bool = True
```

2. `CrawlScope.full()`과 `CrawlScope.sampled()`가 선택값을 받을 수 있게 하되 기본값은 `True`로 유지한다.
3. 전수 수집 여부를 판단하는 기존 `_is_full_collection()` 또는 이에 해당하는 로직에는 `collect_broker_details`를 조건으로 넣지 않는다. 상세 슬라이드 수집 여부와 전수 매물 수집 여부는 별개다.
4. `_claim_run(run_id)`가 `CrawlRun.collect_broker_details`도 조회하고 반환하도록 한다.

```python
tuple[str, str | None, UUID | None, bool]
```

5. `_execute_pipeline()`은 조회한 값으로 실행별 scope를 만든다.

```python
scope = CrawlScope.full(
    collect_broker_details=collect_broker_details,
)
payload = await collector.collect(source_url, scope=scope)
```

실제 `collect()`의 기존 인자 형태가 다르면 동일 의미가 유지되는 최소 변경으로 연결한다.

6. 로컬 dispatcher와 Celery 메시지에는 옵션을 새로 넣지 않는다. 기존처럼 `run_id`만 전달하고 작업자가 DB를 단일 기준으로 읽는다.

**완료 조건**

- 프로세스 재시작이나 큐 지연 뒤에도 DB에 저장된 옵션이 그대로 적용된다.
- 로컬 실행과 Celery 실행이 동일한 경로를 사용한다.
- 상세 수집 OFF가 sampled/full 또는 건수 검증의 의미를 바꾸지 않는다.

---

### 작업 4. Chrome UI 수집기에서 상세 슬라이드 선택 분기 구현

**대상 파일**

- 수정: `backend/app/crawler/browser.py`
- 필요 시에만 수정: `backend/app/crawler/scope.py`
- 변경하지 않음: `backend/app/crawler/live_dom.py`

**구현 내용**

1. `_collect_visible_group()`의 기존 순서를 유지한다.

```text
표시된 매물 그룹 확인
-> "중개사 n곳에서 등록했어요" 확장
-> lazy loading을 포함해 모든 중개사 행 수집
-> 각 행의 안전한 네이버 내부 article target 검증
-> article ID 중복 제거와 표시 건수 검증
```

2. 위 공통 수집이 끝난 후 `scope.collect_broker_details`로 물건별 처리를 분기한다.
3. `True` 경로에서는 현재 `_collect_slide_article()` 호출, Npay 버튼 처리, 상세 슬라이드 파싱을 그대로 사용한다.
4. `False` 경로에서는 다음 동작을 금지한다.

- 중개사 물건 상세 trigger 클릭
- `Npay 부동산에서 보기` 클릭
- `매물 보러가기` 클릭
- 상세 슬라이드 대기 및 파싱

5. `False` 경로는 이미 읽은 `BrokerCardObservation`과 안전 검증된 target으로 최소 `BrokerArticleDetail`을 만든다.

```python
BrokerArticleDetail(
    article_id=target.article_id,
    article_url=target.article_url,
    provider=observation.provider or "미표시",
    is_npay=observation.is_npay,
    description=observation.description,
    captured_at=captured_at,
    detail_collected=False,
    market_details=None,
)
```

현재 모델의 실제 필드명에 맞춰 작성하되 의미는 바꾸지 않는다.

6. 제공처가 비어 있으면 현재 정책대로 `미표시`를 저장하고 `provider_missing` warning을 기록한다.
7. 최소 객체 생성과 안전 URL 검증이 성공한 다음에만 `seen_article_ids`에 넣는다.
8. 상세 수집 OFF에서도 다음 fail-closed 검증을 그대로 수행한다.

- 화면의 매물 그룹 수와 수집 그룹 수
- `중개사 n곳` 표시 수와 수집한 고유 article ID 수
- lazy loading 완료 여부
- 비어 있지 않은 거래유형 전수 순회
- 외부 또는 검증되지 않은 article target 거부

9. 상세 수집 ON 결과에는 `detail_collected=True`가 저장되도록 기본값 또는 명시값을 사용한다.

**완료 조건**

- OFF 실행은 상세 슬라이드를 한 번도 열지 않는다.
- OFF 실행도 화면에 존재하는 모든 중개사 등록 물건번호를 저장한다.
- ON 실행의 기존 Npay/일반 상세 수집 동작은 바뀌지 않는다.
- 상세정보 선택이 전수 수집 제한값이나 조기 종료 조건으로 사용되지 않는다.

---

### 작업 5. 상세 미수집으로 인한 허위 변경 이력 차단

**대상 파일**

- 수정: `backend/app/domain/comparator.py`
- 수정: `backend/app/services/persistence_service.py`
- 원칙적으로 변경하지 않음: `backend/app/domain/aggregator.py`

**구현 내용**

1. `compare_listings()`에 상세 파생 필드 비교 여부를 추가한다.

```python
def compare_listings(
    before: ComparableListing | None,
    after: ComparableListing | None,
    *,
    compare_detail_fields: bool = True,
) -> ListingChange:
```

2. `compare_detail_fields=False`일 때 비교에서 제외할 필드는 다음으로 한정한다.

```text
management_fee
move_in_date
option_tags
```

상세 JSON에 대한 별도 비교가 존재하면 비용, 입주, 옵션, 상세 단지·위치 등 상세 슬라이드에서만 생기는 필드도 같은 조건으로 제외한다.

3. 다음 핵심 필드는 옵션과 무관하게 계속 비교한다.

```text
매물 그룹의 등장·삭제
article ID 집합
거래유형
가격
보증금
월세
동
층
방향
면적
```

4. `persistence_service.py`에서 직전 비교 대상 스냅샷뿐 아니라 그 스냅샷을 만든 완료 실행의 `collect_broker_details`를 함께 조회한다.
5. 현재 실행의 `CrawlRun.collect_broker_details`도 DB에서 읽는다.
6. 다음 조건일 때만 상세 파생 필드를 비교한다.

```python
compare_detail_fields = (
    previous_run_collect_broker_details
    and current_run_collect_broker_details
)
```

7. 이전 실행 컬럼 또는 이전 snapshot JSON에 새 필드가 없는 legacy 데이터는 `True`로 해석한다.
8. OFF 최소 물건 객체도 현재 aggregator가 가격, 거래유형, article ID를 집계할 수 있으므로 aggregator는 필요한 경우에만 최소 수정한다.

**완료 조건**

- ON → OFF, OFF → ON 비교에서 관리비·입주일·옵션이 삭제 또는 추가된 것처럼 표시되지 않는다.
- OFF → OFF에서도 핵심 가격과 article ID 변화는 계속 기록된다.
- ON → ON의 기존 상세 변경 감지는 유지된다.
- 신규 매물과 사라진 매물 감지는 옵션과 무관하게 유지된다.

---

### 작업 6. 조회 API와 백엔드 XLSX에 수집 상태 노출

**대상 파일**

- 수정: `backend/app/schemas/listing.py`
- 수정: `backend/app/services/query_service.py`
- 수정: `backend/app/services/export_service.py`

**구현 내용**

1. `BrokerRegistration` 응답 모델에 다음 필드를 추가한다.

```python
detail_collected: bool = True
```

JSON에서는 기존 alias 정책에 따라 `detailCollected`로 반환한다.

2. `_broker_registrations()`는 snapshot JSON에서 다음과 같이 읽는다.

```python
detail_collected = details.get("detail_collected", True)
```

3. `detail_collected=False`이면 `market_details=None`으로 반환한다. 비어 있는 상세 객체를 실제 수집 결과처럼 만들지 않는다.
4. 중개사명, article ID, URL, Npay 여부, 행 설명 등 기본 등록정보는 그대로 반환한다.
5. 서버 XLSX의 `중개사등록` 시트 헤더에 `추가상세수집여부`를 추가한다.
6. 각 행에 다음 값을 쓴다.

- `detail_collected=True`: `Y`
- `detail_collected=False`: `N`
- legacy 필드 없음: `Y`

7. `N`인 행은 물건별 상세 JSON 열을 강제로 빈 값으로 출력한다. 승인된 범위의 7개 상세 영역은 다음과 같다.

```text
시세
거래
비용
관리비
단지
입지
추가 필드
```

8. 기본 등록정보 열과 article ID는 `N`이어도 정상 출력한다.

**완료 조건**

- API 소비자는 값의 부재와 의도적 미수집을 구분할 수 있다.
- 과거 snapshot은 `detailCollected=true`로 계속 조회된다.
- XLSX만 보고도 각 중개사 등록 물건의 상세 수집 여부를 알 수 있다.

---

### 작업 7. 자동 조사 스케줄에 동일 옵션 저장 및 전파

**대상 파일**

- 수정: `backend/app/schemas/schedule.py`
- 수정: `backend/app/services/schedule_service.py`
- 확인만 하고 불필요하면 변경하지 않음: `backend/app/api/routes/schedules.py`
- 변경하지 않음: `backend/app/tasks/scheduled_tasks.py`

**구현 내용**

1. 다음 schema에 `collect_broker_details`를 추가한다.

- `ScheduleCreate`: `bool = True`
- `SchedulePatch`: `bool | None = None`
- `ScheduleResponse`: `bool`
- `ScheduleRun`: `bool`

2. `ScheduleService.create()`는 새 스케줄에 선택값을 저장한다.
3. `ScheduleService.patch()`는 값이 전달된 경우에만 갱신한다.
4. 스케줄 응답 변환 함수는 DB 값을 반환한다.
5. `enqueue_due()`는 각 스케줄의 값을 분석 실행 생성에 전달한다.

```python
await analysis_service.create(
    source.source_url,
    collect_broker_details=schedule.collect_broker_details,
)
```

6. 생성된 `CrawlRun`이 스케줄의 당시 값을 복사해 독립적으로 보존하게 한다.
7. 과거 스케줄 실행 목록의 각 `ScheduleRun`에는 실제 실행의 값을 반환한다.
8. 스케줄 변경 이후에도 이미 생성된 과거 실행의 값은 바뀌지 않는다.

**완료 조건**

- 자동 조사도 수동 조사와 동일한 수집 분기를 사용한다.
- 사용자가 스케줄 옵션을 변경하면 이후 실행부터 적용된다.
- 실행 기록에서 당시 적용된 옵션을 확인할 수 있다.

---

### 작업 8. React 분석 요청 UI, API, 상태 흐름 구현

**대상 파일**

- 수정: `frontend/src/types/api.ts`
- 수정: `frontend/src/api/analyses.ts`
- 수정: `frontend/src/state/AnalysisProvider.tsx`
- 수정: `frontend/src/components/analysis/UrlAnalysisPanel.tsx`
- 수정: `frontend/src/pages/AnalysisPage.tsx`

**구현 내용**

1. API 요청 타입을 추가한다.

```typescript
export interface AnalysisCreateApi {
  sourceUrl: string
  collectBrokerDetails: boolean
}
```

2. `AnalysisAcceptedApi`와 이를 확장하는 상태 응답에 `collectBrokerDetails: boolean`을 추가한다.
3. 위치 인자 증가를 막기 위해 `createAnalysis()`를 객체 요청 방식으로 변경한다.

```typescript
export function createAnalysis(
  request: AnalysisCreateApi,
): Promise<AnalysisAcceptedApi>
```

4. `AnalysisProvider.startAnalysis()`도 같은 요청 객체를 받도록 변경한다.
5. `UrlAnalysisPanel`의 URL 입력 행 바로 아래에 체크박스를 배치한다.

- 라벨: `중개사 등록 물건 추가 상세정보 수집`
- 보조 설명: `각 중개사 매물의 시세·거래·비용·관리비·단지·입지 정보를 함께 수집합니다. 분석 시간이 더 걸릴 수 있습니다.`
- 초기값: `true`
- queued/running 상태: disabled

6. 제출할 때 URL과 선택값을 한 객체로 전달한다.
7. `AnalysisPage`는 같은 요청 객체를 real provider와 demo provider에 전달한다.
8. 서버가 반환한 `collectBrokerDetails`를 현재 실행에 실제 적용된 값으로 취급한다.
9. 409 `analysis_option_conflict`는 기존 오류 표시 영역에 사용자가 이해할 수 있는 문장으로 표시한다.

**완료 조건**

- 사용자는 URL 제출 전에 옵션을 바로 선택할 수 있다.
- 기본 동작은 지금과 동일하게 상세 수집 ON이다.
- 실행 중에는 선택값을 바꿔 현재 실행과 화면 상태가 어긋나지 않는다.
- 실제 API와 데모가 같은 입력 계약을 사용한다.

---

### 작업 9. React 스케줄, 매물 카드, 데모, 브라우저 XLSX 반영

**대상 파일**

- 수정: `frontend/src/types/api.ts`
- 수정: `frontend/src/types/realEstate.ts`
- 수정: `frontend/src/adapters/realEstate.ts`
- 수정: `frontend/src/pages/SchedulePage.tsx`
- 수정: `frontend/src/pages/ListingDetailPage.tsx`
- 수정: `frontend/src/state/useDemoDashboard.ts`
- 필요 시 수정: `frontend/src/state/DemoAnalysisContext.tsx`
- 수정: `frontend/src/mocks/demoRealEstate.ts`
- 수정: `frontend/src/utils/exportWorkbook.ts`
- 변경하지 않음: `frontend/src/components/export/ExcelDownloadButton.tsx`
- 변경하지 않음: `frontend/src/api/exports.ts`

**구현 내용**

#### 9.1 타입과 adapter

1. API 스케줄 타입에 다음 필드를 추가한다.

```typescript
collectBrokerDetails: boolean
```

`SchedulePatchApi`에서만 optional로 둔다.

2. 도메인 `ScheduleDraft`에 `collectBrokerDetails: boolean`을 추가한다.
3. API와 도메인 `BrokerRegistration`에 각각 다음 필드를 추가한다.

```typescript
detailCollected: boolean
```

4. `adaptRegistration()`이 값을 누락 없이 전달한다.

#### 9.2 스케줄 화면

1. `SchedulePage` draft 초기값에 `collectBrokerDetails: true`를 넣는다.
2. 기존 스케줄을 편집할 때 서버값을 draft로 복사한다.
3. create/patch 요청에 선택값을 포함한다.
4. URL 분석 화면과 같은 의미의 체크박스를 스케줄 폼에 배치한다.
5. 현재 스케줄 요약에는 다음 중 하나를 표시한다.

- `추가 상세 수집`
- `기본 정보만 수집`

6. 최근 자동 조사 실행 행에도 당시 적용값을 표시한다.

#### 9.3 매물 상세 카드

1. `RegistrationCard`는 `registration.detailCollected`를 먼저 확인한다.
2. `true`이면 현재의 상세정보 표현을 유지한다.
3. `false`이면 중개사명, article ID, URL, Npay 여부, 행 설명 등 기본 등록정보는 보여준다.
4. 상세 영역에는 다음 안내를 한 번만 표시한다.

```text
이 조사에서는 추가 상세정보를 수집하지 않았습니다.
```

5. 상세 미수집 상태에서 7개 영역이나 상세 파생값을 `-` 목록으로 길게 표시하지 않는다.
6. 그룹 공통 `apiMarket` fallback이 OFF registration을 legacy 데이터로 오인해 상세정보를 채우지 않도록 `detailCollected`를 우선 조건으로 사용한다.

#### 9.4 데모 모드

1. `startDemoAnalysis()`가 `collectBrokerDetails`를 받는다.
2. ON이면 현재 데모 데이터를 그대로 사용하고 registration에 `detailCollected=true`를 보장한다.
3. OFF이면 결과를 파생 복제해 다음 상태로 만든다.

```typescript
detailCollected: false
marketDetails: undefined
```

상세 슬라이드에서만 얻는 파생 필드도 화면에서 실제 수집된 것처럼 보이지 않도록 제거 또는 숨긴다.

4. 원본 mock 객체를 직접 변형하지 않는다. 다음 분석에 ON을 선택했을 때 원래 상세정보가 다시 보여야 한다.

#### 9.5 브라우저 XLSX

1. 데모용 `중개사등록` sheet에 `추가상세수집여부` 열을 추가한다.
2. `detailCollected`를 `Y` 또는 `N`으로 쓴다.
3. `N`인 행의 7개 상세 JSON 셀은 빈 값으로 만든다.
4. 기본 등록정보는 유지한다.
5. 현재 열 너비 배열을 새 열 수에 맞게 `41`개에서 `42`개로 조정한다.

**완료 조건**

- 즉시 분석과 스케줄 화면의 옵션 의미가 같다.
- 상세 미수집 매물은 결측치가 아니라 미수집 상태로 명확하게 보인다.
- 데모와 실제 서버 응답의 UX가 같다.
- 서버 XLSX와 브라우저 XLSX의 열 이름과 Y/N 의미가 같다.

---

### 작업 10. 구현 완료 후 실행할 집중 테스트

> 이 작업은 생산 코드 구현이 모두 끝난 뒤 진행한다. 아래 테스트 코드 작성 및 명령 실행은 사용자가 승인한 범위만 수행하며, 전체 테스트나 추가 URL 검증으로 확대하지 않는다.

**수정 또는 추가할 테스트 파일**

- 수정: `backend/tests/unit/test_model_constraints.py`
- 수정: `backend/tests/unit/test_analysis_service.py`
- 수정: `backend/tests/unit/test_crawl_scope.py`
- 수정: `backend/tests/unit/test_comparator.py`
- 수정: `backend/tests/unit/test_schedule_service.py`
- 수정: `backend/tests/integration/test_persistence.py`
- 수정: `backend/tests/integration/test_export.py`
- 필요 시 생성: `backend/tests/unit/test_query_broker_details.py`
- 수정: `frontend/src/tests/App.test.tsx`
- 수정: `frontend/src/tests/domain.test.ts`
- 필요 시 생성: `frontend/src/tests/exportWorkbook.test.ts`

#### 10.1 백엔드 집중 확인 항목

1. 모델과 schema 기본값이 `True`다.
2. 분석 요청 생략 시 ON, 명시 `false` 시 OFF가 `CrawlRun`에 저장된다.
3. 같은 URL의 활성 실행은 같은 옵션일 때만 재사용된다.
4. 다른 옵션이면 409용 `analysis_option_conflict`가 발생한다.
5. `CrawlScope.full()`이 옵션과 관계없이 full collection을 유지한다.
6. OFF 수집은 모든 broker row를 최소 객체로 만들고 `_collect_slide_article()`을 호출하지 않는다.
7. ON 수집은 기존 상세 호출 경로를 사용한다.
8. OFF에서도 표시 중개사 수와 고유 article ID 수가 다르면 실패한다.
9. 비교기가 ON/OFF 경계에서 관리비·입주일·옵션 허위 변화를 만들지 않는다.
10. 가격, article ID, 신규·삭제 변화는 OFF에서도 감지한다.
11. 스케줄 값이 생성된 `CrawlRun`에 복사된다.
12. query가 legacy를 `detailCollected=true`, OFF를 `false`로 반환한다.
13. 서버 XLSX의 `추가상세수집여부`와 상세 JSON 빈 값 규칙이 맞다.

#### 10.2 프런트엔드 집중 확인 항목

1. URL 폼 체크박스의 초기값이 checked다.
2. queued/running 중 체크박스가 disabled다.
3. OFF 제출 시 API와 demo에 `collectBrokerDetails: false`가 전달된다.
4. 스케줄 생성·수정·요약에 값이 유지된다.
5. `detailCollected=false` 카드가 안내문과 기본 등록정보만 보여준다.
6. 데모 OFF 실행 뒤 ON 실행을 해도 원본 상세정보가 복원된다.
7. 브라우저 XLSX가 Y/N 및 상세 JSON 빈 값 규칙을 지킨다.

#### 10.3 승인 후 사용할 최소 명령

백엔드에서는 관련 파일만 지정한다.

```powershell
Set-Location backend
python -m pytest `
  tests/unit/test_model_constraints.py `
  tests/unit/test_analysis_service.py `
  tests/unit/test_crawl_scope.py `
  tests/unit/test_comparator.py `
  tests/unit/test_schedule_service.py `
  tests/integration/test_persistence.py `
  tests/integration/test_export.py
```

프런트엔드에서도 관련 테스트 파일만 지정한다.

```powershell
Set-Location frontend
npm test -- src/tests/App.test.tsx src/tests/domain.test.ts src/tests/exportWorkbook.test.ts
```

신규 테스트 파일을 만들 필요가 없으면 실제 존재하는 관련 파일만 명령에 포함한다.

#### 10.4 실사이트 동작 확인 범위

- 사용자가 앞서 지시한 대로 아파트는 1곳만 사용한다.
- 같은 아파트에서 ON과 OFF의 차이만 확인한다.
- Chrome UI/CDP 경로만 사용한다.
- OFF에서는 중개사 등록 물건 수와 article ID를 모두 저장하면서 상세 슬라이드 클릭이 0회인지 확인한다.
- ON에서는 기존 규칙대로 중개사 상세정보가 저장되는지만 확인한다.
- 무작위 클릭 간격은 기존 사용자 지시인 1~3초를 유지한다.
- CAPTCHA, 로그인, 403, 429 또는 접근 제한이 나타나면 우회하지 않고 중단 상태를 보고한다.
- 다른 아파트나 전체 라이브 E2E 모음은 실행하지 않는다.

---

## 6. 구현 의존 순서

```text
작업 1 DB·도메인
  ├─> 작업 2 즉시 분석 API
  ├─> 작업 3 작업자·scope
  └─> 작업 7 스케줄 백엔드

작업 3 ─> 작업 4 Chrome UI 수집 분기
작업 1 ─> 작업 5 비교·저장
작업 1 ─> 작업 6 조회·서버 XLSX

작업 2 + 작업 6 ─> 작업 8 React 분석 UI
작업 6 + 작업 7 + 작업 8 ─> 작업 9 React 상세·스케줄·데모·XLSX

작업 1~9 완료 ─> 작업 10 승인된 집중 테스트
```

### 7. 구현 완료 판정 기준

- URL 분석 화면에서 기본 ON인 상세 수집 옵션을 선택할 수 있다.
- 옵션값이 API, DB, 작업 큐 이후 수집기까지 손실 없이 전달된다.
- OFF에서도 네이버에 등록된 모든 매물 그룹과 모든 중개사 등록 물건을 저장한다.
- OFF에서는 각 물건의 추가 상세 슬라이드를 열지 않는다.
- ON에서는 기존 상세 수집 결과를 유지한다.
- 자동 조사 스케줄이 선택값을 저장하고 매 실행에 적용한다.
- 상세 미수집 실행이 허위 삭제·변경 이력을 만들지 않는다.
- 매물 카드와 XLSX가 상세 수집 여부를 명시한다.
- 데모 모드에서도 같은 선택 UX를 확인할 수 있다.
- 구현과 무관한 기능, 직접 API 수집, 임의 제한값을 추가하지 않는다.

### 8. 이번 계획 단계에서 하지 않는 일

- 생산 코드 수정
- migration 실행
- 서버 실행
- 자동 테스트 실행
- 네이버 실사이트 접속
- Docker 실행
- Git commit 또는 push

---

# Optional Broker Detail Collection Implementation Plan

## English / AI-readable contract

### Goal

Add a default-on run and schedule option that controls only whether every broker article detail slide is opened. Turning it off must never reduce listing-group coverage, broker-row coverage, safe internal article-ID collection, or fail-closed count validation.

### Canonical names

```text
Database / Python run option: collect_broker_details
JSON / React run option: collectBrokerDetails
Snapshot / Python article state: detail_collected
API / React article state: detailCollected
```

Missing legacy values mean `true`.

### Required implementation sequence

1. Add Alembic columns to `crawl_runs` and `crawl_schedules`; add ORM and captured-model fields.
2. Extend analysis request/response contracts and persist the option on `CrawlRun`.
3. Load the option by `run_id` and pass it through `CrawlScope`.
4. Branch only the per-broker detail-slide action in the Chrome UI collector.
5. Preserve all broker rows as minimal `BrokerArticleDetail` objects when disabled.
6. Gate detail-derived comparisons unless both adjacent runs collected details.
7. Expose `detailCollected` through query APIs and server XLSX.
8. Persist and propagate the option through schedules and schedule-run history.
9. Add React URL, schedule, detail-card, demo, and browser-XLSX behavior.
10. After production implementation, run only the separately approved focused tests and one-apartment live check.

### API and persistence contract

```json
POST /api/analyses
{
  "sourceUrl": "https://fin.land.naver.com/map?...",
  "collectBrokerDetails": true
}
```

- Omitted option defaults to `true`.
- Same URL + same active option reuses the active run.
- Same URL + different active option returns HTTP 409 with `analysis_option_conflict`.
- `AnalysisAccepted`, `AnalysisStatus`, schedule responses, and schedule-run history echo the persisted value.
- Queue messages still carry only `run_id`; workers reload the option from the database.

### Collector invariants

Both modes must:

1. scan every non-empty trade type;
2. collect every displayed listing group;
3. expand every broker group;
4. collect all lazy-loaded broker rows;
5. validate every safe internal article target;
6. enforce displayed group and broker counts;
7. persist all valid article IDs for new/removed tracking.

Enabled mode retains the current Npay/general detail-slide workflow.

Disabled mode must not click any article-detail trigger. It creates a minimal record with:

```text
article_id
article_url
provider
is_npay
description
captured_at
detail_collected=false
market_details=None
```

### Comparison invariant

Always compare core fields and article presence. Compare management fee, move-in date, option tags, and any other detail-only value only when both the previous and current runs have `collect_broker_details=true`.

### Presentation invariant

- A registration with `detailCollected=false` shows its basic broker/article data and the Korean notice: `이 조사에서는 추가 상세정보를 수집하지 않았습니다.`
- It must not render long placeholder lists for uncollected detail sections.
- Both XLSX implementations add `추가상세수집여부` with `Y` or `N`.
- Detail JSON cells are blank when the value is `N`.

### Execution constraints

- Chrome UI/CDP only; no Naver API or direct HTTP acquisition.
- No arbitrary listing limit.
- No unrelated refactor or validation.
- No broad test suite without user approval.
- At most one apartment for the approved live behavior check.
- No commit or push.
