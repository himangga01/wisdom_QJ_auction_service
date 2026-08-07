# 남은 작업 완료 Implementation Plan

> **에이전트 작업자 필수 지침:** REQUIRED SUB-SKILL: 이 계획을 실행할 때는 `superpowers:subagent-driven-development` 또는 `superpowers:executing-plans`를 사용하고, 각 체크박스를 순서대로 처리한다. 사용자가 별도로 요청하지 않는 한 서브에이전트는 생성하지 않는다.

**목표:** 현재 `main`의 CI 실패를 먼저 복구한 뒤 Windows 로컬, Docker, GitHub 보호형 Live E2E, 운영 파일럿, 레거시 스키마 정리를 각각 독립 승인 단계로 완료한다.

**아키텍처:** 코드 결함 수정과 외부 환경 작업을 분리한다. P0 코드 수정은 기존 인터페이스를 유지하는 최소 변경으로 끝내고, 서버 기동·Docker·실제 네이버 접속·운영 DB 변경은 앞 단계가 통과하고 사용자가 해당 작업을 명시적으로 승인한 경우에만 실행한다.

**기술 스택:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, SQLite, React 19, TypeScript 6, Vite 8, Vitest 4, Tailwind CSS 4, GitHub Actions, PowerShell, Docker Compose, Google Chrome CDP.

## 전체 제약조건 (Global Constraints)

- 기준 브랜치는 `main`, 기준 커밋은 `a1b430800546b08b54646a4c19f2b8c25a88d02a`이다.
- 사용자 소유 `temp/`는 열람·수정·삭제·스테이징·커밋하지 않는다.
- 사용자가 승인한 단계와 그 단계에 명시된 테스트만 실행한다. 광범위한 추가 검증은 별도 승인을 받는다.
- 네이버 수집은 외부 Google Chrome의 일반 UI와 loopback CDP만 사용한다. 네이버 API 직접 호출, 직접 HTTP 수집, CAPTCHA 우회, stealth, 프록시 회전은 금지한다.
- 실제 네이버 접속은 `case-131197` 아파트 1곳만 대상으로 하며 별도 Live E2E 승인을 받은 뒤 실행한다.
- 로컬 포트는 Portal `42880`, API `42881`, Chrome CDP `42973`을 유지한다.
- Docker CDP `9222`는 Compose 내부 네트워크에만 노출하고 호스트에 게시하지 않는다.
- Docker 종료 시 `down -v`를 사용하지 않는다. DB·Redis·Chrome profile 볼륨을 삭제하지 않는다.
- 운영 DB migration, backup, restore, deploy는 각각 명시적 승인을 받은 뒤 실행한다.
- 현재 사용자 범위가 Windows 전용이므로 운영 파일럿도 별도 Linux 서버가 아닌 승인된 Windows Docker 호스트 1대를 기준으로 한다.
- Markdown 문서는 한국어를 먼저 작성하고 AI 실행용 영어 명세를 뒤에 둔다.

---

## 1. 현재 기준선

| 항목 | 현재 상태 | 완료 조건 |
|---|---|---|
| Git | `main == origin/main == a1b4308` | 수정 커밋이 `origin/main`에 반영됨 |
| 일반 CI | 실패 | Backend, Frontend, Compose contract 모두 성공 |
| Live workflow | 정의 검증 실패 | GitHub에 `Live Naver E2E` 이름으로 정상 등록 |
| Windows 로컬 | 코드·가이드 구현 | 승인된 기동 점검 성공 |
| Docker | 코드·Compose 구현, 로컬 Docker CLI 없음 | Docker Desktop 설치 후 전체 stack health 성공 |
| Live Naver E2E | 과거 reference 검증 이력만 존재 | 현재 코드로 아파트 1곳 비교 성공 |
| 레거시 listing 상태 칼럼 | 모델에 남아 있음 | 안정화 기간 후 별도 migration으로 제거 |

## 2. 실행 방식 선택

### 검토한 방식

1. **단계별 승인 방식 — 권장**
   - CI 복구 → 로컬 기동 → Docker → Live E2E → 운영 → 스키마 정리 순서로 진행한다.
   - 외부 상태 변경과 실사이트 접근을 코드 수정에서 격리할 수 있다.

2. **전체 일괄 실행**
   - 빠르게 보이지만 Docker 설치, self-hosted runner, fresh reference, 운영 승인이 동시에 필요하다.
   - 중간 실패 시 원인과 책임 범위를 분리하기 어렵기 때문에 사용하지 않는다.

