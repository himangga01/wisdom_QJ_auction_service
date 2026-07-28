# 1단계: 데이터 조회·비교 정합성 수정계획

## 한국어 계획

### 목표

조사 아파트가 100개를 넘어도 전체 검색·페이지 이동·선택이 가능하게 하고, 대시보드가 사용자가 고른 아파트 한 곳을 정확히 조회하도록 수정한다. 상세 슬라이드에서 수집한 단지 기본정보를 아파트 데이터로 승격하며, 선택 조사일의 실제 매물과 중개사 등록만 반환하도록 날짜 조회 의미를 바로잡는다. 날짜 비교에서는 서버의 `missing`·`removed` 판정과 화면 표현을 일치시키고 상세 변경 필드를 모두 강조한다.

### 현재 문제와 수정 원칙

| 문제 | 현재 원인 | 수정 원칙 |
|---|---|---|
| 101번째 이후 아파트가 보이지 않음 | `AnalysisProvider`가 첫 페이지 100건을 전체 목록처럼 사용 | `/api/apartments`의 `items/page/pageSize/total`을 화면별로 직접 사용 |
| 서버 검색을 활용하지 않음 | `ApartmentsPage`가 브라우저 배열만 필터링 | 검색어·페이지·페이지 크기를 API로 전달 |
| 대시보드 선택 제한 | 첫 100건으로 native `<select>` 구성 | 서버 검색형 아파트 picker 사용 |
| 단지 기본정보가 빈 값 | `ComplexDetail(details={})`를 저장 | 매물 상세의 `MarketDetails.complex`를 canonical 아파트 정보로 승격 |
| 사라진 매물이 다시 active처럼 보임 | 선택일 이전 최신 snapshot을 계속 반환 | 선택 run에서 실제 생성된 snapshot과 별도 absence 상태를 분리 |
| 과거 중개사 등록이 잔류 | 중개사도 선택일 이전 최신 snapshot을 사용 | 실제 선택 run의 등록 snapshot만 기본 목록에 포함 |
| 비교 강조가 4개 필드뿐 | 프런트 비교 union이 가격·월세·층·방향으로 제한 | 기본·상세 집계 필드 전체로 확대 |
| 화면 삭제 의미가 서버와 다름 | 화면은 한 번 사라지면 삭제로 계산 | `missing`과 연속 2회 후 `removed`를 분리 |

### 선행·후행 관계

- 이 단계가 먼저 `selectedApartment` 전체 객체와 전체 검색 계약을 제공한다.
- 2단계는 이 계약을 사용해 선택 상태 복원과 명시적인 Excel 대상 선택 UI를 완성한다.
- 1단계에서는 Excel 버튼이 첫 100개 배열을 참조할 필요가 없도록 source ID를 전달할 수 있는 상태까지만 보장한다.
- 인증과 사용자별 데이터 분리는 4단계 범위이며 이 단계의 API에는 아직 사용자 조건을 추가하지 않는다.

### 신규 파일

| 파일 | 책임 |
|---|---|
| `backend/app/domain/apartment_details.py` | 단지 상세 label을 canonical 필드로 정규화하고 여러 중개사 값을 병합 |
| `backend/alembic/versions/0006_promote_apartment_basic_details.py` | `apartments.details_json`, `details_updated_at` 추가 |
| `backend/tests/integration/test_query_service.py` | 페이지네이션과 날짜별 실재 매물 조회 계약 |
| `frontend/src/components/dashboard/DashboardApartmentPicker.tsx` | 전체 서버 검색·더보기·선택 UI |
| `frontend/src/components/ui/Pagination.tsx` | 공용 페이지 이동과 page size 선택 |
| `frontend/src/tests/ApartmentsPagination.test.tsx` | 목록 서버 검색·페이지 이동 계약 |
| `frontend/src/tests/DashboardApartmentPicker.test.tsx` | 첫 페이지 밖 아파트 선택 계약 |

### 수정 파일

