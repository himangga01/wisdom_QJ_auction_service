# 3단계 상세 수정계획 — Chrome 실행환경 통일

> 작성일: 2026-07-28  
> 대상 프로젝트: `wisdom_QJ_auction_service`  
> 상태: 계획만 작성됨. 기능 코드·설정·테스트는 아직 수정하거나 실행하지 않음.

## 1. 단계 목표

로컬 실행과 Docker 실행 모두에서 서비스가 직접 Playwright Chromium을 실행하지 않고, 별도로 실행 중인 일반 Chrome에 CDP로 연결하도록 수집 실행 계약을 통일한다.

이번 단계에서 달성할 결과는 다음과 같다.

1. 로컬은 Windows Google Chrome과 전용 프로필을 사용한다.
2. Docker는 독립 Chrome 컨테이너와 전용 영속 프로필을 사용한다.
3. Backend worker는 두 환경 모두 `connect_over_cdp()`로만 Chrome에 연결한다.
4. Chrome 준비 여부를 API와 화면에서 확인할 수 있다.
5. 연결 실패와 수집 도중 연결 종료를 서로 다른 오류로 기록한다.
6. Docker의 CDP 포트는 호스트에 공개하지 않는다.
7. stealth, User-Agent 위장, fingerprint 변경, 프록시 회전, CAPTCHA 우회는 구현하지 않는다.

## 2. 완료 후 실행 구조

| 항목 | 로컬 실행 | Docker 실행 |
|---|---|---|
| Chrome 소유자 | `scripts/start-naver-browser.ps1` | Compose `chrome` 서비스 |
| CDP 주소 | `http://127.0.0.1:42973` | `http://chrome:9222` |
| Chrome 종류 | 설치된 일반 Google Chrome | 버전을 고정한 Google Chrome Stable |
| 프로필 | `backend/data/naver-chrome-profile` | `chrome_profile` named volume |
| 화면 모드 | 사용자가 볼 수 있는 headed Chrome | Xvfb 위 headed Chrome |
| Backend 연결 | Playwright CDP attach | Playwright CDP attach |
| 수집 동시성 | 1 | 1 |
| CDP 외부 공개 | loopback만 허용 | 호스트 포트 공개 금지 |

로컬 프로필과 Docker 프로필은 물리적으로 공유하지 않는다. Windows와 Linux 사이의 프로필 호환성·파일 잠금·권한 충돌을 피하기 위해서다.

두 프로필에는 다음 공통 정책을 적용한다.

- 사용자의 기본 Chrome 프로필을 읽거나 수정하지 않는다.
- 서비스 전용 프로필로만 사용한다.
- 재시작 뒤에도 유지한다.
- cookie와 세션이 들어갈 수 있는 민감 데이터로 취급한다.
- 초기화·삭제는 사용자의 별도 승인 없이는 실행하지 않는다.
- CDP WebSocket 주소, cookie, 프로필 내용은 API 응답이나 로그에 출력하지 않는다.

## 3. Docker Chrome 이미지 결정

Docker에서는 `google-chrome-stable`을 버전 고정해 설치하고 Xvfb에서 headed 모드로 실행하는 안을 기본안으로 한다. 현재 로컬의 “일반 Chrome” 계약과 가장 가깝기 때문이다.

구현 시에는 다음 조건을 지킨다.

- 비 root 전용 사용자로 Chrome을 실행한다.
- 일반적인 sandbox 구성을 유지한다.
- `--no-sandbox`, `privileged`, `cap_add: SYS_ADMIN`을 임의로 추가하지 않는다.
- sandbox 문제로 시작되지 않으면 보안을 낮춰 우회하지 않고 별도 승인 사항으로 보고한다.
- Chrome 136 이후 요구사항에 맞춰 반드시 기본 프로필이 아닌 별도 `--user-data-dir`을 사용한다.
- 이미지의 Chrome 버전과 변경 절차를 운영 문서에 기록한다.

참고 문서:

