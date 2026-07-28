# GPT 기준 네이버 부동산 라이브 E2E 구현계획서

> **에이전트 작업 지침:** `superpowers:subagent-driven-development` 또는 `superpowers:executing-plans`를 사용해 작업별 TDD 순서를 지킨다. 각 단계는 체크박스로 추적한다.

**목표:** 세 개의 네이버 부동산 URL에서 GPT 브라우저 기준 결과와 운영 수집기 결과를 비교하는 표본·전수 라이브 E2E TC를 구현하고, 표본 TC가 드러낸 실제 DOM 불일치를 수집기에 반영한다.

**구조:** GPT 탐색 결과는 시각이 포함된 JSON oracle로 저장한다. 순수 Python 계층이 oracle 검증·만료·정규화·diff를 담당하고, `PlaywrightNaverLandCollector`는 주입 가능한 `HumanizedDelay`와 `CrawlScope`를 사용해 표본 또는 전수 범위를 실행한다. 라이브 테스트는 환경변수가 없으면 skip되고, 일반 단위 테스트와 CI에는 포함되지 않는다.

**기술 스택:** Python 3.12~3.14, pytest, pytest-asyncio, Pydantic 2, Playwright Chromium, 기존 FastAPI 백엔드

## 공통 제약

- 대상은 설계서의 `case-131197`, `case-155817`, `case-22746` 세 URL뿐이다.
- 모든 페이지 이동, 거래유형 전환, 목록 스크롤, 중개사 펼치기, 상세 열기 사이에 실제 `1.0~3.0초` 균등 랜덤 지연을 한 번 적용한다.
- 브라우저와 케이스 동시 실행 수는 1이다.
- CAPTCHA, 로그인, 접근 제한, 외부 브리지 우회는 금지한다.
- Npay 링크가 있으면 네이버 내부 `/articles/{articleId}`만 허용하고 다른 링크로 fallback하지 않는다.
- 전체 query URL, 연락처, 쿠키, 인증값은 로그와 diff에 기록하지 않는다.
- 단위 테스트는 실제 대기를 하지 않고 주입한 가짜 sleep과 RNG를 사용한다.
- 전수 테스트는 구현만 하고 `RUN_LIVE_NAVER_FULL_E2E=1` 별도 지시 없이는 실행하지 않는다.
- Git commit은 사용자가 별도로 요청하지 않았으므로 만들지 않는다.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `backend/app/crawler/delay.py` | 1~3초 사용자형 지연과 테스트 주입 경계 |
| `backend/app/crawler/scope.py` | 표본·전수 거래유형 및 매물 범위 |
| `backend/app/crawler/live_dom.py` | 실제 네이버 단지·매물·중개사 카드의 표시값 파싱 |
| `backend/app/crawler/selectors.py` | 실제 화면의 안정된 `data-nlogs-*`, `data-sentry-*` selector |
| `backend/app/crawler/browser.py` | 거래유형 순회, 가상 목록, 중개사 펼치기, 상세 수집 연결 |
| `backend/app/crawler/types.py` | 거래유형별 표시 건수 보존 |
| `backend/tests/fixtures/live_*.html` | 개인정보를 제거한 최소 실제 DOM 계약 fixture |
| `backend/tests/e2e/reference_schema.py` | GPT oracle 모델과 30분 만료 검증 |
| `backend/tests/e2e/comparison.py` | 정규화와 구조화 diff |
| `backend/tests/e2e/reference/gpt_naver_observations.json` | GPT 표본 oracle |
| `backend/tests/e2e/test_naver_live_scrape.py` | opt-in 표본·전수 라이브 TC |
| `backend/tests/unit/test_humanized_delay.py` | 지연 범위와 호출 계약 |
| `backend/tests/unit/test_live_dom.py` | 실제 DOM 표시값 파싱 계약 |
| `backend/tests/unit/test_e2e_reference.py` | oracle 만료·diff·로그 정제 계약 |
| `docs/testing/naver-live-e2e.md` | 한국어 우선 실행·갱신 가이드 |

