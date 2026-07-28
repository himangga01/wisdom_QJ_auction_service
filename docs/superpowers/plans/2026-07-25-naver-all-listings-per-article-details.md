# 네이버 전체 매물·물건별 상세 저장 수정 구현 계획

> **구현 담당 AI:** 구현 승인을 받은 뒤 `superpowers:subagent-driven-development` 또는 `superpowers:executing-plans`를 사용해 체크박스 순서대로 진행한다. 이 문서 작성 단계에서는 코드를 수정하거나 테스트를 실행하지 않는다.

**목표:** 네이버 부동산 URL 한 개에 표시된 매매·전세·월세 전체 매물 그룹과 그룹 안의 모든 중개사 등록 물건을 일반 Chrome UI로 끝까지 확인하고, 각 물건의 상세 슬라이드 정보를 물건별 스냅샷으로 저장·조회·표시·XLSX 출력한다.

**아키텍처:** 수집기는 외부에서 실행된 일반 Google Chrome에 CDP로 연결하고 네이버 화면의 버튼·목록·상세 슬라이드만 조작한다. 고정 스크롤 횟수 대신 화면 표시 건수와 실제 고유 수집 건수를 비교하는 진행 기반 반복을 사용한다. 각 중개사 물건은 `BrokerArticleSnapshot.details_json` 안에 자체 상세정보와 자체 `market_details`를 함께 저장한다.

**기술 스택:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, Playwright CDP, Google Chrome, React 19, TypeScript 6, Tailwind CSS, openpyxl, pytest, Vitest

## 전체 제약

- 네이버 데이터 수집은 일반 Chrome UI와 현재 페이지 DOM으로만 수행한다.
- 네이버 내부 API, 네이버 공식 API, 별도 HTTP 수집기 또는 직접 `requests` 호출을 사용하지 않는다.
- 네이버 페이지와 리소스는 사람이 Chrome을 여는 것과 같이 Chrome 자체가 로드한다. 수집 서비스가 네이버 endpoint를 별도로 호출하지 않는다.
- 이 계획에서 말하는 API는 저장된 결과를 React에 전달하는 **우리 서비스 내부 FastAPI**뿐이다.
- 사용자 기본 Chrome 프로필을 사용하지 않고 `backend/data/naver-chrome-profile` 전용 프로필만 사용한다.
- 모든 페이지 이동, 클릭, 키보드 동작과 스크롤 전에 기존 1~3초 무작위 지연을 유지한다.
- `Npay 부동산에서 보기`가 있으면 내부 Npay 버튼만 클릭하고 out-link bridge는 사용하지 않는다.
- production `CrawlScope.full()`에는 스크롤 횟수, 그룹 수, 물건 수의 고정 상한을 두지 않는다.
- 표본 E2E용 `CrawlScope.sampled()`의 25개 그룹 제한은 production 전체 수집과 분리하여 유지한다.
- 거래유형 표시 건수보다 적게 수집했거나, `중개사 n곳`보다 적게 물건 상세를 저장한 경우 완료 상태로 저장하지 않는다.
- raw 상세 HTML은 DB에 저장하지 않는다. 정제된 필드, 설명, 옵션, 인식하지 못한 라벨 값은 물건별 `extra_fields`에 보존한다.
- 기존 DB의 과거 스냅샷은 `market_details=null`로 읽을 수 있어야 하며 DB 마이그레이션은 추가하지 않는다.
- 관련 없는 전체 테스트, Docker 검증, 프런트엔드 전체 리디자인, git commit은 수행하지 않는다.

## 선택한 방식

### 채택: 표시 건수 + 진행 기반 전체 탐색

각 거래유형에서 화면의 현재 `매물 n개`를 읽고, 가상 스크롤을 끝까지 순회한다. 끝에 도달했는데 수집 건수가 부족하면 맨 위로 돌아가 누락 그룹을 다시 탐색한다. 한 번의 전체 재탐색에서 새로운 고유 그룹이 한 건이라도 추가되면 계속하고, 새 그룹이 전혀 추가되지 않으면서 표시 건수보다 부족하면 명시적 불완전 수집 오류로 종료한다.

### 배제: DOM 끝 도달만으로 완료

가상 스크롤 렌더링 누락이 있어도 완료로 오판할 수 있으므로 사용하지 않는다.

### 배제: 네이버 API 직접 호출

접근 차단 가능성이 있고 사용자가 금지했으므로 사용하지 않는다.

---

### Task 1: 고정 100회 제한 제거와 전체 그룹 완료 조건

**Files:**

- Modify: `backend/app/crawler/browser.py`
- Modify: `backend/app/crawler/errors.py`
- Modify: `backend/tests/unit/test_crawl_scope.py`

**인터페이스:**

- 추가 오류:

```python
class IncompleteListingCollectionError(CrawlError):
    code = "incomplete_listing_collection"
```

- `PlaywrightNaverLandCollector`에 추가할 화면 건수 판독 메서드:

```python
async def _current_trade_count(self, page, trade_type: str) -> int:
    buttons = page.locator(TRADE_COUNT_BUTTON)
    pattern = re.compile(
        rf"^\s*{re.escape(trade_type)}\s*([0-9][0-9,]*)\s*$"
    )
    for index in range(await buttons.count()):
        match = pattern.fullmatch(await buttons.nth(index).inner_text())
        if match is not None:
            return int(match.group(1).replace(",", ""))
    raise SelectorMismatchError(
        f"{trade_type} 거래유형의 현재 표시 건수를 읽지 못했습니다."
    )
```

- `_scan_listing_groups()`에 추가할 keyword-only 입력과 반환 계약:

```python
trade_type: str
expected_group_count: int
return_type: tuple[list[CollectedListingGroup], int]
```

- 소비 항목: `TRADE_COUNT_BUTTON`, `LISTING_CARD`, `LISTING_SCROLL_CONTAINER`, `CrawlScope`
- 반환 튜플의 두 번째 값은 목록 끝에서 다시 읽은 최신 표시 건수다. sampled scope가 조기 종료되면 최초 `expected_group_count`를 그대로 반환한다.

- [ ] **Step 1: 100회보다 긴 가상 목록 RED 작성**

`tests/unit/test_crawl_scope.py`에 150번 이상의 스크롤 갱신 후 마지막 그룹이 나타나는 `_LongVirtualPage`/`_LongVirtualCollector`와, 표시 건수보다 한 건 부족한 `_StalledFullPage`/`_StalledFullCollector`를 추가한다. 두 가짜 page는 `TRADE_COUNT_BUTTON` locator도 구현해 각각 설정된 표시 건수를 반환한다.

```python
def test_full_scan_has_no_fixed_scroll_round_limit() -> None:
    page = _LongVirtualPage(group_count=151)
    collector = _LongVirtualCollector()

    groups, latest_count = asyncio.run(
        collector._scan_listing_groups(
            page,
            CrawlScope.full(),
            trade_type="매매",
            expected_group_count=151,
            captured_at=_UI3_CAPTURED_AT,
            seen_article_ids=set(),
            blocked_statuses=set(),
        )
    )

    assert len(groups) == 151
    assert latest_count == 151
    assert page.container.scroll_mutations >= 150
```

- [ ] **Step 2: RED 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py::test_full_scan_has_no_fixed_scroll_round_limit -q
```

예상 결과: 첫 실행은 새 `trade_type`/`expected_group_count` 계약이 아직 없어 `TypeError`로 실패한다. 새 인자를 먼저 연결하고 기존 반복을 그대로 두면 `_MAX_SCROLL_ROUNDS = 100` 때문에 `SelectorMismatchError`로 실패한다.

- [ ] **Step 3: 고정 횟수 반복 제거**

`_MAX_SCROLL_ROUNDS`와 더 이상 사용하지 않는 `_STABLE_SCROLL_ROUNDS`를 삭제하고 다음 진행 기반 구조로 바꾼다.

```python
seen = set()
groups: list[CollectedListingGroup] = []
container = page.locator(LISTING_SCROLL_CONTAINER).first
if not await container.count():
    raise SelectorMismatchError("매물 스크롤 영역을 찾지 못했습니다.")

full_collection = _is_full_collection(scope)
full_pass_start_count = len(groups)
latest_count = expected_group_count

while True:
    cards = page.locator(LISTING_CARD)
    for index in range(await cards.count()):
        if not _should_scan_group(scope, groups_scanned=len(groups)):
            return groups, latest_count
        card = cards.nth(index)
        key = await self._card_key(card)
        if key in seen:
            continue
        seen.add(key)
        groups.append(
            await self._collect_visible_group(
                page,
                card,
                scope=scope,
                captured_at=captured_at,
                seen_article_ids=seen_article_ids,
                blocked_statuses=blocked_statuses,
            )
        )

    at_end = await container.evaluate(
        "element => element.scrollTop + element.clientHeight "
        ">= element.scrollHeight - 2"
    )
    if at_end:
        if not full_collection:
            return groups, latest_count
        latest_count = await self._current_trade_count(page, trade_type)
        if len(groups) >= latest_count:
            return groups, latest_count
        if len(groups) == full_pass_start_count:
            raise IncompleteListingCollectionError(
                f"{trade_type} 표시 {latest_count}건 중 "
                f"{len(groups)}건만 수집했습니다."
            )
        full_pass_start_count = len(groups)
        await self._reset_listing_scroll(page)
        continue

    previous_snapshot = await self._listing_snapshot(page)
    await self._interaction_delay("scroll_listing_list")
    await container.evaluate(
        "element => { element.scrollTop = Math.min("
        "element.scrollHeight, element.scrollTop + "
        "Math.max(element.clientHeight, 600)); }"
    )
    await self._wait_for_listing_settle(page, previous_snapshot)