| 파일 | 수정 내용 |
|---|---|
| `backend/app/models/entities.py` | `Apartment` 최신 canonical details 저장 |
| `backend/app/models/__init__.py` | 변경 모델 export 확인 |
| `backend/app/crawler/types.py` | `ComplexDetail.details` typed JSON 허용 |
| `backend/app/crawler/browser.py` | 상세 슬라이드의 단지정보·주소 병합 |
| `backend/app/domain/comparator.py` | 비교 가능한 필드 확대 |
| `backend/app/services/persistence_service.py` | 단지정보 병합·빈 값 보호·변경 이벤트 확대 |
| `backend/app/services/query_service.py` | exact-run 매물, absence 상태, exact-run 중개사 조회 |
| `backend/app/services/export_service.py` | canonical 아파트 기본정보 출력 |
| `backend/app/schemas/apartment.py` | 선택 아파트·회차 데이터 계약 유지 |
| `backend/app/schemas/dashboard.py` | 전체 개수 추가, capped recent 목록 의존 제거 |
| `backend/app/schemas/listing.py` | `absentItems`, `removedAt`, 비교 상태 계약 |
| `backend/app/api/routes/apartments.py` | 기존 query/page/pageSize/status 전달 유지 및 absence 응답 |
| `frontend/src/types/api.ts` | dashboard count, listing absence, canonical detail 타입 |
| `frontend/src/types/realEstate.ts` | deposit·absence·확대 changed fields |
| `frontend/src/api/apartments.ts` | 명시적 페이지 인자와 query key |
| `frontend/src/state/AnalysisProvider.tsx` | 전체 배열 대신 명시적 선택 아파트 객체 |
| `frontend/src/pages/AnalysisPage.tsx` | 완료된 complex ID로 선택 객체 확정 |
| `frontend/src/pages/ApartmentsPage.tsx` | 서버 검색·페이지네이션 |
| `frontend/src/pages/DashboardPage.tsx` | 전체 검색 picker와 정확한 source dashboard |
| `frontend/src/pages/SchedulePage.tsx` | 선택 아파트 객체의 source 사용 |
| `frontend/src/pages/ApartmentDetailPage.tsx` | actual/absent 목록과 확대 비교 |
| `frontend/src/pages/ListingDetailPage.tsx` | removed 상세 시각 표시 |
| `frontend/src/adapters/realEstate.ts` | deposit·canonical details·absence 변환 |
| `frontend/src/utils/listingHistory.ts` | missing/removed 및 확대 필드 비교 |
| `frontend/src/components/research/ListingComparisonBoard.tsx` | 모든 변경 사양 강조 |

### API 계약

기존 아파트 페이지 API를 전체 목록의 유일한 검색 계약으로 사용한다.

```http
GET /api/apartments?query={query}&page={page}&pageSize={pageSize}
```

```ts
interface ApartmentPageApi {
  items: ApartmentSummaryApi[]
  page: number
  pageSize: number
  total: number
}
```

대시보드 응답에는 정확한 전체 개수를 추가한다.

```py
class DashboardResponse(ApiSchema):
    source_id: UUID
    source_url: str
    run_id: UUID
    collected_at: str
    apartment_count: int
    apartment: ApartmentDetail
    listings: list[ListingSummary]
```

기존 `recentApartments`는 한 번의 호환 기간에는 빈 배열 또는 deprecated 필드로 유지할 수 있지만 신규 프런트는 사용하지 않는다. 호환 소비자가 없음을 확인한 뒤 제거한다.

선택 조사일 매물 응답은 실제 관측과 미관측 상태를 분리한다.

```py
class ListingAbsence(ApiSchema):
    group_id: UUID
    status: Literal["missing", "removed"]
    last_snapshot: ListingSummary
    detected_at: str
    removed_at: str | None = None

class ListingPage(ApiSchema):
    complex_id: str
    run_id: UUID
    collected_at: str
    items: list[ListingSummary]
    absent_items: list[ListingAbsence]
```

불변조건:

- `items`는 선택 run에서 실제 `ListingSnapshot`이 생성된 매물만 포함한다.
- `absentItems`의 `missing`은 완료 조사에서 1회 미관측된 상태다.
- `removed`는 완료 조사에서 연속 2회 미관측된 경우에만 포함한다.
- partial 실행은 새로운 missing/removed 근거로 사용하지 않는다.
- removed 상세는 마지막 실제 snapshot과 삭제 확인 시각을 반환한다.

### 선택 아파트 상태 계약

`AnalysisProvider`는 전체 데이터 배열 대신 현재 선택을 명시적으로 보관한다.

```ts
interface AnalysisProviderValue {
  selectedApartment: ApartmentSummaryApi | null
  selectedApartmentId: string | null
  selectApartment(apartment: ApartmentSummaryApi): void
  refreshSelectedApartment(): Promise<void>
}
```

- 현재 페이지에 선택 아파트가 없다는 이유로 첫 항목으로 변경하지 않는다.
- URL 조사 완료 후 `getAnalysisResult()`의 `naverComplexId`로 `getApartment()`를 호출해 객체를 확정한다.
- 대시보드, 스케줄, Excel은 `selectedApartment.sourceId`를 사용한다.
- 전체 아파트 존재 여부는 `GET /apartments?page=1&pageSize=1`의 `total`로 판단한다.

### 세부 작업 순서

#### 1-1. 조사 아파트 서버 페이지네이션

1. `ApartmentsPage`가 자체 `query`, `page`, `pageSize` 상태를 가진다.
2. 실데이터 모드에서 `getApartments({ query, page, pageSize })`를 직접 호출한다.
3. 기본 page size는 20, 선택지는 20·50·100으로 고정한다.
4. 검색어 또는 page size가 바뀌면 page를 1로 초기화한다.
5. 서버 `total`을 `저장된 아파트 n개`에 사용한다.
6. 현재 page가 삭제나 검색 결과 변경으로 마지막 page를 넘으면 유효한 마지막 page로 교정한다.
7. 검색 결과 없음과 전체 데이터 없음 화면을 구분한다.
8. 데모 모드는 현재 작은 정적 배열 방식을 유지한다.

#### 1-2. 대시보드 전체 검색 picker

1. 기존 첫 100건 native select를 제거한다.
2. `DashboardApartmentPicker`에서 검색어로 첫 20건을 조회한다.
3. `더 보기`를 누르면 다음 서버 page를 가져와 중복 complex ID 없이 합친다.
4. 현재 선택 아파트가 검색 결과에 없더라도 picker 상단 선택값은 유지한다.
5. 항목 선택 시 전체 `ApartmentSummaryApi`를 provider에 전달한다.
6. 선택 객체의 `sourceId`로 `/dashboard?sourceId=`를 호출한다.
7. `조사한 아파트 n개 전체 보기`의 n은 첫 페이지 길이가 아니라 API `total`을 사용한다.
8. dashboard API가 더 이상 `recentApartments` 100건을 생성하기 위해 추가 SQL을 실행하지 않도록 정리한다.

#### 1-3. 단지 기본정보 canonical 승격

다음 canonical key를 사용한다.

```text
household_count
building_count
approval_date
parking_count
parking_per_household
heating
entrance_type
floor_area_ratio
building_coverage_ratio
management_office_phone
builders
```

1. `apartment_details.py`에 한글 label과 data-field alias 매핑을 둔다.
2. 여러 중개사 상세에서 같은 key·value가 반복되면 하나로 만든다.
3. 충돌하면 article ID 순서상 첫 번째 비어 있지 않은 값을 저장하고 `apartment_detail_conflict:{key}` warning을 남긴다.
4. `PlaywrightNaverLandCollector.collect()`이 성공한 모든 `article.market_details.complex`를 병합한다.
5. 병합 결과를 `payload.apartment.details`에 넣는다.
6. 명시적 주소 후보가 없으면 빈 문자열을 보내되 persistence가 기존 주소를 지우지 못하게 한다.
7. `Apartment.details_json`에는 최신 non-empty canonical 값을 병합 저장한다.
8. `ApartmentSnapshot.details_json`에는 해당 run에서 사용할 canonical 결과를 저장한다.
9. 과거 run 조회에서 미래에 알게 된 값을 노출하지 않도록 snapshot 시점 값을 우선한다.
10. 상세수집 OFF run은 기존 최신 기본정보를 지우지 않는다.