---

### Task 1: 사용자형 랜덤 지연 경계

**파일**

- 생성: `backend/app/crawler/delay.py`
- 생성: `backend/tests/unit/test_humanized_delay.py`
- 수정: `backend/app/crawler/browser.py`

**인터페이스**

```python
Sleep = Callable[[float], Awaitable[None]]
RandomUniform = Callable[[float, float], float]

@dataclass(frozen=True, slots=True)
class DelayObservation:
    reason: str
    seconds: float

class HumanizedDelay:
    def __init__(
        self,
        min_seconds: float = 1.0,
        max_seconds: float = 3.0,
        *,
        sleep: Sleep = asyncio.sleep,
        uniform: RandomUniform = random.uniform,
    ) -> None:
        if min_seconds < 0 or max_seconds < min_seconds:
            raise ValueError("invalid delay range")
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        self.sleep = sleep
        self.uniform = uniform

    async def wait(self, reason: str) -> DelayObservation:
        seconds = self.uniform(self.min_seconds, self.max_seconds)
        await self.sleep(seconds)
        return DelayObservation(reason=reason, seconds=seconds)
```

- [ ] **1.1 실패하는 지연 단위 테스트 작성**

```python
def test_humanized_delay_uses_injected_uniform_and_sleep() -> None:
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    delay = HumanizedDelay(1.0, 3.0, sleep=fake_sleep, uniform=lambda low, high: 2.25)
    observation = asyncio.run(delay.wait("open_broker_group"))

    assert slept == [2.25]
    assert observation == DelayObservation("open_broker_group", 2.25)
```

- [ ] **1.2 RED 확인**

실행:

```powershell
cd backend
..\.venv\Scripts\python -m pytest tests/unit/test_humanized_delay.py -q
```

예상: `ModuleNotFoundError: app.crawler.delay`.

- [ ] **1.3 최소 구현**

생성자는 `min_seconds < 0`, `max_seconds < min_seconds`를 `ValueError`로 거부한다. `wait()`는 정확히 한 번 `uniform(min, max)`를 호출하고 정확히 한 번 sleep한다.

- [ ] **1.4 GREEN 확인**

같은 명령에서 모든 지연 테스트가 통과해야 한다.

- [ ] **1.5 수집기에 주입**

`PlaywrightNaverLandCollector.__init__`에 `delay: HumanizedDelay | None = None`을 추가하고, 기존 `_navigation_delay()` 구현을 다음 계약으로 교체한다.

```python
self.delay = delay or HumanizedDelay(
    self.settings.naver_request_delay_min,
    self.settings.naver_request_delay_max,
)

async def _interaction_delay(self, reason: str) -> None:
    await self.delay.wait(reason)
```

기존 대기 호출부는 이유 코드 `navigate_source`, `switch_trade_type`, `scroll_listing_list`, `open_broker_group`, `open_article_detail` 중 하나를 전달한다.

---

### Task 2: GPT oracle 모델, 만료와 diff

**파일**

- 생성: `backend/tests/e2e/__init__.py`
- 생성: `backend/tests/e2e/reference_schema.py`
- 생성: `backend/tests/e2e/comparison.py`
- 생성: `backend/tests/unit/test_e2e_reference.py`

**인터페이스**

