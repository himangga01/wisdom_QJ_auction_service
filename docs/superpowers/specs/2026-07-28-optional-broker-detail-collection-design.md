# 중개사 등록 물건 추가 상세정보 선택 수집 설계

## 한국어

### 1. 목표

사용자가 네이버 부동산 URL 조사를 시작할 때 중개사가 등록한 각 물건의 추가 상세 슬라이드까지 수집할지 선택할 수 있게 한다.

- 기본값은 기존 동작과 같은 `상세정보 수집 켜짐`이다.
- 상세정보 수집을 꺼도 아파트 매물 그룹, 중개사 등록 행, 네이버 매물번호와 기본 등록 정보는 모두 수집한다.
- 상세정보 수집을 끄면 각 중개사 물건의 상세 슬라이드는 열지 않는다.
- 자동 조사 스케줄에도 같은 선택값을 저장하고 반복 실행에 적용한다.
- 상세정보를 의도적으로 수집하지 않은 실행이 관리비·입주일·옵션 삭제로 잘못 판정되지 않게 한다.

### 2. 용어와 필드명

| 구분 | 필드명 | 의미 |
|---|---|---|
| Python·DB | `collect_broker_details` | 실행 또는 스케줄에서 중개사 물건별 추가 상세를 수집할지 여부 |
| JSON·React | `collectBrokerDetails` | API와 프런트엔드에서 사용하는 camelCase 이름 |
| 물건 스냅샷 | `detail_collected` / `detailCollected` | 해당 중개사 물건 스냅샷이 상세 슬라이드를 실제로 열어 수집됐는지 여부 |

`collect_broker_details`와 `detail_collected`의 기본값은 모두 `true`로 둔다. 기존 실행과 기존 JSON 스냅샷은 상세 수집이 수행된 데이터이므로, 필드가 없는 과거 데이터도 `true`로 해석한다.

### 3. 사용자 경험

#### 3.1 URL 조사 화면

네이버 URL 입력 행 바로 아래에 체크박스형 옵션 행을 배치한다.

- 제목: `중개사 등록 물건 추가 상세정보 수집`
- 설명: `각 중개사 매물의 시세·거래·비용·관리비·단지·입지 정보를 함께 수집합니다. 분석 시간이 더 걸릴 수 있습니다.`
- 기본 상태: 켜짐
- 조사 요청이 대기 또는 실행 중일 때: 비활성화

별도 모달이나 고급 설정 화면을 만들지 않는다. URL 입력과 같은 폼에서 한 번에 선택하고 분석을 시작한다.

#### 3.2 스케줄 화면

자동 조사 설정 폼에도 같은 체크박스를 배치한다.

- 새 스케줄 기본값은 켜짐이다.
- 기존 스케줄은 DB 기본값에 따라 켜짐으로 표시한다.
- 스케줄 수정 시 변경된 값이 이후 실행부터 적용된다.
- 현재 스케줄 요약에도 `추가 상세 수집` 또는 `기본 정보만 수집` 상태를 표시한다.

#### 3.3 매물 상세 화면

중개사 등록 카드마다 `detailCollected`를 확인한다.

- `true`: 현재와 같이 정제된 기본 정보와 7개 상세 섹션을 표시한다.
- `false`: 기본 등록 정보는 표시하고, 상세 영역에는 `이 조사에서는 추가 상세정보를 수집하지 않았습니다.` 안내를 표시한다.
- 빈 상세 필드를 실제로 값이 없는 정보처럼 표현하지 않는다.

#### 3.4 XLSX

`중개사등록` 시트에 `추가상세수집여부` 열을 추가한다.

- 상세 수집 실행: `Y`
- 기본 정보만 수집한 실행: `N`
- `N`인 행의 물건별 금융·실거래·비용·관리비·단지·입지·추가필드 JSON 열은 빈 값으로 출력한다.

### 4. API 계약

#### 4.1 분석 생성

`POST /api/analyses`

```json
{
  "sourceUrl": "https://fin.land.naver.com/map?...",
  "collectBrokerDetails": true
}
```