```

`collect()`에서 현재 `trade_type`과 `trade_counts[trade_type]`을 전달하고, 반환된 `latest_count`로 `trade_counts[trade_type]`을 갱신한다. 이로써 실행 중 추가·삭제된 표시 건수를 최종 payload에도 반영한다. sampled scope의 예상 article 조기 종료 분기는 기존대로 유지하되 `(groups, latest_count)`를 반환한다. 기존 테스트의 `_scan_listing_groups()` override와 직접 호출부도 동일한 keyword 인자와 튜플 반환 계약으로 한 번에 갱신한다.

- [ ] **Step 4: GREEN 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py::test_full_scan_has_no_fixed_scroll_round_limit tests/unit/test_crawl_scope.py::test_scan_reenumerates_page_root_after_each_virtual_group tests/unit/test_crawl_scope.py::test_full_scroll_settles_after_each_scroll_mutation -q
```

예상 결과: 3개 테스트 통과.

- [ ] **Step 5: 진행 없는 불완전 목록 RED/GREEN**

표시 건수는 5건인데 전체 위·아래 재탐색 후에도 고유 그룹이 4건인 경우 성공 반환하지 않고 `IncompleteListingCollectionError`를 발생시키는 테스트를 작성한 뒤 통과시킨다.

```python
def test_full_scan_fails_closed_when_end_is_stable_but_count_is_short() -> None:
    with pytest.raises(
        IncompleteListingCollectionError,
        match="표시 5건 중 4건",
    ):
        asyncio.run(
            _StalledFullCollector()._scan_listing_groups(
                _StalledFullPage(group_count=4, displayed_count=5),
                CrawlScope.full(),
                trade_type="매매",
                expected_group_count=5,
                captured_at=_UI3_CAPTURED_AT,
                seen_article_ids=set(),
                blocked_statuses=set(),
            )
        )
```

---

### Task 2: 모든 중개사 등록 물건 상세 클릭 보장

**Files:**

- Modify: `backend/app/crawler/browser.py`
- Modify: `backend/app/crawler/live_dom.py`
- Modify: `backend/tests/unit/test_crawl_scope.py`
- Modify: `backend/tests/unit/test_live_dom.py`

**인터페이스:**

- 입력: 펼쳐진 `BROKER_ARTICLE_LINK` 전체 목록과 `displayed_broker_count`
- 출력: 한 그룹의 모든 고유 article ID가 들어 있는 `CollectedListingGroup.articles`
- 추가 helper 계약: `_collect_expanded_broker_rows(card, expected_count)`는 현재 DOM에 보이는 행만 한 번 읽고 끝내지 않고, 고유 행 수가 `expected_count`에 도달할 때까지 마지막 행을 Chrome UI로 스크롤하며 재조회한다.
- `live_dom.py` 계약: 기존 broker count 파싱을 `parse_live_displayed_broker_count(html) -> int | None`로 분리하고 `parse_live_listing_group()`도 같은 helper를 사용한다.

- [ ] **Step 1: 그룹 전체 물건 순회 계약과 지연 로딩 RED 작성**

중개사 120곳을 가진 가짜 그룹을 만들고 `CrawlScope.full()`에서 120개 물건 상세를 모두 여는 테스트를 작성한다.

```python
def test_full_group_opens_every_unique_broker_article() -> None:
    rows = [_ui3_row(str(index)) for index in range(1, 121)]
    card = _Ui3Card("<li>group</li>", rows, grouped=True)
    collector = _Ui3Collector()

    result = _run_visible_group(
        collector,
        _Ui3Page([card]),
        card,
        scope=CrawlScope.full(),
        seen_article_ids=set(),
    )

    assert collector.slide_calls == [str(index) for index in range(1, 121)]
    assert len(result.articles) == 120
```

같은 테스트 대역에서 최초 10개 행만 DOM에 두고 마지막 행을 스크롤할 때마다 다음 행이 나타나게 한 `test_expanded_group_loads_rows_until_displayed_count()`도 추가한다. 기대값은 `displayed_broker_count=120`, 반환 고유 행 120개, 상세 클릭 120회다. 정적 120행 테스트는 기존 전체 순회 동작을 보호하는 characterization test이고, 지연 로딩 테스트가 이 Task의 RED다.

```python
def test_parses_live_displayed_broker_count() -> None:
    html = "<button>중개사 120곳에서 등록했어요</button>"
    assert parse_live_displayed_broker_count(html) == 120
```