```python
class ReferenceStaleError(RuntimeError):
    code = "reference_stale"

class GptArticleObservation(BaseModel):
    article_id: str
    trade_type: Literal["매매", "전세", "월세"]
    price: int | None
    building: str | None
    floor: str | None
    direction: str | None
    supply_area_m2: Decimal | None
    exclusive_area_m2: Decimal | None
    displayed_broker_count: int
    option_tags: list[str]
    move_in_date: str | None
    required_detail_fields: dict[str, str]

class GptCaseObservation(BaseModel):
    case_id: str
    source_url: str
    complex_id: str
    complex_name: str
    trade_counts: dict[str, int]
    articles: list[GptArticleObservation]

class GptObservationSet(BaseModel):
    schema_version: Literal["1"]
    collector: Literal["gpt_browser_exploration"]
    mode: Literal["sample", "full"]
    captured_at: datetime
    cases: list[GptCaseObservation]

class Difference(BaseModel):
    code: str
    path: str
    expected: object
    actual: object

class ComparisonReport(BaseModel):
    case_id: str
    differences: list[Difference]

    @property
    def ok(self) -> bool:
        return not self.differences

def load_reference(path: Path, *, now: datetime, max_age: timedelta) -> GptObservationSet:
    reference = GptObservationSet.model_validate_json(path.read_text(encoding="utf-8"))
    if now.astimezone(timezone.utc) - reference.captured_at > max_age:
        raise ReferenceStaleError("GPT reference is older than the allowed window")
    return reference

def compare_case(expected: GptCaseObservation, actual: CrawlPayload) -> ComparisonReport:
    differences: list[Difference] = []
    if expected.complex_id != actual.apartment.complex_id:
        differences.append(Difference(
            code="complex_identity_mismatch",
            path="apartment.complex_id",
            expected=expected.complex_id,
            actual=actual.apartment.complex_id,
        ))
    if expected.trade_counts != actual.trade_counts:
        differences.append(Difference(
            code="trade_count_mismatch",
            path="trade_counts",
            expected=expected.trade_counts,
            actual=actual.trade_counts,
        ))
    return ComparisonReport(case_id=expected.case_id, differences=differences)
```

- [ ] **2.1 실패하는 만료·정규화·diff 테스트 작성**

```python
def test_reference_older_than_thirty_minutes_is_rejected(tmp_path: Path) -> None:
    path = write_reference(tmp_path, captured_at="2026-07-24T00:00:00Z")
    with pytest.raises(ReferenceStaleError):
        load_reference(
            path,
            now=datetime(2026, 7, 24, 0, 31, tzinfo=timezone.utc),
            max_age=timedelta(minutes=30),
        )

def test_diff_reports_oracle_field_missing_from_production() -> None:
    report = compare_case(expected_with_option("시스템에어컨 2대"), actual_without_options())
    assert report.ok is False
    assert report.differences[0].code == "missing_expected_field"
```

- [ ] **2.2 RED 확인**

```powershell
cd backend
..\.venv\Scripts\python -m pytest tests/unit/test_e2e_reference.py -q
```

예상: `reference_schema` 또는 `comparison` 모듈 부재로 실패.

- [ ] **2.3 최소 구현**

문자열은 연속 공백만 축약하고, 금액은 원 단위 정수, 면적은 `Decimal("0.01")`, 옵션은 중복 제거한 집합으로 비교한다. 전체 URL은 diff 직렬화 시 `case_id`로 대체한다.

- [ ] **2.4 GREEN 확인**

동일 명령에서 만료, 금액, 면적, 옵션, 상세 필드, URL 정제 테스트가 모두 통과해야 한다.

---

### Task 3: 라이브 TC를 먼저 작성하고 RED 확인

**파일**

- 생성: `backend/tests/e2e/reference/gpt_naver_observations.json`
- 생성: `backend/tests/e2e/test_naver_live_scrape.py`
- 수정: `backend/pyproject.toml`

**oracle 작성 규칙**

GPT 브라우저로 각 URL을 열고 거래유형별 표시 건수와 거래유형당 첫 번째 대표 그룹을 확인한다. `중개사 n곳에서 등록했어요`를 1~3초 지연 후 펼치고 내부 `/articles/{id}` 상세를 1~3초 지연 후 연다. 현재 시점의 실제 매물번호와 상세값을 JSON에 기록한다. 전화번호와 매물소개 원문은 저장하지 않는다.

- [ ] **3.1 pytest marker 등록**

```toml
markers = [
  "live_naver: opt-in sampled Naver Land live comparison",
  "live_naver_full: opt-in exhaustive Naver Land live comparison",
]
```

