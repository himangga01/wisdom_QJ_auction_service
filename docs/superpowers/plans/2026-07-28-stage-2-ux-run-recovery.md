# 2단계: UX 및 작업 상태 복원 수정계획

## 한국어 계획

### 목표

실데이터 모드인데도 데모처럼 표시되는 문구를 바로잡고, URL 조사 작업이 새로고침으로 유실되지 않게 한다. 대기 중인 작업은 화면에서 취소할 수 있게 하며, 데모 상태 이중화와 암묵적인 Excel 대상 선택을 제거한다.

### 확정 설계

- 실행 모드의 단일 진실 원천은 `AnalysisProvider.isDemo`로 통일한다.
- 실데이터 모드에는 `실데이터 · 서버 데이터 모드`, 데모 모드에는 `DEMO · 샘플 데이터 모드`를 표시한다.
- URL 입력값은 실데이터와 데모 모두 빈 문자열로 시작한다.
- 활성 분석 복원에는 `sessionStorage`를 사용한다. URL, 수집 옵션, 진행률, 오류 메시지는 저장하지 않고 `runId`만 저장한다.
- 서버의 `GET /api/analyses/{runId}` 응답을 작업 상태의 최종 진실 원천으로 사용한다.
- 취소 버튼은 서버가 취소를 허용하는 `queued` 상태에서만 표시한다. `running` 상태에는 취소 버튼을 표시하지 않는다.
- 데모 상태는 `DemoAnalysisProvider` 한 인스턴스만 소유하고 `AnalysisProvider`가 그 인스턴스를 소비한다.
- Excel 버튼은 전역 배열의 첫 항목을 암묵적으로 선택하지 않고, 상위 화면이 명시적인 export target을 전달한다.
- 실데이터 Excel 대상 선택기는 1단계의 서버 검색·페이지 API를 사용하며 전체 아파트 배열을 메모리에 적재하지 않는다.
- 잘못된 URL 경로와 예상하지 못한 라우트 렌더링 오류를 별도 화면으로 구분한다.

### 신규 파일

| 파일 | 책임 |
|---|---|
| `frontend/src/components/layout/RuntimeModeStatus.tsx` | 실데이터·데모 모드 배지와 설명 |
| `frontend/src/state/analysisRunSession.ts` | 활성 `runId`의 안전한 sessionStorage 저장·복원 |
| `frontend/src/pages/NotFoundPage.tsx` | 존재하지 않는 클라이언트 경로의 404 화면 |
| `frontend/src/pages/RouteErrorPage.tsx` | React Router 렌더링 오류 화면 |
| `frontend/src/components/export/ExcelExportTargetSelector.tsx` | 사용자가 명시적으로 Excel source를 선택하는 UI |
| `frontend/src/tests/analysisRunSession.test.ts` | 저장값 버전·손상·예외 계약 |
| `frontend/src/tests/analysisRecovery.test.tsx` | 새로고침 복원과 queued 취소 계약 |
| `frontend/src/tests/ApartmentsPage.test.tsx` | 명시적인 Excel source 선택 계약 |

### 수정 파일

| 파일 | 수정 내용 |
|---|---|
| `frontend/src/App.tsx` | 데모 provider 한 인스턴스 구조 유지 및 의존 순서 명시 |
| `frontend/src/app/router.tsx` | 재사용 가능한 route 배열, `errorElement`, catch-all 404 |
| `frontend/src/components/layout/PortalHeader.tsx` | 고정 `DEMO` 문구 제거 |
| `frontend/src/components/layout/PortalShell.tsx` | 모드별 footer 문구 |
| `frontend/src/components/analysis/UrlAnalysisPanel.tsx` | 빈 URL 초기값, 복원 중 비활성화, queued 취소 연결 |
| `frontend/src/components/analysis/CrawlProgress.tsx` | queued 전용 취소 동작 |
| `frontend/src/state/AnalysisProvider.tsx` | 단일 데모 상태, run 저장·복원·취소 |
| `frontend/src/pages/AnalysisPage.tsx` | provider 단일 분석 시작 경로와 복원 안내 |
| `frontend/src/pages/ApartmentsPage.tsx` | 명시적 Excel target 상태 |
| `frontend/src/api/apartments.ts` | 1단계 서버 검색·페이지 API 재사용 |
| `frontend/src/components/export/ExcelDownloadButton.tsx` | 전역 상태 추론 제거 |
| `frontend/src/tests/App.test.tsx` | 모드 문구, 빈 URL, 404, 단일 데모 상태 |
| `frontend/src/tests/interactionDelay.test.tsx` | 빈 입력 초기값에 맞춘 제출 준비 |

### 인터페이스 계약

