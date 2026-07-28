# 네이버 부동산 조사 데이터 정책

## 한국어 데이터 정책

### 1. 목적과 적용 범위

이 정책은 네이버 부동산 조사 서비스의 수집, 저장, 조회, XLSX 내보내기, 로그, 백업 및 삭제에 적용한다. 초기 운영 목적은 운영자 1명이 직접 등록한 아파트 URL 1개의 공개 매물 변화를 하루 1회 확인하는 것이다. 회원 관리, 광고, 프로파일링, 연락처 마케팅, 가격 예측 또는 제3자 데이터 판매에는 사용하지 않는다.

이 문서는 기술적 기본 정책이다. 실제 운영 전에 네이버 이용약관, robots 정책, 저작권, 개인정보 및 데이터베이스 관련 법적 검토를 완료하고 허용 범위를 문서로 승인해야 한다. 법률·약관 또는 source 정책이 더 엄격하면 그 기준을 우선한다.

### 2. 파일럿 수집 제한

- 운영자 본인이 등록한 `https://fin.land.naver.com/`의 허용된 내부 URL만 처리한다.
- 활성 URL은 1개, 예약 조사는 하루 1회, 동시 브라우저는 1개로 제한한다.
- Npay 내부 article 경로를 우선하며 외부 bridge 링크를 따라가지 않는다.
- 로그인, CAPTCHA, 접근 제한, robots 정책 또는 anti-bot 통제를 우회하지 않는다.
- 원본 HTML, screenshot, cookie, 인증 정보는 영속 저장하지 않는다.
- 화면에 존재하지 않는 값을 추정하거나 보강하지 않는다.

### 3. 데이터 분류와 허용 목적

| 분류 | 예시 | 허용 목적 | 기본 보호 수준 |
|---|---|---|---|
| source 설정 | 원본 URL, 정규화 URL, hash, source ID | 동일 URL 식별, 예약 조사 | 기밀 운영 데이터 |
| 실행 메타데이터 | run ID, stage, status, selector version, 시각, 오류 코드 | 진행 상태, 장애 분석, 감사 | 내부 운영 데이터 |
| 단지·매물 snapshot | 단지명, 주소, 거래 유형, 가격, 면적, 층, 방향, 상태 | 시점 비교, 화면 조회, XLSX | 제한 데이터 |
| 중개 article 정보 | article ID, 제공자, Npay 여부, 내부 URL, 확인 시각 | 중복 제거, 매물 근거 추적 | 제한 데이터 |
| 공개 중개 정보 | 상호, 대표자, 전화번호, 등록번호, 주소 | 선택한 매물의 출처 확인 | 개인정보 가능 데이터 |
| 상세 설명과 추가 필드 | 매물 설명, 옵션, 입주, 대출, 관리비 | 운영자가 요청한 매물 비교 | 저작권·개인정보 검토 대상 |
| 변경 이벤트 | 변경 필드, 이전/이후 구조화 값 | 신규·변경·삭제·복원 감사 | 제한 데이터 |
| 운영 로그 | run/source ID, stage, count, error, duration | 안정성·누락·차단 집계 | 최소화된 운영 데이터 |

전화번호와 상세 설명은 운영 로그나 metric label에 절대 복사하지 않는다. DB 저장과 XLSX 제공은 사전 승인된 업무 목적과 보관 기간 안에서만 허용한다. source URL의 query는 로그에 남기지 않으며 DB 접근 권한이 있는 운영자만 볼 수 있다.

### 4. 최소 수집과 금지 데이터

다음 원칙을 적용한다.

- 화면과 승인된 내부 article 상세에 실제 표시된 구조화 값만 저장한다.
- 전체 HTML, 페이지 source, 브라우저 storage, cookie, 계정 정보는 저장하지 않는다.
- 전화번호는 공개 중개업소 식별 목적에 필요한 경우에만 DB에 저장하고 검색 index, 로그, 운영 보고서에는 넣지 않는다.
- 상세 설명 원문은 승인된 비교 목적에 필요한 경우에만 DB snapshot에 저장한다. 로그, 경고 메시지, ticket, chat, metric, 배포 산출물에는 복사하지 않는다.
- 자유 텍스트에 주민등록번호, 계좌, 개인 휴대전화 등 예상하지 않은 민감정보가 보이면 재배포하지 않고 해당 필드의 저장 중단과 삭제 여부를 검토한다.
- 수집되지 않은 값은 추정하지 않고 비어 있는 값으로 유지한다.

### 5. 로그 데이터 최소화

실행 로그는 안정된 `event` 이름과 다음 필드만 사용한다.

