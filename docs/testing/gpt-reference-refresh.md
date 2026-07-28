# GPT 웹탐색 기준자료 수동 갱신

이 절차는 사용자가 직접 만든 로컬 JSON을 검증·정제하는 개발 도구다. 서비스
런타임, Backend API, 일반 CI는 GPT/OpenAI를 호출하지 않으며 기준자료를
production API나 DB에 업로드하지 않는다.

## 한국어 운영 가이드

### 1. 한 아파트 조사

사용자가 GPT 웹탐색에서 승인한 네이버 지도 URL의 아파트 한 곳만 조사한다.
결과를 `backend/tests/e2e/reference.schema.json`의 버전 2 형식에 맞춰 로컬
JSON으로 저장한다.

필수 상위 필드는 다음과 같다.

```json
{
  "schemaVersion": "2",
  "captureTool": "gpt_browser_manual",
  "mode": "sample",
  "capturedAt": "2026-07-29T12:00:00+09:00",
  "normalizationVersion": "2",
  "cases": []
}
```

`capturedAt`에는 반드시 timezone을 포함한다. 현재 시각보다 2분을 초과해
미래인 값은 거부한다. `caseId`는 영문 대소문자, 숫자, `.`, `_`, `-`만 사용해
1~100자로 작성한다. 각 case에는 `caseId`,
`sourceUrlSha256`, 단지 식별자·이름·거래 건수와 article 목록을 넣는다. 전체
URL, 전화번호, 중개사 주소·등록번호, 원본 HTML, cookie/session, screenshot,
Chrome profile, 민감한 긴 자유서술은 입력 JSON에 넣지 않는다.

### 2. 로컬 파일 분리

실제 파일은 Git에서 제외된 다음 경로만 사용한다.

```text
temp/e2e/reference/inbox/<capture>.json
temp/e2e/reference/case-manifest.local.json
temp/e2e/reference/current/reference.json
```

manifest 형식은 다음과 같다.

```json
{
  "schemaVersion": "1",
  "cases": [
    {
      "caseId": "case-local-id",
      "sourceUrl": "<전체 https://fin.land.naver.com/map?... URL>"
    }
  ]
}
```

입력 JSON과 manifest의 `caseId` 집합은 정확히 같아야 한다. URL 문자열의
UTF-8 바이트를 SHA-256으로 계산한 소문자 hex 값을 입력 JSON의
`sourceUrlSha256`에 기록한다. URL은 편집하거나 재정렬하지 않고 실제
manifest 문자열 그대로 해시한다.

### 3. 반입 실행

capture 후 30분 안에 저장소 루트에서 실행한다.

```powershell
.\scripts\import-gpt-reference.ps1 `
  -InputPath .\temp\e2e\reference\inbox\<capture>.json `
  -ManifestPath .\temp\e2e\reference\case-manifest.local.json
```

도구는 다음 항목을 fail-closed 방식으로 검사한다.

- version 2 schema와 허용되지 않은 추가 필드
- timezone, 미래 시각 2분 제한, 실행 시작 기준 30분 freshness
- 안전 문자만 사용하는 case ID와 출력 경로 경계
- 중복 case ID와 case 내부 중복 article ID
- 정확한 네이버 지도 URL host/path와 URL SHA-256
- 전화번호, HTML, cookie/session 형태, 500자를 넘는 자유서술
- canonical 가격·면적·날짜 공백·option tag·detail key/value
- `requiredDetailFields`의 관리비·융자·면적·구조·검증시각 등 허용 key
  allowlist와 중개사명·주소·등록번호·연락처 계열 key 차단

성공하면 `temp/e2e/reference/current/reference.json`만 갱신한다. 결과에는 전체
URL이 없고 `sourceUrlSha256`과 canonical payload의 `payloadSha256`만 있다.
stdout에는 case 수와 payload hash만 나오며 입력·manifest·전체 URL은 나오지
않는다.

### 4. 사용자 확인과 live E2E 승인

사용자는 성공 요약과 정제 결과의 case ID·단지·article 범위를 확인한다. 이
반입 성공은 네이버 실환경 실행 승인이 아니다. 같은 case로 Chrome live E2E를
실행하려면 별도 승인을 받고, 최신 reference와 manifest hash가 일치하는지 다시
검사해야 한다.

## AI Execution Specification (English)

1. Accept only a user-provided local version 2 JSON capture and a local manifest.
2. Do not call GPT, OpenAI, Naver, a production API, or a production database.
3. Require timezone-aware `capturedAt` no older than 30 minutes at import
   start and no more than two minutes in the future.
4. Reject schema violations, duplicate case/article IDs, manifest case mismatch,
   non-Naver-map URLs, URL-hash mismatch, phone numbers, raw HTML,
   cookie/session material, long free-form text, unsafe case IDs, and any
   broker-name/address/registration/contact detail key.
5. Normalize whitespace, integer-won prices, decimal areas, dates, option tags,
   and allowlisted detail keys/values. Remove identical normalized detail
   duplicates and reject conflicting or non-allowlisted detail keys.
6. Serialize sorted-key compact UTF-8 JSON. Compute `payloadSha256` over the
   canonical payload before adding `payloadSha256`.
7. Write only `temp/e2e/reference/current/reference.json`; never log input,
   manifest content, source URLs, or sensitive rejected values.
8. Treat import success as preparation only. Do not run live E2E without a
   separate explicit approval.