3. **운영 환경부터 구성**
   - 현재 CI가 실패한 커밋을 배포 준비 대상으로 사용하게 되므로 사용하지 않는다.

### 승인 게이트

| 게이트 | 승인 대상 | 승인 전 금지 작업 |
|---|---|---|
| A | P0 코드 수정, 지정 테스트, `main` 커밋·푸시 | 파일 수정, 테스트, push |
| B | Windows 로컬 기동 점검 | 서버·Chrome 실행 |
| C | Docker 설치 후 전체 stack 점검 | image build, container 실행 |
| D | GitHub runner 구성 및 실제 1개 아파트 E2E | runner 등록, workflow dispatch, 네이버 접속 |
| E | 운영 파일럿 배포 | 운영 migration, deploy, scheduler 시작 |
| F | 레거시 칼럼 제거 | destructive schema migration |

---

### Task 1: PostgreSQL Alembic revision 칼럼 확장

**승인 게이트:** A

**Files:**
- Modify: `backend/alembic/versions/0002_listing_aggregate_source_count.py:14`
- Modify: `backend/tests/unit/test_auth_migrations.py`

**Interfaces:**
- Consumes: Alembic `op.get_bind()`, `op.alter_column()`과 기존 revision chain.
- Produces: `_widen_alembic_version_column() -> None`; PostgreSQL에서 `alembic_version.version_num`을 `VARCHAR(128)`로 확장하고 SQLite에서는 아무 작업도 하지 않는다.

- [ ] **Step 1: PostgreSQL과 SQLite 분기 테스트를 추가한다**

```python
from types import SimpleNamespace
from unittest.mock import Mock


def test_revision_0002_widens_postgresql_version_column(monkeypatch) -> None:
    migration = _load("0002_listing_aggregate_source_count.py")
    alter_column = Mock()
    monkeypatch.setattr(
        migration.op,
        "get_bind",
        lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
    )
    monkeypatch.setattr(migration.op, "alter_column", alter_column)

    migration._widen_alembic_version_column()

    alter_column.assert_called_once()
    args, kwargs = alter_column.call_args
    assert args == ("alembic_version", "version_num")
    assert kwargs["existing_type"].length == 32
    assert kwargs["type_"].length == 128
    assert kwargs["existing_nullable"] is False


def test_revision_0002_leaves_sqlite_version_column_unchanged(monkeypatch) -> None:
    migration = _load("0002_listing_aggregate_source_count.py")
    alter_column = Mock()
    monkeypatch.setattr(
        migration.op,
        "get_bind",
        lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
    )
    monkeypatch.setattr(migration.op, "alter_column", alter_column)

    migration._widen_alembic_version_column()

    alter_column.assert_not_called()
```

- [ ] **Step 2: 승인된 집중 테스트를 실행해 현재 실패를 확인한다**

Run:

```powershell
Set-Location .\backend
..\.venv\Scripts\python -m pytest tests/unit/test_auth_migrations.py -q
```

Expected: `_widen_alembic_version_column`이 없어 새 테스트 2개가 실패한다.

- [ ] **Step 3: 0002 migration 시작부에서 version 칼럼을 확장한다**

```python
def _widen_alembic_version_column() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def upgrade() -> None:
    _widen_alembic_version_column()
    with op.batch_alter_table("listing_aggregates") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_count", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch_op.alter_column("source_count", server_default=None)
```

`downgrade()`에서는 35자 revision 값이 저장된 상태에서 32자로 축소하면 실패할 수 있으므로 version 칼럼을 줄이지 않는다.

- [ ] **Step 4: 집중 테스트를 다시 실행한다**

Run:

```powershell
Set-Location .\backend
..\.venv\Scripts\python -m pytest tests/unit/test_auth_migrations.py -q
```

Expected: 전체 PASS.

---

### Task 2: Frontend CI 이식성과 삭제 매물 분류 복구

**승인 게이트:** A

**Files:**
- Modify: `frontend/src/tests/authClient.test.ts:34`
- Modify: `frontend/src/tests/domain.test.ts`
- Modify: `frontend/src/utils/listingHistory.ts:174-178`

**Interfaces:**
- Consumes: `compareListingSnapshots(before, after, options)`와 `ListingGroup.removedAt`.
- Produces: 명시적 `removedAt`이 있는 과거 매물은 `removed`; 근거 없는 미관측 매물은 `unobserved`로 유지한다.

- [ ] **Step 1: Node 22 호환 Response fixture로 변경한다**

```typescript
new Response('file', {
  status: 200,
  headers: { 'Content-Disposition': 'attachment; filename="result.xlsx"' },
})
```

