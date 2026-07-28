# 네이버 부동산 아파트 분석 대시보드 데모 구현 계획

> **에이전트 작업자용:** 구현 시 `superpowers:subagent-driven-development`(권장) 또는 `superpowers:executing-plans`를 사용해 체크박스 단위로 진행한다. 다만 이 저장소의 `AGENTS.md` 지침에 따라 테스트·빌드·브라우저 확인은 반드시 사용자 승인을 받은 뒤 실행한다.

**목표:** 네이버 부동산 URL을 입력하면 아파트별 매매 현황, 대표 매물, 중개사별 등록 정보와 XLSX 다운로드 흐름을 확인할 수 있는 React/Tailwind 데모 화면을 만든다.

**아키텍처:** 1차 마일스톤은 프런트엔드 전용 데모다. 실제 네이버 접속, Python API, 데이터베이스, 작업 큐는 연결하지 않고 타입이 지정된 목업 데이터와 브라우저 내 상태 전환으로 전체 UX를 시연한다. 화면 승인을 받은 뒤 별도 계획에서 FastAPI·Playwright 수집 워커·PostgreSQL을 연결한다.

**기술 스택:** React, TypeScript, Vite, Tailwind CSS, React Router, Lucide React, Recharts, SheetJS(xlsx), Vitest, React Testing Library

## 전체 제약

- 이번 계획의 실제 구현 범위는 `frontend/` 데모 껍데기까지다.
- 실제 웹 스크래핑, 로그인, CAPTCHA 처리, 백엔드 API, 데이터베이스, 배포는 이번 구현에서 제외한다.
- 아실·호갱노노의 정보 밀도와 탐색 흐름만 참고하고 로고, 문구, 색상, 이미지, 고유 레이아웃은 복제하지 않는다.
- 화면 문구는 한국어를 기본으로 한다.
- 모든 데이터는 화면 상단의 `DEMO DATA` 배지로 목업임을 명확히 표시한다.
- 데스크톱 1440px을 우선 설계하고, 768px 이하에서는 테이블을 카드 목록으로 전환한다.
- 테스트·빌드·개발 서버 실행과 브라우저 시각 확인은 계획에 명령을 기록하되 사용자 승인 전에는 실행하지 않는다.
- 사용자 승인 없는 커밋, 푸시, 배포를 하지 않는다.

---

## 1. 데모 UX 범위

### 주요 사용자 흐름

1. 사용자가 네이버 부동산 URL을 입력한다.
2. `분석 시작`을 누르면 데모 진행 상태가 `URL 확인 → 매물 수집 → 중개사 등록 정리 → 완료` 순서로 전환된다.
3. 완료 후 상단 KPI, 가격·면적 차트, 아파트별 표가 나타난다.
4. 아파트 행을 선택하면 우측 상세 패널에서 대표 매물과 중개사별 등록 내용을 확인한다.
5. `Excel 다운로드`를 누르면 목업 데이터가 3개 시트로 구성된 XLSX 파일로 내려받아진다.

### 대시보드 정보 구조

- 상단 헤더: 서비스명, `분석 대시보드`, `수집 내역`, 데모 배지
- URL 분석 카드: URL 입력, 분석 시작, 최근 실행 시간, 진행 상태
- KPI: 아파트 수, 대표 매물 수, 중개사 등록 수, 최저 매매가
- 차트: 아파트별 평균 호가, 전용면적 구성, 아파트별 중개사 등록 수
- 필터: 단지 검색, 면적, 가격대, 정렬
- 아파트 표: 단지명, 매물 수, 중개사 등록 수, 가격 범위, 대표 전용면적, 최근 확인일
- 상세 패널: 단지 요약, 대표 매물 목록, 중개사별 상세 등록, 상세 URL
- 다운로드: 전체 Excel 다운로드

---

## 2. 계획된 파일 구조

