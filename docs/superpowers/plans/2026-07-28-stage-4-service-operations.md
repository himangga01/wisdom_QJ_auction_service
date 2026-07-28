# 4단계 상세 수정계획 — 서비스 운영 기능

> 작성일: 2026-07-28  
> 대상 프로젝트: `wisdom_QJ_auction_service`  
> 상태: 계획만 작성됨. 기능 코드·DB migration·테스트·CI는 아직 수정하거나 실행하지 않음.

## 1. 단계 목표

데모와 단일 사용자 개발환경을 넘어 실제 여러 사용자가 안전하게 사용할 수 있는 운영 기반을 만든다.

이번 단계는 네 개의 하위 단계로 나눈다.

1. **4A — 로그인과 사용자별 데이터 격리**
2. **4B — 신규·변경·삭제 매물 인앱 알림**
3. **4C — GPT 웹탐색 기준자료의 수동 갱신·반입 절차**
4. **4D — 일반 CI와 승인형 실제 네이버 E2E 자동화**

이 단계는 1단계 데이터 정합성, 2단계 UX 상태 복원, 3단계 Chrome 실행환경 통일이 완료된 뒤 구현한다.

## 2. 현재 구조에서 먼저 해결해야 하는 문제

| 현재 문제 | 원인 | 수정 원칙 |
|---|---|---|
| 모든 사용자가 같은 조사 데이터를 보게 됨 | 사용자와 세션 모델이 없음 | 모든 사용자 요청을 인증하고 source owner를 기준으로 제한 |
| 같은 URL을 여러 사용자가 독립 조사할 수 없음 | `tracked_sources.url_hash`가 전역 unique | `(owner_user_id, url_hash)` unique로 전환 |
| 같은 단지를 조사한 사용자 사이에서 상태가 섞일 수 있음 | `ListingGroup.state`, `missing_count`가 전역 값 | source별 `SourceListingState`로 관찰 상태 분리 |
| ID를 알면 다른 사용자의 run·매물·Excel에 접근할 수 있음 | 서비스 query에 actor 조건이 없음 | 모든 query가 `actor_user_id`를 필수로 받음 |
| 스케줄 worker에는 로그인 사용자가 없음 | HTTP 사용자 문맥과 background 실행이 동일 서비스에 섞임 | worker는 source에서 owner를 다시 조회 |
| 변화가 저장돼도 사용자가 알 수 없음 | `ChangeEvent`를 소비하는 알림 모델이 없음 | 같은 transaction에서 인앱 알림 생성 |
| GPT 기준자료가 오래되거나 URL을 저장소에 남길 수 있음 | 수동 capture 반입 계약이 없음 | URL manifest와 정제 reference를 분리 |
| 일반 CI에서 실제 네이버 접속 위험 | live test 실행 경계가 workflow로 강제되지 않음 | 일반 CI는 live marker 제외, live는 수동 승인 전용 |

## 3. 전체 소유권 구조

사용자별 권한 기준은 `TrackedSource.owner_user_id` 하나로 통일한다.

```text
User
  └─ TrackedSource
       ├─ CrawlSchedule
       ├─ SourceListingState
       └─ CrawlRun
            ├─ ApartmentSnapshot
            ├─ ListingSnapshot
            ├─ BrokerArticleSnapshot
            └─ ChangeEvent
```

`Apartment`, `ListingGroup`, `BrokerArticle`은 네이버의 공개 식별자를 중복 제거하기 위한 전역 canonical entity로 유지한다. 단, 사용자 API는 이 전역 entity만으로 결과를 반환하지 않는다. 반드시 사용자가 소유한 `TrackedSource → CrawlRun → Snapshot` 경로가 확인돼야 한다.

다음 값은 전역 entity에서 사용자 응답에 직접 사용하지 않는다.

- `ListingGroup.first_seen_at`
- `ListingGroup.last_seen_at`
- `ListingGroup.state`
- `ListingGroup.missing_count`
- `BrokerArticle.first_seen_at`
- `BrokerArticle.last_seen_at`

사용자별 최초·최종 관찰과 누락·삭제 상태는 `SourceListingState`와 해당 source의 snapshot/event에서 계산한다.

## 4. 4A — 로그인과 사용자별 데이터 격리

### 작업 4A-1. 인증 모델과 보안 유틸리티 추가

생성 파일:

- `backend/app/models/user.py`
- `backend/app/models/auth_session.py`
- `backend/app/core/security.py`
- `backend/app/api/dependencies/__init__.py`
- `backend/app/api/dependencies/auth.py`
- `backend/app/schemas/auth.py`
- `backend/app/services/auth_service.py`

수정 파일:

- `backend/app/models/entities.py`
- `backend/app/models/__init__.py`
- `backend/app/core/config.py`
- `backend/pyproject.toml`
- `backend/.env.example`

`User` 모델:

```python
class User(Base):
    id: UUID
    email: str
    display_name: str
    password_hash: str | None
    role: Literal["admin", "member"]
    is_active: bool
    is_system: bool
    failed_login_count: int
    locked_until: datetime | None
    created_at: datetime
    updated_at: datetime
```

제약:

- email은 앞뒤 공백 제거 후 소문자로 정규화한다.
- `email`은 전역 unique다.
- 일반 사용자는 `password_hash`가 필수다.
- `is_system=True` 사용자는 로그인할 수 없다.
- role은 `admin`, `member`만 허용한다.
- 마지막 활성 admin은 비활성화하거나 member로 낮출 수 없다.

`AuthSession` 모델:

```python
class AuthSession(Base):
    id: UUID
    user_id: UUID
    token_hash: str
    csrf_hash: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
```

보안 계약:

- 비밀번호는 Argon2id로 해시한다.
- `backend/pyproject.toml`에 `pwdlib[argon2]>=0.3,<1`을 추가한다.
- 원본 세션 토큰과 원본 CSRF 토큰은 DB나 로그에 저장하지 않는다.
- 세션 토큰은 32-byte cryptographic random 값으로 만든다.
- DB에는 SHA-256 기반 token hash만 저장한다.
- 비밀번호 길이는 12~128자로 제한한다.
- 로그인 실패는 존재하지 않는 email과 잘못된 비밀번호에 동일한 문구를 사용한다.
- 사용자별 5회 연속 실패 시 15분 잠금한다.
- 로그인 성공 시 실패 횟수와 잠금을 초기화한다.
- 비밀번호 변경·관리자 비활성화 시 해당 사용자의 기존 session을 모두 revoke한다.

쿠키:

| 쿠키 | 설정 |
|---|---|
| `wisdom_session` | HttpOnly, SameSite=Lax, Path=/ |
| `wisdom_csrf` | JavaScript readable, SameSite=Strict, Path=/ |

- production HTTPS에서는 두 쿠키 모두 `Secure=True`다.
- local HTTP에서는 `Secure=False`를 명시적으로 사용한다.
- mutating method인 POST·PATCH·DELETE는 `X-CSRF-Token` header를 검증한다.
- CSRF cookie, header, session에 저장된 hash가 모두 일치해야 한다.
- 로그인과 최초 bootstrap은 아직 session이 없으므로 Origin 검증과 엄격한 rate limit을 적용한다.
- 운영 Frontend와 API는 same-origin reverse proxy 구성을 기본 계약으로 한다.

환경설정:

```text
AUTH_SESSION_TTL_HOURS=12
AUTH_COOKIE_SECURE=true|false
AUTH_BOOTSTRAP_TOKEN=<32-byte 이상 임의값>
AUTH_ALLOWED_ORIGINS=http://127.0.0.1:42880,...
```

- `AUTH_BOOTSTRAP_TOKEN`은 최초 관리자 생성에만 사용한다.
- 설정값을 API·로그·화면에 다시 출력하지 않는다.
- 최초 관리자 생성 후 운영자는 token을 환경설정에서 제거·회전한다.

### 작업 4A-2. 인증·관리자 API 추가

생성 파일:

- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/admin_users.py`

수정 파일:

- `backend/app/api/router.py`
- `backend/app/main.py`

공개 endpoint:

```http
GET /api/auth/bootstrap-status
POST /api/auth/bootstrap
POST /api/auth/login
GET /api/health
```

`GET /api/auth/bootstrap-status`:

```json
{
  "bootstrapRequired": true
}
```

- human admin이 한 명도 없을 때만 `true`다.
- 사용자 email이나 수는 노출하지 않는다.

`POST /api/auth/bootstrap`:

- header: `X-Bootstrap-Token`
- body:

```json
{
  "email": "admin@example.com",
  "displayName": "관리자",
  "password": "..."
}
```

규칙:

- human admin이 0명일 때 한 번만 성공한다.
- 환경변수 token과 constant-time 비교한다.
- admin 생성과 legacy source 이전을 한 transaction으로 처리한다.
- 이미 bootstrap이 완료됐으면 `409/bootstrap_completed`다.
- token이 틀리면 `404`로 응답해 bootstrap endpoint 상태를 자세히 노출하지 않는다.

로그인 응답:

```json
{
  "user": {
    "id": "uuid",
    "email": "admin@example.com",
    "displayName": "관리자",
    "role": "admin"
  },
  "expiresAt": "2026-07-28T20:00:00+09:00"
}
```

- 세션 token은 response body에 넣지 않는다.
- cookie로만 전달한다.

인증 사용자 endpoint:

```http
GET  /api/auth/me
POST /api/auth/logout
POST /api/auth/change-password
```

관리자 endpoint:

```http
GET   /api/admin/users?page=1&pageSize=20&query=
POST  /api/admin/users
PATCH /api/admin/users/{userId}
POST  /api/admin/users/{userId}/temporary-password
```

관리자 규칙:

- 공개 회원가입은 제공하지 않는다.
- admin이 member 계정을 생성한다.
- 임시 비밀번호를 API가 임의 생성해 로그에 남기지 않는다. 관리자가 요청 body로 전달한다.
- 사용자는 첫 로그인 후 자신의 비밀번호를 변경할 수 있다.
- admin도 일반 데이터 endpoint를 통해 다른 사용자의 조사 데이터에 접근할 수 없다.
- impersonation 기능은 구현하지 않는다.

인증 오류:

| 상황 | 응답 |
|---|---|
| session 없음·만료·폐기 | `401/authentication_required` |
| CSRF 불일치 | `403/csrf_invalid` |
| admin 권한 필요 | `403/admin_required` |
| 비활성 사용자 | cookie 삭제 후 `401/account_inactive` |
| 다른 사용자 데이터 ID | `404/dataset_not_found` |

### 작업 4A-3. 사용자별 source 소유권 migration

생성 파일:

- `backend/alembic/versions/0007_auth_principal_and_source_owner_expand.py`
- `backend/alembic/versions/0008_source_owner_contract_and_listing_state.py`

`0007` expand migration:

1. `users`와 `auth_sessions`를 생성한다.
2. 로그인할 수 없는 고정 legacy system user를 생성한다.
3. `tracked_sources.owner_user_id` FK를 추가한다.
4. 기존 source를 legacy system user 소유로 backfill한다.
5. 신규 code와 구 code가 유지보수 창에서 잠시 공존할 수 있도록 legacy owner server default를 둔다.
6. `(owner_user_id, url_hash)` composite unique constraint와 owner 조회 index를 추가한다.
7. 기존 global `url_hash` unique는 아직 유지한다.

최초 bootstrap transaction:

1. 첫 human admin을 생성한다.
2. legacy user의 모든 source를 첫 admin에게 이전한다.
3. legacy user는 비활성 system user로 남긴다.
4. source owner가 null 또는 system user로 남았으면 transaction을 실패시킨다.

`0008` contract migration:

1. `tracked_sources.owner_user_id`의 server default를 제거한다.
2. `owner_user_id NOT NULL`을 최종 고정한다.
3. 기존 global `url_hash` unique를 제거한다.
4. `(owner_user_id, url_hash)` unique만 유지한다.
5. `source_listing_states`를 생성한다.

```python
class SourceListingState(Base):
    id: UUID
    source_id: UUID
    listing_group_id: UUID
    visibility_state: Literal["active", "missing", "removed"]
    missing_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    removed_at: datetime | None
    updated_at: datetime