애플리케이션 `apiFile()`은 변경하지 않는다. 테스트가 검증하는 same-origin credentials 계약도 유지한다.

- [ ] **Step 2: 근거 없는 미관측이 삭제로 바뀌지 않는 회귀 테스트를 추가한다**

기존 demo fixture 테스트는 `124735-sale-118`이 `removed`인지 계속 확인한다. 같은 테스트 block에 아래 검증을 추가한다.

```typescript
const unobservedBefore = {
  ...previous[0]!,
  groupId: 'unobserved-without-removed-at',
  removedAt: undefined,
}
const absenceComparison = compareListingSnapshots([unobservedBefore], [])

expect(absenceComparison.removed).toHaveLength(0)
expect(absenceComparison.unobserved.map((item) => item.before?.groupId))
  .toContain('unobserved-without-removed-at')
```

- [ ] **Step 3: 승인된 Frontend 집중 테스트를 실행해 삭제 분류 실패를 확인한다**

Run:

```powershell
npm --prefix .\frontend run test -- src/tests/authClient.test.ts src/tests/domain.test.ts
```

Expected: Blob runtime 오류 또는 `124735-sale-118` 삭제 기대값 실패가 재현된다.

- [ ] **Step 4: 명시적 삭제와 단순 미관측을 분리한다**

```typescript
for (const beforeListing of before) {
  if (afterById.has(beforeListing.groupId)) continue
  if (beforeListing.removedAt) {
    removed.push({ ...beforeListing, status: 'removed' })
  } else {
    unobserved.push({ before: beforeListing })
  }
}
```

`partial` 안전 계약을 유지하기 위해 `removedAt`이 없는 항목은 삭제로 추정하지 않는다.

- [ ] **Step 5: Frontend 집중 테스트를 다시 실행한다**

Run:

```powershell
npm --prefix .\frontend run test -- src/tests/authClient.test.ts src/tests/domain.test.ts
```

Expected: 두 테스트 파일 전체 PASS.

---

### Task 3: GitHub Live E2E workflow 정의 복구

**승인 게이트:** A

**Files:**
- Modify: `.github/workflows/live-naver-e2e.yml:47-94`
- Modify: `backend/tests/unit/test_deployment_contract.py`

**Interfaces:**
- Consumes: GitHub `runner.temp`, `github.run_id`, 기존 PowerShell E2E runner.
- Produces: job-level 평가에서는 `runner` context를 사용하지 않고, runner가 배정된 step 안에서만 artifact directory를 구성한다.

- [ ] **Step 1: workflow context 위치 계약 테스트를 추가한다**

```python
def test_live_workflow_uses_runner_temp_only_inside_steps() -> None:
    workflow = _compose(REPOSITORY_ROOT / ".github/workflows/live-naver-e2e.yml")
    job = workflow["jobs"]["live-one-apartment"]
    assert "LIVE_E2E_ARTIFACT_DIR" not in job.get("env", {})

    run_step = next(
        step for step in job["steps"]
        if step["name"] == "Run protected one-apartment live E2E"
    )
    assert "${{ runner.temp }}" in run_step["env"]["LIVE_E2E_ARTIFACT_DIR"]

    upload_step = next(
        step for step in job["steps"]
        if step["name"] == "Upload sanitized live comparison"
    )
    assert "${{ runner.temp }}" in upload_step["with"]["path"]
```

- [ ] **Step 2: 승인된 workflow 계약 테스트를 실행해 현재 실패를 확인한다**

Run:

```powershell
Set-Location .\backend
..\.venv\Scripts\python -m pytest tests/unit/test_deployment_contract.py -q
```

Expected: job-level env에 `LIVE_E2E_ARTIFACT_DIR`가 있어 새 테스트가 실패한다.

- [ ] **Step 3: artifact directory를 step 범위로 이동한다**

job-level `env`에서 `LIVE_E2E_ARTIFACT_DIR`를 제거하고 실행 step에 다음을 추가한다.

```yaml
      - name: Run protected one-apartment live E2E
        shell: powershell
        env:
          LIVE_E2E_ARTIFACT_DIR: ${{ runner.temp }}\wisdom-naver-live-e2e\${{ github.run_id }}
```

업로드 step은 동일 경로를 직접 사용한다.

```yaml
          path: |
            ${{ runner.temp }}\wisdom-naver-live-e2e\${{ github.run_id }}\summary.json
            ${{ runner.temp }}\wisdom-naver-live-e2e\${{ github.run_id }}\diff.json
```

