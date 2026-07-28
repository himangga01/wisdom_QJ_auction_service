# Chrome 화면 탐색 지연 프리셋 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**목표:** 사용자가 즉시 분석과 예약 조사에서 Chrome 화면 동작 간 지연 프리셋을 선택하고, 서버가 실행별 선택값을 저장·복원해 실제 `HumanizedDelay`에 적용하도록 구현한다.

**구조:** API와 DB에는 `interaction_delay_preset` 키 하나만 저장한다. `backend/app/crawler/delay.py`가 다섯 프리셋과 실제 초 범위의 유일한 서버 기준이며, worker가 실행 레코드의 키를 읽어 `HumanizedDelay`를 만들어 collector에 주입한다. React는 동일한 공용 선택 컴포넌트를 즉시 분석과 스케줄 화면에서 재사용한다.

**기술:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Celery, Playwright, React 19, TypeScript 6, Tailwind CSS 4, Vitest, Testing Library

## 전역 제약

- `very_fast`: 0.5~0.5초
- `fast`: 0.7~1.2초
- `normal`: 1.0~2.5초이며 신규·기존 데이터의 기본값
- `careful`: 2.0~5.0초
- `very_careful`: 3.0~7.0초
- 사용자 직접 초 입력은 지원하지 않는다.
- 즉시 분석과 예약 조사 모두에 같은 프리셋 계약을 적용한다.
- JSON·React 이름은 `interactionDelayPreset`, Python·DB 이름은 `interaction_delay_preset`이다.
- dispatcher는 계속 `run_id`만 전달하고 `CrawlScope`는 변경하지 않는다.
- 내부 DOM polling 지연, 동시 실행 수, 수집 범위, 상세정보 수집 의미는 변경하지 않는다.
- 기존 데이터와 필드 생략 요청은 `normal`로 해석한다.
- 현재 `main` 작업공간의 기존 변경을 보존한다.
- 커밋과 push를 생성하지 않는다.
- 각 작업의 명시된 집중 TDD만 실행한다. 전체 suite, 라이브 네이버 크롤링, Docker, 서버, 브라우저 수동 검증은 실행하지 않는다.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `backend/app/crawler/delay.py` | 프리셋 타입·기본값·범위 매핑·`HumanizedDelay` factory |
| `backend/app/core/config.py` | 실행 레코드가 없는 collector의 fallback 기본 범위 |
| `backend/alembic/versions/0005_interaction_delay_presets.py` | run·schedule 프리셋 컬럼과 DB check migration |
| `backend/app/models/entities.py` | run·schedule ORM 필드와 check constraint |
| `backend/app/schemas/analysis.py` | 즉시 분석 프리셋 요청·응답 계약 |
| `backend/app/services/analysis_service.py` | 프리셋 저장과 활성 실행 옵션 충돌 |
| `backend/app/api/routes/analyses.py` | 분석 API 필드 전달·응답 |
| `backend/app/tasks/crawl_tasks.py` | 실행 프리셋 복원과 collector delay 주입 |
| `backend/app/schemas/schedule.py` | 스케줄 프리셋 요청·응답·실행 이력 계약 |
| `backend/app/services/schedule_service.py` | 스케줄 저장·수정·실행 복사 |
| `frontend/src/types/api.ts` | React API preset union과 요청·응답 타입 |
| `frontend/src/components/analysis/InteractionDelaySelector.tsx` | 공용 라디오 카드 선택기와 표시 metadata |
| `frontend/src/components/analysis/UrlAnalysisPanel.tsx` | 즉시 분석 프리셋 상태·요청 |
| `frontend/src/pages/SchedulePage.tsx` | 스케줄 프리셋 저장·복원·요약·이력 |
| `frontend/src/types/realEstate.ts` | 스케줄 draft 프리셋 타입 |

### Task 1: 중앙 프리셋 계약과 fallback 기본값

**Files:**

