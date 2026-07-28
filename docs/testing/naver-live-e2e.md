# 네이버 부동산 라이브 E2E 실행 가이드

## 한국어

### 목적과 대상

이 테스트는 같은 시점에 만든 GPT 기준 자료와 production collector의 네이버 부동산 수집 결과를 비교한다. 표본 대상은 reference에 등록된 다음 세 case ID로만 식별한다.

- `case-131197`
- `case-155817`
- `case-22746`

보안과 개인정보 보호를 위해 이 문서, 테스트 보고서, diff에 네이버 전체 URL을 다시 기록하지 않는다.

### 기본 정책

- 라이브 E2E는 기본적으로 비활성화되어 있다. 명시적인 환경 변수가 없으면 pytest가 건너뛴다.
- Docker는 필요하지 않다. 저장소 루트의 기존 `.venv`를 사용한다.
- production collector는 Playwright 내장 브라우저를 새로 실행하지 않고, 전용 프로필로 실행된 일반 Google Chrome의 기본 context에 CDP로 연결한다.
- 네이버 수집은 일반 외부 Chrome UI와 loopback CDP만 사용한다. Chrome이 정상 페이지 navigation으로 리소스를 로드하며, collector는 열린 페이지의 DOM만 조작한다. 네이버 API와 네이버에 대한 직접 HTTP 호출은 사용하지 않는다.
- 사용자 기본 Chrome 프로필, stealth 패치, User-Agent 위장, fingerprint 변경, proxy 회전, 네이버 데이터 API 직접 호출을 사용하지 않는다.
- 네이버의 CAPTCHA, 로그인 요구, 접근 제한 문구 또는 HTTP 403/429가 관찰되면 `E2E_BLOCKED: access_blocked`로 분류하고 즉시 중단한다.
- 접근 차단을 우회하거나 CAPTCHA·로그인을 자동으로 통과하려고 시도하지 않는다.
- 클릭, 페이지 이동, 스크롤 등 모든 브라우저 상태 변경 직전에 1~3초의 주입형 랜덤 지연을 적용한다.
- 생산 수집기는 단지 목록 페이지 한 장만 연다. `/articles/{id}`로 직접 이동하거나 별도 상세 탭을 만들지 않는다.
- `중개사 n곳에서 등록했어요`를 펼친 뒤 현재 행의 내부 버튼을 클릭한다. `Npay 부동산에서 보기`가 있으면 그 버튼만 사용하고, 없을 때만 `매물 보러가기`를 사용한다.
- 상세 데이터는 현재 페이지에 열린 `매물번호` 포함 상세 슬라이드의 HTML에서만 읽고, 처리 후 `창닫기`로 닫는다.
- production 전수 수집에는 스크롤·그룹·물건의 고정 상한이 없다. 표시 매물 건수에 미달하거나 `중개사 n곳` 지연 로딩 행을 끝까지 확보하지 못하면 `incomplete_listing_collection`으로 fail-closed 처리하고 불완전 결과를 저장하지 않는다.
- 모든 물건에서 `중개사 n곳`을 끝까지 펼치고, 물건별 상세 슬라이드를 저장한다. `BrokerArticleSnapshot.details_json`에는 중첩 `market_details`가 저장되며, 과거 스냅샷의 값은 `None`이다. React 등록 카드와 XLSX 중개사등록 7열도 물건별 상세 데이터를 반영한다.
- 표본 수집은 테스트 전용으로 거래유형당 최대 25개 그룹을 순차 확인하고, 기대 article ID를 발견하면 해당 거래유형 탐색을 즉시 멈춘다. 이 제한은 production 전수 수집에 적용하지 않는다.
- 전체 URL, 중개사 연락처, 중개사 주소·등록번호, 장문 매물 설명은 실행 기록이나 공유 결과에 남기지 않는다.

### 준비 사항

저장소 루트에 Python 의존성이 준비된 `.venv`와 설치된 Google Chrome이 있어야 한다. 별도 Docker 서비스는 실행하지 않는다. 테스트 전에 저장소 루트에서 다음 명령으로 전용 Chrome을 준비한다.

