# 네이버 UI 슬라이드 수집기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**목표:** 생산 Playwright 수집기에서 매물 상세 URL 직접 이동을 제거하고, GPT 브라우저와 같은 목록 UI 클릭·활성 상세 슬라이드 수집 흐름을 구현한다.

**아키텍처:** 거래유형별 virtual list를 순회할 때 각 매물 그룹을 열고, 해당 카드 locator가 살아 있는 동안 broker 행의 안전한 내부 버튼을 클릭해 상세 슬라이드를 수집·닫는다. 상세 파싱은 전체 페이지가 아니라 현재 `매물번호`를 포함한 `SideLayer`의 `outerHTML`만 사용한다.

**기술 스택:** Python 3.13, FastAPI 프로젝트 설정, Playwright async API, pytest, 기존 Pydantic crawler models

## 전체 제약

- 지정된 세 표본 case만 라이브 비교한다.
- 전수 E2E, Docker, 프런트엔드, 전체 테스트는 실행하지 않는다.
- 모든 브라우저 상태 변경 직전에 1~3초 랜덤 지연을 적용한다.
- Npay가 보이면 Npay 버튼만 클릭하며 일반 링크로 fallback하지 않는다.
- 외부 URL, `/out-link-bridge`, CAPTCHA, 로그인, HTTP 403/429를 우회하지 않는다.
- 사용자 Chrome 프로필, 쿠키, 로컬 스토리지, 로그인 정보를 읽거나 재사용하지 않는다.
- 사용자 요청이 없으므로 git commit은 생성하지 않는다.
- 생성·수정하는 Markdown은 한국어를 먼저, 영어를 뒤에 둔다.

---

### Task 1: 실제 UI selector와 상세 슬라이드 fixture 고정

**파일:**

- 수정: `backend/app/crawler/selectors.py`
- 생성: `backend/tests/fixtures/live_article_slide.html`
- 수정: `backend/tests/unit/test_crawl_scope.py`
- 수정: `backend/tests/unit/test_live_dom.py`

**인터페이스:**

- 생성 selector:

```python
BROKER_NPAY_DETAIL_TRIGGER = (
    "a[data-sentry-component='ButtonBoxLink'][href^='/articles/']"
)
BROKER_STANDARD_DETAIL_TRIGGER = (
    "a[data-nlogs-area='article*l.group'][href^='/articles/'], "
    "a[data-nlogs-area='article*l.list'][href^='/articles/']"
)
DETAIL_SLIDE_ROOT = (
    "div[data-sentry-component='SideLayer']:"
    "has(div[class*='DataList'][class*='term']:text-is('매물번호'))"
)
DETAIL_SLIDE_CLOSE_BUTTON = "button:has-text('창닫기')"
```

- 기존 `DETAIL_READY = "text=매물번호"`는 slide 내부 readiness 확인에 재사용한다.

- [ ] **Step 1: selector 계약과 slide fixture parsing 실패 테스트 작성**

`test_crawl_scope.py`에서 네 selector의 정확한 문자열을 고정한다. `live_article_slide.html`은 관찰한 `SideLayer`, `DataList` label/value, `창닫기`, `/articles/{id}` 구조를 최소 재현한다.

```python
def test_detail_slide_selector_contract_is_exact() -> None:
    assert "data-sentry-component='SideLayer'" in DETAIL_SLIDE_ROOT
    assert "text-is('매물번호')" in DETAIL_SLIDE_ROOT
    assert "ButtonBoxLink" in BROKER_NPAY_DETAIL_TRIGGER
    assert "article*l.group" in BROKER_STANDARD_DETAIL_TRIGGER
```

- [ ] **Step 2: RED 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py tests/unit/test_live_dom.py -q
```

예상: 신규 selector import 또는 slide fixture assertion 실패.

- [ ] **Step 3: 최소 selector와 fixture 구현**

실제 관찰 DOM만 fixture에 넣고 연락처·중개사 주소·장문 소개는 넣지 않는다.

- [ ] **Step 4: GREEN 실행**

동일한 두 파일만 실행하며 신규 selector와 기존 parser가 slide HTML을 처리하는지 확인한다.

---

### Task 2: 상세 슬라이드 원자적 열기·파싱·닫기 구현

**파일:**

- 수정: `backend/app/crawler/browser.py`
- 수정: `backend/tests/unit/test_crawl_scope.py`

**인터페이스:**

```python
async def _collect_slide_article(
    self,
    page,
    card,
    *,
    observation: BrokerCardObservation,
    target: str,
    article_id: str,
    captured_at: datetime,
    blocked_statuses: set[int],
) -> tuple[BrokerArticleDetail, MarketDetails]:
    ...