- `runId`
- `sourceId`
- `stage`
- `count`
- `error` (오류 코드만)
- `duration` (밀리초)

금지 항목은 전체 URL/query, 전화번호, 상세 설명, HTML, request/response body, stack trace 안의 페이지 내용, cookie, token, DB connection string이다. 예외를 기록할 때 `str(exception)`이나 객체 dump를 사용하지 않고 승인된 오류 코드로 변환한다. Uvicorn과 Nginx access log는 비활성화하며 외부 proxy에서도 query 없는 path만 취급한다.

### 6. 접근 통제와 전송·저장 보호

- 파일럿 DB 조회와 XLSX 다운로드 권한은 지정 운영자 1명에게만 부여한다.
- PostgreSQL과 Redis 포트는 인터넷에 공개하지 않는다.
- 원격 접속은 TLS가 적용된 승인 proxy 또는 관리 채널을 사용한다.
- `backend/.env`, DB dump, XLSX는 source control, chat, issue, 공개 공유 폴더에 올리지 않는다.
- DB 계정과 운영 비밀은 비밀 저장소에서 관리하고 담당자 변경이나 침해 의심 시 회전한다.
- 백업은 운영 DB와 같은 등급으로 암호화하고 접근·복사 기록을 남긴다.
- 개발·검증 환경에는 실제 전화번호와 상세 설명을 복제하지 않고 비식별 fixture를 사용한다.

### 7. 보관 기간 초안

다음 기간은 파일럿 기본 상한이며, 운영 전 정책 검토에서 더 짧게 조정할 수 있다.

| 데이터 | 기본 보관 상한 | 만료 처리 |
|---|---:|---|
| 운영 JSON 로그 | 30일 | rolling 삭제 |
| PostgreSQL 백업 | 14일 | 암호화 백업 만료 삭제 |
| 전화번호·상세 설명이 포함된 article snapshot | 90일 | 해당 snapshot 및 파생 export 삭제 |
| 단지·매물 snapshot과 변경 이벤트 | 180일 | 승인된 이력 목적이 없으면 삭제 또는 집계만 유지 |
| 비활성 source URL과 schedule | 비활성화 후 30일 | 관련 운영 설정 삭제 |
| 로컬 XLSX export | 다운로드 목적 달성 후 즉시, 최대 7일 | 운영 단말에서 안전 삭제 |

법적 보존 의무, 삭제 요청, source 정책 변경 또는 수집 동의 철회에 따라 더 짧은 기간이 필요하면 즉시 그 기준을 따른다. 백업 안의 만료 데이터는 다음 backup rotation에서 소멸시키고, 복구 때문에 재등장하면 만료 절차를 다시 적용한다.

### 8. 조회와 XLSX 제공

- 화면과 XLSX는 같은 backend snapshot과 aggregate를 사용한다.
- XLSX는 운영자가 선택한 source와 기간으로 제한한다.
- 전화번호와 상세 설명이 XLSX에 포함되는 경우 사전 승인된 사용 목적을 확인한다.
- XLSX 파일명, 메타데이터 또는 공유 메시지에 source URL/query나 전화번호를 넣지 않는다.
- export 파일을 이메일, 메신저 또는 외부 저장소에 올리는 행위는 이 정책의 자동 승인 범위가 아니다.
- `partial`, `failed`, `blocked` 결과를 완전한 조사 결과로 표시하지 않는다.

### 9. 수정·삭제 요청과 source 종료

삭제 또는 정정 요청을 받으면 다음 순서로 처리한다.

1. 요청 대상과 처리 권한을 확인하되 요청자의 민감정보를 운영 로그에 남기지 않는다.
2. 해당 schedule과 source를 비활성화해 추가 수집을 멈춘다.
3. article snapshot, 연락처, 상세 설명, export와 파생 데이터를 식별한다.
4. 영향 범위와 DB backup을 확인하고 명시적 승인 후 삭제 또는 정정한다.
5. 삭제 완료 시 데이터 내용이 아니라 범주, 건수, 처리 일시, 담당자만 감사 기록에 남긴다.
6. backup rotation 후 잔여 사본 소멸을 확인한다.

삭제 구현은 별도 승인된 운영 작업이어야 한다. 임의 SQL, volume 삭제 또는 `docker compose down -v`를 사용하지 않는다.

### 10. 침해·오수집 대응

전화번호, 상세 설명, URL query 또는 자격 증명이 로그나 외부 시스템에 노출되면 다음을 수행한다.