- [ ] **Step 2: RED 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py::test_expanded_group_loads_rows_until_displayed_count -q
```

예상 결과: 현재 `_wait_for_expanded_broker_links()`가 최초로 붙은 행 목록을 즉시 반환하므로 10건만 확인되고 120건 기대값에서 실패한다.

- [ ] **Step 3: 전체 그룹 수집 로직 정리**

production full scope에서는 다음 규칙을 적용한다.

그룹 HTML을 `parse_live_displayed_broker_count()`로 먼저 읽어 `displayed_broker_count`를 확보하고, 펼친 목록이 그 수에 도달할 때까지 다음 로직으로 행을 모은다. 전체 listing parser를 조기 호출하지 않으므로 거래유형·가격 파싱 시점은 바뀌지 않는다.

```python
rows_by_article_id: dict[str, str] = {}
while True:
    broker_links = card.locator(BROKER_ARTICLE_LINK)
    for index in range(await broker_links.count()):
        row_html = await broker_links.nth(index).evaluate(
            "element => element.closest('li')?.outerHTML || ''"
        )
        if not row_html:
            raise SelectorMismatchError(
                "중개사 매물 링크의 li 행을 찾지 못했습니다."
            )
        article_id = _broker_target(row_html)[2]
        rows_by_article_id.setdefault(article_id, row_html)

    if (
        expected_count is None
        or len(rows_by_article_id) >= expected_count
    ):
        return list(rows_by_article_id.values())

    previous_count = await broker_links.count()
    await self._interaction_delay("scroll_expanded_broker_list")
    await broker_links.last.scroll_into_view_if_needed()
    try:
        await card.locator(BROKER_ARTICLE_LINK).nth(
            previous_count
        ).wait_for(state="attached", timeout=8_000)
    except Exception as exc:
        raise IncompleteListingCollectionError(
            f"중개사 {expected_count}곳 중 "
            f"{len(rows_by_article_id)}곳만 목록에서 확인했습니다."
        ) from exc
```

8초는 다음 DOM 행이 나타나는 UI 대기시간이며, 물건 수나 반복 횟수의 상한이 아니다. 행이 추가되는 동안에는 등록 수와 무관하게 계속 진행한다.

확보한 모든 행에 대해서는 다음 순서로 상세를 연다.

```python
for broker_html in rows:
    observation, target, article_id = _broker_target(broker_html)
    if article_id in seen_article_ids:
        continue
    current_card = await self._current_card_for_target(page, target)
    article, details = await self._collect_slide_article(
        page,
        current_card,
        observation=observation,
        target=target,
        article_id=article_id,
        captured_at=captured_at,
        blocked_statuses=blocked_statuses,
    )
    seen_article_ids.add(article_id)
    articles.append(article)
```

상세 성공 전에 `seen_article_ids`에 추가하지 않는다. 상세 파싱이 실패한 article은 성공 수와 저장 대상에 포함하지 않으며, full scope에서는 Task 4의 완전성 검사에 의해 전체 실행이 실패한다.

표시 중개사 수가 있으면 그 값을 기대 수로 사용한다. 표시 수를 파싱하지 못한 단일 물건 카드는 펼쳐진 내부 행의 고유 article ID 수를 기대 수로 사용한다. 따라서 중개사 수 표기가 없는 카드도 상세 누락을 성공으로 처리하지 않는다.

- [ ] **Step 4: GREEN 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_live_dom.py::test_parses_live_displayed_broker_count tests/unit/test_crawl_scope.py::test_full_group_opens_every_unique_broker_article tests/unit/test_crawl_scope.py::test_expanded_group_loads_rows_until_displayed_count tests/unit/test_crawl_scope.py::test_visible_group_separates_row_article_and_global_dedupe_and_warnings tests/unit/test_crawl_scope.py::test_each_detail_reacquires_current_card_by_exact_target_after_retarget -q
```

---

### Task 3: 물건별 상세·시세 데이터 모델

**Files:**

- Modify: `backend/app/crawler/types.py`
- Modify: `backend/app/crawler/browser.py`
- Modify: `backend/tests/unit/test_crawl_scope.py`
- Modify: `backend/tests/integration/test_persistence.py`

**인터페이스:**

- `MarketDetails` 선언을 `BrokerArticleDetail` 위로 이동한 뒤 추가할 필드:

```python
market_details: MarketDetails | None = None
```

- 호환성: `ListingDetail.market_details`는 과거 API 호환용 대표값으로 유지한다.

- [ ] **Step 1: 물건마다 서로 다른 상세지표를 갖는 RED 작성**

두 중개사 물건이 서로 다른 금융·관리비 상세를 반환하도록 구성하고, 반환된 두 `BrokerArticleDetail`에 각각의 값이 붙는지 확인한다.