- [ ] **3.2 기본 skip 테스트 작성**

```python
RUN_SAMPLE = os.getenv("RUN_LIVE_NAVER_E2E") == "1"
RUN_FULL = os.getenv("RUN_LIVE_NAVER_FULL_E2E") == "1"
REFERENCE_PATH = Path(__file__).parent / "reference" / "gpt_naver_observations.json"

def load_current_reference() -> GptObservationSet:
    return load_reference(
        REFERENCE_PATH,
        now=datetime.now(timezone.utc),
        max_age=timedelta(minutes=30),
    )

def load_full_reference_from_environment() -> GptObservationSet:
    raw_path = os.environ["GPT_NAVER_FULL_REFERENCE_PATH"]
    return load_reference(
        Path(raw_path),
        now=datetime.now(timezone.utc),
        max_age=timedelta(minutes=30),
    )

def live_collector(*, delay: HumanizedDelay) -> PlaywrightNaverLandCollector:
    settings = Settings(
        crawler_headless=True,
        naver_request_delay_min=1.0,
        naver_request_delay_max=3.0,
        _env_file=None,
    )
    return PlaywrightNaverLandCollector(settings, delay=delay)

def write_sanitized_report(report: ComparisonReport) -> None:
    output = Path("../temp/e2e/naver-live") / report.case_id / "diff.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")

@pytest.mark.live_naver
@pytest.mark.skipif(not RUN_SAMPLE, reason="RUN_LIVE_NAVER_E2E=1 required")
@pytest.mark.parametrize("case_id", ["case-131197", "case-155817", "case-22746"])
def test_sampled_production_scrape_matches_gpt_reference(case_id: str) -> None:
    reference = load_current_reference()
    expected = next(item for item in reference.cases if item.case_id == case_id)
    article_ids = {item.article_id for item in expected.articles}
    collector = live_collector(delay=HumanizedDelay(1.0, 3.0))
    actual = asyncio.run(
        collector.collect(expected.source_url, scope=CrawlScope.sampled(article_ids))
    )
    report = compare_case(expected, actual)
    write_sanitized_report(report)
    assert report.ok, report.model_dump_json(indent=2)

@pytest.mark.live_naver_full
@pytest.mark.skipif(not RUN_FULL, reason="RUN_LIVE_NAVER_FULL_E2E=1 required")
def test_full_production_scrape_matches_gpt_reference() -> None:
    reference = load_full_reference_from_environment()
    assert reference.mode == "full"
    collector = live_collector(delay=HumanizedDelay(1.0, 3.0))
    for expected in reference.cases:
        actual = asyncio.run(collector.collect(expected.source_url, scope=CrawlScope.full()))
        report = compare_case(expected, actual)
        write_sanitized_report(report)
        assert report.ok, report.model_dump_json(indent=2)
```

- [ ] **3.3 일반 실행에서 skip 확인**

```powershell
cd backend
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -q
```

예상: 네 테스트 모두 `SKIPPED`; 네이버 접속 0회.

- [ ] **3.4 표본 라이브 RED 확인**

```powershell
cd backend
$env:RUN_LIVE_NAVER_E2E='1'
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -m live_naver -vv -s
```

예상: 현재 fixture 전용 `[data-complex-id]`, `[data-group-id]` selector 때문에 `ComplexNotFoundError` 또는 `SelectorMismatchError`로 실패. 이 실패가 작업 4·5의 생산 코드 변경을 정당화한다.

---

### Task 4: 실제 DOM 최소 fixture와 파서

**파일**

- 생성: `backend/tests/fixtures/live_complex_panel.html`
- 생성: `backend/tests/fixtures/live_listing_group.html`
- 생성: `backend/tests/fixtures/live_article_detail.html`
- 생성: `backend/tests/unit/test_live_dom.py`
- 생성: `backend/app/crawler/live_dom.py`
- 수정: `backend/app/crawler/parsers/broker_article.py`
- 수정: `backend/app/crawler/parsers/market_details.py`