- Modify: `backend/app/crawler/delay.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Modify: `docs/operations/runbook.md`
- Test: `backend/tests/unit/test_humanized_delay.py`
- Test: `backend/tests/unit/test_runtime_config.py`

**Interfaces:**

- Produces: `InteractionDelayPreset`
- Produces: `DEFAULT_INTERACTION_DELAY_PRESET`
- Produces: `INTERACTION_DELAY_RANGES`
- Produces: `humanized_delay_for_preset(preset, *, sleep, uniform) -> HumanizedDelay`
- Rejects: 저장값이 다섯 프리셋에 없으면 `ValueError`

- [x] **Step 1: 중앙 매핑의 실패 테스트 작성**

`backend/tests/unit/test_humanized_delay.py`에 다음 계약을 추가한다.

```python
@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        ("very_fast", (0.5, 0.5)),
        ("fast", (0.7, 1.2)),
        ("normal", (1.0, 2.5)),
        ("careful", (2.0, 5.0)),
        ("very_careful", (3.0, 7.0)),
    ],
)
def test_delay_presets_resolve_to_exact_ranges(preset, expected) -> None:
    delay = humanized_delay_for_preset(preset)
    assert (delay.min_seconds, delay.max_seconds) == expected


def test_unknown_delay_preset_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported interaction delay preset"):
        humanized_delay_for_preset("turbo")
```

기존 injected sleep 테스트와 별도로 `very_fast`가 `uniform(0.5, 0.5)`의 결과 `0.5`를 sleep에 전달하는 테스트를 추가한다.

`backend/tests/unit/test_runtime_config.py`에는 다음을 추가한다.

```python
def test_crawler_fallback_delay_matches_normal_preset() -> None:
    settings = Settings(_env_file=None)
    assert (settings.naver_request_delay_min, settings.naver_request_delay_max) == (
        1.0,
        2.5,
    )
```

- [x] **Step 2: RED 확인**

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest tests/unit/test_humanized_delay.py tests/unit/test_runtime_config.py
```

예상 결과: factory import가 없고 fallback이 1.5~3.0이므로 실패한다.

- [x] **Step 3: 최소 중앙 구현 작성**

`backend/app/crawler/delay.py`에 다음 계약을 추가한다.

```python
from typing import Final, Literal

InteractionDelayPreset = Literal[
    "very_fast",
    "fast",
    "normal",
    "careful",
    "very_careful",
]
DEFAULT_INTERACTION_DELAY_PRESET: InteractionDelayPreset = "normal"
INTERACTION_DELAY_RANGES: Final[
    dict[InteractionDelayPreset, tuple[float, float]]
] = {
    "very_fast": (0.5, 0.5),
    "fast": (0.7, 1.2),
    "normal": (1.0, 2.5),
    "careful": (2.0, 5.0),
    "very_careful": (3.0, 7.0),
}


def humanized_delay_for_preset(
    preset: str,
    *,
    sleep: Sleep = asyncio.sleep,
    uniform: RandomUniform = random.uniform,
) -> HumanizedDelay:
    try:
        min_seconds, max_seconds = INTERACTION_DELAY_RANGES[preset]
    except KeyError as exc:
        raise ValueError(
            f"unsupported interaction delay preset: {preset}"
        ) from exc
    return HumanizedDelay(
        min_seconds,
        max_seconds,
        sleep=sleep,
        uniform=uniform,
    )
```

타입 검사에서 `dict` key 접근이 좁혀지지 않으면 `cast(InteractionDelayPreset, preset)`은 membership 확인 뒤에만 사용한다. 알 수 없는 값을 `normal`로 대체하지 않는다.

- [x] **Step 4: fallback 문서와 환경값 수정**

- `Settings.naver_request_delay_min = 1.0`
- `Settings.naver_request_delay_max = 2.5`
- `backend/.env.example`의 두 값을 `1.0`, `2.5`로 변경
- `docs/operations/runbook.md`의 fallback 설명을 `1.0~2.5초`로 변경

- [x] **Step 5: GREEN 확인**

Step 2와 같은 두 파일만 다시 실행해 모두 통과하는지 확인한다.

실행 결과: RED는 factory import 부재로 수집 오류가 발생했다. GREEN은 두 파일에서 **29 passed**.

### Task 2: run DB·즉시 분석 API·활성 실행 충돌

**Files:**

- Create: `backend/alembic/versions/0005_interaction_delay_presets.py`
- Modify: `backend/app/models/entities.py`
- Modify: `backend/app/schemas/analysis.py`
- Modify: `backend/app/services/analysis_service.py`
- Modify: `backend/app/api/routes/analyses.py`
- Test: `backend/tests/unit/test_model_constraints.py`
- Test: `backend/tests/unit/test_analysis_service.py`

