# 네이버 UI 슬라이드 수집기 설계

## 한국어

### 목표

생산 Playwright 수집기의 매물 상세 수집을 GPT 브라우저 탐색과 같은 UI 순서로 변경한다. 별도 상세 탭이나 `/articles/{id}` 직접 이동을 제거하고, 단지 목록 페이지에서 중개사 행의 내부 버튼을 클릭해 열린 상세 슬라이드 DOM만 수집한다.

지정된 세 표본 case(`case-131197`, `case-155817`, `case-22746`)는 같은 시점의 GPT 브라우저 기준과 필드 단위로 비교한다.

### 선택한 접근

기존 Playwright 기반을 유지하는 단일 페이지 UI 수집 방식을 선택한다.

1. 단지 URL을 브라우저로 연다.
2. 매매·전세·월세 버튼을 실제로 클릭한다.
3. 매물 그룹의 `중개사 n곳에서 등록했어요`를 클릭한다.
4. 각 중개사 행을 파싱해 안전한 내부 `/articles/{id}` 후보를 확인한다.
5. 같은 행에 `Npay 부동산에서 보기`가 있으면 그 링크만 클릭한다.
6. Npay가 없을 때만 같은 행의 `매물 보러가기`를 클릭한다.
7. 같은 페이지에서 `매물번호`가 포함된 활성 상세 슬라이드를 기다린다.
8. 활성 슬라이드의 `outerHTML`을 기존 상세·시장정보 parser에 전달한다.
9. 상세 슬라이드의 `창닫기` 버튼을 클릭하고 해당 매물 행으로 복귀한다.
10. 그룹 처리가 끝나면 그룹을 접고 다음 그룹으로 이동한다.

### 제외한 접근

- 사용자 Chrome 프로필·쿠키·로그인 세션 연결: 개인정보, 인증 상태, 서버 동시성 문제가 있어 제외한다.
- 네이버 내부 API 직접 호출: 브라우저 UI 탐색 요구와 반대이므로 제외한다.
- `navigator.webdriver` 제거, User-Agent 위장, CAPTCHA·429 우회: 접근 제한 우회에 해당하므로 제외한다.

### 구성요소

#### 브라우저 행 후보

broker row HTML에서 기존 `BrokerCardObservation`을 생성한다. `article_href`, `provider`, `description`, `is_npay`를 유지하며, 선택된 링크의 exact href와 버튼 문구로 현재 카드 내부 locator를 다시 찾는다.

#### 활성 상세 슬라이드

`매물번호` label과 현재 기대 article ID가 함께 존재하는 활성 panel만 상세 루트로 인정한다. 전체 페이지 HTML이 아니라 panel `outerHTML`을 parser에 전달해 배경 목록의 가격·면적·다른 매물 텍스트가 섞이지 않게 한다.

#### 상세 열기·닫기

모든 클릭 직전에 기존 `HumanizedDelay(1~3초)`를 사용한다.

- `open_article_detail`: Npay 또는 매물 보러가기 클릭 직전
- `close_article_detail`: 활성 슬라이드의 창닫기 클릭 직전
- `open_broker_group`, `close_broker_group`: 그룹 버튼 클릭 직전

상세가 닫힌 뒤 `매물번호`가 사라질 때까지 기다린 후 다음 행으로 진행한다.

#### 표본과 전수

표본은 거래유형당 최대 25개 그룹에서 기대 article ID를 찾으면 해당 거래유형을 종료한다. 전수 모드는 기존 명시적 opt-in을 유지하지만 이번 작업에서는 실행하지 않는다.

### 오류 처리

- Npay가 표시된 행에서 Npay가 아닌 링크로 fallback하지 않는다.
- 외부 URL, `/out-link-bridge`, 잘못된 article path는 기존 `UnsafeArticleTarget` hard failure를 유지한다.
- 기대 article ID와 열린 슬라이드의 매물번호가 다르면 `SelectorMismatchError`로 중단한다.
- HTTP 403/429, CAPTCHA, 로그인 요구, 접근 제한은 `E2E_BLOCKED`로 중단하며 우회하지 않는다.
- 상세 수집 중 UI selector가 바뀐 경우 해당 매물은 기존 partial 경고 계약을 유지하되 안전 링크 위반은 숨기지 않는다.

### 테스트 전략