```

```python
async def _close_detail_slide(self, slide) -> None:
    ...
```

- `target`은 호출 전에 `choose_article_target()`으로 검증된 `/articles/{id}`다.
- `article_url = urljoin("https://fin.land.naver.com", target)`은 결과 metadata에만 사용하며 navigation에는 사용하지 않는다.

- [ ] **Step 1: Npay 우선과 direct goto 금지 RED 작성**

가짜 card에 같은 ID의 Npay 버튼과 일반 버튼을 모두 둔다. `_collect_slide_article()` 호출 후 Npay만 클릭되고 `page.goto()`가 호출되지 않아야 한다.

```python
def test_slide_article_clicks_npay_only_without_direct_navigation(...):
    article, details = asyncio.run(
        collector._collect_slide_article(
            page,
            card,
            observation=BrokerCardObservation(
                article_href="/articles/2637329815",
                provider="아실",
                description="",
                is_npay=True,
            ),
            target="/articles/2637329815",
            article_id="2637329815",
            captured_at=CAPTURED_AT,
            blocked_statuses=set(),
        )
    )
    assert card.npay_clicks == 1
    assert card.standard_clicks == 0
    assert page.goto_calls == []
```

- [ ] **Step 2: 일반 버튼 조건부 사용 RED 작성**

Npay가 없는 observation은 `매물 보러가기`만 클릭해야 한다.

- [ ] **Step 3: slide 범위·ID 검증·닫기 RED 작성**

다음 항목을 별도 테스트로 고정한다.

- parser 두 개에 slide `outerHTML`만 전달
- parsed article ID와 target ID 불일치 시 `SelectorMismatchError`
- 성공·parser 실패 모두 `close_article_detail` 지연 후 창닫기 클릭
- slide가 hidden/detached 될 때까지 대기
- 클릭 이후 새 HTTP 403/429가 관찰되고 slide가 준비되지 않으면 `BlockedCrawlError`

- [ ] **Step 4: RED 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py -q
```

예상: `_collect_slide_article`, `_close_detail_slide` 부재 또는 기존 `_collect_article`의 `goto()` 호출로 실패.

- [ ] **Step 5: 최소 구현**

```python
label = (
    "Npay 부동산에서 보기"
    if observation.is_npay
    else "매물 보러가기"
)
trigger = card.locator(f"a[href='{target}']").filter(has_text=label).first
if not await trigger.count():
    raise SelectorMismatchError(f"{label} 버튼을 찾지 못했습니다.")

before_blocked = set(blocked_statuses)
await self._interaction_delay("open_article_detail")
await trigger.click()

slide = page.locator(DETAIL_SLIDE_ROOT).last
try:
    await slide.locator(DETAIL_READY).first.wait_for(
        state="visible", timeout=15_000
    )
except Exception as exc:
    if blocked_statuses - before_blocked:
        raise BlockedCrawlError(
            "상세 열기 중 접근 제한 응답이 관찰됐습니다."
        ) from exc
    raise SelectorMismatchError(
        "활성 상세 슬라이드를 찾지 못했습니다."
    ) from exc

try:
    html = await slide.evaluate("element => element.outerHTML")
    article = parse_broker_article(
        html,
        article_url=urljoin("https://fin.land.naver.com", target),
        provider=observation.provider or None,
        is_npay=observation.is_npay,
        captured_at=captured_at,
    )
    if article.article_id != article_id:
        raise SelectorMismatchError("열린 상세 매물번호가 대상과 다릅니다.")
    return article, parse_market_details(html, captured_at=captured_at)
finally:
    await self._close_detail_slide(slide)
```

- [ ] **Step 6: GREEN 실행**

`test_crawl_scope.py`만 실행해 상세 UI 계약을 확인한다.

---

### Task 3: virtual list 순회 중 그룹 단위 즉시 상세 수집

**파일:**

- 수정: `backend/app/crawler/browser.py`
- 수정: `backend/tests/unit/test_crawl_scope.py`

**인터페이스:**

```python
@dataclass(slots=True)
class CollectedListingGroup:
    group_html: str
    broker_rows: list[str]
    articles: list[BrokerArticleDetail]
    market_details: MarketDetails | None
    warnings: list[str]
```

```python
async def _collect_visible_group(
    self,
    page,
    card,
    *,
    scope: CrawlScope,
    captured_at: datetime,
    seen_article_ids: set[str],
    blocked_statuses: set[int],
) -> CollectedListingGroup:
    ...
```

`_scan_listing_groups()`는 `CollectedListingGroup` 목록을 반환하며, 각 card가 현재 virtual DOM에 존재할 때 `_collect_visible_group()`을 완료한 다음에만 scroll한다.

- [ ] **Step 1: 그룹 locator 수명 RED 작성**