```python
def test_each_broker_article_keeps_its_own_market_details() -> None:
    market_a = MarketDetails(
        finance={"대출한도": "5억"},
        captured_at=_UI3_CAPTURED_AT,
    )
    market_b = MarketDetails(
        finance={"대출한도": "7억"},
        captured_at=_UI3_CAPTURED_AT,
    )
    rows = [_ui3_row("1"), _ui3_row("2")]
    card = _Ui3Card("<li>group</li>", rows, grouped=True)
    collector = _Ui3Collector(
        outcomes={
            "1": (_ui3_article("1"), market_a),
            "2": (_ui3_article("2"), market_b),
        }
    )
    result = _run_visible_group(
        collector,
        _Ui3Page([card]),
        card,
        scope=CrawlScope.full(),
        seen_article_ids=set(),
    )

    assert result.articles[0].market_details.finance == {"대출한도": "5억"}
    assert result.articles[1].market_details.finance == {"대출한도": "7억"}
    assert result.articles[0].market_details is not result.articles[1].market_details
```

- [ ] **Step 2: RED 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py::test_each_broker_article_keeps_its_own_market_details -q
```

예상 결과: 현재 `BrokerArticleDetail`에 `market_details`가 없고 그룹의 첫 상세값만 남으므로 실패한다.

- [ ] **Step 3: 물건 모델과 수집 결과 연결**

`MarketDetails`를 `BrokerArticleDetail`보다 먼저 선언하고 필드를 추가한다. 상세 슬라이드를 파싱한 뒤 해당 물건에 자체 상세지표를 결합한다.

```python
market_details = parse_market_details(html, captured_at=captured_at)
article = article.model_copy(
    update={"market_details": market_details}
)
return article, market_details
```

그룹의 `market_details`는 기존 클라이언트 호환을 위해 첫 번째 물건 값을 유지하지만, 물건별 원본은 각 `BrokerArticleDetail.market_details`가 된다.

- [ ] **Step 4: persistence RED 작성**

`test_new_listing_snapshot_aggregate_and_event_share_one_transaction()`의 payload에 다음 `MarketDetails`를 넣고, 기존 저장 검증 뒤에 snapshot 검증을 추가한다. `MarketDetails` import도 함께 추가한다.

```python
article_market = MarketDetails(
    finance={"대출한도": "5억"},
    captured_at=now,
)

broker_snapshot = next(
    value
    for value in session.added
    if isinstance(value, BrokerArticleSnapshot)
)
assert broker_snapshot.details_json["market_details"]["finance"] == {
    "대출한도": "5억"
}
```

위 `article_market`은 테스트 payload의 `BrokerArticleDetail(market_details=article_market)`에 전달한다.

- [ ] **Step 5: GREEN 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py::test_each_broker_article_keeps_its_own_market_details tests/integration/test_persistence.py::test_new_listing_snapshot_aggregate_and_event_share_one_transaction -q
```

`details_json`이 JSON 컬럼이므로 DB 마이그레이션은 만들지 않는다.

---

### Task 4: 불완전 수집의 완료 저장 차단

**Files:**

- Modify: `backend/app/crawler/browser.py`
- Modify: `backend/app/crawler/errors.py`
- Modify: `backend/tests/unit/test_crawl_scope.py`
- Modify: `backend/app/tasks/crawl_tasks.py` only if error mapping requires an explicit branch

**인터페이스:**

- 결과: 전체 수집 부족 시 `IncompleteListingCollectionError`
- 불변 조건:

```text
거래유형별 고유 그룹 수 >= 화면 표시 그룹 수
각 그룹의 저장 article 수 == 화면 표시 중개사 수
화면 표시 중개사 수가 없으면 저장 article 수 == 펼친 행의 고유 article ID 수
```

- [ ] **Step 1: 중개사 표시 수 불일치 RED 작성**

```python
def test_full_collection_rejects_group_with_missing_broker_details(
    monkeypatch,
) -> None:
    articles = [_ui3_article(str(index)) for index in range(1, 7)]
    group = browser_module.CollectedListingGroup(
        group_html="broker-short-group",
        broker_rows=[_ui3_row(str(index)) for index in range(1, 8)],
        articles=articles,
        market_details=MarketDetails(captured_at=_UI3_CAPTURED_AT),
        warnings=[],
    )
    collector = _AssemblyCollector(
        [group],
        attempted_ids={article.article_id for article in articles},
    )
    listing = ListingDetail(
        trade_type="매매",
        displayed_broker_count=7,
        captured_at=_UI3_CAPTURED_AT,
    )
    with pytest.raises(
        IncompleteListingCollectionError,
        match="중개사 7곳 중 6건",
    ):
        _run_collect_assembly(
            monkeypatch,
            collector=collector,
            scope=CrawlScope.full(),
            trade_counts={"매매": 1},
            listings_by_html={"broker-short-group": listing},
        )
```