**Interfaces:**

- Consumes: `InteractionDelayPreset`, `DEFAULT_INTERACTION_DELAY_PRESET`
- Produces: `CrawlRun.interaction_delay_preset: str`
- Produces: `AnalysisService.create(..., interaction_delay_preset="normal")`
- API: `interactionDelayPreset` 생략 시 `normal`; 알 수 없는 값은 Pydantic `422`

- [x] **Step 1: 모델·스키마 실패 테스트 작성**

`backend/tests/unit/test_model_constraints.py`에서 분석 schema와 두 ORM 테이블의 계약을 확인한다. 스케줄 schema 계약은 Task 4에서 추가한다.

```python
analysis = AnalysisCreate(sourceUrl="https://fin.land.naver.com/map?a=1")
assert analysis.interaction_delay_preset == "normal"

with pytest.raises(ValidationError):
    AnalysisCreate(
        sourceUrl="https://fin.land.naver.com/map?a=1",
        interactionDelayPreset="turbo",
    )

for table_name in ("crawl_runs", "crawl_schedules"):
    table = Base.metadata.tables[table_name]
    column = table.c.interaction_delay_preset
    assert column.nullable is False
    assert column.default.arg == "normal"
    assert str(column.server_default.arg) == "'normal'"
```

두 테이블의 `CheckConstraint` SQL에 다섯 허용값이 포함되는지도 metadata로 확인한다.

- [x] **Step 2: 분석 저장·재사용 실패 테스트 작성**

`backend/tests/unit/test_analysis_service.py`의 옵션 테스트를 확장한다.

```python
run, created = asyncio.run(
    AnalysisService(session, dispatcher).create(
        source.source_url,
        collect_broker_details=False,
        interaction_delay_preset="fast",
    )
)
assert created is True
assert run.interaction_delay_preset == "fast"

reused, created = asyncio.run(
    AnalysisService(
        ExistingSourceSession(source, active_run),
        dispatcher,
    ).create(
        source.source_url,
        collect_broker_details=False,
        interaction_delay_preset="fast",
    )
)
assert (reused, created) == (active_run, False)

with pytest.raises(AnalysisOptionConflictError):
    asyncio.run(
        AnalysisService(
            ExistingSourceSession(source, active_run),
            dispatcher,
        ).create(
            source.source_url,
            collect_broker_details=False,
            interaction_delay_preset="careful",
        )
    )
```

fixture의 활성 `CrawlRun`에는 `interaction_delay_preset="fast"`를 명시한다. 상세 수집 옵션만 다른 경우의 기존 충돌 assertion도 유지한다.