- [ ] **Step 4: workflow 계약 테스트를 다시 실행한다**

Run:

```powershell
Set-Location .\backend
..\.venv\Scripts\python -m pytest tests/unit/test_deployment_contract.py -q
```

Expected: 전체 PASS.

---

### Task 4: P0 통합 확인, 커밋, push, 자동 CI 확인

**승인 게이트:** A

**Files:**
- Verify only: Task 1~3에서 수정한 파일
- Do not stage: `temp/`

**Interfaces:**
- Consumes: Task 1~3의 수정 결과.
- Produces: `main`의 CI 성공 커밋과 GitHub에 정상 등록된 `Live Naver E2E` workflow.

- [ ] **Step 1: 승인된 집중 테스트만 한 번에 실행한다**

```powershell
Set-Location .\backend
..\.venv\Scripts\python -m pytest tests/unit/test_auth_migrations.py tests/unit/test_deployment_contract.py -q
Set-Location ..
npm --prefix .\frontend run test -- src/tests/authClient.test.ts src/tests/domain.test.ts
```

Expected: Backend 집중 테스트와 Frontend 두 파일 모두 PASS.

- [ ] **Step 2: Frontend production build를 실행한다**

```powershell
npm --prefix .\frontend run build
```

Expected: exit code 0. 기존 chunk-size warning은 실패로 간주하지 않는다.

- [ ] **Step 3: diff 범위를 확인한다**

```powershell
git diff --check
git status --short
git diff -- backend/alembic/versions/0002_listing_aggregate_source_count.py backend/tests/unit/test_auth_migrations.py frontend/src/tests/authClient.test.ts frontend/src/tests/domain.test.ts frontend/src/utils/listingHistory.ts .github/workflows/live-naver-e2e.yml backend/tests/unit/test_deployment_contract.py
```

Expected: 승인된 파일과 이 계획서만 변경되어 있고 `temp/`는 untracked 상태로 유지된다.

- [ ] **Step 4: 승인된 파일만 스테이징하고 커밋한다**

```powershell
git add -- backend/alembic/versions/0002_listing_aggregate_source_count.py backend/tests/unit/test_auth_migrations.py frontend/src/tests/authClient.test.ts frontend/src/tests/domain.test.ts frontend/src/utils/listingHistory.ts .github/workflows/live-naver-e2e.yml backend/tests/unit/test_deployment_contract.py docs/superpowers/plans/2026-08-07-remaining-work-execution.md
git commit -m "fix: restore CI portability and workflow validation"
```

- [ ] **Step 5: `main`을 push하고 자동 CI만 확인한다**

```powershell
git push origin main
$ciRun = gh run list --workflow CI --branch main --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $ciRun --exit-status
```

Expected: Backend, Frontend, Compose contract 성공. Live workflow는 push에서 실제 네이버 작업을 실행하지 않으며 GitHub workflow 목록에 `Live Naver E2E`로 등록된다.

- [ ] **Step 6: 원격 동기화를 확인한다**

```powershell
git rev-parse HEAD
git rev-parse origin/main
git status --short --branch
gh workflow view "Live Naver E2E" --yaml
```

Expected: `HEAD == origin/main`; worktree에는 사용자 소유 `temp/`만 남아 있고 Live workflow YAML 조회가 성공한다.

---

### Task 5: Windows 로컬 무수집 기동 점검

**승인 게이트:** B

**Files:**
- Verify only: `scripts/start.ps1`, `scripts/status.ps1`, `scripts/stop-local.ps1`
- Verify only: `backend/.env.local.example`

**Interfaces:**
- Consumes: 설치된 Python 3.12~3.14, Node.js 22, Google Chrome.
- Produces: Portal/API/Chrome readiness가 정상인 로컬 실행 증거. 네이버 분석은 실행하지 않는다.

- [ ] **Step 1: 필수 실행 파일 버전만 확인한다**

```powershell
python --version
node --version
npm --version
. .\scripts\runtime-common.ps1
$installedChrome = Find-InstalledGoogleChrome
if (-not $installedChrome) { throw 'Google Chrome is not installed' }
$installedChrome
```

Expected: Python 3.12~3.14, Node 22, npm, Google Chrome 확인.

- [ ] **Step 2: 로컬 모드로 기동한다**

```powershell
.\scripts\start.ps1 -Mode local
```

Expected: 전용 Chrome, migration, API, Portal이 시작되고 포트 `42973`, `42881`, `42880`을 사용한다.

- [ ] **Step 3: 상태와 health만 확인한다**