- [Playwright CDP 연결](https://playwright.dev/python/docs/api/class-browsertype)
- [Chrome remote debugging 보안 변경](https://developer.chrome.com/blog/remote-debugging-port)
- [Docker Compose 시작 순서](https://docs.docker.com/compose/how-tos/startup-order/)
- [Docker Compose 네트워크](https://docs.docker.com/compose/how-tos/networking/)

## 4. 단계별 상세 작업

### 작업 3-1. Backend 브라우저 설정 계약 통일

수정 파일:

- `backend/app/core/config.py`
- `backend/app/crawler/browser_runtime.py`
- `backend/app/crawler/errors.py`
- `backend/.env.example`

수정 내용:

1. Backend가 Playwright 소유 Chromium을 직접 `launch()`하는 분기를 제거한다.
2. 운영 수집기는 항상 외부 Chrome CDP에 연결한다.
3. 실행환경별 CDP 기본값을 다음과 같이 확정한다.

   - local: `http://127.0.0.1:42973`
   - docker: `http://chrome:9222`

4. `CRAWLER_RUNTIME=local|docker`를 실행환경 구분 값으로 사용한다.
5. `CRAWLER_BROWSER_MODE`, `CRAWLER_HEADLESS`처럼 더 이상 의미가 없는 설정은 제거한다.
6. `CRAWLER_CDP_URL`은 명시적 override로 유지하되 실행환경별 안전 규칙을 적용한다.

설정 검증 규칙:

- `http` scheme만 허용한다.
- 포트가 반드시 있어야 한다.
- local에서는 `127.0.0.1:42973`만 허용한다.
- docker에서는 `chrome:9222`만 허용한다.
- 사용자 이름·비밀번호·path·query·fragment가 포함된 URL은 거부한다.
- 설정 오류 메시지에 전체 CDP URL이나 자격정보를 출력하지 않는다.

예정 인터페이스:

```python
class BrowserUnavailableError(CrawlError):
    code = "browser_unavailable"
    run_status = "failed"


class BrowserDisconnectedError(CrawlError):
    code = "browser_disconnected"
    run_status = "failed"


async def connect_external_chrome(
    playwright,
    endpoint_url: str,
    *,
    attempts: int = 3,
    sleep=asyncio.sleep,
):
    ...
```

연결 재시도 규칙:

- 최대 3회 연결한다.
- 기술적 backoff는 0.5초, 1.0초만 사용한다.
- 이 대기시간은 사용자가 선택하는 탐색 지연 preset과 별개다.
- 각 실패에서 만들어진 연결 자원이 있으면 정리한다.
- 기본 browser context가 없으면 연결 실패로 처리한다.
- 모든 시도가 실패하면 `browser_unavailable`로 종료한다.
- 실행 중 Chrome 연결이 끊기면 `browser_disconnected`로 종료한다.
- 자동 resume, Celery 자동 retry, 자동 requeue는 하지 않는다.
- 수집 task가 만든 tab만 닫고 Chrome profile과 기본 context는 유지한다.

### 작업 3-2. Chrome readiness 확인과 API 오류 계약 추가

생성 파일:

- `backend/app/crawler/browser_readiness.py`

수정 파일:

- `backend/app/api/routes/health.py`
- `backend/app/api/routes/analyses.py`
- 예약 실행을 시작하는 기존 scheduler/worker 진입점

예정 인터페이스:

```python
BrowserStatus = Literal["ready", "unavailable"]


async def probe_browser_cdp(
    endpoint_url: str,
    *,
    timeout_seconds: float = 2.0,
) -> BrowserStatus:
    ...
```

readiness 판정:

1. CDP endpoint의 `/json/version`만 조회한다.
2. HTTP 응답 성공 여부를 확인한다.
3. `Browser` 값이 `Chrome/` 계열인지 확인한다.
4. `webSocketDebuggerUrl` 존재 여부를 확인한다.
5. 새 tab을 만들거나 네이버 페이지로 이동하지 않는다.
6. timeout 또는 잘못된 응답은 `unavailable`로 정규화한다.

`GET /api/health` 응답 확장:

```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected",
  "browser": "ready"
}
```

상태 규칙:

- Browser가 준비되지 않았으면 `status`는 `degraded`, `browser`는 `unavailable`이다.
- API 자체는 HTTP 200을 반환해 화면이 장애 안내를 표시할 수 있게 한다.
- Browser 장애만으로 API 컨테이너를 재시작하지 않는다.
- demo runtime에서는 `browser`를 `not_required`로 반환한다.

즉시 분석 `POST /api/analyses` 규칙:

- Browser ready: 기존처럼 run을 생성하고 `202`를 반환한다.
- Browser unavailable: run 생성과 queue 전송 전에 `503`을 반환한다.

```json
{
  "detail": {
    "code": "browser_unavailable",
    "message": "수집용 Chrome이 준비되지 않았습니다."
  }
}
```

예약 실행 규칙:

- Browser 장애 중에도 스케줄의 생성·수정은 허용한다.
- 예약 시각에 Browser가 계속 준비되지 않았으면 실행 이력을 `failed/browser_unavailable`로 남긴다.
- 동일 예약을 무한 재시도하지 않는다.

### 작업 3-3. Docker Chrome sidecar 구성

생성 파일:

- `docker/chrome/Dockerfile`
- `docker/chrome/entrypoint.sh`
- `docker/chrome/check-cdp.sh`

수정 파일:

- `docker-compose.production.yml`
- `backend/docker-compose.yml`
- `backend/Dockerfile`
- `backend/.env.example`

Compose 서비스 구조:

```text
default
  api, worker, scheduler, postgres, redis, migrate, frontend

crawler_control (internal)
  api, worker, chrome

browser_egress
  chrome
```

`chrome` 서비스 계약:

- `init: true`
- `restart: unless-stopped`
- `shm_size: 1gb`
- 컨테이너 내부 `9222`만 `expose`
- host `ports`에는 CDP 포트를 추가하지 않음
- `chrome_profile:/var/lib/chrome/profile` 연결
- `crawler_control`과 `browser_egress` 네트워크 연결
- Chrome은 `0.0.0.0:9222`에 bind하되 Compose 내부에서만 접근 가능하게 함
- healthcheck는 `check-cdp.sh`로 `/json/version`을 검사
- worker는 `condition: service_healthy`로 Chrome 준비 후 시작
- API는 Chrome 장애 중에도 상태 API를 제공해야 하므로 Chrome health 때문에 시작을 막지 않음

Chrome 실행 인자 허용 범위:

- 전용 `--user-data-dir`
- CDP address와 port
- first-run 안내 비활성화
- Xvfb display 지정

명시적 금지 항목:

- stealth script
- User-Agent 위장
- fingerprint 변경
- proxy rotation
- CAPTCHA 또는 로그인 우회
- `--disable-web-security`
- 호스트 CDP port publish
- `network_mode: host`

`backend/Dockerfile`에서는 Chrome sidecar 연결이 확정된 뒤 다음 항목을 제거한다.

- `PLAYWRIGHT_BROWSERS_PATH`
- `python -m playwright install --with-deps chromium`

Python `playwright` package는 CDP client 용도로 계속 유지한다.

`backend/docker-compose.yml`은 production Compose와 동일 계약으로 맞춘다. 동일 기능에 서로 다른 Docker 실행방식이 남지 않게 한다.

### 작업 3-4. 로컬·Docker 실행 스크립트 통일

수정 파일:

- `scripts/runtime-common.ps1`
- `scripts/setup-local.ps1`
- `scripts/start-local.ps1`
- `scripts/start-naver-browser.ps1`
- `scripts/start.ps1`
- `scripts/status.ps1`

로컬 동작:

1. 설치된 Google Chrome 경로를 확인한다.
2. `backend/data/naver-chrome-profile` 전용 프로필을 사용한다.
3. loopback `42973`으로 Chrome을 시작한다.
4. readiness가 확인되면 Backend를 시작한다.
5. Chrome이 이미 준비돼 있으면 중복 실행하지 않는다.
6. 사용자 기본 Chrome 프로필과 기존 Chrome 창은 종료하지 않는다.

Docker 동작:

1. Compose가 `chrome` 서비스를 함께 시작한다.
2. Chrome health를 확인한다.
3. worker가 Chrome ready 이후 시작된다.
4. `status.ps1 -Mode docker`에서 Chrome 서비스 health를 보여준다.
5. 스크립트는 Chrome profile volume을 자동 삭제하지 않는다.

설치 스크립트 변경:

- 로컬 환경에 Playwright Chromium을 설치하는 단계는 제거한다.
- Python Playwright library 설치는 유지한다.
- Google Chrome 미설치 시 필요한 설치 항목만 안내하고 자동 설치는 하지 않는다.

### 작업 3-5. 화면의 Browser 상태와 오류 안내

생성 파일:

- `frontend/src/api/health.ts`
- `frontend/src/utils/runErrorMessages.ts`

수정 파일:

- `frontend/src/types/api.ts`
- `frontend/src/state/AnalysisProvider.tsx`
- `frontend/src/pages/AnalysisPage.tsx`
- `frontend/src/components/analysis/UrlAnalysisPanel.tsx`
- `frontend/src/pages/SchedulePage.tsx`

화면 동작:

1. live runtime에서 분석 화면을 연 동안 `/api/health`를 5초 간격으로 확인한다.
2. `browser=unavailable`이면 분석 시작 버튼을 비활성화한다.
3. “수집용 Chrome에 연결할 수 없습니다. 실행 상태를 확인한 뒤 다시 시도해 주세요.”를 표시한다.
4. Browser가 다시 ready가 되면 버튼을 자동 활성화한다.
5. health API 자체가 실패하면 기존 Backend 연결 오류를 표시한다.
6. 분석 실행 중 Browser가 끊기면 terminal 상태를 표시하고 입력 URL과 옵션은 그대로 유지한다.
7. demo runtime에서는 Browser health polling을 하지 않는다.
8. 예약 실행 이력에도 내부 오류 code가 아닌 사용자 문구를 표시한다.

오류 문구 매핑:

| 오류 코드 | 사용자 문구 |
|---|---|
| `browser_unavailable` | 수집용 Chrome에 연결할 수 없습니다. 실행 상태를 확인한 뒤 다시 시도해 주세요. |
| `browser_disconnected` | 조사 중 Chrome 연결이 끊겼습니다. Chrome이 준비되면 분석을 다시 시작해 주세요. |
| `access_blocked` | 네이버에서 접근을 제한해 조사를 중단했습니다. |
| `login_required` | Chrome에서 로그인이 필요한 상태입니다. |
| `captcha_detected` | 추가 사용자 확인이 필요해 조사를 중단했습니다. |

Chrome 재시작, 접근 우회, CAPTCHA 자동 처리 문구는 제공하지 않는다.

### 작업 3-6. 운영·설치 문서 갱신

수정 파일:

- `README.md`
- `docs/setup/local-setup.md`
- `docs/setup/docker-setup.md`
- `docs/operations/runbook.md`
- `docs/operations/data-policy.md`
- `docs/testing/naver-live-e2e.md`

문서에 포함할 내용:

- local/Docker의 CDP endpoint와 프로필 위치
- Docker CDP 포트가 호스트에 공개되지 않는 이유
- Browser health 확인 및 정상 복구 순서
- `browser_unavailable`, `browser_disconnected` 대응법
- Chrome profile 백업·초기화 시 별도 승인 원칙
- Chrome image 버전 갱신 절차
- 금지된 stealth·fingerprint·CAPTCHA 우회 정책
- 실제 네이버 1개 아파트 점검은 별도 사용자 승인 후에만 실행한다는 규칙

## 5. 데이터베이스 변경 여부

이 단계에는 Alembic migration이 없다.

- Browser 설정은 DB 필드가 아니다.
- `crawl_runs.error_code`의 기존 문자열 컬럼에 새 안정 오류 코드를 저장할 수 있다.
- Docker `chrome_profile` named volume은 DB schema 대상이 아니다.
- 기존 run과 schedule의 backfill이 필요하지 않다.

운영 환경파일에서 제거되거나 의미가 변경되는 Browser 환경변수만 배포 변경사항에 기록한다.

## 6. 구현 순서와 의존성

```text
3-1 Backend CDP 계약
        ↓
3-2 readiness/API 계약
        ↓
3-3 Docker Chrome sidecar
        ↓
3-4 실행 스크립트
        ↓
3-5 사용자 오류 UX
        ↓
3-6 문서
```

- 3-1과 3-2가 확정되기 전에는 Compose 주소와 health 계약을 고정하지 않는다.
- 3-3의 sidecar 연결이 확인되기 전에는 Backend 이미지의 Chromium 설치 단계를 제거하지 않는다.
- 3-5는 3-2의 API 응답 형식을 그대로 사용한다.
- 1·2단계의 분석 상태 복원 계약을 유지하며 Browser 장애 시 저장된 입력값을 지우지 않는다.

## 7. 승인 후 수행할 확인 항목

아래 명령과 실제 접속은 계획에만 포함한다. 사용자의 별도 승인 전에는 실행하지 않는다.

### 확인 A. Backend 집중 확인

대상:

- 설정별 CDP URL 검증
- bounded 연결 재시도
- Browser 연결 종료 오류 분류
- health 응답
- unavailable 상태에서 run과 queue가 생성되지 않는지 확인

예정 테스트 파일:

- `backend/tests/unit/test_runtime_config.py`
- `backend/tests/unit/test_browser_runtime.py`
- `backend/tests/unit/test_browser_readiness.py`
- `backend/tests/integration/test_health.py`
- `backend/tests/integration/test_analysis_browser_readiness.py`

### 확인 B. Frontend 집중 확인

대상:

- Browser unavailable 시 버튼 비활성화
- 503 오류 문구
- disconnected terminal 문구
- health 회복 후 버튼 재활성화
- demo runtime 영향 없음

예정 테스트 파일:

- `frontend/src/tests/browserReadiness.test.tsx`
- `frontend/src/tests/interactionDelay.test.tsx`

### 확인 C. Docker 구성 확인

별도 승인 후 다음 순서로 수행한다.

1. `docker compose config` 정적 확인
2. Chrome image build
3. Chrome service 단독 시작
4. `/json/version` health 확인
5. worker network에서 `about:blank` tab 생성·종료
6. host에 `9222` 포트가 공개되지 않았는지 확인
7. Chrome 재시작 뒤 profile과 readiness 복구 확인

이 단계에서는 네이버 URL로 이동하지 않는다.

### 확인 D. 실제 네이버 1개 아파트 확인

사용자가 별도로 명시 승인한 경우에만 실행한다.

- 아파트 1곳만 사용한다.
- Chrome 1개, 수집 동시성 1을 유지한다.
- 기존 탐색 지연 preset과 fail-closed 정책을 지킨다.
- stealth, 우회, CAPTCHA 자동 처리는 하지 않는다.
- 성공을 사전에 보장하지 않고 Chrome/네이버 실제 상태를 결과에 기록한다.

## 8. 완료 기준

- local과 Docker가 모두 외부 Chrome CDP 연결 한 방식만 사용한다.
- Playwright-owned Chromium launch 경로가 운영 코드에 남지 않는다.
- local CDP는 loopback만, Docker CDP는 Compose 내부에서만 접근할 수 있다.
- Chrome profile이 runtime별로 분리되고 영속화된다.
- health API와 화면에서 Browser 준비 상태를 확인할 수 있다.
- 즉시 분석은 Browser unavailable 상태에서 run을 만들지 않는다.
- 예약 실행의 Browser 실패는 명시적인 실패 이력으로 남는다.
- 연결 불가와 실행 중 연결 종료가 서로 다른 안정 오류 코드로 저장된다.
- 서비스가 stealth·차단 우회 기능을 포함하지 않는다.
- 설치·운영 문서가 실제 실행 계약과 일치한다.

---

# AI Execution Specification (English)

## Objective

Unify local and Docker crawler runtimes around a separately owned, persistent Google Chrome instance connected through Playwright CDP. Do not launch a Playwright-managed Chromium browser in production crawler code.

## Fixed runtime contract

```text
local:
  Chrome owner: scripts/start-naver-browser.ps1
  endpoint: http://127.0.0.1:42973
  profile: backend/data/naver-chrome-profile
  display: headed

docker:
  Chrome owner: docker compose service "chrome"
  endpoint: http://chrome:9222
  profile: named volume chrome_profile
  display: headed Chrome on Xvfb
  host CDP publish: forbidden

both:
  connection: playwright.chromium.connect_over_cdp()
  crawler concurrency: 1
  browser launch from worker: forbidden
```

## Implementation tasks

### Task 3.1 — Backend runtime contract

Modify:

- `backend/app/core/config.py`
- `backend/app/crawler/browser_runtime.py`
- `backend/app/crawler/errors.py`
- `backend/.env.example`

Requirements:

- Remove the Playwright-owned browser launch branch.
- Use runtime-aware exact endpoint validation.
- Keep an explicit CDP override only within the same host/port policy.
- Add bounded 3-attempt connection logic with 0.5s and 1.0s technical backoff.
- Add stable errors `browser_unavailable` and `browser_disconnected`.
- Do not auto-resume or auto-requeue a disconnected crawl.
- Close only pages created by the crawl task.

### Task 3.2 — Browser readiness and API contract

Create:

- `backend/app/crawler/browser_readiness.py`

Modify:

- `backend/app/api/routes/health.py`
- `backend/app/api/routes/analyses.py`
- the existing scheduled-run entry point

Required response:

```json
{
  "status": "ok | degraded",
  "database": "connected | disconnected",
  "redis": "connected | disconnected | not_required",
  "browser": "ready | unavailable | not_required"
}
```

Immediate analysis must return `503` with `detail.code=browser_unavailable` before persisting a run or dispatching a job when Chrome is unavailable.

### Task 3.3 — Docker Chrome sidecar

Create:

- `docker/chrome/Dockerfile`
- `docker/chrome/entrypoint.sh`
- `docker/chrome/check-cdp.sh`

Modify:

- `docker-compose.production.yml`
- `backend/docker-compose.yml`
- `backend/Dockerfile`
- `backend/.env.example`

Requirements:

- Pin Google Chrome Stable.
- Run it as a non-root user on Xvfb.
- Expose `9222` only inside Compose.
- Persist `/var/lib/chrome/profile` in `chrome_profile`.
- Add an internal control network and a Chrome-only egress network.
- Require Chrome health before starting the worker.
- Keep API startup independent of browser health.
- Do not add stealth flags, privileged mode, host networking, or a host CDP port.

### Task 3.4 — Runtime scripts

Modify:

- `scripts/runtime-common.ps1`
- `scripts/setup-local.ps1`
- `scripts/start-local.ps1`
- `scripts/start-naver-browser.ps1`
- `scripts/start.ps1`
- `scripts/status.ps1`

Requirements:

- Retain local Chrome on loopback port `42973`.
- Remove local Playwright Chromium installation.
- Do not close a user's normal Chrome windows.
- Wait for readiness without deleting or resetting the runtime profile.
- Report Chrome health in runtime status output.

### Task 3.5 — Failure UX

Create:

- `frontend/src/api/health.ts`
- `frontend/src/utils/runErrorMessages.ts`

Modify:

- `frontend/src/types/api.ts`
- `frontend/src/state/AnalysisProvider.tsx`
- `frontend/src/pages/AnalysisPage.tsx`
- `frontend/src/components/analysis/UrlAnalysisPanel.tsx`
- `frontend/src/pages/SchedulePage.tsx`

Requirements:

- Poll health every 5 seconds only in live runtime.
- Disable analysis start while browser status is unavailable.
- Re-enable automatically when readiness recovers.
- Preserve URL and selected options after terminal failure.
- Render user-facing messages, not raw internal codes.
- Do not poll browser health in demo runtime.

### Task 3.6 — Documentation

Modify:

- `README.md`
- `docs/setup/local-setup.md`
- `docs/setup/docker-setup.md`
- `docs/operations/runbook.md`
- `docs/operations/data-policy.md`
- `docs/testing/naver-live-e2e.md`

Document the runtime contracts, profile sensitivity, recovery procedure, image upgrade procedure, and prohibited bypass behavior.

## Database impact

No Alembic migration is required.

## Approval gates

Do not run tests, builds, Docker commands, browser commands, live Naver navigation, migrations, commits, or pushes without a separate user approval.

If approved later, verification order is:

1. focused backend tests;
2. focused frontend tests;
3. Compose config validation;
4. Chrome sidecar `about:blank` smoke check;
5. explicit one-apartment Naver check only under separate live-test approval.

## Acceptance criteria

- One CDP attach architecture is used in both runtimes.
- Runtime profiles are private, persistent, and separate.
- Docker CDP is not published to the host.
- Browser health and stable failure codes are surfaced through API and UI.
- Runs are not created when immediate analysis cannot reach Chrome.
- No stealth, CAPTCHA bypass, proxy rotation, or fingerprint spoofing is implemented.
