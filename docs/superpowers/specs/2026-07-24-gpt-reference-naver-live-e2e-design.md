# GPT 기준 네이버 부동산 라이브 E2E 설계서

## 한국어 설계

### 1. 목표

GPT 브라우저가 실제 네이버 부동산 화면에서 확인한 결과를 독립 기준 스냅샷으로 저장하고, 우리 서비스의 `PlaywrightNaverLandCollector`가 같은 URL에서 수집한 결과와 비교한다. 테스트는 빠른 표본 비교와 운영자가 명시적으로 실행하는 전수 비교로 분리한다.

### 2. 대상 URL과 단지 식별 기준

| 번호 | 단지명 | 네이버 단지 ID | 테스트 URL |
|---|---|---:|---|
| 1 | 신동탄포레자이 | `131197` | `case-131197` |
| 2 | 올림픽파크포레온 | `155817` | `case-155817` |
| 3 | 리센츠 | `22746` | `case-22746` |

2026-07-24 GPT 브라우저 사전 확인값은 각각 `매매/전세/월세` 기준 `53/2/1`, `597/431/385`, `214/68/55`다. 이 건수는 변동값이므로 영구 고정 기대값으로 사용하지 않고, 기준 스냅샷의 수집 시각과 함께 기록한다. 단지명과 단지 ID는 정확히 일치해야 한다.

세 URL의 전체 문자열은 다음과 같으며 테스트 케이스 목록 파일에 그대로 저장한다.

```text
case-131197=https://fin.land.naver.com/map?center=3zl7w3-2Ayhk0&zoom=15&layer=NobwRAlgJmBcYGMD2BbADgGwKYA8D6UWALgIYQZgA0YaJATiSgM5zjLrY4CSM8AjAGY%2BfAJwB2MAF9qTLPQQALAAr1GLWOFIAjOGHpEICbFT10DRrABUGhSwE80WdWACCfE0QYA7JiQQGkLyU7LECAc3tHADkAVxQtLDpdd2pPEh8-AK9rElsHLF03KWo6Yhi6LxItY1hPGKxJAF0gA
case-155817=https://fin.land.naver.com/map?center=3zo0wV-2AKg3w&zoom=14&layer=NobwRAlgJmBcYGMD2BbADgGwKYA8D6UWALgIYQZgA0YaJATiSgM5zjLrY4CSM8AjAFYBADj4B2MAF9qTLPQQALAAr1GLWOFIAjOGHpEICbFT10DRrABUGhSwE80WdWACCfE0QYA7JiQQGkLyU7LECAc3tHADkAVxQtLDpdAE4Pb19-CEDrElsHLF03KWo6Yhi6LxItY1hPGKxJAF0gA
case-22746=https://fin.land.naver.com/map?center=3zlP9R-2AJOsS&zoom=14&layer=NobwRAlgJmBcYGMD2BbADgGwKYA8D6UWALgIYQZgA0YaJATiSgM5zjLrY4CSM8ATHwDsAFgBsYAL7UmWeggAWABXqMWscKQBGcMPSIQE2Krrr7DWACoNCFgJ5osasAEEAjMaIMAdkxIJ9SF6KtliBAOZ2DgByAK4omlh0Oq4ADB7evv4QgVYkNvZYOm6S1HTEMXReJJpGsJ4xWBIAukA
```

로그와 일반 오류 메시지에는 query가 포함된 전체 URL을 출력하지 않고 케이스 ID와 단지 ID만 출력한다.

### 3. GPT 기준 스냅샷

pytest 프로세스는 GPT 브라우저 플러그인을 직접 호출할 수 없으므로, GPT 웹 탐색 결과를 JSON 기준 아티팩트로 저장해 테스트 입력으로 사용한다. 각 아티팩트는 다음 값을 포함한다.

- `schema_version`, `captured_at`, `collector: "gpt_browser_exploration"`
- 케이스 ID, 단지명, 네이버 단지 ID
- 매매·전세·월세 표시 건수
- 표본 또는 전수 매물의 매물번호, 거래 유형, 가격, 동, 층, 방향, 공급·전용면적
- 표시된 중개사 등록 수와 중개사별 매물번호
- 상세 화면의 옵션, 입주 가능일, 관리비, 방·욕실, 융자, 시스템에어컨, 중문, 식기세척기 등 실제로 표시된 추가 필드
- Npay 표시 여부와 실제로 사용한 내부 `/articles/{articleId}` 경로