```text
frontend/
  package.json
  package-lock.json
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    app/
      App.tsx
      router.tsx
    styles/
      globals.css
    types/
      realEstate.ts
    mocks/
      demoRealEstate.ts
    components/
      ui/
        Badge.tsx
        Button.tsx
        Card.tsx
        Drawer.tsx
      layout/
        PortalHeader.tsx
        PortalShell.tsx
      analysis/
        UrlAnalysisPanel.tsx
        CrawlProgress.tsx
      dashboard/
        SummaryCards.tsx
        MarketCharts.tsx
        ApartmentFilterBar.tsx
        ApartmentTable.tsx
        ApartmentCardList.tsx
        ApartmentDetailDrawer.tsx
      export/
        ExcelDownloadButton.tsx
    pages/
      DashboardPage.tsx
    state/
      useDemoDashboard.ts
    utils/
      exportWorkbook.ts
      formatters.ts
    tests/
      setup.ts
      DashboardPage.test.tsx
      exportWorkbook.test.ts
```

각 파일은 하나의 역할만 담당한다. `DashboardPage.tsx`는 조립만 담당하고 데이터 변환, XLSX 생성, 상태 전환 로직은 각각 `utils/`와 `state/`로 분리한다.

---

### 작업 1: React/Tailwind 데모 기반 구성

**파일**

- 생성: `frontend/package.json`
- 생성: `frontend/vite.config.ts`
- 생성: `frontend/tsconfig.json`
- 생성: `frontend/index.html`
- 생성: `frontend/src/main.tsx`
- 생성: `frontend/src/app/App.tsx`
- 생성: `frontend/src/app/router.tsx`
- 생성: `frontend/src/styles/globals.css`
- 생성: `frontend/src/tests/setup.ts`

**인터페이스**

- 제공: `App(): JSX.Element`
- 제공: `router` — `/` 경로에서 `DashboardPage`를 렌더링
- 이후 작업이 사용하는 Tailwind 색상 토큰: `portal`, `surface`, `positive`, `warning`

- [ ] **1단계: Vite React TypeScript 프로젝트 파일 생성**

  실행 단계에서는 `npm create vite@latest frontend -- --template react-ts`를 사용한다. 네트워크 설치가 필요하므로 먼저 사용자 승인을 받는다.

- [ ] **2단계: 데모 의존성 정의**

  `react-router-dom`, `lucide-react`, `recharts`, `xlsx`를 런타임 의존성으로, `tailwindcss`, `@tailwindcss/vite`, `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`을 개발 의존성으로 둔다.

- [ ] **3단계: 앱 진입점과 라우터 작성**

```tsx
// frontend/src/app/App.tsx
import { RouterProvider } from "react-router-dom";
import { router } from "./router";

export function App() {
  return <RouterProvider router={router} />;
}
```

- [ ] **4단계: 전역 디자인 토큰 작성**

  배경은 연한 회색, 본문은 짙은 남색 계열, 주 행동 색은 독자적인 청록색으로 정의한다. 숫자는 `tabular-nums`를 사용하고 카드의 기본 모서리는 `rounded-2xl`로 통일한다.

- [ ] **5단계: 승인 후 기반 빌드 확인**

  명령: `npm run build`  
  예상 결과: TypeScript 오류 없이 `frontend/dist/` 생성  
  주의: 사용자 승인 전 실행 금지

- [ ] **6단계: 승인 후 커밋**

```bash
git add frontend
git commit -m "chore: scaffold dashboard demo frontend"
```

---

### 작업 2: 부동산 도메인 타입과 목업 데이터

**파일**

- 생성: `frontend/src/types/realEstate.ts`
- 생성: `frontend/src/mocks/demoRealEstate.ts`
- 생성: `frontend/src/utils/formatters.ts`

**인터페이스**

- 제공: `ApartmentSummary`
- 제공: `ListingGroup`
- 제공: `BrokerRegistration`
- 제공: `DashboardDataset`
- 제공: `demoDashboardDataset: DashboardDataset`
- 제공: `formatKoreanPrice(value: number): string`

- [ ] **1단계: 도메인 타입 정의**

```ts
export type CrawlStatus = "idle" | "running" | "completed" | "failed";

export interface BrokerRegistration {
  articleId: string;
  realtorName: string;
  provider: string;
  description: string;
  verifiedAt: string;
  articleUrl: string;
}

export interface ListingGroup {
  groupId: string;
  building: string;
  price: number;
  supplyAreaM2: number;
  exclusiveAreaM2: number;
  floor: string;
  direction: string;
  registrations: BrokerRegistration[];
}

export interface ApartmentSummary {
  complexId: string;
  complexName: string;
  address: string;
  listingGroups: ListingGroup[];
}

export interface DashboardDataset {
  sourceUrl: string;
  collectedAt: string;
  apartments: ApartmentSummary[];
}
```