`_AssemblyCollector._scan_listing_groups()` 테스트 대역도 새 keyword 인자 `trade_type`, `expected_group_count`를 받고 `(self.groups, expected_group_count)`를 반환하도록 갱신한다.

- [ ] **Step 2: 전체 수집 fail-closed 구현**

기존 full scope의 `listing_count_mismatch`, `broker_count_mismatch`, `detail_collection_failed` 경고 후 부분 저장을 다음처럼 변경한다.

```python
if full_collection and latest_count > len(collected_groups):
    raise IncompleteListingCollectionError(
        f"{trade_type} 표시 {latest_count}건 중 "
        f"{len(collected_groups)}건만 수집했습니다."
    )

expected_broker_count = (
    listing.displayed_broker_count
    if listing.displayed_broker_count is not None
    else len(
        {
            _broker_target(row_html)[2]
            for row_html in group.broker_rows
        }
    )
)
if full_collection and len(group.articles) != expected_broker_count:
    raise IncompleteListingCollectionError(
        f"중개사 {expected_broker_count}곳 중 "
        f"{len(group.articles)}건의 상세만 수집했습니다."
    )

if full_collection and group.warnings:
    raise IncompleteListingCollectionError(
        "물건 상세 수집 경고: " + ", ".join(group.warnings)
    )
```

표본 E2E는 기존처럼 예상 article만 비교하므로 sampled scope의 경고 동작은 유지한다.

- [ ] **Step 3: 작업 상태 계약 확인**

`crawl_tasks.py`의 기존 `except CrawlError` 경로를 사용해 `error_code="incomplete_listing_collection"`, `status="failed"`로 종료한다. 불완전 payload는 `PersistenceService.persist()`에 전달하지 않는다.

- [ ] **Step 4: GREEN 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py::test_full_scan_fails_closed_when_end_is_stable_but_count_is_short tests/unit/test_crawl_scope.py::test_full_collection_rejects_group_with_missing_broker_details tests/unit/test_crawl_scope.py::test_collect_assembly_uses_success_ids_and_group_warning_for_partial -q
```

마지막 기존 테스트는 sampled scope의 부분 결과 계약이 유지되는지 확인한다.

---

### Task 5: 우리 FastAPI의 물건별 상세 응답

**Files:**

- Modify: `backend/app/schemas/listing.py`
- Modify: `backend/app/services/query_service.py`
- Create: `backend/tests/unit/test_per_article_market_details.py`

**인터페이스:**

- `MarketDetails`를 `BrokerRegistration`보다 먼저 선언한 뒤 추가할 응답 필드:

```python
market_details: MarketDetails | None = None
```

- [ ] **Step 1: 과거·신규 스냅샷 응답 RED 작성**

```python
def test_snapshot_market_details_maps_nested_article_json() -> None:
    value = QueryService._snapshot_market_details(
        {"finance": {"대출한도": "5억"}}
    )
    assert value is not None
    assert value.finance == {"대출한도": "5억"}


def test_snapshot_market_details_maps_legacy_none() -> None:
    assert QueryService._snapshot_market_details(None) is None
```

- [ ] **Step 2: 내부 API 스키마와 query mapping 구현**

`query_service.py`에 중첩 JSON을 `MarketDetails`로 변환하는 순수 helper를 만들고 `_broker_registrations()`에서 사용한다.

```python
@staticmethod
def _snapshot_market_details(
    value: dict[str, Any] | None,
) -> MarketDetails | None:
    if not value:
        return None
    return MarketDetails(
        finance=camelize_json(value.get("finance") or {}),
        transactions=camelize_json(value.get("transactions") or {}),
        costs=camelize_json(value.get("costs") or {}),
        maintenance=camelize_json(value.get("maintenance") or {}),
        complex=camelize_json(value.get("complex") or {}),
        location=camelize_json(value.get("location") or {}),
        extra_fields=camelize_json(value.get("extra_fields") or {}),
    )


market_details=self._snapshot_market_details(
    details.get("market_details")
),
```

이 단계는 DB에 저장된 결과를 우리 React에 전달할 뿐 네이버에 요청하지 않는다.

- [ ] **Step 3: GREEN 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_per_article_market_details.py -q
```

---

### Task 6: React 물건별 상세 카드 표시

**Files:**

- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/realEstate.ts`
- Modify: `frontend/src/adapters/realEstate.ts`
- Modify: `frontend/src/pages/ListingDetailPage.tsx`
- Create: `frontend/src/tests/ListingDetailPage.market-details.test.tsx`

**인터페이스:**

- 입력: `BrokerRegistrationApi.marketDetails`
- 출력: 접힌 `중개사 n곳에서 등록했어요` 영역 안의 물건별 `RegistrationCard` 상세 섹션

- [ ] **Step 1: 타입과 화면 RED 작성**

```tsx
function makeRegistration(
  articleId: string,
  loanLimit: string,
): BrokerRegistration {
  return {
    articleId,
    realtorName: `중개사 ${articleId}`,
    provider: '네이버부동산',
    description: '',
    verifiedAt: '2026-07-25',
    articleUrl: `/articles/${articleId}`,
    marketDetails: {
      finance: { 대출한도: loanLimit },
      transactions: {},
      costs: {},
      maintenance: {},
      complex: {},
      location: {},
      extraFields: {},
    },
  }
}

it('renders distinct market details inside each broker article card', () => {
  render(
    <>
      <RegistrationCard registration={makeRegistration('a', '5억')} />
      <RegistrationCard registration={makeRegistration('b', '7억')} />
    </>,
  )

  expect(
    within(screen.getByTestId('registration-a')).getByText('5억')
  ).toBeInTheDocument()
  expect(
    within(screen.getByTestId('registration-b')).getByText('7억')
  ).toBeInTheDocument()
})
```

- [ ] **Step 2: 타입·adapter 구현**

```ts
// frontend/src/types/api.ts의 BrokerRegistrationApi에 추가
marketDetails: MarketDetailsApi | null

// frontend/src/types/realEstate.ts에서 BrokerRegistration보다 먼저 선언
export interface StructuredMarketDetails {
  finance: Record<string, unknown>
  transactions: Record<string, unknown>
  costs: Record<string, unknown>
  maintenance: Record<string, unknown>
  complex: Record<string, unknown>
  location: Record<string, unknown>
  extraFields: Record<string, unknown>
}