```ts
export type RuntimeDataMode = 'demo' | 'server'

export interface ActiveAnalysisSessionV1 {
  version: 1
  runId: string
}

export const ACTIVE_ANALYSIS_SESSION_KEY =
  'wisdom-qj-auction.active-analysis-run.v1'

export function readActiveAnalysisSession(
  storage?: Storage,
): ActiveAnalysisSessionV1 | null

export function writeActiveAnalysisSession(
  runId: string,
  storage?: Storage,
): void

export function clearActiveAnalysisSession(
  storage?: Storage,
): void
```

`AnalysisProviderValue`에는 다음 계약을 추가한다.

```ts
interface AnalysisProviderValue {
  isRestoringRun: boolean
  isCancelling: boolean
  notice: string
  cancelQueuedAnalysis(): Promise<void>
}
```

Excel 다운로드는 다음 명시적 target만 받는다.

```ts
export type ExcelDownloadTarget =
  | { kind: 'demo'; dataset: DashboardDataset }
  | { kind: 'source'; sourceId: string; from?: string; to?: string }

interface ExcelDownloadButtonProps {
  target: ExcelDownloadTarget | null
}

interface ExcelExportTargetSelectorProps {
  value: ApartmentSummaryApi | null
  onChange(apartment: ApartmentSummaryApi): void
  disabled?: boolean
}
```

### 세부 작업 순서

#### 2-1. 런타임 모드 문구 정합성

1. `RuntimeModeStatus`를 추가한다.
2. `PortalHeader`의 고정 `DEMO`, `프런트엔드 UX 프리뷰` 문자열을 제거한다.
3. 실데이터 모드에는 서버 데이터 모드라는 사실만 표시하고 API 연결 성공을 단정하지 않는다.
4. `PortalShell` footer도 모드에 따라 다음처럼 분리한다.
   - 실데이터: `서버에 저장된 조사 데이터를 사용하는 모드입니다.`
   - 데모: `샘플 데이터로 동작하는 UX 미리보기입니다.`

#### 2-2. URL 입력 초기상태 수정

1. `UrlAnalysisPanel`의 `DEMO_URL` 상수를 삭제한다.
2. URL state를 `useState('')`로 초기화한다.
3. 빈 값에서는 분석 시작 버튼을 비활성화한다.
4. 사용자가 직접 입력한 값만 `sourceUrl`로 제출한다.

#### 2-3. 데모 상태 이중화 제거

1. `AnalysisProvider` 내부의 `useDemoDashboard()` 호출을 제거한다.
2. 이미 상위에 있는 `DemoAnalysisProvider`의 `useDemoAnalysis()`를 사용한다.
3. `AnalysisPage`는 실·데모를 직접 분기해 두 번 호출하지 않고 항상 `analysis.startAnalysis(request)`를 호출한다.
4. 데모 dataset이 필요한 페이지에서만 `useDemoAnalysis()`를 직접 사용한다.
5. 상세 수집 ON/OFF, 선택 지연 프리셋, 진행률이 같은 context 인스턴스에서 관찰되도록 한다.

#### 2-4. 활성 분석 새로고침 복원

1. `analysisRunSession.ts`에서 v1 JSON 형식과 UUID 검증을 구현한다.
2. JSON 손상, 버전 불일치, UUID 형식 오류는 저장값을 제거한 뒤 `null`을 반환한다.
3. storage 접근 예외는 앱을 중단시키지 않는다.
4. 실데이터 provider 초기화 시 저장된 run ID를 `currentRunId` 초기값으로 사용한다.
5. 복원 조회가 끝날 때까지 `isRestoringRun=true`로 두고 폼 전체를 비활성화한다.
6. `queued` 또는 `running`이면 기존 1초 폴링을 계속한다.
7. `completed` 또는 `partial`이면 기존 결과 조회와 관련 query invalidation을 실행한다.
8. terminal 상태에서는 sessionStorage를 제거하되 현재 화면의 완료·오류 결과는 유지한다.
9. 복원 대상이 404이면 저장값을 제거하고 새 분석을 허용한다.
10. 네트워크 오류이면 저장값을 지우지 않아 다음 새로고침에서 재시도할 수 있게 한다.
11. 새 분석 생성 또는 기존 활성 작업 재사용 응답을 받으면 즉시 run ID를 저장한다.

#### 2-5. queued 작업 취소

1. 기존 `cancelAnalysis(runId)` API 함수를 provider에 연결한다.
2. `status === 'queued'`인 경우에만 `대기 중인 분석 취소` 버튼을 표시한다.
3. 취소 중에는 버튼을 비활성화하고 `취소 중...`을 표시한다.
4. 성공하면 active session을 제거하고 상태를 `cancelled`로 갱신한다.
5. 취소 직전 작업이 `running`으로 바뀌어 409가 오면 상태를 다시 조회하고 서버 메시지를 표시한다.
6. 취소 성공은 오류 색상이 아닌 notice로 표시한다.