- [ ] **2단계: 목업 데이터 작성**

  최소 3개 아파트, 8개 대표 매물, 20개 이상의 중개사 등록 데이터를 만든다. 첫 번째 아파트는 테스트에서 확인한 `병점역아이파크캐슬` 구조를 사용하고, 나머지는 `샘플` 접두어가 붙은 가상 단지로 만들어 실제 시세로 오인되지 않게 한다.

- [ ] **3단계: 가격·면적·날짜 포맷 함수 작성**

  원 단위 정수를 `8억 3,000` 형식으로, 면적을 `110A㎡ (전용 84.98㎡)` 형식으로 표현한다.

- [ ] **4단계: 타입 계약 테스트 작성**

```tsx
import { describe, expect, it } from "vitest";
import { demoDashboardDataset } from "../mocks/demoRealEstate";

describe("demoDashboardDataset", () => {
  it("keeps property groups separate from broker registrations", () => {
    const groups = demoDashboardDataset.apartments.flatMap(
      (apartment) => apartment.listingGroups,
    );
    const registrations = groups.flatMap((group) => group.registrations);
    expect(groups.length).toBeGreaterThan(0);
    expect(registrations.length).toBeGreaterThan(groups.length);
  });
});
```

- [ ] **5단계: 승인 후 단위 테스트 실행**

  명령: `npm run test -- src/tests/DashboardPage.test.tsx`  
  예상 결과: 목업 데이터 계약 테스트 통과  
  주의: 사용자 승인 전 실행 금지

- [ ] **6단계: 승인 후 커밋**

```bash
git add frontend/src/types frontend/src/mocks frontend/src/utils
git commit -m "feat: add real estate demo data model"
```

---

### 작업 3: 포털 레이아웃과 URL 분석 화면

**파일**

- 생성: `frontend/src/components/layout/PortalHeader.tsx`
- 생성: `frontend/src/components/layout/PortalShell.tsx`
- 생성: `frontend/src/components/analysis/UrlAnalysisPanel.tsx`
- 생성: `frontend/src/components/analysis/CrawlProgress.tsx`
- 생성: `frontend/src/state/useDemoDashboard.ts`
- 생성: `frontend/src/pages/DashboardPage.tsx`

**인터페이스**

- 제공: `useDemoDashboard()`
- 입력: 네이버 부동산 URL 문자열
- 출력: `status`, `progressStep`, `dataset`, `startDemoAnalysis(url)`

- [ ] **1단계: 독자적인 포털 헤더 구현**

  서비스명은 `집계뷰`라는 임시 데모명을 사용한다. 좌측에는 텍스트 로고, 중앙에는 내비게이션, 우측에는 `DEMO DATA` 배지를 둔다.

- [ ] **2단계: URL 입력 카드 구현**

  `https://fin.land.naver.com/`로 시작하는 URL만 데모 분석 대상으로 인정한다. 잘못된 URL은 입력창 하단에 한국어 오류문을 표시한다.

- [ ] **3단계: 데모 진행 상태 구현**

```ts
const DEMO_STEPS = [
  "URL 확인",
  "매물 목록 구성",
  "중개사 등록 정리",
  "대시보드 생성",
] as const;
```

  `startDemoAnalysis`는 실제 네트워크 요청 없이 상태만 순차 전환하고 마지막에 `demoDashboardDataset`를 노출한다.

- [ ] **4단계: 페이지 조립**

  첫 진입 시 URL 입력 카드와 데모 설명을 보여주고, 분석 완료 후 같은 페이지 아래쪽에 대시보드를 표시한다.

- [ ] **5단계: URL 검증 테스트 작성**

```tsx
it("rejects non-Naver real estate URLs", async () => {
  render(<DashboardPage />);
  await userEvent.type(screen.getByLabelText("네이버 부동산 URL"), "https://example.com");
  await userEvent.click(screen.getByRole("button", { name: "분석 시작" }));
  expect(screen.getByText("네이버 부동산 URL을 입력해 주세요.")).toBeInTheDocument();
});
```