**fixture 내용 경계**

- 단지: `신동탄포레자이`, `/complexes/131197`, `매매 53`, `전세 2`, `월세 1`만 보존한다.
- 대표 그룹: `108동`, `매매 9억`, `81㎡ (전용59.98)`, `27/29층`, `남동향`, `중개사 3곳`만 보존한다.
- 중개사: `/articles/2639879471`, 제공처, 옵션 문구만 보존하고 전화번호·장문 소개는 제거한다.
- 상세: 공급·전용면적, 층, 방·욕실, 방향, 입주가능일, 매물번호, 관리비와 추가 필드의 최소 label/value만 보존한다.

**인터페이스**

| 함수/타입 | 입력 | 출력 |
|---|---|---|
| `ComplexPanelObservation` | `complex_id`, `name`, `trade_counts` | immutable dataclass |
| `BrokerCardObservation` | `article_href`, `provider`, `description` | immutable dataclass |
| `parse_complex_panel` | `html: str`, `title: str` | `ComplexPanelObservation` |
| `parse_live_listing_group` | `html: str`, `captured_at: datetime` | `ListingDetail` |
| `parse_live_broker_card` | `html: str` | `BrokerCardObservation` |
| `extract_option_mentions` | `text: str` | 중복 제거된 `list[str]` |

- [ ] **4.1 실제 최소 fixture 기반 실패 테스트 작성**

```python
def test_live_group_parses_visible_card_contract() -> None:
    listing = parse_live_listing_group(FIXTURE.read_text(encoding="utf-8"), captured_at=NOW)
    assert listing.trade_type == "매매"
    assert listing.price == 900_000_000
    assert listing.building == "108동"
    assert listing.supply_area == Decimal("81")
    assert listing.exclusive_area == Decimal("59.98")
    assert listing.floor == "27/29층"
    assert listing.direction == "남동향"
    assert listing.displayed_broker_count == 3
```

- [ ] **4.2 RED 확인 후 최소 파서 구현**

카드 visible text에만 근거해 정규식으로 파싱한다. 존재하지 않는 값은 추론하지 않는다. `extract_option_mentions()`는 `시스템 에어컨`, `시스템에어컨`, `시에`, `중문`, `식기세척기`, `식세기`처럼 실제 관찰된 명시 표현만 표준 태그로 변환한다.

- [ ] **4.3 상세 parser 실제 markup 보강**

기존 `dt/dd` 계약을 유지하면서 실제 상세 markup의 label/value 쌍을 읽는다. caller가 제공한 `provider`와 `is_npay`를 우선 사용하고, 매물번호는 내부 article URL 또는 화면 `매물번호`에서 추출한다.

- [ ] **4.4 GREEN 확인**

```powershell
cd backend
..\.venv\Scripts\python -m pytest tests/unit/test_live_dom.py tests/unit/test_broker_article_parser.py -q
```

---

### Task 5: 표본·전수 수집 범위와 실제 selector 연결

**파일**

- 생성: `backend/app/crawler/scope.py`
- 수정: `backend/app/crawler/selectors.py`
- 수정: `backend/app/crawler/browser.py`
- 수정: `backend/app/crawler/types.py`
- 생성: `backend/tests/unit/test_crawl_scope.py`

**인터페이스**

```python
@dataclass(frozen=True, slots=True)
class CrawlScope:
    trade_types: tuple[str, ...] = ("매매", "전세", "월세")
    max_groups_per_trade_type: int | None = None
    expected_article_ids: frozenset[str] = frozenset()

    @classmethod
    def sampled(cls, article_ids: Collection[str]) -> "CrawlScope":
        return cls(max_groups_per_trade_type=1, expected_article_ids=frozenset(article_ids))

    @classmethod
    def full(cls) -> "CrawlScope":
        return cls()
```

`CrawlPayload`에 `trade_counts: dict[str, int] = Field(default_factory=dict)`를 추가한다. 기존 호출자는 기본값으로 호환된다.

