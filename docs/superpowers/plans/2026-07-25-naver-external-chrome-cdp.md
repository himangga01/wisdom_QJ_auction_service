# 네이버 외부 Chrome CDP 수집기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**목표:** 로컬 생산 수집기가 Playwright로 브라우저를 실행하지 않고, 전용 프로필을 가진 일반 Chrome에 CDP로 연결해 승인된 네이버 세 case의 실제 상세 데이터를 GPT 브라우저 기준과 비교한다.

**아키텍처:** PowerShell 로컬 실행기가 loopback CDP Chrome agent를 먼저 시작한다. Python `browser_runtime.py`는 외부 Chrome과 기존 Playwright 실행 방식을 하나의 async context manager로 추상화하며, `browser.py`는 받은 page에서 기존 UI 수집만 담당한다.

**기술 스택:** Python 3.13, Playwright async Python, Google Chrome 150, PowerShell 7/Windows PowerShell, pytest

## 전체 제약

- 한국어 문서가 항상 영어 섹션보다 먼저 온다.
- 사용자 기본 Chrome 프로필을 사용하지 않는다.
- CDP는 `127.0.0.1:42973`에만 연다.
- stealth, webdriver 위장, fingerprint 변경, CAPTCHA solver, proxy 회전을 추가하지 않는다.
- 기존 1~3초 랜덤 지연과 Npay 우선 정책을 유지한다.
- 승인된 crawler 집중 단위 파일과 세 표본 live E2E만 실행한다.
- Docker, 프런트엔드 build, 전체 테스트, 전수 E2E, git commit은 실행하지 않는다.

---

### Task 1: 외부 Chrome browser runtime

**파일:**

- 생성: `backend/app/crawler/browser_runtime.py`
- 수정: `backend/app/crawler/errors.py`
- 수정: `backend/app/crawler/browser.py`
- 생성: `backend/tests/unit/test_browser_runtime.py`
- 수정: `backend/tests/unit/test_crawl_scope.py`

**인터페이스:**

```python
BrowserMode = Literal["external_chrome", "playwright"]

@asynccontextmanager
async def open_crawler_page(
    playwright: object,
    settings: Settings,
) -> AsyncIterator[object]:
    ...
```

- [x] **Step 1: CDP lifecycle RED 작성**

가짜 Chromium에서 `connect_over_cdp()`가 정확한 URL로 한 번 호출되고, `browser.contexts[0].new_page()`가 사용되며, 종료 시 page와 연결 Browser만 닫히고 기본 context는 닫히지 않는 테스트를 작성한다.

- [x] **Step 2: RED 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_browser_runtime.py tests/unit/test_crawl_scope.py -q
```

예상: `browser_runtime` 부재와 기존 `collect()` 내부 `launch()`로 실패.

- [x] **Step 3: 최소 runtime 구현**

```python
@asynccontextmanager
async def open_crawler_page(playwright, settings):
    if settings.crawler_browser_mode == "external_chrome":
        try:
            browser = await playwright.chromium.connect_over_cdp(
                settings.crawler_cdp_url
            )
        except Exception as exc:
            raise BrowserUnavailableError(
                "전용 Chrome 브라우저에 연결할 수 없습니다."
            ) from exc
        if not browser.contexts:
            await browser.close()
            raise BrowserUnavailableError(
                "전용 Chrome의 기본 브라우저 context가 없습니다."
            )
        context = browser.contexts[0]
        page = await context.new_page()
        try:
            yield page
        finally:
            await page.close()
            await browser.close()
        return

    browser = await playwright.chromium.launch(
        headless=settings.crawler_headless
    )
    context = await browser.new_context()
    page = await context.new_page()
    try:
        yield page
    finally:
        await context.close()
        await browser.close()
