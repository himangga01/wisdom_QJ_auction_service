# Chrome 화면 탐색 지연 프리셋 설계

## 한국어 설계

### 1. 목표

사용자가 네이버 부동산 Chrome 화면 탐색 시 적용되는 동작 간 지연 시간을 프리셋으로 선택할 수 있게 한다. 선택값은 즉시 분석과 예약 조사에 모두 적용하고, 각 실행 기록에 보존한다.

사용자가 최소·최대 초를 직접 입력하는 기능은 제공하지 않는다. 서버가 프리셋별 실제 범위의 유일한 기준이 된다.

### 2. 확정 프리셋

| 화면 표시 | API 값 | 최소 지연 | 최대 지연 | 설명 |
|---|---|---:|---:|---|
| 매우 빠름 | `very_fast` | 0.5초 | 0.5초 | 모든 화면 동작 사이에 0.5초 고정 지연 |
| 빠름 | `fast` | 0.7초 | 1.2초 | 0.7~1.2초 무작위 지연 |
| 기본 | `normal` | 1.0초 | 2.5초 | 1~2.5초 무작위 지연, 서비스 기본값 |
| 신중 | `careful` | 2.0초 | 5.0초 | 2~5초 무작위 지연 |
| 매우 신중 | `very_careful` | 3.0초 | 7.0초 | 3~7초 무작위 지연 |

`normal`을 신규 요청, 기존 실행, 기존 스케줄 및 필드가 없는 과거 데이터의 기본값으로 사용한다.

### 3. 이름과 계약

| 계층 | 이름 | 타입 |
|---|---|---|
| Python·DB | `interaction_delay_preset` | `very_fast`, `fast`, `normal`, `careful`, `very_careful` 중 하나 |
| JSON·React | `interactionDelayPreset` | 동일한 문자열 union |

프런트엔드는 초 범위를 API로 보내지 않고 프리셋 이름만 보낸다. 백엔드는 중앙 매핑을 사용해 선택값을 `HumanizedDelay(min_seconds, max_seconds)`로 변환한다.

### 4. 적용 범위

선택 지연은 기존 `HumanizedDelay.wait()`를 통과하는 Chrome 사용자 동작에 적용한다.

- 네이버 부동산 URL 이동
- 거래 유형 변경
- 매물 목록 가상 스크롤 및 초기화
- 중개사 등록 그룹 열기·닫기·스크롤
- 중개사별 매물 선택
- 물건별 상세 슬라이드 열기·닫기

DOM 상태를 확인하기 위한 내부 0.1초 polling처럼 화면 안정화에 필요한 기술적 대기는 사용자 프리셋의 적용 대상이 아니다.

### 5. 데이터 모델

다음 문자열 컬럼을 추가한다.

```text
crawl_runs.interaction_delay_preset NOT NULL DEFAULT 'normal'
crawl_schedules.interaction_delay_preset NOT NULL DEFAULT 'normal'
```

허용값 이외의 문자열이 저장되지 않도록 데이터베이스 check constraint와 Python 스키마 검증을 함께 적용한다.

실제 최소·최대 초는 데이터베이스에 중복 저장하지 않는다. 프리셋 범위는 중앙 코드에서 고정된 제품 계약으로 관리한다.

### 6. 즉시 분석 흐름

```text
사용자 프리셋 선택
  → POST /api/analyses { sourceUrl, collectBrokerDetails, interactionDelayPreset }
  → CrawlRun.interaction_delay_preset 저장
  → dispatcher에는 기존처럼 run_id만 전달
  → worker가 CrawlRun에서 프리셋 복원
  → 서버 중앙 매핑으로 최소·최대 지연 결정
  → HumanizedDelay를 collector에 주입
```

`AnalysisCreate`에서 필드를 생략하면 `normal`을 적용한다. `AnalysisAccepted`와 `AnalysisStatus`는 서버에 실제 저장된 프리셋을 반환한다.

같은 URL에 활성 실행이 있을 때 `collectBrokerDetails` 또는 `interactionDelayPreset` 중 하나라도 다르면 기존 `analysis_option_conflict`로 거절한다. 두 옵션이 모두 같을 때만 활성 실행을 재사용한다.

### 7. 예약 조사 흐름

`ScheduleCreate`, `SchedulePatch`, `ScheduleResponse`, `ScheduleRun`에 `interactionDelayPreset`을 포함한다.

- 새 스케줄의 기본값은 `normal`이다.
- 스케줄 수정 시 새 프리셋을 저장한다.
- 예약 실행을 생성할 때 스케줄의 프리셋을 새 `CrawlRun`에 복사한다.
- 이후 스케줄이 변경돼도 이미 생성된 실행의 프리셋은 바뀌지 않는다.
- 현재 스케줄 요약과 최근 실행 이력에 실제 프리셋을 표시한다.

### 8. 프런트엔드 UX

즉시 분석 URL 입력 화면과 스케줄 설정 화면에서 동일한 공용 프리셋 선택 컴포넌트를 사용한다.