동적 데이터 비교 전에 기준 스냅샷의 유효시간을 확인한다. 기본 최대 나이는 30분이다. 기준이 오래되면 데이터 불일치로 판정하지 않고 `reference_stale`로 중단해 GPT 기준을 먼저 갱신하도록 한다.

### 4. 2단계 E2E 구조

#### 4.1 표본 E2E

`RUN_LIVE_NAVER_E2E=1`일 때만 실행한다. 세 단지에서 매매·전세·월세 중 매물이 존재하는 거래 유형별로 대표 매물 1건을 선택해 단지당 최대 3건을 비교한다. 선택 기준은 GPT 스냅샷에 기록된 매물번호이며 테스트 도중 임의로 다른 매물로 대체하지 않는다.

표본 테스트는 다음을 검증한다.

1. 단지명과 단지 ID가 정확히 일치한다.
2. 거래 유형별 표시 건수가 기준 스냅샷과 일치한다.
3. 기준 표본 매물번호가 서비스 수집 결과에 존재한다.
4. 거래 유형, 가격, 동, 층, 방향, 면적을 정규화한 뒤 비교한다.
5. `중개사 n곳에서 등록했어요`의 표시 수와 실제 수집된 중개사 등록 수가 일치한다.
6. Npay 버튼이 있으면 외부 브리지 대신 네이버 내부 `/articles/{articleId}`만 사용한다.
7. 상세 화면에 표시된 추가 정보가 중복 제거 후 서비스 결과에 모두 포함된다.

#### 4.2 수동 전수 E2E

`RUN_LIVE_NAVER_FULL_E2E=1`일 때만 실행한다. 매물이 존재하는 모든 거래 유형의 가상 목록을 끝까지 순회하고, 모든 대표 매물의 중개사 패널과 중개사별 상세를 비교한다. 기본 테스트 명령과 CI에서는 실행하지 않는다.

전수 비교는 매물번호 집합, 거래 유형별 건수, 대표 매물별 중개사 수, 중개사별 상세 핵심 필드의 차이를 JSON 리포트로 남긴다. 단 하나라도 누락되면 테스트는 실패한다. 라이브 데이터가 실행 중 변경될 수 있으므로 운영자가 기준 수집 시각과 차이를 함께 검토한다.

### 5. 사용자와 유사한 탐색 속도

표본과 전수 테스트 모두 다음 규칙을 지킨다.

- 페이지 이동, 거래 유형 전환, 가상 목록 스크롤, 중개사 패널 열기, 매물 상세 열기처럼 상태를 바꾸는 각 동작 사이에 `1.0~3.0초` 균등 랜덤 지연을 한 번 둔다.
- 브라우저와 테스트 케이스를 병렬 실행하지 않고 동시 실행 수를 1로 고정한다.
- 같은 실패 동작을 빠르게 반복하지 않는다.
- CAPTCHA, 로그인 요구, 접근 제한이 감지되면 즉시 중단하고 `E2E_BLOCKED`로 분류한다.
- CAPTCHA 해결, 로그인 우회, 외부 링크 우회 또는 접근 제한 회피는 구현하지 않는다.
- 테스트 리포트에는 실제 적용된 지연 범위와 총 방문 수를 기록한다.

랜덤 지연은 테스트에서 주입 가능한 `HumanizedDelay` 경계로 분리한다. 단위 테스트에서는 가짜 대기 함수를 주입하고, 라이브 E2E에서는 실제 `asyncio.sleep(random.uniform(1.0, 3.0))`을 사용한다.

### 6. 비교 정규화와 실패 판정

- 문자열은 앞뒤 공백과 연속 공백만 정규화한다. 의미를 추론하거나 누락값을 채우지 않는다.
- 금액은 원 단위 정수로 비교한다.
- 면적은 제곱미터 기준 소수 둘째 자리까지 비교한다.
- 옵션 목록은 중복 제거 후 순서와 무관하게 비교한다.
- GPT 기준에 없는 필드는 실패 사유가 아니다. GPT 기준에 존재하지만 서비스 결과에 없는 필드는 실패다.
- 매물번호, 단지 ID, 거래 유형, 가격 불일치는 하드 실패다.
- 접근 차단과 기준 만료는 데이터 불일치와 구분된 오류 코드로 종료한다.