- [x] **Step 3: RED 확인**

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest tests/unit/test_model_constraints.py tests/unit/test_analysis_service.py
```

예상 결과: schema·ORM·service 필드가 없어 실패한다.

- [x] **Step 4: migration과 ORM 구현**

신규 migration 계약:

```python
revision = "0005_interaction_delay_presets"
down_revision = "0004_optional_broker_detail_collection"
```

두 테이블에 다음 컬럼과 각 테이블의 check constraint를 만든다.

```python
sa.Column(
    "interaction_delay_preset",
    sa.String(length=20),
    nullable=False,
    server_default=sa.text("'normal'"),
)
```

check SQL:

```sql
interaction_delay_preset IN
('very_fast','fast','normal','careful','very_careful')
```

constraint 이름:

- `ck_crawl_runs_interaction_delay_preset_values`
- `ck_crawl_schedules_interaction_delay_preset_values`

`downgrade()`는 constraint를 먼저 제거하고 컬럼을 제거한다.

ORM의 각 모델에는 같은 허용값 check와 다음 필드를 추가한다.

```python
interaction_delay_preset: Mapped[str] = mapped_column(
    String(20),
    default="normal",
    server_default=text("'normal'"),
    nullable=False,
)
```

- [x] **Step 5: 분석 schema·service·route 구현**

`AnalysisCreate`:

```python
interaction_delay_preset: InteractionDelayPreset = (
    DEFAULT_INTERACTION_DELAY_PRESET
)
```

`AnalysisAccepted`에 필수 응답 필드를 추가한다. `AnalysisStatus`는 상속으로 포함한다.

`AnalysisService._deduplicated_run()`과 `create()`에 프리셋 인자를 추가한다. 활성 run의 상세 옵션과 프리셋이 모두 같을 때만 재사용한다. 신규 run 생성과 commit 경합 뒤 재조회 경로 모두 같은 비교 함수를 사용한다.

`create_analysis()`는 payload 값을 service에 전달하고, create/get 응답은 요청값이 아니라 `run.interaction_delay_preset`을 반환한다.

- [x] **Step 6: GREEN 확인**

Step 3의 두 파일만 다시 실행한다.

실행 결과: RED는 5 passed / 3 failed로 schema·ORM·service 부재를 확인했다. GREEN은 **8 passed**.

### Task 3: worker의 실행별 프리셋 복원과 collector 주입

**Files:**

- Modify: `backend/app/tasks/crawl_tasks.py`
- Create: `backend/tests/unit/test_crawl_tasks.py`

**Interfaces:**

- Consumes: `CrawlRun.interaction_delay_preset`
- Consumes: `humanized_delay_for_preset()`
- Produces: `_collector_for_run(interaction_delay_preset, progress) -> PlaywrightNaverLandCollector`
- `_claim_run()` 반환: `(status, source_url, source_id, collect_broker_details, interaction_delay_preset)`

- [x] **Step 1: worker factory 실패 테스트 작성**

새 테스트는 실제 collector 객체를 만들되 Chrome·Celery task·네트워크를 실행하지 않는다.

```python
from app.tasks.crawl_tasks import _collector_for_run


def test_worker_collector_uses_run_delay_preset() -> None:
    collector = _collector_for_run("fast", progress=None)
    assert collector.delay.min_seconds == 0.7
    assert collector.delay.max_seconds == 1.2


def test_worker_collector_rejects_corrupt_delay_preset() -> None:
    with pytest.raises(ValueError, match="unsupported interaction delay preset"):
        _collector_for_run("turbo", progress=None)
```

- [x] **Step 2: RED 확인**

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest tests/unit/test_crawl_tasks.py
```

예상 결과: `_collector_for_run`이 없어 수집 단계에서 실패한다.

- [x] **Step 3: worker 구현**

`_claim_run()`의 기존 두 SELECT에 `CrawlRun.interaction_delay_preset`을 추가한다. 존재하지 않는 run의 반환 프리셋은 `None`, 정상 run은 저장된 문자열이다.

다음 factory를 추가하고 `_execute_pipeline()`에서만 사용한다.

```python
def _collector_for_run(
    interaction_delay_preset: str,
    progress,
) -> PlaywrightNaverLandCollector:
    return PlaywrightNaverLandCollector(
        settings,
        progress=progress,
        delay=humanized_delay_for_preset(interaction_delay_preset),
    )
```

`_execute_pipeline()`은 `_claim_run()`의 다섯 값을 복원하고, 정상 run에서 프리셋이 `None`이면 `ValueError`를 발생시킨다. factory 호출은 기존 `try` 블록 안에서 실행해 손상된 값이 수집 시작 전에 run 실패 처리로 이어지게 한다.

dispatcher와 `CrawlScope.full(collect_broker_details=...)` 호출은 변경하지 않는다.

- [x] **Step 4: GREEN 확인**

Step 2의 신규 파일만 다시 실행한다.

실행 결과: RED는 `_collector_for_run` import 부재로 수집 오류가 발생했다. GREEN은 **2 passed**.

### Task 4: 스케줄 저장·수정·이력·예약 실행 복사

**Files:**

- Modify: `backend/app/schemas/schedule.py`
- Modify: `backend/app/services/schedule_service.py`
- Test: `backend/tests/unit/test_schedule_service.py`

**Interfaces:**

- Consumes: `InteractionDelayPreset`, `DEFAULT_INTERACTION_DELAY_PRESET`
- API: `ScheduleCreate` 기본 `normal`
- API: `SchedulePatch.interaction_delay_preset: InteractionDelayPreset | None`
- Produces: schedule response와 run history의 실제 저장 프리셋

- [x] **Step 1: 스케줄 실패 테스트 작성**