- 한 번에 하나만 선택하는 라디오 카드 또는 세그먼트형 목록
- 각 항목에 이름과 실제 초 범위를 함께 표시
- 기본 선택값은 `기본 · 1~2.5초`
- 분석 실행 중에는 즉시 분석 선택기를 비활성화
- `매우 빠름 · 0.5초`에는 “접근 제한 가능성이 높아질 수 있습니다” 안내 표시
- 스케줄 요약과 실행 이력에는 프리셋 이름과 범위를 함께 표시

데모 모드는 선택값을 요청·상태·화면에 보존하지만 실제 Chrome 탐색을 실행하지 않으므로 데모 애니메이션 타이머에는 적용하지 않는다.

### 9. 서버 중앙 매핑

프리셋 해석은 하나의 백엔드 모듈에서만 수행한다.

```python
DELAY_PRESET_RANGES = {
    "very_fast": (0.5, 0.5),
    "fast": (0.7, 1.2),
    "normal": (1.0, 2.5),
    "careful": (2.0, 5.0),
    "very_careful": (3.0, 7.0),
}
```

worker는 저장된 프리셋을 이 매핑으로 해석해 `HumanizedDelay`를 생성한다. `CrawlScope`는 수집 범위를 나타내므로 지연 프리셋을 넣지 않는다.

환경설정의 fallback 기본 지연도 `1.0~2.5초`로 맞춘다. 실행 레코드가 있는 정상 작업 경로에서는 실행별 프리셋이 환경설정보다 우선한다.

### 10. 오류 처리

- 알 수 없는 프리셋을 보낸 API 요청은 `422`로 거절한다.
- 데이터베이스에는 허용된 다섯 값만 저장한다.
- worker가 비정상적인 저장값을 읽는 경우 임의로 추정하지 않고 실행을 실패 처리한다.
- 프리셋 선택은 접근 차단을 보장하거나 회피하는 기능이 아니다. 기존 차단 감지와 fail-closed 정책은 변경하지 않는다.

### 11. 테스트 범위

구현은 기능별 최소 TDD로 진행한다.

- 백엔드: 프리셋 검증·기본값·활성 실행 충돌·스케줄 복사·worker의 범위 해석
- 프런트엔드: 기본 선택·요청 전달·실행 중 비활성화·스케줄 저장·매우 빠름 안내
- `HumanizedDelay` 실제 범위는 sleep을 주입한 단위 테스트로 확인

이번 기능 구현에서는 전체 테스트 suite, 실제 네이버 라이브 크롤링, Docker 실행 및 브라우저 수동 검증을 자동으로 수행하지 않는다. 필요하면 사용자에게 별도 승인을 요청한다.

### 12. 제외 범위

- 사용자가 임의의 최소·최대 초를 직접 입력하는 기능
- URL 또는 아파트별 자동 지연 추천
- 차단 발생 시 프리셋을 자동 변경하는 기능
- 동시 Chrome 작업 수 변경
- 기존 수집 범위와 상세정보 수집 옵션의 의미 변경

## English implementation contract

### Goal

Allow users to choose a server-defined Chrome interaction-delay preset for both immediate analyses and scheduled crawls. Persist the selected preset on every run and schedule.

### Presets

| Label | Value | Range |
|---|---|---|
| Very fast | `very_fast` | fixed 0.5 seconds |
| Fast | `fast` | random 0.7–1.2 seconds |
| Normal | `normal` | random 1.0–2.5 seconds; default |
| Careful | `careful` | random 2.0–5.0 seconds |
| Very careful | `very_careful` | random 3.0–7.0 seconds |

API and React use `interactionDelayPreset`. Python and database models use `interaction_delay_preset`. Clients send only the preset key; the backend owns the range mapping.

### Persistence and execution

Add non-null `interaction_delay_preset` columns with a `normal` default to `crawl_runs` and `crawl_schedules`. Copy the schedule preset into each newly created run. The worker reloads the run preset, resolves it through the central mapping, creates `HumanizedDelay`, and injects it into `PlaywrightNaverLandCollector`.

The dispatcher continues to carry only `run_id`. `CrawlScope` remains unchanged because delay is an execution dependency, not a collection scope.

### API and conflict behavior

Add the preset to analysis create/accepted/status schemas and schedule create/patch/response/run schemas. Omission defaults to `normal`; unknown values return `422`.

An active run may be reused only when both `collectBrokerDetails` and `interactionDelayPreset` match. A mismatch continues to return `analysis_option_conflict`.

### UI

Use one shared preset selector in the URL analysis panel and schedule page. Show labels and exact ranges, default to Normal, disable the immediate selector while busy, and show an access-restriction risk note for Very fast. Demo mode preserves and displays the selection without changing demo animation timers.

### Constraints

The preset affects only existing humanized Chrome interaction waits. Internal DOM polling remains unchanged. It does not bypass access restrictions or alter fail-closed behavior, crawl concurrency, listing scope, or broker-detail semantics. No custom second range is supported.

### Verification scope

Use focused TDD for preset validation/defaults, active-run conflicts, schedule propagation, worker range resolution, request delivery, disabled UI state, and the Very fast warning. Do not run the full suite, live Naver crawling, Docker, or manual browser verification without separate user approval.