**실제 selector 계약**

```python
COMPLEX_LINK = "a[href^='/complexes/']"
TRADE_COUNT_BUTTON = "button[data-sentry-component='ButtonBoxLink']"
LISTING_CARD = (
    "li:has(button[data-nlogs-area='article*l.group']), "
    "li:has(a[data-nlogs-area='article*l.list'][href^='/articles/'])"
)
BROKER_OPEN_BUTTON = "button[data-nlogs-area='article*l.group']"
BROKER_ARTICLE_LINK = "a[data-nlogs-area='article*l.group'][href^='/articles/']"
SINGLE_ARTICLE_LINK = "a[data-nlogs-area='article*l.list'][href^='/articles/']"
LISTING_SCROLL_CONTAINER = "div[class*='ScrollBox'][class*='panel']"
```

- [ ] **5.1 실패하는 scope 테스트 작성**

표본은 거래유형당 대표 그룹 1개만 허용하고, 전수는 제한값이 없어야 한다. 빈 거래유형은 건수 0으로 기록하고 클릭하지 않는다.

- [ ] **5.2 실제 단지 식별 구현**

`document.title`과 같은 이름을 가진 `/complexes/{id}` 내부 링크에서 ID를 추출한다. 단지 주소는 첫 상세의 `위치` 표시값에서 가져오고, 표시되지 않으면 빈 문자열로 보존하며 다른 주소를 추론하지 않는다.

- [ ] **5.3 거래유형 순회 구현**

`TRADE_COUNT_BUTTON`의 visible text에서 `매매53`, `전세2`, `월세1` 형식을 파싱해 `trade_counts`에 저장한다. 건수가 0보다 큰 거래유형만 1~3초 대기 후 버튼을 클릭하고 해당 목록이 표시될 때까지 기다린다.

- [ ] **5.4 그룹·중개사·상세 구현**

각 `LISTING_CARD`의 outerHTML을 `parse_live_listing_group()`에 전달한다. 그룹 버튼을 펼치기 전에 `open_broker_group` 지연을 적용하고, 펼친 카드 안의 내부 article 링크만 수집한다. 상세 이동 전 `open_article_detail` 지연을 적용한다. Npay 후보가 있으면 `choose_article_target()`의 hard-failure 규칙을 유지한다.

- [ ] **5.5 표본과 전수 스크롤 구현**

표본은 거래유형당 첫 그룹을 수집한 뒤 중단한다. 전수는 scroll container의 `scrollTop`, `clientHeight`, `scrollHeight`를 사용해 끝까지 이동하고 각 스크롤 사이 `scroll_listing_list` 지연을 적용한다. 동일 article ID는 한 번만 상세 방문한다.

- [ ] **5.6 단위 GREEN 확인**

```powershell
cd backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py tests/unit/test_live_dom.py tests/unit/test_navigation_policy.py tests/unit/test_humanized_delay.py -q
```

---

### Task 6: 표본 라이브 E2E GREEN과 diff 리포트

**파일**

- 수정: `backend/tests/e2e/test_naver_live_scrape.py`
- 수정: `backend/tests/e2e/reference/gpt_naver_observations.json`
- 필요할 때만 수정: 작업 4·5의 crawler 파일

- [ ] **6.1 GPT oracle 수집 시각 갱신**

세 URL을 순차 방문하며 모든 상태 변경 사이 1~3초 랜덤 지연을 적용한다. 각 거래유형의 첫 대표 그룹과 그 그룹의 모든 중개사 article을 기록한다. query 전체 URL과 연락처는 oracle에서 제외한다.

- [ ] **6.2 표본 라이브 테스트 실행**

```powershell
cd backend
$env:RUN_LIVE_NAVER_E2E='1'
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -m live_naver -vv -s
```

예상: `case-131197`, `case-155817`, `case-22746` 세 표본 비교 PASS. 환경 접근 제한이면 `E2E_BLOCKED`, 기준이 30분을 넘으면 `reference_stale`로 데이터 불일치와 구분한다.