```

제약:

- unique `(source_id, listing_group_id)`
- `missing_count >= 0`
- `visibility_state`는 `active`, `missing`, `removed`만 허용
- source와 listing group을 각각 index한다.

기존 데이터 backfill:

1. `ListingSnapshot → CrawlRun.source_id`에서 distinct source/listing group 조합을 만든다.
2. 모든 run을 source별 시간순으로 재생한다.
3. snapshot이 보이면 `active`, `missing_count=0`, `removed_at=null`로 만든다.
4. partial run에서 보이지 않은 매물은 누락 횟수를 올리지 않는다.
5. completed run에서 처음 보이지 않으면 `missing`, `missing_count=1`이다.
6. 다음 completed run에서도 보이지 않으면 `removed`, `missing_count=2`, 해당 run 완료 시각을 `removed_at`으로 저장한다.
7. 이후 다시 보이면 `active`, `missing_count=0`, `removed_at=null`로 복원한다.
8. `first_seen_at`, `last_seen_at`은 해당 source의 snapshot만으로 계산한다.

기존 `ListingGroup`의 전역 상태 컬럼은 이번 단계에서 즉시 drop하지 않는다. production code의 read/write만 제거하고 migration rollback 안전성을 위해 한 release 동안 남긴다. 삭제는 별도의 사용자 승인이 필요한 후속 정리 범위다.

### 작업 4A-4. 서비스 query에 actor와 source 조건 적용

수정 파일:

- `backend/app/services/analysis_service.py`
- `backend/app/services/query_service.py`
- `backend/app/services/export_service.py`
- `backend/app/services/schedule_service.py`
- `backend/app/services/persistence_service.py`
- `backend/app/api/routes/analyses.py`
- `backend/app/api/routes/apartments.py`
- `backend/app/api/routes/dashboard.py`
- `backend/app/api/routes/listings.py`
- `backend/app/api/routes/exports.py`
- `backend/app/api/routes/schedules.py`

생성 파일:

- `backend/app/services/schedule_runner_service.py`
- `backend/app/models/source_listing_state.py`

서비스 생성자 계약:

```python
QueryService(session, actor_user_id: UUID)
ExportService(session, actor_user_id: UUID)
ScheduleService(session, actor_user_id: UUID)
```

`actor_user_id`는 사용자 요청 서비스에서 optional로 만들지 않는다.

분석 서비스 계약:

```python
async def create_for_user(
    actor_user_id: UUID,
    source_url: str,
    *,
    collect_broker_details: bool,
    interaction_delay_preset: InteractionDelayPreset,
) -> tuple[CrawlRun, bool]:
    ...

async def create_for_source(
    source_id: UUID,
    *,
    collect_broker_details: bool,
    interaction_delay_preset: InteractionDelayPreset,
) -> tuple[CrawlRun, bool]:
    ...