```powershell
.\scripts\status.ps1
Invoke-RestMethod http://127.0.0.1:42881/api/health
Invoke-WebRequest http://127.0.0.1:42880/healthz
```

Expected: API/Portal 성공, browser readiness 정상. 분석 URL 제출이나 네이버 접속은 하지 않는다.

- [ ] **Step 4: 로컬 프로세스를 정상 종료한다**

```powershell
.\scripts\stop-local.ps1
.\scripts\status.ps1
```

Expected: 프로젝트가 시작한 프로세스만 종료되고 사용자 기본 Chrome profile은 영향받지 않는다.

---

### Task 6: Windows Docker 전체 stack 무수집 점검

**승인 게이트:** C

**선행 조건:** Task 4 성공, 사용자가 WSL 2와 Docker Desktop을 설치하고 Docker Desktop을 실행한 상태.

**Files:**
- Runtime config only: ignored `backend/.env`
- Verify only: `docker-compose.production.yml`
- Verify only: `docs/setup/docker-setup.md`

**Interfaces:**
- Consumes: Docker Desktop, WSL 2, production Compose file.
- Produces: PostgreSQL, Redis, migrate, API, worker, scheduler, frontend, Chrome sidecar health 증거. 네이버 분석은 실행하지 않는다.

- [ ] **Step 1: Docker 설치 상태를 확인한다**

```powershell
docker version
docker compose version
```

Expected: client/server와 Compose version이 모두 출력된다. 실패하면 코드 변경 없이 사용자 설치 단계로 되돌린다.

- [ ] **Step 2: Docker용 로컬 비밀 설정을 준비한다**

```powershell
Copy-Item .\backend\.env.example .\backend\.env
$bootstrapBytes = New-Object byte[] 48
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bootstrapBytes)
$bootstrapToken = [Convert]::ToBase64String($bootstrapBytes)
```

`backend/.env`의 example `AUTH_BOOTSTRAP_TOKEN`을 `$bootstrapToken` 값으로 교체하고 PostgreSQL 자격정보와 `DATABASE_URL`을 일치시킨다. 파일은 Git에 추가하지 않는다.

- [ ] **Step 3: production Compose를 기동한다**

```powershell
.\scripts\start.ps1 -Mode docker
```

Expected: migration 성공 후 API/worker/scheduler/frontend가 시작되고 Chrome sidecar가 healthy가 된다.

- [ ] **Step 4: 서비스와 health만 확인한다**

```powershell
docker compose --env-file .\backend\.env -f .\docker-compose.production.yml ps
Invoke-RestMethod http://127.0.0.1:42881/api/health
Invoke-WebRequest http://127.0.0.1:42880/healthz
```

Expected: PostgreSQL/Redis/Chrome healthy, migrate 성공 종료, API/Portal 성공. 호스트에서 CDP `9222`에 직접 접속할 수 없어야 한다.

- [ ] **Step 5: 볼륨을 보존하며 종료한다**

```powershell
docker compose --env-file .\backend\.env -f .\docker-compose.production.yml down
```

Expected: container와 network만 종료되고 `postgres_data`, `redis_data`, `chrome_profile` 볼륨은 유지된다.

---

### Task 7: 보호형 GitHub Live E2E 환경과 아파트 1곳 실행

**승인 게이트:** D

**선행 조건:** Task 4 성공, Windows self-hosted runner 준비, 최신 reference 생성 승인.

**Files:**
- Configure externally: GitHub Environment `naver-live-e2e`
- Configure externally: Windows runner labels `self-hosted`, `windows`, `naver-e2e`
- Runner-local only: case manifest와 GPT reference
- Verify only: `.github/workflows/live-naver-e2e.yml`

**Interfaces:**
- Consumes: case ID `case-131197`, 30분 이내 fresh reference, loopback CDP `http://127.0.0.1:42973`.
- Produces: 개인정보가 제거된 `summary.json`, `diff.json`; 실제 URL·중개사 연락처·주소·등록번호는 artifact에 포함하지 않는다.

- [ ] **Step 1: GitHub 보호 설정을 구성한다**

- Environment 이름을 `naver-live-e2e`로 고정한다.
- deployment branch policy는 `main`만 허용한다.
- required reviewer를 설정한다.
- 영속 Windows runner에는 `self-hosted`, `windows`, `naver-e2e` label을 모두 설정한다.

- [ ] **Step 2: runner-local 경로를 GitHub Environment variables로 등록한다**