#### 2-6. 404와 route error 분리

1. route definition을 `appRoutes: RouteObject[]`로 내보낸다.
2. 루트 route에 `errorElement: <RouteErrorPage />`를 연결한다.
3. 마지막 child route에 `{ path: '*', element: <NotFoundPage /> }`를 추가한다.
4. API 조회 오류는 기존 `DatasetRequired`가 계속 처리한다.
5. 오류 화면에는 stack trace나 원본 오류 객체를 표시하지 않는다.

#### 2-7. 명시적인 Excel 대상 선택

1. `ExcelDownloadButton` 내부의 `analysis.recentApartments[0]` fallback을 제거한다.
2. 상위 화면이 `ExcelDownloadTarget`을 전달하도록 바꾼다.
3. 실데이터 모드에서는 1단계 `GET /api/apartments?query=&page=&pageSize=20`을 사용하는 검색형 선택기를 표시한다.
4. 선택기는 전체 목록이나 현재 페이지 항목을 export 후보 전체로 간주하지 않는다.
5. 사용자가 검색 결과를 고르면 전체 `ApartmentSummaryApi`를 `analysis.selectApartment()`에 전달하고 그 객체의 `sourceId`를 target으로 만든다.
6. 현재 선택 아파트가 검색 결과에서 사라져도 사용자가 직접 변경하기 전까지 선택값을 유지한다.
7. 선택값이 없으면 버튼을 비활성화하며 첫 source를 임의 선택하지 않는다.
8. 데모 모드는 현재 dataset 전체 다운로드를 유지한다.
9. 날짜 범위와 다중 source 일괄 다운로드는 이번 단계에 포함하지 않는다.

### 완료 기준

- 실데이터 배포에서 `DEMO` 또는 `실제 데이터와 연결되지 않음` 문구가 보이지 않는다.
- URL 입력은 빈 값으로 시작한다.
- 새로고침 후 queued/running 작업의 상태와 진행률이 복원된다.
- queued 작업만 취소할 수 있다.
- 데모 분석 상태가 provider 간에 갈라지지 않는다.
- 잘못된 경로와 API 오류가 서로 다른 화면으로 처리된다.
- Excel 다운로드 대상 source가 화면에 명시되며 첫 100개 배열에 의존하지 않는다.

### 실행 시 제한

- 이 문서는 수정계획만 정의한다.
- 기능 코드, 테스트, 빌드, 브라우저 검증은 별도 승인 전에는 실행하지 않는다.
- 테스트 승인을 받더라도 아래 집중 테스트만 먼저 실행하고 전체 suite는 다시 승인받는다.
- 라이브 네이버 수집과 Docker 실행은 이 단계의 검증 범위에 포함하지 않는다.

---

# Stage 2 UX and Active-Run Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` after explicit implementation approval. Track work with checkbox (`- [ ]`) syntax.

**Goal:** Correct runtime-mode messaging, restore active analyses after refresh, expose queued cancellation, unify demo state, and require an explicit Excel export target.

**Architecture:** `AnalysisProvider.isDemo` is the only runtime-mode authority. The browser stores only a versioned `runId` in `sessionStorage`; the backend analysis status remains authoritative. Export code receives a discriminated target instead of inferring state from an in-memory apartment array.

**Tech Stack:** React 19, TypeScript 6, React Router 7, TanStack Query 5, Tailwind CSS 4, Vitest, Testing Library.

## Global Constraints

- Do not change backend APIs in this stage.
- Never store source URLs, crawl options, progress, errors, or realtor data in browser storage.
- Show cancellation only for `queued`; the backend does not terminate `running` crawls.
- Do not run tests, builds, browser checks, or commits without separate user approval.
- Preserve demo functionality while eliminating duplicate demo state ownership.

### Task 1: Runtime mode and blank URL

**Files:**

- Create: `frontend/src/components/layout/RuntimeModeStatus.tsx`
- Modify: `frontend/src/components/layout/PortalHeader.tsx`
- Modify: `frontend/src/components/layout/PortalShell.tsx`
- Modify: `frontend/src/components/analysis/UrlAnalysisPanel.tsx`
- Test after approval: `frontend/src/tests/App.test.tsx`
- Test after approval: `frontend/src/tests/interactionDelay.test.tsx`

**Interfaces:**

- Produces: `RuntimeDataMode = 'demo' | 'server'`
- Consumes: `AnalysisProviderValue.isDemo`

- [ ] Remove static demo copy from the header and footer.
- [ ] Render mode-specific copy through `RuntimeModeStatus`.
- [ ] Delete `DEMO_URL` and initialize the input with `''`.
- [ ] Keep submission disabled until `url.trim()` is non-empty.
- [ ] If verification is approved, cover server/demo copy and blank initial input.

