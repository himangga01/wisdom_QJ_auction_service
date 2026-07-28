# 네이버 전용 외부 Chrome CDP 수집기 설계

## 한국어

### 목표

Playwright가 직접 실행한 자동화 브라우저 대신, 일반 Google Chrome을 별도 전용 프로필로 먼저 실행하고 생산 수집기가 Chrome DevTools Protocol(CDP)로 연결만 하도록 변경한다. 기존 네이버 목록 UI 클릭·Npay 우선·상세 슬라이드 파싱 로직은 유지한다.

### 확인된 원인과 실험 결과

2026-07-25에 같은 네이버 단지 URL로 다음 실행 방식을 비교했다.

| 실행 방식 | 결과 |
|---|---|
| Playwright bundled Chromium, headless, fresh context | 네이버 404 차단 |
| 설치 Chrome, headed, fresh context | 네이버 404 차단 |
| 설치 Chrome, headed, Playwright persistent context | 네이버 404 차단 |
| 일반 Chrome을 별도 프로세스로 실행하고 CDP 연결 | 정상 단지 화면 |

외부 Chrome CDP 방식으로 승인된 세 case를 연속 방문한 결과는 모두 `fin.land.naver.com`에 머물렀고, 단지명이 표시됐으며, 단지 링크가 5~7개 발견됐고 HTTP 403/429는 없었다.

따라서 문제는 파서나 상세 클릭이 아니라 Playwright가 브라우저를 직접 시작하는 실행 경계에 있다. `headless=False`나 `launch_persistent_context()`만으로는 해결되지 않았다.

### 채택 구조

```text
start-local.ps1
  └─ 일반 Google Chrome 실행
       ├─ localhost CDP 42973
       └─ backend/data/naver-chrome-profile 전용 프로필

FastAPI/로컬 작업 실행기
  └─ Playwright connect_over_cdp()
       └─ 기본 persistent context의 작업 전용 page
            └─ 기존 네이버 UI 수집기
```

Chrome 프로세스는 Playwright가 실행하지 않는다. PowerShell 실행기가 설치된 Chrome을 `--remote-debugging-address=127.0.0.1`, `--remote-debugging-port=42973`, 별도 `--user-data-dir`로 시작한다. 생산 수집기는 CDP endpoint에 연결해 기본 context 안에 작업 page 하나를 만들고, 작업이 끝나면 그 page와 CDP 연결만 닫는다. Chrome 프로세스와 프로필은 다음 배치에서 재사용한다.

### 구성요소

#### `browser_runtime.py`

브라우저 수명 주기를 수집기에서 분리한다.

```python
@asynccontextmanager
async def open_crawler_page(playwright, settings):
    ...
```

- `external_chrome`: `connect_over_cdp(settings.crawler_cdp_url)` 사용
- `playwright`: 기존 bundled Chromium 실행을 회귀 테스트용으로 유지
- CDP mode는 `browser.contexts[0]`만 사용하며 `browser.new_context()`를 만들지 않는다.
- CDP context 자체는 닫지 않는다.
- 작업 page를 닫은 후 연결된 `Browser`를 닫아 외부 Chrome과 연결만 해제한다.
- endpoint 부재, 기본 context 부재는 `BrowserUnavailableError`로 분류한다.

#### 로컬 Chrome 실행기

`scripts/start-naver-browser.ps1`은 다음을 보장한다.

- Google Chrome 설치 경로 확인
- 포트 `42973`이 이미 이 프로젝트의 Chrome이면 재사용
- 다른 프로세스가 포트를 사용하면 실패
- 전용 프로필 경로 생성
- Chrome을 일반 프로세스로 visible/headed 실행
- `/json/version` 응답으로 CDP 준비 확인
- PID 기록

`start-local.ps1`은 API보다 먼저 이 실행기를 호출한다. `status.ps1`은 Chrome agent와 CDP 상태를 표시한다. `stop-local.ps1`은 기록된 전용 Chrome만 종료하며 일반 사용자 Chrome은 건드리지 않는다.

#### 설정