- `NAVER_E2E_CASE_MANIFEST_PATH`: checkout 바깥 manifest 절대경로.
- `NAVER_E2E_REFERENCE_PATH`: checkout 바깥 fresh reference 절대경로.
- 두 파일과 전용 Chrome profile은 runner 계정만 읽을 수 있도록 제한한다.

- [ ] **Step 3: 전용 Chrome과 reference freshness를 확인한다**

```powershell
.\scripts\start-naver-browser.ps1
.\scripts\status.ps1
```

Expected: CDP `http://127.0.0.1:42973` 정상. reference의 `capturedAt`은 실행 시작 시각 기준 30분 이내이고 미래 시각이 아니다.

- [ ] **Step 4: 사용자가 최종 대상과 Live 실행을 다시 승인한다**

승인 요청에는 `case-131197`, `includeDetails=true`, `delayProfile=normal`, 실행 예상 시간, 네이버 실접속 발생 사실을 명시한다. 이 승인이 없으면 다음 step을 실행하지 않는다.

- [ ] **Step 5: GitHub Actions에서 한 번만 수동 실행한다**

입력값은 다음으로 고정한다.

```text
caseId=case-131197
includeDetails=true
delayProfile=normal
approvalPhrase=RUN_ONE_APARTMENT
ref=main
```

- [ ] **Step 6: 차단 신호와 결과를 확인한다**

Expected:

- CAPTCHA, 로그인 요구, 403/429, 접근 제한이면 즉시 `blocked`로 종료한다.
- 우회·자동 재시도·속도 상향을 하지 않는다.
- 성공 시 아파트/거래유형/매물 ID/중개사 등록 수/상세정보 비교가 허용 오차 계약 안에 있다.
- artifact에는 full URL, 연락처, 주소, 등록번호, 장문 설명이 없다.

---

### Task 8: 단일 사용자 운영 파일럿 배포

**승인 게이트:** E

**선행 조건:** Task 4, Task 6, Task 7 성공.

**Files:**
- Follow: `docs/operations/runbook.md`
- Follow: `docs/operations/data-policy.md`
- Runtime config only: production secret store and deployment environment

**Interfaces:**
- Consumes: green CI image/commit, 검증된 migration, PostgreSQL backup 위치, 허용된 단일 source URL.
- Produces: 14일간 단일 사용자·단일 URL·하루 최대 1회·동시성 1의 운영 기록.

- [ ] **Step 1: 배포 전 정책 승인 기록을 확보한다**

기록 항목은 검토자, 검토일, 근거 문서 버전, 허용 수집 필드, 보존 기간, XLSX 제공 목적이다. 하나라도 없으면 worker와 scheduler를 시작하지 않는다.

- [ ] **Step 2: 운영 DB backup과 복구 책임자를 확인한다**

`pg_dump --format=custom`으로 암호화 보관할 위치, checksum 기록 위치, 복구 책임자와 복구 승인자를 기록한다. 기존 운영 데이터가 존재하고 backup 실행이 승인된 경우 아래 순서로 수행한다.

```powershell
docker compose --env-file .\backend\.env -f .\docker-compose.production.yml stop scheduler worker api
docker compose --env-file .\backend\.env -f .\docker-compose.production.yml exec -T postgres pg_dump -U postgres -d wisdom_auction --format=custom --file=/tmp/wisdom_auction.dump
docker compose --env-file .\backend\.env -f .\docker-compose.production.yml cp postgres:/tmp/wisdom_auction.dump .\backups\wisdom_auction.dump
Get-FileHash .\backups\wisdom_auction.dump -Algorithm SHA256
docker compose --env-file .\backend\.env -f .\docker-compose.production.yml start api worker scheduler
```

backup이 없는 신규 파일럿 DB라면 이 step은 `신규 DB, 기존 데이터 없음`으로 운영 기록에 남기고 restore 명령은 실행하지 않는다.

- [ ] **Step 3: green commit을 배포하고 migration을 1회 실행한다**

승인된 Windows Docker 호스트의 저장소를 green commit으로 맞춘 뒤 다음 명령을 실행한다.

```powershell
git fetch origin main
git pull --ff-only origin main
.\scripts\start.ps1 -Mode docker
```

`start.ps1`가 실행하는 `migrate`가 API/worker/scheduler보다 먼저 성공해야 한다. 실패하면 API/worker/scheduler를 시작하지 않고 DB 내용을 변경하는 임의 복구를 하지 않는다.

- [ ] **Step 4: API부터 단계적으로 시작한다**

다음 명령으로 API health, Portal health와 Compose 상태를 확인한다.