### Task 2: Single demo state owner

**Files:**

- Modify: `frontend/src/state/AnalysisProvider.tsx`
- Modify: `frontend/src/pages/AnalysisPage.tsx`
- Review: `frontend/src/App.tsx`

**Interfaces:**

- Consumes: `useDemoAnalysis()` from the parent `DemoAnalysisProvider`
- Removes: the private `useDemoDashboard()` instance inside `AnalysisProvider`

- [ ] Replace the private demo hook instance with the parent context.
- [ ] Route all analysis starts through `AnalysisProvider.startAnalysis`.
- [ ] Preserve direct demo dataset reads only where a page needs the dataset.
- [ ] Ensure demo mode never calls session-storage helpers.

### Task 3: Versioned active-run session

**Files:**

- Create: `frontend/src/state/analysisRunSession.ts`
- Create after approval: `frontend/src/tests/analysisRunSession.test.ts`
- Modify: `frontend/src/state/AnalysisProvider.tsx`
- Modify: `frontend/src/components/analysis/UrlAnalysisPanel.tsx`

**Interfaces:**

```ts
interface ActiveAnalysisSessionV1 {
  version: 1
  runId: string
}

readActiveAnalysisSession(storage?: Storage): ActiveAnalysisSessionV1 | null
writeActiveAnalysisSession(runId: string, storage?: Storage): void
clearActiveAnalysisSession(storage?: Storage): void
```

- [ ] Implement defensive read/write/clear helpers.
- [ ] Hydrate `currentRunId` before enabling real-mode submission.
- [ ] Persist every accepted run, including server-side deduplication reuse.
- [ ] Clear storage on terminal or stale-404 state, but retain it on network failure.
- [ ] Expose `isRestoringRun` and a non-error notice.

### Task 4: Queued cancellation

**Files:**

- Modify: `frontend/src/state/AnalysisProvider.tsx`
- Modify: `frontend/src/components/analysis/CrawlProgress.tsx`
- Modify: `frontend/src/components/analysis/UrlAnalysisPanel.tsx`
- Create after approval: `frontend/src/tests/analysisRecovery.test.tsx`

**Interfaces:**

```ts
cancelQueuedAnalysis(): Promise<void>
```

- [ ] Call the existing `POST /api/analyses/{runId}/cancel`.
- [ ] Render the action only when status is exactly `queued`.
- [ ] Clear the active-run session after successful cancellation.
- [ ] On 409, refetch status because the worker may have claimed the run.
- [ ] Do not present a destructive cancellation control for `running`.

### Task 5: Route-level failure boundaries

**Files:**

- Create: `frontend/src/pages/NotFoundPage.tsx`
- Create: `frontend/src/pages/RouteErrorPage.tsx`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**

- Produces: `appRoutes: RouteObject[]`
- Produces: catch-all route and root `errorElement`

- [ ] Extract reusable route definitions.
- [ ] Add a user-safe route error page.
- [ ] Add a catch-all 404 page.
- [ ] Keep API errors in page/query error components.

### Task 6: Explicit Excel target

**Files:**

- Create: `frontend/src/components/export/ExcelExportTargetSelector.tsx`
- Modify: `frontend/src/components/export/ExcelDownloadButton.tsx`
- Modify: `frontend/src/pages/ApartmentsPage.tsx`
- Modify: `frontend/src/api/apartments.ts`
- Create after approval: `frontend/src/tests/ApartmentsPage.test.tsx`

**Interfaces:**

```ts
type ExcelDownloadTarget =
  | { kind: 'demo'; dataset: DashboardDataset }
  | { kind: 'source'; sourceId: string; from?: string; to?: string }
```

- [ ] Remove internal access to `recentApartments` and `selectedApartmentId`.
- [ ] Require the parent page to supply an explicit target.
- [ ] Reuse the Stage 1 server-side apartment search endpoint with page size 20.
- [ ] Keep only the selected `ApartmentSummaryApi`; do not materialize all apartment pages.
- [ ] Never auto-select the first source when no target is selected.
- [ ] Disable export when no real source is selected.
- [ ] Keep demo workbook generation unchanged.

### Task 7: Approved verification gate

**Files:**

- Test: `frontend/src/tests/analysisRunSession.test.ts`
- Test: `frontend/src/tests/analysisRecovery.test.tsx`
- Test: `frontend/src/tests/App.test.tsx`
- Test: `frontend/src/tests/ApartmentsPage.test.tsx`
- Test: `frontend/src/tests/interactionDelay.test.tsx`

- [ ] Ask for test approval after implementation is complete.
- [ ] If approved, run only the named focused tests.
- [ ] Report results without starting a live browser, Docker, or the full suite.
- [ ] Commit only if the user separately requests a commit.