```

`browser.py.collect()`는 이 context manager 안에서 기존 수집 본문을 실행한다.

- [x] **Step 4: GREEN 실행**

Task 1의 두 파일만 실행해 lifecycle 계약을 확인한다.

---

### Task 2: 설정과 로컬 Chrome agent

**파일:**

- 수정: `backend/app/core/config.py`
- 수정: `backend/.env.example`
- 수정: `scripts/runtime-common.ps1`
- 생성: `scripts/start-naver-browser.ps1`
- 수정: `scripts/start-local.ps1`
- 수정: `scripts/status.ps1`
- 수정: `scripts/stop-local.ps1`
- 수정: `.gitignore`
- 수정: `backend/tests/unit/test_runtime_config.py`

**인터페이스:**

```python
crawler_browser_mode: Literal["external_chrome", "playwright"] = (
    "external_chrome"
)
crawler_cdp_url: str = "http://127.0.0.1:42973"
```

- [x] **Step 1: 설정 RED 작성**

로컬 기본이 `external_chrome`이고 CDP URL scheme/host/port가 정확하며 외부 host URL을 거부하는 테스트를 작성한다.

- [x] **Step 2: RED 실행**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_runtime_config.py -q
```

- [x] **Step 3: 설정과 실행 스크립트 구현**

`start-naver-browser.ps1`은 설치 Chrome, 전용 프로필, loopback port, `/json/version` readiness, PID 기록을 처리한다. `start-local.ps1`은 이를 API보다 먼저 호출한다. stop/status는 기록된 전용 프로세스만 다룬다.

- [x] **Step 4: PowerShell 계약 확인**

새 프로세스를 추가 실행하지 않고 parser와 문자열 계약만 확인한다.

```powershell
$null = [scriptblock]::Create((Get-Content .\scripts\start-naver-browser.ps1 -Raw))
Select-String .\scripts\start-naver-browser.ps1 -Pattern '127\.0\.0\.1','42973','naver-chrome-profile'
```

- [x] **Step 5: GREEN 실행**

`test_runtime_config.py`와 Task 1 runtime 테스트만 실행한다.

---

### Task 3: 세 표본 CDP E2E

**파일:**

- 수정: `backend/tests/e2e/test_naver_live_scrape.py`
- 수정: `backend/tests/e2e/reference/gpt_naver_observations.json`
- 수정: `docs/testing/naver-live-e2e.md`
- 수정: `docs/setup/local-setup.md`
- 수정: `README.md`
- 생성: `.superpowers/sdd/task-external-chrome-cdp-report.md`

**인터페이스:**

```text
RUN_LIVE_NAVER_E2E=1
NAVER_E2E_CDP_URL=http://127.0.0.1:42973
```

- [x] **Step 1: E2E runtime RED 작성**

표본 E2E collector가 `Settings(crawler_browser_mode="external_chrome", crawler_cdp_url=...)`를 사용하도록 고정한다.

- [x] **Step 2: 집중 단위 GREEN**

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests/unit/test_browser_runtime.py tests/unit/test_crawl_scope.py tests/unit/test_live_dom.py tests/unit/test_navigation_policy.py tests/unit/test_humanized_delay.py tests/unit/test_runtime_config.py -q
```

- [x] **Step 3: GPT 브라우저 기준 재수집**

세 case에서 매매·전세·월세 대표 article을 같은 UI 순서로 다시 열고 기준 JSON을 갱신한다. 모든 상태 변경 전 1~3초 지연을 둔다.

- [x] **Step 4: 세 표본 live E2E 실행**

```powershell
Set-Location backend
$env:RUN_LIVE_NAVER_E2E = "1"
$env:NAVER_E2E_CDP_URL = "http://127.0.0.1:42973"
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -m live_naver -vv -s
```

세 case 모두 비교 함수에 도달해야 한다. 실제 diff가 있으면 같은 TC의 parser/selector만 최소 수정한다.

- [x] **Step 5: 문서와 보고서 갱신**

한국어를 먼저 작성하고, 네 가지 실행 방식의 실험 결과, 외부 Chrome 시작 방법, 로컬 실행 순서, 단위 결과, 세 표본 실제 결과를 기록한다.

---

# Naver External Chrome CDP Collector Implementation Plan

## English Summary

Task 1 extracts browser ownership into an async runtime and makes the production collector attach to an externally launched Chrome default context. Task 2 adds loopback-only configuration and local PowerShell lifecycle management for a dedicated Chrome profile. Task 3 refreshes the GPT-browser oracle and runs the three approved sampled comparisons through the external Chrome session.

The implementation preserves the existing serial in-page UI workflow and explicitly excludes user profile access, stealth patches, fingerprint changes, CAPTCHA solving, proxy rotation, full E2E, Docker validation, frontend builds, and unrelated tests.