기존 create/patch/history 테스트에 다음 계약을 포함한다.

```python
default_schedule = ScheduleCreate(
    sourceId=source.id,
    cadence="daily",
    time=time(9),
)
assert default_schedule.interaction_delay_preset == "normal"

response = asyncio.run(
    service.create(
        ScheduleCreate(
            sourceId=source.id,
            cadence="daily",
            time=time(9),
            collectBrokerDetails=False,
            interactionDelayPreset="fast",
        ),
        now=datetime(2026, 7, 28, tzinfo=SEOUL),
    )
)
assert response.interaction_delay_preset == "fast"

patched = asyncio.run(
    service.patch(
        session.schedule.id,
        SchedulePatch(interactionDelayPreset="careful"),
    )
)
assert patched.interaction_delay_preset == "careful"
```

실행 이력 fixture에는 `interaction_delay_preset="fast"`를 넣고 history가 `"fast"`를 반환하는지 확인한다.

due enqueue 테스트의 fake signature와 assertion:

```python
async def create(
    self,
    _url,
    *,
    collect_broker_details=True,
    interaction_delay_preset="normal",
):
    captured.append((collect_broker_details, interaction_delay_preset))
    return object(), True

assert captured == [(False, "very_careful")]
```

- [x] **Step 2: RED 확인**

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest tests/unit/test_schedule_service.py
```

예상 결과: schedule schema·response·service 필드가 없어 실패한다.

- [x] **Step 3: schedule schema와 service 구현**

- `ScheduleCreate`: 기본 `normal`
- `SchedulePatch`: optional preset
- `ScheduleResponse`, `ScheduleRun`: 필수 preset
- `_response()`: `schedule.interaction_delay_preset`
- `create()`: payload 값 저장
- `patch()`: payload 값이 `None`이 아닐 때만 변경
- `runs()`: 각 `run.interaction_delay_preset` 반환
- `enqueue_due()`: schedule 값을 `AnalysisService.create()`에 전달

스케줄 프리셋 수정은 시간 계산 필드가 아니므로 `next_run_at` 재계산 조건에는 넣지 않는다.

- [x] **Step 4: GREEN 확인**

Step 2의 스케줄 테스트 파일만 다시 실행한다.

실행 결과: RED는 2 passed / 2 failed로 schema와 due 전달 누락을 확인했다. GREEN은 **4 passed**.

### Task 5: React 공용 선택기와 즉시 분석 요청

**Files:**

- Modify: `frontend/src/types/api.ts`
- Create: `frontend/src/components/analysis/InteractionDelaySelector.tsx`
- Modify: `frontend/src/components/analysis/UrlAnalysisPanel.tsx`
- Modify: `frontend/src/state/AnalysisProvider.tsx`
- Modify: `frontend/src/state/useDemoDashboard.ts`
- Create: `frontend/src/tests/interactionDelay.test.tsx`
- Modify: `frontend/src/tests/App.test.tsx`

**Interfaces:**

- Produces: `InteractionDelayPresetApi`
- Produces: `INTERACTION_DELAY_PRESET_OPTIONS`
- Produces: `interactionDelayPresetText(value) -> string`
- Produces: `<InteractionDelaySelector value onChange disabled?>`
- `AnalysisCreateApi.interactionDelayPreset`은 필수

- [x] **Step 1: 선택기·요청 전달 실패 테스트 작성**

새 `interactionDelay.test.tsx`에서 실제 `UrlAnalysisPanel`을 렌더링한다.

```tsx
it('defaults to normal and submits the selected fast preset', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()

  render(
    <UrlAnalysisPanel
      status="idle"
      progress={0}
      error=""
      onStart={onStart}
    />,
  )

  expect(
    screen.getByRole('radio', { name: /기본.*1~2.5초/ }),
  ).toBeChecked()

  await user.click(
    screen.getByRole('radio', { name: /빠름.*0.7~1.2초/ }),
  )
  await user.click(screen.getByRole('button', { name: '분석 시작' }))

  expect(onStart).toHaveBeenCalledWith(
    expect.objectContaining({ interactionDelayPreset: 'fast' }),
  )
})
```

별도 테스트에서 `very_fast` 선택 시 `접근 제한 가능성이 높아질 수 있습니다`가 표시되는지 확인한다. `status="running"`으로 렌더링하면 다섯 radio가 모두 disabled인지 확인한다.

기존 `App.test.tsx`의 직접 `startDemoAnalysis()` 요청 두 곳에는 `interactionDelayPreset: "normal"`을 추가한다.

- [x] **Step 2: RED 확인**

```powershell
Set-Location frontend
$env:VITE_USE_DEMO_DATA='true'
npm test -- src/tests/interactionDelay.test.tsx src/tests/App.test.tsx
```

예상 결과: preset 타입·공용 선택기·radio와 요청 필드가 없어 실패한다.

- [x] **Step 3: API 타입과 공용 선택기 구현**

`frontend/src/types/api.ts`:

```ts
export type InteractionDelayPresetApi =
  | 'very_fast'
  | 'fast'
  | 'normal'
  | 'careful'
  | 'very_careful'
