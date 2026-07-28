# 2·3·4단계 우선 구현 실행계획

> 작성일: 2026-07-29  
> 기준 커밋: `917ac53`  
> 작업 브랜치: `main` (사용자 승인)  
> 상태: 구현 승인됨

## 한국어 실행계획

### 1. 목표와 범위

기존에 계획만 작성되어 있던 아래 작업을 순서대로 구현한다.

1. 2단계: 분석 실행 상태 복원과 화면 상태 정리
2. 3단계: Windows 로컬·Docker의 외부 Chrome CDP 실행 구조 통일
3. 4A: 로그인, 세션, 관리자 기능과 사용자별 데이터 격리
4. 4B: 신규·변경·삭제·복원 매물 인앱 알림
5. 4C: GPT 브라우저 기준자료 수동 반입 도구
6. 4D: 일반 CI와 수동 승인형 네이버 실환경 E2E 워크플로

기존 사용자가 보유한 `temp/` 내용은 읽거나 수정하거나 커밋하지 않는다. 실제 운영 DB 마이그레이션, 운영 배포, GitHub Environment/runner 생성, 네이버 실사이트 접속은 이번 코드 구현 범위에 포함하지 않는다.

### 2. 선결 결정

- 런타임 구분 값은 기존 `APP_RUNTIME=local|docker`를 단일 기준으로 재사용한다.
- 별도 `CRAWLER_RUNTIME` 설정은 만들지 않는다.
- 브라우저는 Backend가 직접 실행하지 않고 이미 실행 중인 Google Chrome에 CDP로 연결한다.
- 로컬 기본 CDP는 `http://127.0.0.1:42973`, Docker 내부 기본 CDP는 `http://chrome:9222`이다.
- 사용자가 명시한 주소를 위한 `CRAWLER_CDP_URL` 재정의는 허용하되, 허용된 런타임 호스트·포트 계약을 검증한다.
- 구현 중 생성하는 새 Markdown 문서는 한국어 설명을 먼저 쓰고, 뒤에 AI 실행용 영문 사양을 둔다.

### 3. 구현 파동

#### 파동 1 — 2단계 UX와 실행 복원

- 메인 URL 입력 초기값을 빈 값으로 변경한다.
- 분석 실행 상태의 단일 소유자를 `AnalysisProvider`로 통합한다.
- `sessionStorage`에는 버전이 붙은 `runId`만 저장한다.
- 새로고침 시 실행을 복원하고, 종료·취소·존재하지 않는 실행은 안전하게 정리한다.
- 네트워크 오류에서는 복원 키를 유지해 재시도가 가능하게 한다.
- 대기 중인 실행만 취소 가능하게 한다.
- 런타임 표시, 404 페이지, 라우트 오류 화면을 추가한다.
- Excel 다운로드 대상을 명시적으로 선택할 수 있게 한다.

#### 파동 2 — 3단계 Chrome 런타임 통일

- Playwright의 자체 Chrome 실행 분기를 제거하고 `connect_over_cdp`만 사용한다.
- `/json/version` 기반 준비 상태 확인과 제한된 재시도(0.5초, 1초)를 구현한다.
- `browser_unavailable`, `browser_disconnected` 오류 계약을 고정한다.
- 브라우저가 필요한 환경에서 준비되지 않으면 분석 실행을 만들기 전에 `503`을 반환한다.
- `/api/health`에 `ready|unavailable|not_required` 브라우저 상태와 `degraded` 서비스 상태를 제공한다.
- Docker Compose에 외부 포트를 공개하지 않는 비루트 Chrome/Xvfb sidecar와 영속 프로필 볼륨을 추가한다.
- Windows 실행·상태 스크립트가 Chrome과 Backend 준비 상태를 함께 보여주게 한다.
- Frontend는 5초 간격 상태 확인 결과에 따라 분석 버튼과 안내 문구를 제어한다.

#### 파동 3 — 4A 인증과 사용자별 데이터 격리

- Argon2id 비밀번호와 해시된 서버 세션·CSRF 토큰을 구현한다.
- 최초 관리자 bootstrap, 로그인, 로그아웃, 비밀번호 변경, 사용자 관리 API와 화면을 구현한다.
- `TrackedSource.owner_user_id`를 소유권 기준으로 추가한다.
- 동일 URL을 사용자별로 독립 등록할 수 있도록 `(owner_user_id, url_hash)` 고유 제약으로 전환한다.
- 모든 요청 경로의 source, run, snapshot, listing, schedule, export를 현재 사용자 기준으로 제한한다.
- 다른 사용자의 ID를 알고 있어도 `404`로 응답한다.
- 매물 누락·삭제 상태를 전역 매물에서 분리해 `SourceListingState`에 source별로 저장한다.
- scheduler는 요청 사용자 ID를 받지 않고 source에서 owner를 다시 조회한다.
- SQLite 로컬과 PostgreSQL Docker 모두에서 동작하는 Alembic 변경으로 작성한다.

#### 파동 4 — 4B 인앱 알림

- source별 알림 환경설정과 사용자별 알림 모델을 추가한다.
- 기존 `ChangeEvent`만 알림 생성 근거로 사용한다.
- 첫 정상 수집은 기준선으로 간주해 신규 알림을 만들지 않는다.
- 이후의 신규·변경·확정 삭제·복원만 알림으로 만든다.
- partial 실행은 삭제 알림을 만들지 않는다.
- `(user_id, change_event_id)`로 재실행 중복을 차단한다.
- 알림 목록, 읽지 않은 수, 개별/전체 읽음, source별 설정 API를 구현한다.
- Header의 알림 버튼과 별도 알림 페이지를 구현하며 대시보드에는 알림 목록을 넣지 않는다.

#### 파동 5 — 4C 기준자료 수동 반입