```text
CRAWLER_BROWSER_MODE=external_chrome
CRAWLER_CDP_URL=http://127.0.0.1:42973
```

로컬 기본값은 `external_chrome`이다. Docker 환경은 호스트 loopback Chrome에 직접 접근할 수 없으므로 이번 변경의 실제 검증 대상은 승인된 로컬 실행이다. Docker의 브라우저 provider 확장은 별도 작업으로 둔다.

### 보안·운영 제약

- 사용자의 기본 Chrome 프로필을 읽거나 복사하지 않는다.
- `backend/data/naver-chrome-profile`만 사용하고 Git에 포함하지 않는다.
- CDP는 `127.0.0.1`에만 노출한다.
- 외부에서 전달된 CDP URL을 요청 단위로 받지 않는다.
- webdriver 제거, User-Agent 위장, fingerprint 변경, CAPTCHA 해결, proxy 회전을 추가하지 않는다.
- 네이버 작업은 기존 단일 worker와 1~3초 랜덤 지연을 유지한다.
- 내부 API 직접 호출은 추가하지 않는다.

### 테스트

1. 브라우저 runtime 단위 RED/GREEN
   - CDP mode가 `connect_over_cdp()`와 기본 context를 사용
   - 작업 page만 닫고 외부 context는 닫지 않음
   - Playwright mode의 기존 lifecycle 유지
   - CDP endpoint/context 오류를 typed error로 변환
2. 설정·PowerShell 집중 테스트
   - mode와 URL validation
   - 고유 포트·전용 프로필·loopback 인자 고정
3. GPT 브라우저 기준 재수집
4. 같은 시점 세 case 표본 E2E
   - `E2E_BLOCKED` 없이 비교 함수까지 도달
   - 매매·전세·월세 대표 매물과 필수 상세 필드 비교

### 성공 기준

- 생산 로컬 수집기는 Playwright `launch()` 대신 외부 Chrome CDP를 사용한다.
- 세 case 모두 최초 단지 화면에서 차단되지 않는다.
- 기존 동일 UI 클릭 흐름과 Npay 우선 정책을 유지한다.
- 세 표본 E2E가 GPT 브라우저 기준과 실제 필드값을 비교한다.
- 차이가 있으면 parser/selector diff로 보고하며 접근 차단을 데이터 일치로 처리하지 않는다.

### 근거

- [Playwright `connect_over_cdp`](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp)
- [Chrome 136+ remote debugging 보안 변경](https://developer.chrome.com/blog/remote-debugging-port)
- [Microsoft Playwright Chrome Extension](https://github.com/microsoft/playwright/blob/main/packages/extension/README.md)
- [Playwright MCP persistent profile과 extension mode](https://github.com/microsoft/playwright-mcp)

---

# Naver External Chrome CDP Collector Design

## English

### Goal

Stop launching the production Naver browser through Playwright. Start ordinary Google Chrome as a separate process with a dedicated profile, then attach the existing collector through CDP while retaining the current in-page UI, Npay precedence, and detail-slide parsing flow.

### Evidence

Bundled headless Chromium, headed installed Chrome with a fresh context, and headed installed Chrome with a Playwright persistent context were all redirected to Naver's 404 block page. An independently launched Chrome process with a dedicated profile and a CDP attachment reached all three approved complexes without 403/429 responses.

The selected architecture therefore treats Chrome as a local browser agent. The service attaches to its default persistent context, creates one task page, performs the existing serial UI workflow, closes only that page, and disconnects without terminating the external browser.

### Boundaries

- Use a dedicated project profile, never the user's default Chrome profile.
- Bind CDP to loopback port `42973` only.
- Keep the legacy Playwright-launch mode only for isolated regression tests.
- Do not add stealth patches, fingerprint changes, CAPTCHA solvers, rotating proxies, or direct Naver API calls.
- Validate only local execution in this task; Docker-to-host browser transport is a separate concern.

### Success

The local production collector must use CDP, all three sampled complexes must reach their normal panels without access blocking, and the refreshed GPT-browser reference must be compared field by field by the existing sampled E2E.