#### 1-4. 선택 run의 실제 매물·중개사 조회

1. `_as_of_listing_rows()`를 역할별 함수로 분리한다.
2. `_listing_rows_for_run()`은 `ListingSnapshot.run_id == selected_run.id`만 조회한다.
3. `_absence_states_as_of_run()`은 선택 source의 `ChangeEvent`를 사용해 missing/removed/restored 상태를 계산한다.
4. `_broker_registrations_for_run()`은 기본적으로 `BrokerArticleSnapshot.run_id == selected_run.id`만 반환한다.
5. `QueryService.listing()`이 removed 상세 요청을 받으면 마지막 prior snapshot과 removed event 시각을 결합한다.
6. 선택 시점 응답의 `lastSeenAt`에는 현재 `ListingGroup.last_seen_at`이 아니라 해당 시점의 마지막 관측 시각을 사용한다.
7. `status=removed` 필터는 `absentItems`의 removed 항목에 적용한다.

#### 1-5. 변경 비교 필드 확대

백엔드 변경 이벤트 비교 필드:

```text
price
deposit
monthlyRent
building
floor
direction
supplyAreaM2
exclusiveAreaM2
managementFee
moveInDate
roomBathroom
loan
optionTags
registrationCount
articleIds
```

1. `ComparableListing`, `_FIELDS`, `_DETAIL_FIELDS`를 확장한다.
2. 이전·현재 모두 상세수집 ON일 때만 관리비·입주·방욕실·융자·옵션을 비교한다.
3. `ChangeEvent.changed_fields_json`과 before/after JSON은 기존 JSON 컬럼을 사용하므로 migration을 추가하지 않는다.
4. 프런트 `ListingGroup`에 deposit과 absence metadata를 보존한다.
5. 배열은 정렬·중복 제거 후 비교하고 null·빈 문자열 차이를 정규화한다.
6. 비교 보드에서 관리비·입주·방욕실·융자·옵션·중개사 등록 수까지 실제로 강조한다.
7. before에는 있고 after actual items에는 없을 때 absence 상태가 `missing`이면 `일시 미노출`, `removed`이면 `삭제`로 분류한다.
8. partial 실행에는 removed 표시를 만들지 않는다.

#### 1-6. 후속 화면 연계

1. `AnalysisPage`는 완료 후 선택 객체를 서버에서 다시 가져온다.
2. `SchedulePage`는 첫 100건 fallback 대신 `selectedApartment.sourceId`만 사용한다.
3. `ApartmentDetailPage`는 `items`와 `absentItems`를 날짜별로 분리 보관한다.
4. `ListingDetailPage`는 removed 상세에서 마지막 노출과 삭제 확인 시각을 보여준다.
5. Excel의 최종 target selector는 2단계에서 구현하되, 이 단계에서 source ID가 선택 객체로부터 항상 제공되도록 한다.

### DB 변경

`0006_promote_apartment_basic_details.py`:

```py
op.add_column(
    "apartments",
    sa.Column(
        "details_json",
        sa.JSON(),
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
)
op.add_column(
    "apartments",
    sa.Column("details_updated_at", sa.DateTime(timezone=True), nullable=True),
)
```

- PostgreSQL과 SQLite batch migration을 모두 지원한다.
- 기존 아파트는 `{}`로 시작한다.
- downgrade는 `details_updated_at`, `details_json` 순으로 제거한다.
- migration 실행은 구현 완료 후 별도 사용자 승인을 받는다.

### 완료 기준