`collectBrokerDetails`를 생략하면 `true`로 처리한다.

`AnalysisAccepted`와 `AnalysisStatus`에도 실제 적용된 `collectBrokerDetails`를 반환한다. 프런트엔드는 서버가 적용한 값을 기준으로 현재 실행 상태를 표시할 수 있다.

같은 URL에 이미 활성 실행이 있을 때:

- 요청 옵션이 활성 실행과 같으면 기존 실행을 반환한다.
- 요청 옵션이 다르면 기존 실행을 조용히 재사용하지 않고 HTTP `409`와 `analysis_option_conflict`를 반환한다.

#### 4.2 스케줄

`ScheduleCreate`, `SchedulePatch`, `ScheduleResponse`에 `collectBrokerDetails`를 추가한다.

```json
{
  "sourceId": "uuid",
  "cadence": "daily",
  "timeOfDay": "09:00",
  "timezone": "Asia/Seoul",
  "enabled": true,
  "collectBrokerDetails": true
}
```

스케줄러가 실행을 생성할 때 스케줄의 값을 새 `CrawlRun.collect_broker_details`로 복사한다.
`ScheduleRun`에도 각 실행에 실제 적용된 값을 반환해 과거 실행 방식을 확인할 수 있게 한다.

### 5. 데이터베이스

새 Alembic migration에서 다음 열을 추가한다.

```text
crawl_runs.collect_broker_details BOOLEAN NOT NULL DEFAULT TRUE
crawl_schedules.collect_broker_details BOOLEAN NOT NULL DEFAULT TRUE
```

실행별 선택은 `TrackedSource`에 저장하지 않는다. 같은 URL도 실행마다 사용자가 다른 선택을 할 수 있기 때문이다.

스케줄별 선택은 `CrawlSchedule`에 저장한다. 반복 실행이 생성될 때마다 사용자가 저장한 옵션을 그대로 사용한다.

### 6. 백그라운드 작업 데이터 흐름

```text
URL 조사 폼
  -> POST /api/analyses { sourceUrl, collectBrokerDetails }
  -> AnalysisService.create()
  -> CrawlRun.collect_broker_details 저장
  -> dispatcher.enqueue(run_id)
  -> _claim_run(run_id)에서 URL과 옵션 조회
  -> CrawlScope.full(collect_broker_details=...)
  -> PlaywrightNaverLandCollector.collect()
```

Celery와 로컬 dispatcher에는 기존처럼 `run_id`만 전달한다. 실행 옵션은 DB에서 다시 읽으므로 프로세스 재시작과 큐 지연에도 값이 유실되지 않는다.

### 7. 크롤러 동작

#### 7.1 공통 동작

옵션과 관계없이 다음 동작은 항상 수행한다.

1. 매매·전세·월세 표시 건수를 읽는다.
2. 모든 매물 그룹을 순회한다.
3. `중개사 n곳에서 등록했어요`를 펼친다.
4. 지연 로딩된 모든 중개사 등록 행을 수집한다.
5. 네이버 내부 `/articles/{articleId}` 경로와 표시 중개사 수를 검증한다.
6. 매물번호 기준 신규·유지·삭제 판정을 수행한다.

상세 수집을 꺼도 전수 건수 검사와 fail-closed 정책은 약화하지 않는다.

#### 7.2 상세정보 수집 켜짐

현재 동작을 유지한다.

- Npay 행은 `Npay 부동산에서 보기`만 클릭한다.
- 일반 행은 네이버 내부 `매물 보러가기`를 클릭한다.
- 상세 슬라이드에서 기본 상세와 `market_details`를 파싱한다.
- `BrokerArticleDetail.detail_collected=true`로 저장한다.

#### 7.3 상세정보 수집 꺼짐

각 중개사 행의 상세 슬라이드를 열지 않는다.

확장된 중개사 행에서 다음 최소 정보를 사용해 `BrokerArticleDetail`을 만든다.