```

`AnalysisCreateApi`, `AnalysisAcceptedApi`에 `interactionDelayPreset`을 추가한다. `AnalysisStatusApi`는 상속으로 포함한다. 스케줄 타입은 Task 6에서 같은 union을 사용한다.

`InteractionDelaySelector.tsx`의 공용 metadata:

```ts
export const INTERACTION_DELAY_PRESET_OPTIONS = [
  { value: 'very_fast', label: '매우 빠름', range: '0.5초' },
  { value: 'fast', label: '빠름', range: '0.7~1.2초' },
  { value: 'normal', label: '기본', range: '1~2.5초' },
  { value: 'careful', label: '신중', range: '2~5초' },
  { value: 'very_careful', label: '매우 신중', range: '3~7초' },
] as const satisfies readonly {
  value: InteractionDelayPresetApi
  label: string
  range: string
}[]
```

컴포넌트는 `<fieldset>`과 실제 radio input 다섯 개를 사용한다. `value`, `onChange`, `disabled=false`를 받고, 선택 항목은 Tailwind의 emerald border/background로 구분한다. `very_fast`가 선택됐을 때만 위험 안내를 출력한다.

- [x] **Step 4: 즉시 분석과 demo 연결**

`UrlAnalysisPanel`:

- `interactionDelayPreset` 상태 기본값 `"normal"`
- 상세 수집 체크박스 아래에 공용 선택기 배치
- submit 객체에 `interactionDelayPreset` 포함
- busy 상태를 선택기의 `disabled`로 전달

`AnalysisProvider`의 `analysis_option_conflict` 문구를 “이미 같은 URL이 다른 수집 옵션으로 분석 중입니다.”로 일반화한다.

`useDemoDashboard.startDemoAnalysis()`은 새 요청 필드를 수용하되 220ms/900ms 데모 timer 계산에는 사용하지 않는다.

- [x] **Step 5: GREEN 확인**

Step 2의 프런트 두 테스트 파일만 다시 실행한다.

실행 결과: 최종 RED는 4 passed / 4 failed로 radio·위험 안내·disabled·demo 상태 부재를 확인했다. GREEN은 **8 passed**.

### Task 6: React 스케줄 선택·저장·요약·이력

**Files:**

- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/realEstate.ts`
- Modify: `frontend/src/pages/SchedulePage.tsx`
- Modify: `frontend/src/tests/App.test.tsx`

**Interfaces:**

- `ScheduleApi.interactionDelayPreset`
- `ScheduleCreateApi.interactionDelayPreset`
- `SchedulePatchApi.interactionDelayPreset?`
- `ScheduleRunApi.interactionDelayPreset`
- `ScheduleDraft.interactionDelayPreset`

- [x] **Step 1: 스케줄 UX 실패 테스트 작성**

데모 App에서 스케줄 화면으로 이동한 뒤 다음을 확인하는 테스트를 `App.test.tsx`에 추가한다.

```tsx
await user.click(screen.getByRole('link', { name: '조사 스케줄' }))
await user.click(
  screen.getByRole('radio', { name: /신중.*2~5초/ }),
)
await user.click(screen.getByRole('button', { name: '스케줄 저장' }))

expect(screen.getByText(/신중 · 2~5초/)).toBeInTheDocument()
```