1. worker와 scheduler를 중지해 추가 처리를 막는다.
2. 노출 위치, 데이터 범주, 기간과 접근자를 확인한다.
3. 관련 로그·export의 접근을 차단하고 보존/삭제 의무를 판단한다.
4. 자격 증명 노출이면 즉시 회전한다.
5. 법적 통지와 source 제공자 대응 필요성을 검토한다.
6. 재개 전에 redaction과 로그 field allowlist를 확인하고 승인을 받는다.

차단 또는 CAPTCHA는 보안 통제로 간주하며 우회하지 않는다.

### 11. 운영 전 승인 기록

운영 기록에는 최소한 다음 항목이 있어야 한다.

- 승인된 목적과 사용자 수
- 허용 source URL 수, 실행 빈도, 동시성
- 검토한 이용약관과 robots 정책의 URL, 버전 또는 확인 시각
- 허용/금지 수집 필드
- 전화번호와 상세 설명의 처리 근거와 보관 기간
- XLSX 제공 범위와 반출 통제
- 로그·DB·백업 보관 기간
- 삭제·침해 대응 책임자
- 파일럿 시작일, 종료일, 확대 또는 종료 결정

승인 근거 문서 자체에 query가 포함된 source URL이나 전화번호를 복사하지 않는다.

---

# AI Data Governance Contract (English)

## Purpose Limitation

Use the system only for a two-week, single-operator pilot that monitors one operator-submitted Naver Pay Real Estate apartment source at most once per day. Do not use collected data for advertising, profiling, direct contact, resale, model training, price prediction, or unrelated enrichment.

## Mandatory Pre-Production Review

Before any worker or scheduler is started, record an approved review of Naver terms, robots policy, copyright/database rights, privacy obligations, allowed fields, retention, export purpose, and deletion handling. The stricter legal, contractual, or source policy always wins. Never bypass authentication, CAPTCHA, access controls, robots rules, or anti-bot measures.

## Collection Contract

```yaml
pilot_limits:
  operators: 1
  active_sources: 1
  scheduled_runs_per_day: 1
  domain_browser_concurrency: 1
allowed:
  - operator-submitted internal source identity
  - public complex and listing fields needed for comparison
  - public broker identity/contact only when approved for source verification
  - structured article details needed for the approved comparison
  - run and change metadata
forbidden:
  - raw HTML or page source persistence
  - cookies, browser storage, credentials, or authenticated content
  - inferred or enriched values not displayed by the approved source
  - external bridge traversal
```

Original listing descriptions and phone numbers may exist only in the restricted database/export scope explicitly approved for the pilot. They must never be copied to logs, metrics, traces, tickets, chat, deployment artifacts, or routine operations reports.

## Log Allowlist

```yaml
metadata:
  - event
allowed_context:
  - runId
  - sourceId
  - stage
  - count
  - error
  - duration
prohibited_values:
  - full URL or any query string
  - phone number or broker contact
  - original description or free-text payload
  - HTML, request body, response body, object dump
  - cookie, token, authorization header, connection string
```

Use stable error codes, never exception text. Disable application and frontend access logs; configure any upstream proxy to omit query data.

## Access and Export Controls

Only the designated pilot operator may query the database or download XLSX. Keep PostgreSQL and Redis private to the Compose network. Use TLS for remote access. Never commit or share `.env`, dumps, or real exports. Production data must not be copied into development fixtures. Exports must be scoped to the selected source and date range, stored locally only as long as needed, and never externally transmitted without separate approval.

## Default Retention Ceilings

```yaml
operational_logs: 30_days
encrypted_backups: 14_days
article_snapshots_with_contact_or_description: 90_days
listing_snapshots_and_change_events: 180_days
inactive_source_configuration: 30_days_after_deactivation
local_xlsx_exports: delete_when_purpose_complete_max_7_days
```

These are ceilings, not guaranteed retention periods. Apply any shorter legal, contractual, deletion-request, or source-policy requirement immediately. Data restored from backup re-enters the same expiry process.

## Deletion and Incident Contract

Deactivate the source and schedule before deleting data. Require explicit approval for record deletion, preserve only category/count/time/operator in the audit record, and let backup copies expire through the approved rotation. Never use ad hoc SQL, volume deletion, or `docker compose down -v` as a deletion workflow.

If a URL query, phone number, description, credential, or other restricted value reaches logs or an external system: stop worker/scheduler, contain access, identify categories and exposure period, rotate exposed secrets, assess notification duties, remediate the allowlist/redaction path, and require approval before resuming.

## Expansion Gate

After 14 days, use aggregate-only reporting for outcome counts, block rate, mismatch warnings, selector failures, manually confirmed false-removal decisions, and duration percentiles. Do not include record-level URLs, contacts, or descriptions. Increasing source count, schedule frequency, concurrency, users, retention, or export distribution requires a new explicit policy and operations approval.