- [ ] **6.3 실패 시 동일 TC로 최소 수정 반복**

불일치 코드별 수정 대상은 고정한다.

| diff/error | 수정 대상 |
|---|---|
| `complex_identity_mismatch` | `parse_complex_panel`, `COMPLEX_LINK` |
| `trade_count_mismatch` | 거래유형 버튼 text parser |
| `listing_missing` | `LISTING_CARD`, scroll 종료 조건 |
| `broker_count_mismatch` | 펼친 그룹 내부 link scope |
| `detail_collection_failed` | 상세 ready 조건과 실제 label/value parser |
| `unsafe_article_target` | 수정하지 않고 Npay 내부 링크 상태를 기준에서 재확인 |
| `E2E_BLOCKED` | 우회하지 않고 실행 중단 |

각 생산 코드 수정 전 해당 최소 fixture 단위 테스트를 실패 상태로 추가하고, 단위 GREEN 후 같은 표본 라이브 TC를 다시 실행한다.

- [ ] **6.4 전수 TC가 기본 실행에서 제외되는지 확인**

`RUN_LIVE_NAVER_FULL_E2E`를 설정하지 않은 상태에서 전수 TC가 skip되어야 한다. 실제 전수 네이버 방문은 수행하지 않는다.

---

### Task 7: 실행 가이드

**파일**

- 생성: `docs/testing/naver-live-e2e.md`
- 수정: `README.md`

- [ ] **7.1 한국어 우선 가이드 작성**

가이드에 표본·전수 환경변수, oracle 30분 만료, 1~3초 지연, 예상 실행 시간, `E2E_BLOCKED`, `reference_stale`, diff 위치와 개인정보 미기록 규칙을 포함한다.

- [ ] **7.2 AI Reference를 문서 후반에 분리**

영문 섹션에는 marker, 환경변수, 파일 계약, 비교 hard-failure 규칙을 구조화한다.

- [ ] **7.3 요청 범위 최종 확인**

실행한 것은 단위 대상 테스트와 표본 라이브 TC뿐이어야 한다. Docker, 전체 백엔드 suite, 프런트 build, 전수 라이브 TC는 실행하지 않는다.

---

# AI Implementation Map (English)

## Required sequence

1. Add `HumanizedDelay` through a red/green unit cycle and inject it into every browser state transition.
2. Add versioned GPT oracle schema, 30-minute freshness enforcement, normalization, sanitized structured diffs, and unit tests.
3. Capture a concrete sampled oracle through GPT browser exploration and write opt-in live tests before changing production selectors; verify the current collector fails for the expected live-DOM reason.
4. Add minimal sanitized DOM fixtures from the observed Naver UI and implement `live_dom.py` parsers without inferring missing values.
5. Add `CrawlScope`, per-trade counts, stable observed selectors, sequential trade switching, broker expansion, internal article navigation, and sampled/full scrolling.
6. Refresh the oracle and run only `live_naver`; repair only failures produced by that TC, always adding a failing fixture test first.
7. Document the opt-in workflow. Do not execute `live_naver_full` without another explicit instruction.

## Interface consistency

```text
HumanizedDelay.wait(reason) -> DelayObservation
CrawlScope.sampled(article_ids) -> max 1 group per trade type
CrawlScope.full() -> no group limit
load_reference(path, now, max_age) -> GptObservationSet | ReferenceStaleError
compare_case(expected, actual) -> ComparisonReport
PlaywrightNaverLandCollector.collect(url, scope: CrawlScope | None) -> CrawlPayload
CrawlPayload.trade_counts -> dict[str, int]
```

## Live safety

All cases are serial. Every state-changing action waits one random duration in `[1.0, 3.0]`. Never solve or bypass CAPTCHA/login/access blocks, never open an external bridge, never log full query URLs or contact data, and never run the exhaustive suite by default.