현재 `App.test.tsx`에는 `ScheduleApi`와 `ScheduleRunApi` 객체 fixture가 없으므로 새 fixture는 만들지 않는다. 이후 테스트 단계에서 해당 타입의 객체를 새로 작성하게 되면 `interactionDelayPreset`을 필수로 명시한다.

- [x] **Step 2: RED 확인**

```powershell
Set-Location frontend
$env:VITE_USE_DEMO_DATA='true'
npm test -- src/tests/App.test.tsx
```

예상 결과: schedule draft·선택기·요약 필드가 없어 실패한다.

- [x] **Step 3: 스케줄 타입과 draft 구현**

네 schedule API 타입과 `ScheduleDraft`에 승인된 preset 타입을 추가한다. draft 기본값은 `"normal"`이다.

`SchedulePage`:

- 저장된 schedule을 draft로 복원할 때 preset 포함
- create/patch payload에 preset 포함
- 상세 수집 체크박스 아래에 공용 선택기 배치
- 현재 스케줄 요약에 `프리셋 이름 · 범위` 표시
- 최근 실행 이력에 각 run의 실제 preset 표시
- demo 저장도 같은 draft 값을 요약에 표시

공용 `interactionDelayPresetText()`를 사용해 label/range 문자열을 중복 작성하지 않는다.

- [x] **Step 4: GREEN 확인**

Step 2의 `App.test.tsx`만 다시 실행한다.

실행 결과: 첫 RED는 중복 메뉴 링크 선택이라는 테스트 오류를 발견해 selector만 수정했다. 수정된 RED는 5 passed / 1 failed로 schedule radio 부재를 확인했고, GREEN은 **6 passed**.

### Task 7: 계획 이행 기록 정리

**Files:**

- Modify: `docs/superpowers/plans/2026-07-28-user-selectable-browser-delay-presets.md`

**Interfaces:**

- 각 checkbox는 실제 완료된 RED·GREEN 단계만 `[x]`로 바꾼다.
- 실행하지 않은 전체 suite·live·Docker·브라우저 검증은 완료로 표시하지 않는다.

- [x] **Step 1: 실제 수행 결과 기록**

각 Task의 체크박스를 실제 수행 결과에 맞게 갱신한다. 실패한 RED 이유와 최종 GREEN 통과 건수를 해당 Task 아래 한 줄로 기록한다.

- [x] **Step 2: 범위 외 작업 미실행 확인**

최종 보고에는 다음을 명시한다.

- 실행한 집중 테스트 파일과 결과
- 실행하지 않은 전체 suite·live·Docker·서버·브라우저 검증
- migration 적용 명령은 실행하지 않았다는 사실
- 커밋과 push를 만들지 않았다는 사실

실제 범위 기록:

- 실행: 계획에 명시된 백엔드 5개 집중 테스트 묶음과 프런트 3개 집중 테스트 묶음의 RED/GREEN
- 미실행: 전체 suite, 라이브 네이버 크롤링, Docker, 서버, Chrome 수동 검증, migration 적용
- 미수행: commit, push

## English execution contract

Implement five fixed interaction-delay presets with `normal` as the default. Persist only the preset key on `CrawlRun` and `CrawlSchedule`; never accept arbitrary client ranges. The backend mapping in `app/crawler/delay.py` is authoritative.

Execution order:

1. Add and test the central preset mapping plus the 1.0–2.5 fallback.
2. Add run/schedule ORM columns and migration, then analysis API persistence and active-run conflict semantics.
3. Reload the run preset in the worker and inject the resolved `HumanizedDelay` into the collector.
4. Persist, patch, return, and copy schedule presets into due runs.
5. Add the shared React radio-card selector and immediate analysis request propagation.
6. Add schedule selection, payload propagation, summary, and run-history display.
7. Record only the focused RED/GREEN commands actually executed.

Required names:

```text
Python / DB: interaction_delay_preset
JSON / React: interactionDelayPreset
Default: normal
```

Required ranges:

```text
very_fast    0.5–0.5
fast         0.7–1.2
normal       1.0–2.5
careful      2.0–5.0
very_careful 3.0–7.0
```

Do not change `CrawlScope`, dispatcher payloads, DOM polling, crawl concurrency, listing limits, broker-detail semantics, or demo timer durations. Do not run the full suite, live Naver crawl, Docker, servers, or manual browser checks. Do not commit or push.