- [ ] **6단계: 승인 후 테스트 실행 및 커밋**

  명령: `npm run test -- src/tests/DashboardPage.test.tsx`  
  예상 결과: URL 오류 상태 테스트 통과  
  주의: 실행과 커밋 모두 사용자 승인 후 진행

---

### 작업 4: 아파트별 대시보드와 필터

**파일**

- 생성: `frontend/src/components/ui/Badge.tsx`
- 생성: `frontend/src/components/ui/Button.tsx`
- 생성: `frontend/src/components/ui/Card.tsx`
- 생성: `frontend/src/components/dashboard/SummaryCards.tsx`
- 생성: `frontend/src/components/dashboard/MarketCharts.tsx`
- 생성: `frontend/src/components/dashboard/ApartmentFilterBar.tsx`
- 생성: `frontend/src/components/dashboard/ApartmentTable.tsx`
- 생성: `frontend/src/components/dashboard/ApartmentCardList.tsx`

**인터페이스**

- 입력: `DashboardDataset`
- 출력: 선택된 `complexId`
- 필터 상태: `query`, `areaRange`, `priceRange`, `sortBy`

- [ ] **1단계: KPI 계산 로직 구현**

  아파트 수, 대표 매물 수, 중개사 등록 수, 전체 최저 매매가를 `DashboardDataset`에서 계산한다. 계산 결과를 별도 API 없이 화면에서 파생한다.

- [ ] **2단계: 요약 카드 구현**

  큰 숫자, 보조 설명, 전일 대비가 아닌 `수집 기준` 표시를 사용한다. 존재하지 않는 변동률을 임의로 생성하지 않는다.

- [ ] **3단계: 차트 3종 구현**

  Recharts로 아파트별 평균 호가 막대 차트, 면적 구성 도넛 차트, 중개사 등록 수 막대 차트를 만든다. 툴팁과 축 라벨은 한국어로 표시한다.

- [ ] **4단계: 필터 바와 데스크톱 표 구현**

  필터 바는 대시보드 상단에 고정되는 형태로 만들고, 표 행 클릭 시 `complexId`를 부모에 전달한다.

- [ ] **5단계: 모바일 카드 목록 구현**

  768px 이하에서는 표 헤더를 숨기고 동일 데이터를 카드 목록으로 표현한다. 데스크톱과 모바일은 같은 필터 결과를 공유한다.

- [ ] **6단계: 필터 동작 테스트 작성**

```tsx
it("filters apartments by complex name", async () => {
  render(<DashboardPage />);
  await completeDemoAnalysis();
  await userEvent.type(screen.getByLabelText("단지 검색"), "병점역");
  expect(screen.getByText("병점역아이파크캐슬")).toBeInTheDocument();
  expect(screen.queryByText("샘플 레이크시티")).not.toBeInTheDocument();
});
```

- [ ] **7단계: 승인 후 테스트·커밋**

  명령: `npm run test -- src/tests/DashboardPage.test.tsx`  
  예상 결과: 필터 테스트 통과  
  주의: 사용자 승인 전 실행 금지

---

### 작업 5: 아파트 상세 패널과 중개사 등록 목록

**파일**

- 생성: `frontend/src/components/ui/Drawer.tsx`
- 생성: `frontend/src/components/dashboard/ApartmentDetailDrawer.tsx`
- 수정: `frontend/src/pages/DashboardPage.tsx`

**인터페이스**

- 입력: `apartment: ApartmentSummary | null`
- 입력: `open: boolean`
- 입력: `onClose(): void`
- 출력: 없음

- [ ] **1단계: 접근 가능한 우측 Drawer 구현**

  데스크톱에서는 화면 너비 520px의 우측 패널, 모바일에서는 전체 화면 패널로 표시한다. Escape 키와 닫기 버튼을 지원하고 제목을 `aria-labelledby`로 연결한다.

- [ ] **2단계: 단지 요약 탭 구현**

  주소, 대표 매물 수, 중개사 등록 수, 가격 범위, 면적 구성을 표시한다.

- [ ] **3단계: 대표 매물 그룹 구현**

  각 그룹에 동, 가격, 면적, 층, 방향, `중개사 n곳에서 등록`을 표시한다. 그룹을 펼치면 중개사 등록 목록을 보여준다.