실패 리포트는 `temp/e2e/naver-live/<run-id>/diff.json`에 저장하며 query를 포함한 전체 URL, 전화번호, 쿠키와 인증 정보는 기록하지 않는다.

### 7. 테스트와 실행 계약

pytest marker는 `live_naver`와 `live_naver_full`을 사용한다. 환경변수가 없으면 두 테스트는 명시적으로 skip된다.

```powershell
$env:RUN_LIVE_NAVER_E2E='1'
pytest backend/tests/e2e/test_naver_live_scrape.py -m live_naver
```

```powershell
$env:RUN_LIVE_NAVER_FULL_E2E='1'
pytest backend/tests/e2e/test_naver_live_scrape.py -m live_naver_full
```

이번 구현에서는 세 URL의 GPT 표본 기준을 갱신한 뒤 표본 E2E를 실행한다. 수동 전수 E2E 코드는 구현하지만, 실제 전수 실행은 별도 명시적 실행 지시가 있을 때만 수행한다.

### 8. 예상 파일 경계

- `backend/tests/e2e/reference/gpt_naver_observations.json`: GPT 기준 스냅샷
- `backend/tests/e2e/reference_schema.py`: 기준 스냅샷 검증과 만료 확인
- `backend/tests/e2e/comparison.py`: 정규화와 diff 생성
- `backend/tests/e2e/test_naver_live_scrape.py`: 표본·전수 라이브 TC
- `backend/app/crawler/delay.py`: 사용자와 유사한 랜덤 지연 경계
- `backend/app/crawler/browser.py`: 표본/전수 수집 범위와 지연 경계 연결
- `backend/pyproject.toml`: pytest marker 등록
- `docs/testing/naver-live-e2e.md`: 한국어 우선 실행·기준 갱신 가이드

기존 수집기가 실제 DOM과 맞지 않아 표본 E2E가 실패하면 실패한 selector 또는 탐색 단계만 수정하고 같은 TC로 다시 검증한다. 관련 없는 기능과 UI는 수정하지 않는다.

---

# AI Implementation Contract (English)

## Goal

Compare production `PlaywrightNaverLandCollector` output against a versioned JSON oracle captured through GPT browser exploration for three fixed Naver Land map URLs. Provide an opt-in sampled live test and a separate opt-in exhaustive live test.

## Fixed identities

- `case-131197`: 신동탄포레자이, complex `131197`
- `case-155817`: 올림픽파크포레온, complex `155817`
- `case-22746`: 리센츠, complex `22746`

Counts, prices, listings, and broker registrations are volatile. Store them with `captured_at` and reject an oracle older than 30 minutes with `reference_stale`.

## Test tiers

- `live_naver`: enabled only by `RUN_LIVE_NAVER_E2E=1`; compare one oracle-selected article per non-empty sale/jeonse/monthly-rent trade type, at most three articles per complex.
- `live_naver_full`: enabled only by `RUN_LIVE_NAVER_FULL_E2E=1`; exhaust every non-empty trade-type list, broker group, and broker article; emit an exact JSON diff and fail on missing data.
- Neither marker belongs to the default test or CI path.

## Interaction contract

Every navigation, trade-tab switch, virtual-list scroll, broker-panel open, and article-detail open must pass through an injectable `HumanizedDelay`. Live behavior is `asyncio.sleep(random.uniform(1.0, 3.0))`. Browser concurrency and case concurrency are exactly one. Never bypass CAPTCHA, login, access restrictions, or Npay external bridges.

## Comparison contract

Exact-match complex IDs, article IDs, trade types, and normalized won prices. Normalize whitespace only, compare square-meter areas to two decimals, and compare deduplicated option sets without order. A field present in the GPT oracle but absent from production is a failure. Save sanitized diffs under `temp/e2e/naver-live/<run-id>/diff.json` without full query URLs, contact data, cookies, or credentials.

## Execution boundary

Refresh the three GPT sampled observations, then run only the sampled live suite during implementation. Implement but do not execute the exhaustive suite without an additional explicit instruction.