- GPT/OpenAI 런타임 호출 없이 로컬 JSON만 반입하는 도구를 구현한다.
- 원본, 전체 URL manifest, 현재 기준자료는 ignored `temp/e2e/reference/`에만 둔다.
- schema, timezone, 30분 freshness, 중복 ID, URL hash, 정규화, 민감정보를 검증한다.
- 정제 결과에는 전체 URL을 저장하지 않고 SHA-256만 저장한다.
- Git에 포함되는 예시는 전체 URL과 개인정보가 없는 단위 테스트 fixture로 교체한다.
- 한국어 운영 가이드 다음에 영문 AI 실행 사양을 기록한다.

#### 파동 6 — 4D CI

- 일반 CI는 Python 3.12/PostgreSQL과 Node 22를 사용해 migration, 비실환경 Backend 검사, Frontend 검사, Compose 정적 계약만 수행한다.
- 일반 CI에서는 Chrome, 네이버, GPT/OpenAI를 호출하지 않는다.
- 실환경 E2E는 `workflow_dispatch` 전용이며 승인 문구, 보호 Environment, Windows self-hosted runner, 단일 아파트 조건을 요구한다.
- URL은 workflow 입력으로 받지 않고 runner 로컬 manifest에서 case ID로 조회한다.
- artifact는 전체 URL·HTML·cookie·프로필·전화번호 없이 정제된 요약과 diff만 남긴다.

#### 파동 7 — 구현 확인

- 각 파동 직후 해당 변경에 직접 관련된 최소 단위·통합·Frontend 테스트만 실행한다.
- 전체 구현 뒤 Backend 비실환경 테스트, Frontend 테스트·빌드, PowerShell 구문, Compose config를 확인한다.
- 실제 네이버 탐색, 운영 DB 적용, Docker 서비스 기동, GitHub workflow 실행은 하지 않는다.

### 4. 구현 후 비판 검토 1회차

서로 다른 관점의 읽기 전용 에이전트 3개를 병렬로 실행한다.

1. 인증·세션·CSRF·사용자 데이터 격리·migration 보안
2. Chrome CDP·Docker·Windows 스크립트·장애 복구·운영 안전성
3. Frontend 실행 복원·API 계약·알림 UX·접근성

각 지적은 파일과 코드 위치, 재현 가능한 근거, 영향도를 요구한다. 메인 세션에서 해당 코드를 다시 확인해 타당한 지적만 반영하고 관련 최소 회귀 검사를 수행한다. 근거가 틀린 지적은 반영하지 않고 사유를 기록한다.

### 5. 구현 후 비판 검토 2회차

첫 회차와 다른 관점의 새 읽기 전용 에이전트 3개를 병렬로 실행한다.

1. 데이터 이력·source별 매물 상태·Excel·migration 정합성
2. 테스트·CI·reference 반입·로그와 artifact의 개인정보 누출 위험
3. Backend–Frontend 통합, 오류 코드, 로딩·빈 상태·복구 경로

메인 세션이 다시 모든 지적을 재검증하고 타당한 코드 수정과 관련 회귀 검사를 수행한다.

### 6. 완료 조건

- 2·3·4단계 계획의 코드·설정·문서·화면이 구현되어 있다.
- 로컬과 Docker가 동일한 외부 Chrome CDP 계약을 사용한다.
- 인증되지 않은 사용자는 운영 데이터 API에 접근할 수 없다.
- 사용자 A의 source/run/listing/export/notification이 사용자 B에게 노출되지 않는다.
- 알림은 기준선과 partial 실행에 안전하고 중복되지 않는다.
- GPT 기준자료는 수동·로컬 반입이며 런타임과 CI가 GPT/OpenAI를 호출하지 않는다.
- 일반 CI와 수동 실환경 E2E가 분리되어 있다.
- 비판 검토 2회와 메인 재검증·타당한 수정 반영이 완료되어 있다.

---

# AI Execution Specification (English)

## Objective

Implement the already approved Stage 2, Stage 3, and Stage 4 plans before conducting two rounds of parallel critical review.

## Ordered waves

1. Stage 2: single analysis state owner, versioned run-ID session recovery, runtime status, route errors, explicit Excel target.
2. Stage 3: external Chrome CDP only, runtime-aware endpoint validation using existing `APP_RUNTIME`, readiness and stable browser errors, Docker Chrome sidecar, Windows scripts, frontend health gating.
3. Stage 4A: Argon2id auth, hashed sessions and CSRF, admin bootstrap/management, source ownership, actor-scoped APIs, source-specific listing state, cross-database migrations.
4. Stage 4B: baseline/partial-safe in-app notifications derived only from `ChangeEvent`, source preferences, APIs and dedicated frontend route.
5. Stage 4C: local manual GPT-reference import with schema/freshness/hash/privacy validation; no runtime or CI GPT/OpenAI calls.
6. Stage 4D: non-live CI and a separately approved, manually dispatched, one-apartment Windows live workflow.
7. Run only checks directly required by the implemented changes; do not navigate Naver live or mutate production state.

## Review protocol

After all implementation waves:

- Round 1 runs three parallel read-only audits: security/tenancy, browser/runtime/operations, and frontend/API/UX.
- The main agent independently verifies every finding, applies only valid fixes, and runs focused regressions.
- Round 2 runs three fresh parallel read-only audits: data/migrations/export, CI/reference/privacy, and cross-stack recovery/contracts.
- The main agent again verifies every finding and applies only valid fixes.

## Non-goals

- Do not inspect, modify, stage, or commit user-owned `temp/`.
- Do not run production migrations, production deployment, Docker services, live Naver navigation, or GitHub workflows.
- Do not introduce a duplicate `CRAWLER_RUNTIME`; `APP_RUNTIME` is the runtime authority.