```powershell
.\scripts\start-naver-browser.ps1
.\scripts\status.ps1
```

정상 상태는 `Naver Chrome: 실행 중`과 `CDP http://127.0.0.1:42973`으로 표시된다. 별도 포트를 사용해야 하면 테스트 프로세스에 `NAVER_E2E_CDP_URL`을 지정할 수 있지만, loopback HTTP 주소만 허용한다.

GPT oracle reference는 생성 시각으로부터 30분까지만 유효하다. 30분을 넘긴 reference는 비교하지 않고 `reference_stale`로 실패하므로, 라이브 실행 직전에 최신 기준 자료인지 확인해야 한다.

### 표본 실행

저장소 루트의 PowerShell에서 다음 명령을 실행한다.

```powershell
Set-Location .\backend
$env:RUN_LIVE_NAVER_E2E = "1"
$env:NAVER_E2E_CDP_URL = "http://127.0.0.1:42973"
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -m live_naver -q
```

표본 세 case는 직렬 실행된다. 정상 응답 기준 예상 시간은 약 5~30분이다. 실제 시간은 매물·중개사 수, 브라우저 상태 변경 횟수, 네이버 응답 속도에 따라 달라진다. 접근 차단이 발생하면 더 일찍 종료될 수 있다.

### 전수 실행 — 명시적 opt-in

전수 수집은 표본 실행과 별개의 명시적 opt-in이다. `RUN_LIVE_NAVER_FULL_E2E=1`과 최신 full reference의 절대 경로인 `GPT_NAVER_FULL_REFERENCE_PATH`를 모두 제공해야 한다.

```powershell
Set-Location .\backend
$env:RUN_LIVE_NAVER_FULL_E2E = "1"
$env:GPT_NAVER_FULL_REFERENCE_PATH = "<absolute-reference-json-path>"
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -m live_naver_full -q
```

전수 실행은 단지와 매물 수에 따라 수십 분에서 수 시간이 걸릴 수 있다. 이번 2026-07-24 작업에서는 전수 E2E를 실행하지 않았다.

### 이번 실제 테스트 범위

실제 네이버 점검은 사용자가 해당 실행을 별도로 명시 승인한 경우에만 아파트 1곳으로 제한해 실행한다. 코드 구현·단위 테스트·Docker 정적 확인 승인은 라이브 점검 승인으로 간주하지 않는다. 이는 표본 E2E 또는 production 전수 수집 정책을 변경하지 않으며, production 전수 수집은 계속 별도의 명시적 opt-in이 필요하다.

### GitHub Actions 수동 실행 보호

`Live Naver E2E` workflow는 `main` ref의 수동 실행만 허용한다. 영속 self-hosted runner에서 다른 branch나 tag의 코드를 실행하지 않는다. GitHub의 `naver-live-e2e` environment에도 main branch만 배포 가능한 보호 규칙을 설정한다. workflow는 저장소 루트 `.venv`를 새로 만들고 그 interpreter만 사용하며, runner-local manifest와 reference는 checkout 바깥 경로에서 읽는다.

### 결과와 diff

비교가 수행되면 case별 diff는 다음 위치에 생성된다.

```text
temp/e2e/naver-live/<case-id>/diff.json
```

차단으로 비교 단계에 도달하지 못한 경우 새 diff가 생성되지 않을 수 있으므로, 기존 파일을 이번 실행 결과로 오인하지 않는다. diff와 실행 로그에도 전체 네이버 URL, 연락처, 장문 설명을 추가하지 않는다.

### 2026-07-25 실제 실행 결과

내장 Playwright 브라우저와 Playwright가 직접 시작한 새 Chrome은 세 case 모두 `financial.pstatic.net/404.html`로 이동했다. 반면 Windows에서 전용 프로필로 먼저 실행한 일반 Google Chrome에 `connect_over_cdp()`로 연결한 방식은 동일한 세 URL의 단지·매물 UI에 정상 접근했다. 이 차이를 근거로 로컬 production collector의 기본 실행 방식을 외부 Chrome CDP로 변경했다.