- `article_id`
- 검증된 네이버 내부 `article_url`
- `provider`
- `is_npay`
- 행에 표시된 `description`
- `captured_at`
- `detail_collected=false`
- `market_details=None`

제공처가 화면에 없으면 기존 정책대로 `미표시`와 `provider_missing` 경고를 기록한다. 최소 물건 객체를 만든 뒤에만 `seen_article_ids`에 추가한다.

### 8. 저장과 조회

`BrokerArticleSnapshot.details_json`에 `detail_collected`를 함께 저장한다. 별도의 물건 스냅샷 열은 추가하지 않는다.

내부 조회 API는 다음 규칙을 사용한다.

- 신규 스냅샷: JSON의 `detail_collected`를 읽는다.
- 과거 스냅샷: 필드가 없으면 `true`로 처리한다.
- 상세 미수집 스냅샷: 상세 필드는 `null` 또는 빈 컬렉션으로 반환하되 `detailCollected=false`를 반드시 함께 반환한다.

### 9. 비교와 변경 이력

상세정보를 끈 실행의 빈 값은 `정보 삭제`가 아니라 `미수집`이다.

변경 비교는 다음처럼 분리한다.

| 비교 항목 | 상세 수집 OFF에서도 비교 |
|---|---|
| 매물 그룹 존재·삭제 | 예 |
| 네이버 매물번호 집합 | 예 |
| 거래유형·가격·보증금·월세 | 예 |
| 동·층·방향·면적 | 예 |
| 관리비 | 아니요 |
| 입주 가능일 | 아니요 |
| 옵션 | 아니요 |
| 상세 시세·비용·단지·입지 필드 | 아니요 |

상세 파생 필드는 이전 실행과 현재 실행이 모두 `collect_broker_details=true`일 때만 변경 비교에 포함한다. 어느 한쪽이라도 `false`이면 상세 파생 필드를 `changed_fields`에서 제외한다.

상세 수집 OFF 실행 뒤 다시 ON으로 실행하더라도, OFF 실행의 빈 값 때문에 허위 변경 이벤트를 만들지 않는다.

### 10. 오류 처리

- 활성 실행 옵션 충돌: `analysis_option_conflict`, HTTP `409`
- 상세 수집 ON에서 표시 중개사 수보다 상세 성공 수가 적음: 기존 `incomplete_listing_collection`
- 상세 수집 OFF에서 중개사 행 또는 안전한 내부 매물번호가 부족함: 기존 `incomplete_listing_collection`
- 상세 수집 OFF에서는 상세 슬라이드 파싱 오류가 발생할 수 없다. 슬라이드를 열지 않기 때문이다.
- CAPTCHA·로그인·403·429·외부 링크 차단 정책은 현재와 동일하게 유지한다.

### 11. 데모 모드

데모 화면도 같은 체크박스를 제공한다.

- 선택값을 데모 분석 상태에 전달한다.
- OFF이면 데모 중개사 등록 카드의 `detailCollected`를 `false`로 만들고 상세 섹션을 숨긴다.
- 실제 네이버 접근은 수행하지 않는다.

### 12. 구현 범위

포함:

- React URL 조사 옵션
- React 스케줄 옵션
- 분석·스케줄 API 계약
- DB migration
- 실행·스케줄 옵션 영속화
- Chrome UI 크롤러 분기
- 상세 미수집 최소 물건 저장
- 내부 조회·화면·XLSX 표시
- 허위 상세 변경 방지
- 데모 모드 일관성

제외:

- 네이버 API 또는 직접 HTTP 수집
- 매물 그룹 자체를 생략하는 빠른 모드
- 거래유형별 별도 상세 옵션
- 물건마다 서로 다른 상세 옵션
- 기존 스냅샷의 상세정보 재수집
- CAPTCHA·로그인·접근 제한 우회

### 13. 승인 후 확인 범위

사용자의 기존 지시에 따라 구현과 별개로 광범위한 테스트를 임의 실행하지 않는다. 구현계획에는 다음 집중 확인 항목을 구분해 기록하고, 실제 실행은 사용자가 승인한 범위만 수행한다.