```powershell
docker compose --env-file .\backend\.env -f .\docker-compose.production.yml ps
Invoke-RestMethod http://127.0.0.1:42881/api/health
Invoke-WebRequest http://127.0.0.1:42880/healthz
```

API health → Chrome health → worker → scheduler → Portal 순으로 판정한다. `CRAWL_CONCURRENCY=1`, 활성 source URL 1개, 예약 하루 최대 1회를 유지한다.

- [ ] **Step 5: 14일 파일럿 결과를 집계한다**

집계 항목은 completed/partial/failed/blocked 건수, block 비율, listing/broker count mismatch, selector mismatch, 수동 확인한 오삭제 판정, p50/p95 실행시간이다. URL·연락처·매물 장문 설명은 보고서에 포함하지 않는다.

---

### Task 9: 안정화 이후 레거시 ListingGroup 상태 칼럼 제거

**승인 게이트:** F

**선행 조건:** 최소 1회 green release와 14일 파일럿 완료, `SourceListingState` 데이터 백업 확인.

**Files:**
- Create: `backend/alembic/versions/0010_drop_legacy_listing_group_state.py`
- Modify: `backend/app/models/entities.py:184-187`
- Modify: `backend/tests/unit/test_model_constraints.py`
- Verify: `backend/app/services/persistence_service.py:620-628`

**Interfaces:**
- Consumes: source별 상태의 단일 진실 원천 `SourceListingState`.
- Produces: `listing_groups`에서 더 이상 사용하지 않는 `first_seen_at`, `last_seen_at`, `state`, `missing_count` 제거. 매물 생명주기는 source별 테이블만 사용한다.

- [ ] **Step 1: 모델 계약 테스트를 먼저 변경한다**

```python
def test_listing_group_has_no_global_lifecycle_columns() -> None:
    columns = Base.metadata.tables["listing_groups"].c
    assert "first_seen_at" not in columns
    assert "last_seen_at" not in columns
    assert "state" not in columns
    assert "missing_count" not in columns
```

- [ ] **Step 2: 승인된 모델 테스트를 실행해 실패를 확인한다**

Run:

```powershell
Set-Location .\backend
..\.venv\Scripts\python -m pytest tests/unit/test_model_constraints.py -q
```

Expected: 네 칼럼이 현재 모델에 있어 실패한다.

- [ ] **Step 3: ORM 모델과 신규 그룹 생성 인자를 정리한다**

`ListingGroup`에서 네 `mapped_column`을 제거하고 `persistence_service.py`의 신규 `ListingGroup(...)` 생성에서 동일 인자를 제거한다. `SourceListingState` 생성과 상태 전이는 변경하지 않는다.

- [ ] **Step 4: 0010 migration을 작성한다**

`upgrade()`는 SQLite와 PostgreSQL 모두에서 `op.batch_alter_table("listing_groups")`를 사용해 네 칼럼을 제거한다. `downgrade()`는 nullable 칼럼을 먼저 복원하고 `source_listing_states`를 다음 규칙으로 집계한 뒤 non-null 제약을 복원한다.

- `first_seen_at`: 동일 listing group의 source 상태 중 최솟값.
- `last_seen_at`: 동일 listing group의 source 상태 중 최댓값.
- `missing_count`: 동일 listing group의 source 상태 중 최댓값.
- `state`: 하나라도 `active`면 `active`, 그렇지 않고 하나라도 `missing`이면 `missing`, 나머지는 `removed`.
- source 상태가 없는 비정상 listing group은 migration을 중단하고 `RuntimeError`를 발생시킨다.

source별 여러 상태를 하나의 global 상태로 축약하면 원래 의미를 완전히 복원할 수 없다는 경고를 migration docstring에 기록한다.

- [ ] **Step 5: 승인된 migration·모델 집중 테스트를 실행한다**

```powershell
Set-Location .\backend
..\.venv\Scripts\python -m pytest tests/unit/test_model_constraints.py tests/integration/test_source_listing_state.py -q
```

Expected: 전체 PASS. PostgreSQL migration은 후속 자동 CI의 ephemeral DB에서 `alembic upgrade head`로 확인한다.

- [ ] **Step 6: 별도 커밋과 CI를 거친다**

```powershell
git add -- backend/alembic/versions/0010_drop_legacy_listing_group_state.py backend/app/models/entities.py backend/app/services/persistence_service.py backend/tests/unit/test_model_constraints.py
git commit -m "refactor: remove legacy global listing state"
git push origin main
```

Expected: 일반 CI 전체 성공. 이 migration은 Task 1~8과 같은 커밋에 포함하지 않는다.

