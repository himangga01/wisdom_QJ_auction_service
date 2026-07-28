# GPT 수동 기준자료 형식

이 디렉터리에는 URL과 개인정보가 없는 버전 2 예시만 커밋한다. 실제 GPT
웹탐색 원본, 전체 네이버 URL manifest, 최신 정제 기준자료는 저장소 루트의
ignored `temp/e2e/reference/` 아래에만 둔다.

`example.json`은 schema와 comparator 개발용 예시이며 실제 네이버 E2E 입력으로
사용하지 않는다. 실제 입력은 다음과 같이 분리한다.

```text
temp/e2e/reference/inbox/*.json
temp/e2e/reference/case-manifest.local.json
temp/e2e/reference/current/reference.json
```

정제 기준자료에는 `sourceUrlSha256`만 들어가며 전체 URL은 들어가지 않는다.
전화번호, 원본 HTML, cookie/session 값, 긴 자유서술, 중개사 개인정보도 넣지
않는다.

## AI Execution Specification (English)

- Treat `reference.schema.json` as the version 2 input/output contract.
- Keep raw captures, the full-URL manifest, and current imported references
  under the ignored repository-local `temp/e2e/reference/` paths.
- Never use `example.json` for live navigation.
- Never add a full URL, phone number, raw HTML, cookie/session value, screenshot,
  browser profile, or sensitive narrative to a committed fixture or diff.
- Resolve a live URL only from the local manifest and verify its SHA-256 before
  collection.