- 상세 수집 ON 요청이 기존 동작을 유지하는지
- 상세 수집 OFF 요청이 상세 슬라이드를 열지 않고 중개사 등록 수를 보존하는지
- OFF 실행이 허위 관리비·입주일·옵션 변경을 만들지 않는지
- 스케줄이 저장된 옵션으로 `CrawlRun`을 생성하는지
- API·React·XLSX가 `detailCollected`를 일관되게 표시하는지

---

# Optional Per-Broker Detail Collection Design

## English / AI-readable

### Goal

Allow the user to choose whether an analysis opens every broker article detail slide. The default remains enabled for backward compatibility. Disabling the option must still collect every listing group, expanded broker row, safe internal article ID, and basic broker registration.

### Canonical fields

```text
Python / database: collect_broker_details
JSON / React: collectBrokerDetails
Snapshot / domain: detail_collected
Snapshot / API: detailCollected
```

All defaults are `true`. Missing fields in legacy rows or snapshots mean `true`.

### Persistence model

Add non-null boolean columns with a database default of true:

```text
crawl_runs.collect_broker_details
crawl_schedules.collect_broker_details
```

Store the immediate choice on `CrawlRun`, not `TrackedSource`. Store the repeated choice on `CrawlSchedule`, and copy it into every scheduled `CrawlRun`.

### API contract

`POST /api/analyses` accepts:

```json
{
  "sourceUrl": "https://fin.land.naver.com/map?...",
  "collectBrokerDetails": true
}
```

`AnalysisAccepted` and `AnalysisStatus` echo the applied value. An active run with the same URL and the same value is deduplicated. An active run with a different value returns HTTP 409 with `analysis_option_conflict`.

Schedule create, patch, response, and run-history schemas expose the same field.

### Collector contract

`CrawlScope` gains `collect_broker_details: bool = True`. This flag must not change the meaning of full collection.

Both modes always:

1. scan all non-empty trade types;
2. collect every displayed listing group;
3. expand every broker group;
4. collect all lazy-loaded broker rows;
5. validate safe internal article targets;
6. enforce displayed group and broker counts;
7. persist article IDs for new/removed tracking.

When enabled, retain the existing detail-slide flow and store `detail_collected=true`.

When disabled, never click an article detail trigger. Build a minimal `BrokerArticleDetail` from the broker-row observation and safe target:

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

Only add the article ID to `seen_article_ids` after the minimal article object is valid.

### Snapshot and query contract

Persist `detail_collected` inside `BrokerArticleSnapshot.details_json`. API `BrokerRegistration` exposes `detailCollected`. Legacy snapshots default to true.

The React registration card must show a clear not-collected notice instead of presenting empty values as real missing data. The XLSX broker sheet gains `추가상세수집여부` with `Y` or `N`; per-article detail JSON cells remain blank when false.

### Comparison contract

Core listing and presence fields remain comparable in both modes:

```text
presence/removal
article IDs
trade type
price/deposit/monthly rent
building/floor/direction/area
```

Detail-derived fields are comparable only when both the previous and current runs used `collect_broker_details=true`:

```text
management fee
move-in date
options
detail market/cost/complex/location fields
```

This prevents disabled runs from producing false deletion or changed events for fields that were intentionally not collected.

### UX contract

Place a default-on checkbox directly below the URL input row. Disable it while a run is queued or running. Add the same option to the schedule form and current schedule summary.

Demo mode accepts the option and hides demo detail sections when disabled; it never accesses Naver.

### Safety and exclusions

- Chrome UI/CDP only for Naver acquisition.
- No direct Naver APIs or HTTP scraping.
- No weakening of full-count or fail-closed checks.
- No CAPTCHA, login, or access-restriction bypass.
- No per-trade-type or per-article option in this scope.
- No retroactive detail collection for old snapshots.

### Focused verification boundary

The implementation plan will list focused ON, OFF, comparison, schedule, API, React, and XLSX checks. Per the user's standing instruction, no broad or unrelated test suite is executed without explicit approval.