1. 단위 RED/GREEN
   - 상세 수집이 `goto()`를 호출하지 않는지 확인한다.
   - Npay가 있는 행은 Npay locator만 클릭하는지 확인한다.
   - Npay가 없는 행은 매물 보러가기 locator를 클릭하는지 확인한다.
   - 상세 panel의 매물번호가 기대 ID와 일치해야 parser가 호출되는지 확인한다.
   - panel `outerHTML`만 parser에 전달되는지 확인한다.
   - 상세 닫기 전 지연과 창닫기 클릭, 닫힘 대기를 확인한다.
2. GPT 브라우저 기준 갱신
   - 세 case의 거래 건수와 대표 상세 필드를 같은 UI 순서로 다시 관찰한다.
3. 표본 라이브 E2E
   - 생산 수집 결과를 GPT 기준 JSON과 비교한다.
   - 같은 결과이면 세 case 모두 PASS다.
   - 네이버 접근 제한이면 `E2E_BLOCKED`로 기록하며 동일 결과로 간주하지 않는다.

### 성공 기준

- 생산 코드에 `detail_page.goto(article_url)`와 별도 상세 페이지가 없다.
- 상세는 현재 목록 페이지의 내부 UI 클릭과 활성 슬라이드에서만 수집된다.
- Npay 우선 정책과 1~3초 지연이 단위 테스트로 고정된다.
- 세 표본 E2E가 GPT 기준과 일치하거나, 외부 차단 때문에 비교 불가능한 경우 그 사실이 정확히 분류된다.
- 전수 E2E, Docker, 프런트엔드, 전체 테스트는 실행하지 않는다.

---

# Naver UI Slide Collector Design

## English

### Goal

Change the production Playwright collector to follow the same UI sequence as GPT browser exploration. Remove the separate detail tab and direct `/articles/{id}` navigation. Open each broker article through the current complex-list UI and parse only the active detail slide.

The three sampled cases (`case-131197`, `case-155817`, and `case-22746`) are compared field by field against a time-aligned GPT browser reference.

### Selected Approach

Retain Playwright but use a single-page UI workflow:

1. Open the complex URL in a browser.
2. Click the sale, lease, and monthly-rent controls.
3. Expand each broker group.
4. Parse broker-row metadata and validate the internal `/articles/{id}` target.
5. Click only `Npay 부동산에서 보기` when present.
6. Otherwise click the internal `매물 보러가기` control.
7. Wait for the active slide containing `매물번호`.
8. Pass only that slide's `outerHTML` to the existing parsers.
9. Click the slide's `창닫기` button and wait for it to close.
10. Collapse the broker group before moving on.

### Rejected Approaches

- Attaching to a user's Chrome profile, cookies, or authenticated session is rejected for privacy, authentication-state, and concurrency reasons.
- Calling Naver's internal APIs directly contradicts the requested browser workflow.
- WebDriver masking, user-agent spoofing, CAPTCHA handling, or HTTP 429 evasion remain prohibited.

### Components

Broker-row parsing continues to produce `BrokerCardObservation`, retaining the article href, provider, description, and Npay flag. The selected row is clicked by exact safe href and visible action text inside the current card.

The active detail root must contain both the `매물번호` label and the expected article ID. Only its `outerHTML` is parsed, preventing background listing values from contaminating the detail result.

Every state mutation keeps the injected 1–3 second delay. New reasons are `open_article_detail` and `close_article_detail`; the existing group open/close reasons remain.

Sampled collection scans at most 25 groups per trade type and stops after finding the expected article ID for that trade type. Exhaustive mode stays opt-in and is not run in this task.

### Error Handling

- Never fall back from a visible Npay action to another link.
- Preserve hard failures for external URLs, `/out-link-bridge`, and invalid article paths.
- Reject a detail slide whose article ID differs from the expected target.
- Stop as `E2E_BLOCKED` on HTTP 403/429, CAPTCHA, login requirements, or access restrictions.
- Preserve the existing partial-detail warning contract for ordinary detail UI failures without hiding unsafe-link failures.

### Test Strategy

Use focused red/green tests to prove that no detail `goto()` occurs, Npay is preferred, ordinary internal links are used only without Npay, the expected article ID gates parsing, only panel HTML is parsed, and closing the panel is delayed and awaited.

Refresh the three-case GPT browser oracle through the same UI sequence, then run only the sampled live E2E. A successful comparison requires all three cases to match. An external block remains `E2E_BLOCKED` and is never reported as equivalent data.

### Success Criteria

- No separate detail page or direct detail navigation remains.
- Production details come only from current-page UI clicks and the active slide.
- Npay precedence and 1–3 second delays are regression-tested.
- The three sampled cases either match the refreshed GPT reference or accurately report an external block.
- Exhaustive E2E, Docker, frontend checks, and the full test suite remain out of scope.