```

- HTTP API는 `create_for_user()`만 사용한다.
- scheduler는 `create_for_source()`만 사용한다.
- scheduler가 client-supplied user ID를 받지 않는다.
- source 조회는 `(owner_user_id, url_hash)` 조건을 사용한다.
- 활성 run unique는 사용자별 source가 분리되므로 기존 source 기준을 유지한다.

API별 ownership 조건:

| API | 필수 권한 조건 |
|---|---|
| analysis status/result/cancel | `run.source.owner_user_id == current_user.id` |
| apartments page | owner source의 result snapshot만 |
| apartment detail/history/listings | `sourceId` 필수, owner 확인 |
| dashboard | `sourceId` owner 확인 |
| listing detail | `sourceId` 필수, run도 같은 source인지 확인 |
| schedules | schedule의 source owner 확인 |
| Excel | path의 source owner 확인 |
| notifications | notification user 또는 source owner 확인 |

변경할 endpoint query:

```http
GET /api/apartments/{complexId}?sourceId={sourceId}
GET /api/apartments/{complexId}/history?sourceId={sourceId}
GET /api/apartments/{complexId}/listings?sourceId={sourceId}&runId={runId}
GET /api/listings/{listingGroupId}?sourceId={sourceId}&runId={runId}
```

- `runId`가 있으면 반드시 `run.source_id == sourceId`인지 확인한다.
- 다른 사용자의 source/run/listing은 모두 404로 정규화한다.
- window function으로 최신 아파트 snapshot을 고를 때 owner 조건을 subquery 안에 먼저 적용한다.
- snapshot rank partition은 최소 `(source_id, apartment_id)` 단위로 계산한다.
- broker registration query에는 `BrokerArticleSnapshot → CrawlRun.source_id` 조건을 반드시 포함한다.
- global BrokerArticle의 최신 snapshot을 사용자 source 조건 없이 선택하지 않는다.
- Excel의 모든 sheet query에도 같은 source 조건을 반복 적용한다.

`SourceListingState` 적용:

- persistence는 현재 run의 `source_id`로 상태 row를 조회한다.
- new/changed event는 현재 snapshot에서 만든다.
- missing/removed/restored 판정은 source별 state만 변경한다.
- partial run은 missing count를 올리지 않는다.
- API와 Excel은 global `ListingGroup.state`를 읽지 않는다.

background 분리:

- HTTP용 `ScheduleService`는 항상 actor를 요구한다.
- 신규 `ScheduleRunnerService`만 전체 due schedule을 조회할 수 있다.
- runner는 DB의 source owner를 사용해 run과 notification owner를 결정한다.
- 전체 due query는 사용자 입력을 받지 않는다.

### 작업 4A-5. Frontend 인증 흐름

생성 파일:

- `frontend/src/api/auth.ts`
- `frontend/src/state/AuthProvider.tsx`
- `frontend/src/components/auth/ProtectedRoute.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/pages/BootstrapAdminPage.tsx`
- `frontend/src/pages/AccountPage.tsx`
- `frontend/src/pages/AdminUsersPage.tsx`

수정 파일:

- `frontend/src/App.tsx`
- `frontend/src/app/router.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/components/layout/PortalHeader.tsx`
- `frontend/src/components/layout/PortalShell.tsx`
- `frontend/src/state/AnalysisProvider.tsx`
- `frontend/src/state/analysisRunSession.ts`

라우팅:

```text
/login                 공개
/bootstrap             bootstrapRequired일 때만
/                      인증 필요
/dashboard             인증 필요
/apartments            인증 필요
/apartments/...        인증 필요
/schedules             인증 필요
/notifications         인증 필요
/account               인증 필요
/admin/users           admin 필요
```

동작:

1. live runtime 시작 시 `/api/auth/me`를 한 번 조회한다.
2. session이 없으면 로그인 화면으로 이동한다.
3. 서버가 bootstrap 필요 상태면 `/bootstrap`으로 이동한다.
4. `apiRequest`와 `apiFile`은 `credentials: "same-origin"`을 사용한다.
5. POST·PATCH·DELETE에는 CSRF cookie 값을 `X-CSRF-Token`으로 전달한다.
6. `401` 수신 시 AuthProvider를 로그아웃 상태로 바꾸고 로그인 화면으로 이동한다.
7. logout 시 다음 클라이언트 상태를 모두 비운다.

   - 현재 사용자
   - 선택 아파트
   - 활성 analysis run ID
   - `sessionStorage`의 run 복원 값
   - React Query의 사용자별 server cache

8. 다른 사용자가 같은 브라우저에서 로그인해도 이전 사용자 데이터가 잠깐 표시되지 않게 한다.
9. demo runtime은 기존 샘플 UX를 유지하고 synthetic demo identity를 사용하며 Backend auth API를 호출하지 않는다.
10. Header에는 사용자명, 계정 메뉴, 로그아웃을 표시한다.

## 5. 4B — 신규·변경·삭제 매물 인앱 알림

### 작업 4B-1. 알림 모델과 migration

생성 파일:

- `backend/app/models/notification.py`
- `backend/app/models/notification_preference.py`
- `backend/alembic/versions/0009_in_app_notifications.py`
- `backend/app/schemas/notification.py`
- `backend/app/services/notification_service.py`

수정 파일:

- `backend/app/models/entities.py`
- `backend/app/models/__init__.py`
- `backend/app/services/persistence_service.py`

`SourceNotificationPreference`:

```python
class SourceNotificationPreference(Base):
    source_id: UUID
    enabled: bool
    notify_new: bool
    notify_changed: bool
    notify_removed: bool
    notify_restored: bool
    created_at: datetime
    updated_at: datetime
```

- `source_id`를 PK/FK로 사용해 source당 하나만 존재하게 한다.
- owner는 `TrackedSource.owner_user_id`에서 결정한다.
- 기본값은 `enabled=False`다.
- 사용자가 명시적으로 켠 뒤부터 알림을 만든다.

`Notification`:

```python
class Notification(Base):
    id: UUID
    user_id: UUID
    source_id: UUID
    run_id: UUID
    change_event_id: UUID
    apartment_id: UUID
    listing_group_id: UUID
    event_type: Literal["new", "changed", "removed", "restored"]
    title: str
    summary_json: dict
    read_at: datetime | None
    created_at: datetime
```

제약·index:

- unique `(user_id, change_event_id)`
- index `(user_id, read_at, created_at)`
- index `(source_id, created_at)`
- 모든 FK는 실제 event/run/source 관계와 일치해야 한다.

### 작업 4B-2. 알림 생성 규칙

알림의 변화 판단 기준은 기존 `ChangeEvent` 하나만 사용한다. 별도의 diff 알고리즘을 만들지 않는다.

규칙:

1. source의 첫 정상 수집은 기준선이므로 모든 매물을 신규 알림으로 만들지 않는다.
2. 두 번째 정상 수집부터 알림을 생성한다.
3. `new`, `changed`는 현재 run에서 실제 관찰된 매물만 대상으로 한다.
4. `removed`는 1단계 규칙에 따라 completed run 두 번 연속 미관찰로 확정된 event만 대상으로 한다.
5. partial run의 미관찰 매물은 removed 알림을 만들지 않는다.
6. `missing`은 임시 상태이므로 알림 유형에 포함하지 않는다.
7. 다시 등장한 매물은 preference가 켜져 있으면 `restored` 알림을 만든다.
8. ChangeEvent와 Notification을 같은 DB transaction에서 저장한다.
9. worker 재시도에도 unique constraint로 중복 알림을 막는다.
10. 알림 대상 user는 요청을 시작한 세션이 아니라 source owner다.
11. 알림 `summary_json`에는 정규화된 변경 필드와 before/after 요약만 저장한다.
12. 전화번호, 원본 HTML, cookie, 긴 자유서술 원문은 복사하지 않는다.

알림 링크에 저장할 화면 문맥:

```json
{
  "sourceId": "uuid",
  "complexId": "naver-complex-id",
  "runId": "uuid",
  "compareRunId": "uuid-or-null",
  "focusListingId": "uuid"
}
```

사용자가 알림을 누르면 해당 조사일 비교 화면으로 이동하고 대상 매물 카드를 강조한다.

### 작업 4B-3. 알림 API

생성 파일:

- `backend/app/api/routes/notifications.py`
- `backend/app/api/routes/notification_preferences.py`

수정 파일:

- `backend/app/api/router.py`

endpoint:

```http
GET   /api/notifications?cursor=&limit=20&unreadOnly=false
GET   /api/notifications/unread-count
PATCH /api/notifications/{notificationId}
POST  /api/notifications/read-all