GPT Chrome에서 같은 UI 순서로 세 case의 매매·전세·월세 대표 매물 9건을 수집해 reference를 만들었다. production collector는 `중개사 n곳에서 등록했어요`를 펼치고, Npay가 있으면 내부 Npay 버튼만 선택한 뒤 같은 상세 슬라이드를 읽었다.

최종 표본 E2E 결과는 다음과 같다.

```text
case-131197  통과
case-155817  통과
case-22746   통과
3 passed in 689.36s (0:11:29)
```

비교 항목은 단지 ID·이름, 거래유형별 건수, 매물번호, 거래유형, 가격, 동·층·방향, 공급/전용면적, 중개사 등록 수, 옵션 태그, 입주 가능일, 정보 제공처, Npay 여부, 관리비, 방/욕실 수와 구조다. 실시간 등록·삭제로 분 단위 변동이 확인된 거래유형별 건수와 중개사 수에만 `±2` 허용치를 적용하고, 매물번호와 상세 필드는 정확히 일치해야 통과한다.

이번 최종 수정 범위의 집중 단위 테스트는 세 명령에서 총 10건이 통과했다. 거래유형 설명문 오인, 월세 가격 범위 `5억 7,000/120 ~ 6억/100`, 복합 관리비, 실시간 건수 허용 경계를 확인했다. 전수 E2E와 관련 없는 전체 테스트는 실행하지 않았다.

---

# Naver Land Live E2E Guide

## English

### Purpose and Cases

These tests compare a time-aligned GPT oracle reference with data collected by the production Naver Land collector. The sampled set is identified only by these reference case IDs:

- `case-131197`
- `case-155817`
- `case-22746`

For security and privacy, do not reproduce full Naver URLs in this guide, test reports, or diffs.

### Default Policy

- Live E2E is disabled by default and skipped unless its explicit environment variable is set.
- Docker is not required. Use the existing `.venv` at the repository root.
- The production collector does not launch a bundled browser. It attaches over CDP to an ordinary Google Chrome process started with the project-owned dedicated profile.
- Naver acquisition uses only ordinary external Chrome UI and loopback CDP. Chrome loads resources through normal page navigation, and the collector manipulates only the DOM of the open page; direct Naver APIs and direct HTTP calls are forbidden.
- It does not reuse the user's default Chrome profile or use stealth patches, User-Agent spoofing, fingerprint alteration, proxy rotation, or direct Naver data APIs.
- CAPTCHA, login requirements, access-restriction text, or HTTP 403/429 are classified as `E2E_BLOCKED: access_blocked` and stop the run immediately.
- Never bypass access controls, CAPTCHA, or login requirements.
- The injected random delay of 1–3 seconds runs before every browser state mutation, including navigation, clicks, and scrolling.
- Production collection uses one complex-list page only. It neither navigates directly to `/articles/{id}` nor creates a separate detail tab.
- It expands the broker group and clicks the internal action in the current row. An Npay action is exclusive when present; the ordinary internal action is used only without Npay.
- Detail data comes only from the active slide containing the article-number field, and the collector closes that slide before continuing.
- Full production collection has no fixed scroll, group, or article cap. A short displayed count or any unavailable lazy-loaded `중개사 n곳` broker rows fails closed as `incomplete_listing_collection`, with no incomplete payload persisted.
- Every broker group is expanded to completion and every article detail slide is stored. `BrokerArticleSnapshot.details_json` contains nested per-article `market_details`; legacy snapshots deserialize it as `None`. React registration cards and the seven XLSX broker-registration columns consume this per-article detail.
- Sampled collection checks at most 25 groups per trade type and stops that trade type immediately after finding an expected article ID. This boundary is test-only and never limits full production collection.
- Never retain full URLs, realtor contact details, realtor addresses or registration numbers, or long listing descriptions in execution records or shared output.