- 101개 이상 저장돼도 임의 페이지 이동과 전체 서버 검색이 가능하다.
- 대시보드에서 첫 페이지 밖의 아파트를 검색해 정확한 source dashboard를 표시한다.
- 세대수·동수·승인일·주차·난방 등 실제 수집값이 아파트 상세에 나타난다.
- 상세수집 OFF 재조사가 기존 기본정보를 지우지 않는다.
- 선택 조사일 목록에는 그 run에서 실제 관측된 매물과 중개사 등록만 나온다.
- 1회 미관측과 확정 삭제가 서로 다른 색상·문구로 표시된다.
- 확정 삭제 후 이후 날짜에서 과거 매물이 active로 되살아나지 않는다.
- 날짜 비교가 관리비·입주·옵션·방욕실·융자·중개사 구성까지 강조한다.

### 실행 시 제한

- 기능 코드와 migration은 이 문서 작성 단계에서 수정하지 않는다.
- 테스트·빌드·migration·브라우저·Docker 실행은 별도 승인 전에는 수행하지 않는다.
- 테스트 승인 시에도 아래 명시된 집중 테스트부터 실행한다.
- 운영 네이버 URL 전수 조사는 이 단계의 기본 검증 범위에 넣지 않는다.

---

# Stage 1 Data Pagination and Historical Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` after explicit implementation approval. Track work with checkbox (`- [ ]`) syntax.

**Goal:** Remove the 100-apartment ceiling, make selection server-backed, promote complex facts, and return historically correct observed and absent listings.

**Architecture:** The existing paginated apartment API becomes the only collection-search contract. Selection stores one explicit `ApartmentSummaryApi`, not a capped pseudo-global array. Listing queries separate exact-run observations from lifecycle absence events.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL, SQLite, React 19, TypeScript 6, TanStack Query 5, Tailwind CSS 4.

## Global Constraints

- `items` means actually observed in the selected run.
- `missing` is not `removed`; removal requires two consecutive completed misses.
- Partial runs never advance absence state.
- Do not leak future apartment or listing values into a historical run.
- Do not run tests, migrations, builds, browsers, Docker, commits, or pushes without separate approval.
- Stage 2 owns the final Excel target-selector UX.

### Task 1: Explicit selected-apartment state

**Files:**

- Modify: `frontend/src/state/AnalysisProvider.tsx`
- Modify: `frontend/src/pages/AnalysisPage.tsx`
- Modify: `frontend/src/pages/SchedulePage.tsx`
- Modify: `frontend/src/api/apartments.ts`

**Interfaces:**

```ts
selectedApartment: ApartmentSummaryApi | null
selectApartment(apartment: ApartmentSummaryApi): void
refreshSelectedApartment(): Promise<void>
```

- [ ] Stop treating the first 100 items as the complete apartment collection.
- [ ] Keep selection even when the selected item is outside the current page.
- [ ] Resolve the completed analysis complex ID through `getApartment`.
- [ ] Make downstream source selection consume `selectedApartment.sourceId`.

### Task 2: Server-paginated apartment page

**Files:**

- Create: `frontend/src/components/ui/Pagination.tsx`
- Modify: `frontend/src/pages/ApartmentsPage.tsx`
- Create after approval: `frontend/src/tests/ApartmentsPagination.test.tsx`

**Interfaces:**

```ts
getApartments({ query, page, pageSize }): Promise<ApartmentPageApi>
```

- [ ] Add server query, page, and page-size state.
- [ ] Use page sizes 20, 50, and 100.
- [ ] Reset page to 1 after query or page-size changes.
- [ ] Render `total`, current page, last page, previous, and next controls.
- [ ] Separate empty-dataset from empty-search-result states.

### Task 3: Searchable dashboard picker

**Files:**

- Create: `frontend/src/components/dashboard/DashboardApartmentPicker.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/query_service.py`
- Modify: `frontend/src/types/api.ts`
- Create after approval: `frontend/src/tests/DashboardApartmentPicker.test.tsx`