// BrokerRegistration에 추가
marketDetails?: StructuredMarketDetails
```

`adaptRegistration()`에서 `marketDetails: registration.marketDetails ?? undefined`로 매핑한다.

- [ ] **Step 3: 물건별 카드 표시 구현**

`RegistrationCard`를 named export로 바꾸고 `<article data-testid={\`registration-${registration.articleId}\`}>`를 지정한다. 카드 안에서 해당 물건의 `marketDetails`를 렌더링한다. 전체 그룹 아래에 있던 `apiMarket`은 과거 스냅샷에 물건별 상세가 없을 때만 fallback으로 표시한다.

`RegistrationCard` 내부:

```tsx
{registration.marketDetails ? (
  <ApiMarketDetails details={registration.marketDetails} />
) : null}
```

`ListingDetailPage`의 `return` 앞과 기존 그룹 대표 상세 위치:

```tsx
const hasPerRegistrationMarket = listing.registrations.some(
  (registration) => Boolean(registration.marketDetails),
)

{apiMarket && !hasPerRegistrationMarket ? (
  <ApiMarketDetails details={apiMarket} />
) : null}
```

`<details>`는 기본적으로 접힌 상태를 유지하며, 펼치면 모든 중개사 물건 카드가 보인다.

- [ ] **Step 4: GREEN 실행**

```powershell
Set-Location frontend
npm test -- src/tests/ListingDetailPage.market-details.test.tsx
```

---

### Task 7: XLSX 물건별 상세지표 출력

**Files:**

- Modify: `backend/app/services/export_service.py`
- Modify: `backend/tests/integration/test_export.py`
- Create: `backend/tests/integration/test_export_per_article_market_details.py`
- Modify: `frontend/src/utils/exportWorkbook.ts` for demo/local in-browser export parity

**인터페이스:**

- 확장 시트: `중개사등록`
- 추가 열:

```text
물건별금융JSON
물건별실거래JSON
물건별비용세금JSON
물건별관리비JSON
물건별단지JSON
물건별입지교통JSON
물건별추가필드JSON
```

- [ ] **Step 1: XLSX RED 작성**

서로 다른 `market_details`를 가진 두 `BrokerArticleSnapshot`을 export하고 `중개사등록` 시트의 각 행이 해당 물건 값을 갖는지 확인한다.

새 테스트 파일에 `AsyncSession.stream()`이 두 `(BrokerArticleSnapshot, BrokerArticle, ListingGroup)` 행을 반환하는 최소 테스트 대역을 만들고, `ExportService._append_brokers()` 결과를 메모리 workbook으로 읽는다. 첫 행의 금융 JSON은 5억, 두 번째 행은 7억이어야 한다.

```python
assert row_a["물건별금융JSON"] == '{"대출한도": "5억"}'
assert row_b["물건별금융JSON"] == '{"대출한도": "7억"}'
```

- [ ] **Step 2: export 구현**

`snapshot.details_json["market_details"]`를 읽어 각 중개사등록 행에 7개 JSON 열을 추가한다. 기존 그룹 단위 `상세지표` 시트는 과거 파일 호환을 위해 유지한다.

- [ ] **Step 3: GREEN 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/integration/test_export.py tests/integration/test_export_per_article_market_details.py -q
```

---

### Task 8: 구현 범위 집중 확인과 문서 갱신

**Files:**

- Modify: `docs/testing/naver-live-e2e.md`
- Modify: `docs/setup/local-setup.md`
- Modify: `README.md`
- Create: `.superpowers/sdd/2026-07-25-naver-all-listings-per-article-details/progress.md`

- [ ] **Step 1: 백엔드 집중 테스트**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_crawl_scope.py tests/integration/test_persistence.py tests/unit/test_per_article_market_details.py tests/integration/test_export.py tests/integration/test_export_per_article_market_details.py -q
```

- [ ] **Step 2: 프런트엔드 집중 테스트**

```powershell
Set-Location frontend
npm test -- src/tests/ListingDetailPage.market-details.test.tsx
```

- [ ] **Step 3: 기존 표본 E2E 계약 확인**

기존 표본 E2E는 production 전체 수집이 아니라 선택 article 비교용이므로 `CrawlScope.sampled()`를 유지한다. 사용자가 별도로 실사이트 실행을 승인한 경우에만 전용 Chrome을 시작해 세 표본 E2E를 실행한다.

```powershell
.\scripts\start-naver-browser.ps1
Set-Location backend
$env:RUN_LIVE_NAVER_E2E = "1"
$env:NAVER_E2E_CDP_URL = "http://127.0.0.1:42973"
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py::test_sampled_naver_live_scrape -q -s
```

- [ ] **Step 4: 실사이트 전수 실행은 별도 승인**

전수 실행은 매물·중개사 수만큼 상세 슬라이드를 모두 열기 때문에 수십 분에서 수 시간이 걸릴 수 있다. 계획 승인만으로 자동 실행하지 않으며, 사용자가 실행 대상 URL과 실행을 명시적으로 승인한 경우에만 `CrawlScope.full()`로 수행한다.

- [ ] **Step 5: 문서 기록**

한국어 섹션을 먼저 작성하고 다음 내용을 기록한다.

- production 전체 수집에는 고정 스크롤 상한이 없음
- 표시 건수와 수집 건수 불일치 시 실패 처리
- 중개사 물건별 상세·시세 JSON 저장
- 네이버 API 직접 호출 금지
- 우리 FastAPI는 DB 조회 전용
- 과거 스냅샷의 물건별 `market_details`는 `null`

---

# Naver Full Listing and Per-Article Detail Implementation Plan

## English / AI-readable Contract

Implementation workers must use `superpowers:subagent-driven-development` or `superpowers:executing-plans` only after implementation approval.

### Goal

Collect every visible sale, jeonse, and monthly listing group for one Naver Land URL, expand every broker group, open every unique internal article detail action, and persist article-specific structured detail and market data.

### Network boundary

- Naver acquisition: ordinary Google Chrome UI + in-page DOM through loopback CDP only.
- Chrome loads the Naver page and its resources through normal browser navigation; the collector does not issue separate Naver endpoint calls.
- Forbidden: direct Naver APIs, HTTP scraping clients, requests-based endpoints, out-link bridges, stealth, profile spoofing, CAPTCHA bypass, or proxy rotation.
- Internal FastAPI: reads persisted database records for React and XLSX only.

### Completion invariants

```text
collected unique groups >= current displayed trade count
stored unique broker articles == displayed broker count for every group
when displayed broker count is absent, stored unique broker articles == unique expanded broker-row article IDs
every stored broker article has its own detail snapshot
full collection never persists an incomplete payload
```

### Termination model

- No fixed scroll-round or group-count ceiling in `CrawlScope.full()`.
- Continue while a full pass adds at least one new unique group.
- Complete only when the current displayed count is satisfied.
- Fail closed with `incomplete_listing_collection` when a full top-to-bottom pass makes no progress while the count remains short.
- `CrawlScope.sampled()` keeps its explicit 25-group test-only boundary.

### Data contract

```python
BrokerArticleDetail.market_details: MarketDetails | None
BrokerRegistration.market_details: MarketDetails | None
```

The nested structure is stored inside the existing JSON snapshot column, so no database migration is required. Legacy snapshots deserialize with `None`.

### Task dependency order

```text
Task 1 unlimited progress-based scan
  -> Task 2 every broker article lifecycle
  -> Task 3 per-article detail model
  -> Task 4 fail-closed completeness
  -> Task 5 internal FastAPI response
  -> Task 6 React per-article display
  -> Task 7 XLSX per-article columns
  -> Task 8 focused checks and documentation
```

### Explicit exclusions

- No Naver API integration.
- No raw HTML persistence.
- No Docker validation.
- No broad unrelated test suite.
- No live full crawl without separate user approval.
- No git commit.