---

## 3. 완료 판정

- [ ] 일반 CI의 Backend, Frontend, Compose contract가 모두 성공했다.
- [ ] GitHub가 `Live Naver E2E` workflow를 정상 등록했다.
- [ ] Windows 로컬 모드가 네이버 접속 없이 health 점검을 통과했다.
- [ ] Docker production Compose가 네이버 접속 없이 전체 health 점검을 통과했다.
- [ ] 별도 승인된 `case-131197` 한 곳의 Live E2E가 성공하거나 차단 상태를 안전하게 보고했다.
- [ ] 운영 파일럿을 승인한 경우 14일 결과와 개인정보 없는 집계 보고가 완료됐다.
- [ ] 안정화 조건이 충족된 경우에만 레거시 global listing state 칼럼을 제거했다.
- [ ] 모든 커밋에서 `temp/`, 비밀정보, full Naver URL이 제외됐다.

---

# AI Execution Specification (English)

## Objective

Close the remaining work in approval-gated phases: restore CI first, then verify Windows local runtime, verify Docker runtime, configure and run one protected live Naver case, operate an optional single-user pilot, and only then remove legacy global listing lifecycle columns.

## Mandatory Order and Gates

1. **Gate A — CI remediation:** Tasks 1 through 4. Requires approval for edits, the listed focused tests, commit, and direct push to `main`.
2. **Gate B — Windows local smoke:** Task 5. Starts local Chrome/API/Portal but performs no Naver analysis.
3. **Gate C — Docker smoke:** Task 6. Requires user-installed WSL 2 and Docker Desktop. Never use `down -v`.
4. **Gate D — Protected live E2E:** Task 7. Requires a second explicit approval immediately before dispatch. Run `case-131197` only.
5. **Gate E — Production pilot:** Task 8. Requires deployment, migration, backup, and policy approval.
6. **Gate F — Destructive schema cleanup:** Task 9. Requires one green release plus the 14-day pilot and a backup.

## P0 Patch Contract

### Alembic

- In revision `0002_listing_aggregate_source_count`, widen `alembic_version.version_num` from `String(32)` to `String(128)` on PostgreSQL before any other upgrade operation.
- Do nothing on SQLite.
- Do not shrink the column in downgrade.
- Do not rename existing revision IDs.

### Frontend

- Replace the jsdom `Blob` used as a Node `Response` body with the string body `"file"`; production `apiFile()` stays unchanged.
- In `compareListingSnapshots`, an item missing from `after` is `removed` only when `beforeListing.removedAt` is explicit. Otherwise it remains `unobserved`.
- Preserve partial-run safety and the existing explicit removal fixture.

### GitHub Workflow

- Remove `${{ runner.temp }}` from job-level `env`.
- Define `LIVE_E2E_ARTIFACT_DIR` in the protected run step.
- Use `${{ runner.temp }}` directly in artifact upload paths.
- The workflow remains `workflow_dispatch`-only, `main`-only, protected by environment `naver-live-e2e`, and bound to labels `self-hosted`, `windows`, `naver-e2e`.

## Focused Verification Contract

Run only these local commands under Gate A:

```powershell
Set-Location .\backend
..\.venv\Scripts\python -m pytest tests/unit/test_auth_migrations.py tests/unit/test_deployment_contract.py -q
Set-Location ..
npm --prefix .\frontend run test -- src/tests/authClient.test.ts src/tests/domain.test.ts
npm --prefix .\frontend run build
git diff --check
```

Push triggers the repository's existing full CI. Do not manually trigger the live workflow during Gate A.

## Runtime and Live Safety Contract

- Local endpoints remain Portal `127.0.0.1:42880`, API `127.0.0.1:42881`, CDP `127.0.0.1:42973`.
- Docker Chrome CDP remains internal at `chrome:9222`.
- Never inspect, modify, stage, or delete `temp/`.
- Never call Naver data APIs or direct HTTP acquisition endpoints.
- Stop immediately on CAPTCHA, login requirement, access restriction, 403, or 429. Never bypass or automatically retry.
- Live artifacts must exclude full URLs, broker contact details, broker addresses, registration numbers, raw HTML, cookies, profiles, and long descriptions.

## Deferred Schema Cleanup Contract

After the stabilization gate, create revision `0010_drop_legacy_listing_group_state` and remove `ListingGroup.first_seen_at`, `last_seen_at`, `state`, and `missing_count`. `SourceListingState` remains the only lifecycle source. Keep this migration in a separate commit and validate it through the existing PostgreSQL CI migration step.