### Prerequisites

The repository-root `.venv` must already contain the Python dependencies, and Google Chrome must be installed. No Docker services are needed. Start and inspect the dedicated browser from the repository root:

```powershell
.\scripts\start-naver-browser.ps1
.\scripts\status.ps1
```

The expected status is `Naver Chrome: 실행 중` with `CDP http://127.0.0.1:42973`. `NAVER_E2E_CDP_URL` may override the test endpoint, but only an HTTP loopback base URL is accepted.

The GPT oracle reference is valid for only 30 minutes after capture. A reference older than 30 minutes fails as `reference_stale` before comparison, so confirm freshness immediately before a live run.

### Sampled Run

Run from PowerShell at the repository root:

```powershell
Set-Location .\backend
$env:RUN_LIVE_NAVER_E2E = "1"
$env:NAVER_E2E_CDP_URL = "http://127.0.0.1:42973"
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -m live_naver -q
```

The three sampled cases run serially. Under normal responses, expect approximately 5–30 minutes. Actual duration varies with listing and broker counts, browser mutations, and Naver response latency. Access blocking may end the run earlier.

### Full Run — Explicit Opt-in

Full collection is a separate, explicit opt-in. Set both `RUN_LIVE_NAVER_FULL_E2E=1` and `GPT_NAVER_FULL_REFERENCE_PATH` to the absolute path of a fresh full reference.

```powershell
Set-Location .\backend
$env:RUN_LIVE_NAVER_FULL_E2E = "1"
$env:GPT_NAVER_FULL_REFERENCE_PATH = "<absolute-reference-json-path>"
..\.venv\Scripts\python -m pytest tests/e2e/test_naver_live_scrape.py -m live_naver_full -q
```

A full run can take tens of minutes to several hours depending on complex and listing volume. Full E2E was not run during the 2026-07-24 work.

### Current Live-Test Scope

Run an actual Naver check only after separate, explicit approval for that live action, and limit it to one apartment. Approval for implementation, unit tests, or static Docker checks is not live-test approval. This does not change the sampled-E2E or full-production collection policies; full collection remains a separate explicit opt-in.

### Protected GitHub Actions Dispatch

The `Live Naver E2E` workflow accepts manual dispatch only from the `main` ref. Never execute arbitrary branch or tag code on the persistent self-hosted runner. Configure the `naver-live-e2e` GitHub environment with a matching main-only deployment branch policy. The workflow creates and exclusively uses the repository-root `.venv`; runner-local manifests and references remain outside the checkout.

### Results and Diffs

When comparison runs, each case diff is written under:

```text
temp/e2e/naver-live/<case-id>/diff.json
```

A blocked run may stop before producing a new diff, so do not mistake an existing file for the current result. Do not add full Naver URLs, contact information, or long descriptions to diffs or logs.

### Observed Result on 2026-07-25

Bundled Playwright Chromium and a fresh Chrome process launched by Playwright were redirected to `financial.pstatic.net/404.html` for all three cases. An ordinary Chrome process started externally with a dedicated profile, then attached through `connect_over_cdp()`, reached the same complex and listing UI normally. Local production collection now defaults to that external-Chrome runtime.

The GPT Chrome oracle captured one sale, lease, and monthly-rent article for each case. The production collector followed the same in-page broker expansion, exclusive Npay action when available, and detail-slide workflow. The final sampled result was:

```text
case-131197  passed
case-155817  passed
case-22746   passed
3 passed in 689.36s (0:11:29)
```

Comparison covers complex identity, trade counts, article ID, trade type, price, building/floor/direction, areas, displayed broker count, option tags, move-in date, provider, Npay flag, management fee, room/bath counts, and structure. Only rapidly changing aggregate trade counts and displayed broker counts tolerate `±2`; article identity and detail fields remain exact. Ten focused unit tests also passed across the three final regression commands. Full live collection and unrelated broad suites were not run.