**Interfaces:**

```ts
onSelect(apartment: ApartmentSummaryApi): void
```

- [ ] Search the server in pages of 20.
- [ ] Append deduplicated “load more” results.
- [ ] Query the dashboard with the chosen source ID.
- [ ] Add exact `apartmentCount` to the dashboard contract.
- [ ] Stop generating or consuming a capped recent-apartment list.

### Task 4: Canonical apartment details

**Files:**

- Create: `backend/app/domain/apartment_details.py`
- Create: `backend/alembic/versions/0006_promote_apartment_basic_details.py`
- Modify: `backend/app/models/entities.py`
- Modify: `backend/app/crawler/types.py`
- Modify: `backend/app/crawler/browser.py`
- Modify: `backend/app/services/persistence_service.py`
- Modify: `backend/app/services/query_service.py`
- Modify: `backend/app/services/export_service.py`
- Modify: `frontend/src/adapters/realEstate.ts`

**Interfaces:**

```py
def normalize_apartment_details(
    values: dict[str, str],
) -> tuple[dict[str, object], list[str]]

def merge_apartment_details(
    observations: list[tuple[str, dict[str, str]]],
) -> tuple[dict[str, object], list[str]]
```

- [ ] Implement deterministic alias normalization and conflict warnings.
- [ ] Promote per-article complex facts into the crawl payload.
- [ ] Add current canonical details to `Apartment`.
- [ ] Merge only non-empty values and protect prior address/details.
- [ ] Prefer historical snapshot facts when reading historical runs.

### Task 5: Exact-run listing and absence APIs

**Files:**

- Modify: `backend/app/schemas/listing.py`
- Modify: `backend/app/services/query_service.py`
- Modify: `backend/app/api/routes/apartments.py`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/adapters/realEstate.ts`
- Modify: `frontend/src/pages/ApartmentDetailPage.tsx`
- Modify: `frontend/src/pages/ListingDetailPage.tsx`
- Create after approval: `backend/tests/integration/test_query_service.py`

**Interfaces:**

```py
async def _listing_rows_for_run(...)
async def _absence_states_as_of_run(...)
async def _broker_registrations_for_run(...)
```

- [ ] Return exact-run listing and broker snapshots as normal items.
- [ ] Return missing and removed lifecycle records separately.
- [ ] Resolve removed details from the last prior observation.
- [ ] Prevent current `last_seen_at` from leaking into historical responses.

### Task 6: Full comparison field coverage

**Files:**

- Modify: `backend/app/domain/comparator.py`
- Modify: `backend/app/services/persistence_service.py`
- Modify: `frontend/src/types/realEstate.ts`
- Modify: `frontend/src/utils/listingHistory.ts`
- Modify: `frontend/src/components/research/ListingComparisonBoard.tsx`
- Test after approval: `backend/tests/unit/test_comparator.py`
- Test after approval: `frontend/src/tests/domain.test.ts`

- [ ] Expand backend comparable fields and before/after payloads.
- [ ] Gate detail-derived comparisons on both runs collecting details.
- [ ] Preserve deposit and absence state in frontend adapters.
- [ ] Distinguish temporary missing from confirmed removal.
- [ ] Highlight every rendered specification whose value changed.

### Task 7: Approved verification gate

**Files:**

- Test: `backend/tests/integration/test_query_service.py`
- Test: `backend/tests/integration/test_persistence.py`
- Test: `backend/tests/unit/test_comparator.py`
- Test: `backend/tests/integration/test_export.py`
- Test: `frontend/src/tests/ApartmentsPagination.test.tsx`
- Test: `frontend/src/tests/DashboardApartmentPicker.test.tsx`
- Test: `frontend/src/tests/domain.test.ts`

- [ ] Ask for approval after implementation.
- [ ] If approved, run only focused pagination, history, aggregation, comparison, and source-export tests.
- [ ] Request separate approval before any migration execution, full suite, live Naver crawl, or Docker run.
- [ ] Commit only when separately requested.