- [ ] **4단계: 중개사 등록 상세 구현**

  중개사명, 제공업체, 확인일, 설명, 개별 매물 URL을 표시한다. 데모 URL은 새 탭 이동 대신 비활성 링크 스타일과 `데모 데이터` 안내를 사용해 실제 매물로 오인되지 않게 한다.

- [ ] **5단계: 상세 패널 테스트 작성**

```tsx
it("shows broker registrations for the selected apartment", async () => {
  render(<DashboardPage />);
  await completeDemoAnalysis();
  await userEvent.click(screen.getByRole("button", { name: /병점역아이파크캐슬 상세 보기/ }));
  expect(screen.getByRole("dialog", { name: "병점역아이파크캐슬 상세" })).toBeInTheDocument();
  expect(screen.getByText(/중개사 15곳에서 등록/)).toBeInTheDocument();
});
```

- [ ] **6단계: 승인 후 테스트·커밋**

  명령: `npm run test -- src/tests/DashboardPage.test.tsx`  
  예상 결과: 상세 패널 테스트 통과  
  주의: 사용자 승인 전 실행 금지

---

### 작업 6: 목업 데이터 XLSX 다운로드

**파일**

- 생성: `frontend/src/utils/exportWorkbook.ts`
- 생성: `frontend/src/components/export/ExcelDownloadButton.tsx`
- 생성: `frontend/src/tests/exportWorkbook.test.ts`
- 수정: `frontend/src/pages/DashboardPage.tsx`

**인터페이스**

- 제공: `buildDashboardWorkbook(dataset: DashboardDataset): WorkBook`
- 제공: `downloadDashboardWorkbook(dataset: DashboardDataset): void`
- 시트명: `아파트요약`, `대표매물`, `중개사등록`

- [ ] **1단계: XLSX 행 변환 함수 구현**

  객체를 그대로 덤프하지 않고 각 시트의 열 순서를 고정한다. 가격은 계산 가능한 숫자 열과 사용자가 읽는 한국어 표시 열을 함께 포함한다.

- [ ] **2단계: 워크북 생성 구현**

```ts
import * as XLSX from "xlsx";

export function buildDashboardWorkbook(dataset: DashboardDataset) {
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, createApartmentSheet(dataset), "아파트요약");
  XLSX.utils.book_append_sheet(workbook, createListingSheet(dataset), "대표매물");
  XLSX.utils.book_append_sheet(workbook, createBrokerSheet(dataset), "중개사등록");
  return workbook;
}
```

- [ ] **3단계: 다운로드 버튼 구현**

  분석 완료 전에는 비활성화하고, 완료 후 `naver-land-demo-YYYYMMDD.xlsx` 파일명으로 저장한다.

- [ ] **4단계: 워크북 구조 테스트 작성**

```ts
it("creates the three required worksheets", () => {
  const workbook = buildDashboardWorkbook(demoDashboardDataset);
  expect(workbook.SheetNames).toEqual(["아파트요약", "대표매물", "중개사등록"]);
});
```

- [ ] **5단계: 승인 후 테스트·수동 다운로드 확인**

  명령: `npm run test -- src/tests/exportWorkbook.test.ts`  
  예상 결과: 시트명과 행 개수 테스트 통과  
  수동 확인: 사용자가 별도 승인하면 다운로드한 XLSX를 열어 한글 시트명과 열 순서를 확인

- [ ] **6단계: 승인 후 커밋**

```bash
git add frontend/src/components/export frontend/src/utils/exportWorkbook.ts frontend/src/tests/exportWorkbook.test.ts
git commit -m "feat: export dashboard demo as xlsx"
```

---

### 작업 7: 반응형 마감과 사용자 데모 전달

**파일**

- 수정: `frontend/src/styles/globals.css`
- 수정: `frontend/src/pages/DashboardPage.tsx`
- 수정: `frontend/src/components/**/*.tsx`

**인터페이스**

- 데스크톱 기준: 1440px
- 태블릿 기준: 1024px
- 모바일 전환: 768px 이하

- [ ] **1단계: 로딩·빈 결과·오류 상태 마감**

  URL 입력 전, 진행 중, 완료, URL 오류의 네 상태를 모두 같은 화면 구조 안에서 자연스럽게 표현한다.