테스트 event 순서를 다음과 같이 고정한다.

```text
open_group
open_article_detail
close_article_detail
close_group
scroll_listing_list
```

상세 수집이 scroll 이후로 밀리면 실패해야 한다.

- [ ] **Step 2: sampled filter·dedupe RED 작성**

- 기대 ID가 아닌 broker 행은 클릭하지 않는다.
- 같은 article ID는 전체 거래유형에서 한 번만 클릭한다.
- 기대 ID가 그룹에서 발견되면 해당 거래유형 스캔을 즉시 끝낸다.
- unsafe Npay target은 일반 링크로 fallback하지 않고 예외를 전파한다.

- [ ] **Step 3: collector context RED 작성**

`collect()`에서 `context.new_page()`가 map page 한 번만 호출되고 별도 `detail_page`가 생성되지 않는 것을 고정한다.

- [ ] **Step 4: RED 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py -q
```

- [ ] **Step 5: 최소 구조 변경**

- `_broker_rows()`의 “HTML 저장 후 즉시 닫기” 책임을 `_collect_visible_group()`으로 이동한다.
- 그룹이 열린 동안 unique broker row HTML을 만든 뒤, 대상 행마다 exact safe target을 현재 card에서 다시 찾아 `_collect_slide_article()`을 호출한다.
- 모든 대상 처리가 끝난 뒤에만 `close_broker_group` 지연과 Escape를 실행한다.
- single listing은 그룹 open/close 없이 동일 상세 수집 경로를 사용한다.
- 기존 broker-count mismatch, partial warning, 첫 명시 위치, trade count, scroll settle 정책을 유지한다.
- 기존 `_collect_article(detail_page, ...)`와 `detail_page` 생성·close 코드를 삭제한다.

- [ ] **Step 6: GREEN 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py tests/unit/test_live_dom.py tests/unit/test_navigation_policy.py tests/unit/test_humanized_delay.py -q
```

허용된 crawler 관련 네 파일만 실행한다.

---

### Task 4: GPT 브라우저 기준 갱신과 세 표본 E2E

**파일:**

- 수정: `backend/tests/e2e/reference/gpt_naver_observations.json`
- 필요할 때만 수정: `backend/tests/e2e/comparison.py`
- 수정: `docs/testing/naver-live-e2e.md`
- 생성: `.superpowers/sdd/task-ui-slide-report.md`

**인터페이스:**

- 기준 schema와 비교 함수는 기존 `load_reference()`와 `compare_case()`를 유지한다.
- 기준 최대 나이는 30분이다.

- [ ] **Step 1: GPT 브라우저 기준 재수집**

세 case를 순차 방문한다. 각 상태 변경 전 1~3초 대기하고, 거래유형별 기대 article을 실제 그룹 UI로 열어 Npay 우선 정책과 상세 슬라이드 값을 기록한다. 전체 URL, 연락처, 중개사 주소, 장문 소개는 기준 결과에 추가하지 않는다.

- [ ] **Step 2: 표본 라이브 E2E 실행**

```powershell
Set-Location backend
$env:RUN_LIVE_NAVER_E2E = "1"
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -m live_naver -vv -s
```

판정:

- 세 case가 모두 같은 필드값이면 PASS.
- 비교 차이는 `temp/e2e/naver-live/<case-id>/diff.json`으로 확인하고 같은 TC의 최소 parser/selector 수정만 수행.
- HTTP 403/429, CAPTCHA, 로그인 요구면 `E2E_BLOCKED`; PASS로 보고하지 않는다.

- [ ] **Step 3: 문서·보고서 갱신**

한국어 섹션을 먼저 작성하고 영어 섹션을 뒤에 둔다. direct article navigation 제거, UI slide 흐름, Npay 우선, 실행 결과, 전수 미실행을 기록한다.

- [ ] **Step 4: 완료 증거 확인**

새 검증을 추가하지 않고 이 계획에서 승인된 crawler 단위 파일과 sampled live E2E 결과만 최종 보고에 사용한다.

---

# Naver UI Slide Collector Implementation Plan

## English Summary

Task 1 freezes the observed broker-action and detail-slide selectors with a minimal fixture. Task 2 implements an atomic in-page click, active-slide parse, ID validation, and delayed close cycle without any detail navigation. Task 3 moves that cycle inside each live virtual-list card lifetime and removes the separate detail page. Task 4 refreshes the GPT oracle and runs only the three approved sampled live cases.

The implementation must retain safe internal-target validation, Npay precedence, 1–3 second mutation delays, sampled bounds, typed access blocking, and existing comparison semantics. It must not attach to user browser state, spoof automation indicators, bypass restrictions, run exhaustive collection, or execute unrelated builds and test suites.