GET   /api/sources/{sourceId}/notification-preference
PATCH /api/sources/{sourceId}/notification-preference
```

응답 계약:

```typescript
interface NotificationPage {
  items: NotificationItem[]
  nextCursor: string | null
}

interface NotificationItem {
  id: string
  eventType: 'new' | 'changed' | 'removed' | 'restored'
  title: string
  summary: Record<string, unknown>
  readAt: string | null
  createdAt: string
  link: {
    sourceId: string
    complexId: string
    runId: string
    compareRunId: string | null
    focusListingId: string
  }
}
```

- cursor는 `(created_at, id)`를 opaque 문자열로 encode한다.
- `limit`은 1~100, 기본 20이다.
- 알림과 preference 모두 current user 소유인지 확인한다.
- 다른 사용자의 ID는 404다.

### 작업 4B-4. 알림 UX

생성 파일:

- `frontend/src/api/notifications.ts`
- `frontend/src/components/notifications/NotificationBell.tsx`
- `frontend/src/components/notifications/NotificationList.tsx`
- `frontend/src/pages/NotificationsPage.tsx`

수정 파일:

- `frontend/src/app/router.tsx`
- `frontend/src/components/layout/PortalHeader.tsx`
- `frontend/src/pages/SchedulePage.tsx`
- `frontend/src/pages/ApartmentDetailPage.tsx`
- `frontend/src/components/research/ListingComparisonBoard.tsx`
- `frontend/src/types/api.ts`

UX:

- Header에는 unread count가 있는 종 모양 버튼만 추가한다.
- 대시보드에 알림 목록을 추가하지 않아 정보 밀도를 높이지 않는다.
- count는 live runtime에서 30초 간격으로 조회하고 숨겨진 tab에서는 polling을 멈춘다.
- 종 버튼을 누르면 `/notifications` 새 페이지로 이동한다.
- 알림 페이지는 읽지 않음 필터와 cursor 기반 `더 보기`를 제공한다.
- 알림 클릭 시 먼저 읽음 처리하고 날짜 비교 화면으로 이동한다.
- `focusListingId` 매물 카드는 색상과 outline으로 강조한다.
- SchedulePage의 기존 비활성 `notifyOnChange` UI를 실제 source preference와 연결한다.
- 알림 ON/OFF와 유형별 new/changed/removed/restored 선택을 제공한다.
- demo runtime에서는 정적 알림 예시만 제공하거나 알림 메뉴를 숨긴다. Backend에는 쓰지 않는다.

## 6. 4C — GPT 웹탐색 기준자료 수동 갱신·반입

서비스 런타임이나 CI가 GPT 브라우저 또는 OpenAI API를 직접 호출하지 않도록 명확히 분리한다.

### 작업 4C-1. reference와 실제 URL manifest 분리

생성 파일:

- `backend/tests/e2e/reference_loader.py`
- `backend/tests/e2e/reference.schema.json`
- `backend/tools/import_gpt_reference.py`
- `scripts/import-gpt-reference.ps1`
- `backend/tests/e2e/reference/README.md`
- `docs/testing/gpt-reference-refresh.md`

수정 파일:

- `backend/tests/e2e/reference_schema.py`
- `backend/tests/e2e/comparison.py`
- `backend/tests/e2e/test_naver_live_scrape.py`
- `backend/tests/unit/test_e2e_reference.py`
- `backend/tests/e2e/reference/gpt_naver_observations.json`
- `.gitignore`

파일 분리:

```text
temp/e2e/reference/inbox/*.json
  GPT 웹탐색 결과 원본
  Git 제외

temp/e2e/reference/case-manifest.local.json
  caseId → 전체 네이버 URL
  Git 제외

temp/e2e/reference/current/*.json
  검증·정제된 최신 reference
  Git 제외

backend/tests/e2e/reference/example.json
  URL·개인정보를 제거한 schema/unit fixture
  Git 포함
```

기존 stale bundled live reference는 역사적 live 입력으로 더 이상 사용하지 않는다. URL을 제거한 `example.json`으로 전환해 schema와 comparator 단위 fixture 용도로만 사용한다.

정제 reference 계약:

```json
{
  "schemaVersion": "2",
  "captureTool": "gpt_browser_manual",
  "mode": "sample",
  "capturedAt": "2026-07-28T10:00:00+09:00",
  "normalizationVersion": "2",
  "cases": [
    {
      "caseId": "case-...",
      "sourceUrlSha256": "...",
      "complexId": "...",
      "complexName": "...",
      "tradeCounts": {},
      "articles": []
    }
  ],
  "payloadSha256": "..."
}
```

Git 저장 금지:

- 전체 네이버 URL
- 중개사 전화번호·주소·등록번호
- cookie와 session
- 원본 HTML
- screenshot
- Chrome profile 경로와 내용
- 개인정보가 포함될 수 있는 긴 자유서술 원문

### 작업 4C-2. 수동 import 도구

실행 계약:

```powershell
.\scripts\import-gpt-reference.ps1 `
  -InputPath <원본-json> `
  -ManifestPath <case-manifest.local.json>
```

도구 처리 순서:

1. Pydantic schema를 검증한다.
2. `capturedAt`에 timezone이 있는지 확인한다.
3. 실행 시작 기준 30분보다 오래된 reference를 거부한다.
4. 중복 case ID와 case 내부 중복 article ID를 거부한다.
5. manifest URL이 `https://fin.land.naver.com/map` 형식인지 확인한다.
6. URL hash와 `sourceUrlSha256`이 일치하는지 확인한다.
7. 가격·면적·날짜·공백·option tag를 canonical 형식으로 정규화한다.
8. 중복 상세 key/value를 제거한다.
9. 전화번호·원본 HTML·cookie 형태 값을 거부한다.
10. key 정렬 canonical JSON으로 `payloadSha256`을 계산한다.
11. 정제 결과를 `temp/e2e/reference/current/`에 저장한다.
12. 원본·manifest·전체 URL을 stdout과 log에 출력하지 않는다.

서비스 경계:

- production API에는 reference upload endpoint를 만들지 않는다.
- production DB에는 GPT 기준자료를 저장하지 않는다.
- OpenAI API key나 GPT 호출 코드를 Backend에 추가하지 않는다.
- import는 개발·검증 도구이고 실제 조사 데이터 수집 기능과 분리한다.

비교 규칙:

- complex ID, complex name, article ID, 거래유형, 가격, 면적, 층, 방향, 정규화 상세필드는 exact 비교한다.
- 빠르게 변할 수 있는 거래유형별 총 건수와 화면의 중개사 수만 기존 허용오차 규칙을 유지한다.
- timestamp, JSON key 순서, 공백 차이는 비교 전에 정규화한다.
- diff에는 case ID와 정제 필드만 기록하고 전체 URL을 기록하지 않는다.

### 작업 4C-3. 한국어 운영 가이드

`docs/testing/gpt-reference-refresh.md`에 한국어를 먼저 작성하고 뒤에 AI 실행 규격을 둔다.

가이드 순서:

1. 사용자가 GPT 웹탐색으로 지정 아파트 1곳을 조사한다.
2. 제공된 JSON template으로 결과를 저장한다.
3. 전체 URL은 ignored local manifest에만 넣는다.
4. import script로 schema·freshness·hash·민감정보를 검증한다.
5. 결과 요약을 사용자가 확인한다.
6. 별도 승인 후에만 같은 case로 Chrome live E2E를 실행한다.

## 7. 4D — CI 자동화

### 작업 4D-1. 일반 CI

생성 파일:

- `.github/workflows/ci.yml`

trigger:

```text
pull_request
push: main
```

공통 정책:

- workflow permission은 `contents: read`만 사용한다.
- 같은 branch의 이전 실행은 취소한다.
- Python 3.12, Node 22를 사용한다.
- 일반 CI에서는 Chrome을 시작하지 않는다.
- 일반 CI에서는 네이버 URL에 접속하지 않는다.
- GPT 또는 OpenAI API를 호출하지 않는다.
- live marker를 명시적으로 제외한다.
- 전체 URL과 자격정보를 artifact에 넣지 않는다.

Backend job:

1. source checkout
2. Python 3.12 setup
3. `pip install -e ".[test]"`
4. PostgreSQL 16 service 준비
5. ephemeral CI 설정으로 `alembic upgrade head`
6. `pytest -m "not live_naver and not live_naver_full"`

Frontend job:

1. source checkout
2. Node 22 setup
3. lockfile 기반 `npm ci`
4. `npm run lint`
5. `npm run test`
6. `npm run build`

Compose contract job:

1. `backend/.env.example`에서 runner 전용 임시 `backend/.env` 생성
2. production secret 대신 CI 전용 비밀이 아닌 dummy 값을 사용
3. `docker compose -f docker-compose.production.yml config -q`
4. 실제 image build와 service start는 일반 CI 기본 범위에 넣지 않는다.

`backend/.env` 임시 파일은 workflow 종료 시 runner와 함께 폐기하며 Git에 추가하지 않는다.

### 작업 4D-2. 승인형 실제 네이버 E2E workflow

생성 파일:

- `.github/workflows/live-naver-e2e.yml`

trigger:

- `workflow_dispatch`만 사용한다.
- push, pull request, schedule trigger를 추가하지 않는다.

필수 GitHub 외부 설정:

- GitHub Environment: `naver-live-e2e`
- required reviewer 승인
- self-hosted Windows runner label: `self-hosted`, `windows`, `naver-e2e`
- runner에 일반 Google Chrome 설치
- runner Git 외부에 최신 local case manifest와 정제 reference 준비

workflow 입력:

```text
caseId
includeDetails       기본 true
delayProfile         기본 normal
approvalPhrase       RUN_ONE_APARTMENT
```

제약:

- URL 자체는 workflow input으로 받지 않는다.
- `caseId`로 runner local manifest를 조회한다.
- `approvalPhrase`가 정확히 일치하지 않으면 실행하지 않는다.
- concurrency group을 1로 고정한다.
- timeout은 180분으로 제한한다.
- 한 실행에서 아파트 1곳만 허용한다.
- Stage 3 전용 Chrome CDP readiness 확인 후 시작한다.
- reference가 30분 freshness를 넘거나 URL hash가 다르면 시작하지 않는다.
- 실제 수집에는 선택한 delay preset과 상세수집 옵션을 그대로 전달한다.
- 접근 차단·CAPTCHA·로그인 요구가 나오면 fail-closed한다.
- stealth, proxy, fingerprint 변경, 우회를 실행하지 않는다.

artifact:

- 정제된 comparison summary와 URL이 제거된 diff만 저장한다.
- 보존기간은 3일로 제한한다.
- raw HTML, screenshot, cookie, Chrome profile, 전화번호, 전체 URL은 업로드하지 않는다.
- blocked 상태는 실패 원인 code만 기록한다.

workflow는 GPT reference를 만들거나 수정하지 않는다. 사용자가 별도로 GPT 웹탐색을 수행하고 import한 최신 reference가 준비돼 있어야 한다.

## 8. 배포 순서

### 8.1 선행 단계

```text
1단계 데이터 조회·비교 정합성
    ↓
2단계 UX 및 작업 상태 복원
    ↓
3단계 Chrome 실행환경 통일
    ↓
4단계 서비스 운영 기능
```

### 8.2 4단계 내부 배포

1. 별도 승인 후 DB backup을 만든다.
2. write를 막는 유지보수 모드로 전환한다.
3. `0007_auth_principal_and_source_owner_expand`까지만 적용한다.
4. 새 인증 Backend와 bootstrap 화면을 배포한다.
5. 신뢰된 local 접근에서 최초 admin을 생성한다.
6. 같은 transaction에서 legacy source를 최초 admin에게 이전한다.
7. 별도 승인된 ownership 확인 뒤 `0008_source_owner_contract_and_listing_state`를 적용한다.
8. 인증 필수 Frontend·Backend를 재시작하고 유지보수 모드를 해제한다.
9. 안정화 후 `0009_in_app_notifications`와 알림 UX를 배포한다.
10. GPT reference import 도구와 한국어 문서를 배포한다.
11. 일반 CI를 활성화한다.
12. self-hosted runner와 required reviewer가 준비된 후에만 live workflow를 활성화한다.

fresh installation은 `alembic upgrade head` 후 bootstrap 절차를 수행한다.

rollback 원칙:

- production 사용자·알림 데이터가 생긴 뒤 자동 downgrade로 테이블을 삭제하지 않는다.
- app rollback은 migration 호환 범위를 확인하고 수행한다.
- ownership migration 자체를 되돌려야 하면 별도 승인 후 DB backup 복원 방식으로 처리한다.

## 9. 승인 후 수행할 확인 항목

아래 항목은 계획에만 포함한다. 현재는 실행하지 않는다.

### 인증 집중 확인

예정 파일:

- `backend/tests/unit/test_security.py`
- `backend/tests/unit/test_auth_service.py`
- `backend/tests/integration/test_auth_api.py`
- `frontend/src/tests/auth.test.tsx`

확인 대상:

- 비밀번호 hash/verify
- raw session token 미저장
- cookie 속성
- CSRF 거부
- session 만료·logout·비밀번호 변경 revoke
- 로그인 잠금
- bootstrap 단 한 번
- 마지막 admin 보호

### 사용자 데이터 격리 확인

예정 파일:

- `backend/tests/integration/test_tenant_isolation.py`
- `backend/tests/integration/test_source_listing_state.py`

사용자 A와 B가 같은 URL을 등록한 상황에서 확인:

- 서로 다른 source 생성
- A가 B의 source, run, dashboard, history, listing, broker detail, schedule, export에 접근 불가
- ID를 알고 요청해도 404
- A의 수집이 B의 missing/removed 상태를 변경하지 않음
- broker registration snapshot이 다른 source에서 섞이지 않음
- scheduler가 source owner로 정확한 run을 생성

### 알림 집중 확인

예정 파일:

- `backend/tests/integration/test_notifications.py`
- `frontend/src/tests/notifications.test.tsx`

확인 대상:

- 첫 정상 수집에는 알림 없음
- 이후 new/changed/removed/restored 알림
- partial run 미관찰은 removed 알림 없음
- worker 재시도에도 중복 없음
- 다른 사용자 알림 접근 불가
- unread count, 읽음, 모두 읽음
- 알림 링크에서 정확한 날짜·매물 강조

### reference import 확인

예정 파일:

- `backend/tests/unit/test_gpt_reference_import.py`
- `backend/tests/unit/test_e2e_reference.py`

확인 대상:

- stale, 중복 ID, 잘못된 URL hash 거부
- 전화번호·HTML·cookie 형태 입력 거부
- canonical hash 재현성
- 전체 URL 없는 정제 output과 diff

### CI 설정 확인

별도 승인 후 확인:

- 일반 CI가 live marker를 제외함
- 일반 CI가 Chrome과 네이버를 호출하지 않음
- migration, Backend, Frontend, Compose config job 분리
- live workflow가 manual trigger 이외에는 시작되지 않음
- required reviewer와 self-hosted label 없이는 실행되지 않음
- 한 workflow에 아파트 1곳만 들어감

실제 네이버 접속은 이 확인들과 별도로 다시 명시 승인을 받아야 한다.

## 10. 완료 기준

- 사용자 session 없이 운영 데이터 API에 접근할 수 없다.
- 최초 관리자 생성은 일회성 token으로만 가능하다.
- 모든 source가 human owner를 가지며 같은 URL을 사용자별로 독립 등록할 수 있다.
- 사용자 A의 조사·스케줄·Excel·매물 상세가 사용자 B에게 노출되지 않는다.
- 매물의 missing/removed 상태가 source별로 독립적이다.
- 알림은 `ChangeEvent`와 같은 transaction에서 중복 없이 생성된다.
- 첫 기준 수집과 partial 미관찰이 잘못된 신규·삭제 알림을 만들지 않는다.
- 알림 화면이 별도 페이지로 제공되고 해당 날짜 비교 매물로 이동한다.
- GPT 기준자료는 수동 import하며 서비스·CI가 GPT를 자동 호출하지 않는다.
- 전체 URL과 민감정보가 reference fixture, log, diff, artifact에 남지 않는다.
- 일반 CI는 live test를 실행하지 않는다.
- 실제 네이버 workflow는 수동 승인·self-hosted Windows·아파트 1곳 조건을 모두 요구한다.

---

# AI Execution Specification (English)

## Objective

Add production operations in four ordered increments:

1. authentication and strict tenant isolation;
2. in-app change notifications;
3. manual GPT-browser reference import;
4. non-live CI plus an explicitly approved one-apartment live workflow.

Do not implement this stage before Stages 1–3 have established exact-run data semantics, UX recovery, and the external-Chrome runtime.

## 4A — Authentication and tenant isolation

### Create

- `backend/app/models/user.py`
- `backend/app/models/auth_session.py`
- `backend/app/models/source_listing_state.py`
- `backend/app/core/security.py`
- `backend/app/api/dependencies/auth.py`
- `backend/app/schemas/auth.py`
- `backend/app/services/auth_service.py`
- `backend/app/services/schedule_runner_service.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/admin_users.py`
- `backend/alembic/versions/0007_auth_principal_and_source_owner_expand.py`
- `backend/alembic/versions/0008_source_owner_contract_and_listing_state.py`
- `frontend/src/api/auth.ts`
- `frontend/src/state/AuthProvider.tsx`
- `frontend/src/components/auth/ProtectedRoute.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/pages/BootstrapAdminPage.tsx`
- `frontend/src/pages/AccountPage.tsx`
- `frontend/src/pages/AdminUsersPage.tsx`

### Modify

- auth/model/router/config/package files listed in the Korean section;
- every analysis, query, schedule, persistence, export, and frontend API consumer listed above.

### Fixed security contract

- Argon2id passwords via `pwdlib[argon2]>=0.3,<1`.
- Server-side sessions with hashed session and CSRF tokens.
- `wisdom_session`: HttpOnly, SameSite=Lax.
- `wisdom_csrf`: readable cookie submitted as `X-CSRF-Token`.
- Secure cookies in production HTTPS.
- 12-hour session TTL.
- 5 failed logins lock the account for 15 minutes.
- No public sign-up.
- One-time bootstrap requires `X-Bootstrap-Token`.
- Session tokens never appear in JSON or logs.
- Admins do not implicitly gain access to other users' datasets.

### Ownership contract

```text
current user
  -> owned tracked source
  -> crawl run
  -> snapshots and change events
```

- Replace global source URL uniqueness with `(owner_user_id, url_hash)`.
- Require `actor_user_id` in all request-facing services.
- Return 404 for another tenant's object.
- Require `sourceId` on apartment and listing detail/history routes.
- Filter broker snapshots through both run and source.
- Rank latest apartment snapshots per `(source_id, apartment_id)` after owner filtering.
- Store missing/removal state in `SourceListingState`, never in the global listing entity.
- Background scheduling uses a separate service that derives owner from source.

### Migration order

`0007`:

- create users/sessions;
- create the non-login legacy system user;
- add and backfill source owner;
- add composite unique while retaining global URL unique.

Bootstrap:

- create first human admin;
- atomically transfer all legacy sources.

`0008`:

- remove owner server default;
- enforce owner NOT NULL;
- remove global URL unique;
- create/backfill source-specific listing state.

## 4B — In-app notifications

### Create

- `backend/app/models/notification.py`
- `backend/app/models/notification_preference.py`
- `backend/app/schemas/notification.py`
- `backend/app/services/notification_service.py`
- `backend/app/api/routes/notifications.py`
- `backend/app/api/routes/notification_preferences.py`
- `backend/alembic/versions/0009_in_app_notifications.py`
- `frontend/src/api/notifications.ts`
- `frontend/src/components/notifications/NotificationBell.tsx`
- `frontend/src/components/notifications/NotificationList.tsx`
- `frontend/src/pages/NotificationsPage.tsx`

### Rules

- `ChangeEvent` is the sole diff source.
- Do not notify every listing in the first baseline run.
- Notify observed new/changed items from later runs.
- Notify removed only after the Stage 1 confirmed-removal rule.
- Never infer removal from a partial run.
- Do not notify provisional missing.
- Store ChangeEvent and Notification in one transaction.
- Deduplicate by `(user_id, change_event_id)`.
- Derive recipient from source owner.
- Poll unread count every 30 seconds only in visible live tabs.
- Keep notifications off the dashboard and provide a dedicated route.

## 4C — Manual GPT reference import

### Create

- `backend/tests/e2e/reference_loader.py`
- `backend/tests/e2e/reference.schema.json`
- `backend/tools/import_gpt_reference.py`
- `scripts/import-gpt-reference.ps1`
- `backend/tests/e2e/reference/README.md`
- `docs/testing/gpt-reference-refresh.md`

### Contract

- Runtime and CI must not call GPT, OpenAI APIs, or an upload endpoint.
- Raw capture, full URL manifest, and current reference remain under ignored `temp/`.
- A committed example fixture contains no full URL or personal data.
- Import validates schema, timezone, 30-minute freshness, unique IDs, URL hash, canonical formatting, and sensitive-data rejection.
- Output contains `sourceUrlSha256` and `payloadSha256`, never a full URL.
- Stable identity/detail fields compare exactly; only existing rapidly changing count tolerances remain.

## 4D — CI

### General CI

Create `.github/workflows/ci.yml`:

- `pull_request` and push to `main`;
- `contents: read`;
- Python 3.12 backend with PostgreSQL migration and non-live pytest;
- Node 22 frontend lint/test/build;
- Compose config validation only;
- no Chrome, Naver, GPT, or OpenAI calls.

### Live workflow

Create `.github/workflows/live-naver-e2e.yml`:

- `workflow_dispatch` only;
- required-reviewer environment `naver-live-e2e`;
- self-hosted Windows runner with label `naver-e2e`;
- one concurrent run and one apartment per dispatch;
- local case manifest and reference, no URL workflow input;
- exact approval phrase;
- 180-minute timeout;
- Stage 3 Chrome readiness;
- fail closed on blocking/CAPTCHA/login;
- sanitized summary/diff artifacts only, retained for 3 days.

## Approval gates

Do not run tests, builds, migrations, database backups, Docker, browsers, live navigation, workflows, commits, or pushes without separate user approval.

Implementation order after approval:

1. Stage 4A expand migration and auth code;
2. bootstrap and source transfer during maintenance;
3. Stage 4A contract migration and tenant enforcement;
4. Stage 4B notifications;
5. Stage 4C import tooling/docs;
6. Stage 4D general CI;
7. live workflow only after external reviewer/runner setup.

## Acceptance criteria

- Every operational API is authenticated and tenant-scoped.
- Same URL can be owned independently by different users.
- Source-specific state prevents cross-user missing/removal interference.
- Notifications are consistent, deduplicated, and baseline/partial safe.
- GPT references are manually imported and fully separated from runtime.
- Normal CI is non-live.
- Live E2E requires manual approval, a dedicated runner, a fresh local reference, and exactly one apartment.