- [ ] **2단계: 키보드 포커스와 대비 마감**

  모든 버튼과 입력 요소에 명확한 포커스 링을 적용하고 색상만으로 상태를 구분하지 않는다.

- [ ] **3단계: 승인 후 정적 빌드**

  명령: `npm run build`  
  예상 결과: TypeScript와 Vite 빌드 성공  
  주의: 사용자 승인 전 실행 금지

- [ ] **4단계: 승인 후 데모 서버 실행**

  명령: `npm run dev -- --host 127.0.0.1 --port 5173`  
  예상 결과: `http://127.0.0.1:5173`에서 데모 화면 접근 가능

- [ ] **5단계: 승인 후 브라우저에서 사용자에게 시연**

  사용자에게 URL 입력, 진행 상태, 필터, 상세 Drawer, XLSX 다운로드 순서로 보여준다. 시각적 변경 요청을 받은 뒤에만 다음 수정을 진행한다.

- [ ] **6단계: 사용자 승인 후 최종 커밋**

```bash
git add frontend
git commit -m "feat: complete real estate dashboard demo"
```

---

## 3. 데모 완료 조건

- 첫 화면에서 서비스 목적과 네이버 부동산 URL 입력 위치가 즉시 이해된다.
- 목업 분석 완료 후 아파트별 집계와 중개사별 등록 정보를 탐색할 수 있다.
- 대표 매물 수와 중개사 등록 수가 서로 다른 개념으로 표현된다.
- 데스크톱 표와 모바일 카드가 같은 데이터를 보여준다.
- 상세 패널에서 대표 매물 → 중개사 등록의 2단계 구조가 드러난다.
- XLSX에 `아파트요약`, `대표매물`, `중개사등록` 시트가 생성되도록 계획되어 있다.
- 모든 화면에 목업 데이터임이 표시된다.
- 실제 네이버 요청이나 백엔드 의존성이 없다.

---

## 4. 데모 승인 이후 별도 계획으로 진행할 범위

1. Python FastAPI API와 PostgreSQL 데이터 모델
2. Redis 작업 큐와 Playwright 수집 워커
3. 네이버 지도 목록의 스크롤 종료 조건과 매물 그룹 수집
4. `중개사 n곳` 펼치기 및 `ArticleCardSub` 수집
5. 개별 `/articles/{articleId}` 상세 페이지 수집
6. 재시도, 접근 제한, CAPTCHA 중단 및 운영자 상태
7. 서버 측 XLSX 생성과 다운로드 이력
8. React 데모를 실제 API 응답으로 교체
9. 배포, 모니터링, 이용약관·수집 정책 검토

이 범위는 데모 UI가 승인된 뒤 별도의 구현 계획 문서로 작성한다.

---

# AI-Optimized Execution Contract (English)

## Scope

Build only a frontend demo under `frontend/`. Do not create backend, crawler, database, authentication, deployment, or live Naver requests in this milestone.

## Milestone Order

1. Scaffold Vite + React + TypeScript + Tailwind.
2. Define typed real-estate entities and clearly labeled mock data.
3. Build the portal shell and URL-analysis simulation.
4. Build dashboard summaries, charts, filters, and responsive apartment results.
5. Build the apartment detail drawer with nested broker registrations.
6. Export mock data to a three-sheet XLSX workbook.
7. After explicit user approval, run build/tests/dev server and present the visual demo.

## Required Data Separation

- `ApartmentSummary` represents a complex.
- `ListingGroup` represents one grouped physical listing shown in the portal.
- `BrokerRegistration` represents one broker/provider registration under a listing group.
- Never report listing-group count as broker-registration count.
- Use `articleId` as the future integration key for live article details.

## UI Contract

- Korean-first copy.
- Original brand identity; reference market portals only for information density and navigation patterns.
- Permanent `DEMO DATA` indicator.
- Desktop table and mobile card presentation must consume the same filtered dataset.
- Detail drawer must show the hierarchy: apartment → listing group → broker registrations.
- Excel button exports `아파트요약`, `대표매물`, and `중개사등록`.

## Approval Gates

- Do not install dependencies without approval.
- Do not run tests, builds, dev servers, or browser visual checks without approval.
- Do not commit, push, or deploy without approval.
- When visual demo approval is received, stop and write a separate backend/crawler implementation plan before adding live scraping.
